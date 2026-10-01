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
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

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
from pitquant.security_master.service import SecurityMaster

ET = ZoneInfo("America/New_York")


def security_for_cik(session: Session, settings: Settings, cik: str, *, register: bool) -> str:
    """Security carrying CIK ``cik``. With ``register`` a missing one is created WITHOUT a
    ticker: tickers come only from dated sources (universe events / D-05), never from the
    current submissions document projected into the past."""
    sm = SecurityMaster(session)
    key = cik10(cik)
    try:
        return sm.resolve_identifier("CIK", key, utc_now().date())
    except UnknownSecurityError:
        if not register:
            raise
    sec = sm.register(name=f"CIK {key} (SEC EDGAR)", exchange="XNYS", currency="USD", country="US")
    sm.add_identifier(sec.security_id, "CIK", key, settings.fundamentals.sec.coverage_start)
    return sec.security_id


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
    if not f.acceptance_raw:
        return None
    naive = datetime.fromisoformat(f.acceptance_raw.replace("Z", "")).replace(tzinfo=None)
    return naive.replace(tzinfo=ET)  # EDGAR wall time; header confirms at ingestion


def scan_stress_cases(cik: str, filings: list[SubmissionFiling], forms: list[str]) -> StressScan:
    cal = get_calendar("XNYS")
    scan = StressScan(cik10(cik))
    periods: dict[tuple[str, date], list[str]] = defaultdict(list)
    for f in filings:
        if f.form not in forms:
            continue
        acc = f.accession_number
        base = f.form.removesuffix("/A")
        if base in ("10-K", "10-Q"):
            scan.by_tag[base].append(acc)
        if f.form.endswith("/A"):
            scan.by_tag["amendment"].append(acc)
        if f.report_date:
            periods[(base, f.report_date)].append(acc)
        hint = _acceptance_hint(f)
        if hint is None:
            continue
        day = hint.date()
        if hint.date() < f.filing_date:
            scan.by_tag["filing_date_after_acceptance_day"].append(acc)
        if not cal.is_session(day):
            continue
        open_, close = cal.session_open(day), cal.session_close(day)
        if hint < open_:
            scan.by_tag["pre_market"].append(acc)
        elif hint < close:
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
