# ruff: noqa: E501
"""Price ingestion for the daily-routine universe (ADR-0042). With a vendor key (``PITQUANT_EODHD_API_KEY``) EVERY configured ticker is registered (price tracking only) and its daily bars,
splits and dividends stored as normalised VENDOR-tier records through the same pipeline the Analyzer uses. Without a key nothing is invented: the tickers stay ``NO_PRICE_DATA`` and the report says so.
A ticker is written ``SYMBOL`` (suffix by market: IBEX .MC, SP500/MSCI_WORLD .US) or ``SYMBOL.EXCH`` for another exchange (e.g. ``ASML.AS``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models import TickerHistory
from pitquant.market.credentials import SourceStatus
from pitquant.market.pipeline import store_batch
from pitquant.market.providers.eodhd import EODHDMarketDataProvider
from pitquant.positions import routine as rt
from pitquant.security_master.service import SecurityMaster

EXCHANGE_OF_SUFFIX = {"MC": ("XMAD", "EUR", "ES"), "US": ("XNYS", "USD", "US")}


def split_symbol(entry: str, market: str) -> tuple[str, str]:
    """('SAN', 'SAN.MC') for the IBEX list; an explicit suffix wins."""
    entry = entry.upper().strip()
    if "." in entry:
        base = entry.rsplit(".", 1)[0]
        return base, entry
    return entry, entry + rt.VENDOR_SUFFIX[market]


def ensure_security(session: Session, base: str, vendor_symbol: str) -> str:
    sid = session.scalars(
        select(TickerHistory.security_id).where(TickerHistory.ticker == base)
    ).first()
    if sid:
        return str(sid)
    suffix = vendor_symbol.rsplit(".", 1)[-1]
    exchange, currency, _ = EXCHANGE_OF_SUFFIX.get(suffix, ("XNYS", "USD", "US"))
    sm = SecurityMaster(session)
    sec = sm.register(
        name=f"{base} (daily routine: price tracking only)",
        exchange=exchange,
        currency=currency,
        listing_start=date(1990, 1, 1),
    )
    sm.add_ticker(sec.security_id, base, exchange, date(1990, 1, 1))
    return sec.security_id


def ingest_universe(
    session: Session,
    settings: Settings,
    store: ArchiveStore,
    universe: dict[str, list[str]] | None = None,
    provider: Any = None,
    since: str = "2011-01-01",
) -> dict[str, Any]:
    """Returns per-ticker results; ``SOURCE_NOT_CONFIGURED`` when there is no key (nothing is written)."""
    prov = provider or EODHDMarketDataProvider()
    if prov.status() is SourceStatus.SOURCE_NOT_CONFIGURED:
        return {
            "status": "SOURCE_NOT_CONFIGURED",
            "detail": "set PITQUANT_EODHD_API_KEY to ingest the whole universe",
            "tickers": {},
        }
    out: dict[str, str] = {}
    for market, entries in (universe or rt.load_universe()).items():
        for entry in entries:
            base, vendor = split_symbol(entry, market)
            try:
                sid = ensure_security(session, base, vendor)
                raw: dict[str, bytes] = {}
                for ep in ("eod", "splits", "div"):
                    body, red = prov.download(
                        ep, vendor, **{"from": since, "to": utc_now().date().isoformat()}
                    )
                    archive_document(
                        session,
                        store,
                        provider=f"EODHD:{ep}",
                        source_identifier=red,
                        data=body,
                        mime_type="application/json",
                        parser_version="routine-universe-1",
                        notes="daily routine universe; VENDOR tier",
                    )
                    raw[ep] = body
                batch = prov.normalize(base, vendor, raw["eod"], raw["splits"], raw["div"])
                rep = store_batch(
                    session,
                    batch,
                    key_to_security={base: sid},
                    market=EXCHANGE_OF_SUFFIX.get(vendor.rsplit(".", 1)[-1], ("", "", "US"))[2],
                )
                out[entry] = f"OK bars={len(batch.bars)} inserted={rep.bars_inserted}"
                session.commit()
            except (
                Exception
            ) as exc:  # one failing ticker never stops the others; the reason is reported
                session.rollback()
                out[entry] = f"FAILED: {str(exc)[:160]}"
    return {"status": "DONE", "tickers": out}
