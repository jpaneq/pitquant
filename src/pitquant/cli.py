"""Command line: data-readiness, explain, sec-stress-scan, sec-ingest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

from pitquant.config.settings import Settings, get_settings
from pitquant.data.providers.sec_edgar.provider import SECEdgarFundamentalProvider
from pitquant.db.session import make_engine, make_session_factory


def _readiness(args: argparse.Namespace) -> int:
    from pitquant.readiness import Status, data_readiness

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.database.url))
    with factory() as session:
        rep = data_readiness(session, settings)
    if args.json:
        print(json.dumps(rep.as_dict(), default=str, indent=2))
    else:
        print(rep.to_text())
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
                cik, provider.submissions(session, cik), settings.fundamentals.sec.forms
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
    sc = sub.add_parser("sec-stress-scan", help="pick stress-test filings from submissions")
    sc.add_argument("ciks", nargs="+")
    sc.set_defaults(func=_sec_scan)
    si = sub.add_parser("sec-ingest", help="ingest SEC EDGAR fundamentals for CIKs")
    si.add_argument("ciks", nargs="+")
    si.add_argument("--register-missing", action="store_true")
    si.set_defaults(func=_sec_ingest)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
