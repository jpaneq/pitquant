"""Verify only the weak instruments blocking the recovered critical cohorts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, SP500Anchor, SP500AnchorMember
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.identity_bridge import add_cusip_evidence, candidates_for, quarter_of

NAMES = (
    "E. I. du Pont de Nemours & Co.",
    "Harman International Industries, Inc.",
    "Dun & Bradstreet Corp.",
    "St. Jude Medical, Inc.",
    "Transocean, Ltd.",
    "Whole Foods Market, Inc.",
    "Owens-Illinois, Inc.",
    "Ryder System, Inc.",
    "Mallinckrodt PLC",
    "Cablevision Systems Corp. (Class A)",
)


def main() -> None:
    cfg = get_settings()
    store = ArchiveStore(Path(cfg.archive.root))
    results = []
    with make_session_factory(make_engine(cfg.database.url))() as session:
        for name in NAMES:
            ids = set(
                session.scalars(
                    select(SP500AnchorMember.security_id).where(
                        SP500AnchorMember.issuer_name == name,
                        SP500AnchorMember.security_id.is_not(None),
                    )
                )
            )
            if len(ids) != 1:
                raise ValueError(f"Nonunique reviewed weak instrument: {name}")
            sid = next(iter(ids))
            observations = session.execute(
                select(
                    SP500AnchorMember.issuer_name,
                    SP500Anchor.as_of_date,
                )
                .join(SP500Anchor)
                .where(
                    SP500AnchorMember.security_id == sid,
                    SP500Anchor.form == "N-30D",
                )
            ).all()
            picks = []
            for original, observed in observations:
                entries = candidates_for(session, original, quarter_of(observed))
                if len(entries) != 1:
                    raise ValueError(f"Nonunique quarter/class observation: {original}/{observed}")
                picks.append((original, observed, entries[0]))
            if len({entry.cusip for _, _, entry in picks}) != 1:
                raise ValueError(f"CUSIP transition needs separate official event: {name}")
            refs = []
            for original, observed, entry in picks:
                archive = session.get_one(RawSourceArchive, entry.archive_id)
                if hashlib.sha256(store.get(archive.sha256)).hexdigest() != entry.raw_source_hash:
                    raise ValueError("SEC 13F archive integrity failure")
                add_cusip_evidence(
                    session,
                    sid,
                    entry,
                    "critical-weak-identity-1: exact class-preserving legal format, "
                    "same CUSIP verified at every N-30D observation quarter",
                )
                refs.append(
                    dict(
                        name_at_anchor=original,
                        anchor_date=str(observed),
                        quarter=entry.quarter,
                        cusip=entry.cusip,
                        original_issuer=entry.issuer_name,
                        original_class=entry.issuer_description,
                        archive_id=entry.archive_id,
                        hash=entry.raw_source_hash,
                        url=archive.source_identifier,
                    )
                )
            results.append(dict(name=name, security_id=sid, observations=refs))
        session.commit()
    Path("docs/D02_CRITICAL_WEAK_IDENTITY.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
