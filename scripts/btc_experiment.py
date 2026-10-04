"""Build the explicitly retrospective price baseline without opening the reserved holdout."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pitquant.btc.experimental import build_models  # noqa: E402
from pitquant.btc.providers import PublicProvider  # noqa: E402
from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402


def main() -> None:
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as session:
        provider = PublicProvider(session, ArchiveStore(ROOT / cfg.archive.root))
        # Fill the already identified gap with official archived originals. No holdout requests.
        start, end = datetime(2020, 5, 12, tzinfo=UTC), datetime(2024, 1, 10, tzinfo=UTC)
        while start < end:
            response = provider.spot(
                start_ms=int(start.timestamp() * 1000), end_ms=int(end.timestamp() * 1000) - 1
            )
            session.commit()
            if not response.latest:
                raise ValueError("BACKFILL_STOPPED_WITHOUT_DATA")
            latest = datetime.fromisoformat(response.latest)
            if latest <= start:
                raise ValueError("BACKFILL_DID_NOT_ADVANCE")
            start = latest
        # Retry observed missing days individually; absent upstream bars stay missing.
        for day in (datetime(2018, 2, 8, tzinfo=UTC), datetime(2023, 2, 6, tzinfo=UTC)):
            provider.spot(
                start_ms=int(day.timestamp() * 1000),
                end_ms=int((day + timedelta(days=1)).timestamp() * 1000) - 1,
            )
            session.commit()
        results = build_models(session)
        session.commit()
        summary = [{k: v for k, v in r.items() if k not in ("reg", "cls", "oos")} for r in results]
        (ROOT / "data/btc_experimental_report.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
