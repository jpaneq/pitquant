"""Alpha Vantage ``TIME_SERIES_DAILY`` — raw (as-traded) daily OHLCV (ADR-0023).

Official documentation (archived by ``scripts/archive_adapter_docs.py``): «raw (as-traded)
daily time series (date, daily open, daily high, daily low, daily close, daily volume)»;
``outputsize=compact`` = latest 100 data points (free and premium), ``outputsize=full`` is
PREMIUM only. We never use ``TIME_SERIES_DAILY_ADJUSTED``: raw prices and corporate actions
stay separate. Not a canonical source; without ``PITQUANT_ALPHAVANTAGE_API_KEY`` →
``SOURCE_NOT_CONFIGURED`` (BLOCKED_BY_CREDENTIAL).

Error payloads (HTTP 200!) are refused, never parsed as empty data: ``Error Message``
(bad symbol), ``Note`` / ``Information`` (rate limit or premium endpoint).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.credentials import Credential, SourceStatus, redact
from pitquant.market.normalized import MarketBar, NormalizedBatch, Provenance, SourceTier
from pitquant.market.validation import calendar_status

PROVIDER = "ALPHAVANTAGE:TIME_SERIES_DAILY"
PARSER_VERSION = "alphavantage-daily-1"
API = "https://www.alphavantage.co/query"
CREDENTIAL = Credential("PITQUANT_ALPHAVANTAGE_API_KEY")
_FIELDS = ("1. open", "2. high", "3. low", "4. close", "5. volume")


@dataclass(frozen=True)
class DailyMeta:
    symbol: str
    last_refreshed: str
    output_size: str
    time_zone: str


def parse_daily(
    payload: bytes,
) -> tuple[DailyMeta, dict[date, tuple[float, float, float, float, float]]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise DataQualityError("Alpha Vantage: payload is not JSON") from e
    for k in ("Error Message", "Note", "Information"):
        if k in data:
            raise DataQualityError(f"Alpha Vantage refused the request ({k}): {str(data[k])[:160]}")
    meta, series = data.get("Meta Data"), data.get("Time Series (Daily)")
    if not isinstance(meta, dict) or not isinstance(series, dict) or not series:
        raise DataQualityError("Alpha Vantage: unexpected layout (no Meta Data / Time Series)")
    m = DailyMeta(
        str(meta.get("2. Symbol", "")),
        str(meta.get("3. Last Refreshed", "")),
        str(meta.get("4. Output Size", "")),
        str(meta.get("5. Time Zone", "")),
    )
    out: dict[date, tuple[float, float, float, float, float]] = {}
    for d, row in series.items():
        day = date.fromisoformat(d)
        if day in out:
            raise DataQualityError(f"Alpha Vantage: duplicate date {d}")
        try:
            o, h, lo, c, v = (float(row[f]) for f in _FIELDS)
        except (KeyError, ValueError) as e:
            raise DataQualityError(f"Alpha Vantage {d}: malformed row {row}") from e
        out[day] = (o, h, lo, c, v)
    return m, out


@dataclass
class AlphaVantageDailyProvider:
    fetch: Callable[[str], bytes] | None = None
    credential: Credential = CREDENTIAL

    def status(self) -> SourceStatus:
        return self.credential.status()

    def url(self, symbol: str, outputsize: str = "compact") -> str:
        q = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": self.credential.get(),
        }
        return API + "?" + urllib.parse.urlencode(q)

    def download(self, symbol: str, outputsize: str = "compact") -> tuple[bytes, str]:
        u = self.url(symbol, outputsize)
        body = self.fetch(u) if self.fetch is not None else _http_get(u)
        return body, redact(u)

    def normalize(
        self, security_key: str, payload: bytes, exchange: str = "XNYS"
    ) -> NormalizedBatch:
        meta, rows = parse_daily(payload)
        if meta.time_zone and meta.time_zone != "US/Eastern" and exchange == "XNYS":
            raise DataQualityError(f"Alpha Vantage time zone {meta.time_zone!r} != US/Eastern")
        cal = get_calendar(exchange)
        sha = sha256_hex(payload)
        out = NormalizedBatch()
        for day in sorted(rows):
            o, h, lo, c, v = rows[day]
            if (cs := calendar_status(cal, day)) != "ok":
                out.warnings.append(f"{day}: {cs} for {exchange} (bar not stored)")
                continue
            out.bars.append(
                MarketBar(
                    security_key,
                    day,
                    o,
                    h,
                    lo,
                    c,
                    v,
                    "USD",
                    cal.session_close(day),
                    Provenance(
                        PROVIDER, SourceTier.VENDOR, f"{meta.symbol}:{day}", sha, PARSER_VERSION
                    ),
                )
            )
        return out


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PITQuant research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body: bytes = r.read()
    return body
