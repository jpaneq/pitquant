"""Read-only, hash-verified manifest of critical-path issuer and identifier evidence."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from apply_d02_critical_identity import EVENTS
from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, Security, SecuritySuccession
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.identity_bridge import _entry


def main() -> None:
    cfg = get_settings()
    store = ArchiveStore(Path(cfg.archive.root))
    with make_session_factory(make_engine(cfg.database.url))() as s:
        out = json.loads(Path("docs/D02_CRITICAL_IDENTITY_RESOLUTIONS.json").read_text())
        out["events"] = [asdict(ev) for ev in EVENTS]
        out["provenance"] = []
        for ev in EVENTS:
            src = []
            rows = s.scalars(
                select(RawSourceArchive)
                .where(RawSourceArchive.source_identifier.contains(ev.accession.replace("-", "")))
                .order_by(RawSourceArchive.retrieved_at)
            ).all()
            seen = set()
            for a in rows:
                if (a.source_identifier, a.sha256) in seen:
                    continue
                seen.add((a.source_identifier, a.sha256))
                assert hashlib.sha256(store.get(a.sha256)).hexdigest() == a.sha256
                src.append(
                    dict(
                        url=a.source_identifier,
                        archive_id=a.archive_id,
                        sha256=a.sha256,
                        retrieved_at=str(a.retrieved_at),
                        published_at=str(a.published_at),
                        provider=a.provider,
                        bytes=a.size_bytes,
                    )
                )
            lists = []
            for q, c in ev.verify:
                e = _entry(s, q, c)
                a = s.get(RawSourceArchive, e.archive_id)
                lists.append(
                    dict(
                        quarter=q,
                        cusip=c,
                        issuer_text=e.issuer_name,
                        class_text=e.issuer_description,
                        url=a.source_identifier,
                        archive_id=a.archive_id,
                        sha256=e.raw_source_hash,
                        retrieved_at=str(a.retrieved_at),
                    )
                )
            links = s.scalars(
                select(SecuritySuccession).where(
                    SecuritySuccession.source.contains(ev.accession),
                    SecuritySuccession.event_type == ev.event_type,
                )
            ).all()
            out["provenance"].append(
                dict(
                    key=ev.key,
                    document_form=ev.form,
                    accession=ev.accession,
                    filer_cik=ev.cik,
                    primary_proofs=src,
                    official_13f=lists,
                    links=[
                        dict(
                            predecessor_id=link.security_predecessor_id,
                            successor_id=link.security_successor_id,
                            ratio=link.exchange_ratio,
                            effective_at=str(link.effective_at),
                            source_hash=link.source_hash,
                            issuer_before={
                                "issuer_id": s.get_one(
                                    Security, link.security_predecessor_id
                                ).issuer_id,
                                "anchor_security_name": s.get_one(
                                    Security, link.security_predecessor_id
                                ).name,
                            },
                            issuer_after={
                                "issuer_id": s.get_one(
                                    Security, link.security_successor_id
                                ).issuer_id,
                                "anchor_security_name": s.get_one(
                                    Security, link.security_successor_id
                                ).name,
                            },
                        )
                        for link in links
                    ],
                    precision=(
                        "SOURCE_LOCAL_TIME_TIMEZONE_UNSPECIFIED; "
                        "stored timestamp is monthly boundary only"
                    )
                    if ev.key in ("L3_HOLDING_SUCCESSOR", "ALCOA_ARCONIC_NAME")
                    else "See event note; date-only is not an exact UTC instant",
                    review_note=ev.note,
                    confidence="HIGH_CLASS_PRESERVING_DOCUMENT_REVIEW",
                )
            )
        Path("docs/D02_CRITICAL_IDENTITY_RESOLUTIONS.json").write_text(
            json.dumps(out, indent=2, default=str) + "\n"
        )


if __name__ == "__main__":
    main()
