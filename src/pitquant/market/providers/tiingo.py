"""TiingoEODMarketDataProvider — D-05 CANDIDATE evaluation (ADR-0024). Not canonical.

Endpoint (vendor documentation): ``GET /tiingo/daily/<ticker>/prices?startDate=&endDate=`` with
fields date, open, high, low, close, volume, adjOpen, adjHigh, adjLow, adjClose, adjVolume,
divCash, splitFactor; ``GET /tiingo/daily/<ticker>`` = meta (ticker, name, exchangeCode,
startDate, endDate). Per the vendor, the date of ``divCash`` is the ex-date.

* The token travels in the ``Authorization`` header, never in the URL, and only from
  ``PITQUANT_TIINGO_API_KEY`` (missing → SOURCE_NOT_CONFIGURED / BLOCKED_BY_CREDENTIAL).
* RAW ``open/high/low/close/volume`` are the base series. ``adj*`` fields are QA only
  (``vendor_adj_close``; ``adjustment_report``).
* ``divCash`` / ``splitFactor`` become corporate actions with tier VENDOR — never promoted to
  OFFICIAL; an official event always wins on disagreement (``ca_compare``).
* ``TiingoBudget`` stops BEFORE the free-tier limits are exceeded (50 requests/hour, 1000/day,
  500 unique symbols/month); time is injected so tests never sleep.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pitquant.core.errors import DataQualityError, PITQuantError
from pitquant.core.timeutils import require_aware, utc_now
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.credentials import Credential, SourceStatus, redact
from pitquant.market.normalized import (
    CorporateAction,
    CorporateActionKind,
    MarketBar,
    NormalizedBatch,
    Provenance,
    SourceTier,
)
from pitquant.market.validation import calendar_status

PROVIDER = "TIINGO:eod"
PARSER_VERSION = "tiingo-eod-1"
BASE = "https://api.tiingo.com/tiingo/daily"
CREDENTIAL = Credential("PITQUANT_TIINGO_API_KEY")
_REQUIRED = ("date", "open", "high", "low", "close", "volume")

Fetch = Callable[[str, Mapping[str, str]], bytes]


class BudgetExceededError(PITQuantError):
    """A free-tier limit would be exceeded: the request is NOT made."""


@dataclass
class TiingoBudget:
    hourly: int = 50
    daily: int = 1000
    monthly_symbols: int = 500
    calls: list[datetime] = field(default_factory=list)
    symbols: dict[str, set[str]] = field(default_factory=dict)  # "YYYY-MM" -> symbols

    def check_and_record(self, symbol: str, now: datetime) -> None:
        now = require_aware(now, "now")
        if sum(c > now - timedelta(hours=1) for c in self.calls) >= self.hourly:
            raise BudgetExceededError(f"hourly limit {self.hourly} reached")
        if sum(c > now - timedelta(days=1) for c in self.calls) >= self.daily:
            raise BudgetExceededError(f"daily limit {self.daily} reached")
        month = self.symbols.setdefault(now.strftime("%Y-%m"), set())
        if symbol not in month and len(month) >= self.monthly_symbols:
            raise BudgetExceededError(f"monthly unique-symbol limit {self.monthly_symbols} reached")
        self.calls.append(now)
        month.add(symbol)

    def used(self, now: datetime) -> dict[str, int]:
        return {
            "last_hour": sum(c > now - timedelta(hours=1) for c in self.calls),
            "last_day": sum(c > now - timedelta(days=1) for c in self.calls),
            "symbols_this_month": len(self.symbols.get(now.strftime("%Y-%m"), set())),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "calls": [c.isoformat() for c in self.calls],
                    "symbols": {k: sorted(v) for k, v in self.symbols.items()},
                }
            )
        )

    @classmethod
    def load(cls, path: Path) -> TiingoBudget:
        if not path.exists():
            return cls()
        d = json.loads(path.read_text())
        return cls(
            calls=[datetime.fromisoformat(c) for c in d["calls"]],
            symbols={k: set(v) for k, v in d["symbols"].items()},
        )


def _http_get(url: str, headers: Mapping[str, str]) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PITQuant research", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        body: bytes = r.read()
    return body


def parse_prices(payload: bytes) -> list[dict[str, Any]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise DataQualityError("Tiingo: payload is not JSON") from e
    if isinstance(data, dict):  # error payloads: {"detail": "..."}
        raise DataQualityError(f"Tiingo refused the request: {str(data.get('detail', data))[:160]}")
    if not isinstance(data, list):
        raise DataQualityError("Tiingo: expected a JSON array")
    seen: set[str] = set()
    for r in data:
        missing = [k for k in _REQUIRED if r.get(k) is None]
        if missing:
            raise DataQualityError(f"Tiingo row {r.get('date')}: missing {missing}")
        day = str(r["date"])[:10]
        if day in seen:
            raise DataQualityError(f"Tiingo: duplicate date {day}")
        seen.add(day)
    return data


@dataclass
class TiingoEODMarketDataProvider:
    fetch: Fetch = _http_get
    credential: Credential = CREDENTIAL
    budget: TiingoBudget = field(default_factory=TiingoBudget)
    clock: Callable[[], datetime] = utc_now

    def status(self) -> SourceStatus:
        return self.credential.status()

    def url(self, ticker: str, start: date, end: date | None = None, meta: bool = False) -> str:
        t = urllib.parse.quote(ticker.lower(), safe="")
        if meta:
            return f"{BASE}/{t}"
        q = {"startDate": start.isoformat(), "format": "json", "resampleFreq": "daily"}
        if end is not None:
            q["endDate"] = end.isoformat()
        return f"{BASE}/{t}/prices?{urllib.parse.urlencode(q)}"

    def download(
        self, ticker: str, start: date, end: date | None = None, *, meta: bool = False
    ) -> tuple[bytes, str]:
        """(raw bytes, URL safe to archive). The token is a header: it is never in the URL."""
        token = self.credential.get()
        self.budget.check_and_record(ticker.upper(), self.clock())
        u = self.url(ticker, start, end, meta)
        body = self.fetch(
            u, {"Authorization": f"Token {token}", "Content-Type": "application/json"}
        )
        return body, redact(u)

    def normalize(
        self, security_key: str, payload: bytes, exchange: str = "XNYS"
    ) -> NormalizedBatch:
        rows = parse_prices(payload)
        cal = get_calendar(exchange)
        sha = sha256_hex(payload)
        out = NormalizedBatch()
        for r in sorted(rows, key=lambda x: str(x["date"])):
            d = date.fromisoformat(str(r["date"])[:10])
            if (cs := calendar_status(cal, d)) != "ok":
                out.warnings.append(f"{d}: {cs} for {exchange} (bar not stored)")
                continue
            close_at = cal.session_close(d)
            prov = Provenance(
                PROVIDER, SourceTier.VENDOR, f"{security_key}:{d}", sha, PARSER_VERSION
            )
            out.bars.append(
                MarketBar(
                    security_key=security_key,
                    session_date=d,
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    volume=float(r["volume"]),
                    currency="USD",
                    available_at=close_at,
                    provenance=prov,
                    vendor_adj_close=_opt(r.get("adjClose")),
                )
            )
            div, split = float(r.get("divCash") or 0.0), float(r.get("splitFactor") or 1.0)
            ap = Provenance(PROVIDER, SourceTier.VENDOR, f"{security_key}:{d}", sha, PARSER_VERSION)
            if div > 0:  # vendor: the date of divCash is the ex-date. Known from the ex-date close.
                out.actions.append(
                    CorporateAction(
                        security_key,
                        CorporateActionKind.CASH_DIVIDEND,
                        close_at,
                        replace_raw(ap, f"div:{d}"),
                        ex_date=d,
                        cash_amount=div,
                        currency="USD",
                        details={"source_field": "divCash"},
                    )
                )
            if split != 1.0:
                out.actions.append(
                    CorporateAction(
                        security_key,
                        CorporateActionKind.SPLIT
                        if split > 1
                        else CorporateActionKind.REVERSE_SPLIT,
                        close_at,
                        replace_raw(ap, f"split:{d}"),
                        ex_date=d,
                        ratio=split,
                        details={"source_field": "splitFactor"},
                    )
                )
        return out


def replace_raw(p: Provenance, raw_id: str) -> Provenance:
    return Provenance(p.provider, p.tier, raw_id, p.source_hash, p.parser_version, p.archive_id)


def _opt(v: Any) -> float | None:
    return None if v is None or v == "" else float(v)


@dataclass
class AdjustmentReport:
    n_bars: int
    n_adjusted_days: int  # bars whose adjClose differs from the raw close
    last_bar_factor: float | None  # adjClose/close on the last bar (≈ 1 expected)
    max_abs_log_gap: float
    implied_factor_jumps: list[tuple[date, float]]  # days where the adjustment factor changes


def adjustment_report(payload: bytes, tol: float = 1e-6) -> AdjustmentReport:
    """Raw vs vendor-adjusted difference (QA only). A jump of adjClose/close between two
    consecutive bars marks a split or dividend adjustment in the vendor's own data."""
    import math

    rows = sorted(parse_prices(payload), key=lambda r: str(r["date"]))
    prev: float | None = None
    jumps: list[tuple[date, float]] = []
    adjusted = 0
    worst = 0.0
    last: float | None = None
    for r in rows:
        adj = _opt(r.get("adjClose"))
        if adj is None:
            continue
        f = adj / float(r["close"])
        last = f
        worst = max(worst, abs(math.log(f)))
        if abs(f - 1) > tol:
            adjusted += 1
        if prev is not None and abs(f / prev - 1) > 1e-4:
            jumps.append((date.fromisoformat(str(r["date"])[:10]), f / prev))
        prev = f
    return AdjustmentReport(len(rows), adjusted, last, worst, jumps)
