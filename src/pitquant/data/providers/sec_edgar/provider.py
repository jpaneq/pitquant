"""SECEdgarFundamentalProvider and its point-in-time ingestion (D-01).

Temporal provenance is resolved per ACCESSION, never from companyfacts alone:

1. Submissions → CIK, accession, form, filing date, metadata.
2. For every accession that carries facts: the EDGAR header (``.hdr.sgml``) is fetched and
   archived; ``ACCEPTANCE-DATETIME`` (US/Eastern) becomes ``accepted_at``.
3. The filing's own XBRL instance is fetched and archived; companyfacts values are
   validated against it when present (mismatch → rejected and logged).
4. Each fact is stored as a VERSION bound to (cik, accession, form, filed_date,
   accepted_at, taxonomy, concept, unit, period, value, source_document, amendment).
5. ``available_at`` follows the configured availability policy.

companyfacts is used for discovery and efficient download only. A fact whose accession
cannot be tied to an archived header is rejected (``fact_without_filing``).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import SecConfig
from pitquant.core.errors import DataQualityError
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import utc_now
from pitquant.data.archive import ArchiveStore, archive_document, load_archived
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.availability import filing_available_at
from pitquant.data.providers.sec_edgar.client import (
    ARCHIVE_DIR_URL,
    COMPANYFACTS_URL,
    HEADER_URL,
    INDEX_URL,
    SUBMISSIONS_PAGE_URL,
    SUBMISSIONS_URL,
    SECClient,
    SECFetchError,
)
from pitquant.data.providers.sec_edgar.parsers import (
    PARSER_VERSION,
    CompanyFact,
    SubmissionFiling,
    acceptance_raw_consistent,
    accession_nodash,
    cik10,
    parse_acceptance_datetime,
    parse_companyfacts,
    parse_submissions,
    parse_xbrl_instance,
    pick_xbrl_instance,
)
from pitquant.db.models import DataQualityIssue, DataSource, FundamentalFact, SecFiling

PROVIDER = "SEC_EDGAR"


@dataclass
class SecIngestReport:
    cik: str
    filings_inserted: int = 0
    filings_skipped_existing: int = 0
    facts_inserted: int = 0
    facts_skipped_existing: int = 0
    facts_rejected: int = 0
    facts_out_of_coverage: int = 0
    filings_not_cited: int = 0
    issues: list[str] = field(default_factory=list)


@dataclass
class SECEdgarFundamentalProvider:
    client: SECClient
    store: ArchiveStore
    config: SecConfig

    # ── raw fetches, always archived ───────────────────────────────────────
    def _fetch(
        self, session: Session, url: str, mime: str, published_at: object = None
    ) -> tuple[bytes, str]:
        body = self.client.get(url).body
        row = archive_document(
            session,
            self.store,
            provider=PROVIDER,
            source_identifier=url,
            data=body,
            mime_type=mime,
            published_at=published_at,  # type: ignore[arg-type]
            parser_version=PARSER_VERSION,
        )
        return body, row.archive_id

    def submissions(self, session: Session, cik: str) -> list[SubmissionFiling]:
        body, _ = self._fetch(session, SUBMISSIONS_URL.format(cik10=cik10(cik)), "application/json")
        filings, pages = parse_submissions(body)
        for name in pages:  # older history is paginated
            page, _ = self._fetch(
                session, SUBMISSIONS_PAGE_URL.format(name=name), "application/json"
            )
            filings.extend(parse_submissions(page)[0])
        return filings

    def companyfacts(self, session: Session, cik: str) -> list[CompanyFact]:
        body, _ = self._fetch(
            session, COMPANYFACTS_URL.format(cik10=cik10(cik)), "application/json"
        )
        return parse_companyfacts(body)

    def header(self, session: Session, cik: str, acc: str) -> tuple[datetime, str]:
        """Fetch, parse and archive the header; the archive row carries accepted_at."""
        url = HEADER_URL.format(cik=int(cik), acc_nodash=accession_nodash(acc), acc=acc)
        body = self.client.get(url).body
        accepted = parse_acceptance_datetime(body, expected_accession=acc)
        row = archive_document(
            session,
            self.store,
            provider=PROVIDER,
            source_identifier=url,
            data=body,
            mime_type="text/plain",
            published_at=accepted,
            parser_version=PARSER_VERSION,
        )
        return accepted, row.archive_id

    def xbrl_instance(self, session: Session, cik: str, acc: str) -> tuple[bytes, str, str] | None:
        idx, _ = self._fetch(
            session,
            INDEX_URL.format(cik=int(cik), acc_nodash=accession_nodash(acc)),
            "application/json",
        )
        name = pick_xbrl_instance(idx)
        if name is None:
            return None
        url = ARCHIVE_DIR_URL.format(cik=int(cik), acc_nodash=accession_nodash(acc)) + name
        body, arch_id = self._fetch(session, url, "application/xml")
        return body, arch_id, url


def _issue(session: Session, sid: str, check: str, sev: str, detail: str, **fields: object) -> None:
    """Record a DQ issue with STRUCTURED details (the only trace of a rejected fact, used by
    ``audit.explain``). Re-running an ingestion does not duplicate an identical issue."""
    details: dict[str, object] = {"detail": detail, **{k: _jsonable(v) for k, v in fields.items()}}
    fingerprint = content_hash({"check": check, "security_id": sid, **details})
    for prior in session.scalars(
        select(DataQualityIssue).where(
            DataQualityIssue.check_name == check, DataQualityIssue.security_id == sid
        )
    ):
        if prior.details.get("fingerprint") == fingerprint:
            return
    session.add(
        DataQualityIssue(
            entity="sec_fact",
            security_id=sid,
            check_name=check,
            severity=sev,
            details={**details, "fingerprint": fingerprint},
        )
    )
    session.flush()


def _jsonable(v: object) -> object:
    return v.isoformat() if isinstance(v, date | datetime) else v


def _source_id(session: Session) -> int:
    src = session.scalars(select(DataSource).where(DataSource.name == PROVIDER)).first()
    if src is None:
        src = DataSource(
            name=PROVIDER,
            provider_type="fundamentals",
            is_synthetic=False,
            is_point_in_time=True,
            description="SEC EDGAR, accession-level provenance",
        )
        session.add(src)
        session.flush()
    return src.source_id


def ingest_sec_company(
    session: Session,
    provider: SECEdgarFundamentalProvider,
    cik: str,
    security_id: str,
    *,
    exchange: str = "XNYS",
) -> SecIngestReport:
    cfg = provider.config
    rep = SecIngestReport(cik=cik10(cik))
    cal = get_calendar(exchange)
    src_id = _source_id(session)

    all_filings = {f.accession_number: f for f in provider.submissions(session, cik)}
    filings = {
        a: f
        for a, f in all_filings.items()
        if f.form in cfg.forms and f.filing_date >= cfg.coverage_start
    }
    facts = provider.companyfacts(session, cik)
    by_acc: dict[str, list[CompanyFact]] = defaultdict(list)
    for f in facts:
        if f.filed < cfg.coverage_start:
            rep.facts_out_of_coverage += 1
            continue
        by_acc[f.accession_number].append(f)

    # companyfacts attributes a value to ONE filing; an in-scope filing it never cites
    # (e.g. an original 10-Q whose facts companyfacts attributes to the later 10-Q/A) is
    # not ingested. No leak (the data shows up later, not earlier) but a coverage gap:
    # made visible, never silent.
    for acc, meta in sorted(filings.items()):
        if acc not in by_acc:
            _issue(
                session,
                security_id,
                "filing_not_cited_by_companyfacts",
                "medium",
                f"{acc} {meta.form} filed {meta.filing_date}: in scope but cited by no "
                "companyfacts value; its facts are first known from a later filing",
                accession=acc,
                form=meta.form,
                filed_date=meta.filing_date,
            )
            rep.filings_not_cited += 1
    sec_rows: dict[str, SecFiling] = {}
    instances: dict[str, dict[tuple[str, str, date | None, date, str], float]] = {}
    for acc in sorted(by_acc):
        meta = filings.get(acc)
        if meta is None:
            continue  # handled below as fact_without_filing (not in submissions / not in scope)
        existing = session.get(SecFiling, acc)
        if existing is not None:
            sec_rows[acc] = existing
            rep.filings_skipped_existing += 1
            if existing.xbrl_archive_id:  # re-validate from the ARCHIVED instance, no refetch
                instances[acc] = parse_xbrl_instance(
                    load_archived(session, provider.store, existing.xbrl_archive_id)
                )
            continue
        try:
            accepted, hdr_id = provider.header(session, cik, acc)
        except (SECFetchError, DataQualityError) as e:
            _issue(session, security_id, "header_unavailable", "high", f"{acc}: {e}", accession=acc)
            rep.issues.append(f"{acc}: header unavailable")
            continue
        if acceptance_raw_consistent(meta.acceptance_raw, accepted) is False:
            _issue(
                session,
                security_id,
                "acceptance_mismatch",
                "medium",
                f"{acc}: submissions {meta.acceptance_raw} vs header {accepted.isoformat()} "
                "(header used)",
                accession=acc,
                submissions_acceptance_raw=meta.acceptance_raw,
                header_accepted_at=accepted,
            )
        xbrl_id = None
        try:
            inst = provider.xbrl_instance(session, cik, acc)
            if inst is not None:
                instances[acc] = parse_xbrl_instance(inst[0])
                xbrl_id = inst[1]
            else:
                _issue(session, security_id, "xbrl_instance_missing", "low", acc, accession=acc)
        except (SECFetchError, ValueError) as e:
            _issue(
                session,
                security_id,
                "xbrl_instance_unavailable",
                "medium",
                f"{acc}: {e}",
                accession=acc,
            )
        row = SecFiling(
            accession_number=acc,
            cik=cik10(cik),
            security_id=security_id,
            form=meta.form,
            is_amendment=meta.form.endswith("/A"),
            filed_date=meta.filing_date,
            report_period=meta.report_date,
            accepted_at=accepted,
            submissions_acceptance_raw=meta.acceptance_raw,
            available_at=filing_available_at(
                cal, accepted, cfg.availability_policy, cfg.lag_minutes
            ),
            availability_policy=cfg.availability_policy,
            primary_document=meta.primary_document,
            header_archive_id=hdr_id,
            xbrl_archive_id=xbrl_id,
        )
        session.add(row)
        session.flush()
        sec_rows[acc] = row
        rep.filings_inserted += 1

    open_rejections = _open_rejections(session, security_id)
    for acc, rows in sorted(by_acc.items()):
        filing = sec_rows.get(acc)
        if filing is None and acc in all_filings and acc not in filings:
            rep.facts_out_of_coverage += len(rows)  # form/date outside configured scope
            continue
        if filing is None:
            rep.facts_rejected += len(rows)
            for f in rows:
                _issue(
                    session,
                    security_id,
                    "fact_without_filing",
                    "high",
                    f"{acc} cites no verified filing header",
                    accession=acc,
                    taxonomy=f.taxonomy,
                    concept=f.concept,
                    unit=f.unit,
                    period_start=f.start,
                    period_end=f.end,
                    companyfacts_value=f.value,
                )
            continue
        inst_facts = instances.get(acc)
        seen = {
            (r.taxonomy, r.concept, r.unit, r.period_start, r.period_end): r.value
            for r in session.scalars(
                select(FundamentalFact).where(FundamentalFact.accession_number == acc)
            )
        }
        for f in rows:
            key = (f.taxonomy, f.concept, f.unit, f.start, f.end)
            ident = {
                "accession": acc,
                "taxonomy": f.taxonomy,
                "concept": f.concept,
                "unit": f.unit,
                "period_start": f.start,
                "period_end": f.end,
            }
            if key in seen:
                stored = seen[key]
                if stored is not None and not _close(stored, f.value):
                    # Same accession, same fact, different value: the source drifted. The
                    # stored version stays (append-only); the drift is surfaced, never applied.
                    _issue(
                        session,
                        security_id,
                        "companyfacts_value_drift",
                        "high",
                        f"{acc} {f.concept} {f.start}..{f.end}: stored {stored} vs "
                        f"companyfacts now {f.value}",
                        **ident,
                        stored_value=stored,
                        companyfacts_value=f.value,
                    )
                    rep.issues.append(f"{acc}: value drift on {f.concept}")
                else:
                    _resolve_rejections(open_rejections, ident)
                rep.facts_skipped_existing += 1
                continue
            if inst_facts is not None:
                v = inst_facts.get((f.taxonomy, f.concept, f.start, f.end, f.unit))
                if v is not None and math.isnan(v):
                    rep.facts_rejected += 1
                    _issue(
                        session,
                        security_id,
                        "xbrl_inconsistent_duplicates",
                        "high",
                        f"{acc} {f.concept} {f.start}..{f.end}: the instance reports "
                        "conflicting values for this fact",
                        **ident,
                        companyfacts_value=f.value,
                    )
                    continue
                if v is not None and not _close(v, f.value):
                    rep.facts_rejected += 1
                    _issue(
                        session,
                        security_id,
                        "companyfacts_xbrl_mismatch",
                        "high",
                        f"{acc} {f.concept} {f.start}..{f.end}: companyfacts {f.value} != "
                        f"instance {v}",
                        **ident,
                        companyfacts_value=f.value,
                        instance_value=v,
                    )
                    continue
            if f.form and f.form != filing.form:
                _issue(
                    session,
                    security_id,
                    "form_mismatch",
                    "low",
                    f"{acc}: companyfacts form {f.form} vs submissions {filing.form}",
                    accession=acc,
                    companyfacts_form=f.form,
                    submissions_form=filing.form,
                )
            session.add(
                FundamentalFact(
                    security_id=security_id,
                    taxonomy=f.taxonomy,
                    concept=f.concept,
                    fiscal_period=f"{f.fy}{f.fp}" if f.fy and f.fp else None,
                    period_start=f.start,
                    period_end=f.end,
                    value=f.value,
                    unit=f.unit,
                    currency="USD" if f.unit.startswith("USD") else None,
                    available_at=filing.available_at,
                    cik=filing.cik,
                    accession_number=acc,
                    form=filing.form,
                    filed_date=filing.filed_date,
                    accepted_at=filing.accepted_at,
                    is_amendment=filing.is_amendment,
                    source_document=ARCHIVE_DIR_URL.format(
                        cik=int(cik), acc_nodash=accession_nodash(acc)
                    )
                    + (filing.primary_document or ""),
                    source_id=src_id,
                )
            )
            seen[key] = f.value
            rep.facts_inserted += 1
            _resolve_rejections(open_rejections, ident)
    session.flush()
    return rep


_REJECTION_CHECKS = ("companyfacts_xbrl_mismatch", "xbrl_inconsistent_duplicates")


def _open_rejections(
    session: Session, sid: str
) -> dict[tuple[object, ...], list[DataQualityIssue]]:
    out: dict[tuple[object, ...], list[DataQualityIssue]] = defaultdict(list)
    for issue in session.scalars(
        select(DataQualityIssue).where(
            DataQualityIssue.security_id == sid,
            DataQualityIssue.check_name.in_(_REJECTION_CHECKS),
            DataQualityIssue.resolved_at.is_(None),
        )
    ):
        out[_ident_key(issue.details)].append(issue)
    return out


def _ident_key(d: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(
        _jsonable(d.get(k))
        for k in ("accession", "taxonomy", "concept", "unit", "period_start", "period_end")
    )


def _resolve_rejections(
    open_: dict[tuple[object, ...], list[DataQualityIssue]], ident: Mapping[str, object]
) -> None:
    """A fact once rejected and now accepted (e.g. after a parser fix) closes its open DQ
    issues. The issue rows stay (audit trail); only ``resolved_at`` is set."""
    for issue in open_.pop(_ident_key(ident), []):
        issue.resolved_at = utc_now()


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a))
