"""Load the SYNTHETIC market (tests, demos). Never used against a production database."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from pitquant.config.settings import Settings
from pitquant.data.providers.synthetic import END, START, SyntheticMarket
from pitquant.db.session import session_scope
from pitquant.jobs import ingest


def load_synthetic_market(
    factory: sessionmaker[Session],
    settings: Settings,
    *,
    start: date = START,
    end: date = END,
) -> dict[str, ingest.IngestReport]:
    m = SyntheticMarket(seed=settings.seed)
    out: dict[str, ingest.IngestReport] = {}
    with session_scope(factory) as s:
        out["securities"] = ingest.ingest_securities(s, m)
        out["membership_sp"] = ingest.ingest_memberships(s, m, "SYN_SP500")
        out["membership_ibex"] = ingest.ingest_memberships(s, m, "SYN_IBEX35")
        out["corporate_actions"] = ingest.ingest_corporate_actions(s, m, start, end)
        out["prices"] = ingest.ingest_prices(s, m, None, start, end)
        out["fundamentals"] = ingest.ingest_fundamentals(
            s, m, start, end, settings.pit.default_publication_lag_minutes
        )
    return out
