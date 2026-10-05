# ruff: noqa: E501

"""Reviewed critical-path transitions; no research-series remapping or training.

SEC submission header and declared primary document + exact transaction phrases +
quarterly official CUSIPs are required. Index additions/removals remain S&P evidence.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.identity_events import Alias, CorporateEvent, apply_events

VERSION = "d02-critical-identity-1"
EVENTS = (
    CorporateEvent(
        "DOMINION_RESOURCES_ENERGY",
        "NAME_CHANGE_SAME_SECURITY",
        "0000715957-17-000019",
        715957,
        (
            "to change the name of the Company from Dominion Resources, Inc. to Dominion Energy, Inc.",
            "On May 10, 2017, the Company's shareholders approved the Name Change",
        ),
        datetime(2017, 5, 10, tzinfo=UTC),
        "Dominion Resources, Inc.",
        "25746U109",
        "25746U109",
        None,
        (("2017Q1", "25746U109"), ("2017Q3", "25746U109")),
        None,
        (Alias("D", None, date(2017, 5, 9)),),
        (Alias("D", date(2017, 5, 10), None),),
        "Legal name change on 2017-05-10, date precision only; same common CUSIP in both official lists; no new security or index exit/entry.",
    ),
    CorporateEvent(
        "TESORO_ANDEAVOR",
        "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY",
        "0000050104-17-000180",
        50104,
        (
            "Effective August 1, 2017, we amended our Restated Certificate of Incorporation",
            "to change our name from “Tesoro Corporation” to “Andeavor”",
        ),
        datetime(2017, 8, 1, tzinfo=UTC),
        "Tesoro Corp.",
        "881609101",
        "03349M105",
        None,
        (("2017Q1", "881609101"), ("2017Q3", "03349M105")),
        None,
        (Alias("TSO", None, date(2017, 7, 31)),),
        (Alias("ANDV", date(2017, 8, 1), None),),
        "Legal name change 2017-08-01. CUSIP transition is quarterly PARTIAL unless separately corroborated by exchange notice; same security.",
    ),
    CorporateEvent(
        "CSC_DXC",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0001193125-17-112036",
        1688568,
        (
            "Effective as of 3:01 a.m. Eastern time on April 1, 2017",
            "CSC stockholders received one share of DXC Common Stock for every one share of CSC common stock",
        ),
        datetime(2017, 4, 1, 7, 1, tzinfo=UTC),
        "Computer Sciences Corp.",
        "205363104",
        "23355L106",
        None,
        (("2017Q1", "205363104"), ("2017Q3", "23355L106")),
        1.0,
        (Alias("CSC", None, date(2017, 3, 31)),),
        (Alias("DXC", date(2017, 4, 3), None),),
        "CSC shares replaced 1:1 by new issuer DXC at 2017-04-01 03:01 ET; regular-way trading April 3; S&P slot addition April 4 is independently sourced.",
    ),
    CorporateEvent(
        "DOW_DOWDUPONT",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0001193125-17-274834",
        1666700,
        (
            "Effective August 31, 2017, DowDuPont Inc.",
            "was converted into the right to receive one fully paid and non-assessable share",
            "This Current Report on Form 8-K establishes the Company as the successor issuer to Dow and DuPont",
        ),
        datetime(2017, 9, 1, 13, 30, tzinfo=UTC),
        "The Dow Chemical Co.",
        "260543103",
        "26078J100",
        None,
        (("2017Q1", "260543103"), ("2017Q3", "26078J100")),
        1.0,
        (Alias("DOW", None, date(2017, 8, 31)),),
        (Alias("DWDP", date(2017, 9, 1), None),),
        "MERGER closes 2017-08-31; index-effective successor first session 2017-09-01. Dow->new issuer 1:1; DuPont common 1.282 is separate and its index removal is not a continuity link.",
        form="8-K12B",
    ),
)

EVENTS += (
    CorporateEvent(
        "GENERAL_GROWTH_GGP",
        "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY",
        "0001496048-17-000018",
        1496048,
        (
            "effective January 27, 2017",
            "changed its name from General Growth Properties, Inc. to GGP Inc.",
        ),
        datetime(2017, 1, 27, tzinfo=UTC),
        "General Growth Properties, Inc.",
        "370023103",
        "36174X101",
        None,
        (("2016Q3", "370023103"), ("2017Q1", "36174X101")),
        None,
        (Alias("GGP", None, date(2017, 1, 26)),),
        (Alias("GGP", date(2017, 1, 27), None),),
        "Name change completed 2017-01-27 (2016 annual 10-K filed 2017-02-22); January 18 8-K announced it. Preferred CUSIP 36174X200 is not common 36174X101.",
        form="10-K",
    ),
    CorporateEvent(
        "L3_HOLDING_SUCCESSOR",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0001567619-17-000002",
        1039101,
        (
            "Effective as of December 31, 2016 at 11:58 p.m.",
            "was converted into one share of common stock, par value $0.01 per share, of the Company",
            "Outstanding shares of the Company’s common stock have been issued CUSIP number 502413107",
        ),
        datetime(2017, 1, 1, 4, 58, tzinfo=UTC),
        "L-3 Communications Holdings, Inc.",
        "502424104",
        "502413107",
        None,
        (("2016Q3", "502424104"), ("2017Q1", "502413107")),
        1.0,
        (Alias("LLL", None, date(2016, 12, 31)),),
        (Alias("LLL", date(2017, 1, 1), None),),
        "MERGER 2016-12-31 23:58, source timezone unspecified; effective_at is a monthly reconstruction boundary, not a verified UTC instant. Holding predecessor into operating company 1:1; legal rename one minute later. Separate issuer/security.",
        "EXACT",
        form="8-K12B",
    ),
    CorporateEvent(
        "FMC_TECHNIPFMC",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0001193125-17-010427",
        1135152,
        (
            "On January 16, 2017",
            "was automatically exchanged for one TechnipFMC Ordinary Share",
            "suspended from trading on the NYSE and Euronext Paris, respectively, prior to the open of trading on January 17, 2017",
        ),
        datetime(2017, 1, 17, 14, 30, tzinfo=UTC),
        "FMC Technologies, Inc.*",
        "30249U101",
        "G87110105",
        "GB00BDSFG982",
        (("2016Q3", "30249U101"), ("2017Q1", "G87110105")),
        1.0,
        (Alias("FTI", None, date(2017, 1, 13)),),
        (Alias("FTI", date(2017, 1, 17), None),),
        "MERGER completed January 16, 2017 (NYSE holiday); FMC 1:1 into UK successor. First regular session January 17; Technip 2:1 is a separate instrument.",
    ),
    CorporateEvent(
        "ALCOA_ARCONIC_NAME",
        "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY",
        "0001193125-16-755445",
        4281,
        (
            "change the name of the Company to Arconic Inc.",
            "it became effective as of 11:59 p.m. on October 31, 2016",
        ),
        datetime(2016, 11, 1, 3, 59, tzinfo=UTC),
        "Alcoa, Inc.",
        "013817101",
        "03965L100",
        None,
        (("2016Q3", "013817101"), ("2017Q1", "03965L100")),
        None,
        (Alias("AA", None, date(2016, 10, 31)),),
        (Alias("ARNC", date(2016, 11, 1), None),),
        "Legal rename 2016-10-31 23:59, source timezone unspecified; effective_at is a monthly reconstruction boundary, not a verified UTC instant. Trading ARNC November 1; preceding reverse split and Alcoa Corporation spin-off are separate.",
    ),
)


def main() -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        raise SystemExit("PITQUANT_SEC_USER_AGENT with contact required")
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as session:
        results = apply_events(
            session,
            SECClient(UrllibTransport(timeout_s=60), ua),
            ArchiveStore(Path(cfg.archive.root)),
            EVENTS,
        )
        session.commit()
    out = {
        "resolver_version": VERSION,
        "events": [asdict(x) for x in EVENTS],
        "results": [asdict(x) for x in results],
    }
    Path("docs/D02_CRITICAL_IDENTITY_RESOLUTIONS.json").write_text(
        json.dumps(out, indent=2, default=str) + "\n"
    )
    print(json.dumps(out["results"], indent=2))
    return 0 if all(x.applied for x in results) else 1


EVENTS += (
    CorporateEvent(
        "DAVITA_NAME",
        "NAME_CHANGE_SAME_SECURITY",
        "0001193125-16-702143",
        927066,
        (
            "Effective September 1, 2016",
            "changed its name to DaVita Inc.",
            "CUSIP number will remain the same",
        ),
        datetime(2016, 9, 1, tzinfo=UTC),
        "DaVita HealthCare Partners,Inc.",
        "23918K108",
        "23918K108",
        None,
        (("2016Q1", "23918K108"), ("2016Q3", "23918K108")),
        None,
        (Alias("DVA", None, date(2016, 8, 31)),),
        (Alias("DVA", date(2016, 9, 1), None),),
        "Legal name change effective 2016-09-01; unchanged common CUSIP and ticker, not an exit/entry.",
    ),
    CorporateEvent(
        "MCGRAW_SP_GLOBAL",
        "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY",
        "0000064040-16-000062",
        64040,
        (
            "to change the name of the Company to “S&P Global Inc.” from “McGraw Hill Financial, Inc.”",
            "on April 27, 2016",
        ),
        datetime(2016, 4, 27, tzinfo=UTC),
        "McGraw Hill Financial, Inc.",
        "580645109",
        "78409V104",
        None,
        (("2016Q1", "580645109"), ("2016Q3", "78409V104")),
        None,
        (Alias("MHFI", None, date(2016, 4, 27)),),
        (Alias("SPGI", date(2016, 4, 28), None),),
        "Legal name approved/filed April 27; trading symbol April 28 corroborated by issuer release. CUSIP precise transition remains PARTIAL.",
    ),
)


EVENTS += (
    CorporateEvent(
        "XL_REDOMICILIATION",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0000875159-16-000163",
        875159,
        (
            "At 12:30 p.m., Irish time, on July 25, 2016",
            "on a one-for-one basis",
            "the CUSIP number for the XL-Bermuda common shares issued in place of the XL-Ireland ordinary shares will be G98294 104",
        ),
        datetime(2016, 7, 25, 11, 30, tzinfo=UTC),
        "XL Group PLC Class A",
        "G98290102",
        "G98294104",
        None,
        (("2016Q1", "G98290102"), ("2016Q3", "G98294104")),
        1.0,
        (Alias("XL", None, date(2016, 7, 22)),),
        (Alias("XL", date(2016, 7, 25), None),),
        "REDOMICILIATION: Irish predecessor shares cancelled; new Bermuda issuer common issued 1:1, July 25 at 12:30 Irish time (11:30 UTC). Same ticker is not proof of same security. CUSIP effective explicitly stated.",
        "EXACT",
        form="8-K12B",
    ),
    CorporateEvent(
        "TYCO_JCI_CONSOLIDATION_NAME",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0001104659-16-143068",
        833444,
        (
            "at 11:59 p.m. New York time on September 2, 2016",
            "Tyco changed its name to “Johnson Controls International plc”",
            "by virtue of a 0.955-for-one share consolidation",
            "A new CUSIP number of G51502 105 and a new ISIN number of IE00BY7QL619",
        ),
        datetime(2016, 9, 3, 3, 59, tzinfo=UTC),
        "Tyco International, Ltd.",
        "G91442106",
        "G51502105",
        "IE00BY7QL619",
        (("2016Q1", "G91442106"), ("2016Q3", "G51502105")),
        0.955,
        (Alias("TYC", None, date(2016, 9, 2)),),
        (Alias("JCI", date(2016, 9, 6), None),),
        "SHARE_CONSOLIDATION 0.955:1 of existing Tyco legal issuer plus rename, distinct instrument/CUSIP. Completed merger September 2 at 23:59 New York time; JCI trading September 6. Old Johnson Controls shares' cash/election consideration is separate; no continuity link from that issuer.",
    ),
)

if __name__ == "__main__":
    raise SystemExit(main())
