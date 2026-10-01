"""CNMVFundamentalProvider: point-in-time ingestion of CNMV periodic reports (ADR-0018).

Temporal policy (DATE_ONLY, fail closed):
* the CNMV page gives the «Publicación inicial» DATE and the DATES of later modifications,
  never an hour → ``availability_precision = DATE_ONLY``; no hour is invented;
* the XBRL that can be downloaded is the CURRENT version of the report (modifications
  already merged) and there is no way to prove which values existed at the initial
  publication → the content is usable from the first XMAD session open strictly after the
  end of the LATEST of those dates (``MarketCalendar.date_only_available_at``);
* every retrieval (page and XBRL) is archived with its SHA-256; facts are append-only
  versions bound to the filing row (``cnmv_filings``).
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError, UnknownSecurityError
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.providers.cnmv.parsers import (
    PARSER_VERSION,
    IfiDetail,
    IfiListEntry,
    parse_ifi_detail,
    parse_ifi_list,
    parse_ipp_xbrl,
)
from pitquant.db.models import CnmvFiling, DataSource, FundamentalFact
from pitquant.security_master.service import SecurityMaster

PROVIDER = "CNMV"
BASE = "https://www.cnmv.es"
LIST_URL = BASE + "/Portal/Consultas/IFI/ListaIFI.aspx?nif={nif}"
DETAIL_URL = BASE + "/Portal/AlDia/DetalleIFIAlDia?nreg={nreg}"


class Fetcher:
    """Plain HTTPS GET with a fixed delay between requests (public pages, low volume)."""

    def __init__(self, user_agent: str = "PITQuant research", delay_s: float = 1.0) -> None:
        self.user_agent, self.delay_s = user_agent, delay_s

    def get(self, url: str) -> tuple[bytes, str]:
        safe = urllib.parse.quote(url, safe=":/?=&%.-_")
        req = urllib.request.Request(safe, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=120) as r:
            body, ctype = r.read(), r.headers.get("Content-Type", "")
        time.sleep(self.delay_s)
        return body, ctype


@dataclass
class CnmvIngestReport:
    nreg: str
    status: str = "pending"
    facts_inserted: int = 0
    facts_skipped_existing: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class CNMVFundamentalProvider:
    fetcher: Fetcher
    store: ArchiveStore

    def list_reports(self, session: Session, nif: str) -> list[IfiListEntry]:
        url = LIST_URL.format(nif=nif)
        body, _ = self.fetcher.get(url)
        archive_document(
            session,
            self.store,
            provider=PROVIDER,
            source_identifier=url,
            data=body,
            mime_type="text/html",
            parser_version=PARSER_VERSION,
            notes="source_type=ifi_list",
        )
        return parse_ifi_list(body)

    def detail(self, session: Session, nreg: str) -> tuple[IfiDetail, str]:
        url = DETAIL_URL.format(nreg=nreg)
        body, _ = self.fetcher.get(url)
        row = archive_document(
            session,
            self.store,
            provider=PROVIDER,
            source_identifier=url,
            data=body,
            mime_type="text/html",
            parser_version=PARSER_VERSION,
            notes="source_type=ifi_detail",
        )
        return parse_ifi_detail(body), row.archive_id

    def xbrl(self, session: Session, nreg: str, path: str) -> tuple[bytes, str, str]:
        url = (
            path
            if path.startswith("http")
            else BASE + "/Portal/consultas/wuc/" + path.split("/")[-1]
        )
        body, ctype = self.fetcher.get(url)
        # The download token is per page view; archive under a stable identifier.
        row = archive_document(
            session,
            self.store,
            provider=PROVIDER,
            source_identifier=f"cnmv:ipp-xbrl:{nreg}",
            data=body,
            mime_type="application/xml",
            parser_version=PARSER_VERSION,
            notes=f"source_type=ipp_xbrl; Content-Type: {ctype}; url={url}",
        )
        return body, row.archive_id, row.sha256


def _source_id(session: Session) -> int:
    src = session.scalars(select(DataSource).where(DataSource.name == PROVIDER)).first()
    if src is None:
        src = DataSource(
            name=PROVIDER,
            provider_type="fundamentals",
            is_synthetic=False,
            is_point_in_time=True,
            description="CNMV regulated information (IPP XBRL), DATE_ONLY",
        )
        session.add(src)
        session.flush()
    return src.source_id


def security_for_cif(session: Session, cif: str, company: str, *, register: bool) -> str:
    """Issuer identified by its CIF (no ticker invented from today's data)."""
    sm = SecurityMaster(session)
    from datetime import date

    try:
        return sm.resolve_identifier("CIF", cif, date(2100, 1, 1))
    except UnknownSecurityError:
        if not register:
            raise
    sec = sm.register(name=f"{company} (CNMV)", exchange="XMAD", currency="EUR", country="ES")
    sm.add_identifier(sec.security_id, "CIF", cif, date(1900, 1, 1))
    return sec.security_id


def ingest_cnmv_report(
    session: Session,
    provider: CNMVFundamentalProvider,
    nreg: str,
    *,
    register_missing: bool = False,
) -> CnmvIngestReport:
    rep = CnmvIngestReport(nreg)
    det, detail_id = provider.detail(session, nreg)
    if det.xbrl_path is None:
        rep.status = "no_xbrl"
        rep.notes.append("report has no XBRL download (PDF only): not machine-readable")
        return rep
    data, data_id, sha = provider.xbrl(session, nreg, det.xbrl_path)
    prior = session.scalars(
        select(CnmvFiling).where(CnmvFiling.nreg == nreg, CnmvFiling.data_sha256 == sha)
    ).first()
    if prior is not None:
        n = session.scalar(
            select(func.count())
            .select_from(FundamentalFact)
            .where(FundamentalFact.cnmv_filing_id == prior.filing_id)
        )
        if n:
            rep.status = "already_ingested"
            return rep
    sid = security_for_cif(session, det.cif, det.company, register=register_missing)
    if prior is not None:  # same bytes, previously rejected (0 facts): retry the parse only
        return _insert_facts(session, prior, data, rep)
    latest = max(d for d in (det.publication_date, det.last_modification) if d is not None)
    available = get_calendar("XMAD").date_only_available_at(latest)
    rule = (
        "DATE_ONLY: next XMAD open after end of latest(publication, modifications)"
        if det.modifications
        else "DATE_ONLY: next XMAD open after end of publication date"
    )
    filing = CnmvFiling(
        nreg=nreg,
        doc_kind="IFI_IPP",
        cif=det.cif,
        company=det.company,
        security_id=sid,
        period_start=det.period_start,
        period_end=det.period_end,
        period_label=f"{det.fiscal_year} S{det.semester}" if det.semester else str(det.fiscal_year),
        publication_date=det.publication_date,
        publication_time=None,
        last_modification_date=det.last_modification,
        modifications=[
            {"section": m.section, "description": m.description, "date": m.on.isoformat()}
            for m in det.modifications
        ],
        availability_precision="DATE_ONLY",
        effective_available_at=available,
        availability_rule=rule,
        source_url=DETAIL_URL.format(nreg=nreg),
        detail_archive_id=detail_id,
        data_archive_id=data_id,
        data_sha256=sha,
        parser_version=PARSER_VERSION,
    )
    session.add(filing)
    session.flush()
    return _insert_facts(session, filing, data, rep)


def _insert_facts(
    session: Session, filing: CnmvFiling, data: bytes, rep: CnmvIngestReport
) -> CnmvIngestReport:
    try:
        facts = parse_ipp_xbrl(data)
    except DataQualityError as e:
        rep.status = "rejected"
        rep.notes.append(str(e))
        return rep
    src_id = _source_id(session)
    for f in facts:
        session.add(
            FundamentalFact(
                security_id=filing.security_id,
                taxonomy=f.taxonomy,
                concept=f.concept[:200],
                fiscal_period=filing.period_label,
                period_start=f.period_start,
                period_end=f.period_end,
                value=f.value,
                unit=f.unit,
                currency="EUR" if f.unit.lower() in ("euro", "eur") else None,
                available_at=filing.effective_available_at,
                source_document=filing.source_url,
                source_id=src_id,
                cnmv_filing_id=filing.filing_id,
            )
        )
        rep.facts_inserted += 1
    session.flush()
    rep.status = "ok"
    return rep
