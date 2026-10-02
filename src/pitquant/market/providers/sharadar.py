"""Sharadar adapters (US market data and S&P 500 membership candidate) — ADR-0021.

Built from the OFFICIAL public schema (sharadar.com/docs: stocks, actions, tickers, sp500),
retrieved 2026-10-01. No subscription is needed to develop the interface; without
``PITQUANT_SHARADAR_API_KEY`` the source is ``SOURCE_NOT_CONFIGURED``.

Schema facts used (official docs):
* SEP (``stocks``): ticker, date, open/high/low/close «Split Adjusted», volume «Split
  Adjusted», closeadj «Adjusted for Splits Dividends and Spinoffs», closeunadj
  «Unadjusted», lastupdated.
* ACTIONS: date, action, ticker, name, value, contraticker, contraname; actions split,
  dividend, spinoff, spinoffdividend, acquisitionby/of, mergerfrom/to, delisted,
  tickerchangefrom/to, listed, bankruptcyliquidation, regulatory/voluntarydelisting,
  relation.
* TICKERS: permaticker = permanent id of a share class; tickers are REUSED after delisting.
* SP500: date, action, ticker, name, contraticker, contraname, note; actions current,
  historical, added, removed.

Normalization decisions (fail closed, nothing guessed):
* RAW base series: close = ``closeunadj``. Open/high/low/volume are only published
  split-adjusted: they are de-adjusted with the factor ``closeunadj / close`` and flagged
  ``imputed_fields``. ``closeadj`` is kept as ``vendor_adj_close`` (QA only).
* Tickers are reused, so every row is keyed by ``permaticker`` resolved from TICKERS by
  (ticker, date ∈ [firstpricedate, lastpricedate]); unresolvable or ambiguous → rejected.
* UNVERIFIED semantics (the official pages do not state them — see
  docs/ADAPTER_FIELD_EVIDENCE.md; to check against real data):
  whether dividend ``value`` is split-adjusted (sources disagree: recorded per row as
  ``value_basis=UNVERIFIED``), the direction of tickerchangefrom/to rows, and whether an
  SP500 ``date`` is the effective date. Acquisitions carry no consideration type, so they
  are normalized as MERGER + DelistingEvent(ACQUIRED), never as cash or stock.
"""

from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.credentials import Credential, SourceStatus, redact
from pitquant.market.normalized import (
    CorporateAction,
    CorporateActionKind,
    DelistingEvent,
    ListingEvent,
    MarketBar,
    NormalizedBatch,
    Provenance,
    SecurityListing,
    SourceTier,
    TickerEvent,
)

PROVIDER = "SHARADAR"
PARSER_VERSION = "sharadar-1"
API = "https://api.sharadar.com/v1.0/data/{table}"
CREDENTIAL = Credential("PITQUANT_SHARADAR_API_KEY")
PAGE_LIMIT = 10_000  # documented default/maximum rows per request

COLUMNS = {
    "stocks": (
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "closeadj",
        "closeunadj",
        "lastupdated",
    ),
    "actions": ("date", "action", "ticker", "name", "value", "contraticker", "contraname"),
    "sp500": ("date", "action", "ticker", "name", "contraticker", "contraname", "note"),
    "tickers": (
        "table",
        "permaticker",
        "ticker",
        "name",
        "exchange",
        "isdelisted",
        "category",
        "cusips",
        "firstpricedate",
        "lastpricedate",
        "currency",
        "lastupdated",
    ),
}
ACTION_CODES = frozenset(
    {
        "split",
        "dividend",
        "spinoff",
        "spinoffdividend",
        "acquisitionby",
        "acquisitionof",
        "mergerfrom",
        "mergerto",
        "delisted",
        "tickerchangefrom",
        "tickerchangeto",
        "listed",
        "bankruptcyliquidation",
        "regulatorydelisting",
        "voluntarydelisting",
        "relation",
    }
)

Fetch = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PITQuant research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body: bytes = r.read()
    return body


def parse_table(table: str, payload: bytes) -> list[dict[str, str]]:
    """CSV of one table. The header must contain every documented column (extra columns
    are allowed and ignored); otherwise the layout is unknown → fail closed."""
    text = payload.decode("utf-8-sig")
    if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        raise DataQualityError(f"sharadar {table}: HTML instead of CSV")
    rd = csv.DictReader(io.StringIO(text))
    have = set(rd.fieldnames or ())
    missing = [c for c in COLUMNS[table] if c not in have]
    if missing:
        raise DataQualityError(f"sharadar {table}: missing columns {missing}")
    return [dict(r) for r in rd]


