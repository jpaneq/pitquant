# ruff: noqa: E501

"""Regression cases from the dated critical window; fixture prose, no live requests."""

from datetime import date

import pytest
from scripts.apply_d02_critical_identity import EVENTS
from sqlalchemy.orm import Session

from pitquant.research import first_ml_contract as contract
from pitquant.universe.identity_events import Fetched, apply_events
from pitquant.universe.sources.sp500_evidence import parse_release
from tests.unit.test_identity_bridge import F13World


@pytest.mark.pit
def test_short_removed_name_keeps_nemours_and_uses_full_local_mention() -> None:
    text = (
        "Charter Communications Inc. (NASD: CHTR) will replace E. I. du Pont de Nemours and Co. (NYSE: DD) "
        "in the S&P 100, and SBA Communications Corp. (NASD: SBAC) will replace E. I. du Pont de Nemours "
        "in the S&P 500 effective prior to the open on Friday, September 1."
    )
    changes = parse_release(text, date(2017, 8, 24))
    assert len(changes) == 1
    assert changes[0].removed_ticker == "DD"
    assert changes[0].removed_name == "E. I. du Pont de Nemours and Co."
    assert changes[0].stated_change_date == date(2017, 9, 1)


@pytest.mark.pit
@pytest.mark.parametrize("removed", ["E. I. du Pont de Nemour", "E. I. du Pont de Nemours Class C"])
def test_removed_name_similarity_or_class_difference_is_not_an_alias(removed: str) -> None:
    text = (
        "E. I. du Pont de Nemours and Co. (NYSE: DD) is merging. "
        f"SBA Communications Corp. (NASD: SBAC) will replace {removed} "
        "in the S&P 500 effective prior to the open on Friday, September 1."
    )
    assert parse_release(text, date(2017, 8, 24)) == []


@pytest.mark.pit
@pytest.mark.parametrize("key", ["CSC_DXC", "DOW_DOWDUPONT"])
def test_successor_requires_transaction_phrases_not_just_names(session: Session, key: str) -> None:
    fw = F13World(session)
    ev = next(e for e in EVENTS if e.key == key)
    before, after = fw.sec(ev.old_name_only or "before"), fw.sec("after")
    fw.member(before, ev.old_name_only or "before", "NAME_ONLY")
    fw.evidence(after, ev.new_cusip)
    for q, c in ev.verify:
        fw.e13(q, c, "irrelevant issuer", "COM")
    weak = {ev.accession: Fetched("a" * 64, fw.arch.archive_id, "CSC DXC Dow DowDuPont", ev.form)}
    assert not apply_events(session, None, None, (ev,), fetched=weak)[0].applied


