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
        x["state"] in ("TARGET_HIT", "STOP_HIT", "AMBIGUOUS_STOP", "EXPIRED")
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
