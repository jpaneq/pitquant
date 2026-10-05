# ruff: noqa: E501
"""PIT FX for the return currency basis (ADR-0049). Source: Yahoo chart daily FX closes (VENDOR tier, ``CANONICAL_PROVIDER_FOR_PITQUANT``: methodological choice, not an official exchange source).

* Rates are stored as USD per 1 unit of currency. ``available_at`` of the quote of day d = 00:00 UTC of d+1: a rate is never used before the day it quotes has ended. Today's rate is never used for history.
* Lookup by INSTANT: the last rate with ``available_at <= instant``; older than ``MAX_STALE_DAYS`` => ``FX_STALE`` (no rate), a missing currency => ``FX_DATA_NOT_READY``.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models_research import FxRate
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider

SOURCE = "YAHOO_CHART:fx"
QUALITY = "CANONICAL_SOURCE"
MAX_STALE_DAYS = 7
QUOTES: dict[str, tuple[str, bool]] = {  # currency -> (Yahoo symbol, quoted as units of currency PER USD => invert)
    "EUR": ("EURUSD=X", False), "GBP": ("GBPUSD=X", False), "CHF": ("CHFUSD=X", False), "JPY": ("JPY=X", True),
    "CAD": ("CAD=X", True), "AUD": ("AUD=X", True), "DKK": ("DKK=X", True), "SEK": ("SEK=X", True),
}  # fmt: skip


def parse_chart(body: bytes, invert: bool) -> list[tuple[date, float]]:
    r = json.loads(body)["chart"]["result"][0]
    out: dict[date, float] = {}
    for ts, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"], strict=True):
        if c is None or c <= 0:
            continue
        d = datetime.fromtimestamp(ts, UTC).date()
        out[d] = (1.0 / c) if invert else float(c)
    bad = [d for d, v in out.items() if not 0.001 < v < 5.0]
    if bad:
        raise ValueError(f"implausible USD-per-unit rate on {bad[:3]}: wrong quote direction?")
    return sorted(out.items())


def ingest_fx(
    session: Session,
    store: ArchiveStore,
    since: date = date(2011, 1, 3),
    today: date | None = None,
    provider: Any = None,
) -> dict[str, str]:
    y = provider or YahooChartMarketDataProvider()
    today = today or datetime.now(UTC).date()
    res: dict[str, str] = {}
    for cur, (sym, inv) in QUOTES.items():
        have = {
            d
            for (d,) in session.execute(
                select(FxRate.rate_date).where(FxRate.currency == cur, FxRate.source == SOURCE)
            )
        }
        try:
            body, ident = y.download(sym, since, today)
            archive_document(
                session,
                store,
                provider=SOURCE,
                source_identifier=ident,
                data=body,
                mime_type="application/json",
                parser_version="fx-chart-1",
                notes="daily FX close; VENDOR tier; CANONICAL_PROVIDER_FOR_PITQUANT",
            )
            n = 0
            for d, v in parse_chart(body, inv):
                if d in have or d >= today:  # today's quote is not final
                    continue
                session.add(
                    FxRate(
                        currency=cur,
                        rate_date=d,
                        usd_per_unit=v,
                        quote_symbol=sym,
                        source=SOURCE,
                        source_tier="VENDOR",
                        quality_status=QUALITY,
                        available_at=datetime(d.year, d.month, d.day, tzinfo=UTC)
                        + timedelta(days=1),
                    )
                )
                n += 1
            res[cur] = f"OK inserted={n}"
        except Exception as exc:  # one pair failing must not hide the others
            res[cur] = f"FAILED: {exc}"
    session.flush()
    return res


@dataclass
class FxTable:
    """In-memory FX lookup (``usd_per_unit_at`` is the only way a research row gets a rate)."""

    series: dict[str, tuple[list[datetime], list[float], list[date]]]

    @classmethod
    def load(cls, session: Session) -> FxTable:
        rows: dict[str, list[tuple[datetime, float, date]]] = {}
        for r in session.scalars(
            select(FxRate).where(FxRate.source == SOURCE).order_by(FxRate.available_at)
        ):
            rows.setdefault(r.currency, []).append((r.available_at, r.usd_per_unit, r.rate_date))
        return cls(
            {c: ([x[0] for x in v], [x[1] for x in v], [x[2] for x in v]) for c, v in rows.items()}
        )

    def usd_per_unit_at(
        self, currency: str, instant: datetime
    ) -> tuple[float, date, datetime] | None:
        """(rate, rate_date, rate_available_at) known at ``instant``; None = ``FX_DATA_NOT_READY`` / ``FX_STALE``."""
        if instant.tzinfo is None:
            raise ValueError("naive datetime")
        if currency == "USD":
            return 1.0, instant.date(), instant
        s = self.series.get(currency)
        if not s:
            return None
        i = bisect_right(s[0], instant) - 1
        if i < 0 or (instant - s[0][i]).days > MAX_STALE_DAYS:
            return None
        return s[1][i], s[2][i], s[0][i]


def default_store(root: str) -> ArchiveStore:
    return ArchiveStore(Path(root))
