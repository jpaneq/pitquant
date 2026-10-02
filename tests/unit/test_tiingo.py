# ruff: noqa: E501
"""Tiingo EOD adapter (SYNTHETIC payloads in the vendor's documented layout), budget, adjustment
QA and vendor-vs-official comparison (REAL extracts: AAPL 2020 split, MSFT 2004 special)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from pitquant.core.errors import DataQualityError
from pitquant.market.ca_compare import Agreement, compare_with_official
from pitquant.market.credentials import SourceStatus
from pitquant.market.normalized import CorporateActionKind
from pitquant.market.official_ca import parse_apple, parse_microsoft
from pitquant.market.providers.tiingo import (
    BudgetExceededError,
    TiingoBudget,
    TiingoEODMarketDataProvider,
    adjustment_report,
    parse_prices,
)
from pitquant.market.validation import validate_series
from tests.real_extracts import APPLE_TEXT, MSFT_TEXT

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)


def row(d: str, c: float, div: float = 0.0, split: float = 1.0, adj: float | None = None) -> dict:  # type: ignore[type-arg]
    return {
        "date": f"{d}T00:00:00.000Z", "open": c, "high": c + 1, "low": c - 1, "close": c,
        "volume": 1000, "adjOpen": c, "adjHigh": c + 1, "adjLow": c - 1,
        "adjClose": c if adj is None else adj, "adjVolume": 1000, "divCash": div, "splitFactor": split,
    }  # fmt: skip


def payload(rows: list[dict]) -> bytes:  # type: ignore[type-arg]
    return json.dumps(rows).encode()


SYN = [row("2024-03-04", 100.0, adj=95.0), row("2024-03-05", 101.0, div=1.0, adj=96.0),
       row("2024-03-06", 50.5, split=2.0, adj=97.0), row("2024-03-09", 50.0)]  # fmt: skip


def test_normalize_raw_first_vendor_tier_and_calendar() -> None:
    b = TiingoEODMarketDataProvider().normalize("SYN", payload(SYN))
    assert [x.session_date for x in b.bars] == [
        date(2024, 3, 4),
        date(2024, 3, 5),
        date(2024, 3, 6),
    ]
    assert any("non_session" in w for w in b.warnings)  # the Saturday is kept out
    assert b.bars[0].close == 100.0 and b.bars[0].vendor_adj_close == 95.0  # adjusted = QA only
    kinds = {a.kind: a for a in b.actions}
    div, split = kinds[CorporateActionKind.CASH_DIVIDEND], kinds[CorporateActionKind.SPLIT]
    assert div.ex_date == date(2024, 3, 5) and div.cash_amount == 1.0  # divCash date = ex-date
    assert split.ratio == 2.0 and split.ex_date == date(2024, 3, 6)
    assert {a.provenance.tier.value for a in b.actions} == {"VENDOR"}  # never OFFICIAL
    assert validate_series(b.bars, "XNYS").clean


def test_error_payload_duplicates_and_missing_fields_refused() -> None:
    with pytest.raises(DataQualityError, match="refused"):
        parse_prices(b'{"detail": "Error: Free and Starter users are limited"}')
    with pytest.raises(DataQualityError, match="duplicate"):
        parse_prices(payload([row("2024-03-04", 1), row("2024-03-04", 1)]))
    bad = row("2024-03-04", 1)
    del bad["volume"]
    with pytest.raises(DataQualityError, match="missing"):
        parse_prices(payload([bad]))


def test_token_only_in_header_never_in_url_and_blocked_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fetch(url: str, headers: dict[str, str]) -> bytes:
        seen.update(url=url, headers=headers)
        return payload(SYN)

    monkeypatch.delenv("PITQUANT_TIINGO_API_KEY", raising=False)
    p = TiingoEODMarketDataProvider(fetch=fetch, clock=lambda: NOW)
    assert p.status() is SourceStatus.SOURCE_NOT_CONFIGURED
    with pytest.raises(Exception, match="SOURCE_NOT_CONFIGURED"):
        p.download("AAPL", date(2011, 1, 1))
    monkeypatch.setenv("PITQUANT_TIINGO_API_KEY", "SECRETTOKEN")
    body, url = p.download("AAPL", date(2011, 1, 1), date(2024, 3, 6))
    assert "SECRETTOKEN" not in url and "SECRETTOKEN" not in str(seen["url"])
    assert seen["headers"]["Authorization"] == "Token SECRETTOKEN"  # type: ignore[index]
    assert "/tiingo/daily/aapl/prices" in url and "startDate=2011-01-01" in url
    assert "endDate=2024-03-06" in url and body == payload(SYN)


def test_budget_stops_before_limits_without_sleeping() -> None:
    b = TiingoBudget(hourly=3, daily=5, monthly_symbols=2)
    for t in ("A", "B", "A"):
        b.check_and_record(t, NOW)
    with pytest.raises(BudgetExceededError, match="hourly"):
        b.check_and_record("A", NOW)
    later = NOW + timedelta(hours=2)
    with pytest.raises(BudgetExceededError, match="monthly"):
        b.check_and_record("C", later)  # third unique symbol this month
    b.check_and_record("B", later)  # known symbols still allowed
    assert b.used(later)["symbols_this_month"] == 2


def test_adjustment_report_is_qa_only() -> None:
    rep = adjustment_report(
        payload([row("2024-03-04", 100.0, adj=95.0), row("2024-03-05", 101.0, adj=101.0)])
    )
    assert rep.n_adjusted_days == 1 and rep.last_bar_factor == 1.0
    assert rep.implied_factor_jumps[0][0] == date(2024, 3, 5)


# ───────────── vendor vs official: the official event always wins (real extracts) ─────────
def _vendor_for(official_text: str, security: str, rows: list[dict]):  # type: ignore[no-untyped-def,type-arg]
    del official_text
    return TiingoEODMarketDataProvider().normalize(security, payload(rows)).actions


def test_aapl_2020_split_matches_and_msft_2004_disagrees() -> None:
    apple = parse_apple(APPLE_TEXT.encode(), "AAPL", min_rows=1).actions
    v = _vendor_for("", "AAPL", [row("2020-08-28", 499.23), row("2020-08-31", 129.04, split=4.0)])
    (c,) = compare_with_official(apple, v)
    assert c.status is Agreement.MATCH and not c.differences

    msft = parse_microsoft(MSFT_TEXT.encode(), "MSFT").actions
    vm = _vendor_for("", "MSFT", [row("2004-11-12", 29.97), row("2004-11-15", 27.39, div=3.08)])
    (d,) = compare_with_official(msft, vm)
    assert d.status is Agreement.VENDOR_DISAGREEMENT
    assert d.differences == ["cash_amount: official 3.0 vs vendor 3.08"]
    assert d.info and "SPECIAL_DIVIDEND" in d.info[0]  # kind is informational only
    assert "not decomposed" in d.explanation  # 3.08 = 3.00 + 0.08 is NOT inferred
    assert d.official.cash_amount == 3.0  # official untouched


def test_missing_in_vendor() -> None:
    msft = parse_microsoft(MSFT_TEXT.encode(), "MSFT").actions
    (c,) = compare_with_official(msft, [])
    assert c.status is Agreement.MISSING_IN_VENDOR


# ───────────── ingestion, coverage discovery, D-05 criteria ──────────────────────────────
def test_ingest_symbol_archives_raw_without_token_and_compares(
    session,
    tmp_path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    from pitquant.data.archive import ArchiveStore
    from pitquant.db.models import Price, RawSourceArchive
    from pitquant.market.tiingo_eval import ingest_symbol
    from pitquant.security_master.service import SecurityMaster

    monkeypatch.setenv("PITQUANT_TIINGO_API_KEY", "SECRETTOKEN")
    sid = (
        SecurityMaster(session)
        .register(name="SYN INC", exchange="XNYS", currency="USD")
        .security_id
    )
    p = TiingoEODMarketDataProvider(fetch=lambda u, h: payload(SYN), clock=lambda: NOW)
    res = ingest_symbol(
        session, ArchiveStore(tmp_path), p, ticker="SYN", security_id=sid, start=date(2024, 3, 4)
    )
    again = ingest_symbol(
        session,
        ArchiveStore(tmp_path),
        TiingoEODMarketDataProvider(fetch=lambda u, h: payload(SYN), clock=lambda: NOW),
        ticker="SYN",
        security_id=sid,
        start=date(2024, 3, 4),
    )
    assert res.bars_inserted == 3 and again.bars_inserted == 0  # idempotent
    assert session.query(Price).count() == 3
    arch = session.query(RawSourceArchive).one()
    assert arch.sha256 == res.sha256 and "SECRETTOKEN" not in arch.source_identifier
    assert res.series.clean and res.adjustment.n_adjusted_days == 3
    assert len(res.actions_vendor) == 2  # compared, never stored as official


def test_coverage_discovery_statuses() -> None:
    from pitquant.market.tiingo_eval import CoverageStatus as C
    from pitquant.market.tiingo_eval import UniverseRow, coverage_rows, load_supported

    csv_ = (
        "ticker,exchange,assetType,priceCurrency,startDate,endDate\n"
        "AAA,NASDAQ,Stock,USD,1990-01-01,2026-10-01\n"  # active
        "BBB,NYSE,Stock,USD,2005-01-01,2016-05-03\n"  # delisted, covers period
        "CCC,NYSE,Stock,USD,2019-01-01,2026-10-01\n"  # recycled ticker: starts after the period
        "DDD,NYSE,Stock,USD,2013-06-01,2015-01-01\n"  # partial
    )
    sup = load_supported(csv_.encode())
    u = [UniverseRow("1", t, date(2011, 1, 3), e) for t, e in
         (("AAA", None), ("BBB", date(2016, 5, 3)), ("CCC", date(2014, 1, 1)), ("DDD", date(2015, 1, 1)), ("EEE", date(2012, 1, 1)))]  # fmt: skip
    got = {r.historical_ticker: r.status for r in coverage_rows(u, sup, date(2026, 10, 2))}
    assert got == {"AAA": C.ACTIVE_COVERED, "BBB": C.DELISTED_COVERED, "CCC": C.TICKER_RECYCLED_SUSPECT,
                   "DDD": C.PARTIAL_PERIOD, "EEE": C.MISSING}  # fmt: skip


def test_d05_candidate_requires_every_criterion() -> None:
    from pitquant.market.tiingo_eval import evaluate_d05

    ev = evaluate_d05(
        series=[],
        comparisons=[],
        identity_reproducible=True,
        coverage=None,
        provenance_complete=None,
    )
    assert not ev.candidate and all(c.value == "UNKNOWN" for c, _ in list(ev.criteria.values())[:3])
    good = validate_series(
        TiingoEODMarketDataProvider().normalize("S", payload([row("2011-01-03", 10.0)])).bars,
        "XNYS",
    )
    ev2 = evaluate_d05(
        series=[good],
        comparisons=[],
        identity_reproducible=True,
        coverage=None,
        provenance_complete=True,
    )
    assert not ev2.candidate  # coverage of former constituents unmeasured -> not a candidate


# ───────────── identity without ISIN: OFFICIAL CUSIP chain (ADR-0024) ────────────────────
def _evidence(session, sid: str, kind: str, dates: list[date], value: str = "037833100") -> None:  # type: ignore[no-untyped-def]
    from pitquant.db.models import SecurityIdentifierEvidence

    for d in dates:
        session.add(SecurityIdentifierEvidence(security_id=sid, id_type="CUSIP", value=value, kind=kind,
                    observed_on=d, source_kind="SYN", source_url=f"u{d}", parser_version="t"))  # fmt: skip
    session.flush()


def test_identity_accepts_official_cusip_chain_but_not_derived_or_gapped(session) -> None:  # type: ignore[no-untyped-def]
    from pitquant.coverage import CoverageStatus, _identity
    from pitquant.db.models import Security
    from pitquant.security_master.service import SecurityMaster

    sm = SecurityMaster(session)
    annual = [date(y, 2, 14) for y in range(2011, 2025)]
    a = sm.register(name="SYN A", exchange="XNYS", currency="USD").security_id
    _evidence(session, a, "OFFICIAL", annual)
    dc = _identity(session, session.get_one(Security, a), date(2012, 1, 1), date(2024, 1, 1))
    assert dc.status is CoverageStatus.COMPLETE and "no ISIN" in dc.detail
    late = _identity(session, session.get_one(Security, a), date(2012, 1, 1), date(2026, 9, 1))
    assert late.status is CoverageStatus.PARTIAL  # evidence ends 2024-02: no claim beyond +400d
    d = sm.register(name="SYN D", exchange="XNYS", currency="USD").security_id
    _evidence(session, d, "DERIVED", annual)  # e.g. an ISIN built from a CUSIP: never evidence
    assert (
        _identity(session, session.get_one(Security, d), date(2012, 1, 1), date(2024, 1, 1)).status
        is CoverageStatus.UNRESOLVED_IDENTITY
    )
    g = sm.register(name="SYN G", exchange="XNYS", currency="USD").security_id
    _evidence(session, g, "OFFICIAL", [date(2011, 2, 14), date(2014, 2, 14)])  # 3-year hole
    assert (
        _identity(session, session.get_one(Security, g), date(2012, 1, 1), date(2014, 1, 1)).status
        is CoverageStatus.PARTIAL
    )


# ───────────── deterministic D-05 sample, per-security coverage, fixed thresholds ─────────────
def test_sample_is_deterministic_and_not_cherry_picked() -> None:
    from pitquant.market.tiingo_eval import SAMPLE_SEED, deterministic_sample

    cands = [f"T{i:03d}" for i in range(200)]
    a = deterministic_sample(cands, 20, salt="ACTIVE")
    assert a == deterministic_sample(
        list(reversed(cands)), 20, salt="ACTIVE"
    )  # order of the input is irrelevant
    assert len(a) == 20 and a != deterministic_sample(cands, 20, salt="FORMER")
    assert deterministic_sample(["X", "Y"], 20) in (
        ["X", "Y"],
        ["Y", "X"],
    )  # fewer candidates -> all of them
    assert SAMPLE_SEED == "PITQUANT_D05_SAMPLE_V1"


def _bar(
    d: date, o: float = 10.0, h: float = 11.0, lo: float = 9.0, c: float = 10.0, v: float = 5.0
):  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    return SimpleNamespace(session_date=d, open=o, high=h, low=lo, close=c, volume=v)


def test_security_coverage_counts_gaps_duplicates_noncalendar_and_invalid_ohlc() -> None:
    from pitquant.market.tiingo_eval import security_coverage_row

    sess = [
        d
        for d in __import__("pitquant.data.calendars.market_calendar", fromlist=["get_calendar"])
        .get_calendar("XNYS")
        .sessions(date(2024, 3, 4), date(2024, 3, 15))
    ]
    bars = [_bar(d) for d in sess if d != sess[3]]  # one missing session
    bars += [
        _bar(sess[0]),
        _bar(date(2024, 3, 9)),
        _bar(sess[5], lo=10.5),
    ]  # duplicate, Saturday, close outside [low, high]
    row = security_coverage_row("SYN", "ACTIVE", bars, date(2024, 3, 4), None, date(2024, 3, 15))
    assert row.expected_sessions == len(sess) and row.missing_sessions == 1
    assert row.duplicate_rows == 2 and row.noncalendar_rows == 1 and row.invalid_ohlc == 1
    excused = security_coverage_row(
        "SYN",
        "ACTIVE",
        [b for b in bars if b.session_date != sess[3]],
        date(2024, 3, 4),
        None,
        date(2024, 3, 15),
        documented_missing=frozenset({sess[3]}),
    )
    assert excused.documented_exceptions == 1 and excused.coverage >= row.coverage


def test_sample_verdict_uses_fixed_thresholds_and_missing_measurements_fail() -> None:
    from pitquant.market.tiingo_eval import SecurityCoverage, evaluate_sample

    def row(cat: str, cov: float) -> SecurityCoverage:
        n = 1000
        return SecurityCoverage(
            "T",
            cat,
            date(2011, 1, 3),
            None,
            date(2011, 1, 3),
            date(2026, 9, 30),
            n,
            round(n * cov),
            n - round(n * cov),
            0,
            0,
            0,
        )

    good = (
        [row("ACTIVE", 1.0)] * 49
        + [row("ACTIVE", 0.5)]
        + [row("FORMER", 1.0)] * 19
        + [row("FORMER", 0.5)]
    )  # 98 % active, 95 % former
    v = evaluate_sample(
        good, ground_truth_unexplained=0, mapping_reproducible=True, provenance_complete=True
    )
    assert (
        v.candidate
        and v.active_coverage == pytest.approx(0.98)
        and v.former_coverage == pytest.approx(0.95)
    )
    worse = (
        [row("ACTIVE", 1.0)] * 48 + [row("ACTIVE", 0.5)] * 2 + [row("FORMER", 1.0)] * 20
    )  # 96 % active < 98 %
    assert not evaluate_sample(
        worse, ground_truth_unexplained=0, mapping_reproducible=True, provenance_complete=True
    ).candidate
    assert not evaluate_sample(
        good, ground_truth_unexplained=1, mapping_reproducible=True, provenance_complete=True
    ).candidate
    assert not evaluate_sample(
        good, ground_truth_unexplained=None, mapping_reproducible=None, provenance_complete=None
    ).candidate  # unmeasured = fail
    assert not evaluate_sample(
        [], ground_truth_unexplained=0, mapping_reproducible=True, provenance_complete=True
    ).candidate
