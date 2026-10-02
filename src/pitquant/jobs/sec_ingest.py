"""SEC EDGAR jobs: ingest a list of CIKs, and pick stress-test filings BY QUERY.

Real runs need ``PITQUANT_SEC_USER_AGENT`` with a contact e-mail (SEC fair-access policy);
``SECClient`` refuses to start without it, so nothing here can reach SEC anonymously.

Stress cases are selected from each issuer's own ``submissions`` metadata — never from
memory of "company X restated in year Y". The submissions acceptance field is only a HINT
(its zone is ambiguous); the archived header remains authoritative once ingested.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import UnknownSecurityError
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.providers.sec_edgar.parsers import SubmissionFiling, cik10
from pitquant.data.providers.sec_edgar.provider import (
    SECEdgarFundamentalProvider,
    SecIngestReport,
    ingest_sec_company,
)
from pitquant.db.models import Issuer, IssuerIdentifier, SecFiling, Security
from pitquant.security_master.service import SecurityMaster

ET = ZoneInfo("America/New_York")


def security_for_cik(session: Session, settings: Settings, cik: str, *, register: bool) -> str:
    """Security carrying CIK ``cik`` (ADR-0022): the CIK identifies an ISSUER. A real ISSUER
    (``issuers`` + ``issuer_identifiers``) always exists; the returned security is its
    registration ANCHOR (``role=ISSUER_ANCHOR``) until a traded security of that issuer is
    registered from a dated source. Fundamentals carry ``issuer_id`` and so apply to every
    security of the issuer. No ticker is invented: tickers come only from dated sources."""
    sm = SecurityMaster(session)
    key = cik10(cik)
    try:
        sid = sm.resolve_identifier("CIK", key, utc_now().date())
        _ensure_cik_issuer(session, session.get_one(Security, sid), key, settings)
        return sid
    except UnknownSecurityError:
        if not register:
            raise
    sec = sm.register(name=f"CIK {key} (SEC EDGAR)", exchange="XNYS", currency="USD", country="US")
    sec.role = "ISSUER_ANCHOR"
    sm.add_identifier(sec.security_id, "CIK", key, settings.fundamentals.sec.coverage_start)
    _ensure_cik_issuer(session, sec, key, settings)
    return sec.security_id


def _ensure_cik_issuer(session: Session, sec: Security, key: str, settings: Settings) -> str:
    ident = session.scalars(
        select(IssuerIdentifier).where(
            IssuerIdentifier.id_type == "CIK", IssuerIdentifier.value == key
        )
    ).first()
    if ident is None:
        iss = Issuer(name=sec.name, country="US")
        session.add(iss)
        session.flush()
        session.add(
            IssuerIdentifier(
                issuer_id=iss.issuer_id,
                id_type="CIK",
                value=key,
                valid_from=settings.fundamentals.sec.coverage_start,
                source="SEC EDGAR (CIK)",
            )
        )
        session.flush()
        issuer_id = iss.issuer_id
    else:
        issuer_id = ident.issuer_id
    if sec.issuer_id is None:
        sec.issuer_id = issuer_id
    return issuer_id


def ingest_ciks(
    session: Session,
    provider: SECEdgarFundamentalProvider,
    settings: Settings,
    ciks: list[str],
    *,
    register_missing: bool = False,
) -> list[SecIngestReport]:
    reports = []
    for cik in ciks:
        sid = security_for_cik(session, settings, cik, register=register_missing)
        reports.append(ingest_sec_company(session, provider, cik, sid))
        session.commit()  # one issuer at a time: a failure later keeps earlier work
    return reports


# ───────────────────────────── stress-case selection ─────────────────────────────


@dataclass
class StressScan:
    cik: str
    by_tag: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    @property
    def missing(self) -> list[str]:
        return [t for t in STRESS_TAGS if not self.by_tag.get(t)]


STRESS_TAGS = (
    "10-K",
    "10-Q",
    "amendment",
    "pre_market",
    "intraday",
    "after_close",
    "friday_after_close",
    "holiday_eve_or_early_close",
    "filing_date_after_acceptance_day",
    "same_period_multiple_filings",
)


def _acceptance_hint(f: SubmissionFiling) -> datetime | None:
    """submissions ``acceptanceDateTime`` read as UTC. Verified on real data (2026-10-01):
    126/126 MSFT+AAPL filings matched the header ACCEPTANCE-DATETIME (US/Eastern) converted
    to UTC to the second. Still only a hint: the header is authoritative."""
    if not f.acceptance_raw:
        return None
    naive = datetime.fromisoformat(f.acceptance_raw.replace("Z", "")).replace(tzinfo=None)
    return naive.replace(tzinfo=UTC)


@dataclass(frozen=True)
class _Row:
    accession: str
    form: str
    filing_date: date
    report_date: date | None
    accepted: datetime | None


def scan_stress_cases(
    cik: str, filings: list[SubmissionFiling], forms: list[str], coverage_start: date
) -> StressScan:
    """Pre-ingestion selection from submissions metadata (acceptance = hint)."""
    rows = [
        _Row(f.accession_number, f.form, f.filing_date, f.report_date, _acceptance_hint(f))
        for f in filings
        if f.form in forms and f.filing_date >= coverage_start
    ]
    return _scan(cik, rows)


def scan_ingested(session: Session, cik: str) -> StressScan:
    """Post-ingestion tags from the archived HEADER acceptance (authoritative)."""
    rows = [
        _Row(f.accession_number, f.form, f.filed_date, f.report_period, f.accepted_at)
        for f in session.scalars(select(SecFiling).where(SecFiling.cik == cik10(cik)))
    ]
    return _scan(cik, rows)


def _scan(cik: str, rows: list[_Row]) -> StressScan:
    cal = get_calendar("XNYS")
    scan = StressScan(cik10(cik))
    periods: dict[tuple[str, date], list[str]] = defaultdict(list)
    for f in rows:
        acc = f.accession
        base = f.form.removesuffix("/A")
        if base in ("10-K", "10-Q"):
            scan.by_tag[base].append(acc)
        if f.form.endswith("/A"):
            scan.by_tag["amendment"].append(acc)
        if f.report_date:
            periods[(base, f.report_date)].append(acc)
        if f.accepted is None:
            continue
        local = f.accepted.astimezone(ET)
        day = local.date()
        if day < f.filing_date:
            scan.by_tag["filing_date_after_acceptance_day"].append(acc)
        if not cal.is_session(day):
            continue
        open_, close = cal.session_open(day), cal.session_close(day)
        if f.accepted < open_:
            scan.by_tag["pre_market"].append(acc)
        elif f.accepted < close:
            scan.by_tag["intraday"].append(acc)
        else:
            scan.by_tag["after_close"].append(acc)
            if day.weekday() == 4:
                scan.by_tag["friday_after_close"].append(acc)
        nxt = cal.next_session(day)
        early = close.astimezone(ET).time() < time(16, 0)
        if early or (nxt - day).days > (3 if day.weekday() == 4 else 1):
            scan.by_tag["holiday_eve_or_early_close"].append(acc)
    for accs in periods.values():
        if len(accs) > 1:
            scan.by_tag["same_period_multiple_filings"].extend(accs)
    return scan