@pytest.mark.pit
def test_critical_target_is_85_and_three_calendar_folds_without_changing_100() -> None:
    months = [date(2015 + (8 + i) // 12, (8 + i) % 12 + 1, 1) for i in range(85)]
    folds = contract.walk_forward_folds(months).folds
    assert len(folds) == 3
    assert [(f.n_train_months, f.purged_months, f.test_end - f.test_start + 1) for f in folds] == [
        (37, 12, 12),
        (49, 12, 12),
        (61, 12, 12),
    ]
    assert contract.EMBARGO_MONTHS == 1
    assert contract.REQUIRED_SECURITIES == 100
    assert all(f.test_end < contract.month_index(contract.HOLDOUT[0]) for f in folds)


@pytest.mark.pit
@pytest.mark.parametrize("index", ["S&P 500", "S&P MIDCAP 400"])
def test_indexless_pair_needs_exact_sp500_summary(index: str) -> None:
    text = (
        "Fortune Brands Home & Security Inc. (NYSE: FBHS) will replace Cablevision Systems Corp. (NYSE: CVC), "
        "and Another Inc. (NYSE: OTHER) will replace Fortune Brands in the S&P MidCap 400 "
        "after the close of trading on Thursday, June 23. "
        f"{index} INDEX – June 23, 2016 COMPANY GICS ECONOMIC SECTOR "
        "ADDED Fortune Brands Home & Security Consumer Discretionary Building Products "
        "DELETED Cablevision Systems Consumer Discretionary Cable & Satellite"
    )
    changes = parse_release(text, date(2016, 6, 21))
    assert [(x.added_ticker, x.removed_ticker) for x in changes] == (
        [("FBHS", "CVC")] if index == "S&P 500" else []
    )


@pytest.mark.pit
def test_at_the_open_is_exact_not_date_tba() -> None:
    text = (
        "Incyte Corp. (NASD: INCY) will replace Spectra Energy Corp. (NYSE: SE) "
        "in the S&P 500 effective at the open of trading on Tuesday, February 28."
    )
    changes = parse_release(text, date(2017, 2, 23))
    assert changes[0].stated_change_date == date(2017, 2, 28)
    assert changes[0].timing.value == "BEFORE_OPEN"


@pytest.mark.pit
def test_br_alias_is_scoped_and_keeps_class() -> None:
    from pitquant.universe.document_aliases import document_name

    raw = "CBRE Group, Inc. Class AREIT"
    assert document_name(raw, "0001193125-16-777823") == "CBRE Group, Inc. Class A"
    assert document_name(raw, "another-accession") == raw
    assert (
        document_name("CBRE Group, Inc. Class CREIT", "0001193125-16-777823")
        == "CBRE Group, Inc. Class CREIT"
    )


@pytest.mark.pit
def test_explicit_concatenated_13f_class_a_does_not_resolve_class_c(session: Session) -> None:
    from pitquant.universe.identity_bridge import candidates_for

    fw = F13World(session)
    fw.e13("2016Q3", "N53745100", "LYONDELLBASELL INDUSTRIES N SHS - A -", "")
    assert len(candidates_for(session, "LyondellBasell Industries NV Class A", "2016Q3")) == 1
    assert candidates_for(session, "LyondellBasell Industries NV Class C", "2016Q3") == []


@pytest.mark.pit
@pytest.mark.parametrize("paired", [True, False])
def test_absent_removal_restored_only_for_same_pretraded_official_pair(
    session: Session, paired: bool
) -> None:
    from pitquant.universe.sp500_anchor_graph import reconstruct
    from tests.unit.test_sp500_anchor_graph import World

    w = World(session)
    w.anchor(date(2016, 3, 31), ["A", "OLD"], form="N-30D")
    w.anchor(date(2016, 9, 30), ["A", "NEW"], form="N-30D")
    w.anchor(date(2017, 3, 31), ["A", "NEW"], form="N-30D")
    if paired:
        w.event("OFFICIAL_CONFIRMED", "NEW", "OLD", date(2016, 10, 3), date(2016, 10, 3))
    else:
        w.event("OFFICIAL_CONFIRMED", "NEW", None, date(2016, 10, 3), date(2016, 10, 3))
        w.event("OFFICIAL_CONFIRMED", None, "OLD", date(2016, 10, 3), date(2016, 10, 3))
    r = reconstruct(session, date(2016, 10, 1), date(2017, 3, 31))
    assert r.ready == (6 if paired else 0)
    if paired:
        assert w.security("OLD") not in r.cohorts[0].members


@pytest.mark.pit
@pytest.mark.parametrize("valid_cik", [True, False])
def test_sec_primary_is_declared_not_first_exhibit(
    session: Session, tmp_path, valid_cik: bool
) -> None:
    import json

    from pitquant.data.archive import ArchiveStore
    from pitquant.data.providers.sec_edgar.client import SECClient
    from pitquant.universe.identity_events import fetch_8k
    from tests.unit.test_spy_anchor_parsers import FakeSec, header

    accession = "0000884394-16-000001"
    cik = 884394
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    complete = (
        header("8-K", accession, "2016-04-01", cik=str(cik if valid_cik else 111111))
        + "\n<DOCUMENT>\n<TYPE>8-K\n<SEQUENCE>1\n<FILENAME>primary.htm\n<TEXT>primary</TEXT>\n</DOCUMENT>"
    ).encode()
    client = SECClient(
        FakeSec(
            {
                base + "index.json": json.dumps(
                    {"directory": {"item": [{"name": "exhibit.htm"}, {"name": "primary.htm"}]}}
                ).encode(),
                base + accession + ".txt": complete,
                base + "primary.htm": b"<html>Verified principal &amp; transaction</html>",
            }
        ),
        "Synthetic research test test@example.invalid",
    )
    if valid_cik:
        result = fetch_8k(session, client, ArchiveStore(tmp_path), cik, accession)
        assert result.form == "8-K"
        assert "Verified principal & transaction" in result.text
    else:
        with pytest.raises(ValueError, match="CIK"):
            fetch_8k(session, client, ArchiveStore(tmp_path), cik, accession)


@pytest.mark.pit
def test_company_exact_name_does_not_hide_explicit_classes() -> None:
    from pitquant.universe.sp500_anchor_graph import Resolver

    resolver = object.__new__(Resolver)
    resolver.name_idx = {
        "cablevision systems": {"generic"},
        "cablevision systems class a": {"A"},
        "cablevision systems class b": {"B"},
    }
    assert resolver._by_containment("Cablevision Systems") == {"generic", "A", "B"}
    assert resolver._by_containment("Cablevision Systems Class A") == {"A"}


@pytest.mark.pit
def test_explicit_cablevision_13f_class_stays_separate(session: Session) -> None:
    from pitquant.universe.identity_bridge import candidates_for

    fw = F13World(session)
    fw.e13("2016Q1", "12686C109", "CABLEVISION SYS CORP CL A NY CABLVS", "")
    assert len(candidates_for(session, "Cablevision Systems Corp. Class A", "2016Q1")) == 1
    assert candidates_for(session, "Cablevision Systems Corp. Class B", "2016Q1") == []
    assert candidates_for(session, "Cablevision Systems Corp.", "2016Q1") == []


@pytest.mark.pit
@pytest.mark.parametrize(
    "raw,name",
    [
        ("DU PONT E I DE NEMOURS & CO", "E. I. du Pont de Nemours & Co."),
        ("HARMAN INTL INDS INC", "Harman International Industries, Inc."),
        ("DUN & BRADSTREET CORP DEL NE", "Dun & Bradstreet Corp."),
        ("ST JUDE MED INC", "St. Jude Medical, Inc."),
        ("TRANSOCEAN LTD REG", "Transocean, Ltd."),
        ("WHOLE FOODS MKT INC", "Whole Foods Market, Inc."),
        ("OWENS ILL INC", "Owens-Illinois, Inc."),
        ("RYDER SYS INC", "Ryder System, Inc."),
        ("MALLINCKRODT PUB LTD CO", "Mallinckrodt PLC"),
    ],
)
def test_critical_legal_formats_require_exact_name_and_preserve_class(
    session: Session, raw: str, name: str
) -> None:
    from pitquant.universe.identity_bridge import candidates_for

    fw = F13World(session)
    fw.e13("2016Q3", "123456789", raw, "COM")
    assert len(candidates_for(session, name, "2016Q3")) == 1
    assert candidates_for(session, name + " Different", "2016Q3") == []
    fw.e13("2016Q3", "987654321", raw, "CL C")
    assert len(candidates_for(session, name, "2016Q3")) == 1
