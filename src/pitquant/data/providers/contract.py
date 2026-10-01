"""D-05 acceptance contract for market data + corporate actions providers.

No market-data provider becomes definitive because it is easy to integrate. A candidate is
wrapped in an adapter implementing :class:`ContractCandidate` and run against
:data:`pitquant.data.providers.contract_cases.CASES` — known historical events that a
survivorship-free, unadjusted, corporate-action-complete source must reproduce.

A candidate is ACCEPTED only when every case PASSES **and** every expectation it was
checked against is VERIFIED against an official source. Expectations written from memory
are ``UNVERIFIED`` and block acceptance until someone cites the official document.

Checks per category (see ``_check_*``):

* SPLIT / REVERSE_SPLIT — split action with the expected ratio near the ex-date, and the
  RAW bars around the ex-date show the price discontinuity (an adjusted series would not).
* SPECIAL_DIVIDEND — dividend typed special/extraordinary with the expected amount.
* SPIN_OFF — spin-off action pointing at the spun-off security with the expected ratio.
* CASH_ACQUISITION / STOCK_ACQUISITION — the target is still present (not dropped), has a
  listing end, and a merger/acquisition action with cash amount or exchange ratio.
* BANKRUPTCY / DELISTED — the security is present with a listing end and a delisting
  reason, its last bars exist, and a terminal value / delisting return is provided.
* RIGHTS_ISSUE / SCRIP_DIVIDEND — explicit action with ratio (and price/amount).
* TICKER_CHANGE — same provider key carries both symbols, switching on the change date.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from typing import Any, Protocol

from pitquant.data.providers.base import (
    CorporateActionRecord,
    DividendRecord,
    PriceBar,
    ProviderInfo,
    SecurityRecord,
)


class Category(StrEnum):
    DELISTED = "DELISTED"
    BANKRUPTCY = "BANKRUPTCY"
    CASH_ACQUISITION = "CASH_ACQUISITION"
    STOCK_ACQUISITION = "STOCK_ACQUISITION"
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    SPIN_OFF = "SPIN_OFF"
    SPECIAL_DIVIDEND = "SPECIAL_DIVIDEND"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    SCRIP_DIVIDEND = "SCRIP_DIVIDEND"
    TICKER_CHANGE = "TICKER_CHANGE"


class Verification(StrEnum):
    VERIFIED = "VERIFIED"  # checked against the cited official source
    UNVERIFIED = "UNVERIFIED"  # written from general knowledge: must be confirmed first


@dataclass(frozen=True)
class ContractCase:
    case_id: str
    market: str  # US | ES
    category: Category
    symbol: str  # symbol as quoted on ``symbol_on``
    symbol_on: date
    expect: dict[str, Any]  # category-specific (see module docstring)
    verification: Verification = Verification.UNVERIFIED
    source: str = ""  # official document that verifies ``expect`` (required if VERIFIED)
    note: str = ""
    tolerance_days: int = 5

    def __post_init__(self) -> None:
        if self.verification is Verification.VERIFIED and not self.source.startswith("http"):
            raise ValueError(f"{self.case_id}: VERIFIED requires an official source URL")


class ContractCandidate(Protocol):
    """Adapter a provider must implement to be evaluated."""

    @property
    def info(self) -> ProviderInfo: ...

    def security(self, symbol: str, on: date, market: str) -> SecurityRecord | None: ...

    def bars(self, keys: Sequence[str], start: date, end: date) -> Sequence[PriceBar]: ...

    def actions(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[CorporateActionRecord]: ...

    def dividends(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[DividendRecord]: ...


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: Category
    outcome: Outcome
    verification: Verification
    problems: tuple[str, ...] = ()


@dataclass
class ContractReport:
    provider: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.results if r.outcome is Outcome.FAIL]

    @property
    def unverified(self) -> list[CaseResult]:
        return [r for r in self.results if r.verification is Verification.UNVERIFIED]

    @property
    def accepted(self) -> bool:
        """Definitive acceptance: every case passes AND every expectation is verified."""
        return bool(self.results) and not self.failed and not self.unverified

    def summary(self) -> str:
        lines = [
            f"D-05 contract — {self.provider}: "
            f"{'ACCEPTED' if self.accepted else 'NOT ACCEPTED'} "
            f"({len(self.results) - len(self.failed)}/{len(self.results)} pass, "
            f"{len(self.unverified)} unverified expectation(s))"
        ]
        for r in self.results:
            lines.append(f"  {r.outcome:<4} {r.verification:<10} {r.case_id} ({r.category})")
            lines += [f"         - {p}" for p in r.problems]
        return "\n".join(lines)


# ───────────────────────────── checks ─────────────────────────────


def _near(d: date | None, target: date, tol: int) -> bool:
    return d is not None and abs((d - target).days) <= tol


def _close(a: float | None, b: float, rel: float = 1e-3) -> bool:
    return a is not None and abs(a - b) <= rel * max(1.0, abs(b))


def _window(c: ContractCase, key: str) -> tuple[date, date]:
    d: date = c.expect[key]
    return d - timedelta(days=40), d + timedelta(days=40)


def _actions(
    cand: ContractCandidate, sec: SecurityRecord, c: ContractCase, key: str, types: set[str]
) -> list[CorporateActionRecord]:
    lo, hi = _window(c, key)
    return [
        a
        for a in cand.actions([sec.provider_security_key], lo, hi)
        if a.action_type.lower() in types
    ]


def _check_split(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    p: list[str] = []
    ex: date = c.expect["ex_date"]
    ratio: float = c.expect["ratio"]
    hits = [
        a
        for a in _actions(cand, sec, c, "ex_date", {"split", "reverse_split"})
        if _near(a.ex_date, ex, c.tolerance_days) and _close(a.ratio, ratio)
    ]
    if not hits:
        p.append(f"no split action with ratio {ratio} near {ex}")
    lo, hi = ex - timedelta(days=10), ex + timedelta(days=10)
    bars = sorted(cand.bars([sec.provider_security_key], lo, hi), key=lambda b: b.session_date)
    before = [b for b in bars if b.session_date < ex]
    after = [b for b in bars if b.session_date >= ex]
    if not before or not after:
        p.append("no raw bars around the ex-date")
    else:
        jump = before[-1].close / after[0].close
        if not (0.65 * ratio <= jump <= 1.5 * ratio):
            p.append(
                f"bars around ex-date move x{jump:.3f}, expected ~x{ratio}: prices look "
                "adjusted (raw unadjusted OHLCV required)"
            )
    return p


def _check_special_dividend(
    cand: ContractCandidate, sec: SecurityRecord, c: ContractCase
) -> list[str]:
    lo, hi = _window(c, "ex_date")
    hits = [
        d
        for d in cand.dividends([sec.provider_security_key], lo, hi)
        if _near(d.ex_date, c.expect["ex_date"], c.tolerance_days)
        and _close(d.gross_amount, c.expect["amount"])
    ]
    if not hits:
        return [f"no dividend of {c.expect['amount']} near {c.expect['ex_date']}"]
    if not any(d.dividend_type.lower() in {"special", "extraordinary"} for d in hits):
        return ["dividend present but not typed special/extraordinary"]
    return []


def _check_spin_off(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    hits = [
        a
        for a in _actions(cand, sec, c, "ex_date", {"spin_off", "spinoff"})
        if _near(a.ex_date, c.expect["ex_date"], c.tolerance_days)
    ]
    if not hits:
        return [f"no spin-off action near {c.expect['ex_date']}"]
    p = []
    if not any(_close(a.ratio, c.expect["ratio"]) for a in hits):
        p.append(f"spin-off ratio != {c.expect['ratio']}")
    if not any(a.target_key for a in hits):
        p.append("spin-off without the spun-off security (target_key)")
    return p


def _check_terminal(
    cand: ContractCandidate, sec: SecurityRecord, c: ContractCase, reasons: set[str]
) -> list[str]:
    p = []
    end: date = c.expect["delisted_on"]
    if not _near(sec.listing_end, end, c.tolerance_days):
        p.append(f"listing_end {sec.listing_end} != ~{end} (security must not be dropped)")
    if (sec.delisting_reason or "").lower() not in reasons:
        p.append(f"delisting_reason {sec.delisting_reason!r} not in {sorted(reasons)}")
    lo = end - timedelta(days=30)
    if not cand.bars([sec.provider_security_key], lo, end):
        p.append("no bars in the 30 days before delisting")
    return p


def _check_bankruptcy(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    p = _check_terminal(cand, sec, c, {"bankruptcy", "resolution", "liquidation"})
    term = [
        a
        for a in _actions(cand, sec, c, "delisted_on", {"delisting", "bankruptcy", "resolution"})
        if a.cash_amount is not None or "delisting_return" in a.details
    ]
    if not term:
        p.append("no terminal value / delisting return (survivorship-safe returns impossible)")
    return p


def _check_cash_acq(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    p = _check_terminal(cand, sec, c, {"acquired", "merger", "acquisition"})
    hits = [
        a
        for a in _actions(cand, sec, c, "delisted_on", {"merger", "acquisition", "cash_merger"})
        if _close(a.cash_amount, c.expect["cash_per_share"])
    ]
    if not hits:
        p.append(f"no acquisition action paying {c.expect['cash_per_share']} in cash")
    return p


def _check_stock_acq(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    p = _check_terminal(cand, sec, c, {"acquired", "merger", "acquisition"})
    hits = [
        a
        for a in _actions(cand, sec, c, "delisted_on", {"merger", "acquisition", "stock_merger"})
        if _close(a.ratio, c.expect["exchange_ratio"]) and a.target_key
    ]
    if not hits:
        p.append(f"no stock merger with ratio {c.expect['exchange_ratio']} and acquirer key")
    return p


def _check_delisted(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    return _check_terminal(cand, sec, c, set(c.expect.get("reasons", ["delisted"])))


def _check_rights(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    hits = [
        a
        for a in _actions(cand, sec, c, "ex_date", {"rights", "rights_issue"})
        if _near(a.ex_date, c.expect["ex_date"], c.tolerance_days)
    ]
    if not hits:
        return [f"no rights issue near {c.expect['ex_date']}"]
    p = []
    if "ratio" in c.expect and not any(_close(a.ratio, c.expect["ratio"]) for a in hits):
        p.append(f"rights ratio != {c.expect['ratio']}")
    if "subscription_price" in c.expect and not any(
        _close(a.cash_amount, c.expect["subscription_price"]) for a in hits
    ):
        p.append(f"subscription price != {c.expect['subscription_price']}")
    return p


def _check_scrip(cand: ContractCandidate, sec: SecurityRecord, c: ContractCase) -> list[str]:
    lo, hi = _window(c, "ex_date")
    acts = [
        a
        for a in cand.actions([sec.provider_security_key], lo, hi)
        if a.action_type.lower() in {"scrip", "scrip_dividend"}
        and _near(a.ex_date, c.expect["ex_date"], c.tolerance_days)
    ]
    divs = [
        d
        for d in cand.dividends([sec.provider_security_key], lo, hi)
        if d.dividend_type.lower() in {"scrip", "scrip_dividend"}
        and _near(d.ex_date, c.expect["ex_date"], c.tolerance_days)
    ]
    return [] if acts or divs else [f"no scrip dividend near {c.expect['ex_date']}"]


def _check_ticker_change(
    cand: ContractCandidate, sec: SecurityRecord, c: ContractCase
) -> list[str]:
    old, new, on = c.symbol, c.expect["new_symbol"], c.expect["change_date"]
    p = []
    olds = [t for t in sec.tickers if t[0] == old]
    news = [t for t in sec.tickers if t[0] == new]
    if not olds or not news:
        p.append(f"ticker history lacks {old} or {new} on the same provider key")
    else:
        if not any(_near(t[2], on, c.tolerance_days) for t in olds):
            p.append(f"{old} does not end near {on}")
        if not any(_near(t[1], on, c.tolerance_days) for t in news):
            p.append(f"{new} does not start near {on}")
    later = cand.security(new, on + timedelta(days=c.tolerance_days + 1), c.market)
    if later is None or later.provider_security_key != sec.provider_security_key:
        p.append("new symbol resolves to a different security")
    return p


_CHECKS = {
    Category.SPLIT: _check_split,
    Category.REVERSE_SPLIT: _check_split,
    Category.SPECIAL_DIVIDEND: _check_special_dividend,
    Category.SPIN_OFF: _check_spin_off,
    Category.BANKRUPTCY: _check_bankruptcy,
    Category.CASH_ACQUISITION: _check_cash_acq,
    Category.STOCK_ACQUISITION: _check_stock_acq,
    Category.DELISTED: _check_delisted,
    Category.RIGHTS_ISSUE: _check_rights,
    Category.SCRIP_DIVIDEND: _check_scrip,
    Category.TICKER_CHANGE: _check_ticker_change,
}


def run_case(cand: ContractCandidate, c: ContractCase) -> CaseResult:
    sec = cand.security(c.symbol, c.symbol_on, c.market)
    if sec is None:
        problems = [f"{c.symbol} on {c.symbol_on} not found (survivorship bias?)"]
    else:
        problems = _CHECKS[c.category](cand, sec, c)
    return CaseResult(
        c.case_id,
        c.category,
        Outcome.FAIL if problems else Outcome.PASS,
        c.verification,
        tuple(problems),
    )


def run_contract(
    cand: ContractCandidate, cases: Sequence[ContractCase], market: str | None = None
) -> ContractReport:
    rep = ContractReport(cand.info.name)
    for c in cases:
        if market is None or c.market == market:
            rep.results.append(run_case(cand, c))
    return rep
