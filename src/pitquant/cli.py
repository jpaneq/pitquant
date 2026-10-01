"""Command line: ``pitquant data-readiness`` and ``pitquant explain``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime

from pitquant.config.settings import get_settings
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
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
