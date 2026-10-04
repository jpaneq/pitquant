# ruff: noqa: E501, F811, F401
"""Daily simulated-buy routine (SYNTHETIC SYNF): one analysis per market, horizons 1/3/6/12, entry/target/stop, weekly evaluation, text report."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models_positions import PaperPosition
from pitquant.db.models_routine import DailyEvaluation, DailyPick
from pitquant.positions import routine as rt
from pitquant.positions import service as ps
from pitquant.positions.review import Context
from pitquant.positions.routine_report import build_report
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import env

Env = tuple[Session, Settings, str, str]
NOW = datetime(2016, 6, 30, 23, 0, tzinfo=UTC)
UNI = {"IBEX": ["NOPE1", "NOPE2"], "SP500": ["SYNF"], "MSCI_WORLD": ["NOPE3"]}


@pytest.fixture(autouse=True)
def no_real_btc(monkeypatch: pytest.MonkeyPatch) -> None:
    from pitquant.api import btc as btc_api

    monkeypatch.setattr(
        btc_api,
        "_market",
        lambda db: {
            "quote": {
                "price": None,
                "retrieved_at": None,
                "status": "UNAVAILABLE",
                "source": "BINANCE_SPOT",
            },
            "data_mode": "REAL",
        },
    )


def picks(s: Session) -> dict[str, DailyPick]:
    return {p.market: p for p in s.scalars(select(DailyPick))}


def test_one_company_per_market_per_day_and_what_is_not_accessible_is_recorded(env: Env) -> None:
    s, cfg, _, _ = env
    out = rt.run_daily(s, cfg, NOW, UNI)
    p = picks(s)
    assert [m["market"] for m in out["markets"]] == ["IBEX", "SP500", "MSCI_WORLD", "BTC"]
    assert (
        p["IBEX"].status == "NO_DATA"
        and set(p["IBEX"].unavailable) == {"NOPE1", "NOPE2"}
        and "NOT_RESOLVED" in p["IBEX"].unavailable["NOPE1"]
    )
    assert (
        p["MSCI_WORLD"].status == "NO_DATA"
        and p["BTC"].status == "NO_DATA"
        and "PRICE_UNAVAILABLE" in p["BTC"].unavailable["BTC"]
    )
    sp = p["SP500"]
    assert (
        sp.status == "ANALYZED"
        and sp.ticker == "SYNF"
        and sp.price
        and [d["horizon_months"] for d in sp.decisions] == [1, 3, 6, 12]
    )
    assert all(d["decision"] in ("BUY", "NO_ORDER") and d["reason"] for d in sp.decisions)


def test_running_twice_the_same_day_adds_nothing(env: Env) -> None:
    s, cfg, _, _ = env
    rt.run_daily(s, cfg, NOW, UNI)
    n_pick, n_pos = (
        s.scalar(select(func.count()).select_from(DailyPick)),
        s.scalar(select(func.count()).select_from(PaperPosition)),
    )
    again = rt.run_daily(s, cfg, NOW + timedelta(minutes=30), UNI)
    assert all(m["status"] == "ALREADY_DONE_TODAY" for m in again["markets"])
    assert (
        s.scalar(select(func.count()).select_from(DailyPick)) == n_pick
        and s.scalar(select(func.count()).select_from(PaperPosition)) == n_pos
    )


def test_rotation_is_deterministic_and_cycles_through_the_eligible_tickers() -> None:
    tickers = ["B", "A", "C"]
    days = [date(2026, 10, d) for d in range(1, 7)]
    seq = [rt.pick_ticker(tickers, "SP500", d) for d in days]
    assert seq == [
        rt.pick_ticker(list(reversed(tickers)), "SP500", d) for d in days
    ]  # order of the input does not matter
    assert set(seq[:3]) == {"A", "B", "C"} and seq[:3] == seq[3:]
    assert (
        rt.pick_ticker(tickers, "IBEX", days[0]) != rt.pick_ticker(tickers, "SP500", days[0])
        or len(tickers) == 1
    )


def test_target_and_stop_follow_the_documented_volatility_rule() -> None:
    ctx = Context(price=100.0, atr14=2.0, vol_annual=0.30)
    for h in (1, 3, 6, 12):
        lv = rt.levels(100.0, ctx, h)
        span = 0.30 * (h / 12) ** 0.5
        assert (
            lv is not None
            and lv["target_pct"] == pytest.approx(max(0.02, 0.5 * span))
            and lv["target_price"] == pytest.approx(100 * (1 + lv["target_pct"]))
        )
        assert (
            lv["stop_price"] == pytest.approx(100 - max(2 * 2.0, 0.35 * span * 100))
            and lv["stop_price"] < 100
        )
    assert (
        rt.levels(100.0, Context(price=100.0, atr14=2.0, vol_annual=None), 3) is None
    )  # no volatility: nothing is guessed
    assert rt.levels(100.0, Context(price=100.0, atr14=None, vol_annual=0.3), 3) is None
    long_, short = rt.levels(100.0, ctx, 12), rt.levels(100.0, ctx, 1)
    assert long_["target_pct"] > short["target_pct"] and long_["stop_pct"] >= short["stop_pct"]


def test_a_justified_entry_opens_one_position_per_horizon_with_entry_target_and_stop(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, _, _ = env
    real = rt.engine.review

    def always_add(pos, ctx, now):
        return {**real(pos, ctx, now), "recommendation": "ADD", "reason": "forced for the test"}

    monkeypatch.setattr(rt.engine, "review", always_add)
    rt.run_daily(s, cfg, NOW, UNI)
    sp = picks(s)["SP500"]
    bought = [d for d in sp.decisions if d["decision"] == "BUY"]
    assert [d["horizon_months"] for d in bought] == [1, 3, 6, 12]
    rows = rt.routine_positions(s)
    assert len(rows) == 4 and {p.horizon_months for p in rows} == {1, 3, 6, 12}
    for p, d in zip(sorted(rows, key=lambda x: x.horizon_months), bought, strict=True):
        ev = ps.events_of(s, p.position_id)[0]
        assert (
            p.note.startswith(rt.NOTE_PREFIX)
            and p.stop_rule == "ROUTINE_VOL_ATR"
            and p.stop_price < ev.price
            and p.target_return > 0
        )
        assert (
            ev.price == pytest.approx(d["entry_price"])
            and d["target_price"] == pytest.approx(ev.price * (1 + p.target_return))
            and ev.price_source == "EOD_CLOSE"
        )
    assert (
        bought[0]["target_pct"] <= bought[-1]["target_pct"]
    )  # a longer horizon never projects a smaller move (low-volatility synthetic data sits on the floor)


@pytest.mark.parametrize(
    ("rows", "state", "fill"),
    [
        ([(10, 100, 112, 99, 111)], "TARGET_HIT", 110.0),
        ([(10, 100, 101, 89, 90)], "STOP_HIT", 90.0),
        ([(10, 100, 112, 89, 100)], "AMBIGUOUS_STOP", 90.0),
        (
            [(10, 85, 86, 80, 82)],
            "STOP_HIT",
            85.0,
        ),  # gap below the stop fills at the open, not at the stop
        ([(10, 100, 105, 95, 102)], "EXPIRED", 102.0),
    ],
)
def test_outcome_first_touch_rules(rows, state, fill) -> None:
    bars = pd.DataFrame(
        [r[1:] for r in rows],
        index=[date(2026, 1, r[0]) for r in rows],
        columns=["open", "high", "low", "close"],
    )
    o = rt.outcome(
        bars, 100.0, 110.0, 90.0, date(2026, 1, 10), datetime(2026, 1, 10, 23, tzinfo=UTC)
    )
    assert (o["state"], o["fill"]) == (state, fill)


def test_outcome_ignores_bars_after_the_horizon_and_waits_when_nothing_happened() -> None:
    bars = pd.DataFrame(
        [(100, 150, 99, 140)], index=[date(2026, 2, 1)], columns=["open", "high", "low", "close"]
    )
    assert (
        rt.outcome(bars, 100.0, 110.0, 90.0, date(2026, 1, 10), datetime(2026, 1, 9, tzinfo=UTC))[
            "state"
        ]
        == "IN_PROGRESS"
    )  # the target print is beyond the horizon: not used
    assert (
        rt.outcome(
            pd.DataFrame(columns=["open", "high", "low", "close"]),
            100.0,
            110.0,
            90.0,
            date(2026, 1, 10),
            datetime(2026, 1, 9, tzinfo=UTC),
        )["state"]
        == "IN_PROGRESS"
    )


def open_manual(
    s: Session, cfg: Settings, sf: str, target: float, stop_frac: float, months: int = 3
):
    ctx, _ = ps.equity_context(s, cfg, sf, NOW)
    return ps.open_position(
        s,
        cfg,
        asset_type="EQUITY",
        security_id=sf,
        horizon_months=months,
        notional=10_000,
        price=ctx.price,
        target_return=target,
        stop_price=ctx.price * stop_frac,
        note=f"{rt.NOTE_PREFIX}SP500|SYNF|{months}|pick",
        now=NOW,
        price_source="EOD_CLOSE",
        stop_rule="ROUTINE_VOL_ATR",
    )


@pytest.mark.pit
def test_weekly_evaluation_uses_only_bars_after_the_entry_and_closes_on_target(env: Env) -> None:
    s, cfg, sf, _ = env
    pos = open_manual(s, cfg, sf, target=0.01, stop_frac=0.5)
    res = rt.evaluate_positions(s, cfg, NOW + timedelta(days=20))
    ev = s.scalars(
        select(DailyEvaluation).where(DailyEvaluation.position_id == pos.position_id)
    ).one()
    assert (
        res["closed"] == 1
        and ev.week_key == "FINAL"
        and ev.state == "TARGET_HIT"
        and ev.outcome_date > NOW.date()
    )  # the entry day's own bar is never counted
    st = ps.fold(ps.events_of(s, pos.position_id))
    assert (
        st["closed"]
        and ps.events_of(s, pos.position_id)[-1].price_source == "ROUTINE_RULE"
        and ps.events_of(s, pos.position_id)[-1].price == pytest.approx(ev.detail["target"])
    )
    assert (
        rt.evaluate_positions(s, cfg, NOW + timedelta(days=21))["evaluations_written"] == 0
    )  # closed: nothing more


def test_in_progress_is_recorded_once_per_iso_week(env: Env) -> None:
    s, cfg, sf, _ = env
    pos = open_manual(s, cfg, sf, target=5.0, stop_frac=0.5, months=12)
    first = rt.evaluate_positions(s, cfg, NOW + timedelta(days=8))
    again = rt.evaluate_positions(s, cfg, NOW + timedelta(days=8, hours=3))
    next_week = rt.evaluate_positions(s, cfg, NOW + timedelta(days=18))
    keys = [
        e.week_key
        for e in s.scalars(
            select(DailyEvaluation)
            .where(DailyEvaluation.position_id == pos.position_id)
            .order_by(DailyEvaluation.evaluated_at)
        )
    ]
    assert (
        (
            first["evaluations_written"],
            again["evaluations_written"],
            next_week["evaluations_written"],
        )
        == (1, 0, 1)
        and len(set(keys)) == 2
        and "FINAL" not in keys
    )
    e = s.scalars(
        select(DailyEvaluation).where(DailyEvaluation.position_id == pos.position_id)
    ).first()
    assert e.state == "IN_PROGRESS" and 0 <= e.target_progress < 1


def test_report_is_plain_text_with_every_section_the_parameters_and_the_missing_data(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    rt.run_daily(s, cfg, NOW, UNI)
    open_manual(s, cfg, sf, target=0.01, stop_frac=0.5)
    rt.evaluate_positions(s, cfg, NOW + timedelta(days=20))
    txt = build_report(s, cfg, NOW + timedelta(days=20), days=30)
    for head in (
        "1. PARÁMETROS",
        "2. DATOS NO ACCESIBLES",
        "3. ACTIVIDAD",
        "4. SELECTIVIDAD",
        "5. PREDICCIONES ABIERTAS",
        "6. PREDICCIONES CERRADAS",
        "7. RESUMEN POR MERCADO",
        "8. PUNTOS A REVISAR",
        "FIN DEL INFORME",
    ):
        assert head in txt, head
    for needle in ("target_k: 0.5", "NOT_RESOLVED", "SIN DATOS", "OBJETIVO CUMPLIDO", "SYNF"):
        assert needle in txt, needle
    assert (
        "(N<10)" in txt and "NO están validados" in txt and "no es una predicción" in txt.lower()
    ) or "nada de esto es una predicción" in txt.lower()
    assert txt.isprintable() or "\n" in txt  # plain text, no markup
    assert "<" not in txt.replace("<=", "").replace("N<10", "")


def test_report_before_any_run_says_so_and_invents_nothing(env: Env) -> None:
    s, cfg, _, _ = env
    txt = build_report(s, cfg, NOW)
    assert (
        "la rutina aún no se ha ejecutado" in txt
        and "(ninguna)" in txt
        and "Aún no hay evidencia suficiente" in txt
    )


def test_routine_endpoints(client) -> None:
    r = client.get("/routine/report")
    assert (
        r.status_code == 200
        and r.headers["content-type"].startswith("text/plain")
        and "INFORME DE LA RUTINA" in r.text
    )
    assert client.get("/routine/params").json()["params"]["horizons_months"] == [1, 3, 6, 12]
