# ruff: noqa: E501
"""Plain-text report of the daily routine (ADR-0042), written to be pasted back so the parameters that are not working can be re-tuned. Facts only: N is always shown and
no rate is quoted from fewer than ``MIN_N`` closed predictions; the hints are orientative and say so."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.db.models_positions import PaperPosition
from pitquant.db.models_routine import DailyEvaluation, DailyPick, DailyVirtualEvaluation
from pitquant.positions import review as engine
from pitquant.positions import routine as rt
from pitquant.positions import service as ps

MIN_N = 10
HINT_N = 5
LINE = "-" * 100


def _pct(v: float | None, d: int = 1) -> str:
    return "  n/d" if v is None else f"{v * 100:+.{d}f}%"


def _px(v: float | None) -> str:
    return "n/d" if v is None else f"{v:,.2f}"


def build_report(
    session: Session, settings: Settings, now: datetime | None = None, days: int = 14
) -> str:
    now = now or utc_now()
    out: list[str] = []
    w = out.append
    w("=" * 100)
    w(
        f"INFORME DE LA RUTINA DIARIA DE COMPRAS SIMULADAS · {now:%Y-%m-%d %H:%M} UTC · {rt.PARAMS_VERSION} / {engine.ENGINE_VERSION}"
    )
    w("=" * 100)
    w(
        "AVISO: simulación sin dinero real. Las reglas y parámetros NO están validados con backtest y nada de esto es una predicción de un modelo entrenado ni consejo de inversión."
    )
    w(
        f"Las muestras pequeñas no prueban nada: no se calcula ninguna tasa con menos de {MIN_N} predicciones cerradas."
    )
    w("")
    w("1. PARÁMETROS EN USO (para reajustar)")
    w(LINE)
    for k, v in rt.PARAMS.items():
        w(f"  {k}: {v}")
    w(
        f"  umbral vender: puntuación <= {engine.SELL_AT:+.1f} · umbral ampliar/entrar: puntuación >= {engine.ADD_AT:+.1f} · estiramiento máx. {engine.OVEREXTENDED_ATR} ATR sobre la media 50 · RSI máx. 70"
    )
    for b, ws in engine.WEIGHTS.items():
        w(f"  pesos horizonte {b}: " + ", ".join(f"{k}={v}" for k, v in ws.items()))
    w("")

    picks = list(session.scalars(select(DailyPick).order_by(DailyPick.run_date, DailyPick.market)))
    recent = [pk for pk in picks if pk.run_date >= (now - timedelta(days=days)).date()]
    w("2. DATOS NO ACCESIBLES")
    w(LINE)
    last_by_market: dict[str, DailyPick] = {}
    for pk in picks:
        last_by_market[pk.market] = pk
    unavailable: dict[str, dict[str, str]] = defaultdict(dict)
    for pk in recent:
        for t, why in (pk.unavailable or {}).items():
            unavailable[pk.market][t] = why
    if not unavailable:
        w("  (ninguno en el periodo)")
    for m in (*rt.MARKET_ORDER, "BTC"):
        if unavailable.get(m):
            w(f"  {m}: {len(unavailable[m])} valores sin datos utilizables:")
            for t, why in sorted(unavailable[m].items())[:15]:
                w(f"    - {t}: {why}")
            if len(unavailable[m]) > 15:
                w(f"    … y {len(unavailable[m]) - 15} más")
    w("")

    w(f"3. ACTIVIDAD DE LOS ÚLTIMOS {days} DÍAS (un valor por mercado y día)")
    w(LINE)
    if not recent:
        w("  Sin actividad: la rutina aún no se ha ejecutado.")
    for pk in recent:
        head = f"  {pk.run_date} {pk.market:<10}"
        if pk.status == "NO_DATA":
            w(
                f"{head} SIN DATOS ({', '.join(f'{t}' for t in list(pk.unavailable)[:4])}{'…' if len(pk.unavailable) > 4 else ''})"
            )
            continue
        w(
            f"{head} {pk.ticker:<6} precio {_px(pk.price)}"
            + (f" [{pk.price_freshness}]" if pk.price_freshness else "")
        )
        for d in pk.decisions:
            if d["decision"] == "BUY":
                w(
                    f"      {d['horizon_months']:>2} m  COMPRA  entrada {_px(d['entry_price'])}  objetivo {_px(d['target_price'])} ({_pct(d['target_pct'])})  stop {_px(d['stop_price'])} ({_pct(-d['stop_pct'])})  puntuación {d['score']:+.1f}"
                )
            else:
                w(
                    f"      {d['horizon_months']:>2} m  no compra  puntuación {d['score']:+.1f} · {d['reason'][:110]}"
                )
    w("")

    sel: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    for pk in picks:
        for d in pk.decisions:
            sel[(pk.market, d["horizon_months"])][0 if d["decision"] == "BUY" else 1] += 1
    w("4. SELECTIVIDAD DE LA REGLA DE ENTRADA (todas las jornadas)")
    w(LINE)
    w("  mercado      horizonte  compras  sin compra")
    for (m, h), (n_buy, n_skip) in sorted(sel.items()):
        w(f"  {m:<12} {h:>4} m     {n_buy:>6}   {n_skip:>9}")
    if not sel:
        w("  (sin datos)")
    w("")

    positions = rt.routine_positions(session)
    finals = {
        e.position_id: e
        for e in session.scalars(select(DailyEvaluation).where(DailyEvaluation.week_key == "FINAL"))
    }
    latest: dict[str, DailyEvaluation] = {}
    for e in session.scalars(select(DailyEvaluation).order_by(DailyEvaluation.evaluated_at)):
        latest[e.position_id] = e
    w("5. PREDICCIONES ABIERTAS (evaluación semanal)")
    w(LINE)
    openp = [
        p
        for p in positions
        if p.position_id not in finals
        and not ps.fold(ps.events_of(session, p.position_id))["closed"]
    ]
    if not openp:
        w("  (ninguna)")
    for p in sorted(openp, key=lambda x: x.opened_at):
        info = rt.parse_note(p.note)
        ev = ps.events_of(session, p.position_id)[0]
        tgt = ev.price * (1 + (p.target_return or 0))
        last_ev = latest.get(p.position_id)
        prog = (
            "sin evaluar aún"
            if last_ev is None
            else f"{last_ev.week_key}: precio {_px(last_ev.price)} ({_pct(last_ev.return_pct)}) progreso hacia objetivo {_pct(last_ev.target_progress, 0)}"
        )
        left = (p.opened_at + timedelta(days=30.44 * p.horizon_months) - now).days
        w(
            f"  {info['market']:<10} {info['ticker']:<6} {p.horizon_months:>2} m  abierta {p.opened_at:%Y-%m-%d}  entrada {_px(ev.price)}  objetivo {_px(tgt)}  stop {_px(p.stop_price)}  quedan ~{left} d  | {prog}"
        )
    w("")

    w("6. PREDICCIONES CERRADAS")
    w(LINE)
    closed = [(p, finals[p.position_id]) for p in positions if p.position_id in finals]
    if not closed:
        w("  (ninguna todavía: la primera cierra cuando toque objetivo, stop o venza su horizonte)")
    names = {
        "TARGET_HIT": "OBJETIVO CUMPLIDO",
        "STOP_HIT": "STOP",
        "AMBIGUOUS_INTRABAR": "AMBIGUA (intradía)",
        "EXPIRED": "VENCIDA",
    }
    for p, e in sorted(closed, key=lambda x: x[1].evaluated_at):
        info = rt.parse_note(p.note)
        w(
            f"  {info['market']:<10} {info['ticker']:<6} {p.horizon_months:>2} m  {names[e.state]:<18} resultado {_pct(e.return_pct)}  fecha {e.outcome_date}  mejor {_pct(e.max_favorable)}  peor {_pct(e.max_adverse)}"
        )
    w("")

    w("7. RESUMEN POR MERCADO Y HORIZONTE (predicciones cerradas)")
    w(LINE)
    groups: dict[tuple[str, int], list[tuple[PaperPosition, DailyEvaluation]]] = defaultdict(list)
    for p, e in closed:
        groups[(rt.parse_note(p.note)["market"], p.horizon_months)].append((p, e))
    w(
        "  mercado      hor.   N   objetivo  stop  vencida   aciertos     retorno medio   días medios"
    )
    for (m, h), rows in sorted(groups.items()):
        rows_n = len(rows)
        cnt = {k: sum(1 for _, e in rows if e.state == k) for k in names}
        stops = cnt["STOP_HIT"] + cnt["AMBIGUOUS_INTRABAR"]
        rate = f"{cnt['TARGET_HIT'] / rows_n:>7.0%}" if rows_n >= MIN_N else "  (N<10)"
        gaps = [(e.outcome_date - p.opened_at.date()).days for p, e in rows if e.outcome_date]
        w(
            f"  {m:<12} {h:>3} m {rows_n:>3}   {cnt['TARGET_HIT']:>6}  {stops:>4}  {cnt['EXPIRED']:>7}   {rate}      {_pct(mean(e.return_pct for _, e in rows)):>8}        {mean(gaps) if gaps else float('nan'):>6.0f}"
        )
    if not groups:
        w("  (sin predicciones cerradas)")
    w("")

    virt_final = list(
        session.scalars(
            select(DailyVirtualEvaluation).where(DailyVirtualEvaluation.week_key == "FINAL")
        )
    )
    pick_market = {pk.pick_id: pk.market for pk in picks}
    acc: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: {"buy_n": 0, "buy_ok": 0, "no_n": 0, "no_ok": 0}
    )
    for cp, ce in closed:
        cell = acc[(rt.parse_note(cp.note)["market"], cp.horizon_months)]
        cell["buy_n"] += 1
        cell["buy_ok"] += 1 if ce.state == "TARGET_HIT" else 0
    for ve in virt_final:
        cell = acc[(pick_market.get(ve.pick_id, "?"), ve.horizon_months)]
        cell["no_n"] += 1
        cell["no_ok"] += 0 if ve.state == "TARGET_HIT" else 1
    w("8. ACIERTO DE TODAS LAS DECISIONES (comprar y NO comprar cuentan igual)")
    w(LINE)
    w(
        "  Compra acertada = objetivo cumplido. No compra acertada = el objetivo NO se habría cumplido (stop o plazo vencido). No compra fallida = oportunidad perdida (se habría cumplido)."
    )
    w("  mercado      hor.   compras cerradas (acertadas)    no compras valoradas (acertadas)")
    for (m, h), c in sorted(acc.items()):
        bt = (
            f"{c['buy_n']:>3} ({c['buy_ok'] / c['buy_n']:.0%})"
            if c["buy_n"] >= MIN_N
            else f"{c['buy_n']:>3} (N<10)"
        )
        nt = (
            f"{c['no_n']:>3} ({c['no_ok'] / c['no_n']:.0%})"
            if c["no_n"] >= MIN_N
            else f"{c['no_n']:>3} (N<10)"
        )
        w(f"  {m:<12} {h:>3} m   {bt:<30}   {nt}")
    if not acc:
        w("  (todavía ninguna decisión cerrada)")
    open_virtual = sum(
        1
        for pk in picks
        for d in pk.decisions
        if d["decision"] == "NO_ORDER" and d.get("hypothetical")
    ) - len(virt_final)
    w(f"  No compras aún en evaluación: {max(open_virtual, 0)}")
    w("")

    w("9. PUNTOS A REVISAR (orientativos; no concluyentes con N pequeña)")
    w(LINE)
    hints: list[str] = []
    for (m, h), rows in sorted(groups.items()):
        rows_n = len(rows)
        if rows_n < HINT_N:
            continue
        t_rate = sum(1 for _, e in rows if e.state == "TARGET_HIT") / rows_n
        s_rate = sum(1 for _, e in rows if e.state in ("STOP_HIT", "AMBIGUOUS_INTRABAR")) / rows_n
        x_rate = sum(1 for _, e in rows if e.state == "EXPIRED") / rows_n
        tag = f"{m} {h} m (N={rows_n}{', N<10: muy poco fiable' if rows_n < MIN_N else ''})"
        if t_rate < 0.35 and x_rate >= 0.4:
            hints.append(
                f"{tag}: pocos objetivos y muchas vencidas ({t_rate:.0%} objetivo, {x_rate:.0%} vencidas) → el objetivo parece demasiado ambicioso: probar un target_k menor."
            )
        if s_rate > 0.5:
            hints.append(
                f"{tag}: {s_rate:.0%} acaban en stop → el stop parece demasiado ajustado: probar un stop_k / stop_atr_mult mayor, o endurecer la entrada."
            )
        if t_rate > 0.8:
            hints.append(
                f"{tag}: {t_rate:.0%} cumplen objetivo → el objetivo puede ser conservador: probar un target_k mayor."
            )
    for (m, h), c in sorted(acc.items()):
        if c["no_n"] >= HINT_N and c["no_ok"] / c["no_n"] < 0.4:
            hints.append(
                f"{m} {h} m: {1 - c['no_ok'] / c['no_n']:.0%} de las NO compras eran oportunidades perdidas (N={c['no_n']}) → la regla de entrada puede ser demasiado estricta."
            )
        if c["buy_n"] >= HINT_N and c["buy_ok"] / c["buy_n"] < 0.35:
            hints.append(
                f"{m} {h} m: solo {c['buy_ok'] / c['buy_n']:.0%} de las compras cumplen objetivo (N={c['buy_n']}) → la regla de entrada puede ser demasiado laxa o el objetivo demasiado ambicioso."
            )
    for (m, h), (n_buy, n_skip) in sorted(sel.items()):
        if n_buy == 0 and n_skip >= 10:
            hints.append(
                f"{m} {h} m: {n_skip} análisis sin ninguna compra → la regla de entrada puede ser demasiado estricta para ese horizonte."
            )
    blocked = [
        m
        for m in (*rt.MARKET_ORDER, "BTC")
        if m in last_by_market and all(x.status == "NO_DATA" for x in picks if x.market == m)
    ]
    for m in blocked:
        hints.append(
            f"{m}: todos los días sin datos utilizables → no se puede evaluar nada ahí hasta tener precios (ver sección 2)."
        )
    if not hints:
        hints.append("Aún no hay evidencia suficiente para sugerir cambios de parámetros.")
    for hint in hints:
        w(f"  - {hint}")
    w("")
    w("FIN DEL INFORME")
    return "\n".join(out) + "\n"
