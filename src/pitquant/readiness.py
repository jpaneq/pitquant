"""'Real data ready' report (gate before Feature Engine / scoring).

Every status is computed from database state. Nothing is hardcoded as READY, and fixture or
synthetic rows never count: synthetic securities/sources, the fixture CIK 0000999999,
``SYN_*`` indices, SYNTHETIC builds and builds whose raw hash marks them as fixtures are
excluded (and the number excluded is reported).

Global READY requires every critical component READY and both invariant scans PASS. A
provisional source can never yield a global READY.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.availability import filing_available_at
from pitquant.db.models import (
    CorporateAction,
    DataQualityIssue,
    DataSource,
    Dividend,
    FundamentalFact,
    IndexMembership,
    MembershipBuild,
    Price,
    RawSourceArchive,
    SecFiling,
    Security,
)

FIXTURE_CIK = "0000999999"


class Status(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    PROVISIONAL = "PROVISIONAL"
    BLOCKED = "BLOCKED"


class Check(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class Component:
    name: str
    status: Status
    critical: bool = True
    securities: int = 0
    coverage_from: date | None = None
    coverage_to: date | None = None
    sources: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Scan:
    name: str
    result: Check
    rows_checked: int
    violations: list[str] = field(default_factory=list)


@dataclass
class ReadinessReport:
    overall: Status
    components: list[Component]
    identity_coverage_pct: float | None
    scans: list[Scan]
    provisional_sources: list[str]
    definitive_sources: list[str]
    excluded_fixture_rows: dict[str, int]
    blockers: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_text(self) -> str:
        out = [f"PITQuant data readiness: {self.overall}", ""]
        for c in self.components:
            cov = f"{c.coverage_from}..{c.coverage_to}" if c.coverage_from else "-"
            out.append(f"  {c.name:<22} {c.status:<12} securities={c.securities:<6} coverage={cov}")
            for g in c.gaps:
                out.append(f"      gap: {g}")
            for w in c.warnings:
                out.append(f"      warning: {w}")
        ic = "n/a" if self.identity_coverage_pct is None else f"{self.identity_coverage_pct:.1f}%"
        out.append(f"  {'Security identity':<22} coverage={ic}")
        for s in self.scans:
            out.append(f"  {s.name:<22} {s.result} ({s.rows_checked} rows checked)")
            for v in s.violations[:10]:
                out.append(f"      violation: {v}")
        out.append("")
        out.append(f"Definitive sources:  {', '.join(self.definitive_sources) or '-'}")
        out.append(f"Provisional sources: {', '.join(self.provisional_sources) or '-'}")
        if any(self.excluded_fixture_rows.values()):
            ex = ", ".join(f"{k}={v}" for k, v in self.excluded_fixture_rows.items() if v)
            out.append(f"Excluded fixture/synthetic rows: {ex}")
        if self.blockers:
            out.append("Blockers:")
            out += [f"  - {b}" for b in self.blockers]
        return "\n".join(out)


# ───────────────────────────── helpers ─────────────────────────────


def _synthetic_security_ids(session: Session) -> set[str]:
    rows = session.execute(select(Security.security_id, Security.name, Security.is_synthetic))
    return {
        sid for sid, name, syn in rows if syn or name.upper().startswith(("SYNTHETIC", "FIXTURE"))
    }


def _is_fixture_build(b: MembershipBuild) -> bool:
    return (
        b.source_confidence == "SYNTHETIC"
        or b.index_code.startswith("SYN_")
        or "fixture" in b.raw_source_hash.lower()
        or "fixture" in b.membership_source.lower()
    )


def _real_builds(session: Session, index_code: str) -> list[MembershipBuild]:
    rows = session.scalars(
        select(MembershipBuild)
        .where(MembershipBuild.index_code == index_code, MembershipBuild.status == "ok")
        .order_by(MembershipBuild.built_at.desc())
    )
    return [b for b in rows if not _is_fixture_build(b)]


def _intervals(session: Session, build_id: str) -> list[IndexMembership]:
    return list(
        session.scalars(select(IndexMembership).where(IndexMembership.build_id == build_id))
    )


def _membership_component(
    session: Session, name: str, index_code: str, provisional_status: Status
) -> tuple[Component, MembershipBuild | None, list[IndexMembership]]:
    builds = _real_builds(session, index_code)
    if not builds:
        return (
            Component(name, Status.BLOCKED, gaps=[f"no real membership build for {index_code}"]),
            None,
            [],
        )
    canon = next((b for b in builds if b.source_confidence == "CANONICAL"), None)
    build = canon or builds[0]
    ivs = _intervals(session, build.build_id)
    unresolved = sum(1 for i in ivs if i.identity_status != "RESOLVED")
    comp = Component(
        name,
        Status.READY,
        securities=len({i.security_id for i in ivs}),
        coverage_from=min((i.effective_from for i in ivs), default=None),
        coverage_to=max((i.effective_to or date.max for i in ivs), default=None),
        sources=[f"{build.membership_source} ({build.source_confidence})"],
    )
    if comp.coverage_to == date.max:
        comp.coverage_to = None  # open-ended: current
    if canon is None:
        comp.status = provisional_status
        comp.warnings.append(
            f"only {build.source_confidence} builds: not usable for final validation"
        )
    elif unresolved or not build.eligible_for_final_model_validation:
        comp.status = Status.PARTIAL
        comp.gaps.append(f"{unresolved}/{len(ivs)} interval(s) IDENTITY_UNRESOLVED")
    return comp, build, ivs


def _fundamentals_component(
    session: Session,
    name: str,
    provider: str,
    universe: list[IndexMembership],
    universe_ok: bool,
    min_coverage: float,
    synthetic: set[str],
) -> Component:
    src = session.scalars(select(DataSource).where(DataSource.name == provider)).first()
    if src is None:
        return Component(name, Status.BLOCKED, gaps=[f"no {provider} data ingested"])
    stmt = select(
        FundamentalFact.security_id,
        func.min(FundamentalFact.period_end),
        func.max(FundamentalFact.period_end),
    ).where(FundamentalFact.source_id == src.source_id)
    if provider == "SEC_EDGAR":
        stmt = stmt.where((FundamentalFact.cik.is_(None)) | (FundamentalFact.cik != FIXTURE_CIK))
    rows = [
        r
        for r in session.execute(stmt.group_by(FundamentalFact.security_id))
        if r[0] not in synthetic
    ]
    if not rows:
        return Component(name, Status.BLOCKED, gaps=[f"no real {provider} facts"])
    covered = {r[0] for r in rows}
    comp = Component(
        name,
        Status.PARTIAL,
        securities=len(covered),
        coverage_from=min(r[1] for r in rows),
        coverage_to=max(r[2] for r in rows),
        sources=[provider],
    )
    members = {i.security_id for i in universe}
    if not members or not universe_ok:
        comp.gaps.append("no canonical, identity-resolved universe to measure coverage against")
        return comp
    pct = len(members & covered) / len(members)
    if pct >= min_coverage:
        comp.status = Status.READY
    else:
        comp.gaps.append(f"{pct:.1%} of universe members have facts (need {min_coverage:.0%})")
    return comp


def _market_component(
    session: Session,
    name: str,
    exchange: str,
    accepted: list[str],
    synthetic: set[str],
) -> Component:
    rows = session.execute(
        select(
            DataSource.name,
            Price.security_id,
            func.min(Price.session_date),
            func.max(Price.session_date),
        )
        .join(DataSource, DataSource.source_id == Price.source_id)
        .join(Security, Security.security_id == Price.security_id)
        .where(Security.exchange == exchange, DataSource.is_synthetic.is_(False))
        .group_by(DataSource.name, Price.security_id)
    ).all()
    rows = [r for r in rows if r[1] not in synthetic]
    if not rows:
        return Component(name, Status.BLOCKED, gaps=[f"no real {exchange} prices (D-05 open)"])
    sources = sorted({r[0] for r in rows})
    comp = Component(
        name,
        Status.PARTIAL,
        securities=len({r[1] for r in rows}),
        coverage_from=min(r[2] for r in rows),
        coverage_to=max(r[3] for r in rows),
        sources=sources,
    )
    if accepted and set(sources) <= set(accepted):
        comp.status = Status.READY
    else:
        comp.gaps.append("provider not accepted by the D-05 contract suite (ADR pending)")
    return comp


def _corporate_actions_component(
    session: Session, accepted: list[str], synthetic: set[str]
) -> Component:
    names: Counter[str] = Counter()
    secs: set[str] = set()
    for model in (CorporateAction, Dividend):
        for src_name, sid in session.execute(
            select(DataSource.name, model.security_id)
            .join(DataSource, DataSource.source_id == model.source_id)
            .where(DataSource.is_synthetic.is_(False))
        ):
            if sid not in synthetic:
                names[src_name] += 1
                secs.add(sid)
    if not names:
        return Component(
            "Corporate actions", Status.BLOCKED, gaps=["no real corporate actions (D-05 open)"]
        )
    comp = Component(
        "Corporate actions", Status.PARTIAL, securities=len(secs), sources=sorted(names)
    )
    if accepted and set(names) <= set(accepted):
        comp.status = Status.READY
    else:
        comp.gaps.append("provider not accepted by the D-05 contract suite (ADR pending)")
    return comp


# ───────────────────────────── invariant scans ─────────────────────────────


def scan_pit(session: Session, settings: Settings) -> Scan:
    """Temporal invariants over real SEC data: facts never available before acceptance,
    every fact bound to a stored filing with matching acceptance, availability equal to the
    policy applied to the header acceptance."""
    cfg = settings.fundamentals.sec
    cal = get_calendar("XNYS")
    v: list[str] = []
    n = 0
    filings = {
        f.accession_number: f
        for f in session.scalars(select(SecFiling).where(SecFiling.cik != FIXTURE_CIK))
    }
    for f in filings.values():
        n += 1
        if f.available_at < f.accepted_at:
            v.append(f"filing {f.accession_number}: available_at < accepted_at")
        expected = filing_available_at(cal, f.accepted_at, f.availability_policy, cfg.lag_minutes)
        if f.availability_policy == cfg.availability_policy and f.available_at != expected:
            v.append(f"filing {f.accession_number}: available_at differs from policy")
    for fact in session.scalars(
        select(FundamentalFact).where(
            FundamentalFact.accession_number.is_not(None), FundamentalFact.cik != FIXTURE_CIK
        )
    ):
        n += 1
        filing = filings.get(fact.accession_number or "")
        if filing is None:
            v.append(f"fact {fact.fact_id}: accession {fact.accession_number} has no filing")
            continue
        if fact.accepted_at != filing.accepted_at or fact.available_at != filing.available_at:
            v.append(
                f"fact {fact.fact_id}: timestamps differ from filing {filing.accession_number}"
            )
        if fact.accepted_at is not None and fact.available_at < fact.accepted_at:
            v.append(f"fact {fact.fact_id}: available_at < accepted_at")
    return Scan("PIT validation", Check.FAIL if v else Check.PASS, n, v)


def scan_provenance(session: Session) -> Scan:
    """Every real filing has an archived header; every archive object exists on disk and
    re-hashes to its recorded SHA-256."""
    v: list[str] = []
    n = 0
    for f in session.scalars(select(SecFiling).where(SecFiling.cik != FIXTURE_CIK)):
        n += 1
        if session.get(RawSourceArchive, f.header_archive_id) is None:
            v.append(f"filing {f.accession_number}: header archive missing")
    seen: set[str] = set()
    for row in session.scalars(select(RawSourceArchive)):
        n += 1
        if row.sha256 in seen:
            continue
        seen.add(row.sha256)
        path = Path(row.storage_uri)
        if not path.exists():
            v.append(f"archive {row.archive_id}: object missing at {path}")
        elif sha256_hex(path.read_bytes()) != row.sha256:
            v.append(f"archive {row.archive_id}: SHA-256 mismatch")
    return Scan("Raw provenance", Check.FAIL if v else Check.PASS, n, v)


# ───────────────────────────── report ─────────────────────────────


def data_readiness(session: Session, settings: Settings) -> ReadinessReport:
    cfg = settings.data_readiness
    synthetic = _synthetic_security_ids(session)

    sp, sp_build, sp_ivs = _membership_component(
        session, "S&P membership", "SP500", Status.PROVISIONAL
    )
    ibex, ibex_build, ibex_ivs = _membership_component(
        session, "IBEX membership", "IBEX35", Status.PARTIAL
    )
    sec = _fundamentals_component(
        session,
        "SEC fundamentals",
        "SEC_EDGAR",
        sp_ivs,
        sp.status is Status.READY,
        cfg.min_universe_coverage,
        synthetic,
    )
    cnmv = _fundamentals_component(
        session,
        "CNMV fundamentals",
        "CNMV",
        ibex_ivs,
        ibex.status is Status.READY,
        cfg.min_universe_coverage,
        synthetic,
    )
    us = _market_component(
        session, "US market data", "XNYS", cfg.accepted_market_data_sources.get("US", []), synthetic
    )
    es = _market_component(
        session, "ES market data", "XMAD", cfg.accepted_market_data_sources.get("ES", []), synthetic
    )
    ca = _corporate_actions_component(session, cfg.accepted_corporate_action_sources, synthetic)
    components = [sec, cnmv, sp, ibex, us, es, ca]

    all_ivs = sp_ivs + ibex_ivs
    identity = (
        100.0 * sum(1 for i in all_ivs if i.identity_status == "RESOLVED") / len(all_ivs)
        if all_ivs
        else None
    )
    scans = [scan_pit(session, settings), scan_provenance(session)]

    issues = Counter(
        name
        for name, sid in session.execute(
            select(DataQualityIssue.check_name, DataQualityIssue.security_id).where(
                DataQualityIssue.resolved_at.is_(None)
            )
        )
        if sid not in synthetic
    )
    sec.warnings += [f"{k}: {n}" for k, n in sorted(issues.items())]

    provisional: list[str] = []
    definitive: list[str] = []
    for b in (sp_build, ibex_build):
        if b is not None:
            label = f"{b.index_code}:{b.membership_source}"
            (definitive if b.source_confidence == "CANONICAL" else provisional).append(label)
    for c in (sec, cnmv, us, es, ca):
        if c.status is Status.READY:
            definitive += c.sources
        elif c.sources:
            provisional += c.sources

    blockers = [
        f"{c.name}: {c.status} — {'; '.join(c.gaps) or 'see warnings'}"
        for c in components
        if c.critical and c.status is not Status.READY
    ] + [f"{s.name}: FAIL" for s in scans if s.result is Check.FAIL]
    if any(s.rows_checked == 0 for s in scans):
        blockers.append("invariant scans ran over zero real rows (vacuous PASS)")
    overall = (
        Status.READY
        if not blockers
        else (
            Status.BLOCKED
            if all(c.status is Status.BLOCKED for c in components)
            else Status.PARTIAL
        )
    )

    excluded = {
        "synthetic_securities": len(synthetic),
        "fixture_sec_filings": int(
            session.scalar(
                select(func.count()).select_from(SecFiling).where(SecFiling.cik == FIXTURE_CIK)
            )
            or 0
        ),
        "fixture_or_synthetic_builds": sum(
            1 for b in session.scalars(select(MembershipBuild)) if _is_fixture_build(b)
        ),
    }
    return ReadinessReport(
        overall,
        components,
        identity,
        scans,
        sorted(set(provisional)),
        sorted(set(definitive)),
        excluded,
        blockers,
    )
