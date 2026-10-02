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
    CnmvFiling,
    CorporateAction,
    CorporateActionEvent,
    DataQualityIssue,
    DataSource,
    Dividend,
    FundamentalFact,
    IndexEvent,
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
    # v2: maturity / source / coverage detail
    maturity: list[str] = field(default_factory=list)  # CODE_READY, FIXTURE_TESTED, ...
    source_status: str = "NONE"  # SOURCE_CANONICAL | SOURCE_PROVISIONAL | NONE
    active: int | None = None
    delisted: int | None = None
    unresolved_identities: int = 0
    unresolved_events: int = 0
    source_version: str | None = None


# What the CODE can do (true independently of the database). An adapter that is CODE_READY
# and CONTRACT_TESTED does NOT make its source READY: only real data does.
_CODE = {
    "SEC fundamentals": ("CODE_READY", "CONTRACT_TESTED"),
    "CNMV fundamentals": ("CODE_READY", "CONTRACT_TESTED"),
    "US identity": ("CODE_READY",),
    "ES identity": ("CODE_READY", "CONTRACT_TESTED"),
    "ES identity (pre-2011, archival)": ("CODE_READY", "CONTRACT_TESTED"),
    "S&P membership": ("CODE_READY", "CONTRACT_TESTED"),
    "IBEX membership": ("CODE_READY", "CONTRACT_TESTED"),
    "US market adapter": ("CODE_READY", "CONTRACT_TESTED"),
    "ES market adapter": ("CODE_READY", "CONTRACT_TESTED"),
    "US real market data": ("CODE_READY", "CONTRACT_TESTED"),
    "ES real market data": ("CODE_READY", "CONTRACT_TESTED"),
    "Corporate actions": ("CODE_READY", "CONTRACT_TESTED"),
    "Total return engine": ("CODE_READY", "CONTRACT_TESTED"),
}


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
            out.append(
                f"      {' / '.join([c.source_status, *c.maturity])}"
                + (
                    f"  current={c.active} former_members={c.delisted}"
                    if c.active is not None
                    else ""
                )
                + f"  unresolved identities={c.unresolved_identities}"
                f" events={c.unresolved_events}"
                + (f"  version={c.source_version}" if c.source_version else "")
            )
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
    # normalized table (ADR-0021); FIXTURE-tier rows never count
    for prov, sid in session.execute(
        select(CorporateActionEvent.provider, CorporateActionEvent.security_id).where(
            CorporateActionEvent.source_tier != "FIXTURE"
        )
    ):
        if sid not in synthetic:
            names[prov] += 1
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


def _latest_parser(session: Session, provider: str) -> str | None:
    row = session.scalars(
        select(RawSourceArchive.parser_version)
        .where(RawSourceArchive.provider == provider)
        .order_by(RawSourceArchive.retrieved_at.desc())
    ).first()
    return row


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
    xmad = get_calendar("XMAD")
    for c in session.scalars(select(CnmvFiling)):
        n += 1
        latest = max(d for d in (c.publication_date, c.last_modification_date) if d is not None)
        if c.availability_precision == "DATE_ONLY" and c.effective_available_at != (
            xmad.date_only_available_at(latest)
        ):
            v.append(f"cnmv {c.nreg}: effective_available_at differs from the DATE_ONLY rule")
        if c.publication_time is not None and c.availability_precision == "DATE_ONLY":
            v.append(f"cnmv {c.nreg}: a time is stored but precision is DATE_ONLY")
    for cfact in session.scalars(
        select(FundamentalFact).where(FundamentalFact.cnmv_filing_id.is_not(None))
    ):
        n += 1
        cf = session.get(CnmvFiling, cfact.cnmv_filing_id)
        if cf is None or cfact.available_at != cf.effective_available_at:
            v.append(f"fact {cfact.fact_id}: availability differs from its CNMV filing")
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


def _us_identity_component(sp_build: MembershipBuild | None) -> Component:
    c = Component("US identity", Status.BLOCKED)
    if sp_build is None:
        c.gaps.append(
            "no S&P membership source to resolve against (S&P DJI file D-02; SHARADAR_SP500 "
            "candidate BLOCKED_BY_CREDENTIAL)"
        )
    c.warnings.append(
        "SEC issuers are identified by CIK (issuer level); share-class identity "
        "(CUSIP/permaticker) needs the D-05 security master"
    )
    return c


