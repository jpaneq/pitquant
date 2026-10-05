# ruff: noqa: E501
"""Archive official instrument evidence for the four unresolved research links.

No issuer is substituted for a security, no links are invented and no features or
models are written. SEC contact comes exclusively from the runtime environment.
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport
from pitquant.db.session import make_engine, make_session_factory

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "XOM": ["https://www.sec.gov/Archives/edgar/data/34088/000119312526291986/d70995d8k.htm"],
    "RTX": [
        "https://www.sec.gov/Archives/edgar/data/101829/000114036120008397/nc10010681x2_8k.htm",
        "https://www.sec.gov/Archives/edgar/data/1047122/000119312520097237/d827106d8k.htm",
    ],
    "GOOGL": [
        "https://www.sec.gov/Archives/edgar/data/1652044/000119312517040409/d347399dsc13ga.htm",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2015-156",
    ],
    "GE": ["https://www.sec.gov/Archives/edgar/data/40545/000120677421001925/ge3936671-ex911.htm"],
}
FINDINGS = {
    "XOM": {
        "status": "PARTIAL",
        "event": "SECURITY_REPLACEMENT_SUCCESSOR",
        "effective_on": "2026-07-01",
        "reason": "Old Exxon Mobil CIK 34088 and new ExxonMobil Holdings CIK 2115436 are different legal issuers/securities, 1:1. The current SEC profile cannot certify the old research security. Post-DEV evidence is identity audit only, never a feature or membership input.",
        "minimum_action": "Create dated predecessor/successor security intervals and bind vendor history to the old instrument; verify old CUSIP 30231G102 independently.",
    },
    "RTX": {
        "status": "PARTIAL",
        "event": "UTX_NAME_CHANGE_AND_RTN_MERGER",
        "effective_on": "2020-04-03",
        "reason": "UTX issuer CIK 101829 continues as RTX; RTN CIK 1047122 is a different instrument exchanged at 2.3348. The exchange ratio must never be applied to UTX. Carrier/Otis spin-offs require a separate return reconciliation.",
        "minimum_action": "Bind UTX/RTX common-share lineage by dated identifiers, keep RTN separate and QA returns crossing the spin-offs.",
    },
    "GOOGL": {
        "status": "PARTIAL",
        "event": "GOOGLE_ALPHABET_CLASS_PRESERVING_REPLACEMENT",
        "effective_on": "2015-10-05",
        "verified_cusip": "02079K305",
        "class": "A",
        "distinct_other_cusip": "02079K107",
        "reason": "SEC proves Alphabet Class A 02079K305; Nasdaq proves GOOGL Class A and GOOG Class C are distinct 1:1 replacements. This closes the identifier fact, not the dated research-price instrument assignment across the 2014 class distribution and 2015 replacement.",
        "minimum_action": "Introduce dated class-A instrument bindings for the research series; keep Google predecessor and Alphabet successor distinct, with official corporate-action evidence.",
    },
    "GE": {
        "status": "PARTIAL",
        "event": "REVERSE_SPLIT_IDENTIFIER_CHANGE_SAME_COMMON_CLASS",
        "effective_on": "2021-08-02",
        "verified_cusip": "369604301",
        "previous_cusip": "369604103",
        "reason": "Issuer exhibit proves 1-for-8 reverse split and new common-stock CUSIP. Same issuer alone does not join the two anchor securities. Later healthcare/Vernova spin-offs must not relabel pre-event history as the current business.",
        "minimum_action": "Formalize the dated common-share identifier event using existing old-CUSIP anchor evidence and the July 2021 exhibit, preserve reverse-split units and reconcile vendor adjusted returns separately.",
    },
}


def main() -> None:
    cfg = get_settings()
    client = SECClient(UrllibTransport(), os.environ["PITQUANT_SEC_USER_AGENT"])
    result = {}
    with make_session_factory(make_engine(cfg.database.url))() as session:
        for ticker, urls in SOURCES.items():
            evidence = []
            for url in urls:
                response = client.get(url)
                row = archive_document(
                    session,
                    ArchiveStore(ROOT / cfg.archive.root),
                    provider="FIRST_ML_IDENTITY_AUDIT",
                    source_identifier=url,
                    data=response.body,
                    mime_type=response.content_type,
                    parser_version="first-ml-identity-audit-1",
                    notes=f"{ticker}: reference identity audit only; no eligibility promotion",
                )
                text = re.sub(
                    r"\s+",
                    " ",
                    html.unescape(
                        re.sub(r"<[^>]+>", " ", response.body.decode("utf-8", "replace"))
                    ),
                )
                if (
                    ticker == "GOOGL"
                    and "sec.gov" in url
                    and not re.search(r"Class A Common Stock:\s*02079K\s*305", text)
                ):
                    raise ValueError("GOOGL_CLASS_A_CUSIP_NOT_VERIFIED")
                if ticker == "GE" and not ("369604301" in text and "1-for-8" in text):
                    raise ValueError("GE_SPLIT_CUSIP_NOT_VERIFIED")
                evidence.append(
                    {
                        "url": url,
                        "archive_id": row.archive_id,
                        "sha256": row.sha256,
                        "retrieved_at": str(row.retrieved_at),
                        "parser_version": row.parser_version,
                    }
                )
            result[ticker] = {**FINDINGS[ticker], "sources": evidence, "eligible_promoted": False}
        session.commit()
    (ROOT / "docs/FIRST_ML_SECURITY_IDENTITY.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
