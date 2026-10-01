"""AlphaVantageLifecycleQAProvider — QA ONLY (ADR-0021).

Cross-checks security lifecycle (active / delisted, listing and delisting dates) against
the ``LISTING_STATUS`` endpoint (CSV: symbol, name, exchange, assetType, ipoDate,
delistingDate, status; ``date`` and ``state=active|delisted`` parameters).

It NEVER supplies canonical prices, NEVER builds S&P membership and is never a primary
backtest source: its output is a list of discrepancies for a human/DQ queue. Without
``PITQUANT_ALPHAVANTAGE_API_KEY``: SOURCE_NOT_CONFIGURED.
"""

from __future__ import annotations

import csv
import io
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from pitquant.core.errors import DataQualityError
from pitquant.market.credentials import Credential, SourceStatus, redact
from pitquant.market.normalized import SecurityListing

ROLE = "QA_ONLY"
API = "https://www.alphavantage.co/query"
CREDENTIAL = Credential("PITQUANT_ALPHAVANTAGE_API_KEY")
COLUMNS = ("symbol", "name", "exchange", "assetType", "ipoDate", "delistingDate", "status")


@dataclass(frozen=True)
class LifecycleRow:
    symbol: str
    name: str
    exchange: str
    asset_type: str
    ipo_date: date | None
    delisting_date: date | None
    status: str


def parse_listing_status(payload: bytes) -> list[LifecycleRow]:
    rd = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    missing = [c for c in COLUMNS if c not in (rd.fieldnames or ())]
    if missing:
        raise DataQualityError(f"LISTING_STATUS: missing columns {missing}")

    def d(s: str) -> date | None:
        return date.fromisoformat(s) if s and s.lower() != "null" else None

    return [
        LifecycleRow(
            r["symbol"],
            r["name"],
            r["exchange"],
            r["assetType"],
            d(r["ipoDate"]),
            d(r["delistingDate"]),
            r["status"],
        )
        for r in rd
    ]


@dataclass
class AlphaVantageLifecycleQAProvider:
    fetch: Callable[[str], bytes] | None = None
    credential: Credential = CREDENTIAL
    role: str = ROLE

    def status(self) -> SourceStatus:
        return self.credential.status()

    def url(self, state: str, on: date | None = None) -> str:
        q = {"function": "LISTING_STATUS", "state": state, "apikey": self.credential.get()}
        if on is not None:
            q["date"] = on.isoformat()
        return API + "?" + urllib.parse.urlencode(q)

    def download(self, state: str, on: date | None = None) -> tuple[bytes, str]:
        if self.fetch is None:
            raise DataQualityError("no fetcher configured")
        u = self.url(state, on)
        return self.fetch(u), redact(u)

    @staticmethod
    def cross_check(
        ours: Sequence[SecurityListing], theirs: Sequence[LifecycleRow], tolerance_days: int = 3
    ) -> list[str]:
        """Discrepancies only (no data flows back). Matched by ticker AND overlapping life,
        since tickers are reused; listing/delisting dates must agree within tolerance."""
        by_symbol: dict[str, list[LifecycleRow]] = {}
        for t in theirs:
            by_symbol.setdefault(t.symbol.upper(), []).append(t)
        out: list[str] = []
        for s in ours:
            cands = by_symbol.get(s.ticker.upper(), [])
            if not cands:
                out.append(f"{s.ticker}: not in Alpha Vantage LISTING_STATUS")
                continue
            best = min(
                cands,
                key=lambda c: abs(
                    ((c.ipo_date or date.min) - (s.first_price_date or date.min)).days
                ),
            )
            if s.is_delisted != (best.status.lower() == "delisted"):
                out.append(f"{s.ticker}: delisted ours={s.is_delisted} theirs={best.status}")
            for ours_d, theirs_d, what in (
                (s.first_price_date, best.ipo_date, "listing"),
                (s.last_price_date if s.is_delisted else None, best.delisting_date, "delisting"),
            ):
                if ours_d and theirs_d and abs((ours_d - theirs_d).days) > tolerance_days:
                    out.append(f"{s.ticker}: {what} ours={ours_d} theirs={theirs_d}")
        return out
