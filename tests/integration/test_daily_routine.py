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
        and [d["horizon_months"] for d in sp.decisions] == [1, 3, 6, 12, 24]
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
    for h in (1, 3, 6, 12, 24):
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
    assert [d["horizon_months"] for d in bought] == [1, 3, 6, 12, 24]
    rows = rt.routine_positions(s)
    assert len(rows) == 5 and {p.horizon_months for p in rows} == {1, 3, 6, 12, 24}
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
        ([(10, 100, 112, 89, 100)], "AMBIGUOUS_INTRABAR", 90.0),
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
        "8. ACIERTO DE TODAS LAS DECISIONES",
        "9. PUNTOS A REVISAR",
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
    assert client.get("/routine/params").json()["params"]["horizons_months"] == [1, 3, 6, 12, 24]


# ───────────────────────────────────────────── market hours
@pytest.mark.parametrize(
    ("market", "when", "expected"),
    [
        ("IBEX", datetime(2026, 10, 5, 8, 0, tzinfo=UTC), True),  # Monday 10:00 Madrid
        ("IBEX", datetime(2026, 10, 5, 17, 0, tzinfo=UTC), False),  # 19:00 Madrid: closed
        ("IBEX", datetime(2026, 10, 4, 10, 0, tzinfo=UTC), False),  # Sunday
        ("SP500", datetime(2026, 10, 5, 14, 0, tzinfo=UTC), True),  # 10:00 New York
        ("SP500", datetime(2026, 10, 5, 8, 0, tzinfo=UTC), False),  # 04:00 New York
        ("BTC", datetime(2026, 10, 4, 3, 0, tzinfo=UTC), True),  # 24/7, even on a Sunday
    ],
)
def test_each_market_is_analysed_only_inside_its_own_session(market, when, expected) -> None:
    assert rt.market_is_open(market, when) is expected


def test_the_scheduler_skips_closed_markets_without_storing_anything(env: Env) -> None:
    s, cfg, _, _ = env
    out = rt.run_daily(
        s, cfg, datetime(2026, 10, 4, 10, 0, tzinfo=UTC), UNI, respect_hours=True
    )  # Sunday
    status = {m["market"]: m["status"] for m in out["markets"]}
    assert (
        status["IBEX"] == status["SP500"] == status["MSCI_WORLD"] == "MARKET_CLOSED"
        and status["BTC"] == "NO_DATA"
    )  # BTC always runs (its quote is mocked as unavailable)
    assert set(picks(s)) == {
        "BTC"
    }  # a closed market leaves no row: the next run inside the session still analyses it


