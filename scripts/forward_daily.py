"""Daily forward-learning cycle (ADR-0064): fresh prices -> exam once -> monthly refit ->
forecasts -> reviews of matured forecasts. Idempotent; safe to run several times a day.

    export PITQUANT_DATABASE_URL=sqlite+pysqlite:///data/pitquant.db
    .venv/bin/python scripts/forward_daily.py

``--no-ingest`` skips the downloads (Yahoo equities + funds, Binance BTC, SEC filings).
``--backfill-btc`` downloads every daily BTC candle since 2017 (first run only).
SEC filings (ADR-0066) need the SEC identification ("Name email") in the environment
``PITQUANT_SEC_USER_AGENT`` or in ``data/sec_user_agent.txt`` (not versioned); without it
that step is skipped and v3 keeps the fundamentals it already has.
No orders are ever opened.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "2"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.forward import funds  # noqa: E402
from pitquant.forward.learning import US_UNIVERSE, backfill_btc  # noqa: E402
from pitquant.forward.service import run_cycle  # noqa: E402


def ingest_sec(session: object, cfg: object, store: ArchiveStore) -> object:
    """New 10-K/10-Q filings of the US universe (already-known accessions are skipped)."""
    ua_file = Path("data/sec_user_agent.txt")
    if not os.environ.get("PITQUANT_SEC_USER_AGENT") and ua_file.exists():
        os.environ["PITQUANT_SEC_USER_AGENT"] = ua_file.read_text().strip()
    if not os.environ.get("PITQUANT_SEC_USER_AGENT"):
        return "SKIPPED: no SEC identification configured"
    from pitquant.cli import _sec_provider
    from pitquant.jobs.sec_universe import ingest_fundamentals

    try:
        res = ingest_fundamentals(session, cfg, _sec_provider(cfg), store, US_UNIVERSE)  # type: ignore[arg-type]
    except Exception as exc:  # a SEC outage never stops the forecasts
        return f"FAILED: {str(exc)[:160]}"
    return {t: r.get("status") for t, r in res.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-ingest", action="store_true")
    parser.add_argument("--backfill-btc", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)  # journal paths are stored relative to the repository root
    cfg = get_settings()
    store = ArchiveStore(Path(cfg.archive.root))
    result: dict[str, object] = {}
    with make_session_factory(make_engine(cfg.database.url))() as session:
        if not args.no_ingest:
            from pitquant.btc.providers import PublicProvider
            from pitquant.positions.universe_ingest import ingest_universe

            equities = ingest_universe(session, cfg, store, universe={"SP500": US_UNIVERSE})
            session.commit()
            tickers = equities.get("tickers", {})
            result["ingest_equity"] = {
                "ok": sum(str(v).startswith("OK") for v in tickers.values()),
                "failed": {k: v for k, v in tickers.items() if not str(v).startswith("OK")},
            }
            if args.backfill_btc:
                result["ingest_btc"] = backfill_btc(session, store)
            else:
                result["ingest_btc"] = PublicProvider(session, store).spot().status
                session.commit()
            result["ingest_funds"] = funds.ingest(session, store)
            result["ingest_sec"] = ingest_sec(session, cfg, store)
        result["cycle"] = run_cycle(
            session, Path("data/forward-pilots-v1"), train=True, learn=True, cfg=cfg
        )
        result["funds"] = funds.cycle(session)  # after the cycle: uses this month's champion
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
