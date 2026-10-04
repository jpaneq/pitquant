# ruff: noqa: E501
"""Price ingestion for the daily-routine universe (ADR-0042/0043). Every configured ticker is registered (price tracking only) and its daily bars, splits and dividends stored as normalised
VENDOR-tier records through the same pipeline the Analyzer uses. Source: EODHD when ``PITQUANT_EODHD_API_KEY`` is set, otherwise the FREE keyless Yahoo chart endpoint (unofficial, personal use,
see ``market/providers/yahoo.py``). A security that already has bars from ANOTHER source keeps them (no second source is mixed in). Nothing is invented: a failing ticker is reported.
A ticker is written ``SYMBOL`` (IBEX → ``.MC``; SP500/MSCI_WORLD → US) or ``SYMBOL.EXCH`` for another exchange.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models import DataSource, Price, SecurityProfile, TickerHistory
from pitquant.market.credentials import SourceStatus
from pitquant.market.pipeline import store_batch
from pitquant.market.providers.eodhd import EODHDMarketDataProvider
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
from pitquant.positions import routine as rt
from pitquant.security_master.service import SecurityMaster

BENCHMARKS = {
    "BENCHMARK": ["SPY"]
}  # the designated benchmark proxy of the Analyzer (relative strength, beta): ingested, never picked by the routine
EXCHANGE_OF_SUFFIX = {"MC": ("XMAD", "EUR", "ES"), "US": ("XNYS", "USD", "US")}
YAHOO_SOURCE = "YAHOO_CHART:eod"


def split_symbol(entry: str, market: str) -> tuple[str, str]:
    """('SAN', 'SAN.MC') for the IBEX list; an explicit suffix wins."""
    entry = entry.upper().strip()
    if "." in entry:
        return entry.rsplit(".", 1)[0], entry
    return entry, entry + rt.VENDOR_SUFFIX[market]


def find_security(session: Session, base: str) -> str | None:
    """The CURRENT security of a ticker: a ticker history row still valid, else a profile's current ticker. Retired rows (a ticker reused by another security) are never picked."""
    sid = session.scalars(
        select(TickerHistory.security_id)
        .where(TickerHistory.ticker == base, TickerHistory.valid_to.is_(None))
        .order_by(TickerHistory.valid_from.desc())
    ).first()
    if sid:
        return str(sid)
    sid = session.scalars(
        select(SecurityProfile.security_id).where(SecurityProfile.current_ticker == base)
    ).first()
    return str(sid) if sid else None


def ensure_security(session: Session, base: str, vendor_symbol: str) -> str:
    sid = find_security(session, base)
    if sid:
        return sid
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


def _sources_of(session: Session, sid: str) -> set[str]:
    return {
        str(n)
        for (n,) in session.execute(
            select(DataSource.name)
            .join(Price, Price.source_id == DataSource.source_id)
            .where(Price.security_id == sid)
            .distinct()
        )
    }


def ingest_universe(
    session: Session,
    settings: Settings,
    store: ArchiveStore,
    universe: dict[str, list[str]] | None = None,
    provider: Any = None,
    since: str = "2011-01-01",
) -> dict[str, Any]:
    """Per-ticker results. The provider is chosen once: the injected one, EODHD with a key, else Yahoo (free)."""
    eodhd = EODHDMarketDataProvider()
    if provider is not None:
        prov, source = (
            provider,
            ("YAHOO" if isinstance(provider, YahooChartMarketDataProvider) else "EODHD"),
        )
    elif eodhd.status() is not SourceStatus.SOURCE_NOT_CONFIGURED:
        prov, source = eodhd, "EODHD"
    else:
        prov, source = YahooChartMarketDataProvider(), "YAHOO"
    out: dict[str, str] = {}
    for market, entries in (
        {**(universe or rt.load_universe()), **(BENCHMARKS if universe is None else {})}
    ).items():
        for entry in entries:
            base, vendor = split_symbol(entry, market)
            try:
                sid = ensure_security(session, base, vendor)
                have = _sources_of(session, sid)
                if source == "YAHOO" and have and have != {YAHOO_SOURCE}:
                    out[entry] = (
                        f"SKIPPED: already has bars from {sorted(have)} (another source is not mixed in)"
                    )
                    continue
                first_day = date.fromisoformat(since)
                last = session.scalar(
                    select(func.max(Price.session_date)).where(Price.security_id == sid)
                )
                if last is not None and source == "YAHOO":
                    first_day = max(
                        first_day, last - timedelta(days=10)
                    )  # incremental: only the latest sessions
                today = utc_now().date()
                if source == "YAHOO":
                    body, red = prov.download(
                        vendor if "." in vendor and not vendor.endswith(".US") else base,
                        first_day,
                        today,
                    )
                    archive_document(
                        session,
                        store,
                        provider="YAHOO_CHART:eod",
                        source_identifier=red,
                        data=body,
                        mime_type="application/json",
                        parser_version="yahoo-chart-1",
                        notes="daily routine universe; VENDOR tier; unofficial, personal use",
                    )
                    batch = prov.normalize(
                        base, vendor if "." in vendor and not vendor.endswith(".US") else base, body
                    )
                    suffix = vendor.rsplit(".", 1)[-1] if not vendor.endswith(".US") else "US"
                else:
                    raw: dict[str, bytes] = {}
                    for ep in ("eod", "splits", "div"):
                        body, red = prov.download(
                            ep, vendor, **{"from": first_day.isoformat(), "to": today.isoformat()}
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
                    suffix = vendor.rsplit(".", 1)[-1]
                rep = store_batch(
                    session,
                    batch,
                    key_to_security={base: sid},
                    market=EXCHANGE_OF_SUFFIX.get(suffix, ("", "", "US"))[2],
                )
                out[entry] = f"OK bars={len(batch.bars)} inserted={rep.bars_inserted}" + (
                    f" ({len(batch.warnings)} warnings)" if batch.warnings else ""
                )
                session.commit()
            except (
                Exception
            ) as exc:  # one failing ticker never stops the others; the reason is reported
                session.rollback()
                out[entry] = f"FAILED: {str(exc)[:160]}"
    return {"status": "DONE", "source": source, "tickers": out}
