"""Bounded fundamental-only append-only repair; never builds targets or prices."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pitquant.data.archive import ArchiveStore, archive_document, sha256_hex
from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.fundamental_recovery import TAG_VERSION, rebuild

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    with make_session_factory(make_engine(os.environ["PITQUANT_DATABASE_URL"]))() as session:
        path = ROOT / "src/pitquant/research/fundamental_recovery.py"
        raw = path.read_bytes()
        code = archive_document(
            session,
            ArchiveStore(ROOT / "data/archive"),
            provider="FIRST_ML_FUNDAMENTAL_RECOVERY_SOURCE",
            source_identifier=TAG_VERSION + ":" + sha256_hex(raw),
            data=raw,
            mime_type="text/plain",
            parser_version=TAG_VERSION,
        )
        report = rebuild(session)
        report["source_archive"] = {"archive_id": code.archive_id, "sha256": code.sha256}
        session.commit()
    (ROOT / "docs/FIRST_ML_FUNDAMENTAL_RECOVERY.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "rows_added": report["rows_added"],
                "recovered_security_periods": len(report["recovered"]),
            }
        )
    )


if __name__ == "__main__":
    main()
