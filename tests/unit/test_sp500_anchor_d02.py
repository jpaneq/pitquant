# ruff: noqa: E501
"""D-02: SPY/IVV anchor parsing and reconciliation, spin-offs/transfers/respectively, reconstruction
and the D02_RESEARCH_READY gate. Holdings files are SYNTHETIC but follow the real layouts; the
release excerpts are REAL_EXTRACT (S&P Dow Jones Indices releases, archived locally)."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.db.models import IndexCurrentAnchor, SP500MembershipEvent
from pitquant.universe.sources.sp500_anchor import (
    AnchorEvent,
    AnchorStatus,
    cusip_valid,
    norm_ticker,
    parse_ivv_csv,
    parse_spy_xlsx,
    reconcile,
)
from pitquant.universe.sources.sp500_evidence import (
    EventStatus,
    Timing,
    parse_discovery_csv,
    parse_release,
)
from pitquant.universe.sp500_reconstruct import compute_d02


def xlsx(as_of: str, rows: list[tuple[str, str, str, str, str]]) -> bytes:
    strings: list[str] = []

    def si(s: str) -> int:
        strings.append(s)
        return len(strings) - 1

    def row(r: int, cells: list[tuple[str, str | None]]) -> str:
        return (
            f'<row r="{r}">'
            + "".join(
                f'<c r="{c}{r}" t="s"><v>{si(v)}</v></c>' if v is not None else f'<c r="{c}{r}"/>'
                for c, v in cells
            )
            + "</row>"
        )

    body = [
        row(1, [("A", "Fund Name:"), ("B", "SPDR S&amp;P 500 ETF Trust")]),
        row(2, [("A", "Ticker Symbol:"), ("B", "SPY")]),
        row(3, [("A", "Holdings:"), ("B", f"As of {as_of}")]),
        row(
            4,
            [("A", "Name"), ("B", "Ticker"), ("C", "Identifier"), ("D", "SEDOL"), ("E", "Weight")],
        ),
    ]
    for i, (n, t, c, sd, w) in enumerate(rows):
        body.append(
            f'<row r="{5 + i}"><c r="A{5 + i}" t="s"><v>{si(n)}</v></c><c r="B{5 + i}" t="s"><v>{si(t)}</v></c><c r="C{5 + i}" t="s"><v>{si(c)}</v></c><c r="D{5 + i}" t="s"><v>{si(sd)}</v></c><c r="E{5 + i}"><v>{w}</v></c></row>'
        )
    body.append(row(5 + len(rows), [("A", "Past performance is not a reliable indicator.")]))
    sheet = "<worksheet><sheetData>" + "".join(body) + "</sheetData></worksheet>"
    sst = "<sst>" + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def ivv(
    as_of: str, equities: list[tuple[str, str, float]], extra: list[str] | None = None
) -> bytes:
    head = f'iShares Core S&P 500 ETF\nFund Holdings as of,"{as_of}"\nInception Date,"May 15, 2000"\n\nTicker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date\n'
    rows = [
        f'"{t}","{n}","IT","Equity","1","{w}","1","1","1","United States","NASDAQ","USD","1.00","USD","-"'
        for t, n, w in equities
    ]
    rows += extra or []
    return (head + "\n".join(rows)).encode()


CASH = '"USD","USD CASH","Cash and/or Derivatives","Cash","1","0.1","1","1","1","United States","-","USD","1.00","USD","-"'
FUT = '"ESZ6","S&P500 EMINI DEC 26","Cash and/or Derivatives","Futures","0","0","1","1","1","-","Index","USD","1.00","USD","-"'
UNLISTED = '"HOLX","HOLOGIC INC","Health Care","Equity","28","0.00","28","1","0.01","United States","NO MARKET (E.G. UNLISTED)","USD","1.00","USD","-"'
APPLE, MSFT_C = "037833100", "594918104"


def spy_rows() -> list[tuple[str, str, str, str, str]]:
    return [("APPLE INC", "AAPL", APPLE, "2046251", "7.2"), ("MICROSOFT CORP", "MSFT", MSFT_C, "2588173", "6.5"),
            ("BERKSHIRE HATHAWAY INC CLASS B", "BRK.B", "084670702", "2073390", "1.6"), ("US DOLLAR", "-", "999USDZ92", "-", "0.2"),
            ("TPG INC", "2602335D", "436CVR021", "-", "0.000003")]  # fmt: skip


IVV_EQ = [
    ("AAPL", "APPLE", 7.1),
    ("MSFT", "MICROSOFT", 6.4),
    ("BRK B", "BERKSHIRE HATHAWAY INC CLASS B", 1.6),
]


def test_cusip_check_digit_and_ticker_normalisation() -> None:
    assert cusip_valid(APPLE) and cusip_valid(MSFT_C) and not cusip_valid("037833101")
    assert norm_ticker("BRK.B") == norm_ticker("BRK-B") == norm_ticker("BRK B") == "BRKB"


def test_parsers_filter_non_equity_by_rule_not_by_count() -> None:
    spy = parse_spy_xlsx(xlsx("01-Oct-2026", spy_rows()))
    assert spy.as_of == date(2026, 10, 1) and [h.ticker for h in spy.holdings] == [
        "AAPL",
        "MSFT",
        "BRK.B",
    ]
    reasons = dict(spy.excluded)
    assert any("cash" in v for v in reasons.values()) and any(
        "placeholder" in v for v in reasons.values()
    )
    iv = parse_ivv_csv(ivv("Oct 01, 2026", IVV_EQ, [CASH, FUT, UNLISTED]))
    assert [h.ticker for h in iv.holdings] == [
        "AAPL",
        "MSFT",
        "BRK B",
    ] and iv.key_level == "TICKER_NAME"
    why = " ".join(v for _, v in iv.excluded)
    assert "Cash" in why and "Futures" in why and "no market" in why
    with pytest.raises(DataQualityError):
        parse_ivv_csv(b"not a holdings file")


def test_same_date_anchor_is_multi_source_even_with_different_counts() -> None:
    spy = parse_spy_xlsx(xlsx("01-Oct-2026", spy_rows()))
    iv = parse_ivv_csv(ivv("Oct 01, 2026", IVV_EQ, [CASH]))
    r = reconcile(spy, iv, [])
    assert r.status is AnchorStatus.MULTI_SOURCE_CONFIRMED and r.reconciled == 3
    assert r.status is not AnchorStatus.OFFICIAL_SPDJI  # never labelled official
    assert any("BRK" in n or "TICKER_NAME" in n or "no CUSIP" in n for n in r.notes)


def test_single_extra_equity_is_a_conflict() -> None:
    spy = parse_spy_xlsx(
        xlsx("01-Oct-2026", [*spy_rows(), ("EXTRA CORP", "EXT", "30231G102", "2", "0.1")])
    )
    iv = parse_ivv_csv(ivv("Oct 01, 2026", IVV_EQ))
    r = reconcile(spy, iv, [])
    assert r.status is AnchorStatus.CONFLICT and r.differences == [
        "only in SPY 2026-10-01: EXT (EXTRA CORP)"
    ]


def test_different_dates_need_the_confirmed_event_between_them() -> None:
    spy = parse_spy_xlsx(
        xlsx("01-Oct-2026", [*spy_rows(), ("VYLOR INC", "VYLR", "92892R108", "C0C06F3", "0.07")])
    )
    iv = parse_ivv_csv(ivv("Sep 30, 2026", IVV_EQ))
    assert reconcile(spy, iv, []).status is AnchorStatus.CONFLICT  # unexplained
    ok = reconcile(spy, iv, [AnchorEvent(date(2026, 10, 1), "VYLR", None)])
    assert ok.status is AnchorStatus.MULTI_SOURCE_CONFIRMED and any(
        "advanced" in n for n in ok.notes
    )
    stale = reconcile(
        spy, iv, [AnchorEvent(date(2026, 9, 1), "VYLR", None)]
    )  # an event BEFORE the older snapshot is not applied
    assert stale.status is AnchorStatus.CONFLICT


def test_renamed_issuer_is_corroborated_by_weight_not_silently_matched() -> None:
    spy = parse_spy_xlsx(
        xlsx("01-Oct-2026", [("GENERAL ELECTRIC", "GE", "369604301", "2", "1.00")])
    )
    iv = parse_ivv_csv(ivv("Oct 01, 2026", [("GE", "GE AEROSPACE", 1.05)]))
    r = reconcile(spy, iv, [])
    assert r.status is AnchorStatus.MULTI_SOURCE_CONFIRMED and any(
        "corroborated by ticker + weight" in n for n in r.notes
    )
    far = parse_ivv_csv(ivv("Oct 01, 2026", [("GE", "GE AEROSPACE", 3.0)]))
    assert reconcile(spy, far, []).status is AnchorStatus.CONFLICT


# ───────────────────────────── release structures (REAL_EXTRACT) ─────────────────────────────
RESPECTIVELY = (
    "NEW YORK , March 1, 2024 / PRNewswire / -- S&P Dow Jones Indices will make the following changes to the S&P 500, S&P 100, "
    "S&P MidCap 400, and S&P SmallCap 600 indices effective prior to the open of trading on Monday, March 18 , to coincide with "
    "the quarterly rebalance. S&P MidCap 400 constituents Super Micro Computer Inc. (NASD: SMCI) and Deckers Outdoor Corp. "
    "(NYSE: DECK) will replace Whirlpool Corp. (NYSE: WHR) and Zions Bancorporation N.A. (NASD: ZION) in the S&P 500 respectively, "
    "and Whirlpool and Zions Bancorporation will replace Super Micro Computer and Deckers Outdoor in the S&P MidCap 400, respectively."
)
TRANSFER_SPINOFF = (
    "NEW YORK , Oct. 1, 2026 / PRNewswire / -- S&P Dow Jones Indices will make the following changes to the S&P 500, S&P MidCap 400, "
    "S&P SmallCap 600: Vylor Inc. (NYSE: VYLR) was added to the S&P 500 on October 1 when S&P 500 constituent Corteva Inc (NYSE: CTVA) "
    "spun off Vylor in a transaction completed on that date. Vylor replaces Corteva in the S&P 500. S&P MidCap 400 constituent Twilio Inc. "
    "(NYSE: TWLO) will replace Warner Bros. Discovery, Inc. (NASD: WBD) in the S&P 500, S&P SmallCap 600 constituent Formfactor Inc. "
    "(NASD: FORM) will replace Twilio in the S&P MidCap 400 effective prior to the opening of trading on Tuesday, October 6."
)


def test_respectively_pairs_in_order_never_crossed() -> None:
    ch = parse_release(RESPECTIVELY, date(2024, 3, 1))
    pairs = {(c.added_ticker, c.removed_ticker) for c in ch}
    assert pairs == {("SMCI", "WHR"), ("DECK", "ZION")}  # and NOT SMCI->ZION / DECK->WHR
    assert all(
        c.timing is Timing.BEFORE_OPEN and c.stated_change_date == date(2024, 3, 18) for c in ch
    )


def test_midcap_transfer_enters_sp500_and_spinoff_is_add_only() -> None:
    ch = {
        (c.added_ticker, c.removed_ticker): c
        for c in parse_release(TRANSFER_SPINOFF, date(2026, 10, 1))
    }
    assert ("TWLO", "WBD") in ch  # MidCap constituent enters the S&P 500, WBD leaves it
    assert ("FORM", "TWLO") not in ch  # the MidCap/SmallCap legs are not S&P 500 membership
    vy = ch[("VYLR", "")]
    assert (
        vy.reason_class == "SPINOFF"
        and vy.timing is Timing.EFFECTIVE_ON_DATE
        and vy.stated_change_date == date(2026, 10, 1)
    )
    assert (
        "addition without a simultaneous deletion" in vy.notes
    )  # the parent is NOT removed by the spin-off itself
    assert ("CTVA", "") not in ch and not any(c.removed_ticker == "CTVA" for c in ch.values())
    tw = ch[("TWLO", "WBD")]
    assert tw.timing is Timing.BEFORE_OPEN and tw.stated_change_date == date(
        2026, 10, 6
    )  # «prior to the opening of trading»


def test_ticker_rename_is_not_a_membership_event() -> None:
    rows = parse_discovery_csv(
        b"date,added_tickers,removed_tickers\n2024-01-01,['RVTY'],['RVTY (PREVIOUSLY PKI)']\n",
        date(2011, 1, 1),
    )
    assert rows[0].added == ("RVTY",) and rows[0].removed == (
        "RVTY",
    )  # same security on both sides
    from pitquant.universe.sources.sp500_evidence import match_discovery

    res = match_discovery(rows, [])
    assert all(
        r.status is EventStatus.DISCOVERY_ONLY for r in res
    )  # never promoted to a confirmed exit+entry


# ───────────────────────────── reconstruction & D02 gate ──────────────────────────────────────
def _anchor(
    session: Session, tickers: list[str], as_of: date, status: str = "MULTI_SOURCE_CONFIRMED"
) -> None:
    session.add(
        IndexCurrentAnchor(
            index_code="SP500",
            as_of=as_of,
            status=status,
            key_level="TICKER_NAME",
            members=[{"ticker": t, "name": t, "cusip": None, "sedol": None} for t in tickers],
            reconciled=len(tickers),
            applied_events=[],
            differences=[],
            notes=[],
        )
    )
    session.flush()


def _event(
    session: Session,
    run: str,
    status: str,
    added: str | None,
    removed: str | None,
    disc: date,
    eff: date | None,
) -> None:
    session.add(
        SP500MembershipEvent(
            run_id=run,
            added_ticker=added,
            removed_ticker=removed,
            announcement_at=None,
            stated_change_date=eff,
            timing="AFTER_CLOSE" if eff else None,
            effective_at=datetime(eff.year, eff.month, eff.day, 14, 30, tzinfo=UTC)
            if eff
            else None,
            discovery_date=disc,
            source_tier="OFFICIAL_SPDJI" if eff else "DISCOVERY_ONLY",
            status=status,
            reason="t",
        )
    )
    session.flush()


def test_blocked_without_a_confirmed_anchor(session: Session) -> None:
    rep = compute_d02(session)
    assert rep.anchor_status == "BLOCKED" and not rep.d02_research_ready and rep.cohorts == []
    _anchor(session, ["A"], date(2026, 10, 1), "CONFLICT")
    assert not compute_d02(session).d02_research_ready


def test_unconfirmed_event_breaks_only_earlier_dates_and_replay_is_reversible(
    session: Session,
) -> None:
    _anchor(session, ["AAA", "BBB", "NEW1", "NEW2"], date(2026, 10, 1))
    # confirmed: NEW1 replaced OLD1 (2022-03-15 effective); NEW2 replaced OLD2 (2024-06-24); unconfirmed: a 2019-05 change
    _event(
        session,
        "r",
        EventStatus.OFFICIAL_CONFIRMED.value,
        "NEW1",
        "OLD1",
        date(2022, 3, 15),
        date(2022, 3, 15),
    )
    _event(
        session,
        "r",
        EventStatus.OFFICIAL_CONFIRMED.value,
        "NEW2",
        "OLD2",
        date(2024, 6, 24),
        date(2024, 6, 24),
    )
    _event(session, "r", EventStatus.DISCOVERY_ONLY.value, "AAA", None, date(2019, 5, 2), None)
    rep = compute_d02(session)
    assert rep.reversible is True and rep.n_confirmed == 2
    assert rep.reconstructible_from is not None and rep.reconstructible_from >= date(2019, 5, 2)
    assert all(c > date(2019, 5, 2) for c in rep.cohorts)  # nothing before the break is canonical
    assert (
        any(c.year == 2026 for c in rep.cohorts) and rep.holdout_cohorts_excluded > 0
    )  # holdout months never research cohorts
    assert all(not (date(2022, 10, 1) <= c <= date(2025, 9, 30)) for c in rep.cohorts)
    # a later proven period survives an EARLIER break; the longest run is outside the holdout
    assert len(rep.longest_run) < 60 and not rep.d02_research_ready


def test_d02_gate_needs_60_consecutive_cohorts_outside_the_holdout(session: Session) -> None:
    _anchor(
        session, ["AAA"], date(2022, 9, 30)
    )  # anchor right before the holdout, everything proven
    _event(
        session,
        "r",
        EventStatus.OFFICIAL_CONFIRMED.value,
        "AAA",
        "OLD",
        date(2012, 4, 2),
        date(2012, 4, 2),
    )
    rep = compute_d02(session)
    assert rep.reversible is True and len(rep.longest_run) >= 60 and rep.d02_research_ready
    assert rep.first_complete_year == 2011 and rep.last_complete_year == 2021
    assert rep.preferred == (len(rep.longest_run) >= 96)
    # an unresolved event in 2019-07 cuts the proven region to 2019-08+ (38 months before the holdout starts)
    _event(session, "r", EventStatus.UNRESOLVED.value, None, "ZZZ", date(2019, 7, 1), None)
    rep2 = compute_d02(session)
    assert len(rep2.longest_run) < 60 and not rep2.d02_research_ready
    assert timedelta(days=0) == timedelta(days=0)
