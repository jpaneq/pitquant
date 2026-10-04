# ruff: noqa: E501
"""Benchmark return contract (ADR-0049, ``docs/BENCHMARK_RETURN_CONTRACT.md``).

``future_excess_total_return`` = security total return MINUS benchmark return, and it is only meaningful when both are on the SAME return basis and the SAME currency basis:
* a price-return benchmark against a total-return security is ``PRICE_RETURN_ONLY`` => ``NOT_COMPARABLE_RETURN_BASIS``: the excess is NOT computed and the row is excluded from ML;
* a benchmark in another currency needs PIT FX (``fx.FxTable``): the security series is converted to USD at every instant, never with today's rate; without FX => ``FX_MISMATCH`` (``FX_DATA_NOT_READY``);
* an ETF is always ``ETF_PROXY``, never the official index. Quality ``READY`` is reserved for an official total-return index series; ``PROXY_ACCEPTABLE`` (ETF total return with dividends, comparable currency basis) is the
  methodology-approved state for the first ML. Both sources here are Yahoo (VENDOR, CANONICAL_PROVIDER_FOR_PITQUANT): that is reported by the D05 gate, not hidden in the quality status.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

BENCHMARK_CONTRACT_VERSION = "benchmark-contract-1"
APPROVED_FOR_ML = frozenset({"READY", "PROXY_ACCEPTABLE"})


class ReturnType(StrEnum):
    PRICE_RETURN = "PRICE_RETURN"
    TOTAL_RETURN = "TOTAL_RETURN"
    NET_TOTAL_RETURN = "NET_TOTAL_RETURN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark_id: str
    ticker: str
    name: str
    benchmark_type: str  # INDEX | ETF_PROXY
    return_type: ReturnType
    currency: str
    source: str
    notes: tuple[str, ...] = ()


SPY = BenchmarkSpec(
    "SPY_ETF_PROXY_V1",
    "SPY",
    "SPDR S&P 500 ETF (total return from ex-dividend dates)",
    "ETF_PROXY",
    ReturnType.TOTAL_RETURN,
    "USD",
    "YAHOO_CHART (CANONICAL_SOURCE, VENDOR)",
    ("NOT the official S&P 500 Total Return index",),
)
URTH = BenchmarkSpec(
    "URTH_ETF_PROXY_V1",
    "URTH",
    "iShares MSCI World ETF (USD; tracks MSCI World Net)",
    "ETF_PROXY",
    ReturnType.TOTAL_RETURN,
    "USD",
    "YAHOO_CHART (CANONICAL_SOURCE, VENDOR)",
    ("history starts 2012-01", "NOT the official MSCI World index"),
)
IBEX_PRICE = BenchmarkSpec(
    "IBEX35_PRICE_V1",
    "^IBEX",
    "IBEX 35 (price index)",
    "INDEX",
    ReturnType.PRICE_RETURN,
    "EUR",
    "YAHOO_CHART (CANONICAL_SOURCE, VENDOR)",
    ("no ordinary dividends",),
)
IBEX_TR_REFERENCE = "IBEX 35 CON DIVIDENDOS (ISIN ES0SI0000047, EUR, Total Return): no auditable historical series available => MISSING"


def candidates(exchange: str) -> tuple[BenchmarkSpec, ...]:
    """Preference order of benchmarks for a market. Spain: the coherent one (IBEX Total Return) is MISSING, the price index is listed so the limitation is explicit, URTH is the diagnostic proxy."""
    if exchange == "XNYS":
        return (SPY,)
    if exchange == "XMAD":
        return (IBEX_PRICE, URTH)
    return (URTH,)


def assess(
    spec: BenchmarkSpec, security_currency: str, security_return_type: str, fx_ready: bool
) -> dict[str, str | None]:
    """Quality of ``spec`` for a security: returns quality_status, return_currency_basis, currency_conversion_method, comparability and the blocking reason."""
    if spec.return_type == ReturnType.PRICE_RETURN or security_return_type != "TOTAL_RETURN":
        return {
            "quality_status": "PRICE_RETURN_ONLY",
            "return_currency_basis": None,
            "currency_conversion_method": None,
            "comparability": "NOT_COMPARABLE_RETURN_BASIS",
            "reason": f"{spec.ticker} is {spec.return_type} vs security {security_return_type}",
        }
    if spec.return_type == ReturnType.UNKNOWN:
        return {
            "quality_status": "UNVERIFIED",
            "return_currency_basis": None,
            "currency_conversion_method": None,
            "comparability": "NOT_COMPARABLE_RETURN_BASIS",
            "reason": "benchmark return type unknown",
        }
    if security_currency == spec.currency:
        return {
            "quality_status": "PROXY_ACCEPTABLE" if spec.benchmark_type == "ETF_PROXY" else "READY",
            "return_currency_basis": spec.currency,
            "currency_conversion_method": "NONE_SAME_CURRENCY",
            "comparability": "COMPARABLE",
            "reason": None,
        }
    if not fx_ready:
        return {
            "quality_status": "FX_MISMATCH",
            "return_currency_basis": None,
            "currency_conversion_method": None,
            "comparability": "FX_NOT_READY",
            "reason": f"{security_currency} security vs {spec.currency} benchmark without PIT FX (FX_DATA_NOT_READY)",
        }
    if spec.currency != "USD":
        return {
            "quality_status": "FX_MISMATCH",
            "return_currency_basis": None,
            "currency_conversion_method": None,
            "comparability": "FX_NOT_READY",
            "reason": "only USD-based conversion is implemented",
        }
    return {
        "quality_status": "PROXY_ACCEPTABLE",
        "return_currency_basis": "USD",
        "currency_conversion_method": "SECURITY_TOTAL_RETURN_CONVERTED_TO_USD_AT_PIT_FX",
        "comparability": "COMPARABLE",
        "reason": None,
    }
