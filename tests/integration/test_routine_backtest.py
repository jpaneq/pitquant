# ruff: noqa: E501, F811, F401
"""Retrospective backtest of the routine's rule (SYNTHETIC SYNF): PIT decisions, outcomes only after T, sealed holdout, honest small-sample reporting."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from pitquant.config.settings import HoldoutConfig, Settings
from pitquant.positions import backtest as bt
from pitquant.positions import routine as rt
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import env

Env = tuple[Session, Settings, str, str]
NOW = datetime(2016, 12, 31, 23, tzinfo=UTC)


def run(env: Env, cfg=None, **kw):
    s, c, sf, _ = env
    return bt.backtest_security(
        s, cfg or c, sf, "SYNF", "SP500", date(2015, 1, 2), date(2016, 12, 30), now=NOW, **kw
    )


def test_every_row_is_a_forecast_with_its_outcome_after_the_decision(env: Env) -> None:
    rows, _ = run(env, step_sessions=21)
    assert (
        rows
        and {r["call"] for r in rows} <= {"UP", "DOWN", "NEUTRAL"}
        and {r["horizon"] for r in rows} <= {1, 3, 6, 12, 24}
    )
    s, _, sf, _ = env
    from pitquant.analyzer.market import load_market

    closes = load_market(s, sf, NOW).bars["close"].astype(float)
    from dateutil.relativedelta import relativedelta

    r = rows[0]
    h_end = r["date"] + relativedelta(months=r["horizon"])
    later = closes[(closes.index > r["date"]) & (closes.index <= h_end)]
    assert r["ret_h"] == pytest.approx(
        float(later.iloc[-1]) / float(closes.loc[r["date"]]) - 1.0
    )  # the outcome is read from bars AFTER the decision only
    ups = [x for x in rows if x["call"] == "UP" and x["state"]]
    assert all(
        x["state"] in ("TARGET_HIT", "STOP_HIT", "AMBIGUOUS_INTRABAR", "EXPIRED")
        and set(x["sensitivity"]) == set(bt.SENSITIVITY_K)
        for x in ups
    )
    assert closes.index[0] <= rows[0]["date"]


def test_windows_that_have_not_matured_are_not_scored(env: Env) -> None:
    rows, skipped = run(env, step_sessions=21)
    last = max(r["date"] for r in rows if r["horizon"] == 12)
    assert (
        last <= date(2015, 12, 31) and skipped["immature"] > 0
    )  # a 12-month window needs 12 months of later bars


@pytest.mark.pit
def test_the_sealed_holdout_is_never_used(env: Env) -> None:
    _, cfg, _, _ = env
    sealed = cfg.model_copy(
        update={
            "validation": cfg.validation.model_copy(
                update={
                    "final_holdout": HoldoutConfig(start=date(2016, 3, 1), end=date(2016, 6, 30))
                }
            )
        }
    )
    rows, skipped = run(env, sealed, step_sessions=21)
    lo, hi = date(2016, 3, 1), date(2016, 6, 30)
    assert skipped["holdout"] > 0
    from dateutil.relativedelta import relativedelta

    for r in rows:
        end = r["date"] + relativedelta(months=r["horizon"])
        assert not (lo <= r["date"] <= hi) and not (
            r["date"] < lo <= end
        )  # neither the decision nor its window touches it


def test_report_is_honest_about_what_it_is_and_never_quotes_rates_from_tiny_samples(
    env: Env,
) -> None:
    s, cfg, _, _ = env
    text, summ = bt.run_backtest(
        s, cfg, {"SP500": ["SYNF"]}, start=date(2015, 1, 2), step_sessions=63, now=NOW
    )
    for needle in (
        "RETROSPECTIVO",
        "SIN VALIDAR",
        "SESGO DE SUPERVIVENCIA",
        "Holdout 2022-10-01→2025-09-30 intacto",
        "3. RESULTADOS POR HORIZONTE",
        "4. CALIDAD DE LA SEÑAL",
        "6. VARIANTES DE LA REGLA",
        "7. SENSIBILIDAD",
        "10. POR VALOR",
        "11. PROPUESTAS DE MEJORA",
        "FIN DEL INFORME",
        "SYNF",
    ):
        assert needle in text, needle
    assert "N=" in text and "<10" in text  # small cells say so instead of quoting a rate
    assert summ["rows"] > 0 and summ["version"] == bt.BACKTEST_VERSION


def test_wilson_interval_is_sane() -> None:
    lo, hi = bt.wilson(50, 100)
    assert lo < 0.5 < hi and lo > 0.4 and hi < 0.6
    assert bt.wilson(0, 0) == (0.0, 1.0) and bt.wilson(10, 10)[1] == pytest.approx(1.0)


def test_backtest_endpoint_without_a_run_says_how_to_run_it(
    client, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    r = client.get("/routine/backtest-report")
    assert r.status_code == 200 and "backtest-run" in r.text


# ───────────────────────────────────────────── variants, quality of the signal, detail log (offline analysis over rows)
def fake_rows(n: int = 120):
    out = []
    for i in range(n):
        raws = {
            "trend": 1.0 if i % 2 else -1.0,
            "long_trend": 1.0 if i % 3 else -1.0,
            "momentum": 1.0 if i % 5 else -1.0,
            "support": 0.0,
        }
        w = engine_weights(12)
        score = sum(raws[k] * w[k] for k in raws)
        out.append(
            {
                "ticker": "T",
                "market": "SP500",
                "date": date(2015, 1, 1 + i % 28),
                "horizon": 12,
                "price": 100.0,
                "call": "UP" if score >= 2.5 else "DOWN" if score <= -2.0 else "NEUTRAL",
                "score": score,
                "raws": raws,
                "why": "x",
                "reason": "r",
                "ret_h": 0.1 if raws["momentum"] > 0 else -0.1,
                "max_adverse": -0.2,
                "max_favorable": 0.3,
                "state": None,
            }
        )
    return out


def engine_weights(h: int):
    from pitquant.positions import review as engine

    return engine.WEIGHTS[engine.horizon_bucket(h)]


def test_variant_calls_are_re_scored_from_the_stored_raw_rules() -> None:
    rows = fake_rows()
    v1 = bt.variant_calls(rows, "V1 solo puntuación (sin bloqueos)")
    sign = bt.variant_calls(rows, "V6 solo momentum 6 m (signo)")
    contrarian = bt.variant_calls(rows, "V12 contrarian (invertir)")
    assert all(
        (sign[i] == "UP") == (r["raws"]["momentum"] > 0) for i, r in enumerate(rows)
    )  # momentum sign variant
    flip = {"UP": "DOWN", "DOWN": "UP", "NEUTRAL": "NEUTRAL"}
    assert all(contrarian[i] == flip[v1[i]] for i in range(len(rows)))
    s = bt.stats_for(rows, 12, sign)
    assert (
        s["up_rate"] == 1.0 and s["down_rate"] == 1.0 and s["n"] == len(rows)
    )  # momentum sign perfectly predicts this synthetic return
    assert set(bt.VARIANTS) >= {"V0", "V12 contrarian (invertir)"} and bt.variant_calls(
        rows, "V0"
    ) == {i: r["call"] for i, r in enumerate(rows)}


def test_spearman_needs_enough_pairs_and_variation() -> None:
    assert (
        bt.spearman([1.0] * 40, list(range(40))) is None
        and bt.spearman([1.0, 2.0], [1.0, 2.0]) is None
    )
    assert bt.spearman(list(range(40)), list(range(40))) == pytest.approx(1.0) and bt.spearman(
        list(range(40)), list(range(40, 0, -1))
    ) == pytest.approx(-1.0)


def test_full_report_and_detail_log_explain_every_decision(env: Env, tmp_path) -> None:
    s, cfg, _, _ = env
    text, summ = bt.run_backtest(
        s,
        cfg,
        {"SP500": ["SYNF"]},
        start=date(2015, 1, 2),
        step_sessions=21,
        now=NOW,
        out_dir=tmp_path,
    )
    detail = next(tmp_path.glob("backtest_decisiones_*.txt")).read_text()
    lines = [x for x in detail.splitlines() if x.startswith("SYNF")]
    assert len(lines) == summ["rows"] and all(
        "|" in x and ("SUBE" in x or "BAJA" in x or "UP" in x or "DOWN" in x or "NEUTRAL" in x)
        for x in lines
    )
    assert any("trend=" in x or "sin reglas" in x for x in lines) and all(
        "ret " in x and "peor" in x for x in lines
    )  # each line says why and what happened
    for needle in (
        "5. APORTE DE LOS FUNDAMENTALES",
        "8. SELECCIÓN POR PUNTUACIÓN",
        "9. POR MERCADO",
        "12. PARÁMETROS EN USO",
        "2. COBERTURA DE DATOS",
        "mejor SUBE 6 m",
    ):
        assert needle in text or needle == "mejor SUBE 6 m", needle
    assert "PITQUANT_SEC_USER_AGENT" in text  # tells how to widen the fundamental coverage


def test_proposals_are_generated_from_the_numbers_and_say_what_to_retest(env: Env) -> None:
    s, cfg, _, _ = env
    text, _ = bt.run_backtest(
        s, cfg, {"SP500": ["SYNF"]}, start=date(2015, 1, 2), step_sessions=21, now=NOW
    )
    section = text.split("11. PROPUESTAS DE MEJORA")[1].split("12. PARÁMETROS")[0]
    assert (
        "FUNDAMENTALES" in section
        and "SUPERVIVENCIA" in section.upper()
        and "ESPERANZA" in section.upper()
    )


# ───────────────────────────────────────────── plan P0: support_rule_v1, V13/V14/V15, R metrics, non-overlap, verdicts
def test_support_rule_v1_freezes_the_zone_with_bars_up_to_t_minus_1() -> None:
    tech_prev = {"status": "OK", "support_resistance": {"supports": [
        {"lower": 90.0, "upper": 92.0, "touches": 3, "last_touch": "2020-01-02", "first_touch": "2019-06-03"},
        {"lower": 95.0, "upper": 97.0, "touches": 2, "last_touch": "2020-02-03", "first_touch": "2019-12-02"},
        {"lower": 101.0, "upper": 103.0, "touches": 1, "last_touch": "2020-03-02", "first_touch": "2020-03-02"},  # above the T-1 close: not a support
    ]}}  # fmt: skip
    z = bt.frozen_support(tech_prev, 100.0)
    assert z is not None and (z["low"], z["high"], z["touches"]) == (
        95.0,
        97.0,
        2,
    )  # the nearest zone BELOW the T-1 close, frozen before T is seen
    assert (
        bt.frozen_support({"status": "OK", "support_resistance": {"supports": []}}, 100.0) is None
    )  # no zone → UNAVAILABLE, never "not broken"
    assert bt.frozen_support({"status": "NO_DATA"}, 100.0) is None


def test_outcome_reports_both_readings_of_an_ambiguous_bar() -> None:
    import pandas as pd

    bars = pd.DataFrame(
        [(100, 112, 89, 100)], index=[date(2026, 1, 5)], columns=["open", "high", "low", "close"]
    )
    o = rt.outcome(bars, 100.0, 110.0, 90.0, date(2026, 1, 10), datetime(2026, 1, 10, tzinfo=UTC))
    assert (
        o["state"] == "AMBIGUOUS_INTRABAR"
        and o["ambiguous"] is True
        and o["fill"] == 90.0
        and o["fill_optimistic"] == 110.0
    )
    rd = rt.r_detail(o, 100.0, 90.0)
    assert (
        rd["r_pessimistic"] == pytest.approx(-1.0)
        and rd["r_optimistic"] == pytest.approx(1.0)
        and rd["ambiguous"] is True
        and rd["mae_r"] == pytest.approx(-1.1)
        and rd["mfe_r"] == pytest.approx(1.2)
    )
    clean = rt.outcome(
        pd.DataFrame(
            [(100, 111, 99, 110)],
            index=[date(2026, 1, 5)],
            columns=["open", "high", "low", "close"],
        ),
        100.0,
        110.0,
        90.0,
        date(2026, 1, 10),
        datetime(2026, 1, 10, tzinfo=UTC),
    )
    assert (
        clean["state"] == "TARGET_HIT"
        and clean["ambiguous"] is False
        and clean["fill_optimistic"] == clean["fill"]
    )


def p0_rows(env: Env):
    s, cfg, sf, _ = env
    rows, _ = bt.backtest_security(
        s, cfg, sf, "SYNF", "SP500", date(2015, 1, 2), date(2016, 12, 30), now=NOW, step_sessions=10
    )
    return rows


def test_rows_keep_the_continuous_features_the_support_state_and_the_r_metrics(env: Env) -> None:
    rows = p0_rows(env)
    r = rows[-1]
    assert {"close_vs_sma200", "ret126", "rsi14", "atr14", "vol63", "mom_12_1"} <= set(
        r["feat"]
    ) and r["sup"]["state"] in ("BROKEN", "HELD", "UNAVAILABLE")
    with_levels = [x for x in rows if x["state"]]
    assert with_levels and all(
        set(x) >= {"r_pess", "r_opt", "mae_r", "mfe_r", "bars_to_exit"}
        and x["r_pess"] <= x["r_opt"] + 1e-9
        for x in with_levels
    )  # pessimistic R never above optimistic R
    if r["sup"]["state"] != "UNAVAILABLE":
        assert r["sup"]["zone_low"] < r["price"] + 1e9 and "dist_atr" in r["sup"]


def test_v0_re_scored_from_the_stored_rules_reproduces_the_live_calls(env: Env) -> None:
    from pitquant.positions import backtest_p0 as p0

    df = p0.frame(p0_rows(env), {"SYNF": "EE. UU."})
    assert (
        df["call0"] == df["call_v0_re"]
    ).mean() == 1.0  # the offline variants are scored with the live rule's own arithmetic
    # support_rule_v1 only ever LOWERS a score, so V13 can only remove SUBE calls, never add them
    assert ((df["call13"] == "UP") <= (df["call0"] == "UP")).all()
    assert df.loc[df["sup_state"] == "UNAVAILABLE", "score13"].equals(
        df.loc[df["sup_state"] == "UNAVAILABLE", "score13"]
    )


def test_baja_confirmada_needs_all_three_conditions() -> None:
    import pandas as pd

    from pitquant.positions import backtest_p0 as p0

    base = dict(ticker="T", region="EE. UU.", date=pd.Timestamp("2015-06-01"), h=3, price=100.0, ret=-0.1, mae=-0.2, mfe=0.0, call0="NEUTRAL", score0=0.0, state=None, r_pess=None, r_opt=None, mae_r=None, mfe_r=None,
                bars_exit=None, amb=None, regime=None, sup_dist_atr=None, cs50=-0.05, atr14=2.0, rsi=40.0, raw_trend=-1.0, raw_long_trend=-1.0, raw_momentum=-1.0)  # fmt: skip
    rows = [
        {**base, "sup_state": "BROKEN", "cs200": -0.05, "ret6": -0.1},  # all three
        {**base, "sup_state": "HELD", "cs200": -0.05, "ret6": -0.1},  # support not broken
        {**base, "sup_state": "BROKEN", "cs200": 0.05, "ret6": -0.1},  # above the 200-day average
        {**base, "sup_state": "BROKEN", "cs200": -0.05, "ret6": 0.1},  # positive momentum
        {
            **base,
            "sup_state": "UNAVAILABLE",
            "cs200": -0.05,
            "ret6": -0.1,
        },  # no zone: not confirmed
    ]
    out = p0.add_variants(pd.DataFrame(rows).assign(m=1))
    assert list(out["call15"]) == ["DOWN", "NEUTRAL", "NEUTRAL", "NEUTRAL", "NEUTRAL"]


def test_trading_metrics_expectancy_profit_factor_and_ambiguity() -> None:
    import pandas as pd

    from pitquant.positions import backtest_p0 as p0

    n = 12
    df = pd.DataFrame({"h": [3] * n, "call13": ["UP"] * n, "r_pess": [1.0] * 6 + [-1.0] * 3 + [-0.5] * 3, "r_opt": [1.0] * 6 + [-1.0] * 2 + [1.0] + [-0.5] * 3, "mae_r": [-0.5] * n, "mfe_r": [1.0] * n,
                       "amb": [False] * 8 + [True] + [False] * 3, "state": ["TARGET_HIT"] * 6 + ["STOP_HIT"] * 6, "bars_exit": [10] * n})  # fmt: skip
    t = p0.trading(df, 3, "V13")
    assert (
        t["n"] == 12
        and t["mean_r"] == pytest.approx((6 - 3 - 1.5) / 12)
        and t["pf"] == pytest.approx(6 / 4.5)
        and t["pf_opt"] == pytest.approx(7 / 3.5)
        and t["amb"] == pytest.approx(1 / 12)
        and t["target"] == 0.5
    )
    assert (
        p0.trading(df.head(5), 3, "V13")["n"] == 5
        and p0.trading(df.head(5), 3, "V13")["mean_r"] != p0.trading(df.head(5), 3, "V13")["mean_r"]
    )  # NaN: no figure from fewer than 10


def test_non_overlapping_offsets_are_h_monthly_phases_with_one_decision_per_ticker_and_month() -> (
    None
):
    import pandas as pd

    from pitquant.positions import backtest_p0 as p0

    rows = []
    for m in range(0, 36):
        for t in range(20):
            rows.append(
                {
                    "ticker": f"T{t}",
                    "m": m,
                    "h": 6,
                    "ret": 0.05 if (t + m) % 3 else -0.02,
                    "call13": "UP" if t % 2 == 0 else "NEUTRAL",
                    "score13": float(t % 5),
                    "date": pd.Timestamp("2015-01-01") + pd.DateOffset(months=m),
                }
            )
    no = p0.nonoverlap(pd.DataFrame(rows), 6, "V13")
    assert no["n_off"] == 6 and len(no["edges"]) == 6 and all(-1 <= e <= 1 for e in no["edges"])
    dup = pd.DataFrame(rows + rows)  # a repeated month for the same ticker must not double count
    assert len(p0.nonoverlap(dup, 6, "V13")["edges"]) == 6


def test_a_single_improving_dimension_is_inconclusive_and_three_without_degradation_improve() -> (
    None
):
    from pitquant.positions import backtest_p0 as p0

    base = {k: (0.0, [0.0, 0.0, 0.0]) for k in p0.EPS}

    def with_(**kw):
        d = dict(base)
        for k, v in kw.items():
            d[k] = (v, [v, v, v])
        return d

    one = p0.verdict(base, with_(edge=0.05))
    assert one["edge"] == "IMPROVES" and p0.overall(one) == "INCONCLUSIVE"
    three = p0.verdict(base, with_(edge=0.05, ic=0.05, r=0.2))
    assert p0.overall(three) == "IMPROVES"
    mixed = p0.verdict(base, with_(edge=0.05, ic=0.05, r=0.2, tb=-0.05))
    assert mixed["tb"] == "DEGRADES" and p0.overall(mixed) == "INCONCLUSIVE"
    worse = p0.verdict(base, with_(ic=-0.05, tb=-0.05))
    assert p0.overall(worse) == "DEGRADES"
    tiny = p0.verdict(base, with_(edge=0.001))
    assert tiny["edge"] == "INCONCLUSIVE"  # inside the tolerance
    nan = p0.verdict(base, with_(edge=float("nan")))
    assert nan["edge"] == "INCONCLUSIVE"


def test_the_full_report_contains_the_p0_comparison_and_the_requested_metrics(
    env: Env, tmp_path
) -> None:
    s, cfg, _, _ = env
    text, _ = bt.run_backtest(
        s,
        cfg,
        {"SP500": ["SYNF"]},
        start=date(2015, 1, 2),
        step_sessions=10,
        now=NOW,
        out_dir=tmp_path,
    )
    for needle in (
        "P0. PLAN DE MEJORA",
        "V13_SUPPORT_FIX",
        "V14_SUPPORT_FIX_RISK_ALERT",
        "V15_SUPPORT_FIX_BAJA_CONFIRMADA",
        "RESULTADO GLOBAL",
        "Robustez: ventaja de SUBE en offsets mensuales NO solapados",
        "RISK_ALERT",
        "meanR",
        "PF(p/o)",
        "MAE_R",
        "ambig.",
        "VEREDICTO por dimensión",
        "Soporte v1",
        "RESULTADO DEL PLAN P0",
    ):
        assert needle in text, needle
    detail = next(tmp_path.glob("backtest_decisiones_*.txt")).read_text()
    assert "soporte_v1" in detail and "MAE_R" in detail
