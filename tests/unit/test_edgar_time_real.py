"""ADR-0019 regression: EDGAR timestamp semantics, pinned to REAL archived SEC bytes.

tests/fixtures/sec_real/ holds the raw header (.hdr.sgml), filing index page and company
Atom feeds fetched on 2026-10-01 (public SEC data); docs/edgar_time_investigation.json
holds the raw submissions values and HTTP Last-Modified of the same filings.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pitquant.core.errors import DataQualityError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.providers.sec_edgar.parsers import (
    acceptance_raw_consistent,
    eastern_wall_clock_to_utc,
    parse_acceptance_datetime,
    submissions_acceptance_utc,
)

pytestmark = pytest.mark.pit
ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "sec_real"
CASES = json.loads((ROOT / "docs" / "edgar_time_investigation.json").read_text())
ET = ZoneInfo("America/New_York")


def _atom_updated(acc: str) -> datetime:
    for f in FIX.glob("atom_*.xml"):
        for entry in re.findall(rb"<entry>.*?</entry>", f.read_bytes(), flags=re.S):
            if f"<accession-number>{acc}</accession-number>".encode() in entry:
                m = re.search(rb"<updated>([^<]+)</updated>", entry)
                assert m is not None
                return datetime.fromisoformat(m.group(1).decode())
    raise AssertionError(f"{acc} not in archived Atom feeds")


@pytest.mark.parametrize("case", CASES, ids=[c["accession"] for c in CASES])
def test_header_is_eastern_with_dst_against_explicit_offset_clock(case) -> None:  # type: ignore[no-untyped-def]
    acc = case["accession"]
    header = (FIX / f"{acc}.hdr.sgml").read_bytes()
    parsed = parse_acceptance_datetime(header, expected_accession=acc)
    atom = _atom_updated(acc)  # explicit UTC offset: the independent clock
    assert parsed == atom, case["case"]
    # The offset follows DST: -05:00 in winter, -04:00 in summer ("EST" is generic).
    assert atom.utcoffset() == parsed.astimezone(ET).utcoffset()


@pytest.mark.parametrize("case", CASES, ids=[c["accession"] for c in CASES])
def test_index_page_shows_the_header_wall_clock(case) -> None:  # type: ignore[no-untyped-def]
    page = (FIX / f"{case['accession']}-index.htm").read_bytes()
    m = re.search(rb"Accepted</div>\s*<div class=\"info\">([^<]+)<", page)
    assert m is not None
    assert (
        m.group(1).decode().strip().replace("-", "").replace(" ", "").replace(":", "")
        == (case["H_header_raw"])
    )


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["S_submissions_raw"]], ids=lambda c: c["accession"]
)
def test_submissions_field_is_genuine_utc(case) -> None:  # type: ignore[no-untyped-def]
    s = submissions_acceptance_utc(case["S_submissions_raw"])
    atom = _atom_updated(case["accession"])
    assert s == atom
    header = parse_acceptance_datetime((FIX / f"{case['accession']}.hdr.sgml").read_bytes())
    assert acceptance_raw_consistent(case["S_submissions_raw"], header) is True
    # Reading it as Eastern wall time is now a MISMATCH (no lenient double reading).
    as_et = case["S_submissions_raw"].replace("Z", "")
    wrong = eastern_wall_clock_to_utc(datetime.fromisoformat(as_et).replace(tzinfo=None))
    assert acceptance_raw_consistent(wrong.strftime("%Y-%m-%dT%H:%M:%S.000Z"), header) is False


@pytest.mark.parametrize("case", CASES, ids=[c["accession"] for c in CASES])
def test_filing_date_follows_the_1730_eastern_cutoff(case) -> None:  # type: ignore[no-untyped-def]
    page = (FIX / f"{case['accession']}-index.htm").read_bytes()
    m = re.search(rb'Filing Date</div>\s*<div class="info">([^<]+)<', page)
    assert m is not None
    filed = date.fromisoformat(m.group(1).decode().strip())
    if case["S_filingDate_raw"]:  # submissions agrees with the index page
        assert date.fromisoformat(case["S_filingDate_raw"]) == filed
    accepted = parse_acceptance_datetime((FIX / f"{case['accession']}.hdr.sgml").read_bytes())
    local = accepted.astimezone(ET)
    cal = get_calendar("XNYS")
    after_cutoff = (local.hour, local.minute) >= (17, 30)
    expected = cal.next_session(local.date()) if after_cutoff else local.date()
    assert filed == expected


def test_http_last_modified_never_precedes_acceptance() -> None:
    from email.utils import parsedate_to_datetime

    for c in CASES:
        acc = parse_acceptance_datetime((FIX / f"{c['accession']}.hdr.sgml").read_bytes())
        assert parsedate_to_datetime(c["L_last_modified_raw"]) >= acc


def test_dst_ambiguous_and_missing_wall_times_fail_closed() -> None:
    # 2024-11-03 01:30 happens twice in New York: take the LATER instant (EST, 06:30Z).
    assert eastern_wall_clock_to_utc(datetime(2024, 11, 3, 1, 30)) == datetime(
        2024, 11, 3, 6, 30, tzinfo=UTC
    )
    # 2024-03-10 02:30 never happens: take the later candidate (07:30Z), never earlier.
    assert eastern_wall_clock_to_utc(datetime(2024, 3, 10, 2, 30)) == datetime(
        2024, 3, 10, 7, 30, tzinfo=UTC
    )
    with pytest.raises(DataQualityError):
        eastern_wall_clock_to_utc(datetime(2024, 1, 2, 9, 0, tzinfo=UTC))


def test_unparseable_or_naive_submissions_value_is_not_trusted() -> None:
    assert submissions_acceptance_utc("2024-02-20 16:15:02") is None  # naive: unknown zone
    assert submissions_acceptance_utc("garbage") is None
    assert acceptance_raw_consistent("garbage", datetime(2024, 1, 2, tzinfo=UTC)) is False
