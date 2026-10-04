# ruff: noqa: E501
"""Plain-text reports of the backtest (ADR-0045): a full report (per value, per decision family, quality of the signal, variants, proposals) and the per-decision log. Facts and arithmetic only: the proposals are
generated from the numbers above them and are suggestions to be re-tested, never applied."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from itertools import pairwise
from pathlib import Path
from statistics import mean
from typing import Any

from pitquant.positions import backtest as bt
from pitquant.positions import backtest_p0 as bp0
from pitquant.positions import review as engine
from pitquant.positions import routine as rt

LINE = "-" * 110
H = rt.HORIZONS
PRE_END = date(2022, 9, 30)
POST_START = date(2025, 10, 1)


def _rate(k: int | None, n: int) -> str:
    if k is None or n < bt.MIN_N:
        return f"(N={n}<10)"
    lo, hi = bt.wilson(k, n)
    return f"{k / n:>4.0%} [{lo:.0%}-{hi:.0%}]"


def _pct(v: float | None) -> str:
    return "n/d" if v is None else f"{v:+.1%}"


def _edge(rate: float | None, base: float, n: int) -> str:
    return "n/d" if rate is None or n < bt.MIN_N else f"{rate - base:+.1%}"


def region(market: str, exchange: str | None) -> str:
    if exchange in (None, "XNYS"):
        return "EE. UU." if market != "IBEX" else "España"
    return {
        "XMAD": "España",
        "XTKS": "Asia-Pacífico",
        "XHKG": "Asia-Pacífico",
        "XASX": "Asia-Pacífico",
        "XTSE": "Canadá",
    }.get(exchange, "Europa")


def _calls(rows: list[dict[str, Any]], key: str = "call") -> dict[int, str]:
    return {i: r[key] for i, r in enumerate(rows)}


def write_detail(rows: list[dict[str, Any]], out_dir: Any, now: datetime) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"backtest_decisiones_{now:%Y-%m-%d}.txt"
    lines = [
        f"DETALLE DE TODAS LAS DECISIONES DEL BACKTEST · {now:%Y-%m-%d %H:%M} UTC · {bt.BACKTEST_VERSION}",
        "Una línea por valor, fecha y horizonte. Columnas: valor | fecha | horizonte | precio | LLAMADA(puntuación) | en base a qué (regla=valor→aporte) | qué pasó (rentabilidad al fin del horizonte, peor caída, mejor subida) | objetivo/stop si fue SUBE",
        "RETROSPECTIVO · reglas sin validar · ver el informe principal para las advertencias.",
        "",
    ]
    for r in sorted(rows, key=lambda x: (x["ticker"], x["date"], x["horizon"])):
        res = f"ret {r['ret_h']:+.1%} peor {r['max_adverse']:+.1%} mejor {r['max_favorable']:+.1%}"
        if r["state"]:
            res += f" | {r['state']} (objetivo {r['target_pct']:+.1%} stop {-r['stop_pct']:+.1%}) R {r['r_pess']:+.2f}/{r['r_opt']:+.2f} MAE_R {r['mae_r']:+.2f} MFE_R {r['mfe_r']:+.2f} en {r['bars_to_exit']} barras"
        sup = r["sup"]
        res += f" | soporte_v1 {sup['state']}" + (
            f" (zona {sup['zone_low']:.2f}-{sup['zone_high']:.2f}, {sup['dist_atr']:+.1f} ATR)"
            if sup["state"] != "UNAVAILABLE" and sup.get("dist_atr") is not None
            else ""
        )
        if r.get("regime"):
            res += f" | mercado {r['regime']}"
        line = f"{r['ticker']:<8}|{r['date']}|{r['horizon']:>2}m|{r['price']:>10.2f}|{r['call']:<7}({r['score']:+.1f})|{r['why']}|{res}"
        if "call_f" in r:
            line += f" || CON FUNDAMENTALES: {r['call_f']}({r['score_f']:+.1f}) {r['labels_f']} {r['why_f']}"
        lines.append(line)
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def render_full(
    rows: list[dict[str, Any]],
    skipped: dict[str, int],
    coverage: dict[str, dict[str, Any]],
    now: datetime,
    step: int,
    start: date,
) -> str:
    L: list[str] = []
    w = L.append
    used = {t: c for t, c in coverage.items() if c["used"]}
    reg = {t: region(c["market"], c.get("exchange")) for t, c in used.items()}
    w("=" * 110)
    w(
        f"INFORME COMPLETO DE EVALUACIÓN DEL ALGORITMO · {now:%Y-%m-%d %H:%M} UTC · {bt.BACKTEST_VERSION} / {engine.ENGINE_VERSION}"
    )
    w("=" * 110)
    w(
        "AVISO: RETROSPECTIVO y SIN VALIDAR. Precios de una fuente gratuita no oficial descargados a posteriori; la regla ve solo datos conocidos en cada fecha, pero no hay costes, las ventanas solapadas NO son"
    )
    w(
        "observaciones independientes y la lista son empresas ACTUALES (SESGO DE SUPERVIVENCIA: infla la tasa base de subida). Importa la ventaja sobre la tasa base, no el % absoluto. Holdout 2022-10-01→2025-09-30 intacto."
    )
    w("")

    # ── tabla global
    glob: dict[int, dict[str, Any]] = {h: bt.stats_for(rows, h, _calls(rows)) for h in H}
    w("0. RESUMEN EJECUTIVO")
    w(LINE)
    w(
        f"  Valores analizados: {len(used)} de {len(coverage)} · observaciones (valor×fecha×horizonte): {len(rows)} · muestreo cada {step} sesiones desde {start}."
    )
    for h in H:
        g = glob[h]
        if not g["n"]:
            continue
        w(
            f"  {h:>2} m: tasa base de subida {g['up_base']:.0%} · SUBE acierto {('n/d' if g['up_rate'] is None else f'{g["up_rate"]:.0%}')} (ventaja {_edge(g['up_rate'], g['up_base'], g['n_up'])}, N={g['n_up']}) · BAJA acierto {('n/d' if g['down_rate'] is None else f'{g["down_rate"]:.0%}')} (ventaja {_edge(g['down_rate'], g['down_base'], g['n_down'])}, N={g['n_down']})"
        )
    w("")

    df = bp0.frame(rows, reg)
    w(
        "P0. PLAN DE MEJORA — BASELINE_V0 frente a V13 (soporte corregido), V14 (BAJA como RISK_ALERT) y V15 (BAJA_CONFIRMADA)"
    )
    w(LINE)
    w(
        "  Constantes: universo, fechas, umbrales, objetivo, stop y pesos (solo cambia la semántica de soporte/BAJA). Holdout intacto. Una hipótesis cada vez; no se promueve ninguna variante."
    )
    p0_lines, p0_results = bp0.render_p0(df)
    for line in p0_lines:
        w(line)
    w("")
    w("1. MÉTODO Y LÍMITES")
    w(LINE)
    w(
        "  - En cada fecha T (cada 21 sesiones) y horizonte (1, 3, 6, 12 y 24 meses) la regla emite SUBE / BAJA / NEUTRAL con la información de T (precio: tendencia, media 200, momentum 6 m, soporte)."
    )
    w(
        "  - Se compara con la rentabilidad real al fin del horizonte (¿subió o bajó?) frente a la tasa base. Para SUBE además: ¿se tocó antes el objetivo o el stop (calculados con la volatilidad)?"
    )
    w(
        "  - Valoración y fundamentales solo existen point-in-time para los valores con datos de la SEC (hoy AAPL, MSFT, KO): para ellos se hace una SEGUNDA llamada con esas reglas para medir su aporte."
    )
    w(
        f"  - Holdout intacto: {skipped['holdout']} decisiones/horizontes omitidos por tocarlo; sin contexto suficiente: {skipped['no_context']}; ventanas inmaduras no puntuadas: {skipped['immature']}."
    )
    w(
        "  - Intervalos [x-y] = Wilson 95 %. Sin porcentajes con N<10. N alto por solapamiento no equivale a evidencia independiente: la muestra efectiva es del orden de N/(horizonte/muestreo)."
    )
    w("")

    w("2. COBERTURA DE DATOS")
    w(LINE)
    for t, c in sorted(coverage.items()):
        if c["used"]:
            w(
                f"  {t:<9} {c['market']:<11} {reg[t]:<14} {c['n']:>5} obs. ({c['first']} → {c['last']})"
                + ("  [con fundamentales SEC]" if c["fundamentals"] else "")
            )
    skipped_t = {t: c for t, c in coverage.items() if not c["used"]}
    if skipped_t:
        w("  No usados:")
        for t, c in sorted(skipped_t.items()):
            w(f"    - {t} ({c['market']}): {c['why']}")
    w(
        f"  Fundamentales: solo {sum(1 for c in used.values() if c['fundamentals'])} valores. Para ampliar: exportar PITQUANT_SEC_USER_AGENT (nombre y correo reales) y registrar los emisores con `pitquant sec-ingest <CIK> --register-missing`."
    )
    w("")

    w("3. RESULTADOS POR HORIZONTE")
    w(LINE)
    for h in H:
        g = glob[h]
        if not g["n"]:
            w(f"  Horizonte {h} meses: sin observaciones")
            continue
        w(
            f"  Horizonte {h} meses · observaciones {g['n']} · subió {_rate(round(g['up_base'] * g['n']), g['n'])} · bajó {g['down_base']:.0%}"
        )
        for call, label in (("UP", "SUBE   "), ("NEUTRAL", "NEUTRAL"), ("DOWN", "BAJA   ")):
            cs = [r for r in rows if r["horizon"] == h and r["call"] == call]
            ok = sum(1 for r in cs if (r["ret_h"] < 0 if call == "DOWN" else r["ret_h"] > 0))
            what = "bajó" if call == "DOWN" else "subió"
            base = g["down_base"] if call == "DOWN" else g["up_base"]
            rate = ok / len(cs) if cs else None
            w(
                f"      {label} N={len(cs):>5}  acierto ({what}) {_rate(ok, len(cs)):<18} ventaja {_edge(rate, base, len(cs)):>7}  rentabilidad media {_pct(mean(r['ret_h'] for r in cs) if cs else None)}"
            )
        ups = [r for r in rows if r["horizon"] == h and r["call"] == "UP" and r["state"]]
        if ups:
            st10: dict[str, int] = defaultdict(int)
            for r in ups:
                st10[r["state"]] += 1
            w(
                f"      SUBE con objetivo/stop N={len(ups)}: objetivo {_rate(st10['TARGET_HIT'], len(ups))} · stop {_rate(st10['STOP_HIT'] + st10['AMBIGUOUS_STOP'], len(ups))} · vencida {_rate(st10['EXPIRED'], len(ups))}"
            )
        w("")

    w("4. CALIDAD DE LA SEÑAL")
    w(LINE)
    w(
        "  4a. Puntuación → rentabilidad (¿sube la rentabilidad cuando sube la puntuación?)  [N | % subió | rentabilidad media]"
    )
    bins = [(-99, -2.0), (-2.0, 0.0), (0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 99)]
    w(
        "      horizonte   "
        + "  ".join(
            f"{('<' + str(b)) if a == -99 else ('>=' + str(a)) if b == 99 else f'{a}..{b}':>16}"
            for a, b in bins
        )
    )
    mono: dict[int, list[float]] = {}
    for h in H:
        hs = [r for r in rows if r["horizon"] == h]
        cells, means = [], []
        for a, b in bins:
            bs = [r for r in hs if a <= r["score"] < b]
            cells.append(
                f"{len(bs):>4}|{(sum(1 for r in bs if r['ret_h'] > 0) / len(bs)):>4.0%}|{mean(r['ret_h'] for r in bs):>+5.0%}"
                if len(bs) >= bt.MIN_N
                else f"{len(bs):>4}|  n/d|  n/d"
            )
            if len(bs) >= bt.MIN_N:
                means.append(mean(r["ret_h"] for r in bs))
        mono[h] = means
        w(f"      {h:>3} m       " + "  ".join(f"{c:>16}" for c in cells))
    w(
        "  4b. Correlación de rangos (IC) de cada regla y de la puntuación con la rentabilidad futura (±0.05 es ya apreciable; 0 = nada)"
    )
    w("      horizonte   " + "  ".join(f"{k:>12}" for k in (*bt.RULE_IDS, "PUNTUACIÓN")))
    ic_all: dict[int, dict[str, float | None]] = {}
    for h in H:
        hs = [r for r in rows if r["horizon"] == h]
        ics: dict[str, float | None] = {}
        for k in bt.RULE_IDS:
            sub = [r for r in hs if k in r["raws"]]
            ics[k] = bt.spearman([r["raws"][k] for r in sub], [r["ret_h"] for r in sub])
        ics["score"] = bt.spearman([r["score"] for r in hs], [r["ret_h"] for r in hs])
        ic_all[h] = ics
        w(
            f"      {h:>3} m       "
            + "  ".join(f"{('n/d' if v is None else f'{v:+.3f}'):>12}" for v in ics.values())
        )
    w("")

    w("5. APORTE DE LOS FUNDAMENTALES (solo valores con datos SEC; muestra pequeña)")
    w(LINE)
    frows = [r for r in rows if "call_f" in r]
    if not frows:
        w("  Sin valores con fundamentales point-in-time.")
    else:
        w(
            f"  Valores: {', '.join(sorted({r['ticker'] for r in frows}))} · observaciones {len(frows)}"
        )
        w(
            "  horizonte   SOLO PRECIO: SUBE N | acierto | ventaja        CON FUNDAMENTALES: SUBE N | acierto | ventaja"
        )
        for h in H:
            hs = [r for r in frows if r["horizon"] == h]
            if not hs:
                continue
            nb, ub, _db = bt.base_rates(hs, h)
            cells = []
            for key in ("call", "call_f"):
                ups = [r for r in hs if r[key] == "UP"]
                ok = sum(1 for r in ups if r["ret_h"] > 0)
                cells.append(
                    f"{len(ups):>4} | {_rate(ok, len(ups)):<18} | {_edge(ok / len(ups) if ups else None, ub, len(ups)):>7}"
                )
            w(f"  {h:>3} m       {cells[0]}        {cells[1]}   (base {ub:.0%}, N={nb})")
        w(
            "  Lectura: con 3 valores y ventanas solapadas esto NO permite concluir nada; sirve para comprobar que el mecanismo funciona y como pauta para ampliar la cobertura."
        )
    w("")

    w(
        "6. VARIANTES DE LA REGLA (re-puntuadas sobre las mismas observaciones; ventaja = acierto − tasa base)"
    )
    w(LINE)
    w(
        "  Cada variante cambia UNA cosa (quitar una regla, usar solo el signo de una, mover el umbral, invertir). Estabilidad: ventaja de SUBE en ≤2022-09 / en ≥2025-10 (periodo reciente, muestra pequeña)."
    )
    w(
        "  variante                                   hor.  SUBE N   acierto            ventaja   BAJA N   acierto            ventaja   | estabilidad SUBE (≤2022-09 / ≥2025-10)"
    )
    variant_rows: list[tuple[str, int, dict[str, Any], str]] = []
    for name in bt.VARIANTS:
        calls = bt.variant_calls(rows, name)
        for h in (3, 12, 24):
            s = bt.stats_for(rows, h, calls)
            pre = [
                r
                for i, r in enumerate(rows)
                if r["horizon"] == h and calls[i] == "UP" and r["date"] <= PRE_END
            ]
            post = [
                r
                for i, r in enumerate(rows)
                if r["horizon"] == h and calls[i] == "UP" and r["date"] >= POST_START
            ]
            base_pre = [r for r in rows if r["horizon"] == h and r["date"] <= PRE_END]
            base_post = [r for r in rows if r["horizon"] == h and r["date"] >= POST_START]
            e_pre = (
                (
                    sum(1 for r in pre if r["ret_h"] > 0) / len(pre)
                    - sum(1 for r in base_pre if r["ret_h"] > 0) / len(base_pre)
                )
                if len(pre) >= bt.MIN_N and base_pre
                else None
            )
            e_post = (
                (
                    sum(1 for r in post if r["ret_h"] > 0) / len(post)
                    - sum(1 for r in base_post if r["ret_h"] > 0) / len(base_post)
                )
                if len(post) >= bt.MIN_N and base_post
                else None
            )
            stab = f"{_pct(e_pre)} / {_pct(e_post)}"
            up_ok = None if s["up_rate"] is None else round(s["up_rate"] * s["n_up"])
            dn_ok = None if s["down_rate"] is None else round(s["down_rate"] * s["n_down"])
            w(
                f"  {name[:42]:<42} {h:>3}m {s['n_up']:>7}   {_rate(up_ok, s['n_up']):<18} {_edge(s['up_rate'], s['up_base'], s['n_up']):>7}   {s['n_down']:>6}   {_rate(dn_ok, s['n_down']):<18} {_edge(s['down_rate'], s['down_base'], s['n_down']):>7}   | {stab}"
            )
            variant_rows.append((name, h, s, stab))
    w("")

    w(
        "7. SENSIBILIDAD DEL OBJETIVO (solo SUBE; % que cumple objetivo según target_k) — no ajustar mirando solo esto: riesgo de sobreajuste"
    )
    w(LINE)
    w("  horizonte   " + "   ".join(f"k={k}" for k in bt.SENSITIVITY_K) + "     (N)")
    for h in H:
        ups = [r for r in rows if r["horizon"] == h and r["call"] == "UP" and r.get("sensitivity")]
        w(
            f"  {h:>3} m       "
            + "   ".join(
                f"{(sum(1 for r in ups if r['sensitivity'][k] == 'TARGET_HIT') / len(ups) if len(ups) >= bt.MIN_N else float('nan')):>5.0%}"
                for k in bt.SENSITIVITY_K
            )
            + f"     {len(ups)}"
        )
    w("")

    w(
        "8. SELECCIÓN POR PUNTUACIÓN (corte transversal): cada mes, los valores de mayor puntuación frente a los de menor"
    )
    w(LINE)
    w(
        "  La rutina real elige un valor por rotación, no por puntuación. Aquí: cada mes se ordenan los valores por puntuación y se compara el 20 % superior con el 20 % inferior (rentabilidad al fin del horizonte)."
    )
    spread: dict[int, tuple[float | None, float | None, int]] = {}
    for h in H:
        by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            if r["horizon"] == h:
                by_month[f"{r['date']:%Y-%m}"].append(r)
        sp = []
        for rs in by_month.values():
            if len(rs) < 10:
                continue
            rs = sorted(rs, key=lambda x: x["score"])
            q = max(1, len(rs) // 5)
            lo, hi = rs[:q], rs[-q:]
            if mean(r["score"] for r in hi) <= mean(r["score"] for r in lo):
                continue  # no dispersion of scores that month
            sp.append(mean(r["ret_h"] for r in hi) - mean(r["ret_h"] for r in lo))
        spread[h] = (
            mean(sp) if sp else None,
            (sum(1 for x in sp if x > 0) / len(sp)) if sp else None,
            len(sp),
        )
        w(
            f"  {h:>3} m: meses útiles {len(sp):>3} · diferencia media (top 20 % − bottom 20 %) {_pct(spread[h][0])} · meses en que el top rindió más: {('n/d' if spread[h][1] is None else f'{spread[h][1]:.0%}')}"
        )
    w("")

    w("9. POR MERCADO, REGIÓN Y PERIODO (llamadas SUBE)")
    w(LINE)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[f"mercado {r['market']}"].append(r)
        groups[f"región {reg.get(r['ticker'], '?')}"].append(r)
        groups["periodo ≤2022-09" if r["date"] <= PRE_END else "periodo ≥2025-10"].append(r)
    for h in (3, 12):
        w(f"  Horizonte {h} m:")
        for gname, grows in sorted(groups.items()):
            hs = [r for r in grows if r["horizon"] == h]
            if not hs:
                continue
            ups = [r for r in hs if r["call"] == "UP"]
            base = sum(1 for r in hs if r["ret_h"] > 0) / len(hs)
            ok = sum(1 for r in ups if r["ret_h"] > 0)
            w(
                f"      {gname:<24} obs {len(hs):>5} · base {base:>4.0%} · SUBE N={len(ups):>4} acierto {_rate(ok, len(ups)):<18} ventaja {_edge(ok / len(ups) if ups else None, base, len(ups))}"
            )
    w("")

    w("10. POR VALOR (cada valor: qué decidió la regla, en base a qué y qué pasó)")
    w(LINE)
    for t in sorted(used):
        trs = [r for r in rows if r["ticker"] == t]
        w(
            f"  {t} · {used[t]['market']} · {reg[t]} · {len(trs)} observaciones ({used[t]['first']} → {used[t]['last']})"
            + (" · con fundamentales" if used[t]["fundamentals"] else "")
        )
        for h in H:
            hs = [r for r in trs if r["horizon"] == h]
            if not hs:
                continue
            nb, ub, _db = bt.base_rates(hs, h)
            ups = [r for r in hs if r["call"] == "UP"]
            dns = [r for r in hs if r["call"] == "DOWN"]
            upok, dnok = (
                sum(1 for r in ups if r["ret_h"] > 0),
                sum(1 for r in dns if r["ret_h"] < 0),
            )
            st10 = defaultdict(int)
            for r in ups:
                if r["state"]:
                    st10[r["state"]] += 1
            w(
                f"      {h:>2} m: subió {ub:>4.0%} · SUBE N={len(ups):>3} acierto {('n/d' if not ups else f'{upok / len(ups):.0%}'):>4} (rent. media {_pct(mean(r['ret_h'] for r in ups) if ups else None)}; objetivo {st10['TARGET_HIT']}, stop {st10['STOP_HIT'] + st10['AMBIGUOUS_STOP']}, vencida {st10['EXPIRED']}) · BAJA N={len(dns):>3} acierto {('n/d' if not dns else f'{dnok / len(dns):.0%}'):>4}"
            )
        ex = [r for r in trs if r["horizon"] == 6 and r["call"] == "UP"]
        if ex:
            best, worst = max(ex, key=lambda r: r["ret_h"]), min(ex, key=lambda r: r["ret_h"])
            w(
                f"      mejor SUBE 6 m: {best['date']} ret {best['ret_h']:+.1%} · en base a: {best['why']}"
            )
            w(
                f"      peor  SUBE 6 m: {worst['date']} ret {worst['ret_h']:+.1%} · en base a: {worst['why']}"
            )
        w("")

    w(
        "11. PROPUESTAS DE MEJORA (generadas de los números de arriba; para volver a ejecutar el análisis con ellas)"
    )
    w(LINE)
    for i, p in enumerate(
        proposals(rows, glob, ic_all, variant_rows, spread, mono, used, p0_results), 1
    ):
        w(f"  {i}. {p}")
    w("")
    w("12. PARÁMETROS EN USO")
    w(LINE)
    for k, v in rt.PARAMS.items():
        w(f"  {k}: {v}")
    w(
        f"  umbral vender <= {engine.SELL_AT:+.1f} · umbral entrar >= {engine.ADD_AT:+.1f} · estiramiento máx. {engine.OVEREXTENDED_ATR} ATR · RSI máx. 70"
    )
    for bucket_name, wts in engine.WEIGHTS.items():
        w(f"  pesos {bucket_name}: " + ", ".join(f"{k}={v}" for k, v in wts.items()))
    w("")
    w("FIN DEL INFORME (el detalle de cada decisión está en backtest_decisiones_*.txt)")
    return "\n".join(L) + "\n"


def proposals(rows: list[dict[str, Any]], glob: dict[int, dict[str, Any]], ic: dict[int, dict[str, float | None]], variants: list[tuple[str, int, dict[str, Any], str]], spread: dict[int, tuple[float | None, float | None, int]], mono: dict[int, list[float]], used: dict[str, Any], p0: dict[str, str] | None = None) -> list[str]:  # fmt: skip
    out: list[str] = []
    if p0:
        out.append(
            "RESULTADO DEL PLAN P0 (sección P0): "
            + "; ".join(f"{bp0.NAMES[v]} → {r}" for v, r in p0.items())
            + ". Ninguna variante se promueve sin IMPROVES robusto; si sale INCONCLUSIVE, el siguiente paso es el análisis de features continuas (RUN 3) y el modelo regularizado, no afinar umbrales."
        )
    # 0. rules that never fire (a dead rule is a bug or a design flaw, not a weak signal)
    for k in bt.RULE_IDS:
        have = [r for r in rows if k in r["raws"]]
        if have and all(r["raws"][k] == 0.0 for r in have):
            out.append(
                f"REGLA INACTIVA — {k}: aporta 0 en las {len(have)} observaciones donde se evalúa (nunca se activa). No es una señal débil: es un defecto de diseño. Rediseñarla (p. ej. comparar con el soporte vigente en la fecha de ENTRADA y no con el más cercano por debajo del precio actual, que por construcción nunca está roto) y volver a medirla."
            )
    # 1. BAJA signal
    d_edges = [
        (h, g["down_rate"] - g["down_base"])
        for h, g in glob.items()
        if g["n_down"] >= bt.MIN_N and g["down_rate"] is not None
    ]
    if d_edges and max(e for _, e in d_edges) < 0.05:
        out.append(
            f"LA SEÑAL BAJA NO ANTICIPA CAÍDAS (ventaja ≤ {max(e for _, e in d_edges):+.1%} en todos los horizontes). Propuesta: no usarla para vender por sí sola; degradarla a «alerta de riesgo» o exigir confirmación (cierre bajo la media 200 Y momentum negativo Y pérdida de soporte) y volver a medirla."
        )
    # 2. SUBE edge
    u_edges = [
        (h, g["up_rate"] - g["up_base"])
        for h, g in glob.items()
        if g["n_up"] >= bt.MIN_N and g["up_rate"] is not None
    ]
    if u_edges:
        best_h = max(u_edges, key=lambda x: x[1])
        out.append(
            f"VENTAJA DE SUBE: {', '.join(f'{h} m {e:+.1%}' for h, e in u_edges)} (mejor: {best_h[0]} m). "
            + (
                "Es pequeña: la regla actual apenas mejora el azar; no justifica entrar con más confianza."
                if max(e for _, e in u_edges) < 0.05
                else "Hay ventaja moderada; hay que confirmarla fuera de muestra."
            )
        )
    # 3. Per-rule IC
    weak: list[str] = []
    neg: list[str] = []
    strong: list[str] = []
    for k in bt.RULE_IDS:
        vals = [v for h in H if (v := ic[h].get(k)) is not None]
        if not vals:
            continue
        m = mean(vals)
        (neg if m < -0.02 else weak if abs(m) < 0.02 else strong).append(f"{k} ({m:+.3f})")
    if strong:
        out.append(f"REGLAS CON SEÑAL (IC medio): {', '.join(strong)} → candidatas a MÁS peso.")
    if weak:
        out.append(
            f"REGLAS SIN SEÑAL (|IC|<0.02): {', '.join(weak)} → candidatas a quitarse o a reducir su peso (la ablación de la sección 6 confirma si quitarlas empeora algo)."
        )
    if neg:
        out.append(
            f"REGLAS CONTRARIAS A LO ESPERADO (IC negativo): {', '.join(neg)} → la señal va al revés en esta muestra; probar su inversión como hipótesis (p. ej. «reversión» en vez de «continuación») y comprobarlo fuera de muestra."
        )
    # 4. best stable variant
    cands = []
    for name, h, s, stab in variants:
        if name == "V0" or s["n_up"] < 100 or s["up_rate"] is None:
            continue
        cands.append((s["up_rate"] - s["up_base"], name, h, stab))
    if cands:
        top = sorted(cands, reverse=True)[:3]
        out.append(
            "MEJORES VARIANTES POR VENTAJA DE SUBE (N≥100): "
            + "; ".join(f"{n} a {h} m {e:+.1%} (estabilidad {st})" for e, n, h, st in top)
            + ". Solo se adoptan si la ventaja se mantiene en ambos periodos y mejora a V0; si no, es ruido."
        )
    # 5. monotonicity
    nonmono = [
        h for h, m in mono.items() if len(m) >= 4 and any(b < a - 0.01 for a, b in pairwise(m))
    ]
    if nonmono:
        out.append(
            f"LA PUNTUACIÓN NO ES MONÓTONA con la rentabilidad a {', '.join(f'{h} m' for h in nonmono)} (sección 4a): puntuaciones más altas no siempre rinden más → revisar la escala de pesos y los umbrales (+2.5 / −2.0) antes de afinarlos."
        )
    # 6. cross-section
    sp = [(h, v[0], v[1]) for h, v in spread.items() if v[0] is not None]
    if sp:
        pos = [h for h, a, b in sp if a > 0]
        out.append(
            "SELECCIÓN POR PUNTUACIÓN (sección 8): "
            + ", ".join(f"{h} m {_pct(a)}" for h, a, _ in sp)
            + (
                ". El top 20 % rinde más que el bottom 20 % en "
                + ", ".join(f"{h} m" for h in pos)
                + " → la rutina debería ELEGIR cada día el valor de mayor puntuación en lugar de rotar."
                if pos
                else ". Sin diferencia a favor del top: la puntuación no discrimina entre valores."
            )
        )
    # 7. target/stop
    hit_raw = [
        (
            h,
            sum(
                1
                for r in rows
                if r["horizon"] == h and r["call"] == "UP" and r["state"] == "TARGET_HIT"
            ),
            sum(1 for r in rows if r["horizon"] == h and r["call"] == "UP" and r["state"]),
        )
        for h in H
    ]
    hit = [(h, k / n) for h, k, n in hit_raw if n >= bt.MIN_N]
    if hit:
        out.append(
            "OBJETIVO/STOP: "
            + ", ".join(f"{h} m objetivo {r:.0%}" for h, r in hit)
            + ". Un reparto cercano al 50 % indica que objetivo y stop están casi equidistantes en términos de volatilidad: medir también la ESPERANZA (R medio por operación) en la próxima ejecución antes de mover target_k/stop_k."
        )
    out.append(
        "FUNDAMENTALES: con solo "
        + str(sum(1 for c in used.values() if c.get("fundamentals")))
        + " valores con datos SEC no se puede concluir. Ampliar cobertura SEC (PITQUANT_SEC_USER_AGENT + sec-ingest) y repetir la sección 5; si no aportan, dejar la regla solo de precio para valores sin SEC."
    )
    out.append(
        "FILTRO DE RÉGIMEN: añadir el estado del mercado (p. ej. SPY sobre su media 200) como filtro de entrada y medir si las llamadas SUBE en mercado bajista rinden peor."
    )
    out.append(
        "MÉTRICAS NUEVAS PARA LA PRÓXIMA EJECUCIÓN: esperanza por operación en R, rentabilidad media por llamada ajustada por volatilidad, y evaluación por bloques temporales no solapados para tener una muestra efectiva honesta."
    )
    out.append(
        "DATOS: sustituir la lista de empresas actuales por la composición del índice en cada fecha (supervivencia), añadir costes de operación y, si es posible, una fuente con histórico más largo para probar otros ciclos."
    )
    return out
