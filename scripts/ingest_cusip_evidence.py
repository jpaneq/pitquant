# ruff: noqa: E501
"""Official CUSIP evidence for SEC-registered securities from archived SEC Schedule 13G filings
(ADR-0024).

    PITQUANT_SEC_USER_AGENT="<name> <email>" PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db \
        python scripts/ingest_cusip_evidence.py

One filing per calendar year (2011..now) per issuer is archived (URL, retrieved_at, SHA-256) and
recorded ONLY if its text names the issuer, «Common Stock» and the CUSIP in the same cover page.
The User-Agent is read from the environment and never stored.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.timeutils import utc_now  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.providers.official_identity import extract_text  # noqa: E402
from pitquant.db.models import Security, SecurityIdentifierEvidence  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

PARSER = "sec-13g-cusip-1"
TARGETS = {  # cik -> (cusip, issuer regex)
    "0000320193": ("037833100", r"apple\s+inc"),
    "0000789019": ("594918104", r"microsoft\s+corp"),
}
FORMS = "SC 13G,SC 13G/A,SCHEDULE 13G,SCHEDULE 13G/A"


def get(url: str, ua: str) -> bytes:
    time.sleep(0.25)
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": ua}), timeout=120
    ) as r:
        body: bytes = r.read()
    return body


def main() -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT")
    if not ua:
        print("SOURCE_NOT_CONFIGURED: export PITQUANT_SEC_USER_AGENT")
        return 2
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    added = 0
    with make_session_factory(make_engine(s.database.url))() as ses:
        for cik, (cusip, name_rx) in TARGETS.items():
            sid = ses.scalars(
                select(Security.security_id).where(Security.name.like(f"CIK {cik}%"))
            ).one()
            for year in range(2011, utc_now().year + 1):
                q = urllib.parse.urlencode(
                    {"q": f'"{cusip}"', "forms": FORMS, "dateRange": "custom",
                     "startdt": f"{year}-01-01", "enddt": f"{year}-12-31"}
                )  # fmt: skip
                hits = json.loads(get(f"https://efts.sec.gov/LATEST/search-index?{q}", ua))["hits"][
                    "hits"
                ]
                done = False
                for h in hits:
                    if done or cik not in h["_source"].get("ciks", []):
                        continue
                    acc, fname = h["_id"].split(":")
                    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{fname}"
                    body = get(url, ua)
                    text, _ = extract_text(body)
                    m = re.search(rf"cusip[^0-9]{{0,40}}{cusip}", text, re.I)
                    if not (
                        m
                        and re.search(name_rx, text, re.I)
                        and re.search(r"common\s+stock", text, re.I)
                    ):
                        continue
                    row = archive_document(
                        ses, store, provider="SEC_SCHEDULE_13G", source_identifier=url, data=body,
                        mime_type="text/html" if body[:5] != b"%PDF-" else "application/pdf",
                        parser_version=PARSER, notes=f"accession={acc}; form={h['_source']['form']}",
                    )  # fmt: skip
                    filed = date.fromisoformat(h["_source"]["file_date"])
                    if (
                        ses.scalars(
                            select(SecurityIdentifierEvidence.evidence_id).where(
                                SecurityIdentifierEvidence.security_id == sid,
                                SecurityIdentifierEvidence.value == cusip,
                                SecurityIdentifierEvidence.source_url == url,
                            )
                        ).first()
                        is None
                    ):
                        ses.add(SecurityIdentifierEvidence(
                            security_id=sid, id_type="CUSIP", value=cusip, kind="OFFICIAL",
                            observed_on=filed, source_kind="SEC_SCHEDULE_13G", source_url=url,
                            archive_id=row.archive_id, source_sha256=row.sha256,
                            excerpt=text[max(0, m.start() - 80): m.end() + 40][:600], parser_version=PARSER))  # fmt: skip
                        added += 1
                    print(f"{cik} {year}: {filed} {acc} sha={row.sha256[:12]}", flush=True)
                    done = True
                if not done:
                    print(f"{cik} {year}: no verified 13G")
        ses.commit()
    print(f"added {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
