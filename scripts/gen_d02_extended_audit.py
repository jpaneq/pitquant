# ruff: noqa: E501
"""Read-only DEV anchor/provenance/gap audit. No prices, features or model fitting."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import (
    RawSourceArchive,
    SecurityIdentifierEvidence,
    SP500Anchor,
    SP500AnchorMember,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.sources.spy_sec_anchors import parse_n30d_schedule, parse_submission_header
from pitquant.universe.sp500_anchor_graph import ENGINE_VERSION, classify_gaps, reconstruct

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    cfg = get_settings()
    store = ArchiveStore(ROOT / cfg.archive.root)
    with make_session_factory(make_engine(cfg.database.url))() as session:
        rep = reconstruct(session, date(2011, 1, 1), date(2022, 9, 30))
        gaps = classify_gaps(rep)
        delta_index = {
            (f"{sg.a.as_of}→{sg.b.as_of}", d.name, d.difference_type): d
            for sg in rep.segments
            for d in sg.deltas
        }
        needs = {
            "PRIMARY_EVENT_MISSING": (
                "NO_VERIFIED_PRIMARY_EVENT_LINK",
                "Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.",
            ),
            "SECURITY_IDENTITY_ONLY": (
                "NO_CLASS_PRESERVING_IDENTITY_LINK",
                "Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient.",
            ),
            "MONTHLY_DATE_AMBIGUITY": (
                "PRIMARY_DATE_INSUFFICIENT",
                "Official completed event/effective-session evidence narrowing the candidate interval away from the listed monthly opens.",
            ),
            "PRIMARY_DELTA_UNEXPLAINED": (
                "ARCHIVED_PRIMARY_INCONSISTENT",
                "Audit the linked primary release and both anchor rows; resolve contradictory event legs, transient positions or legal predecessor/successor with official evidence.",
            ),
        }
        for g in gaps:
            delta = delta_index.get((g["segment"], g["security"], g["difference_type"]))
            if delta:
                g.update(
                    {
                        "security_id": delta.security_identifier,
                        "anchor_A_status": delta.anchor_A_status,
                        "anchor_B_status": delta.anchor_B_status,
                    }
                )
            if g["blocks_membership"]:
                availability, requirement = needs.get(
                    g["category"],
                    ("UNRESOLVED", "Official evidence of the dated event and instrument."),
                )
                g.update(
                    {
                        "evidence_availability": availability,
                        "document_required": requirement,
                        "source_role": "membership: S&P; identity: regulator/issuer/exchange",
                        "condition_to_close": "Document the event or class-preserving continuity within the candidate interval; replay forward/backward to equality at every listed decision_at; retain the original source and hash.",
                    }
                )
            g["gap_id"] = hashlib.sha256(
                json.dumps([g["segment"], g["security"], g["difference_type"]]).encode()
            ).hexdigest()[:20]
        blocked = []
        for c in rep.cohorts:
            if c.status == "MEMBERSHIP_READY":
                continue
            relevant = [g for g in gaps if str(c.date) in g["cohorts_blocked"]]
            nodes = []
            if c.segment:
                dates = c.segment.split("→")
                nodes = [n for n in rep.anchors if str(n.as_of) in dates]
            refs = []
            for n in nodes:
                a = session.get_one(SP500Anchor, n.anchor_id)
                refs.append(
                    {
                        "period": str(n.as_of),
                        "form": a.form,
                        "accession": a.accession,
                        "filer_cik": a.filer_cik,
                        "hash": a.source_sha256,
                        "unresolved_lines": n.unresolved_lines,
                    }
                )
            blocked.append(
                {
                    "month": c.date.strftime("%Y-%m"),
                    "decision_at": str(c.date),
                    "status": c.status,
                    "segment": c.segment,
                    "reasons": c.reasons,
                    "anchors": refs,
                    "gap_ids": sorted(g["gap_id"] for g in relevant),
                    "failure_kind": sorted({g["category"] for g in relevant}),
                    "minimum_action": "Archive official effective event dates or class-preserving identity transitions for each listed gap; replay forward/backward. Discovery dates do not close gaps.",
                }
            )
        evidence = []
        for a in session.scalars(
            select(SP500Anchor)
            .where(SP500Anchor.as_of_date < date(2017, 9, 30))
            .order_by(SP500Anchor.as_of_date)
        ):
            arch = session.get_one(RawSourceArchive, a.archive_id)
            raw = store.get(arch.sha256)
            assert hashlib.sha256(raw).hexdigest() == a.source_sha256
            raw_names = {h.position: h.raw_name for h in parse_n30d_schedule(raw)}
            base_url = arch.source_identifier.rsplit("/", 1)[0]
            complete = session.scalars(
                select(RawSourceArchive)
                .where(RawSourceArchive.source_identifier == base_url + "/" + a.accession + ".txt")
                .order_by(RawSourceArchive.retrieved_at.desc())
            ).first()
            header = parse_submission_header(store.get(complete.sha256)) if complete else None
            members = []
            for m in session.scalars(
                select(SP500AnchorMember)
                .where(SP500AnchorMember.anchor_id == a.anchor_id)
                .order_by(SP500AnchorMember.source_position)
            ):
                ids = (
                    [
                        {
                            "type": e.id_type,
                            "value": e.value,
                            "observed_on": str(e.observed_on),
                            "source_hash": e.source_sha256,
                        }
                        for e in session.scalars(
                            select(SecurityIdentifierEvidence).where(
                                SecurityIdentifierEvidence.security_id == m.security_id,
                                SecurityIdentifierEvidence.kind == "OFFICIAL",
                                SecurityIdentifierEvidence.observed_on == a.as_of_date,
                            )
                        )
                    ]
                    if m.security_id
                    else []
                )
                members.append(
                    {
                        "position": m.source_position,
                        "raw_name": raw_names.get(m.source_position),
                        "resolved_name": m.issuer_name,
                        "security_id": m.security_id,
                        "cusip": m.cusip,
                        "isin": m.isin,
                        "identity_basis": m.identity_basis,
                        "status": m.status,
                        "dated_official_identifiers": ids,
                    }
                )
            evidence.append(
                {
                    "accession": a.accession,
                    "period": str(a.as_of_date),
                    "form": a.form,
                    "filer_cik": a.filer_cik,
                    "accepted_at": str(a.source_available_at),
                    "filing_date": str(header.filing_date) if header else None,
                    "complete_submission_hash": complete.sha256 if complete else None,
                    "period_verification_version": "spy-n30d-period-v1",
                    "source": arch.source_identifier,
                    "archive_id": arch.archive_id,
                    "sha256": arch.sha256,
                    "retrieved_at": str(arch.retrieved_at),
                    "parser_version": a.parser_version,
                    "evidence_kind": "SEC_FILED_INDEX_REPLICATION_ANCHOR",
                    "members": members,
                }
            )
        weak = [
            {
                "security_id": sid,
                "names": sorted(
                    set(
                        session.scalars(
                            select(SP500AnchorMember.issuer_name).where(
                                SP500AnchorMember.security_id == sid
                            )
                        )
                    )
                ),
            }
            for sid in rep.weak_identity
        ]
        anomalous = session.scalars(
            select(RawSourceArchive)
            .where(RawSourceArchive.source_identifier.like("%000119312514428689/d813757dn30d.htm"))
            .order_by(RawSourceArchive.retrieved_at.desc())
        ).first()
        output = {
            "scope": "DEV 2011-01..2022-09; sealed holdout and OOT excluded",
            "engine_version": ENGINE_VERSION,
            "anchors_before_raw": 24,
            "anchors_after_raw": session.query(SP500Anchor).count(),
            "canonical_anchors_before": 17,
            "canonical_anchors_after": len(rep.anchors),
            "ready_before": 60,
            "ready_after_membership": rep.ready,
            "longest_run": rep.longest_run,
            "required_run": 85,
            "weak_identity": weak,
            "blocked_months": blocked,
            "gap_categories": dict(Counter(g["category"] for g in gaps if g["blocks_membership"])),
            "membership_blockers": sum(g["blocks_membership"] for g in gaps),
            "gaps": gaps,
            "excluded_filing": {
                "accession": "0001193125-14-428689",
                "expected_period": "2014-09-30",
                "submissions_and_header_period": "2013-09-30",
                "document_schedule_period": "2014-09-30",
                "status": "METADATA_DOCUMENT_DISCREPANCY",
                "archive_id": anomalous.archive_id if anomalous else None,
                "sha256": anomalous.sha256 if anomalous else None,
                "retrieved_at": str(anomalous.retrieved_at) if anomalous else None,
                "minimum_action": "Obtain consistent corrected filing or separately qualified official anchor; never override this period silently.",
            },
        }
    (ROOT / "docs/D02_EXTENDED_AUDIT.json").write_text(json.dumps(output, indent=2) + "\n")
    (ROOT / "docs/D02_EXTENDED_ANCHOR_PROVENANCE.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    md = [
        "# D02 — extensión DEV y cola documental",
        "",
        f"Anclas: 24 → {output['anchors_after_raw']} filas verificadas; 17 → {len(rep.anchors)} nodos por fecha. Membresía: {rep.ready}/141; racha {rep.longest_run}/85; nuevos meses listos: {rep.ready - 60}. No se entrena.",
        "",
        "El encabezado/API del filing 2014-09 discrepa del schedule: permanece excluido. La cadena acota todos los meses; una ancla por sí sola no fija las fechas de los cambios entre anclas.",
        "",
        f"Bloqueos de membresía: {output['membership_blockers']}; identidad débil: {len(weak)} securities históricas. Los 60 meses originales siguen listos.",
        "",
        "## Anclas añadidas",
        "",
        "| Fecha | Formulario | Accession | SHA-256 |",
        "|---|---|---|---|",
    ]
    md += [f"| {a['period']} | {a['form']} | {a['accession']} | {a['sha256']} |" for a in evidence]
    md += [
        "",
        "## Meses bloqueados y mínima acción",
        "",
        "El JSON contiene todas las fichas con gap_id estable, fechas exactas, identificadores, anclas A/B y hashes. La procedencia incluye cada nombre original y resuelto, CUSIP/ISIN observado, método y versión; los bytes originales se conservan en el archivo local.",
        "",
        "| Mes | Segmento | Motivo | Gaps |",
        "|---|---|---|---|",
    ]
    md += [
        f"| {b['month']} | {b['segment']} | {'; '.join(b['reasons'])} | {len(b['gap_ids'])} |"
        for b in blocked
    ]
    md += [
        "",
        "## Identidades pendientes",
        "",
        *[
            f"- {w['security_id']}: {', '.join(w['names'])}. Falta vínculo oficial de clase e identificador, nunca coincidencia difusa."
            for w in weak
        ],
    ]
    (ROOT / "docs/D02_EXTENDED_AUDIT.md").write_text("\n".join(md) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in output.items()
                if k not in {"gaps", "blocked_months", "weak_identity"}
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
