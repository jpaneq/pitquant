"""Ingest the reviewed, allowlisted primary D-02 sources. Default is offline replay.

Use --fetch to retrieve originals; --apply to apply verified corporate facts. Never crawls.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.models import RawSourceArchive  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.d02_documentary import (  # noqa: E402
    VERSION,
    apply_documentary_events,
    source_specs,
)
from pitquant.universe.sp500_anchor_graph import pre_holdout_limit  # noqa: E402

SP_SOURCES = (
    (
        "https://press.spglobal.com/2020-05-06-DexCom-Dominos-Pizza-Set-to-Join-S-P-500-Salesforce-com-to-Join-S-P-100-STORE-Capital-to-Join-S-P-MidCap-400-Capri-Holdings-to-Join-S-P-SmallCap-600",
        date(2020, 5, 6),
    ),
    (
        "https://press.spglobal.com/2022-04-07-S-P-Dow-Jones-Indices-Announces-Treatment-of-AT-T-Transaction-with-Discovery",
        date(2022, 4, 7),
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    cfg = get_settings()
    store = ArchiveStore(ROOT / cfg.archive.root)
    manifest = []
    with make_session_factory(make_engine(cfg.database.url))() as session:
        sources = source_specs()
        sources += [
            (url, published, "SP_PRESS:press.spglobal.com", "text/html")
            for url, published in SP_SOURCES
        ]
        sources = list(
            {
                (url, provider): (url, published, provider, mime)
                for url, published, provider, mime in sources
            }.values()
        )
        for url, published, provider, mime in sources:
            row = session.scalars(
                select(RawSourceArchive).where(
                    RawSourceArchive.source_identifier == url,
                    RawSourceArchive.provider == provider,
                )
            ).first()
            if row is None and args.fetch:
                try:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "Mozilla/5.0 PITQuant documentary research"}
                    )
                    with urllib.request.urlopen(req, timeout=20) as response:
                        body = response.read()
                    # Publication clock is not asserted; conservative end of local publication day.
                    available = datetime.combine(
                        published, datetime.max.time(), ZoneInfo("America/New_York")
                    ).astimezone(UTC)
                    row = archive_document(
                        session,
                        store,
                        provider=provider,
                        source_identifier=url,
                        data=body,
                        mime_type=mime,
                        published_at=available,
                        parser_version=VERSION,
                        notes=(
                            "Reviewed primary original; publication clock unknown; "
                            "conservative end of publication day"
                        ),
                    )
                except Exception as exc:
                    manifest.append({"url": url, "status": "FETCH_FAILED", "reason": str(exc)})
                    continue
            if row is None:
                manifest.append({"url": url, "status": "NOT_ARCHIVED"})
                continue
            store.get(row.sha256)
            manifest.append(
                {
                    "url": url,
                    "status": "ARCHIVED",
                    "archive_id": row.archive_id,
                    "sha256": row.sha256,
                    "published_on": str(published),
                    "provider": provider,
                }
            )
        results = (
            apply_documentary_events(session, store, limit=pre_holdout_limit(cfg))
            if args.apply
            else []
        )
        session.commit()
    report = {"version": VERSION, "sources": manifest, "events": [asdict(r) for r in results]}
    (ROOT / "docs/d02_documentary_ingestion.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 1 if args.apply and any(not r.applied for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
