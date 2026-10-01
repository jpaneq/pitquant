"""Explain a point-in-time value: why the system knew it at T — and why it did not know
the others.

``explain_fact`` answers, for one security, concept and period at an instant ``as_of``:

* **known**: the version ``facts_as_of`` returns, with its full provenance chain
  security → ticker at T → accession → document → acceptance → effective availability →
  XBRL concept/value → parser version → archived source hashes;
* **not known**: every other version of the same fact, each with a reason code:

  - ``available_after_as_of`` — published, but its ``available_at`` is later than T;
  - ``ingested_after_data_version`` — the system stored it after the pinned cutoff;
  - ``superseded_by:<fact_id>`` — visible at T, but a later version was also visible;
  - ``rejected:<check_name>:<issue_id>`` — never stored as a fact (e.g. companyfacts
    disagreed with the filing's own XBRL instance); the data-quality issue is the trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.timeutils import require_aware, utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.engine import FactKey, facts_as_of
from pitquant.db.models import (
    CnmvFiling,
    DataQualityIssue,
    FundamentalFact,
    RawSourceArchive,
    SecFiling,
)
from pitquant.security_master.service import SecurityMaster


@dataclass(frozen=True)
class FactProvenance:
    fact_id: str
    taxonomy: str
    concept: str
    unit: str
    period_start: date | None
    period_end: date
    fiscal_period: str | None
    value: float | None
    accession_number: str | None
    form: str | None
    is_amendment: bool
    filed_date: date | None
    accepted_at: datetime | None  # filing header ACCEPTANCE-DATETIME
    effective_available_at: datetime  # availability policy applied to accepted_at
    availability_policy: str | None
    ingested_at: datetime
    source_document: str | None
    header_sha256: str | None
    xbrl_sha256: str | None
    parser_version: str | None


@dataclass(frozen=True)
class NotKnown:
    reason: str
    detail: str
    provenance: FactProvenance | None = None  # None for rejected (never stored) values
    issue: dict[str, Any] | None = None


@dataclass
class FactExplanation:
    security_id: str
    as_of: datetime
    ticker_at_as_of: str | None
    concept: str
    period_end: date
    known: FactProvenance | None
    not_known: list[NotKnown] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"{self.concept} @ {self.period_end} for {self.security_id} "
            f"(ticker then: {self.ticker_at_as_of or 'unknown'}) as of {self.as_of.isoformat()}",
        ]
        if self.known is None:
            lines.append("KNOWN: nothing — no version was available at that instant.")
        else:
            k = self.known
            lines += [
                f"KNOWN: {k.value} {k.unit} ({k.taxonomy}:{k.concept} "
                f"{k.period_start or ''}..{k.period_end}, {k.fiscal_period or '-'})",
                f"  filing      {k.form} {k.accession_number} filed {k.filed_date}"
                f"{' (amendment)' if k.is_amendment else ''}",
                f"  document    {k.source_document}",
                f"  accepted_at {k.accepted_at.isoformat() if k.accepted_at else '-'} (header)",
                f"  available   {k.effective_available_at.isoformat()} ({k.availability_policy})",
                f"  parser      {k.parser_version}  header sha256 {k.header_sha256}",
                f"  xbrl sha256 {k.xbrl_sha256}",
            ]
        for n in self.not_known:
            v = n.provenance
            what = f"{v.value} from {v.accession_number}" if v else "value never stored"
            lines.append(f"NOT KNOWN: {what} — {n.reason}: {n.detail}")
        return "\n".join(lines)


def _provenance(session: Session, f: FundamentalFact) -> FactProvenance:
    if f.cnmv_filing_id:
        return _cnmv_provenance(session, f)
    filing = session.get(SecFiling, f.accession_number) if f.accession_number else None
    hdr = session.get(RawSourceArchive, filing.header_archive_id) if filing else None
    xbrl = (
        session.get(RawSourceArchive, filing.xbrl_archive_id)
        if filing and filing.xbrl_archive_id
        else None
    )
    return FactProvenance(
        fact_id=f.fact_id,
        taxonomy=f.taxonomy,
        concept=f.concept,
        unit=f.unit,
        period_start=f.period_start,
        period_end=f.period_end,
        fiscal_period=f.fiscal_period,
        value=f.value,
        accession_number=f.accession_number,
        form=f.form,
        is_amendment=f.is_amendment,
        filed_date=f.filed_date,
        accepted_at=f.accepted_at,
        effective_available_at=f.available_at,
        availability_policy=filing.availability_policy if filing else None,
        ingested_at=f.ingested_at,
        source_document=f.source_document,
        header_sha256=hdr.sha256 if hdr else None,
        xbrl_sha256=xbrl.sha256 if xbrl else None,
        parser_version=(hdr.parser_version if hdr else None),
    )


def _cnmv_provenance(session: Session, f: FundamentalFact) -> FactProvenance:
    c = session.get_one(CnmvFiling, f.cnmv_filing_id)
    page = session.get(RawSourceArchive, c.detail_archive_id)
    mods = f", modified {c.last_modification_date}" if c.last_modification_date else ""
    return FactProvenance(
        fact_id=f.fact_id,
        taxonomy=f.taxonomy,
        concept=f.concept,
        unit=f.unit,
        period_start=f.period_start,
        period_end=f.period_end,
        fiscal_period=f.fiscal_period,
        value=f.value,
        accession_number=f"CNMV nreg {c.nreg}",
        form=f"{c.doc_kind} {c.period_label} (published {c.publication_date}{mods}, "
        f"{c.availability_precision})",
        is_amendment=c.last_modification_date is not None,
        filed_date=c.publication_date,
        accepted_at=None,  # the CNMV states no hour: never invented
        effective_available_at=f.available_at,
        availability_policy=c.availability_rule,
        ingested_at=f.ingested_at,
        source_document=c.source_url,
        header_sha256=page.sha256 if page else None,
        xbrl_sha256=c.data_sha256,
        parser_version=c.parser_version,
    )


def explain_fact(
    session: Session,
    security_id: str,
    concept: str,
    period_end: date,
    as_of: datetime,
    *,
    period_start: date | None = None,
    unit: str | None = None,
    ingested_before: datetime | None = None,
    exchange: str = "XNYS",
) -> FactExplanation:
    """Explain the value of ``concept`` for ``period_end`` known at ``as_of``.

    ``period_start``/``unit`` disambiguate when several facts share concept and period end
    (e.g. a quarter and a year-to-date duration). ``ingested_before`` pins a data version.
    """
    as_of = require_aware(as_of, "as_of")
    stmt = select(FundamentalFact).where(
        FundamentalFact.security_id == security_id,
        FundamentalFact.concept == concept,
        FundamentalFact.period_end == period_end,
    )
    if period_start is not None:
        stmt = stmt.where(FundamentalFact.period_start == period_start)
    if unit is not None:
        stmt = stmt.where(FundamentalFact.unit == unit)
    versions = list(session.scalars(stmt))
    keys = {FactKey(v.concept, v.period_start, v.period_end, v.unit, v.taxonomy) for v in versions}
    if len(keys) > 1:
        raise ValueError(
            f"{concept}@{period_end} is ambiguous ({len(keys)} durations/units); "
            "pass period_start and/or unit"
        )

    visible = facts_as_of(session, security_id, as_of, [concept], ingested_before=ingested_before)
    chosen = next((f for k, f in visible.items() if k in keys), None)
    local_day = pd.Timestamp(as_of).tz_convert(get_calendar(exchange).tz).date()
    out = FactExplanation(
        security_id=security_id,
        as_of=as_of,
        ticker_at_as_of=SecurityMaster(session).ticker_as_of(security_id, local_day),
        concept=concept,
        period_end=period_end,
        known=_provenance(session, chosen) if chosen else None,
    )
    cutoff = require_aware(ingested_before) if ingested_before is not None else None
    for v in sorted(versions, key=lambda x: (x.available_at, x.fact_id)):
        if chosen is not None and v.fact_id == chosen.fact_id:
            continue
        prov = _provenance(session, v)
        if v.available_at > as_of:
            out.not_known.append(
                NotKnown(
                    "available_after_as_of",
                    f"available_at {v.available_at.isoformat()} > as_of (accepted "
                    f"{v.accepted_at.isoformat() if v.accepted_at else '-'})",
                    prov,
                )
            )
        elif cutoff is not None and v.ingested_at > cutoff:
            out.not_known.append(
                NotKnown(
                    "ingested_after_data_version",
                    f"ingested {v.ingested_at.isoformat()} after the pinned cutoff "
                    f"{cutoff.isoformat()}",
                    prov,
                )
            )
        else:
            assert chosen is not None  # visible and not chosen => something superseded it
            out.not_known.append(
                NotKnown(
                    f"superseded_by:{chosen.fact_id}",
                    f"a later version ({out.known.accession_number if out.known else '?'}, "
                    "available "
                    f"{chosen.available_at.isoformat()}) was also known at as_of",
                    prov,
                )
            )
    for issue in session.scalars(
        select(DataQualityIssue)
        .where(DataQualityIssue.security_id == security_id)
        .order_by(DataQualityIssue.detected_at)
    ):
        d = issue.details or {}
        if d.get("concept") != concept or d.get("period_end") != period_end.isoformat():
            continue
        if period_start is not None and d.get("period_start") != period_start.isoformat():
            continue
        if cutoff is not None and issue.detected_at > cutoff:
            continue
        resolved_by = cutoff or utc_now()
        if issue.resolved_at is not None and issue.resolved_at <= resolved_by:
            continue  # rejected once, accepted later (e.g. parser fix): not a reason now
        out.not_known.append(
            NotKnown(
                f"rejected:{issue.check_name}:{issue.issue_id}",
                str(d.get("detail", "")),
                None,
                {k: v for k, v in d.items() if k != "fingerprint"},
            )
        )
    return out
