# ruff: noqa: E501
"""Real corporate actions → Total Return (ADR-0023). Ground truth = official pages / BME
bulletins / vendor raw closes captured from REAL sources (tests/real_extracts, labelled
REAL_EXTRACT). Every expected value is computed INDEPENDENTLY of the engine with closed forms;
vendor adjusted close is never used as truth. No network, no sleeps."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.providers.bme.prices import parse_bulletin_price
from pitquant.market.normalized import CorporateAction, CorporateActionKind, Provenance, SourceTier
from pitquant.market.official_ca import parse_apple, parse_enagas, parse_microsoft
from pitquant.market.total_return import total_return
from tests.real_extracts import (
    AAPL_CLOSES,
    APPLE_TEXT,
    BME_ROWS,
    ENAGAS_HTML,
    MSFT_CLOSES,
    MSFT_TEXT,
)

NOW = datetime(2026, 10, 2, tzinfo=UTC)
K = CorporateActionKind


def _closes(d: dict[str, float]) -> dict[date, float]:
    return {date.fromisoformat(k): v for k, v in d.items()}


# ───────────────────────────── official page parsers (real rows) ──────────────────────
def test_apple_split_has_effective_date_and_no_invented_ex_date() -> None:
    p = _apple()
    (split,) = p.actions
    assert split.kind is K.SPLIT and split.ratio == 4.0
    assert split.announcement_date == date(2020, 7, 30)
    assert split.record_date == date(2020, 8, 24)
    assert split.effective_date == date(2020, 8, 31)  # first split-adjusted trading day
    assert split.ex_date is None  # Apple publishes none: never inferred
    assert split.anchor_date == date(2020, 8, 31)
    # Apple dividends carry no ex-date → unresolved, not normalized
    assert [u["payment_date"] for u in p.unresolved] == ["2020-11-12", "2020-08-13", "2020-05-14"]
    assert (
        p.unresolved[1]["cash_amount"] == ".82" and p.unresolved[1]["record_date"] == "2020-08-10"
    )


def _apple():  # type: ignore[no-untyped-def]
    return parse_apple(APPLE_TEXT.encode(), "AAPL", min_rows=1)


def test_enagas_rows_map_gross_amount_ex_and_payment_dates() -> None:
    p = parse_enagas(ENAGAS_HTML.encode(), "ENG")
    by_ex = {a.ex_date: a for a in p.actions}
    a = by_ex[date(2020, 7, 7)]
    assert (a.payment_date, a.cash_amount, a.currency) == (date(2020, 7, 9), 0.96, "EUR")
    assert a.details["type"] == "Complementary" and a.details["for"] == "Fiscal year 2019"
    b = by_ex[date(2020, 12, 21)]
    assert (b.payment_date, b.cash_amount) == (date(2020, 12, 23), 0.672)
    assert by_ex[date(2023, 12, 20)].cash_amount == 0.696  # dot decimal format
    assert a.announcement_date is None  # not published: stays unknown
    # known only from the ex-date close (conservative), never earlier
    assert a.available_at.date() == date(2020, 7, 7)
    # a row without ex-date is reported, not guessed
    assert [u["payment_date"] for u in p.unresolved] == ["02/07/2015"]


def test_enagas_header_change_is_refused() -> None:
    with pytest.raises(DataQualityError, match="header changed"):
        parse_enagas(ENAGAS_HTML.replace("Ex dividend date", "Record date").encode(), "ENG")


def test_microsoft_scheme_has_all_four_dates() -> None:
    (a,) = parse_microsoft(MSFT_TEXT.encode(), "MSFT").actions
    assert a.kind is K.SPECIAL_DIVIDEND and a.cash_amount == 3.0
    assert (a.announcement_date, a.ex_date, a.record_date, a.payment_date) == (
        date(2004, 7, 20),
        date(2004, 11, 15),
        date(2004, 11, 17),
        date(2004, 12, 2),
    )
    assert a.announcement_date < a.ex_date < a.record_date < a.payment_date


# ───────────────────────────── real Total Return vs independent calculation ───────────
def test_real_aapl_split_total_return_independent() -> None:
    split = parse_apple_split()
    closes = _closes(AAPL_CLOSES)
    res = total_return(closes, [split], date(2020, 8, 28), date(2020, 8, 31), NOW)
    expected = 129.04 / (499.23 / 4) - 1  # price relative on a split-adjusted basis
    assert res.total_return == pytest.approx(expected, rel=1e-12)
    # raw price return would claim a -74 % crash: the split creates NO artificial return
    raw = 129.04 / 499.23 - 1
    assert raw < -0.74 and res.total_return > 0
    # whole window 08-25 → 09-04, product of daily adjusted relatives
    full = total_return(closes, [split], date(2020, 8, 25), date(2020, 9, 4), NOW)
    assert full.total_return == pytest.approx(120.96 / (499.30 / 4) - 1, rel=1e-12)


def parse_apple_split() -> CorporateAction:
    return _apple().actions[0]


def test_real_msft_special_dividend_and_enagas_dividends_independent() -> None:
    (m,) = parse_microsoft(MSFT_TEXT.encode(), "MSFT").actions
    r = total_return(_closes(MSFT_CLOSES), [m], date(2004, 11, 12), date(2004, 11, 15), NOW)
    assert r.total_return == pytest.approx((27.39 - 29.97 + 3.00) / 29.97, rel=1e-12)

    eng = {a.ex_date: a for a in parse_enagas(ENAGAS_HTML.encode(), "ENG").actions}
    cases = {  # session pairs (day before ex, ex-date) with BME bulletin closes
        ("20231219", "20231220", date(2023, 12, 20), 0.696),
    }
    for d0, d1, ex, amount in cases:
        b0, prev0 = _bar(d0)
        b1, prev1 = _bar(d1)
        assert prev1 == b0.close  # the bulletin's own «previous close» chains
        res = total_return(
            {b0.session_date: b0.close, b1.session_date: b1.close},
            [eng[ex]],
            b0.session_date,
            b1.session_date,
            NOW,
        )
        assert res.total_return == pytest.approx(
            (b1.close - b0.close + amount) / b0.close, rel=1e-12
        )
        assert res.total_return == pytest.approx(-0.01823635272945423, rel=1e-9)
    _ = prev0


def _bar(ymd: str):  # type: ignore[no-untyped-def]
    d = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
    return parse_bulletin_price(BME_ROWS[ymd], BME_ROWS[ymd].encode(), "ENG", d, "ENG")


def test_bme_bulletin_row_parsing_and_guards() -> None:
    bar, prev = _bar("20240702")
    assert (bar.open, bar.high, bar.low, bar.close, bar.volume) == (
        None,
        13.1,
        12.77,
        12.79,
        2742659.0,
    )
    assert prev == 14.10 and bar.currency == "EUR"
    with pytest.raises(DataQualityError, match="previous date"):
        parse_bulletin_price(
            BME_ROWS["20240702"].replace("01-07-24", "28-06-24"),
            b"x",
            "ENG",
            date(2024, 7, 2),
            "ENG",
        )
    with pytest.raises(DataQualityError, match="no price row"):
        parse_bulletin_price(BME_ROWS["20240702"], b"x", "XXX", date(2024, 7, 2), "XXX")


# ───────────────────────────── split invariance & dividend formula ────────────────────
def _prov() -> Provenance:
    return Provenance("FIXTURE", SourceTier.FIXTURE, "t", "0" * 64, "t-1")


def test_split_invariance_synthetic_100_eur() -> None:
    """SYNTHETIC: 100 EUR x 1 share -> 50 EUR x 2 shares = 100 EUR, return 0."""
    s = CorporateAction("X", K.SPLIT, NOW, _prov(), ex_date=date(2024, 3, 5), ratio=2.0)
    r = total_return(
        {date(2024, 3, 4): 100.0, date(2024, 3, 5): 50.0},
        [s],
        date(2024, 3, 4),
        date(2024, 3, 5),
        NOW,
    )
    assert r.total_return == pytest.approx(0.0, abs=1e-15)
    inv = CorporateAction("X", K.REVERSE_SPLIT, NOW, _prov(), ex_date=date(2024, 3, 5), ratio=0.1)
    r2 = total_return(
        {date(2024, 3, 4): 10.0, date(2024, 3, 5): 100.0},
        [inv],
        date(2024, 3, 4),
        date(2024, 3, 5),
        NOW,
    )
    assert r2.total_return == pytest.approx(0.0, abs=1e-12)


def test_split_requires_ex_or_effective_date() -> None:
    with pytest.raises(DataQualityError, match="ex_date or effective_date"):
        CorporateAction("X", K.SPLIT, NOW, _prov(), ratio=2.0)
    with pytest.raises(DataQualityError, match="missing"):
        CorporateAction(
            "X",
            K.CASH_DIVIDEND,
            NOW,
            _prov(),
            effective_date=date(2024, 1, 2),
            cash_amount=1,
            currency="EUR",
        )


def test_simple_dividend_formula() -> None:
    d = CorporateAction(
        "X",
        K.CASH_DIVIDEND,
        NOW,
        _prov(),
        ex_date=date(2024, 3, 5),
        cash_amount=2.0,
        currency="EUR",
    )
    r = total_return(
        {date(2024, 3, 4): 100.0, date(2024, 3, 5): 99.0},
        [d],
        date(2024, 3, 4),
        date(2024, 3, 5),
        NOW,
    )
    assert r.total_return == pytest.approx((99.0 - 100.0 + 2.0) / 100.0, rel=1e-12)


# ───────────────────────────── DB: duplicates & unknown ex-dates ──────────────────────
def test_reingested_page_version_does_not_double_count_and_unknown_ex_date_is_refused(
    session: Session,
) -> None:
    from dataclasses import replace

    from pitquant.data.point_in_time.context import PITContext
    from pitquant.db.models import DataQualityIssue
    from pitquant.market.normalized import MarketBar, NormalizedBatch
    from pitquant.market.pipeline import store_batch
    from pitquant.market.total_return import InsufficientValuationError
    from pitquant.security_master.service import SecurityMaster

    sid = (
        SecurityMaster(session)
        .register(name="FIXTURE", exchange="XMAD", currency="EUR")
        .security_id
    )
    p = parse_enagas(ENAGAS_HTML.encode(), "ENG")
    ex = next(a for a in p.actions if a.ex_date == date(2023, 12, 20))
    bars = [
        MarketBar("ENG", date(2023, 12, 19), None, 16.805, 16.635, 16.67, 1.0, "EUR",
                  datetime(2023, 12, 19, 16, 35, tzinfo=UTC), _prov()),
        MarketBar("ENG", date(2023, 12, 20), None, 16.06, 15.645, 15.67, 1.0, "EUR",
                  datetime(2023, 12, 20, 16, 35, tzinfo=UTC), _prov()),
    ]  # fmt: skip
    for sha in ("a" * 64, "b" * 64):  # two captures of the same page
        v = replace(ex, provenance=replace(ex.provenance, source_hash=sha))
        store_batch(
            session,
            NormalizedBatch(bars=bars, actions=[v]),
            key_to_security={"ENG": sid},
            market="ES",
            now=NOW,
        )
    ctx = PITContext(session, NOW)
    assert len(ctx.market_actions(sid)) == 1
    tr = ctx.total_return(sid, date(2023, 12, 19), date(2023, 12, 20))
    assert tr.total_return == pytest.approx((15.67 - 16.67 + 0.696) / 16.67, rel=1e-12)
    session.add(DataQualityIssue(entity="corporate_action_events", security_id=sid,
        check_name="ca_unresolved_ex_date", severity="medium",
        details={"window_from": "2023-12-10", "window_to": "2023-12-22", "payment_date": "2023-12-22"}))  # fmt: skip
    session.flush()
    with pytest.raises(InsufficientValuationError, match="unknown ex-date"):
        ctx.total_return(sid, date(2023, 12, 19), date(2023, 12, 20))


# ───────────────────────────── ex-date from a structured source ────────────────────────
_EODHD_AAPL_DIV = (
    b'[{"date":"2020-08-07","declarationDate":"2020-07-30","recordDate":"2020-08-10",'
    b'"paymentDate":"2020-08-13","period":"Quarterly","value":0.205,"unadjustedValue":0.82,'
    b'"currency":"USD"}]'
)


def test_ex_date_merge_requires_full_match_and_keeps_vendor_tier() -> None:
    from pitquant.market.official_ca import merge_vendor_ex_dates

    p = _apple()
    p.unresolved.append(
        {"kind": "CASH_DIVIDEND", "announcement_date": "2020-07-30", "record_date": "2020-08-10",
         "payment_date": "2020-08-13", "cash_amount": ".82", "reason": "x"}
    )  # fmt: skip
    p.unresolved.append(  # same dates, different amount -> must NOT merge
        {"kind": "CASH_DIVIDEND", "announcement_date": "2020-07-30", "record_date": "2020-08-10",
         "payment_date": "2020-08-13", "cash_amount": ".83", "reason": "x"}
    )  # fmt: skip
    got, left = merge_vendor_ex_dates(
        p.unresolved[-2:], _EODHD_AAPL_DIV, "v" * 64, "o" * 64, "AAPL", "XNYS", "APPLE_IR+EODHD"
    )
    assert len(got) == 1 and len(left) == 1 and left[0]["cash_amount"] == ".83"
    d = got[0]
    assert d.ex_date == date(2020, 8, 7) and d.cash_amount == 0.82
    assert d.provenance.tier is SourceTier.VENDOR  # weakest field wins
    assert "vendor" in d.details["field_sources"]["ex_date"]
    assert d.record_date == date(2020, 8, 10) and d.payment_date == date(2020, 8, 13)
