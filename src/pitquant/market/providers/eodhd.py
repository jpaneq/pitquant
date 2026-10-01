"""EODHDMarketDataProvider — practical ES price source (and US fallback), ADR-0021.

Built from EODHD's public technical documentation (retrieved 2026-10-01):
* ``/api/eod/{SYMBOL.EXCHANGE}``: date, open/high/low/close «unadjusted», adjusted_close
  «adjusted for both splits and dividends», volume «adjusted for splits only». Delisted
  symbols keep their history; a RENAMED symbol returns an empty array (history moves to the
  new symbol) — so a ticker is never an identity.
* ``/api/div/{SYMBOL}``: date = ex-date, declarationDate, recordDate, paymentDate, period,
  value (split-adjusted to today's shares), unadjustedValue (actual payout), currency.
* ``/api/splits/{SYMBOL}``: date = ex-split date, split = "new/old".

Normalization: RAW OHLC as published; volume de-adjusted with the LATER splits and flagged
imputed; ``unadjustedValue`` is the dividend amount (``value`` kept in details for QA);
``adjusted_close`` QA only. EODHD is NOT a canonical source for complex Spanish actions
(rights issues, scrip, OPAs, mergers, exchanges): those come from the official BME/CNMV
layer (``CorporateAction.requires_official_source``). Without ``PITQUANT_EODHD_API_KEY``:
SOURCE_NOT_CONFIGURED.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pitquant.core.errors import DataQualityError
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

PROVIDER = "EODHD"
PARSER_VERSION = "eodhd-1"
API = "https://eodhd.com/api/{endpoint}/{symbol}"
CREDENTIAL = Credential("PITQUANT_EODHD_API_KEY")
CALENDAR = {"MC": "XMAD", "US": "XNYS"}
CURRENCY = {"MC": "EUR", "US": "USD"}

Fetch = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PITQuant research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body: bytes = r.read()
    return body


def _json(payload: bytes, what: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise DataQualityError(f"EODHD {what}: not JSON") from e
    if not isinstance(data, list):
        raise DataQualityError(f"EODHD {what}: expected a JSON array, got {type(data).__name__}")
    return data


def parse_split(s: str) -> float:
    try:
        new, old = (float(x) for x in s.split("/"))
    except ValueError as e:
        raise DataQualityError(f"EODHD split {s!r}: not 'new/old'") from e
    if new <= 0 or old <= 0:
        raise DataQualityError(f"EODHD split {s!r}: non-positive")
    return new / old


def _d(s: Any) -> date | None:
    return date.fromisoformat(str(s)[:10]) if s and str(s)[:4] != "0000" else None


@dataclass
class EODHDMarketDataProvider:
    fetch: Fetch = _http_get
    credential: Credential = CREDENTIAL

    def status(self) -> SourceStatus:
        return self.credential.status()

    def url(self, endpoint: str, symbol: str, **params: str) -> str:
        q = {"api_token": self.credential.get(), "fmt": "json", **params}
        return API.format(endpoint=endpoint, symbol=symbol) + "?" + urllib.parse.urlencode(q)

    def download(self, endpoint: str, symbol: str, **params: str) -> tuple[bytes, str]:
        u = self.url(endpoint, symbol, **params)
        return self.fetch(u), redact(u)

    @staticmethod
    def _prov(what: str, raw_id: str, sha: str) -> Provenance:
        return Provenance(f"{PROVIDER}:{what}", SourceTier.VENDOR, raw_id, sha, PARSER_VERSION)

    def normalize(
        self,
        security_key: str,
        symbol: str,
        eod: bytes,
        splits: bytes,
        dividends: bytes,
    ) -> NormalizedBatch:
        """``symbol`` = ``TICKER.EXCHANGE`` (e.g. ``ENG.MC``). ``security_key`` is OUR proven
        identity for that symbol over the requested window (the caller resolves it)."""
        exch = symbol.rsplit(".", 1)[-1]
        if exch not in CALENDAR:
            raise DataQualityError(f"EODHD exchange {exch!r} has no calendar mapping")
        cal = get_calendar(CALENDAR[exch])
        out = NormalizedBatch()
        sp_sha, dv_sha, eod_sha = sha256_hex(splits), sha256_hex(dividends), sha256_hex(eod)
        split_list: list[tuple[date, float]] = []
        for r in _json(splits, "splits"):
            d = _d(r.get("date"))
            if d is None:
                out.warnings.append(f"split without date {r}")
                continue
            ratio = parse_split(str(r["split"]))
            split_list.append((d, ratio))
            if ratio != 1:
                kind = CorporateActionKind.SPLIT if ratio > 1 else CorporateActionKind.REVERSE_SPLIT
                out.actions.append(
                    CorporateAction(
                        security_key,
                        kind,
                        cal.session_close(cal.session_on_or_after(d)),
                        self._prov("splits", f"{symbol}:{d}", sp_sha),
                        ex_date=d,
                        ratio=ratio,
                    )
                )
        for r in _json(dividends, "dividends"):
            ex = _d(r.get("date"))
            amount = r.get("unadjustedValue", r.get("value"))
            if ex is None or amount is None:
                out.warnings.append(f"dividend without ex-date/amount {r}")
                continue
            declared = _d(r.get("declarationDate"))
            period = str(r.get("period") or "")
            kind = (
                CorporateActionKind.SPECIAL_DIVIDEND
                if period.lower() == "special"
                else CorporateActionKind.CASH_DIVIDEND
            )
            # known when declared (vendor-stated) — else, conservatively, at the ex-date close
            known = (
                cal.session_close(cal.session_on_or_after(declared))
                if declared is not None and declared <= ex
                else cal.session_close(cal.session_on_or_after(ex))
            )
            out.actions.append(
                CorporateAction(
                    security_key,
                    kind,
                    known,
                    self._prov("div", f"{symbol}:{ex}", dv_sha),
                    announcement_date=declared,
                    ex_date=ex,
                    record_date=_d(r.get("recordDate")),
                    payment_date=_d(r.get("paymentDate")),
                    cash_amount=float(amount),
                    currency=str(r.get("currency") or CURRENCY[exch]),
                    details={"vendor_value_split_adjusted": r.get("value"), "period": period},
                )
            )
        for r in _json(eod, "eod"):
            d = _d(r.get("date"))
            close = r.get("close")
            if d is None or close is None or float(close) <= 0:
                out.warnings.append(f"EOD {symbol} {r.get('date')}: incomplete")
                continue
            later = 1.0
            for sd, ratio in split_list:
                if sd > d:
                    later *= ratio
            vol = r.get("volume")
            out.bars.append(
                MarketBar(
                    security_key=security_key,
                    session_date=d,
                    open=_opt(r.get("open")),
                    high=_opt(r.get("high")),
                    low=_opt(r.get("low")),
                    close=float(close),
                    volume=None if vol is None else float(vol) / later,
                    currency=CURRENCY[exch],
                    available_at=cal.session_close(cal.session_on_or_after(d)),
                    provenance=self._prov("eod", f"{symbol}:{d}", eod_sha),
                    vendor_adj_close=_opt(r.get("adjusted_close")),
                    imputed_fields=("volume",) if later != 1.0 else (),
                )
            )
        return out


def _opt(v: Any) -> float | None:
    return None if v is None or v == "" else float(v)