def _es_identity_components(
    session: Session, ibex_build: MembershipBuild | None, min_cov: float
) -> tuple[Component, Component]:
    from pitquant.security_master.identity_store import latest_run

    canon = Component("ES identity", Status.BLOCKED)
    pre = Component("ES identity (pre-2011, archival)", Status.BLOCKED, critical=False)
    run = latest_run(session, ibex_build.build_id) if ibex_build is not None else None
    if run is None:
        canon.gaps.append("no identity-resolution run for the IBEX build (ADR-0020)")
        pre.gaps.append("no identity-resolution run")
        return canon, pre
    for comp, key, label in (
        (canon, "canonical", "IBEX_IDENTITY_2011_PLUS"),
        (pre, "pre_canonical", "IBEX_IDENTITY_PRE_2011"),
    ):
        m = run.metrics.get(key, {})
        pct = float(m.get("coverage_percentage", 0.0))
        total = int(m.get("intervals_total", 0))
        dpct = m.get("date_coverage_percentage")
        comp.securities = int(m.get("resolved_exact", 0)) + int(m.get("resolved_multi_source", 0))
        comp.unresolved_identities = int(m.get("provisional", 0)) + int(m.get("unresolved", 0))
        # READY needs BOTH interval coverage and date-level (fail-closed) coverage
        dates_ok = dpct is None or float(dpct) / 100 >= min_cov
        comp.status = (
            Status.READY
            if total and pct / 100 >= min_cov and dates_ok
            else Status.PARTIAL
            if comp.securities
            else Status.BLOCKED
        )
        comp.source_status = "SOURCE_CANONICAL"  # CNMV ANCV official snapshots
        comp.source_version = (
            f"{label}: {pct:.1f}% of {total} intervals"
            + (
                f"; {m.get('dates_backtestable')}/{m.get('dates_total')} month-start dates "
                f"backtestable ({float(dpct):.1f}%)"
                if dpct is not None
                else ""
            )
            + f" (run {run.run_id[:8]})"
        )
        if dpct is not None and m.get("date_blockers"):
            comp.warnings.append(f"date blockers: {m.get('date_blockers')}")
        comp.maturity = [label]
        if comp.status is not Status.READY:
            comp.gaps.append(
                f"{label}: {m.get('provisional', 0)} provisional + {m.get('unresolved', 0)} "
                f"unresolved of {total} intervals (see docs/IBEX_COVERAGE_REPORT.md)"
            )
    return canon, pre


def _adapter_component(name: str) -> Component:
    """A finished adapter is CODE_READY + CONTRACT_TESTED; without a key it is
    BLOCKED_BY_CREDENTIAL. It never makes the SOURCE ready (see '... real market data')."""
    from pitquant.market.credentials import SourceStatus
    from pitquant.market.providers.alphavantage import CREDENTIAL as AV
    from pitquant.market.providers.eodhd import CREDENTIAL as EOD
    from pitquant.market.providers.sharadar import CREDENTIAL as SHR

    creds = {
        "US market adapter": [("SHARADAR", SHR), ("ALPHAVANTAGE(QA)", AV)],
        "ES market adapter": [("EODHD", EOD)],
    }[name]
    c = Component(name, Status.PARTIAL, critical=False)
    c.sources = [n for n, _ in creds]
    missing = [n for n, cr in creds if cr.status() is SourceStatus.SOURCE_NOT_CONFIGURED]
    if missing:
        c.status = Status.BLOCKED
        c.maturity.append("BLOCKED_BY_CREDENTIAL")
        c.gaps.append(f"SOURCE_NOT_CONFIGURED: {', '.join(missing)} (ADAPTER_CONTRACT_TESTED only)")
    else:
        c.gaps.append(
            "configured; REAL_DATA_FULLY_VALIDATED pending the contract suite on real data"
        )
    return c