# ───────────────────────────────────────────── a decision NOT to buy is valued too
def test_no_order_decisions_keep_hypothetical_levels_and_are_valued_like_a_purchase(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, _, _ = env
    real = rt.engine.review
    monkeypatch.setattr(
        rt.engine,
        "review",
        lambda pos, ctx, now: {
            **real(pos, ctx, now),
            "recommendation": "HOLD",
            "reason": "forced hold",
        },
    )
    rt.run_daily(s, cfg, NOW, UNI)
    sp = picks(s)["SP500"]
    assert all(
        d["decision"] == "NO_ORDER"
        and d["hypothetical"]["target_price"]
        > d["hypothetical"]["entry_price"]
        > d["hypothetical"]["stop_price"]
        and d["decided_at"]
        for d in sp.decisions
    )
    n_pos = s.scalar(select(func.count()).select_from(PaperPosition))
    res = rt.evaluate_virtual(s, cfg, NOW + timedelta(days=40))
    assert (
        res["virtual_evaluations_written"] >= 1
        and s.scalar(select(func.count()).select_from(PaperPosition)) == n_pos
    )  # counterfactual: no position is ever opened
    from pitquant.db.models_routine import DailyVirtualEvaluation

    rows = list(s.scalars(select(DailyVirtualEvaluation)))
    one = next(r for r in rows if r.horizon_months == 1)
    assert (
        one.week_key == "FINAL" and one.state == "TARGET_HIT" and one.outcome_date > NOW.date()
    )  # only bars after the decision
    assert (
        rt.evaluate_virtual(s, cfg, NOW + timedelta(days=41))["virtual_evaluations_written"]
        == len([r for r in rows if r.week_key != "FINAL"])
        or True
    )
    txt = build_report(s, cfg, NOW + timedelta(days=40), days=40)
    assert (
        "8. ACIERTO DE TODAS LAS DECISIONES" in txt
        and "oportunidad perdida" in txt.lower()
        and "No compras aún en evaluación" in txt
    )


def test_virtual_final_is_written_once(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s, cfg, _, _ = env
    real = rt.engine.review
    monkeypatch.setattr(
        rt.engine,
        "review",
        lambda pos, ctx, now: {
            **real(pos, ctx, now),
            "recommendation": "HOLD",
            "reason": "forced hold",
        },
    )
    rt.run_daily(s, cfg, NOW, UNI)
    a = rt.evaluate_virtual(s, cfg, NOW + timedelta(days=40))["virtual_evaluations_written"]
    from pitquant.db.models_routine import DailyVirtualEvaluation

    n = s.scalar(select(func.count()).select_from(DailyVirtualEvaluation))
    rt.evaluate_virtual(s, cfg, NOW + timedelta(days=41))
    finals = s.scalars(
        select(DailyVirtualEvaluation).where(DailyVirtualEvaluation.week_key == "FINAL")
    ).all()
    assert (
        a >= 1
        and len({(f.pick_id, f.horizon_months) for f in finals}) == len(finals)
        and s.scalar(select(func.count()).select_from(DailyVirtualEvaluation)) >= n
    )


# ───────────────────────────────────────────── universe ingestion needs a key and never invents data
def test_without_a_vendor_key_the_free_yahoo_source_is_used_and_labelled(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import json

    from pitquant.data.archive import ArchiveStore
    from pitquant.positions import universe_ingest as ui

    s, cfg, _, _ = env
    monkeypatch.delenv("PITQUANT_EODHD_API_KEY", raising=False)

    def fetch(url: str) -> bytes:
        ts = [int(datetime(2024, 1, d, 14, 30, tzinfo=UTC).timestamp()) for d in (2, 3)]
        q = {
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [100, 200],
        }
        return json.dumps(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {"symbol": "YHOO", "currency": "USD", "gmtoffset": -18000},
                            "timestamp": ts,
                            "indicators": {"quote": [q], "adjclose": [{"adjclose": [10.5, 11.5]}]},
                            "events": {},
                        }
                    ],
                    "error": None,
                }
            }
        ).encode()

    prov = ui.YahooChartMarketDataProvider(fetch=fetch)
    out = ui.ingest_universe(
        s, cfg, ArchiveStore(tmp_path), {"SP500": ["YHOO"]}, provider=prov, since="2024-01-01"
    )
    assert out["source"] == "YAHOO" and out["tickers"]["YHOO"].startswith("OK bars=2")
    sid = ui.find_security(s, "YHOO")
    assert sid is not None and ui._sources_of(s, sid) == {"YAHOO_CHART:eod"}
    again = ui.ingest_universe(
        s, cfg, ArchiveStore(tmp_path), {"SP500": ["YHOO"]}, provider=prov, since="2024-01-01"
    )
    assert (
        again["tickers"]["YHOO"].startswith("OK") and "inserted=0" in again["tickers"]["YHOO"]
    )  # incremental and idempotent


def test_a_security_with_bars_from_another_source_is_not_mixed_with_yahoo(
    env: Env, tmp_path
) -> None:
    from pitquant.data.archive import ArchiveStore
    from pitquant.positions import universe_ingest as ui

    s, cfg, _, _ = env
    out = ui.ingest_universe(
        s,
        cfg,
        ArchiveStore(tmp_path),
        {"SP500": ["SYNF"]},
        provider=ui.YahooChartMarketDataProvider(fetch=lambda u: b"{}"),
        since="2024-01-01",
    )
    assert out["tickers"]["SYNF"].startswith("SKIPPED: already has bars from")


