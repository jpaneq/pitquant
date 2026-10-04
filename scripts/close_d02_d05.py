"""Auditable approved alias and Yahoo reconstruction. No models or outcomes selected."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.core.timeutils import utc_now
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models import (
    Issuer,
    IssuerIdentifier,
    Security,
    SecurityProfile,
    SP500Anchor,
    SP500AnchorMember,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.market.pipeline import record_ca_ingestion, store_batch
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
from pitquant.positions.universe_ingest import find_security
from pitquant.universe.document_aliases import PPG_ACCESSION, PPG_RAW, PPG_RESOLVED, VERSION
from pitquant.universe.identity_bridge import (
    bridge_name_only,
    link_same_security,
    security_by_cusip,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = get_settings()
    store = ArchiveStore(ROOT / cfg.archive.root)
    results = {}
    with make_session_factory(make_engine(cfg.database.url))() as s:
        anchor = s.scalars(select(SP500Anchor).where(SP500Anchor.accession == PPG_ACCESSION)).one()
        raw = store.get(anchor.source_sha256)
        member = s.scalars(
            select(SP500AnchorMember).where(
                SP500AnchorMember.anchor_id == anchor.anchor_id,
                SP500AnchorMember.issuer_name == PPG_RAW,
            )
        ).one()
        if b"PPoG" not in raw:
            raise ValueError("PPG_SOURCE_STRING_NOT_IN_ARCHIVE")
        bridge = bridge_name_only(s)
        assert any(b.name == PPG_RESOLVED for b in bridge)
        target_id = security_by_cusip(s, "693506107")
        if not target_id:
            raise ValueError("PPG_CANONICAL_CUSIP_AMBIGUOUS")
        target = s.get_one(Security, target_id)
        link_same_security(
            s,
            member.security_id,
            target_id,
            "DOCUMENT_SPECIFIC_TYPO_ALIAS",
            anchor.source_sha256,
            note="Exact approved N-30D alias; not a corporate succession",
        )
        audit = {
            "source_document": anchor.archive_id,
            "source_filing": PPG_ACCESSION,
            "source_date": str(anchor.as_of_date),
            "source_sha256": anchor.source_sha256,
            "raw_name": PPG_RAW,
            "resolved_name": PPG_RESOLVED,
            "raw_security_id": member.security_id,
            "resolved_security_id": target.security_id,
            "resolved_issuer_id": target.issuer_id,
            "resolution_type": "DOCUMENT_SPECIFIC_TYPO_ALIAS",
            "evidence": "Human-approved exact N-30D typo; canonical PPG identity: NPORT CUSIP",
            "resolution_version": VERSION,
        }
        archive_document(
            s,
            store,
            provider="DOCUMENT_SPECIFIC_TYPO_ALIAS",
            source_identifier=PPG_ACCESSION,
            data=json.dumps(audit, sort_keys=True).encode(),
            mime_type="application/json",
            parser_version=VERSION,
        )
        s.commit()
        results["ppg"] = audit
        provider = YahooChartMarketDataProvider()
        for ticker, symbol in [("AAPL", "AAPL"), ("MSFT", "MSFT"), ("ENG", "ENG.MC")]:
            sid = find_security(s, ticker)
            if not sid:
                raise ValueError(f"CANONICAL_SECURITY_MISSING:{ticker}")
            sec = s.get_one(Security, sid)
            if ticker in ("AAPL", "MSFT") and sec.issuer_id is None:
                profile = s.scalars(
                    select(SecurityProfile).where(SecurityProfile.security_id == sid)
                ).first()
                assert profile and profile.source == "SEC_SUBMISSIONS"
                doc = json.loads(store.get(profile.source_sha256))
                cik = str(doc["cik"]).zfill(10)
                issuer = s.scalars(
                    select(Issuer)
                    .join(IssuerIdentifier)
                    .where(IssuerIdentifier.id_type == "CIK", IssuerIdentifier.value == cik)
                ).first()
                if issuer is None:
                    issuer = Issuer(name=doc["name"], country="US")
                    s.add(issuer)
                    s.flush()
                    s.add(
                        IssuerIdentifier(
                            issuer_id=issuer.issuer_id,
                            id_type="CIK",
                            value=cik,
                            valid_from=profile.ingested_at.date(),
                            source=profile.source_url,
                        )
                    )
                sec.issuer_id = issuer.issuer_id
            body, url = provider.download(symbol, date(2011, 1, 1), utc_now().date())
            ar = archive_document(
                s,
                store,
                provider="YAHOO_CHART:eod",
                source_identifier=url,
                data=body,
                mime_type="application/json",
                parser_version="yahoo-market-data-v1",
            )
            batch = provider.normalize(ticker, symbol, body)
            batch.bars = [
                replace(b, provenance=replace(b.provenance, archive_id=ar.archive_id))
                for b in batch.bars
            ]
            batch.actions = [
                replace(a, provenance=replace(a.provenance, archive_id=ar.archive_id))
                for a in batch.actions
            ]
            rep = store_batch(
                s, batch, key_to_security={ticker: sid}, market="ES" if ticker == "ENG" else "US"
            )
            if rep.rejected:
                raise ValueError(rep.rejected)
            record_ca_ingestion(
                s,
                security_id=sid,
                provider="YAHOO_CHART",
                period_start=date(2011, 1, 1),
                period_end=utc_now().date(),
                completed=True,
                events_found=len(batch.actions),
                source_hash=ar.sha256,
                detail="yahoo-market-data-v1; canonical provider; raw archive preserved",
            )
            s.commit()
            results[ticker] = {
                "security_id": sid,
                "issuer_id": sec.issuer_id,
                "bars": len(batch.bars),
                "inserted": rep.bars_inserted,
                "corporate_actions": len(batch.actions),
                "archive_hash": ar.sha256,
            }
    (ROOT / "docs/D02_D05_RECONSTRUCTION.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
