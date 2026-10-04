# ruff: noqa: E501
"""Command line: data-readiness, cohort-readiness, explain, universe, coverage, sec-ingest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
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


def _anchor_window(args: argparse.Namespace) -> int:
    """D-02 over the HISTORICAL ANCHOR GRAPH (ADR-0032): local segments, never the single current anchor."""
    from pitquant.universe.sp500_anchor_graph import graph_metrics, reconstruct

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        rep = reconstruct(
            session,
            date.fromisoformat(args.start),
            date.fromisoformat(args.end),
            standard=args.standard.upper(),
        )
    m = graph_metrics(rep)
    blocked = [c for c in rep.cohorts if c.status != "MEMBERSHIP_READY"]
    local = [
        s
        for s in rep.segments
        if s.status != "VALIDATED" and any(c.segment == f"{s.a.as_of}→{s.b.as_of}" for c in blocked)
    ]
    status = "READY" if rep.longest_run >= 60 else "BLOCKED_LOCAL_SEGMENTS"
    if args.json:
        print(
            json.dumps(
                {
                    **m,
                    "status": status,
                    "start": args.start,
                    "end": args.end,
                    "membership_ready": rep.ready,
                    "blocked": len(blocked),
                    "cohorts": [
                        {
                            "date": str(c.date),
                            "status": c.status,
                            "segment": c.segment,
                            "reasons": c.reasons,
                        }
                        for c in rep.cohorts
                    ],
                    "local_blocking_segments": [f"{s.a.as_of}→{s.b.as_of}" for s in local],
                },
                indent=2,
            )
        )
        return 0 if status == "READY" else 1
    print(f"window {args.start} → {args.end}  [{m['mode']}]  status: {status}")
    for k in (
        "verified_anchors",
        "segments",
        "validated_segments",
        "forward_validated_segments",
        "backward_validated_segments",
        "monthly_cohorts",
        "monthly_cohorts_reconstructible",
        "longest_continuous_period",
        "post_limit_events_used",
    ):
        print(f"  {k:<34} {m[k]}")
    print(f"  identity_ready                     {m['security_identity_resolution']}")
    print(f"  blocked cohorts                    {len(blocked)}")
    print(f"  local_blocking_segments            {len(local)}")
    for sg in local:
        kinds: dict[str, int] = {}
        for d in sg.deltas:
            kinds[d.difference_type] = kinds.get(d.difference_type, 0) + 1
        print(f"    {sg.a.as_of} → {sg.b.as_of}  {sg.status:<20} {kinds}")
    return 0 if status == "READY" else 1


def _window(args: argparse.Namespace) -> int:
    if not args.legacy:
        return _anchor_window(args)
    from pitquant.universe.sp500_window import window_readiness

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        rep = window_readiness(
            session, date.fromisoformat(args.start), date.fromisoformat(args.end)
        )
    if args.json:
        print(json.dumps(rep.as_dict(), indent=2, default=str))
        return 0 if rep.status == "READY" else 1
    print(f"window {rep.start} → {rep.end}   status: {rep.status}")
    print(f"  monthly_cohorts                         {rep.monthly_cohorts}")
    print(f"  reconstructible_cohorts (today)         {rep.reconstructible_cohorts}")
    print(f"  longest consecutive run (today)         {rep.longest_consecutive_run}")
    print(
        f"  HYPOTHETICAL with an anchor at the end  {rep.intrinsic_reconstructible_cohorts} cohorts, run {rep.intrinsic_longest_run}"
    )
    print(f"  first_failure                           {rep.first_failure}")
    print(f"  blocking events inside the window       {len(rep.blocking_events)}")
    print(
        f"  blocking events AFTER it (chain)        {rep.chain_blocking_events}  {rep.chain_blocking_by_year}"
    )
    print(f"  immaterial conflicts resolved (window)  {rep.immaterial_conflicts_in_window}")
    print(f"  blocking_identity (tickers w/o security){len(rep.blocking_identity):>5}")
    print(f"  holdout_overlap                         {rep.holdout_overlap}")
    by: dict[str, int] = {}
    for c in rep.blocking_events:
        by[f"{c.status}/{c.parser_status}"] = by.get(f"{c.status}/{c.parser_status}", 0) + 1
    for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"    {v:>4}  {k}")
    for n in rep.notes:
        print(f"  note: {n}")
    return 0 if rep.status == "READY" else 1


def _daily_test(args: argparse.Namespace) -> int:
    """Daily forward paper routine over several stocks: optional price refresh, then ONE forward tick at the server clock (idempotent per day; never back-dated)."""
    import subprocess

    from pitquant.strategy.daily import daily_test

    settings = get_settings()
    if args.refresh:
        # EOD refresh with the same script the Analyzer uses (idempotent; demo token = AAPL/MSFT only, a vendor key lifts that limit)
        script = Path(__file__).resolve().parents[2] / "scripts" / "ingest_analyzer_demo_data.py"
        subprocess.run([sys.executable, str(script)], check=True)
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    with make_session_factory(make_engine(settings.database.url))() as session:
        out = daily_test(session, settings, tickers)
        session.commit()
    print(
        json.dumps(out, indent=2, default=str)
        if args.json
        else f"{out['strategy']} · {len(out['universe'])} valores · decisiones nuevas {len(out['new_decisions'])} · {out['label']}"
    )
    return 0


def _routine_run(args: argparse.Namespace) -> int:
    """Daily simulated-buy routine: optional EOD refresh, one analysis per market, weekly evaluation, plain-text report file."""
    import subprocess

    from pitquant.positions.routine import evaluate_positions, run_daily
    from pitquant.positions.routine_report import build_report

    settings = get_settings()
    if args.refresh:
        script = Path(__file__).resolve().parents[2] / "scripts" / "ingest_analyzer_demo_data.py"
        subprocess.run([sys.executable, str(script)], check=True)
    with make_session_factory(make_engine(settings.database.url))() as session:
        ran = run_daily(session, settings) if not args.report_only else None
        evaluated = evaluate_positions(session, settings) if not args.report_only else None
        session.commit()
        text = build_report(session, settings)
    out = Path(args.out or "data/reports") / f"informe_rutina_{datetime.now(UTC).date()}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {"run": ran, "evaluation": evaluated, "report_file": str(out)}, indent=2, default=str
        )
    )
    if args.print_report:
        print(text)
    return 0


def _sim_update(args: argparse.Namespace) -> int:
    """Append-only event-log update of the active paper trades; idempotent (a second run without new bars appends 0 events)."""
    from datetime import UTC

    from pitquant.simulation import service as sim

    settings = get_settings()
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    if as_of is not None and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    with make_session_factory(make_engine(settings.database.url))() as session:
        results = sim.update_active(session, settings, as_of, args.simulation_id, commit=True)
    total = sum(r.new_events for r in results)
    out: dict[str, Any] = {
        "simulations": len(results),
        "new_events": total,
        "outcomes_created": sum(r.outcome_created for r in results),
        "failed": sum(r.status != "OK" for r in results),
        "bars_loaded": sum(r.bars_loaded for r in results),
        "bars_new": sum(r.bars_new for r in results),
        "events_new": total,
        "observations_new": sum(r.new_observations for r in results),
        "detail": [
            {
                "simulation_id": r.simulation_id,
                "status": r.status,
                "state": r.state,
                "new_events": r.new_events,
                "error": r.error,
            }
            for r in results
        ],
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(
            f"PAPER TRADING — NO REAL MONEY\nsimulations {out['simulations']}  new_events = {total}  outcomes_created {out['outcomes_created']}\nbars_loaded {out['bars_loaded']}  bars_new {out['bars_new']}  events_new {out['events_new']}  observations_new {out['observations_new']}"
        )
        for d in out["detail"]:
            print(
                f"  {d['simulation_id']}  {d['status']:<9} {d['state']:<20} +{d['new_events']}"
                + (f"  {d['error']}" if d["error"] else "")
            )
    return 1 if out["failed"] else 0


def _sim_replay(args: argparse.Namespace) -> int:
    """Rebuild the state from the T0 row + the event log ONLY (no market data) and compare it with the persisted outcome."""
    from pitquant.simulation import service as sim
    from pitquant.simulation.registry import EngineVersionUnavailable

    settings = get_settings()
    with make_session_factory(make_engine(settings.database.url))() as session:
        try:
            r = sim.replay_simulation(session, args.simulation_id)
        except EngineVersionUnavailable as e:
            print(f"ENGINE_VERSION_UNAVAILABLE\n  {e}")
            return 1
    if args.json:
        print(
            json.dumps(
                {
                    "match": r.match,
                    "differences": r.differences,
                    "n_events": r.n_events,
                    "engine_version": r.engine_version,
                    "event_schema_versions": list(r.event_schema_versions),
                    "folded": r.folded,
                },
                indent=2,
                default=str,
            )
        )
    elif r.match:
        print(
            f"MATCH\n  simulation_id {r.simulation_id}\n  engine_version {r.engine_version}  event_schema {','.join(map(str, r.event_schema_versions))}\n  events {r.n_events}  state {r.folded['state']}"
        )
    else:
        print(
            f"DIFFERENCES  (simulation {r.simulation_id}, engine {r.engine_version}, {r.n_events} events)"
        )
        for d in r.differences:
            print(f"  - {d}")
    return 0 if (r.match or not args.verify) else 1


def _tiingo_plan(args: argparse.Namespace) -> int:
    """Demand planning only: NO network, NO API key is read for any request."""
    from pitquant.market.providers.tiingo import CREDENTIAL
    from pitquant.universe.us_window_plan import backfill_plan

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        plan = backfill_plan(session, date.fromisoformat(args.start), date.fromisoformat(args.end))
    out = {"PITQUANT_TIINGO_API_KEY": CREDENTIAL.status().value, **plan.summary}
    if args.json:
        print(
            json.dumps(
                {**plan.as_dict(), "credential": out["PITQUANT_TIINGO_API_KEY"]},
                indent=2,
                default=str,
            )
        )
        return 0
    print(f"window {plan.start} → {plan.end}  cohorts {plan.cohorts}  [{plan.summary['label']}]")
    for k, v in out.items():
        if k not in ("label", "already_available_note", "free_plan_capacity"):
            print(f"  {k:<30} {v}")
    cap = plan.summary["free_plan_capacity"]
    print(
        f"  free_plan_capacity             {cap['monthly_unique_symbols']} symbols/month, {cap['daily_requests']} req/day, {cap['hourly_requests']} req/h → {cap['months_needed_for_symbols']} months for the symbols"
    )
    print(
        f"  ({plan.summary['already_available_note']}; capacity as encoded in TiingoBudget, not re-verified)"
    )
    return 0


def _window_dryrun(args: argparse.Namespace) -> int:
    from pitquant.data.calendars.market_calendar import get_calendar
    from pitquant.research.walkforward import WalkForwardConfig, dry_run, format_dry_run
    from pitquant.universe.us_window_plan import (
        backfill_plan,
        dataset_dry_run,
        fundamental_coverage,
    )

    settings = get_settings()
    ho = settings.validation.final_holdout
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        plan = backfill_plan(session, start, end)
        fund = fundamental_coverage(session, plan)
        rows, builder = dataset_dry_run(session, start, end, plan)
    ok = [f for f in fund if f.fundamental_months_possible > 0]
    print(f"[{plan.summary['label']}] window {start} → {end}")
    print(
        f"fundamentals: {len(ok)}/{len(fund)} candidate securities have SEC facts ({sum(f.fundamental_months_possible for f in ok)} security-months of {sum(f.membership_months for f in fund)})"
    )
    tot = {
        k: sum(getattr(r, k) for r in rows)
        for k in (
            "members",
            "identity_ready",
            "fundamentals_ready",
            "prices_ready",
            "corporate_actions_ready",
            "eligible",
        )
    }
    print(f"cohort-members: {tot}  over {len(rows)} cohorts")
    print(
        f"dataset builder (resolved securities only): {json.dumps(builder.get('summary', {}).get('blocking_reasons', {}))}"
    )
    cal = get_calendar("XNYS")
    ds = cal.first_sessions_of_months(start, end)
    for h in (6, 12):
        cfg = WalkForwardConfig(label_horizon_months=h, purge_months=1, embargo_months=1)
        folds = dry_run(ds, cfg, (ho.start, ho.end))
        print(
            f"\nwalk-forward {h}M (train_min {cfg.train_min_months}m, purge 1, embargo 1) PLAN ONLY, labels not consumed:"
        )
        print(format_dry_run(folds))
        print(
            f"holdout_overlap = {any(ho.start <= date.fromisoformat(str(r['validation_end'])) <= ho.end for r in folds)}"
        )
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
    wr = sub.add_parser(
        "sp500-window-readiness", help="exact blockers of a window of monthly S&P 500 cohorts"
    )
    wr.add_argument("--start", required=True, help="YYYY-MM-DD")
    wr.add_argument("--end", required=True, help="YYYY-MM-DD")
    wr.add_argument("--json", action="store_true")
    wr.add_argument(
        "--legacy", action="store_true", help="single-current-anchor reconstruction (superseded)"
    )
    wr.add_argument(
        "--standard",
        choices=["monthly", "daily"],
        default="monthly",
        help="monthly = Research Lab gate; daily = DAILY_CANONICAL",
    )
    wr.set_defaults(func=_window)
    tp = sub.add_parser("tiingo-backfill-plan", help="D-05 demand plan for a window (no API calls)")
    tp.add_argument("--start", default="2017-10-01")
    tp.add_argument("--end", default="2022-09-30")
    tp.add_argument("--json", action="store_true")
    tp.set_defaults(func=_tiingo_plan)
    su = sub.add_parser(
        "simulation-update", help="update the active paper trades from new bars (idempotent)"
    )
    su.add_argument("--simulation-id", default=None)
    su.add_argument("--as-of", default=None, help="ISO instant with offset (default: now)")
    su.add_argument("--json", action="store_true")
    su.set_defaults(func=_sim_update)
    dt = sub.add_parser(
        "strategy-daily-test",
        help="daily forward paper test of the Trade Plan rules over several stocks (no --as-of: server clock only)",
    )
    dt.add_argument(
        "--tickers",
        default=None,
        help="comma-separated; default = every security with enough price history (benchmark excluded)",
    )
    dt.add_argument(
        "--refresh",
        action="store_true",
        help="refresh EOD bars first (scripts/ingest_analyzer_demo_data.py)",
    )
    dt.add_argument("--json", action="store_true")
    dt.set_defaults(func=_daily_test)
    rr = sub.add_parser(
        "routine-run",
        help="daily simulated-buy routine (IBEX/SP500/MSCI World/BTC), weekly evaluation and a plain-text report",
    )
    rr.add_argument("--refresh", action="store_true", help="refresh EOD bars first")
    rr.add_argument(
        "--report-only",
        action="store_true",
        help="do not analyse or evaluate: only rebuild the report",
    )
    rr.add_argument("--print-report", action="store_true")
    rr.add_argument("--out", default=None, help="directory for the report (default data/reports)")
    rr.set_defaults(func=_routine_run)
    sr = sub.add_parser(
        "simulation-replay",
        help="rebuild a paper trade from T0 + events and compare (no market data)",
    )
    sr.add_argument("simulation_id")
    sr.add_argument("--verify", action="store_true", help="exit 1 unless the replay MATCHES")
    sr.add_argument("--json", action="store_true")
    sr.set_defaults(func=_sim_replay)
    wd = sub.add_parser(
        "us-window-dryrun", help="fundamental/dataset/walk-forward dry-run of a window"
    )
    wd.add_argument("--start", default="2017-10-01")
    wd.add_argument("--end", default="2022-09-30")
    wd.set_defaults(func=_window_dryrun)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
