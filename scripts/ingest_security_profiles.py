# ruff: noqa: E501
"""Current display profile (name, ticker, exchange, SIC) for SEC-registered securities (ADR-0029).

    PITQUANT_SEC_USER_AGENT="<name> <email>" PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db \
        python scripts/ingest_security_profiles.py [CIK ...]

Source: SEC ``submissions`` JSON (official). Archived (URL, SHA-256) before use. The User-Agent is read
from the environment and never stored. Sector = SIC division, industry = SIC description (the SEC does
not publish GICS): the Analyzer says so. Idempotent per (security, source hash).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.models import Security, SecurityProfile  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.jobs.sec_universe import division, profile_type  # noqa: E402


def main(argv: list[str]) -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT")
    if not ua:
        print("SOURCE_NOT_CONFIGURED: export PITQUANT_SEC_USER_AGENT")
        return 2
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    with make_session_factory(make_engine(s.database.url))() as ses:
        secs = ses.scalars(select(Security).where(Security.name.like("CIK %(SEC EDGAR)"))).all()
        for sec in secs:
            cik = sec.name.split()[1]
            if argv and cik not in argv:
                continue
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": ua}), timeout=60
            ) as r:
                body: bytes = r.read()
            time.sleep(0.3)
            row = archive_document(
                ses,
                store,
                provider="SEC_SUBMISSIONS",
                source_identifier=url,
                data=body,
                mime_type="application/json",
                parser_version="profile-1",
                notes="company profile",
            )
            j = json.loads(body)
            tick = (j.get("tickers") or [None])[0]
            if ses.scalars(
                select(SecurityProfile.profile_id).where(
                    SecurityProfile.security_id == sec.security_id,
                    SecurityProfile.source_sha256 == row.sha256,
                )
            ).first():
                continue
            sic = str(j.get("sic") or "") or None
            ses.add(
                SecurityProfile(
                    security_id=sec.security_id,
                    current_ticker=tick.upper() if tick else None,
                    display_name=j["name"],
                    exchange=(j.get("exchanges") or [None])[0],
                    country="US",
                    sic=sic,
                    sic_description=j.get("sicDescription"),
                    sector=division(sic),
                    industry=j.get("sicDescription"),
                    profile_type=profile_type(sic),
                    source="SEC_SUBMISSIONS",
                    source_url=url,
                    archive_id=row.archive_id,
                    source_sha256=row.sha256,
                )
            )
            print(
                f"{cik}: {j['name']} ({tick}) SIC {sic} {j.get('sicDescription')} -> {profile_type(sic)}"
            )
        ses.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