def _d(s: str) -> date | None:
    return date.fromisoformat(s[:10]) if s and s.strip() else None


def _f(s: str) -> float | None:
    return float(s) if s and s.strip() else None


@dataclass
class TickerMaster:
    """(ticker, date) → permaticker from TICKERS rows of the SEP table."""

    rows: list[dict[str, str]]
    _by_ticker: dict[str, list[dict[str, str]]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        for r in self.rows:
            if r.get("table", "SEP") not in ("SEP", ""):
                continue
            self._by_ticker.setdefault(r["ticker"].upper(), []).append(r)

    def resolve(self, ticker: str, on: date) -> str:
        hits = []
        for r in self._by_ticker.get(ticker.upper(), []):
            a, b = _d(r["firstpricedate"]), _d(r["lastpricedate"])
            if a is not None and a <= on and (b is None or on <= b):
                hits.append(r["permaticker"])
        if len(set(hits)) != 1:
            why = "ambiguous" if hits else "unknown"
            raise DataQualityError(f"sharadar ticker {ticker}@{on}: {why} ({sorted(set(hits))})")
        return hits[0]

    def resolve_recent(self, ticker: str, on: date, max_days: int = 10) -> str:
        """The share class trading as ``ticker`` on ``on`` or, if none, the one whose LAST
        price date is the latest within ``max_days`` before ``on`` (a removal/delisting is
        often dated after the last trade). Still unique or it fails."""
        try:
            return self.resolve(ticker, on)
        except DataQualityError:
            pass
        best: list[tuple[date, str]] = []
        for r in self._by_ticker.get(ticker.upper(), []):
            b = _d(r["lastpricedate"])
            if b is not None and b <= on and (on - b).days <= max_days:
                best.append((b, r["permaticker"]))
        if not best:
            raise DataQualityError(f"sharadar ticker {ticker}@{on}: unknown")
        top = max(best)[0]
        keys = {k for d, k in best if d == top}
        if len(keys) != 1:
            raise DataQualityError(f"sharadar ticker {ticker}@{on}: ambiguous {sorted(keys)}")
        return keys.pop()


@dataclass
class SharadarMarketDataProvider:
    """US market data from Sharadar (preferred future vendor). Fundamentals stay SEC."""

    fetch: Fetch = _http_get
    credential: Credential = CREDENTIAL
    market: str = "US"

    def status(self) -> SourceStatus:
        return self.credential.status()

    def url(self, table: str, **params: str) -> str:
        q = {"api_key": self.credential.get(), "format": "csv", **params}
        return API.format(table=table) + "?" + urllib.parse.urlencode(q)

    def download(self, table: str, **params: str) -> tuple[bytes, str]:
        """ONE page: raw payload + the REDACTED url to archive it under (the key is never
        stored). A page with as many rows as the limit (default 10000, official docs) may be
        truncated: it is refused here — use ``download_all``."""
        u = self.url(table, **params)
        payload = self.fetch(u)
        limit = int(params.get("limit", PAGE_LIMIT))
        if "offset" not in params and len(parse_table(table, payload)) >= limit:
            raise DataQualityError(
                f"sharadar {table}: {limit} rows = page limit, result possibly truncated "
                "(use download_all)"
            )
        return payload, redact(u)

    def download_all(
        self, table: str, *, max_pages: int = 10_000, **params: str
    ) -> list[tuple[bytes, str]]:
        """Every page (``limit``/``offset``) until a short page. Each page is archived on its
        own; ``max_pages`` reached without a short page fails closed."""
        pages: list[tuple[bytes, str]] = []
        offset = 0
        for _ in range(max_pages):
            payload, stored = self.download(
                table, limit=str(PAGE_LIMIT), offset=str(offset), **params
            )
            pages.append((payload, stored))
            if len(parse_table(table, payload)) < PAGE_LIMIT:
                return pages
            offset += PAGE_LIMIT
        raise DataQualityError(f"sharadar {table}: no short page after {max_pages} pages")

    # ── normalization (no network) ────────────────────────────────────────────
    @staticmethod
    def _prov(table: str, raw_id: str, payload_sha: str) -> Provenance:
        return Provenance(
            f"{PROVIDER}:{table.upper()}", SourceTier.VENDOR, raw_id, payload_sha, PARSER_VERSION
        )

    def normalize_prices(
        self, payload: bytes, tickers: TickerMaster, batch: NormalizedBatch | None = None
    ) -> NormalizedBatch:
        out = batch or NormalizedBatch()
        sha = sha256_hex(payload)
        cal = get_calendar("XNYS")
        for r in parse_table("stocks", payload):
            day = _d(r["date"])
            close, raw = _f(r["close"]), _f(r["closeunadj"])
            if day is None or close is None or raw is None or close <= 0:
                out.warnings.append(f"SEP {r.get('ticker')} {r.get('date')}: incomplete row")
                continue
            try:
                key = tickers.resolve(r["ticker"], day)
            except DataQualityError as e:
                out.warnings.append(str(e))
                continue
            k = raw / close  # split factor applied by the vendor to this row

            def de(x: str, k: float = k) -> float | None:
                v = _f(x)
                return None if v is None else v * k

            vol = _f(r["volume"])
            out.bars.append(
                MarketBar(
                    security_key=f"SHARADAR:{key}",
                    session_date=day,
                    open=de(r["open"]),
                    high=de(r["high"]),
                    low=de(r["low"]),
                    close=raw,
                    volume=None if vol is None else vol / k,
                    currency="USD",
                    available_at=cal.session_close(cal.session_on_or_after(day)),
                    provenance=self._prov("stocks", f"{r['ticker']}:{r['date']}", sha),
                    vendor_adj_close=_f(r["closeadj"]),
                    vendor_last_updated=_d(r["lastupdated"]),
                    imputed_fields=("open", "high", "low", "volume") if abs(k - 1) > 1e-12 else (),
                )
            )
        return out

    def normalize_actions(
        self, payload: bytes, tickers: TickerMaster, batch: NormalizedBatch | None = None
    ) -> NormalizedBatch:
        out = batch or NormalizedBatch()
        sha = sha256_hex(payload)
        cal = get_calendar("XNYS")
        K = CorporateActionKind
        spin_value: dict[tuple[str, date], float] = {}
        rows = parse_table("actions", payload)
        for r in rows:
            if r["action"] == "spinoffdividend" and (d := _d(r["date"])) and (v := _f(r["value"])):
                spin_value[(r["ticker"].upper(), d)] = v
        changes_to: dict[tuple[str, date], str] = {}
        changes_from: dict[tuple[str, date], str] = {}
        for r in rows:
            act, day = r["action"].strip().lower(), _d(r["date"])
            if act not in ACTION_CODES:
                raise DataQualityError(f"sharadar ACTIONS: unknown action code {act!r}")
            if day is None:
                out.warnings.append(f"ACTIONS {r['ticker']} {act}: no date")
                continue
            if act == "tickerchangeto":
                changes_to[(r["ticker"].upper(), day)] = r["contraticker"].upper()
            elif act == "tickerchangefrom":
                changes_from[(r["ticker"].upper(), day)] = r["contraticker"].upper()
            if act in ("spinoffdividend", "relation", "tickerchangefrom", "tickerchangeto"):
                continue
            # an action on its own date: resolve with the last price date on/before it
            try:
                key = tickers.resolve(r["ticker"], day)
            except DataQualityError:
                try:
                    key = tickers.resolve(r["ticker"], _prev_day(day))
                except DataQualityError as e:
                    out.warnings.append(f"ACTIONS {act}: {e}")
                    continue
            sk = f"SHARADAR:{key}"
            prov = self._prov("actions", f"{r['ticker']}:{r['date']}:{act}", sha)
            # The vendor publishes after the session (no announcement date is given): the
            # record is known at the close of its own date at the earliest.
            avail = cal.session_close(cal.session_on_or_after(day))
            value = _f(r["value"])
            contra = r["contraticker"].upper() or None
            if act == "dividend" and value is not None:
                out.actions.append(
                    CorporateAction(
                        sk,
                        K.CASH_DIVIDEND,
                        avail,
                        prov,
                        ex_date=day,
                        cash_amount=value,
                        currency="USD",
                        details={"value_basis": "UNVERIFIED"},
                    )
                )
            elif act == "split" and value is not None and value != 1:
                kind = K.SPLIT if value > 1 else K.REVERSE_SPLIT
                out.actions.append(CorporateAction(sk, kind, avail, prov, ex_date=day, ratio=value))
            elif act == "spinoff":
                v = spin_value.get((r["ticker"].upper(), day))
                out.actions.append(
                    CorporateAction(
                        sk,
                        K.SPINOFF,
                        avail,
                        prov,
                        ex_date=day,
                        target_key=contra,
                        details={"value_per_share_usd": v, "ratio_vendor": value},
                    )
                )
            elif act in ("acquisitionby", "mergerto"):
                out.actions.append(
                    CorporateAction(
                        sk,
                        K.MERGER,
                        avail,
                        prov,
                        effective_date=day,
                        target_key=contra,
                        details={"consideration": "UNKNOWN", "vendor_action": act},
                    )
                )
                out.delistings.append(DelistingEvent(sk, day, "ACQUIRED", avail, prov, contra))
            elif act in ("bankruptcyliquidation",):
                out.actions.append(
                    CorporateAction(sk, K.BANKRUPTCY, avail, prov, effective_date=day)
                )
                out.delistings.append(DelistingEvent(sk, day, "BANKRUPTCY", avail, prov))
            elif act in ("delisted", "regulatorydelisting", "voluntarydelisting"):
                reason = {
                    "delisted": "OTHER",
                    "regulatorydelisting": "REGULATORY",
                    "voluntarydelisting": "VOLUNTARY",
                }[act]
                out.actions.append(
                    CorporateAction(
                        sk, K.DELISTING, avail, prov, effective_date=day, details={"reason": reason}
                    )
                )
                out.delistings.append(DelistingEvent(sk, day, reason, avail, prov))
            elif act == "listed":
                out.listings.append(ListingEvent(sk, day, None, avail, prov))
            elif act in ("acquisitionof", "mergerfrom"):
                pass  # the acquirer side: recorded on the target's row
        # ticker changes: both rows must agree (direction UNVERIFIED until real data)
        for (old, day), new in changes_to.items():
            if changes_from.get((new, day)) != old:
                out.warnings.append(f"ticker change {old}->{new} {day}: rows do not pair")
                continue
            try:
                key = tickers.resolve(old, _prev_day(day))
            except DataQualityError as e:
                out.warnings.append(f"ticker change {old}->{new}: {e}")
                continue
            prov = self._prov("actions", f"{old}:{day}:tickerchange", sha)
            avail = get_calendar("XNYS").session_close(
                get_calendar("XNYS").session_on_or_after(day)
            )
            out.tickers.append(TickerEvent(f"SHARADAR:{key}", old, new, day, avail, prov))
        return out

    def normalize_tickers(self, payload: bytes) -> tuple[TickerMaster, NormalizedBatch]:
        rows = parse_table("tickers", payload)
        sha = sha256_hex(payload)
        out = NormalizedBatch()
        for r in rows:
            if r.get("table", "SEP") not in ("SEP", ""):
                continue
            ids = {"CUSIP": c} if (c := r["cusips"].split(" ")[0] if r["cusips"] else "") else {}
            out.securities.append(
                SecurityListing(
                    f"SHARADAR:{r['permaticker']}",
                    r["ticker"],
                    r["name"],
                    r["exchange"] or None,
                    r["isdelisted"].strip().upper() == "Y",
                    _d(r["firstpricedate"]),
                    _d(r["lastpricedate"]),
                    r["currency"] or None,
                    ids,
                    self._prov("tickers", r["permaticker"], sha),
                    r["category"] or None,
                )
            )
        return TickerMaster(rows), out


def _prev_day(d: date) -> date:
    from datetime import timedelta

    return d - timedelta(days=1)


def flatten(batches: Iterable[NormalizedBatch]) -> NormalizedBatch:
    out = NormalizedBatch()
    for b in batches:
        out.bars += b.bars
        out.actions += b.actions
        out.listings += b.listings
        out.tickers += b.tickers
        out.delistings += b.delistings
        out.securities += b.securities
        out.warnings += b.warnings
    return out


def as_of_utc(d: date) -> datetime:
    return get_calendar("XNYS").session_close(d)


__all__: Sequence[str] = (
    "COLUMNS",
    "SharadarMarketDataProvider",
    "TickerMaster",
    "parse_table",
)
