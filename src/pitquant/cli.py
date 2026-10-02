# ruff: noqa: E501
"""Command line: data-readiness, cohort-readiness, explain, universe, coverage, sec-ingest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from typing import Any

from pitquant.config.settings import Settings, get_settings
from pitquant.data.providers.sec_edgar.provider import SECEdgarFundamentalProvider
from pitquant.db.session import make_engine, make_session_factory


def _readiness(args: argparse.Namespace) -> int:
    from pitquant.readiness import Status, data_readiness

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        rep = data_readiness(session, settings)
    from pitquant.research_readiness import research_readiness

    with factory() as session:
        rf = research_readiness(session, settings)
    if args.json:
        print(
            json.dumps(
                {
                    **rep.as_dict(),
                    "research": {
                        "flags": rf.flags,
                        "status": rf.status,
                        "reasons": rf.reasons,
                        "metrics": rf.metrics,
                    },
                },
                default=str,
                indent=2,
            )
        )
    else:
        print(rep.to_text())
        print()
        print(rf.to_text())
    return 0 if rep.overall is Status.READY else 1


def _explain(args: argparse.Namespace) -> int:
    from pitquant.audit.explain import explain_fact

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    as_of = datetime.fromisoformat(args.as_of)
    with factory() as session:
        ex = explain_fact(
            session,
            args.security_id,
            args.concept,
            date.fromisoformat(args.period_end),
            as_of,
            period_start=date.fromisoformat(args.period_start) if args.period_start else None,
            unit=args.unit,
        )
    print(ex.to_text())
    return 0


def _sec_provider(settings: Settings) -> SECEdgarFundamentalProvider:
    from pathlib import Path

    from pitquant.data.archive import ArchiveStore
    from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport

    cfg = settings.fundamentals.sec
    client = SECClient(UrllibTransport(), cfg.user_agent, cfg.max_requests_per_second)
    return SECEdgarFundamentalProvider(client, ArchiveStore(Path(settings.archive.root)), cfg)


def _sec_scan(args: argparse.Namespace) -> int:
    from pitquant.jobs.sec_ingest import scan_stress_cases

    settings = get_settings()
    provider = _sec_provider(settings)  # refuses without a contact User-Agent
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        for cik in args.ciks:
            scan = scan_stress_cases(
                cik,
                provider.submissions(session, cik),
                settings.fundamentals.sec.forms,
                settings.fundamentals.sec.coverage_start,
            )
            print(f"CIK {scan.cik}")
            for tag, accs in scan.by_tag.items():
                print(f"  {tag:<34} {len(accs):>4}  e.g. {', '.join(accs[:3])}")
            print(f"  missing: {', '.join(scan.missing) or '-'}")
        session.commit()  # the submissions documents were archived
    return 0


def _sec_ingest(args: argparse.Namespace) -> int:
    from pitquant.jobs.sec_ingest import ingest_ciks

    settings = get_settings()
    provider = _sec_provider(settings)
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        for rep in ingest_ciks(
            session, provider, settings, args.ciks, register_missing=args.register_missing
        ):
            print(rep)
    return 0


def _universe(args: argparse.Namespace) -> int:
    from pitquant.db.models import IndexEvent, IndexMembership
    from pitquant.security_master.service import SecurityMaster
    from pitquant.universe.index_membership import IndexUniverse

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    on = date.fromisoformat(args.date)
    with factory() as session:
        u, sm = IndexUniverse(session), SecurityMaster(session)
        build = u.active_build(args.index)
        members = u.universe(args.index, on)
        print(
            f"{args.index} @ {on}: {len(members)} members — build {build.build_id} "
            f"({build.membership_source}, {build.source_confidence}, eligible for final "
            f"validation: {build.eligible_for_final_model_validation})"
        )
        for m in members:
            iv = session.get_one(IndexEvent, m.source_event_id)
            row = (
                session.query(IndexMembership)
                .filter_by(build_id=build.build_id, source_event_id=m.source_event_id)
                .one()
            )
            print(
                f"  {sm.ticker_as_of(m.security_id, on) or '?':<6} {m.security_id}  "
                f"in since {m.effective_from} ({iv.reason})  identity={m.identity_status}  "
                f"source={iv.source_event_id} raw={row.raw_source_hash[:12]}"
            )
    return 0


def _coverage(args: argparse.Namespace) -> int:
    from pitquant.analyzer.eligibility import support_decision
    from pitquant.coverage import security_coverage

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        cov = security_coverage(
            session,
            args.security_id,
            date.fromisoformat(args.start),
            date.fromisoformat(args.end),
            benchmark_code=args.benchmark,
            accepted_ca_sources=settings.data_readiness.accepted_corporate_action_sources,
        )
    print(f"{cov.security_id} {cov.start}..{cov.end}: {cov.status}")
    for name, st, detail in cov.as_rows():
        print(f"  {name:<18} {st:<20} {detail}")
    dec = support_decision(cov)
    print(f"analyzer: {dec.status}" + (f" — {'; '.join(dec.reasons)}" if dec.reasons else ""))
    return 0


def _yn(b: bool) -> str:
    return "Y" if b else "-"


def _us_cohorts(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from pitquant.universe.sp500_cohorts import us_cohort_readiness

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        summ = us_cohort_readiness(session)
    d = summ.d02
    if args.json:
        print(
            json.dumps(
                {
                    "d02": {
                        "status": d.anchor_status,
                        "research_ready": d.d02_research_ready,
                        "longest_run": len(d.longest_run),
                    },
                    "layers": summ.layer_ready_counts,
                    "rows": [asdict(r) for r in summ.rows],
                },
                default=str,
                indent=2,
            )
        )
        return 0
    print(
        f"SP500 cohorts: {len(summ.rows)} month-start sessions; anchor {d.anchor_status} as of {d.anchor_as_of}"
    )
    print(
        f"  complete pre-holdout cohorts: {summ.complete_pre_holdout}; longest continuous proven run: {len(d.longest_run)} (D02 needs 60)"
    )
    print(f"  members per proven cohort: {summ.securities_per_cohort}")
    print(f"  layer-ready dates: {summ.layer_ready_counts}")
    if args.table:
        print("date       members memb ident fund  price ca    bench tr    holdout elig reasons")
        for r in summ.rows:
            print(
                f"{r.date} {r.n_members or '-':>7} {_yn(r.membership_ready):<4} {_yn(r.identity_ready):<5} {_yn(r.fundamentals_ready):<5} {_yn(r.prices_ready):<5} {_yn(r.corporate_actions_ready):<5} {_yn(r.benchmark_ready):<5} {_yn(r.total_return_ready):<5} {_yn(r.in_holdout):<7} {_yn(r.eligible):<4} {'; '.join(r.blocking_reasons[:2])}"
            )
    return 0


def _cohorts(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    if getattr(args, "universe", None) == "SP500":
        return _us_cohorts(args)

    from pitquant.cohorts import cohort_readiness

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        rows, summ = cohort_readiness(
            session,
            settings,
            args.index,
            start=date.fromisoformat(args.start) if args.start else None,
            end=date.fromisoformat(args.end) if args.end else None,
        )
    if args.json:
        print(
            json.dumps(
                {"summary": asdict(summ), "rows": [asdict(r) for r in rows]}, default=str, indent=2
            )
        )
        return 0
    first12 = (
        f"{summ.first_12_identity_cohorts[0]}..{summ.first_12_identity_cohorts[-1]}"
        if summ.first_12_identity_cohorts
        else None
    )
    print(f"{summ.index_code} cohorts (build {summ.build_id[:8]}): {summ.total_dates} dates")
    print(
        f"  identity-eligible: {summ.identity_eligible_dates}   "
        f"fully eligible: {summ.eligible_dates}"
    )
    print(f"  FIRST_IDENTITY_COHORT: {summ.first_identity_cohort}")
    print(f"  FIRST_CANONICAL_COHORT: {summ.first_canonical_cohort}")
    print(f"  first 12 consecutive identity cohorts: {first12}")
    print(
        f"  first complete identity year: {summ.first_complete_identity_year}   "
        f"full year: {summ.first_complete_year}"
    )
    print(f"  research identity dates (outside the sealed holdout): {summ.research_identity_dates}")
    print(f"  layer-ready dates: {summ.layer_ready_dates}")
    print(f"  blockers (dates): {summ.blockers}")
    if args.table:
        print("date       size resolved prices fundam. ca    id_ok elig  reasons")
        for r in rows:
            print(
                f"{r.date} {r.universe_size:>4} {r.resolved_identities:>8} "
                f"{r.price_coverage:>6.0%} {r.fundamental_coverage:>7.0%} "
                f"{r.corporate_action_coverage:>4.0%} {r.identity_eligible!s:<5} "
                f"{r.eligible!s:<5} {'; '.join(r.blocking_reasons[:3])}"
            )
    return 0


def _reconstruct(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from pitquant.reconstruct import reconstruct, to_text

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        rec = reconstruct(session, args.security, date.fromisoformat(args.date))
    print(json.dumps(asdict(rec), indent=2, default=str) if args.json else to_text(rec))
    return 0


def _sp500_evidence(args: argparse.Namespace) -> int:
    from collections import Counter

    from sqlalchemy import select

    from pitquant.db.models import RawSourceArchive, SP500MembershipEvent
    from pitquant.universe.sources.sp500_evidence import CANONICAL_STATUSES, EventStatus

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        run = session.scalars(
            select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
        ).first()
        discovery = session.scalars(
            select(RawSourceArchive.archive_id).where(
                RawSourceArchive.provider == "SP500_DISCOVERY:chinobing"
            )
        ).first()
        events = (
            session.scalars(
                select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == run)
            ).all()
            if run
            else []
        )
        from pitquant.db.models import IndexCurrentAnchor

        anchor = session.scalars(
            select(IndexCurrentAnchor.status)
            .where(IndexCurrentAnchor.index_code == "SP500")
            .order_by(IndexCurrentAnchor.ingested_at.desc())
        ).first()
    st = Counter(e.status for e in events)
    canon = sum(st[x.value] for x in CANONICAL_STATUSES)
    pct = 100 * canon / len(events) if events else 0.0
    print(f"SP500_MEMBERSHIP_DISCOVERY_READY = {str(discovery is not None).lower()}")
    print(f"SP500_MEMBERSHIP_EVIDENCE_COVERAGE = {pct:.1f}% ({canon}/{len(events)})")
    unresolved = len(events) - canon
    ready = anchor == "MULTI_SOURCE_CONFIRMED" and unresolved == 0 and bool(events)
    print(f"SP500_MEMBERSHIP_CANONICAL_READY = {str(ready).lower()}")
    state = anchor or "CURRENT_ANCHOR_BLOCKED"
    print(f"current anchor: {state}; statuses: {dict(st)}")
    _ = EventStatus
    return 0


def _explain_feature(args: argparse.Namespace) -> int:
    from pitquant.features.v0.explain import explain_feature

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        print(
            explain_feature(
                session,
                args.security,
                date.fromisoformat(args.date),
                args.feature,
                benchmark_ref=args.benchmark,
            )
        )
    return 0


def _research_dry_run(args: argparse.Namespace) -> int:
    """Plan walk-forward folds on calendar dates only: no data read, no model trained."""
    from pitquant.data.calendars.market_calendar import get_calendar
    from pitquant.research.walkforward import WalkForwardConfig, dry_run, format_dry_run

    cal = get_calendar("XNYS")
    first, last = date.fromisoformat(args.start), date.fromisoformat(args.end)
    ds, d = [], date(first.year, first.month, 1)
    while d <= last:
        ds.append(cal.session_on_or_after(d))
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    ho = get_settings().validation.final_holdout
    cfg = WalkForwardConfig(
        window_kind=args.window,
        purge_months=args.purge,
        embargo_months=args.embargo,
        label_horizon_months=args.horizon,
    )
    print(f"HOLDOUT SEALED {ho.start}..{ho.end} (never used) · {cfg}")
    print(format_dry_run(dry_run(ds, cfg, (ho.start, ho.end))))
    return 0


def _explain_panel(args: argparse.Namespace) -> int:
    from pitquant.analyzer.search import search
    from pitquant.analyzer.service import AnalyzerService
    from pitquant.core.timeutils import utc_now

    settings = get_settings()
    at = datetime.fromisoformat(args.as_of) if args.as_of else utc_now()
    if at.tzinfo is None:
        print("as_of must include a UTC offset", file=sys.stderr)
        return 2
    ho = settings.validation.final_holdout
    if ho.start <= at.date() <= ho.end:
        print("as_of is inside the sealed final holdout", file=sys.stderr)
        return 3
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        found: dict[str, Any] = search(session, args.security, limit=5)
        hits = [h for h in found["results"] if h["match_type"] in ("EXACT", "IDENTIFIER")]
        if len(hits) != 1:
            print(f"{args.security!r}: {len(hits)} exact matches", file=sys.stderr)
            return 2
        res = AnalyzerService(session, settings).explain(hits[0]["security_id"], at, args.panel)
    print(json.dumps(res, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pitquant")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("data-readiness", help="real-data readiness report (exit 1 unless READY)")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_readiness)
    e = sub.add_parser("explain", help="why a fundamental value was (not) known at an instant")
    e.add_argument("security_id")
    e.add_argument("concept")
    e.add_argument("period_end", help="YYYY-MM-DD")
    e.add_argument("as_of", help="ISO datetime WITH offset, e.g. 2024-12-31T16:00:00-05:00")
    e.add_argument("--period-start")
    e.add_argument("--unit")
    e.set_defaults(func=_explain)
    un = sub.add_parser("universe", help="index members at a date, with their provenance")
    un.add_argument("index")
    un.add_argument("date", help="YYYY-MM-DD")
    un.set_defaults(func=_universe)
    cv = sub.add_parser("coverage", help="data coverage of one security over a period")
    cv.add_argument("security_id")
    cv.add_argument("start", help="YYYY-MM-DD")
    cv.add_argument("end", help="YYYY-MM-DD")
    cv.add_argument("--benchmark")
    cv.set_defaults(func=_coverage)
    co = sub.add_parser("cohort-readiness", help="can each rebalance cohort be reconstructed?")
    co.add_argument("--index", default="IBEX35")
    co.add_argument("--universe", choices=["SP500"], help="US cohorts from the D-02 reconstruction")
    co.add_argument("--start")
    co.add_argument("--end")
    co.add_argument("--table", action="store_true", help="one line per date")
    co.add_argument("--json", action="store_true")
    co.set_defaults(func=_cohorts)
    rs = sub.add_parser(
        "reconstruct-security", help="information set of one security at a date (no features)"
    )
    rs.add_argument("security", help="security_id | dated ticker | CIK:<cik>")
    rs.add_argument("date", help="YYYY-MM-DD")
    rs.add_argument("--json", action="store_true")
    rs.set_defaults(func=_reconstruct)
    se = sub.add_parser("sp500-evidence", help="D-02 candidate: S&P 500 membership evidence states")
    se.set_defaults(func=_sp500_evidence)
    ef = sub.add_parser(
        "explain-feature", help="audit one feature value (inputs, formula, provenance)"
    )
    ef.add_argument("security", help="security_id | dated ticker | CIK:<cik>")
    ef.add_argument("date", help="decision session YYYY-MM-DD (NYSE)")
    ef.add_argument("feature")
    ef.add_argument("--benchmark", help="benchmark security for beta/relative features")
    ef.set_defaults(func=_explain_feature)
    sc = sub.add_parser("sec-stress-scan", help="pick stress-test filings from submissions")
    sc.add_argument("ciks", nargs="+")
    sc.set_defaults(func=_sec_scan)
    si = sub.add_parser("sec-ingest", help="ingest SEC EDGAR fundamentals for CIKs")
    si.add_argument("ciks", nargs="+")
    si.add_argument("--register-missing", action="store_true")
    si.set_defaults(func=_sec_ingest)
    rd = sub.add_parser("research-dry-run", help="walk-forward fold plan (no data, no training)")
    rd.add_argument("--start", default="2011-01-01")
    rd.add_argument("--end", default="2026-09-01")
    rd.add_argument("--window", choices=["EXPANDING", "ROLLING"], default="EXPANDING")
    rd.add_argument("--horizon", type=int, choices=[6, 12], default=6)
    rd.add_argument("--purge", type=int, default=1)
    rd.add_argument("--embargo", type=int, default=1)
    rd.set_defaults(func=_research_dry_run)
    for cmd, panel in (("explain-analysis", "analysis"), ("explain-trade-plan", "trade-plan")):
        xp = sub.add_parser(cmd, help=f"provenance of the {panel} panel")
        xp.add_argument("security", help="ticker | security_id | CIK:<cik>")
        xp.add_argument("--as-of", help="ISO datetime WITH offset (default now)")
        xp.set_defaults(func=_explain_panel, panel=panel)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
