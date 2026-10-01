# ruff: noqa: E501  (CSV fixture lines mirror the vendor layout verbatim)
"""Adapter contract tests: Sharadar (SEP/ACTIONS/TICKERS/SP500), EODHD, Alpha Vantage QA,
the normalized pipeline and the total-return engine (ADR-0021).

ALL payloads below are FIXTURES shaped like the documented public schemas. Event facts
reuse primary-source-verified D-05 cases (AAPL 4:1 split ex 2020-08-31, MSFT $3.00 special
dividend ex 2004-11-15, FB→META 2022-06-09, HNZ $72.50 cash 2013-06-07, XTO 0.7098 XOM
2010-06-25); PRICES ARE INVENTED. These tests prove the adapter logic
(ADAPTER_CONTRACT_TESTED), not the vendor's data (REAL_DATA_FULLY_VALIDATED needs a key).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.db.models import CorporateActionEvent, DataQualityIssue, Price, ProviderAdjustedPrice
from pitquant.market.credentials import SourceNotConfiguredError, SourceStatus, redact
from pitquant.market.normalized import (
    CorporateAction,
    CorporateActionKind,
    MarketBar,
    NormalizedBatch,
    Provenance,
    SourceTier,
)
from pitquant.market.pipeline import store_batch
from pitquant.market.providers.alphavantage import (
    AlphaVantageLifecycleQAProvider,
    parse_listing_status,
)
from pitquant.market.providers.eodhd import EODHDMarketDataProvider, parse_split
from pitquant.market.providers.sharadar import SharadarMarketDataProvider, parse_table
from pitquant.market.total_return import InsufficientValuationError, total_return
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.events import EventType, MembershipSequenceError
from pitquant.universe.sources.sharadar_sp500 import (
    OfficialAnnouncement,
    SharadarSP500MembershipProvider,
    candidate_status,
    cross_check_announcements,
)

pytestmark = pytest.mark.pit
K = CorporateActionKind

TICKERS = b"""table,permaticker,ticker,name,exchange,isdelisted,category,cusips,firstpricedate,lastpricedate,currency,lastupdated
SEP,199059,AAPL,Apple Inc,NASDAQ,N,Domestic Common Stock,037833100,1986-01-01,2026-09-30,USD,2026-09-30
SEP,194817,META,Meta Platforms Inc,NASDAQ,N,Domestic Common Stock,30303M102,2012-05-18,2026-09-30,USD,2026-09-30
SEP,194817,FB,Meta Platforms Inc,NASDAQ,N,Domestic Common Stock,30303M102,2012-05-18,2022-06-08,USD,2022-06-09
SEP,111111,XYZ,Old Xyz Corp (FIXTURE),NYSE,Y,Domestic Common Stock,000000001,2001-01-02,2009-12-31,USD,2010-01-04
SEP,222222,XYZ,New Xyz Inc (FIXTURE),NYSE,N,Domestic Common Stock,000000002,2015-03-02,2026-09-30,USD,2026-09-30
SEP,333333,HNZ,H J Heinz Co,NYSE,Y,Domestic Common Stock,423074103,1986-01-01,2013-06-07,USD,2013-06-10
"""

SEP = b"""ticker,date,open,high,low,close,volume,closeadj,closeunadj,lastupdated
AAPL,2020-08-28,124.0,126.0,123.0,124.81,187000000,122.5,499.24,2020-08-28
AAPL,2020-08-31,127.58,131.0,126.0,129.04,225000000,126.7,129.04,2020-08-31
XYZ,2005-06-01,10,11,9,10.5,1000,10.0,10.5,2005-06-01
XYZ,2016-06-01,20,21,19,20.5,2000,20.0,20.5,2016-06-01
"""

ACTIONS = b"""date,action,ticker,name,value,contraticker,contraname
2020-08-31,split,AAPL,Apple Inc,4.0,,
2020-08-07,dividend,AAPL,Apple Inc,0.82,,
2022-06-09,tickerchangeto,FB,Meta Platforms Inc,,META,Meta Platforms Inc
2022-06-09,tickerchangefrom,META,Meta Platforms Inc,,FB,Meta Platforms Inc
2013-06-07,acquisitionby,HNZ,H J Heinz Co,,BRKA,Berkshire (FIXTURE contra)
2013-06-07,delisted,HNZ,H J Heinz Co,,,
"""


def _sharadar():  # type: ignore[no-untyped-def]
    p = SharadarMarketDataProvider(fetch=lambda u: b"")
    tm, sec = p.normalize_tickers(TICKERS)
    return p, tm, sec


# ───────────────────────────── configuration ─────────────────────────────


def test_missing_key_is_source_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PITQUANT_SHARADAR_API_KEY", raising=False)
    p = SharadarMarketDataProvider(fetch=lambda u: b"")
    assert p.status() is SourceStatus.SOURCE_NOT_CONFIGURED
    with pytest.raises(SourceNotConfiguredError):
        p.url("stocks", ticker="AAPL")
    # normalization (no network) keeps working without a key
    _, tm, _ = _sharadar()
    assert p.normalize_prices(SEP, tm).bars


def test_api_key_never_reaches_a_stored_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PITQUANT_SHARADAR_API_KEY", "SECRET123")
    seen = []
    p = SharadarMarketDataProvider(fetch=lambda u: seen.append(u) or b"x")
    _, stored = p.download("stocks", ticker="AAPL")
    assert "SECRET123" in seen[0] and "SECRET123" not in stored and "REDACTED" in stored
    assert redact("https://x/y?api_token=abc&fmt=json") == "https://x/y?api_token=REDACTED&fmt=json"


# ───────────────────────────── Sharadar SEP / ACTIONS / TICKERS ─────────────────────────


def test_sep_raw_close_and_imputed_ohlv() -> None:
    p, tm, _ = _sharadar()
    bars = {
        b.session_date: b for b in p.normalize_prices(SEP, tm).bars if "199059" in b.security_key
    }
    pre = bars[date(2020, 8, 28)]
    assert pre.close == 499.24  # raw = closeunadj, never the split-adjusted close
    assert pre.open == pytest.approx(124.0 * 499.24 / 124.81)
    assert pre.volume == pytest.approx(187000000 / (499.24 / 124.81))
    assert set(pre.imputed_fields) == {"open", "high", "low", "volume"}
    assert pre.vendor_adj_close == 122.5  # QA only
    post = bars[date(2020, 8, 31)]
    assert post.close == 129.04 and post.imputed_fields == ()


def test_reused_ticker_resolves_by_date() -> None:
    p, tm, _ = _sharadar()
    keys = {b.session_date: b.security_key for b in p.normalize_prices(SEP, tm).bars}
    assert keys[date(2005, 6, 1)] == "SHARADAR:111111"
    assert keys[date(2016, 6, 1)] == "SHARADAR:222222"
    with pytest.raises(DataQualityError, match="unknown"):
        tm.resolve("XYZ", date(2012, 1, 3))  # between the two lives: nobody


def test_actions_normalized_without_guessing() -> None:
    p, tm, _ = _sharadar()
    b = p.normalize_actions(ACTIONS, tm)
    kinds = {(a.kind, a.security_key) for a in b.actions}
    assert (K.SPLIT, "SHARADAR:199059") in kinds
    split = next(a for a in b.actions if a.kind is K.SPLIT)
    assert split.ratio == 4.0 and split.ex_date == date(2020, 8, 31)
    div = next(a for a in b.actions if a.kind is K.CASH_DIVIDEND)
    assert div.details["value_basis"] == "UNVERIFIED"
    heinz = next(a for a in b.actions if a.security_key == "SHARADAR:333333" and a.kind is K.MERGER)
    assert heinz.details["consideration"] == "UNKNOWN"  # cash vs stock is never guessed
    assert {d.reason for d in b.delistings} >= {"ACQUIRED", "OTHER"}
    (chg,) = b.tickers
    assert (chg.old_ticker, chg.new_ticker, chg.security_key) == ("FB", "META", "SHARADAR:194817")


def test_unknown_layout_or_action_code_fails_closed() -> None:
    with pytest.raises(DataQualityError, match="missing columns"):
        parse_table("stocks", b"ticker,date,close\nAAPL,2020-01-02,1\n")
    p, tm, _ = _sharadar()
    with pytest.raises(DataQualityError, match="unknown action"):
        p.normalize_actions(
            b"date,action,ticker,name,value,contraticker,contraname\n"
            b"2020-01-02,teleport,AAPL,Apple,1,,\n",
            tm,
        )
    with pytest.raises(DataQualityError, match="HTML"):
        parse_table("stocks", b"<!DOCTYPE html><html>login</html>")


# ───────────────────────────── SHARADAR/SP500 → membership ─────────────────────────


SP_TICKERS = TICKERS + (
    b"SEP,400001,AAA,Aaa Corp (FIXTURE),NYSE,N,Domestic Common Stock,,2000-01-03,2026-09-30,USD,2026-09-30\n"
    b"SEP,400002,BBB,Bbb Corp (FIXTURE),NYSE,Y,Domestic Common Stock,,2000-01-03,2018-03-01,USD,2018-03-02\n"
    b"SEP,400003,CCC,Ccc Corp (FIXTURE),NYSE,N,Domestic Common Stock,,2000-01-03,2026-09-30,USD,2026-09-30\n"
)
SP500 = b"""date,action,ticker,name,contraticker,contraname,note
2026-09-30,current,AAA,Aaa Corp,,,
2026-09-30,current,META,Meta Platforms,,,
2026-09-30,current,CCC,Ccc Corp,,,
2018-03-05,added,CCC,Ccc Corp,BBB,Bbb Corp,replaces BBB (FIXTURE)
2018-03-05,removed,BBB,Bbb Corp,CCC,Ccc Corp,acquired (FIXTURE)
2022-06-09,added,META,Meta Platforms,FB,Meta Platforms,ticker change
2022-06-09,removed,FB,Meta Platforms,META,Meta Platforms,ticker change
2015-01-02,historical,AAA,Aaa Corp,,,
2015-01-02,historical,BBB,Bbb Corp,,,
2015-01-02,historical,FB,Meta Platforms,,,
"""


def _sp(payload: bytes = SP500):  # type: ignore[no-untyped-def]
    p = SharadarMarketDataProvider(fetch=lambda u: b"")
    tm, _ = p.normalize_tickers(SP_TICKERS)
    return SharadarSP500MembershipProvider(
        payload, tm, coverage_start=date(2012, 6, 1), expected_size=(3, 3)
    )


def test_sp500_events_rebuild_history_without_survivorship() -> None:
    src, rec = _sp().reconstruct()
    assert rec.initial == frozenset({"AAA", "BBB", "FB"})  # BBB (delisted later) is there
    assert rec.checked_historical_dates == [date(2015, 1, 2)]
    types = {(e.event_type, e.ticker, e.effective_date) for e in src.events}
    assert (EventType.INDEX_DELETE, "BBB", date(2018, 3, 5)) in types
    assert (EventType.INDEX_ADD, "CCC", date(2018, 3, 5)) in types
    # same permaticker removed/added → a ticker change, not a turnover
    assert (EventType.TICKER_CHANGE, "FB", date(2022, 6, 9)) in types
    assert not any(e.ticker == "META" and e.event_type is EventType.INDEX_ADD for e in src.events)
    assert all(e.identity_resolved for e in src.events)


def test_sp500_membership_before_and_after_and_delisted_member(session: Session) -> None:
    from pitquant.jobs.index_ingest import ingest_event_source
    from pitquant.universe.index_membership import IndexUniverse

    src, _ = _sp().reconstruct()
    rep = ingest_event_source(
        session, src, exchange="XNYS", currency="USD", country="US", expected_size=(3, 3)
    )
    assert rep.status == "ok", rep.errors
    u, sm = IndexUniverse(session), SecurityMaster(session)

    def tick(d: date) -> set[str]:
        return {sm.ticker_as_of(m.security_id, d) or "?" for m in u.universe("SP500", d)}

    assert tick(date(2018, 3, 2)) == {"AAA", "BBB", "FB"}  # day before: BBB still a member
    assert tick(date(2018, 3, 5)) == {"AAA", "CCC", "FB"}  # effective date
    assert tick(date(2022, 6, 9)) == {"AAA", "CCC", "META"}  # same security, new ticker


def test_sp500_inconsistent_snapshot_fails_closed() -> None:
    bad = SP500.replace(b"2015-01-02,historical,BBB", b"2015-01-02,historical,ZZZ")
    with pytest.raises(MembershipSequenceError, match="historical snapshot"):
        _sp(bad).reconstruct()


def test_sp500_cross_check_with_official_announcements() -> None:
    src, _ = _sp().reconstruct()
    ok = [OfficialAnnouncement("CCC", "added", date(2018, 3, 5), "f" * 64)]
    assert cross_check_announcements(src, ok)
    late = [OfficialAnnouncement("CCC", "added", date(2018, 3, 6), "f" * 64)]
    with pytest.raises(MembershipSequenceError, match="vendor vs official"):
        cross_check_announcements(src, late)


def test_candidate_status_needs_real_data() -> None:
    assert candidate_status("FIXTURE") == "ADAPTER_CONTRACT_TESTED"
    assert candidate_status("REAL_DATA") == "CANONICAL_CANDIDATE"


# ───────────────────────────── EODHD ─────────────────────────────


def test_eodhd_raw_prices_unadjusted_dividends_and_split_volume() -> None:
    eod = json.dumps(
        [
            {
                "date": "2020-08-28",
                "open": 504.0,
                "high": 505.0,
                "low": 495.0,
                "close": 499.23,
                "adjusted_close": 122.4,
                "volume": 187000000 * 4,
            },
            {
                "date": "2020-08-31",
                "open": 127.6,
                "high": 131.0,
                "low": 126.0,
                "close": 129.04,
                "adjusted_close": 126.6,
                "volume": 225000000,
            },
        ]
    ).encode()
    splits = json.dumps([{"date": "2020-08-31", "split": "4.000000/1.000000"}]).encode()
    divs = json.dumps(
        [
            {
                "date": "2020-08-07",
                "declarationDate": "2020-07-30",
                "recordDate": "2020-08-10",
                "paymentDate": "2020-08-13",
                "period": "Quarterly",
                "value": 0.205,
                "unadjustedValue": 0.82,
                "currency": "USD",
            }
        ]
    ).encode()
    b = EODHDMarketDataProvider(fetch=lambda u: b"").normalize("K", "AAPL.US", eod, splits, divs)
    pre = next(x for x in b.bars if x.session_date == date(2020, 8, 28))
    assert pre.close == 499.23 and pre.volume == 187000000 and pre.imputed_fields == ("volume",)
    dv = next(a for a in b.actions if a.kind is K.CASH_DIVIDEND)
    assert dv.cash_amount == 0.82  # unadjustedValue: the actual payout
    assert (dv.announcement_date, dv.record_date, dv.payment_date) == (
        date(2020, 7, 30),
        date(2020, 8, 10),
        date(2020, 8, 13),
    )
    assert dv.available_at.date() == date(2020, 7, 30)
    assert parse_split("1.000000/10.000000") == 0.1
    with pytest.raises(DataQualityError):
        EODHDMarketDataProvider().normalize("K", "X.XXX", b"[]", b"[]", b"[]")


# ───────────────────────────── Alpha Vantage (QA only) ─────────────────────────────


def test_alpha_vantage_is_qa_only() -> None:
    _, _, sec = _sharadar()
    rows = parse_listing_status(
        b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
        b"HNZ,H J Heinz Co,NYSE,Stock,1986-01-01,2013-06-10,Delisted\n"
        b"AAPL,Apple Inc,NASDAQ,Stock,1980-12-12,null,Active\n"
    )
    issues = AlphaVantageLifecycleQAProvider().cross_check(sec.securities, rows)
    assert any("AAPL: listing" in i for i in issues)  # 1986 vs 1980: reported, not fixed
    assert AlphaVantageLifecycleQAProvider().role == "QA_ONLY"


# ───────────────────────────── pipeline ─────────────────────────────


def _prov(tier: SourceTier = SourceTier.FIXTURE, raw: str = "r") -> Provenance:
    return Provenance("FIXTURE_VENDOR", tier, raw, "a" * 64, "fixture-1")


def test_pipeline_stores_raw_and_refuses_unproven_or_future(session: Session) -> None:
    sm = SecurityMaster(session)
    sid = sm.register(name="FIXTURE", exchange="XMAD", currency="EUR").security_id
    t = datetime(2024, 3, 1, 16, 35, tzinfo=UTC)
    bar = MarketBar("K", date(2024, 3, 1), 10, 11, 9, 10.5, 100, "EUR", t, _prov(), 10.2)
    future = MarketBar(
        "K",
        date(2099, 1, 2),
        None,
        None,
        None,
        1.0,
        None,
        "EUR",
        datetime(2099, 1, 2, 16, tzinfo=UTC),
        _prov(raw="f"),
    )
    other = MarketBar("UNKNOWN", date(2024, 3, 1), None, None, None, 1.0, None, "EUR", t, _prov())
    b = NormalizedBatch(bars=[bar, future, other])
    rep = store_batch(
        session, b, key_to_security={"K": sid}, market="ES", now=datetime(2026, 10, 1, tzinfo=UTC)
    )
    assert rep.bars_inserted == 1 and len(rep.rejected) == 2
    assert session.query(Price).one().close == 10.5
    assert session.query(ProviderAdjustedPrice).one().adj_close == 10.2  # QA only
    again = store_batch(
        session,
        NormalizedBatch(bars=[bar]),
        key_to_security={"K": sid},
        market="ES",
        now=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert again.bars_existing == 1


def test_complex_spanish_action_from_vendor_needs_official_source(session: Session) -> None:
    sid = SecurityMaster(session).register(name="F", exchange="XMAD", currency="EUR").security_id
    t = datetime(2021, 3, 26, 16, 35, tzinfo=UTC)
    rights = CorporateAction(
        "K", K.RIGHTS_ISSUE, t, _prov(SourceTier.VENDOR), ex_date=date(2021, 3, 26)
    )
    official = CorporateAction(
        "K", K.RIGHTS_ISSUE, t, _prov(SourceTier.OFFICIAL, "o"), ex_date=date(2021, 3, 26)
    )
    rep = store_batch(
        session,
        NormalizedBatch(actions=[rights, official]),
        key_to_security={"K": sid},
        market="ES",
        now=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert rep.requires_official and rep.actions_inserted == 1
    assert session.query(CorporateActionEvent).one().source_tier == "OFFICIAL"
    assert (
        session.query(DataQualityIssue).filter_by(check_name="requires_official_source").count()
        == 1
    )


def test_corporate_action_model_requires_dates_per_kind() -> None:
    t = datetime(2020, 1, 2, tzinfo=UTC)
    with pytest.raises(DataQualityError, match="missing"):
        CorporateAction("K", K.CASH_DIVIDEND, t, _prov(), cash_amount=1.0, currency="USD")
    with pytest.raises(DataQualityError, match="<= 1"):
        CorporateAction("K", K.SPLIT, t, _prov(), ex_date=date(2020, 1, 2), ratio=0.5)
    for kind in K:  # every required kind is representable
        assert kind.value


# ───────────────────────────── total return ─────────────────────────────

T0 = datetime(2000, 1, 1, tzinfo=UTC)


def _a(kind: CorporateActionKind, **kw: object) -> CorporateAction:
    return CorporateAction("K", kind, kw.pop("available_at", T0), _prov(), **kw)  # type: ignore[arg-type]


def test_split_is_neutral_and_dividend_is_reinvested() -> None:
    closes = {date(2020, 8, 28): 500.0, date(2020, 8, 31): 125.0, date(2020, 9, 1): 126.0}
    acts = [_a(K.SPLIT, ex_date=date(2020, 8, 31), ratio=4.0)]
    r = total_return(
        closes, acts, date(2020, 8, 28), date(2020, 8, 31), datetime(2021, 1, 1, tzinfo=UTC)
    )
    assert r.total_return == pytest.approx(0.0)
    acts.append(_a(K.CASH_DIVIDEND, ex_date=date(2020, 9, 1), cash_amount=1.0, currency="USD"))
    r2 = total_return(
        closes, acts, date(2020, 8, 28), date(2020, 9, 1), datetime(2021, 1, 1, tzinfo=UTC)
    )
    assert r2.total_return == pytest.approx((126.0 + 1.0) / 125.0 - 1)


def test_special_dividend_msft_2004() -> None:
    closes = {date(2004, 11, 12): 30.0, date(2004, 11, 15): 27.4}  # FIXTURE prices
    acts = [_a(K.SPECIAL_DIVIDEND, ex_date=date(2004, 11, 15), cash_amount=3.0, currency="USD")]
    r = total_return(
        closes, acts, date(2004, 11, 12), date(2004, 11, 15), datetime(2005, 1, 1, tzinfo=UTC)
    )
    assert r.total_return == pytest.approx(30.4 / 30.0 - 1)


def test_action_unknown_at_as_of_is_not_applied() -> None:
    closes = {date(2004, 11, 12): 30.0, date(2004, 11, 15): 27.4}
    late = datetime(2004, 12, 1, tzinfo=UTC)
    acts = [
        _a(
            K.SPECIAL_DIVIDEND,
            ex_date=date(2004, 11, 15),
            cash_amount=3.0,
            currency="USD",
            available_at=late,
        )
    ]
    r = total_return(
        closes, acts, date(2004, 11, 12), date(2004, 11, 15), datetime(2004, 11, 16, tzinfo=UTC)
    )
    assert r.total_return == pytest.approx(27.4 / 30.0 - 1)


def test_spinoff_needs_a_valuation() -> None:
    closes = {date(2012, 12, 31): 65.0, date(2013, 1, 2): 32.0}
    sp = _a(K.SPINOFF, ex_date=date(2013, 1, 2), ratio=1.0, target_key="ABBV")
    with pytest.raises(InsufficientValuationError):
        total_return(
            closes, [sp], date(2012, 12, 31), date(2013, 1, 2), datetime(2014, 1, 1, tzinfo=UTC)
        )
    r = total_return(
        closes,
        [sp],
        date(2012, 12, 31),
        date(2013, 1, 2),
        datetime(2014, 1, 1, tzinfo=UTC),
        spun_off_close=lambda k, d: 34.0,
    )
    assert r.total_return == pytest.approx((32.0 + 34.0) / 65.0 - 1)


def test_terminal_events_end_the_position() -> None:
    closes = {date(2013, 6, 6): 72.4, date(2013, 6, 7): 72.45, date(2013, 6, 10): 1.0}
    cash = _a(K.CASH_ACQUISITION, effective_date=date(2013, 6, 7), cash_amount=72.5, currency="USD")
    r = total_return(
        closes, [cash], date(2013, 6, 6), date(2013, 6, 10), datetime(2014, 1, 1, tzinfo=UTC)
    )
    assert r.end == date(2013, 6, 7) and r.total_return == pytest.approx(72.5 / 72.4 - 1)
    stock = _a(K.STOCK_ACQUISITION, effective_date=date(2013, 6, 7), ratio=0.7098, target_key="XOM")
    with pytest.raises(InsufficientValuationError):
        total_return(
            closes, [stock], date(2013, 6, 6), date(2013, 6, 10), datetime(2014, 1, 1, tzinfo=UTC)
        )
    r2 = total_return(
        closes,
        [stock],
        date(2013, 6, 6),
        date(2013, 6, 10),
        datetime(2014, 1, 1, tzinfo=UTC),
        acquirer_close=lambda k, d: 100.0,
    )
    assert r2.total_return == pytest.approx(70.98 / 72.4 - 1)
    bk = _a(K.BANKRUPTCY, effective_date=date(2013, 6, 7))
    r3 = total_return(
        closes, [bk], date(2013, 6, 6), date(2013, 6, 10), datetime(2014, 1, 1, tzinfo=UTC)
    )
    assert r3.total_return == pytest.approx(-1.0)


def test_adjusted_series_rebuilt_matches_vendor_qa() -> None:
    """QA use of a vendor adjusted close: the rebuilt return equals the vendor's adjusted
    return when both describe the same split + dividend (FIXTURE numbers)."""
    closes = {date(2020, 8, 28): 500.0, date(2020, 8, 31): 125.0, date(2020, 9, 1): 126.0}
    vendor_adj = {date(2020, 8, 28): 124.0, date(2020, 8, 31): 124.0, date(2020, 9, 1): 125.992}
    acts = [
        _a(K.SPLIT, ex_date=date(2020, 8, 31), ratio=4.0),
        _a(K.CASH_DIVIDEND, ex_date=date(2020, 9, 1), cash_amount=1.0, currency="USD"),
    ]
    r = total_return(
        closes, acts, date(2020, 8, 28), date(2020, 9, 1), datetime(2021, 1, 1, tzinfo=UTC)
    )
    vendor = vendor_adj[date(2020, 9, 1)] / vendor_adj[date(2020, 8, 28)] - 1
    assert abs(r.total_return - vendor) < 0.002
