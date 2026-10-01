"""Stock Analyzer eligibility — SUPPORTED_SECURITY != INDEX_MEMBERSHIP (ADR-0021).

S&P 500 and IBEX 35 are the initial VALIDATION / BACKTEST universes, not a restriction of
the analyzer: any security can be analysed once its data supports it. Eligibility is
decided ONLY from the Data Coverage Engine (identity, fundamentals, prices, corporate
actions, benchmark/sector) — index membership is deliberately not an input.

Interfaces only: no scoring, no BUY/HOLD/SELL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pitquant.coverage import CoverageStatus, SecurityCoverage


class SupportStatus(StrEnum):
    SUPPORTED_SECURITY = "SUPPORTED_SECURITY"
    NOT_SUPPORTED = "NOT_SUPPORTED"


REQUIRED = ("identity", "fundamentals", "prices", "corporate_actions")
CONTEXT = ("benchmark", "sector")  # at least one of them


@dataclass(frozen=True)
class SupportDecision:
    security_id: str
    status: SupportStatus
    reasons: tuple[str, ...]


def support_decision(cov: SecurityCoverage) -> SupportDecision:
    st = {d.name: d.status for d in cov.dimensions}
    reasons = []
    for dim in REQUIRED:
        if st.get(dim) not in (CoverageStatus.COMPLETE, CoverageStatus.PARTIAL):
            reasons.append(f"{dim}: {st.get(dim, 'missing')}")
    if st.get("identity") is not CoverageStatus.COMPLETE:
        reasons.append("identity must be proven for the whole period")
    if not any(st.get(c) is CoverageStatus.COMPLETE for c in CONTEXT):
        reasons.append("no benchmark or sector context")
    status = SupportStatus.NOT_SUPPORTED if reasons else SupportStatus.SUPPORTED_SECURITY
    return SupportDecision(cov.security_id, status, tuple(dict.fromkeys(reasons)))
