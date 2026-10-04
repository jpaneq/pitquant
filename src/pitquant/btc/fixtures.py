"""Explicit SYNTHETIC BTC fixtures; only invoked by test/demo code, never the real archiver."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

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
