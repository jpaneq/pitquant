# ruff: noqa: E501
"""Walk-forward replay of the daily routine's rule over history (ADR-0044): did the algorithm's call — UP (entry justified), DOWN (score ≤ sell threshold) or NEUTRAL — match what the price did?

* At each sampled past session T the SAME rule engine as the live routine sees ONLY bars known at the close of T (``AnalyzerService.technicals(sid, T)``). Price-only rules are used (trend, 200-day
  trend, 6-month momentum, nearest support): valuation and fundamentals are skipped because they are not available point-in-time for most tickers (they are listed as ``missing_rules``).
* Outcomes use only bars AFTER T: end-of-horizon return (direction) and, for UP calls, first touch of target/stop (``routine.outcome``). Immature windows are not scored.
* The sealed holdout (2022-10-01 → 2025-09-30) is never touched: a decision inside it, or whose window reaches it, is skipped and counted.
* RETROSPECTIVE: prices come from an unofficial free source downloaded after the fact; overlapping windows are not independent observations; no costs. Nothing here is validated or tuned.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.analyzer.service import AnalyzerService, clear_cache
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.positions import review as engine
from pitquant.positions import routine as rt
from pitquant.simulation.service import restated_bars

BACKTEST_VERSION = "routine-backtest-1"
SENSITIVITY_K = (0.3, 0.5, 0.7, 1.0)
MIN_N = 10
CALL = {"ADD": "UP", "SELL": "DOWN", "HOLD": "NEUTRAL"}


def context_at(svc: AnalyzerService, sid: str, at: datetime, price: float) -> engine.Context | None:
    """Price-only context built from bars known at ``at``; ``None`` when there is not enough history."""
    tech = svc.technicals(sid, at)
    if tech.get("status") != "OK":
        return None
    ind = tech.get("indicators", {})
    zones = (tech.get("support_resistance") or {}).get("supports", [])
    below = [z for z in zones if z.get("upper") is not None and z["upper"] < price]
    return engine.Context(
        price=price, atr14=ind.get("atr14"), trend_state=(tech.get("trend") or {}).get("state"), close_vs_sma200=ind.get("close_vs_sma200"), close_vs_sma50=ind.get("close_vs_sma50"),
        ret_6m=(tech.get("momentum") or {}).get("ret126"), rsi14=ind.get("rsi14"), vol_annual=(tech.get("risk") or {}).get("vol63"), support_lower=float(max(below, key=lambda z: z["upper"])["lower"]) if below else None,
    )  # fmt: skip


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def backtest_security(
    session: Session, settings: Settings, sid: str, ticker: str, market: str, start: date, end: date, *, step_sessions: int = 21, now: datetime | None = None
) -> tuple[list[dict[str, Any]], dict[str, int]]:  # fmt: skip
    now = now or utc_now()
    ho = settings.validation.final_holdout
    cal = get_calendar(rt.MARKET_EXCHANGE.get(market) or "XNYS")
    svc = AnalyzerService(session, settings)
    md = load_market(session, sid, now)
    skipped = {"holdout": 0, "no_context": 0, "immature": 0}
    if md.series.n_bars == 0:
        return [], skipped
    idx = list(md.bars.index)
    last_bar = idx[-1]
    rows: list[dict[str, Any]] = []
    closes = md.bars["close"].astype(float)
    for d in [x for x in idx if start <= x <= end][::step_sessions]:
        if d < cal.first_session or d > cal.last_session:
            continue
        if ho.start <= d <= ho.end:
            skipped["holdout"] += 1
            continue
        price = float(closes.loc[d])
        ctx = context_at(svc, sid, cal.session_close(d), price)
        if ctx is None:
            skipped["no_context"] += 1
            continue
        bars, _ = restated_bars(md, d, now)
        for h in rt.HORIZONS:
            h_end = d + relativedelta(months=h)
            if d < ho.start <= h_end:  # this horizon's window would reach the sealed holdout
                skipped["holdout"] += 1
                continue
            if h_end > last_bar:
                skipped["immature"] += 1
                continue
            rv = engine.review(
                engine.Position(
                    price, 1.0, datetime.combine(d, datetime.min.time(), tzinfo=now.tzinfo), h
                ),
                ctx,
                datetime.combine(d, datetime.min.time(), tzinfo=now.tzinfo),
            )
            win = bars[bars.index <= h_end]
            if win.empty:
                skipped["immature"] += 1
                continue
            ret_h = float(win["close"].iloc[-1]) / price - 1.0
            row: dict[str, Any] = {
                "ticker": ticker,
                "market": market,
                "date": d,
                "horizon": h,
                "call": CALL[rv["recommendation"]],
                "score": rv["score"],
                "ret_h": ret_h,
                "max_adverse": float(win["low"].min()) / price - 1.0,
                "state": None,
            }
            lv = rt.levels(price, ctx, h)
            if rv["recommendation"] == "ADD" and lv is not None:
                o = rt.outcome(
                    bars,
                    price,
                    lv["target_price"],
                    lv["stop_price"],
                    h_end,
                    datetime.combine(h_end, datetime.min.time(), tzinfo=now.tzinfo),
                )
                row |= {
                    "state": o["state"],
                    "target_pct": lv["target_pct"],
                    "stop_pct": lv["stop_pct"],
                }
                sens = {}
                for k in SENSITIVITY_K:
                    tp = max(rt.PARAMS["target_floor"], k * lv["sigma_horizon"])
                    sens[k] = rt.outcome(
                        bars,
                        price,
                        price * (1 + tp),
                        lv["stop_price"],
                        h_end,
                        datetime.combine(h_end, datetime.min.time(), tzinfo=now.tzinfo),
                    )["state"]
                row["sensitivity"] = sens
            rows.append(row)
        if len(rows) % 400 == 0:
            clear_cache()  # per-date engine caches hold full market frames
    clear_cache()
    return rows, skipped


def _rate(k: int, n: int) -> str:
    if n < MIN_N:
        return f"  (N={n}<10)"
    lo, hi = wilson(k, n)
    return f"{k / n:>5.0%} [{lo:.0%}-{hi:.0%}]"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for h in rt.HORIZONS:
        hs = [r for r in rows if r["horizon"] == h]
        base_up = sum(1 for r in hs if r["ret_h"] > 0)
        cell: dict[str, Any] = {
            "n": len(hs),
            "base_up": base_up,
            "mean_ret": mean(r["ret_h"] for r in hs) if hs else None,
        }
        for call in ("UP", "NEUTRAL", "DOWN"):
            cs = [r for r in hs if r["call"] == call]
            cell[call] = {
                "n": len(cs),
                "up": sum(1 for r in cs if r["ret_h"] > 0),
                "down": sum(1 for r in cs if r["ret_h"] < 0),
                "mean_ret": mean(r["ret_h"] for r in cs) if cs else None,
            }
        ups = [r for r in hs if r["call"] == "UP" and r["state"]]
        cell["UP"]["states"] = {
            s: sum(1 for r in ups if r["state"] == s)
            for s in ("TARGET_HIT", "STOP_HIT", "AMBIGUOUS_STOP", "EXPIRED")
        }
        cell["UP"]["n_levels"] = len(ups)
        cell["UP"]["sens"] = {
            str(k): sum(1 for r in ups if r["sensitivity"][k] == "TARGET_HIT")
            for k in SENSITIVITY_K
        }
        out[h] = cell
    return out


def render(
    rows: list[dict[str, Any]],
    skipped: dict[str, int],
    universe: dict[str, str],
    now: datetime,
    step: int,
    start: date,
    end: date,
) -> str:
    L: list[str] = []
    w = L.append
    w("=" * 100)
    w(
        f"INFORME DE BACKTEST DE LA REGLA DE LA RUTINA · {now:%Y-%m-%d %H:%M} UTC · {BACKTEST_VERSION} / {engine.ENGINE_VERSION}"
    )
    w("=" * 100)
    w(
        "AVISO: RETROSPECTIVO. Precios de una fuente gratuita NO oficial descargados a posteriori; la regla usa solo datos conocidos en cada fecha (sin mirar el futuro) pero NO está validada,"
    )
    w(
        "no hay costes, y las ventanas solapadas NO son observaciones independientes (las muestras efectivas son mucho menores que N). Es una lectura de tendencias, no una promesa."
    )
    w("")
    w(
        "SESGO DE SUPERVIVENCIA: la lista de valores son empresas ACTUALES y grandes (no la composición del índice en cada fecha); las que se hundieron o salieron no están. Eso infla la tasa base de subida:"
    )
    w(
        "lo que importa es la ventaja de la regla sobre esa tasa base, no el porcentaje absoluto de aciertos."
    )
    w("")
    w("1. QUÉ SE MIDE")
    w("-" * 100)
    w(
        "  La regla emite por valor, fecha y horizonte una PREVISIÓN: SUBE (entrada justificada), BAJA (puntuación <= umbral de venta) o NEUTRAL. Se compara con lo que hizo el precio después:"
    )
    w(
        "  - dirección: rentabilidad al final del horizonte (positiva / negativa) frente a la tasa base (cuántas veces subió en general)."
    )
    w(
        "  - para SUBE: primer contacto del objetivo/stop calculados con la volatilidad (como en la rutina real)."
    )
    w(
        f"  Muestreo cada {step} sesiones entre {start} y {end}. Reglas solo de precio (tendencia, media 200, momentum 6 m, soporte); valoración y fundamentales no se usan."
    )
    w(
        f"  Holdout 2022-10-01 → 2025-09-30 SIN TOCAR: decisiones omitidas por tocarlo: {skipped['holdout']}. Sin contexto suficiente: {skipped['no_context']}. Ventanas inmaduras: {skipped['immature']}."
    )
    w("")
    w("2. VALORES USADOS")
    w("-" * 100)
    for t, info in sorted(universe.items()):
        w(f"  {t:<8} {info}")
    w("")
    s = summarize(rows)
    w("3. RESULTADOS POR HORIZONTE")
    w("-" * 100)
    for h in rt.HORIZONS:
        c = s[h]
        if not c["n"]:
            w(f"  {h:>2} m: sin observaciones")
            continue
        w(
            f"  Horizonte {h} meses · observaciones {c['n']} · tasa base de subida {_rate(c['base_up'], c['n'])} · rentabilidad media {c['mean_ret']:+.1%}"
        )
        for call, label in (("UP", "SUBE   "), ("NEUTRAL", "NEUTRAL"), ("DOWN", "BAJA   ")):
            x = c[call]
            ok = x["up"] if call == "UP" else x["down"] if call == "DOWN" else x["up"]
            what = "subió" if call != "DOWN" else "bajó"
            w(
                f"      {label} N={x['n']:>5}  acierto ({what}) {_rate(ok, x['n'])}  rentabilidad media {('n/d' if x['mean_ret'] is None else f'{x["mean_ret"]:+.1%}')}"
            )
        st = c["UP"]["states"]
        nl = c["UP"]["n_levels"]
        if nl:
            w(
                f"      SUBE con objetivo/stop: N={nl}  objetivo {_rate(st['TARGET_HIT'], nl)}  stop {_rate(st['STOP_HIT'] + st['AMBIGUOUS_STOP'], nl)}  vencida {_rate(st['EXPIRED'], nl)}"
            )
        w("")
    w("4. LECTURA (orientativa)")
    w("-" * 100)
    notes: list[str] = []
    for h in rt.HORIZONS:
        c = s[h]
        if c["UP"]["n"] >= MIN_N and c["n"] >= MIN_N:
            base, p_up = c["base_up"] / c["n"], c["UP"]["up"] / c["UP"]["n"]
            notes.append(
                f"{h} m: cuando la regla dice SUBE, el precio subió {p_up:.0%} de las veces frente a {base:.0%} en general ({p_up - base:+.0%} de ventaja)"
                + (" → sin ventaja visible." if p_up - base < 0.03 else ".")
            )
        if c["DOWN"]["n"] >= MIN_N:
            notes.append(
                f"{h} m: cuando dice BAJA, bajó {c['DOWN']['down'] / c['DOWN']['n']:.0%} de las veces (rentabilidad media {c['DOWN']['mean_ret']:+.1%})."
            )
    if not notes:
        notes.append("Muestra insuficiente para sacar conclusiones.")
    for n_ in notes:
        w(f"  - {n_}")
    w("")
    w(
        "5. SENSIBILIDAD DEL OBJETIVO (solo SUBE; % que cumple objetivo según target_k) — NO ajustar parámetros mirando solo esto: riesgo de sobreajuste"
    )
    w("-" * 100)
    w("  horizonte   " + "   ".join(f"k={k}" for k in SENSITIVITY_K) + "     (N)")
    for h in rt.HORIZONS:
        u = s[h]["UP"]
        nl = u["n_levels"]
        w(
            f"  {h:>3} m       "
            + "   ".join(
                f"{(u['sens'][str(k)] / nl if nl >= MIN_N else float('nan')):>5.0%}"
                for k in SENSITIVITY_K
            )
            + f"     {nl}"
        )
    w("")
    w("6. POR MERCADO Y PERIODO (dirección de las llamadas SUBE; horizonte 3 m)")
    w("-" * 100)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["horizon"] == 3:
            groups[f"{r['market']}"].append(r)
            groups["≤2022-09" if r["date"] <= date(2022, 9, 30) else "≥2025-10"].append(r)
    for g, rs in sorted(groups.items()):
        up = [r for r in rs if r["call"] == "UP"]
        base = sum(1 for r in rs if r["ret_h"] > 0)
        w(
            f"  {g:<10} observaciones {len(rs):>5} · base {_rate(base, len(rs))} · SUBE N={len(up):>4} acierto {_rate(sum(1 for r in up if r['ret_h'] > 0), len(up))}"
        )
    w("")
    w("FIN DEL INFORME")
    return "\n".join(L) + "\n"


def run_backtest(
    session: Session,
    settings: Settings,
    universe: dict[str, list[str]] | None = None,
    *,
    start: date = date(2012, 1, 2),
    step_sessions: int = 21,
    now: datetime | None = None,
    max_tickers: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Backtest every ticker of the routine universe that has enough price history; returns (plain-text report, machine-readable summary)."""
    now = now or utc_now()
    uni = universe or rt.load_universe()
    rows: list[dict[str, Any]] = []
    skipped = {"holdout": 0, "no_context": 0, "immature": 0}
    used: dict[str, str] = {}
    seen: set[str] = set()
    for market, tickers in uni.items():
        for t in tickers:
            base = t.upper().rsplit(".", 1)[0] if "." in t else t.upper()
            if base in seen or (max_tickers is not None and len(seen) >= max_tickers):
                continue
            sid, why = rt.eligibility(session, base)
            if sid is None:
                used[base] = f"{market}: no usado ({why.split(':')[0]})"
                continue
            seen.add(base)
            md_last = load_market(session, sid, now).last_session
            rs, sk = backtest_security(
                session,
                settings,
                sid,
                base,
                market,
                start,
                md_last or now.date(),
                step_sessions=step_sessions,
                now=now,
            )
            rows += rs
            for k, v in sk.items():
                skipped[k] += v
            first = min((r["date"] for r in rs), default=None)
            used[base] = f"{market}: {len(rs)} observaciones ({first} → {md_last})"
    text = render(rows, skipped, used, now, step_sessions, start, now.date())
    return text, {
        "version": BACKTEST_VERSION,
        "rows": len(rows),
        "skipped": skipped,
        "summary": {str(h): v for h, v in summarize(rows).items()},
    }