def data_readiness(session: Session, settings: Settings) -> ReadinessReport:
    cfg = settings.data_readiness
    synthetic = _synthetic_security_ids(session)

    sp, sp_build, sp_ivs = _membership_component(
        session, "S&P membership", "SP500", Status.PROVISIONAL
    )
    ibex, ibex_build, ibex_ivs = _membership_component(
        session, "IBEX membership", "IBEX35", Status.PROVISIONAL
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
        session,
        "US real market data",
        "XNYS",
        cfg.accepted_market_data_sources.get("US", []),
        synthetic,
    )
    es = _market_component(
        session,
        "ES real market data",
        "XMAD",
        cfg.accepted_market_data_sources.get("ES", []),
        synthetic,
    )
    ca = _corporate_actions_component(session, cfg.accepted_corporate_action_sources, synthetic)
    us_id = _us_identity_component(sp_build)
    es_id, es_pre = _es_identity_components(session, ibex_build, cfg.min_universe_coverage)
    us_ad, es_ad = _adapter_component("US market adapter"), _adapter_component("ES market adapter")
    tr = Component(
        "Total return engine",
        Status.PARTIAL,
        critical=False,
        gaps=[
            "validated on FIXTURES (splits, dividends, special, spin-off, acquisitions, "
            "bankruptcy); real-data validation needs real prices"
        ],
    )
    sp.warnings.append(
        "candidate SHARADAR_SP500: ADAPTER_CONTRACT_TESTED, BLOCKED_BY_CREDENTIAL "
        "(not canonical; S&P DJI file stays the canonical target)"
    )
    components = [sec, cnmv, us_id, es_id, es_pre, sp, ibex, us_ad, es_ad, us, es, ca, tr]
    for c in components:
        c.maturity = list(_CODE[c.name]) + [m for m in c.maturity if m not in _CODE[c.name]]
        if c.securities:
            c.maturity.append("REAL_DATA_TESTED")
        if c.status is Status.PARTIAL:
            c.maturity.append("COVERAGE_PARTIAL")
        if c.status is Status.BLOCKED:
            c.maturity.append("BLOCKED")
    for c, b in ((sp, sp_build), (ibex, ibex_build)):
        if b is not None:
            c.source_status = (
                "SOURCE_CANONICAL" if b.source_confidence == "CANONICAL" else "SOURCE_PROVISIONAL"
            )
            c.source_version = f"build {b.build_id[:8]} ({b.membership_source})"
            c.unresolved_events = int(
                session.scalar(
                    select(func.count())
                    .select_from(IndexEvent)
                    .where(
                        IndexEvent.membership_source == b.membership_source,
                        IndexEvent.raw_source_hash == b.raw_source_hash,
                        IndexEvent.event_type == "INDEX_ADD",
                        IndexEvent.reason.like("UNRESOLVED_EVENT_TYPE%"),
                    )
                )
                or 0
            )
    sp.unresolved_identities = sum(1 for i in sp_ivs if i.identity_status != "RESOLVED")
    ibex.unresolved_identities = sum(1 for i in ibex_ivs if i.identity_status != "RESOLVED")
    if es_id.source_version:  # identity resolved by ADR-0020 segments, not in the code build
        ibex.unresolved_identities = es_id.unresolved_identities
        ibex.warnings.append(
            f"identity in code space: {sum(1 for i in ibex_ivs if i.identity_status != 'RESOLVED')}"
            f" intervals; resolved by ADR-0020 segments (2011+: {es_id.source_version})"
        )
    for c in (sec, cnmv):
        if c.securities:
            c.source_status = "SOURCE_CANONICAL"  # official filings (D-01 / D-04)
    sec.source_version = _latest_parser(session, "SEC_EDGAR")
    cnmv.source_version = _latest_parser(session, "CNMV")
    for c, ivs in ((sp, sp_ivs), (ibex, ibex_ivs)):
        if ivs:
            current = {i.security_id for i in ivs if i.effective_to is None}
            c.active = len(current)
            c.delisted = len({i.security_id for i in ivs} - current)  # left the INDEX
            c.warnings.append(
                "exchange delisting status of former members is UNKNOWN until D-05 market data"
            )
    for c in (us_ad, es_ad, tr):
        c.source_status = "NONE"
    for c in (us, es, ca):
        c.source_status = (
            "SOURCE_CANONICAL"
            if c.status is Status.READY
            else ("SOURCE_PROVISIONAL" if c.sources else "NONE")
        )

    for c in components:
        lab = {"SOURCE_CANONICAL": "CANONICAL", "SOURCE_PROVISIONAL": "PROVISIONAL"}.get(
            c.source_status
        )
        if lab and lab not in c.maturity:
            c.maturity.append(lab)

    # V1 canonical-period identity: S&P intervals (code build) + IBEX 2011+ (ADR-0020 run)
    sp_ok = sum(1 for i in sp_ivs if i.identity_status == "RESOLVED")
    es_total = es_id.securities + es_id.unresolved_identities
    denom = len(sp_ivs) + es_total
    identity = 100.0 * (sp_ok + es_id.securities) / denom if denom else None
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
    # By the NATURE of the source, not by component status: official filings (D-01/D-04)
    # are definitive even while coverage is partial; market data only once accepted by
    # the D-05 contract (config).
    definitive += sec.sources + cnmv.sources
    accepted = set(cfg.accepted_corporate_action_sources)
    for names in cfg.accepted_market_data_sources.values():
        accepted |= set(names)
    for c in (us, es, ca):
        for name in c.sources:
            (definitive if name in accepted else provisional).append(name)

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
            if all(c.status is Status.BLOCKED for c in components if c.critical)
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