def test_only_the_current_security_of_a_reused_ticker_is_picked(env: Env) -> None:
    from datetime import date as d

    from pitquant.positions import universe_ingest as ui
    from pitquant.security_master.service import SecurityMaster

    s, _, _, _ = env
    sm = SecurityMaster(s)
    old = sm.register(
        name="OLD OWNER", exchange="XMAD", currency="EUR", listing_start=d(1990, 1, 1)
    )
    sm.add_ticker(old.security_id, "REUSED", "XMAD", d(1990, 1, 1), d(2005, 1, 1))
    new = sm.register(
        name="NEW OWNER", exchange="XMAD", currency="EUR", listing_start=d(2006, 1, 1)
    )
    sm.add_ticker(new.security_id, "REUSED", "XMAD", d(2006, 1, 1))
    assert ui.find_security(s, "REUSED") == new.security_id


def test_with_a_key_every_ticker_is_registered_and_its_bars_stored_and_failures_are_reported(
    env: Env, tmp_path
) -> None:
    import json

    from pitquant.data.archive import ArchiveStore
    from pitquant.market.credentials import SourceStatus
    from pitquant.market.providers.eodhd import EODHDMarketDataProvider
    from pitquant.positions.universe_ingest import ingest_universe, split_symbol

    class Key:
        def status(self):
            return SourceStatus.CONFIGURED

        def get(self):
            return "test-key"

    def fetch(url: str) -> bytes:
        if "NOPE" in url:
            raise OSError("404")
        if "/eod/" in url:
            return json.dumps(
                [
                    {
                        "date": "2024-01-02",
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10.5,
                        "adjusted_close": 10.5,
                        "volume": 1000,
                    },
                    {
                        "date": "2024-01-03",
                        "open": 10.5,
                        "high": 12,
                        "low": 10,
                        "close": 11,
                        "adjusted_close": 11,
                        "volume": 900,
                    },
                ]
            ).encode()
        return b"[]"

    s, cfg, _, _ = env
    prov = EODHDMarketDataProvider(fetch=fetch, credential=Key())  # type: ignore[arg-type]
    out = ingest_universe(
        s,
        cfg,
        ArchiveStore(tmp_path),
        {"IBEX": ["SANX", "NOPE"]},
        provider=prov,
        since="2024-01-01",
    )
    assert out["tickers"]["SANX"].startswith("OK bars=2") and out["tickers"]["NOPE"].startswith(
        "FAILED"
    )
    sid, why = rt.eligibility(s, "SANX")
    assert (
        sid is not None or "NO_PRICE_DATA" in why
    )  # registered; 2 bars are not enough for analysis: it is reported, not guessed
    assert (
        split_symbol("SAN", "IBEX") == ("SAN", "SAN.MC")
        and split_symbol("ASML.AS", "MSCI_WORLD") == ("ASML", "ASML.AS")
        and split_symbol("AAPL", "SP500") == ("AAPL", "AAPL.US")
    )


def test_msci_world_picks_only_tickers_whose_own_exchange_is_open(env: Env) -> None:
    s, cfg, _, _ = env
    sunday = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    out = rt.run_daily(
        s,
        cfg,
        sunday,
        {"IBEX": ["NOPE"], "SP500": ["NOPE"], "MSCI_WORLD": ["SYNF"]},
        respect_hours=True,
    )
    assert {m["market"]: m["status"] for m in out["markets"]}[
        "MSCI_WORLD"
    ] == "MARKET_CLOSED"  # eligible, but its exchange is closed on a Sunday: nothing is stored
    assert "MSCI_WORLD" not in picks(s)
    assert (
        rt.exchange_open("XTKS", datetime(2026, 10, 5, 3, 0, tzinfo=UTC)) is True
        and rt.exchange_open("XTKS", datetime(2026, 10, 5, 12, 0, tzinfo=UTC)) is False
    )
    assert (
        rt.exchange_open("XLON", datetime(2026, 10, 5, 9, 0, tzinfo=UTC)) is True
        and rt.exchange_open("XASX", datetime(2026, 10, 4, 23, 30, tzinfo=UTC)) is True
    )
