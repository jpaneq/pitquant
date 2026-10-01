"""D-05 contract suite.

* Meta-tests (always run): the suite accepts a complete reference stub built from the case
  expectations, and REJECTS deficient stubs — one that drops dead companies (survivorship
  bias) and one that serves back-adjusted prices. Proves the suite has teeth.
* Candidate run: set ``PITQUANT_D05_CANDIDATE=module:factory`` to evaluate a real
  provider adapter (needs its credentials / data). Skipped otherwise — this is not a
  ``pit`` test, skipping it is allowed; acceptance is decided by its report.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

import pytest

from pitquant.data.providers.base import (
    CorporateActionRecord,
    DividendRecord,
    PriceBar,
    ProviderInfo,
    SecurityRecord,
)
from pitquant.data.providers.contract import (
    Category,
    ContractCandidate,
    ContractCase,
    Outcome,
    run_contract,
)
from pitquant.data.providers.contract_cases import CASES
from tests.conftest import utc

ANN = utc(2000, 1, 3)


@dataclass
class StubCandidate:
    """In-memory provider synthesised from case expectations (TEST STUB, not data)."""

    name: str
    secs: dict[tuple[str, str], SecurityRecord] = field(default_factory=dict)
    bars_: list[PriceBar] = field(default_factory=list)
    acts: list[CorporateActionRecord] = field(default_factory=list)
    divs: list[DividendRecord] = field(default_factory=list)

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(self.name, is_synthetic=True, is_point_in_time=False)

    def security(self, symbol: str, on: date, market: str) -> SecurityRecord | None:
        for (m, _), s in self.secs.items():
            if m == market and any(
                t == symbol and a <= on and (b is None or on < b) for t, a, b in s.tickers
            ):
                return s
        return None

    def bars(self, keys: Sequence[str], start: date, end: date) -> Sequence[PriceBar]:
        return [
            b
            for b in self.bars_
            if b.provider_security_key in keys and start <= b.session_date <= end
        ]

    def actions(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[CorporateActionRecord]:
        return [
            a for a in self.acts if a.provider_security_key in keys and start <= a.ex_date <= end
        ]

    def dividends(self, keys: Sequence[str], start: date, end: date) -> Sequence[DividendRecord]:
        return [
            d for d in self.divs if d.provider_security_key in keys and start <= d.ex_date <= end
        ]


def _sec(
    key: str,
    tickers: list[tuple[str, date, date | None]],
    end: date | None = None,
    reason: str | None = None,
) -> SecurityRecord:
    return SecurityRecord(key, key, "X", "USD", None, date(1990, 1, 2), end, reason, tickers, [])


def _bars(
    key: str, around: date, before: float, after: float, last: date | None = None
) -> list[PriceBar]:
    out = []
    d = around - timedelta(days=30)
    while d <= (last or around + timedelta(days=10)):
        if d.weekday() < 5:
            px = before if d < around else after
            out.append(PriceBar(key, d, px, px, px, px, 1.0, "USD"))
        d += timedelta(days=1)
    return out


def reference_stub(cases: Sequence[ContractCase] = CASES) -> StubCandidate:
    s = StubCandidate("REFERENCE_STUB")
    for c in cases:
        k = f"{c.market}:{c.symbol}"  # one security per listing, shared by its cases
        e = c.expect
        start = date(1990, 1, 2)
        if c.category in (Category.SPLIT, Category.REVERSE_SPLIT):
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.acts.append(CorporateActionRecord(k, "split", ANN, e["ex_date"], ratio=e["ratio"]))
            s.bars_ += _bars(k, e["ex_date"], 100.0 * e["ratio"], 100.0)
        elif c.category is Category.SPECIAL_DIVIDEND:
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.divs.append(DividendRecord(k, ANN, e["ex_date"], None, e["amount"], "USD", "special"))
        elif c.category is Category.SPIN_OFF:
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.acts.append(
                CorporateActionRecord(
                    k, "spin_off", ANN, e["ex_date"], ratio=e["ratio"], target_key=k + "-SPUN"
                )
            )
        elif c.category in (
            Category.BANKRUPTCY,
            Category.CASH_ACQUISITION,
            Category.STOCK_ACQUISITION,
            Category.DELISTED,
            Category.TENDER_OFFER_DELISTING,
            Category.MERGER,
        ):
            reason = {
                Category.BANKRUPTCY: "bankruptcy",
                Category.DELISTED: "delisted",
                Category.TENDER_OFFER_DELISTING: "tender_offer",
            }.get(c.category, "acquired")
            end = e["delisted_on"]
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, end)], end, reason)
            s.bars_ += _bars(k, end, 10.0, 10.0, last=end - timedelta(days=1))
            if c.category is Category.BANKRUPTCY:
                s.acts.append(CorporateActionRecord(k, "delisting", ANN, end, cash_amount=0.0))
            elif c.category is Category.CASH_ACQUISITION:
                s.acts.append(
                    CorporateActionRecord(k, "merger", ANN, end, cash_amount=e["cash_per_share"])
                )
            elif c.category in (Category.STOCK_ACQUISITION, Category.MERGER):
                s.acts.append(
                    CorporateActionRecord(
                        k, "merger", ANN, end, ratio=e["exchange_ratio"], target_key="ACQ"
                    )
                )
        elif c.category is Category.ORDINARY_DIVIDEND:
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.divs.append(DividendRecord(k, ANN, e["ex_date"], None, e["amount"], "USD", "regular"))
        elif c.category in (Category.CAPITAL_INCREASE, Category.BONUS_ISSUE):
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            kind = "capital_increase" if c.category is Category.CAPITAL_INCREASE else "bonus_issue"
            s.acts.append(CorporateActionRecord(k, kind, ANN, e["ex_date"], ratio=e.get("ratio")))
        elif c.category is Category.EXCHANGE_MOVE:
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.acts.append(CorporateActionRecord(k, "exchange_change", ANN, e["move_date"]))
        elif c.category is Category.RIGHTS_ISSUE:
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.acts.append(
                CorporateActionRecord(
                    k,
                    "rights_issue",
                    ANN,
                    e["ex_date"],
                    ratio=e.get("ratio"),
                    cash_amount=e.get("subscription_price"),
                )
            )
        elif c.category is Category.SCRIP_DIVIDEND:
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, None)])
            s.divs.append(DividendRecord(k, ANN, e["ex_date"], None, 0.1, "EUR", "scrip"))
        elif c.category is Category.TICKER_CHANGE:
            on = e["change_date"]
            s.secs[(c.market, k)] = _sec(k, [(c.symbol, start, on), (e["new_symbol"], on, None)])
    return s


def test_reference_stub_passes_every_case_but_is_not_accepted_while_unverified() -> None:
    rep = run_contract(reference_stub(), CASES)
    assert rep.failed == [], rep.summary()
    assert len(rep.results) == len(CASES)
    # Unverified expectations block acceptance even with a perfect score.
    assert rep.unverified and not rep.accepted


def test_all_categories_required_by_d05_are_covered() -> None:
    # Generic DELISTED is exercised through bankruptcy and acquisition cases (all delist).
    assert set(Category) - {Category.DELISTED} <= {c.category for c in CASES}
    assert {c.market for c in CASES} == {"US", "ES"}


def test_survivorship_biased_provider_is_rejected() -> None:
    stub = reference_stub()
    dead = {
        Category.BANKRUPTCY,
        Category.CASH_ACQUISITION,
        Category.STOCK_ACQUISITION,
        Category.TENDER_OFFER_DELISTING,
        Category.MERGER,
    }
    dead_cases = [c for c in CASES if c.category in dead]
    dead_keys = {f"{c.market}:{c.symbol}" for c in dead_cases}
    stub.secs = {k: v for k, v in stub.secs.items() if k[1] not in dead_keys}
    rep = run_contract(stub, CASES)
    failed = {r.case_id for r in rep.failed}
    assert failed == {c.case_id for c in dead_cases}
    assert all("not found" in r.problems[0] for r in rep.failed)


def test_back_adjusted_prices_are_rejected() -> None:
    stub = reference_stub()
    stub.bars_ = [replace(b, close=100.0, open=100.0, high=100.0, low=100.0) for b in stub.bars_]
    rep = run_contract(stub, CASES)
    split_cases = {
        c.case_id for c in CASES if c.category in (Category.SPLIT, Category.REVERSE_SPLIT)
    }
    assert {r.case_id for r in rep.failed} == split_cases
    assert all(any("adjusted" in p for p in r.problems) for r in rep.failed)


def test_missing_terminal_value_and_ticker_lineage_are_rejected() -> None:
    stub = reference_stub()
    stub.acts = [a for a in stub.acts if a.action_type != "delisting"]
    for (m, k), s in list(stub.secs.items()):  # ticker change modelled as two securities
        if k == "US:FB":
            stub.secs[(m, k)] = replace(s, tickers=[s.tickers[0]])
            stub.secs[(m, k + "-NEW")] = replace(
                s, provider_security_key=k + "-NEW", tickers=[s.tickers[1]]
            )
    rep = run_contract(stub, CASES)
    by_id = {r.case_id: r for r in rep.results}
    assert by_id["US-BANKRUPTCY-LEH-2008"].outcome is Outcome.FAIL
    assert by_id["ES-RESOLUTION-POP-2017"].outcome is Outcome.FAIL
    assert by_id["US-TICKER-FB-META-2022"].outcome is Outcome.FAIL


def test_verified_case_requires_official_source() -> None:
    from pitquant.data.providers.contract import Verification

    with pytest.raises(ValueError):
        ContractCase("X", "US", Category.SPLIT, "X", date(2020, 1, 2), {}, Verification.VERIFIED)


@pytest.mark.skipif(
    not os.environ.get("PITQUANT_D05_CANDIDATE"), reason="no D-05 candidate configured"
)
def test_candidate_provider() -> None:  # pragma: no cover - needs a real provider
    mod, fn = os.environ["PITQUANT_D05_CANDIDATE"].split(":")
    cand: ContractCandidate = getattr(importlib.import_module(mod), fn)()
    rep = run_contract(cand, CASES)
    print(rep.summary())
    assert not rep.failed, rep.summary()
