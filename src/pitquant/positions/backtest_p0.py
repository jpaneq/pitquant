# ruff: noqa: E501
"""Plan de mejora P0 (ADR-0047): one hypothesis at a time, re-scored OFFLINE over the stored rows of the backtest (constant universe, dates, thresholds, target, stop and weights; holdout untouched).

* ``V0``  BASELINE_V0: the live rule.
* ``V13`` SUPPORT_FIX: support_rule_v1 (zone frozen with bars up to T-1; broken only if close_T < zone low; no zone = rule skipped, not "held").
* ``V14`` SUPPORT_FIX_RISK_ALERT: V13 calls, but the old BAJA is read as RISK_ALERT: it informs deterioration, it is NOT a forecast of a fall, so it is judged by drawdown risk, not by direction.
* ``V15`` SUPPORT_FIX_BAJA_CONFIRMADA: V13's SUBE plus BAJA_CONFIRMADA = close < SMA200 AND 6-month momentum < 0 AND support broken.
Each variant is judged on several dimensions (ranking, direction, R expectancy, robustness over non-overlapping offsets, temporal and regional stability); one dimension alone is INCONCLUSIVE.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from pitquant.positions import review as engine
from pitquant.positions import routine as rt

VARIANTS = ("V0", "V13", "V14", "V15")
NAMES = {
    "V0": "BASELINE_V0",
    "V13": "V13_SUPPORT_FIX",
    "V14": "V14_SUPPORT_FIX_RISK_ALERT",
    "V15": "V15_SUPPORT_FIX_BAJA_CONFIRMADA",
}
MIN_N = 10
PRE_END = pd.Timestamp("2022-09-30")
POST_START = pd.Timestamp("2025-10-01")
EPS = {
    "ic": 0.005,
    "tb": 0.002,
    "edge": 0.005,
    "r": 0.02,
    "robust": 0.05,
    "temporal": 0.005,
    "region": 0.10,
}


def frame(rows: list[dict[str, Any]], region_of: dict[str, str]) -> pd.DataFrame:
    """One DataFrame row per decision with the columns every variant needs (plus the rules' raw contributions)."""
    recs = []
    for r in rows:
        f, sup = r["feat"], r["sup"]
        recs.append(
            {
                "ticker": r["ticker"], "region": region_of.get(r["ticker"], "?"), "date": pd.Timestamp(r["date"]), "h": r["horizon"], "price": r["price"], "ret": r["ret_h"], "mae": r["max_adverse"], "mfe": r["max_favorable"],
                "call0": r["call"], "score0": r["score"], "state": r["state"], "r_pess": r.get("r_pess"), "r_opt": r.get("r_opt"), "mae_r": r.get("mae_r"), "mfe_r": r.get("mfe_r"), "bars_exit": r.get("bars_to_exit"),
                "amb": r.get("ambiguous"), "regime": r.get("regime"), "sup_state": sup["state"], "sup_dist_atr": sup.get("dist_atr"), "cs50": f.get("close_vs_sma50"), "cs200": f.get("close_vs_sma200"), "ret6": f.get("ret126"),
                "rsi": f.get("rsi14"), "atr14": f.get("atr14"), **{f"raw_{k}": v for k, v in r["raws"].items()},
            }
        )  # fmt: skip
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    df["m"] = df["date"].dt.year * 12 + df["date"].dt.month - 1
    return add_variants(df)


def add_variants(df: pd.DataFrame) -> pd.DataFrame:
    w = {b: engine.WEIGHTS[b] for b in engine.WEIGHTS}
    bucket = df["h"].map(engine.horizon_bucket)
    wcol = {
        k: bucket.map(lambda b, k=k: w[b][k])
        for k in ("trend", "long_trend", "momentum", "valuation", "fundamentals", "support")
    }
    for k in ("trend", "long_trend", "momentum", "valuation", "fundamentals", "support"):
        if f"raw_{k}" not in df:
            df[f"raw_{k}"] = np.nan

    def total(support_raw: pd.Series) -> pd.Series:
        s = pd.Series(0.0, index=df.index)
        for k in ("trend", "long_trend", "momentum", "valuation", "fundamentals"):
            s += df[f"raw_{k}"].fillna(0.0) * wcol[k]
        return s + support_raw.fillna(0.0) * wcol["support"]

    # blockers of the live rule for a NEW position (target not met, horizon ahead): trend not clearly up, stretched price, RSI > 70
    ext = (df["price"] - df["price"] / (1 + df["cs50"])) / df["atr14"]
    blocked = (
        (df["raw_trend"].fillna(0) < 1)
        | (ext > engine.OVEREXTENDED_ATR).fillna(False)
        | (df["rsi"] > 70).fillna(False)
    )

    def call(score: pd.Series) -> pd.Series:
        return pd.Series(
            np.where(
                score <= engine.SELL_AT,
                "DOWN",
                np.where((score >= engine.ADD_AT) & ~blocked, "UP", "NEUTRAL"),
            ),
            index=df.index,
        )

    df["score_v0_re"] = total(df["raw_support"])
    df["call_v0_re"] = call(
        df["score_v0_re"]
    )  # replication of the live rule from stored raws (checked against the stored call in the tests)
    sup_raw = pd.Series(
        np.where(
            df["sup_state"] == "BROKEN", -2.0, np.where(df["sup_state"] == "HELD", 0.0, np.nan)
        ),
        index=df.index,
    )
    df["score13"] = total(sup_raw)
    df["call13"] = call(df["score13"])
    confirmed = (df["cs200"] < 0) & (df["ret6"] < 0) & (df["sup_state"] == "BROKEN")
    df["call15"] = np.where(df["call13"] == "UP", "UP", np.where(confirmed, "DOWN", "NEUTRAL"))
    df["call0"] = df["call0"]
    df["call14"] = df["call13"]  # same sets as V13; the DOWN side is read as RISK_ALERT
    return df


def call_col(v: str) -> str:
    return {"V0": "call0", "V13": "call13", "V14": "call14", "V15": "call15"}[v]


def score_col(v: str) -> str:
    return "score0" if v == "V0" else "score13"


def _wilson_safe(k: int, n: int) -> float:
    return k / n if n else float("nan")


def directional(df: pd.DataFrame, h: int, v: str) -> dict[str, Any]:
    d = df[df["h"] == h]
    c = d[call_col(v)]
    base_up, base_down = float((d["ret"] > 0).mean()), float((d["ret"] < 0).mean())
    up, dn = d[c == "UP"], d[c == "DOWN"]
    return {
        "n": len(d), "base_up": base_up, "base_down": base_down, "n_up": len(up), "up_hit": float((up["ret"] > 0).mean()) if len(up) else float("nan"), "n_dn": len(dn), "dn_hit": float((dn["ret"] < 0).mean()) if len(dn) else float("nan"),
        "up_mean": float(up["ret"].mean()) if len(up) else float("nan"), "up_median": float(up["ret"].median()) if len(up) else float("nan"), "dn_mean": float(dn["ret"].mean()) if len(dn) else float("nan"),
        "dn_median": float(dn["ret"].median()) if len(dn) else float("nan"), "dn_mae": float(dn["mae"].mean()) if len(dn) else float("nan"), "base_mae": float(d["mae"].mean()),
        "dn_dd10": float((dn["mae"] <= -0.10).mean()) if len(dn) else float("nan"), "base_dd10": float((d["mae"] <= -0.10).mean()),
    }  # fmt: skip


def edge_up(s: dict[str, Any]) -> float:
    return s["up_hit"] - s["base_up"] if s["n_up"] >= MIN_N else float("nan")


def edge_dn(s: dict[str, Any]) -> float:
    return s["dn_hit"] - s["base_down"] if s["n_dn"] >= MIN_N else float("nan")


def trading(df: pd.DataFrame, h: int, v: str) -> dict[str, Any]:
    d = df[(df["h"] == h) & (df[call_col(v)] == "UP") & df["r_pess"].notna()]
    out: dict[str, Any] = {"n": len(d)}
    if len(d) < MIN_N:
        return out | {"mean_r": float("nan")}

    def pf(r: pd.Series) -> float:
        pos, neg = r[r > 0].sum(), -r[r < 0].sum()
        return float(pos / neg) if neg > 0 else float("inf")

    out |= {
        "mean_r": float(d["r_pess"].mean()), "median_r": float(d["r_pess"].median()), "mean_r_opt": float(d["r_opt"].mean()), "median_r_opt": float(d["r_opt"].median()), "pf": pf(d["r_pess"]), "pf_opt": pf(d["r_opt"]),
        "mae_r": float(d["mae_r"].mean()), "mfe_r": float(d["mfe_r"].mean()), "amb": float(d["amb"].fillna(False).astype(bool).mean()), "target": float((d["state"] == "TARGET_HIT").mean()), "bars": float(d["bars_exit"].mean()),
    }  # fmt: skip
    return out


def _spearman(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 30 or a.nunique() < 2 or b.nunique() < 2:
        return float("nan")
    return float(a.rank().corr(b.rank()))


def _top_bottom(d: pd.DataFrame, score: str) -> list[float]:
    out = []
    for _, g in d.groupby("m"):
        if len(g) < 10:
            continue
        g = g.sort_values(score, kind="stable")
        q = max(1, len(g) // 5)
        lo, hi = g.iloc[:q], g.iloc[-q:]
        if hi[score].mean() <= lo[score].mean():
            continue
        out.append(float(hi["ret"].mean() - lo["ret"].mean()))
    return out


def ranking(df: pd.DataFrame, h: int, v: str) -> dict[str, Any]:
    d = df[df["h"] == h]
    sc = score_col(v)
    tb = _top_bottom(d, sc)
    # D10-D1 with average ranks inside each month (ties share ranks: the score is discrete)
    dec = []
    for _, g in d.groupby("m"):
        if len(g) < 30:
            continue
        pct = g[sc].rank(pct=True, method="average")
        hi, lo = g[pct > 0.9], g[pct <= 0.1]
        if len(hi) and len(lo):
            dec.append(float(hi["ret"].mean() - lo["ret"].mean()))
    return {
        "ic": _spearman(d[sc], d["ret"]),
        "tb": float(np.mean(tb)) if tb else float("nan"),
        "tb_pos": float(np.mean([x > 0 for x in tb])) if tb else float("nan"),
        "d10_d1": float(np.mean(dec)) if dec else float("nan"),
        "months": len(tb),
    }


def nonoverlap(df: pd.DataFrame, h: int, v: str) -> dict[str, Any]:
    """H monthly offsets, each with decisions at least H months apart (non-overlapping windows). Edge of SUBE, IC and top-bottom per offset."""
    d = df[df["h"] == h].drop_duplicates(["ticker", "m"])
    edges, ics, tbs = [], [], []
    for o in range(h):
        sub = d[d["m"] % h == o]
        s = {"n_up": int((sub[call_col(v)] == "UP").sum())}
        up = sub[sub[call_col(v)] == "UP"]
        if s["n_up"] >= MIN_N:
            edges.append(float((up["ret"] > 0).mean() - (sub["ret"] > 0).mean()))
        ic = _spearman(sub[score_col(v)], sub["ret"])
        if not np.isnan(ic):
            ics.append(ic)
        tb = _top_bottom(sub, score_col(v))
        if tb:
            tbs.append(float(np.mean(tb)))
    return {"edges": edges, "ics": ics, "tbs": tbs, "n_off": h}


def period_edges(df: pd.DataFrame, h: int, v: str) -> tuple[float, float]:
    out = []
    for sel in (df["date"] <= PRE_END, df["date"] >= POST_START):
        d = df[(df["h"] == h) & sel]
        up = d[d[call_col(v)] == "UP"]
        out.append(
            float((up["ret"] > 0).mean() - (d["ret"] > 0).mean())
            if len(up) >= MIN_N
            else float("nan")
        )
    return out[0], out[1]


def region_edges(df: pd.DataFrame, h: int, v: str) -> dict[str, float]:
    out = {}
    for rg, d in df[df["h"] == h].groupby("region"):
        up = d[d[call_col(v)] == "UP"]
        if len(up) >= 30:
            out[str(rg)] = float((up["ret"] > 0).mean() - (d["ret"] > 0).mean())
    return out


def regime_edges(df: pd.DataFrame, h: int, v: str) -> dict[str, float]:
    out = {}
    for rg, d in df[(df["h"] == h) & df["regime"].notna()].groupby("regime"):
        up = d[d[call_col(v)] == "UP"]
        if len(up) >= 30:
            out[str(rg)] = float((up["ret"] > 0).mean() - (d["ret"] > 0).mean())
    return out


def _mean(xs: list[float]) -> float:
    xs = [x for x in xs if not np.isnan(x)]
    return float(np.mean(xs)) if xs else float("nan")


def dimensions(
    df: pd.DataFrame, v: str, horizons: tuple[int, ...]
) -> dict[str, tuple[float, list[float]]]:
    """Per dimension: (summary value, per-horizon values) of variant ``v``."""
    per: dict[str, list[float]] = {
        k: [] for k in ("ic", "tb", "edge", "r", "robust", "temporal", "region")
    }
    for h in horizons:
        rk, di, tr, no = (
            ranking(df, h, v),
            directional(df, h, v),
            trading(df, h, v),
            nonoverlap(df, h, v),
        )
        pre, post = period_edges(df, h, v)
        reg = region_edges(df, h, v)
        per["ic"].append(rk["ic"])
        per["tb"].append(rk["tb"])
        per["edge"].append(edge_up(di))
        per["r"].append(tr.get("mean_r", float("nan")))
        per["robust"].append(
            float(np.mean([e > 0 for e in no["edges"]])) if no["edges"] else float("nan")
        )
        both = [x for x in (pre, post) if not np.isnan(x)]
        per["temporal"].append(float(min(both)) if len(both) == 2 else float("nan"))
        per["region"].append(float(np.mean([e > 0 for e in reg.values()])) if reg else float("nan"))
    return {k: (_mean(vs), vs) for k, vs in per.items()}


def verdict(
    base: dict[str, tuple[float, list[float]]], var: dict[str, tuple[float, list[float]]]
) -> dict[str, str]:
    """IMPROVES / DEGRADES / INCONCLUSIVE per dimension: the mean delta must exceed its tolerance AND the delta must have that sign in at least 60 % of the horizons."""
    out = {}
    for k, (b, bv) in base.items():
        x, xv = var[k]
        if np.isnan(b) or np.isnan(x):
            out[k] = "INCONCLUSIVE"
            continue
        deltas = [b2 - a for a, b2 in zip(bv, xv, strict=True) if not (np.isnan(a) or np.isnan(b2))]
        if not deltas:
            out[k] = "INCONCLUSIVE"
            continue
        better = float(np.mean([d > 0 for d in deltas]))
        worse = float(np.mean([d < 0 for d in deltas]))
        if x - b >= EPS[k] and better >= 0.6:
            out[k] = "IMPROVES"
        elif b - x >= EPS[k] and worse >= 0.6:
            out[k] = "DEGRADES"
        else:
            out[k] = "INCONCLUSIVE"
    return out


def overall(v: dict[str, str]) -> str:
    imp, deg = (
        sum(1 for x in v.values() if x == "IMPROVES"),
        sum(1 for x in v.values() if x == "DEGRADES"),
    )
    if imp >= 3 and deg == 0:
        return "IMPROVES"
    if deg >= 2:
        return "DEGRADES"
    return "INCONCLUSIVE"  # one dimension alone, or a mixed picture, is never an improvement


def fmt(x: float, kind: str = "pct") -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/d"
    return {
        "pct": f"{x:+.1%}",
        "p": f"{x:.0%}",
        "num": f"{x:+.3f}",
        "r": f"{x:+.2f}",
        "plain": f"{x:.2f}",
    }[kind]


def render_p0(
    df: pd.DataFrame, horizons: tuple[int, ...] = rt.HORIZONS
) -> tuple[list[str], dict[str, str]]:
    L: list[str] = []
    w = L.append
    if df.empty:
        return ["  (sin observaciones)"], {}
    sup = df.drop_duplicates(["ticker", "date"])
    n_sup = len(sup)
    st = sup["sup_state"].value_counts()
    w(
        f"  Soporte v1 (zona congelada con barras hasta T-1): {n_sup} fechas · ROTO {int(st.get('BROKEN', 0))} ({st.get('BROKEN', 0) / n_sup:.1%}) · MANTENIDO {int(st.get('HELD', 0))} · SIN ZONA {int(st.get('UNAVAILABLE', 0))} (regla omitida, no «mantenido»)."
    )
    w(
        f"  Soporte V0 (sobre el que se calculó el baseline): activaciones {int((df['raw_support'] < 0).sum())} de {int(df['raw_support'].notna().sum())} evaluaciones → regla inactiva."
    )
    rep = df["call0"].eq(df["call_v0_re"]).mean()
    w(
        f"  Control: la regla V0 re-puntuada desde las reglas guardadas coincide con la llamada original en {rep:.2%} de las observaciones."
    )
    w("")
    for h in horizons:
        d = df[df["h"] == h]
        if d.empty:
            continue
        w(
            f"  ── Horizonte {h} meses (N={len(d)}) · base: sube {fmt(float((d['ret'] > 0).mean()), 'p')}, baja {fmt(float((d['ret'] < 0).mean()), 'p')}"
        )
        w(
            "      variante                            SUBE N   acierto  ventaja | BAJA/RISK N  acierto  ventaja  rent.media  DD medio | IC      top20-bot20  D10-D1   | meanR(p/o)  medianR  PF(p/o)     MAE_R  MFE_R  ambig."
        )
        for v in VARIANTS:
            di, rk, tr = directional(df, h, v), ranking(df, h, v), trading(df, h, v)
            trs = (
                "n/d"
                if np.isnan(tr.get("mean_r", float("nan")))
                else f"{fmt(tr['mean_r'], 'r')}/{fmt(tr['mean_r_opt'], 'r')}  {fmt(tr['median_r'], 'r'):>7}  {fmt(tr['pf'], 'plain')}/{fmt(tr['pf_opt'], 'plain')}  {fmt(tr['mae_r'], 'r'):>6} {fmt(tr['mfe_r'], 'r'):>6}  {tr['amb']:.0%}"
            )
            w(
                f"      {NAMES[v]:<34} {di['n_up']:>6}  {fmt(di['up_hit'], 'p'):>7}  {fmt(edge_up(di)):>7} | {di['n_dn']:>10}  {fmt(di['dn_hit'], 'p'):>7}  {fmt(edge_dn(di)):>7}  {fmt(di['dn_mean']):>9}  {fmt(di['dn_mae']):>8} | "
                f"{fmt(rk['ic'], 'num'):>7} {fmt(rk['tb']):>9}   {fmt(rk['d10_d1']):>7} | {trs}"
            )
        di14 = directional(df, h, "V14")
        w(
            f"      V14 como RISK_ALERT: N={di14['n_dn']} · peor caída media tras la alerta {fmt(di14['dn_mae'])} frente a {fmt(di14['base_mae'])} en general · P(caída ≥10 %) {fmt(di14['dn_dd10'], 'p')} frente a {fmt(di14['base_dd10'], 'p')} (la alerta SÍ sirve si el riesgo es mayor que la base, aunque el precio no acabe bajando)."
        )
        w("")
    w(
        "  ── Robustez: ventaja de SUBE en offsets mensuales NO solapados (mediana [mín, máx] · offsets positivos/total · IC mediano [mín, máx])"
    )
    for h in horizons:
        for v in VARIANTS:
            no = nonoverlap(df, h, v)
            e, ic = no["edges"], no["ics"]
            if not e:
                continue
            w(
                f"      {h:>2} m {NAMES[v]:<34} ventaja {fmt(float(np.median(e)))} [{fmt(min(e))}, {fmt(max(e))}] · {sum(1 for x in e if x > 0)}/{len(e)} positivos · IC {fmt(float(np.median(ic)), 'num') if ic else 'n/d'} [{(fmt(min(ic), 'num') + ', ' + fmt(max(ic), 'num')) if ic else 'n/d'}] · top-bottom mediano {fmt(float(np.median(no['tbs']))) if no['tbs'] else 'n/d'}"
            )
    w("")
    w(
        "  ── Estabilidad: ventaja de SUBE por periodo, región y régimen de mercado (diagnóstico; el régimen NO se usa como filtro)"
    )
    for h in (3, 12):
        for v in VARIANTS:
            pre, post = period_edges(df, h, v)
            reg = region_edges(df, h, v)
            rgm = regime_edges(df, h, v)
            w(
                f"      {h:>2} m {NAMES[v]:<34} ≤2022-09 {fmt(pre)} · ≥2025-10 {fmt(post)} · regiones "
                + (", ".join(f"{k} {fmt(x)}" for k, x in sorted(reg.items())) or "n/d")
                + " · régimen "
                + (", ".join(f"{k} {fmt(x)}" for k, x in sorted(rgm.items())) or "n/d")
            )
    w("")
    w(
        "  ── VEREDICTO por dimensión frente a BASELINE_V0 (IMPROVES / DEGRADES / INCONCLUSIVE; una sola dimensión que mejore = INCONCLUSIVE)"
    )
    base = dimensions(df, "V0", horizons)
    labels = {
        "ic": "IC del score",
        "tb": "top20-bottom20",
        "edge": "ventaja de SUBE",
        "r": "esperanza en R",
        "robust": "robustez no solapada",
        "temporal": "estabilidad temporal",
        "region": "estabilidad por región",
    }
    w("      dimensión                  " + "  ".join(f"{NAMES[v][:30]:<30}" for v in VARIANTS))
    verdicts = {}
    for v in VARIANTS:
        verdicts[v] = (
            verdict(base, dimensions(df, v, horizons)) if v != "V0" else dict.fromkeys(base, "—")
        )
    dims = {v: dimensions(df, v, horizons) for v in VARIANTS}
    for k, lab in labels.items():
        cells = []
        for v in VARIANTS:
            val = dims[v][k][0]
            cells.append(
                f"{fmt(val, 'num' if k == 'ic' else 'p' if k in ('robust', 'region') else 'r' if k == 'r' else 'pct')} {verdicts[v][k]}"
            )
        w(f"      {lab:<26} " + "  ".join(f"{c:<30}" for c in cells))
    w(
        "      RESULTADO GLOBAL           "
        + "  ".join(
            f"{('— (referencia)' if v == 'V0' else overall(verdicts[v])):<30}" for v in VARIANTS
        )
    )
    return L, {v: overall(verdicts[v]) for v in VARIANTS if v != "V0"}
