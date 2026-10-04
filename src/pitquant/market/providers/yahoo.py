# ruff: noqa: E501
"""YahooChartMarketDataProvider — FREE, keyless daily bars from Yahoo Finance's unofficial chart endpoint (ADR-0043).

* UNOFFICIAL and without any SLA or licence for redistribution: personal/educational use for the daily simulation routine only. It remains VENDOR tier and is the canonical market price provider chosen by PITQuant (yahoo-market-data-v1); endpoint changes or rate limits can break it at any time, and every failure is reported, never hidden.
* Yahoo returns OHLC already SPLIT-ADJUSTED to today. Our series base is RAW OHLC, so prices are restored by multiplying by the product of the splits AFTER each bar (AAPL 2020-08-28:
  124.81 adjusted → 499.23 raw). Dividends are split-adjusted too: the actual payout is the amount times the later splits. Volume before a split is withheld (None): its adjustment is not verified.
* Only COMPLETED sessions are stored: a bar whose session has not closed (or is dated in the future) is dropped, so an intraday print is never persisted as a final bar.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.credentials import SourceStatus
from pitquant.market.exchanges import SUFFIX, suffix_of
from pitquant.market.normalized import (
    CorporateAction,
    CorporateActionKind,
    MarketBar,
    NormalizedBatch,
    Provenance,
    SourceTier,
)
from pitquant.market.validation import calendar_status

PROVIDER = "YAHOO_CHART"
PARSER_VERSION = "yahoo-market-data-v1"
API = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
Fetch = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (PITQuant personal research)"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data: bytes = r.read()
        return data


def redact_url(url: str) -> str:
    return url  # no credential in the URL


@dataclass
class YahooChartMarketDataProvider:
    fetch: Fetch = field(default=_http_get)

    def status(self) -> SourceStatus:
        return SourceStatus.CONFIGURED  # keyless

    def url(self, symbol: str, start: date, end: date) -> str:
        p1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
        p2 = int(datetime(end.year, end.month, end.day, tzinfo=UTC).timestamp()) + 86_400
        q = {
            "period1": p1,
            "period2": p2,
            "interval": "1d",
            "events": "div,split",
            "includeAdjustedClose": "true",
        }
        return API.format(symbol=urllib.parse.quote(symbol)) + "?" + urllib.parse.urlencode(q)

    def download(self, symbol: str, start: date, end: date) -> tuple[bytes, str]:
        u = self.url(symbol, start, end)
        return self.fetch(u), redact_url(u)

    @staticmethod
    def _prov(what: str, raw_id: str, sha: str) -> Provenance:
        return Provenance(f"{PROVIDER}:{what}", SourceTier.VENDOR, raw_id, sha, PARSER_VERSION)

    def normalize(
        self, security_key: str, symbol: str, body: bytes, now: datetime | None = None
    ) -> NormalizedBatch:
        now = now or datetime.now(UTC)
        try:
            doc = json.loads(body)
            result = doc["chart"]["result"][0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            err = (json.loads(body).get("chart") or {}).get("error") if body[:1] == b"{" else None
            raise DataQualityError(
                f"Yahoo chart response for {symbol} unusable: {err or exc}"
            ) from exc
        meta = result["meta"]
        timestamps = result.get("timestamp") or []
        if timestamps != sorted(set(timestamps)):
            raise DataQualityError("Yahoo duplicate or out-of-order timestamps")
        suffix = suffix_of(symbol)
        if suffix not in SUFFIX:
            raise DataQualityError(
                f"Yahoo symbol {symbol!r}: exchange suffix {suffix!r} has no calendar mapping (supported: {sorted(k for k in SUFFIX if k)})"
            )
        if meta.get("symbol") != symbol or not meta.get("currency"):
            raise DataQualityError("Yahoo identity/currency metadata missing or mismatched")
        cal = get_calendar(SUFFIX[suffix][0])
        gmt = int(meta.get("gmtoffset", 0))
        currency = str(meta.get("currency") or SUFFIX[suffix][1])
        sha = sha256_hex(body)
        out = NormalizedBatch()

        def local_day(ts: int) -> date:
            return (datetime.fromtimestamp(ts, UTC) + timedelta(seconds=gmt)).date()

        splits: list[tuple[date, float]] = []
        for ev in (result.get("events") or {}).get("splits", {}).values():
            num, den = float(ev["numerator"]), float(ev["denominator"])
            if num > 0 and den > 0 and num != den:
                splits.append((local_day(int(ev["date"])), num / den))
        splits.sort()
        for d, ratio in splits:
            out.actions.append(
                CorporateAction(
                    security_key,
                    CorporateActionKind.SPLIT if ratio > 1 else CorporateActionKind.REVERSE_SPLIT,
                    cal.session_close(cal.session_on_or_after(d)),
                    self._prov("splits", f"{symbol}:{d}", sha),
                    ex_date=d,
                    ratio=ratio,
                )
            )

        def later(d: date) -> float:
            f = 1.0
            for sd, r in splits:
                if sd > d:
                    f *= r
            return f

        for ev in (result.get("events") or {}).get("dividends", {}).values():
            ex = local_day(int(ev["date"]))
            amount = float(ev["amount"]) * later(
                ex
            )  # Yahoo amounts are split-adjusted: restore the actual payout
            out.actions.append(
                CorporateAction(
                    security_key, CorporateActionKind.CASH_DIVIDEND, cal.session_close(cal.session_on_or_after(ex)), self._prov("div", f"{symbol}:{ex}", sha), ex_date=ex, cash_amount=amount, currency=currency,
                    details={"vendor_value_split_adjusted": ev["amount"]},
                )
            )  # fmt: skip
        quote = (result.get("indicators") or {}).get("quote", [{}])[0]
        adj = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
        withheld = 0
        for i, ts in enumerate(result.get("timestamp") or []):
            d = local_day(int(ts))
            o, h, lo, c = (
                quote.get(k, [None] * (i + 1))[i] for k in ("open", "high", "low", "close")
            )
            if c is None or o is None or h is None or lo is None:
                continue  # holiday / incomplete row
            if not (0 < lo <= min(o, c) <= max(o, c) <= h):
                raise DataQualityError(f"Yahoo {symbol} {d}: invalid OHLC")
            status = calendar_status(cal, d)
            if status != "ok":
                out.warnings.append(f"YAHOO {symbol} {d}: {status} (bar not stored)")
                continue
            if cal.session_close(d) > now:
                out.warnings.append(f"YAHOO {symbol} {d}: session not closed yet (bar dropped)")
                continue  # an intraday print is never stored as a completed bar
            f = later(d)
            vol = quote.get("volume", [None] * (i + 1))[i]
            if f != 1.0 and vol is not None:
                withheld += 1
            out.bars.append(
                MarketBar(
                    security_key=security_key, session_date=d, open=float(o) * f, high=float(h) * f, low=float(lo) * f, close=float(c) * f, volume=None if (f != 1.0 or vol is None) else float(vol), currency=currency,
                    available_at=cal.session_close(d), provenance=self._prov("eod", f"{symbol}:{d}", sha), vendor_adj_close=float(adj[i]) if i < len(adj) and adj[i] else None, imputed_fields=("open", "high", "low", "close") if f != 1.0 else (),
                )
            )  # fmt: skip
        if withheld:
            out.warnings.append(
                f"YAHOO {symbol}: volume withheld on {withheld} bars before a split (volume adjustment not verified)"
            )
        return out
