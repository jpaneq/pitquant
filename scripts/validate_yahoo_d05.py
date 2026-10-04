"""Validate archived Yahoo payloads and record verified corporate-action coverage."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import DataSource, Price, RawSourceArchive, Security
from pitquant.db.session import make_engine, make_session_factory
from pitquant.market.canonical import audit_series
from pitquant.market.exchanges import SUFFIX
from pitquant.market.pipeline import record_ca_ingestion
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
from pitquant.research.dataset_v1 import _ticker

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = get_settings()
    store = ArchiveStore(ROOT / cfg.archive.root)
    with make_session_factory(make_engine(cfg.database.url))() as s:
        securities = list(
            s.scalars(
                select(Security)
                .join(Price)
                .join(DataSource)
                .where(DataSource.name == "YAHOO_CHART:eod", Security.is_synthetic.is_(False))
                .distinct()
            )
        )
        by_symbol = {}
        failures = []
        for ar in s.scalars(
            select(RawSourceArchive)
            .where(RawSourceArchive.provider == "YAHOO_CHART:eod")
            .order_by(RawSourceArchive.retrieved_at)
        ):
            try:
                body = store.get(ar.sha256)
                result = json.loads(body)["chart"]["result"][0]
                symbol = result["meta"]["symbol"]
                params = parse_qs(urlparse(ar.source_identifier).query)
                if "split" not in params.get("events", [""])[0] or not params.get("period1"):
                    continue
                batch = YahooChartMarketDataProvider().normalize(symbol, symbol, body)
                if batch.bars:
                    by_symbol.setdefault(symbol, []).append((ar, batch))
            except Exception as e:
                failures.append({"archive_id": ar.archive_id, "reason": str(e)})
        for sec in securities:
            ticker = _ticker(s, sec.security_id)
            suffix = next(
                (suffix for suffix, (exchange, _, _) in SUFFIX.items() if exchange == sec.exchange),
                "",
            )
            symbol = ticker + ("." + suffix if suffix else "") if ticker else None
            stored = {
                p.session_date: p
                for p in s.scalars(
                    select(Price)
                    .join(DataSource)
                    .where(
                        Price.security_id == sec.security_id, DataSource.name == "YAHOO_CHART:eod"
                    )
                )
            }
            for ar, batch in by_symbol.get(symbol, []):
                dates = {b.session_date: b for b in batch.bars}
                if not stored or not (min(dates) <= min(stored) and max(dates) >= max(stored)):
                    continue
                same = all(
                    d in dates
                    and abs(stored[d].close - dates[d].close) <= 1e-7 * max(1, stored[d].close)
                    for d in stored
                )
                if not same:
                    failures.append(
                        {
                            "security_id": sec.security_id,
                            "archive_id": ar.archive_id,
                            "reason": "RAW_REBUILD_MISMATCH",
                        }
                    )
                    continue
                record_ca_ingestion(
                    s,
                    security_id=sec.security_id,
                    provider="YAHOO_CHART",
                    period_start=min(dates),
                    period_end=max(dates),
                    completed=True,
                    events_found=len(batch.actions),
                    source_hash=ar.sha256,
                    detail="yahoo-market-data-v1; SHA and deterministic reconstruction verified",
                )
                break
        s.commit()
        rows = [
            {
                **audit_series(s, sec),
                "ticker": _ticker(s, sec.security_id),
                "exchange": sec.exchange,
            }
            for sec in securities
        ]
        report = {
            "contract_version": "yahoo-market-data-v1",
            "securities": rows,
            "states": dict(Counter(r["status"] for r in rows)),
            "archive_failures": failures,
        }
        (ROOT / "docs/D05_YAHOO_QA.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"states": report["states"], "archives_failed": len(failures)}))


if __name__ == "__main__":
    main()
