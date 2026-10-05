# ruff: noqa: E501
"""Audit two BR extraction defects in one original filing; exact class/quarter proof only."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import SP500Anchor, SP500AnchorMember
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.identity_bridge import add_cusip_evidence, candidates_for, link_same_security
from pitquant.universe.sources.spy_sec_anchors import parse_n30d_schedule

VERSION = "d02-document-breaks-1"
HASH = "997f53d43c213337fc103c27ea92e7653ab558dea8999835959429ab7222222a"
CASES = (
    (88, "CBRE Group, Inc. Class A<BR>REIT", "CBRE Group, Inc. Class A", "12504L109"),
    (
        286,
        "LyondellBasell Industries NV<BR>Class A",
        "LyondellBasell Industries NV Class A",
        "N53745100",
    ),
)


def main() -> None:
    cfg = get_settings()
    out = []
    with make_session_factory(make_engine(cfg.database.url))() as s:
        a = s.scalars(
            select(SP500Anchor).where(
                SP500Anchor.accession == "0001193125-16-777823", SP500Anchor.status == "VERIFIED"
            )
        ).one()
        raw = ArchiveStore(Path(cfg.archive.root)).get(a.source_sha256)
        assert a.source_sha256 == HASH == hashlib.sha256(raw).hexdigest()
        corrected = {h.position: h for h in parse_n30d_schedule(raw.replace(b"<BR>", b" "))}
        for pos, literal, name, cusip in CASES:
            assert literal.encode() in raw and corrected[pos].name == name
            old = s.scalars(
                select(SP500AnchorMember).where(
                    SP500AnchorMember.anchor_id == a.anchor_id,
                    SP500AnchorMember.source_position == pos,
                )
            ).one()
            target = s.scalars(
                select(SP500AnchorMember)
                .join(SP500Anchor)
                .where(
                    SP500Anchor.as_of_date == date(2017, 3, 31),
                    SP500AnchorMember.issuer_name == name,
                )
            ).one()
            assert old.security_id and target.security_id and old.security_id != target.security_id
            refs = []
            for owner, quarter in [(old.security_id, "2016Q3"), (target.security_id, "2017Q1")]:
                entries = candidates_for(s, name, quarter)
                assert len(entries) == 1 and entries[0].cusip == cusip
                e = entries[0]
                add_cusip_evidence(
                    s,
                    owner,
                    e,
                    f"{VERSION}; original {HASH} position {pos}: HTML BR restored, exact legal name + explicit Class A",
                )
                refs.append(
                    {
                        "quarter": quarter,
                        "cusip": e.cusip,
                        "hash": e.raw_source_hash,
                        "archive_id": e.archive_id,
                        "raw_name": e.issuer_name,
                        "raw_description": e.issuer_description,
                    }
                )
            link_same_security(
                s,
                old.security_id,
                target.security_id,
                f"{VERSION}:SEC_N30D+SEC_13F_LIST",
                HASH,
                note=f"Extraction artifact at position {pos}, no corporate event. Exact BR restore + official same CUSIP Class A in 2016Q3 and 2017Q1.",
            )
            out.append(
                {
                    "position": pos,
                    "source_document": a.accession,
                    "source_sha256": HASH,
                    "old_raw_name": old.issuer_name,
                    "corrected_name": name,
                    "security_before": old.security_id,
                    "security_after": target.security_id,
                    "decision_type": "DOCUMENT_EXTRACTION_SAME_INSTRUMENT",
                    "resolution_confidence": "HIGH",
                    "version": VERSION,
                    "official_observations": refs,
                }
            )
        s.commit()
    Path("docs/D02_CRITICAL_DOCUMENT_BREAKS.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
