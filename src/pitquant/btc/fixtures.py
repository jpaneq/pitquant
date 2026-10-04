"""Explicit SYNTHETIC BTC fixtures; only invoked by test/demo code, never the real archiver."""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort, digest
from pitquant.btc.models import BTCDatum
from pitquant.data.archive import ArchiveStore, archive_document

T0 = datetime(2026, 10, 4, tzinfo=UTC)


def load_synthetic_btc(session: Session, store_root: Path) -> None:
    raw = archive_document(
        session,
        ArchiveStore(store_root),
        provider="SYNTHETIC_BTC",
        source_identifier="fixture://btc-v0",
        data=b'{"kind":"SYNTHETIC_BTC"}',
        mime_type="application/json",
        retrieved_at=T0,
    )
    for n in range(-430, 43):
        at = T0 + timedelta(days=n)
        if n <= 0:
            o, h, low, c = 100.0, 101.0, 99.0, 100.0
        elif n == 1:
            o, h, low, c = 100.0, 102.0, 99.0, 101.0
        elif n == 2:
            o, h, low, c = 101.0, 105.0, 100.0, 104.0
        elif n == 3:
            o, h, low, c = 104.0, 109.0, 103.0, 108.0
        else:
            o, h, low, c = 108.0, 111.0, 107.0, 110.0
        payload = {"open": o, "high": h, "low": low, "close": c, "volume": 1000.0 + n % 10}
        session.add(
            BTCDatum(
                source="SYNTHETIC_BTC",
                metric="spot",
                cohort=Cohort.SYNTHETIC,
                exchange_timestamp=at,
                available_at=at,
                retrieved_at=at,
                payload=payload,
                raw_hash=raw.sha256,
                archive_id=raw.archive_id,
                value_hash=digest(payload),
            )
        )
    session.flush()


def synthetic_binance_fetch(now: datetime) -> Callable[[str, str, dict[str, Any]], Any]:
    """Binance-shaped responses for E2E/dev ONLY (PITQUANT_E2E_FIXTURE=1). Prices are SYNTHETIC TEST DATA, not market data."""
    day = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    d = 86_400_000
    now_ms = int(now.timestamp() * 1000)

    def kline(start: int, o: float, h: float, low: float, c: float) -> list[Any]:
        return [
            start,
            str(o),
            str(h),
            str(low),
            str(c),
            "300.0",
            start + d - 1,
            "0",
            4321,
            "0",
            "0",
            "0",
        ]

    def fetch(base: str, path: str, params: dict[str, Any]) -> Any:
        if path.endswith("/ticker/price"):
            return {"symbol": "BTCUSDT", "price": "11111.11"}
        if path.endswith("/ticker/24hr"):
            return {
                "symbol": "BTCUSDT", "priceChange": "111.00", "priceChangePercent": "1.01", "highPrice": "11500.00", "lowPrice": "10900.00",
                "volume": "222.5", "quoteVolume": "2470000.0", "openTime": now_ms - d, "closeTime": now_ms,
            }  # fmt: skip
        return [
            kline(day - 2 * d, 100, 105, 99, 101),
            kline(day - d, 101, 108, 100, 107),
            kline(day, 107, 109, 106, 108),
        ]

    return fetch
