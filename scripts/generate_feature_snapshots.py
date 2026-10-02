# ruff: noqa: E501
"""Real Feature Engine V0 snapshots for the SEC-registered securities (AAPL, MSFT), ADR-0027.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/generate_feature_snapshots.py

Monthly decision sessions (first NYSE session of each month), strictly BEFORE the sealed holdout.
These snapshots are NOT research-eligible: the securities are not in a complete cohort and their
price history is a short QA window, so every price feature outside it is NULL with a reason. They
exist to audit the engine on real SEC data. Idempotent (same content hash -> no new row).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.calendars.market_calendar import get_calendar  # noqa: E402
from pitquant.db.models import Security  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.features.v0.engine import FEATURE_NAMES, build_snapshot, persist_if_new  # noqa: E402

INELIGIBLE = (
    (
        "research_eligible",
        "warning",
        "false: not part of a complete research cohort (D-02/D-05 not ready); engine audit only",
    ),
)


def main() -> int:
    s = get_settings()
    ho = s.validation.final_holdout
    cal = get_calendar("XNYS")
    months = [
        d for d in cal.first_sessions_of_months(date(2015, 1, 1), date(2022, 9, 30)) if d < ho.start
    ]
    new = total = 0
    nonnull: list[int] = []
    with make_session_factory(make_engine(s.database.url))() as ses:
        for cik in ("0000320193", "0000789019"):
            sid = ses.scalars(
                select(Security.security_id).where(Security.name == f"CIK {cik} (SEC EDGAR)")
            ).one()
            for d in months:
                snap = build_snapshot(ses, sid, d, extra_warnings=INELIGIBLE)
                _, created = persist_if_new(ses, snap)
                new += int(created)
                total += 1
                nonnull.append(sum(v is not None for v in snap.features.values()))
        ses.commit()
    print(
        f"snapshots: {total} computed, {new} new; features per snapshot: {len(FEATURE_NAMES)}; non-null min/median/max = {min(nonnull)}/{sorted(nonnull)[len(nonnull) // 2]}/{max(nonnull)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
