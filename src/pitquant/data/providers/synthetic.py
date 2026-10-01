"""SYNTHETIC data provider — **NOT REAL MARKET DATA** (§97, ADR-0012).

Generates a deterministic, seeded micro-market whose only purpose is to exercise every
point-in-time edge case in tests and examples:

* a bankruptcy (SYNB) with a zero terminal value,
* a cash acquisition (SYNC acquired by SYNA),
* ticker reuse (SYNX used by two different securities, years apart),
* a ticker change (SYNE → SYNF),
* a 2-for-1 split and quarterly dividends (SYNA),
* fundamentals published with a lag, including a later restatement,
* two markets (XNYS, XMAD) with real calendars.

Index codes are ``SYN_SP500`` / ``SYN_IBEX35`` so they can never be confused with real
index history. All names start with "SYNTHETIC".
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from functools import cached_property
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from pitquant.core.hashing import content_hash
from pitquant.core.types import SYNTHETIC_SOURCE
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.providers.base import (
    CorporateActionRecord,
    CorporateActionsProvider,
    DividendRecord,
    FactRecord,
    FundamentalProvider,
    PriceBar,
    PriceProvider,
    ProviderInfo,
    SecurityProvider,
    SecurityRecord,
)
from pitquant.universe.events import (
    EventSource,
    EventType,
    IndexEventRecord,
    SourceConfidence,
)

NY = ZoneInfo("America/New_York")
MAD = ZoneInfo("Europe/Madrid")

START = date(2000, 1, 3)
END = date(2025, 12, 31)


def _ny(d: date, hh: int = 8, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=NY).astimezone(UTC)


_SECURITIES: list[dict[str, Any]] = [
    # key, name, exchange, ccy, listing_start, listing_end, delisting_reason, tickers, acquirer
    {
        "key": "S-A",
        "name": "SYNTHETIC Alpha Corp",
        "ex": "XNYS",
        "ccy": "USD",
        "start": START,
        "end": None,
        "reason": None,
        "tickers": [("SYNA", START, None)],
        "acq": None,
        "isin": "XS0000000001",
        "index": [("SYN_SP500", START, None, "founding member", None)],
    },
    {
        "key": "S-B",
        "name": "SYNTHETIC Bankrupt Inc",
        "ex": "XNYS",
        "ccy": "USD",
        "start": START,
        "end": date(2009, 3, 2),
        "reason": "bankruptcy",
        "tickers": [("SYNB", START, date(2009, 3, 3))],
        "acq": None,
        "isin": "XS0000000002",
        "index": [("SYN_SP500", START, date(2009, 2, 17), "founding member", "bankruptcy filing")],
    },
    {
        "key": "S-C",
        "name": "SYNTHETIC Target Co",
        "ex": "XNYS",
        "ccy": "USD",
        "start": START,
        "end": date(2015, 6, 30),
        "reason": "acquired",
        "tickers": [("SYNC", START, date(2015, 7, 1))],
        "acq": "S-A",
        "isin": "XS0000000003",
        "index": [
            ("SYN_SP500", date(2003, 3, 24), date(2015, 7, 1), "replaced S-X1", "acquired by S-A")
        ],
    },
    {
        "key": "S-X1",
        "name": "SYNTHETIC Old X Ltd",
        "ex": "XNYS",
        "ccy": "USD",
        "start": START,
        "end": date(2003, 3, 21),
        "reason": "merged",
        "tickers": [("SYNX", START, date(2003, 3, 24))],
        "acq": None,
        "isin": "XS0000000004",
        "index": [("SYN_SP500", START, date(2003, 3, 24), "founding member", "delisted")],
    },
    {
        "key": "S-X2",
        "name": "SYNTHETIC New X Holdings",
        "ex": "XNYS",
        "ccy": "USD",
        "start": date(2012, 5, 1),
        "end": None,
        "reason": None,
        "tickers": [("SYNX", date(2012, 5, 1), None)],
        "acq": None,
        "isin": "XS0000000005",
        "index": [("SYN_SP500", date(2015, 7, 1), None, "replaced S-C", None)],
    },
    {
        "key": "S-E",
        "name": "SYNTHETIC Echo plc",
        "ex": "XNYS",
        "ccy": "USD",
        "start": START,
        "end": None,
        "reason": None,
        "tickers": [("SYNE", START, date(2016, 9, 1)), ("SYNF", date(2016, 9, 1), None)],
        "acq": None,
        "isin": "XS0000000006",
        "index": [("SYN_SP500", START, None, "founding member", None)],
    },
    {
        "key": "S-M",
        "name": "SYNTHETIC Meseta SA",
        "ex": "XMAD",
        "ccy": "EUR",
        "start": START,
        "end": None,
        "reason": None,
        "tickers": [("SYNM", START, None)],
        "acq": None,
        "isin": "XS0000000007",
        "index": [("SYN_IBEX35", START, None, "founding member", None)],
    },
    {
        "key": "S-N",
        "name": "SYNTHETIC Norte SA",
        "ex": "XMAD",
        "ccy": "EUR",
        "start": START,
        "end": None,
        "reason": None,
        "tickers": [("SYNN", START, None)],
        "acq": None,
        "isin": "XS0000000008",
        "index": [
            ("SYN_IBEX35", START, date(2012, 6, 18), "founding member", "free-float review"),
            ("SYN_IBEX35", date(2018, 12, 24), None, "re-inclusion", None),
        ],
    },
]


class SyntheticMarket(
    SecurityProvider,
    PriceProvider,
    CorporateActionsProvider,
    FundamentalProvider,
):
    def __init__(self, seed: int = 20261001) -> None:
        self.seed = seed

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name=SYNTHETIC_SOURCE,
            is_synthetic=True,
            is_point_in_time=True,
            capabilities=frozenset({"prices", "index_events", "corporate_actions", "fundamentals"}),
        )

    # ── securities ─────────────────────────────────────────────────────────
    def securities(self) -> Sequence[SecurityRecord]:
        out = []
        for s in _SECURITIES:
            out.append(
                SecurityRecord(
                    provider_security_key=str(s["key"]),
                    name=str(s["name"]),
                    exchange=str(s["ex"]),
                    currency=str(s["ccy"]),
                    country="US" if s["ex"] == "XNYS" else "ES",
                    listing_start=s["start"],
                    listing_end=s["end"],
                    delisting_reason=s["reason"],
                    tickers=s["tickers"],
                    identifiers=[("ISIN", str(s["isin"]), START, None)],
                    acquirer_key=s["acq"],
                )
            )
        return out

    # ── membership ─────────────────────────────────────────────────────────
    def index_events(self, index_code: str) -> EventSource:
        """Event stream for a SYNTHETIC index (membership is derived, never loaded)."""
        events: list[IndexEventRecord] = []

        def ticker_on(s: dict[str, Any], d: date) -> str:
            return str(next(t for t, f, to in s["tickers"] if f <= d and (to is None or d < to)))

        for s in _SECURITIES:
            for idx, inc, exc, r_in, r_out in s["index"]:
                if idx != index_code:
                    continue
                key = str(s["key"])
                kind = EventType.INITIAL_SNAPSHOT if inc == START else EventType.INDEX_ADD
                events.append(
                    IndexEventRecord(
                        idx, kind, inc, f"{key}:{inc}:in", key, ticker_on(s, inc), reason=r_in
                    )
                )
                if exc is not None:
                    events.append(
                        IndexEventRecord(
                            idx,
                            EventType.INDEX_DELETE,
                            exc,
                            f"{key}:{exc}:out",
                            key,
                            ticker_on(s, exc - timedelta(days=1)),
                            reason=r_out,
                        )
                    )
            if index_code == "SYN_SP500":
                for (old, _f, to), (new, _nf, _nt) in zip(
                    s["tickers"], s["tickers"][1:], strict=False
                ):
                    if to is not None and s["key"] == "S-E":
                        events.append(
                            IndexEventRecord(
                                index_code,
                                EventType.TICKER_CHANGE,
                                to,
                                f"{s['key']}:{to}:ticker",
                                str(s["key"]),
                                old,
                                new_ticker=new,
                                reason="rename",
                            )
                        )
        return EventSource(
            membership_source="SYNTHETIC",
            confidence=SourceConfidence.SYNTHETIC,
            events=events,
            raw_source_hash=content_hash([e.__dict__ for e in events]),
        )

    # ── prices ─────────────────────────────────────────────────────────────
    @cached_property
    def _paths(self) -> dict[str, dict[date, tuple[float, float, float, float, float]]]:
        rng = np.random.default_rng(self.seed)
        paths: dict[str, dict[date, tuple[float, float, float, float, float]]] = {}
        for s in _SECURITIES:
            cal = get_calendar(str(s["ex"]))
            end = s["end"] or END
            sessions = cal.sessions(s["start"], end)
            n = len(sessions)
            drift = {"S-B": -0.0012}.get(str(s["key"]), 0.0003)
            rets = rng.normal(drift, 0.018, n)
            close = 40.0 * np.exp(np.cumsum(rets))
            gap = rng.normal(0, 0.004, n)
            open_ = close * np.exp(gap - rets)  # open near previous close
            hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
            lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
            vol = rng.lognormal(13, 0.4, n)
            bars = {
                d: (float(o), float(h), float(lw), float(c), float(v))
                for d, o, h, lw, c, v in zip(sessions, open_, hi, lo, close, vol, strict=True)
            }
            if s["key"] == "S-A":  # 2-for-1 split on 2014-06-09: raw prices halve from ex-date
                split = date(2014, 6, 9)
                bars = {
                    d: (b[0] / 2, b[1] / 2, b[2] / 2, b[3] / 2, b[4]) if d >= split else b
                    for d, b in bars.items()
                }
            paths[str(s["key"])] = bars
        return paths

    def bars(self, keys: Sequence[str], start: date, end: date) -> Sequence[PriceBar]:
        ccy = {str(s["key"]): str(s["ccy"]) for s in _SECURITIES}
        out = []
        for k in keys:
            for d, (o, h, lw, c, v) in sorted(self._paths.get(k, {}).items()):
                if start <= d <= end:
                    out.append(PriceBar(k, d, o, h, lw, c, v, ccy[k]))
        return out

    # ── corporate actions / dividends ──────────────────────────────────────
    def actions(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[CorporateActionRecord]:
        acts = [
            CorporateActionRecord(
                "S-A", "split", _ny(date(2014, 4, 23)), date(2014, 6, 9), ratio=2.0
            ),
            CorporateActionRecord(
                "S-C",
                "merger",
                _ny(date(2015, 2, 2)),
                date(2015, 6, 30),
                cash_amount=50.0,
                currency="USD",
                target_key="S-A",
                details={"consideration": "cash"},
            ),
            CorporateActionRecord(
                "S-B",
                "delisting",
                _ny(date(2009, 2, 13), 17),
                date(2009, 3, 2),
                cash_amount=0.0,
                currency="USD",
                details={"reason": "bankruptcy"},
            ),
        ]
        return [a for a in acts if a.provider_security_key in keys and start <= a.ex_date <= end]

    def dividends(self, keys: Sequence[str], start: date, end: date) -> Sequence[DividendRecord]:
        out = []
        if "S-A" in keys:
            cal = get_calendar("XNYS")
            for y in range(2005, 2026):
                for m in (2, 5, 8, 11):
                    ex = cal.session_on_or_after(date(y, m, 10))
                    if start <= ex <= end:
                        amt = 0.20 if ex < date(2014, 6, 9) else 0.10  # per post-split share
                        out.append(
                            DividendRecord("S-A", _ny(date(y, m, 1), 16, 30), ex, None, amt, "USD")
                        )
        return out

    # ── fundamentals ───────────────────────────────────────────────────────
    def facts(self, keys: Sequence[str], start: date, end: date) -> Sequence[FactRecord]:
        out: list[FactRecord] = []
        if "S-A" not in keys:
            return out
        rev = 1000.0
        for y in range(2005, 2025):
            for q, (pe_m, pe_d) in enumerate(((3, 31), (6, 30), (9, 30), (12, 31)), start=1):
                pe = date(y, pe_m, pe_d)
                if not (start <= pe <= end):
                    continue
                rev *= 1.015
                # Published ~5 weeks after quarter end, before the US open (aware timestamp).
                pub_day = date.fromordinal(pe.toordinal() + 36)
                published = _ny(pub_day, 7, 30)
                out.append(
                    FactRecord(
                        "S-A",
                        "revenue",
                        f"{y}Q{q}",
                        None,
                        pe,
                        round(rev, 2),
                        "currency",
                        "USD",
                        published,
                        0,
                        f"SYN-{y}Q{q}",
                    )
                )
        # A restatement of 2010Q4 revenue published a year later (revision 1).
        out.append(
            FactRecord(
                "S-A",
                "revenue",
                "2010Q4",
                None,
                date(2010, 12, 31),
                1111.0,
                "currency",
                "USD",
                _ny(date(2011, 11, 15), 16, 5),
                1,
                "SYN-2010Q4-A",
            )
        )
        return out
