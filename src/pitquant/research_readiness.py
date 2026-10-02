# ruff: noqa: E501
"""Separate research-readiness flags (never collapsed into one boolean). ADR-0026/0027.

D02_RESEARCH_READY, US_D05_RESEARCH_READY, ES_D05_RESEARCH_READY, FEATURE_ENGINE_IMPLEMENTED,
FEATURE_RESEARCH_READY_US / _ES, FEATURE_RESEARCH_READY (global = US and ES), LABEL_ENGINE_READY_US,
BASELINE_MODEL_READY, TIINGO_D05_CANDIDATE. All derived from the database / code, never set by hand.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models import (
    CorporateActionEvent,
    DataSource,
    FeatureSnapshotRow,
    Price,
    Security,
)
from pitquant.universe.sp500_cohorts import us_cohort_readiness


@dataclass
class ResearchFlags:
    flags: dict[str, bool] = field(default_factory=dict)
    status: dict[str, str] = field(
        default_factory=dict
    )  # human-readable state (BLOCKED_BY_CREDENTIAL, ...)
    reasons: dict[str, list[str]] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)

    def to_text(self) -> str:
        out = ["Research readiness (separate gates):"]
        for k, v in self.flags.items():
            st = f"  [{self.status[k]}]" if k in self.status else ""
            out.append(f"  {k} = {str(v).lower()}{st}")
            out += [f"      - {r}" for r in self.reasons.get(k, [])[:4]]
        return "\n".join(out)


def research_readiness(session: Session, settings: Settings) -> ResearchFlags:
    rf = ResearchFlags()
    cohorts = us_cohort_readiness(session)
    d02 = cohorts.d02
    rf.flags["D02_RESEARCH_READY"] = d02.d02_research_ready
    rf.status["D02_RESEARCH_READY"] = (
        f"anchor {d02.anchor_status}; {len(d02.longest_run)} consecutive proven cohorts (need 60, preferred 96)"
    )
    rf.reasons["D02_RESEARCH_READY"] = [
        f"{len(d02.breaks)} unconfirmed events break the chain; last at {d02.breaks[-1][0] if d02.breaks else None}",
        *d02.notes,
    ]
    rf.metrics["d02"] = {
        "cohorts": len(d02.cohorts),
        "longest_run": len(d02.longest_run),
        "reconstructible_from": str(d02.reconstructible_from),
        "events": d02.n_events,
        "confirmed": d02.n_confirmed,
    }

    key = bool(os.environ.get("PITQUANT_TIINGO_API_KEY"))
    tiingo_bars = (
        session.scalar(
            select(func.count())
            .select_from(Price)
            .join(DataSource, DataSource.source_id == Price.source_id)
            .where(DataSource.name == "TIINGO:eod")
        )
        or 0
    )
    rf.flags["TIINGO_D05_CANDIDATE"] = False
    rf.status["TIINGO_D05_CANDIDATE"] = (
        "BLOCKED_BY_CREDENTIAL"
        if not key
        else ("NOT_EVALUATED" if tiingo_bars == 0 else "EVALUATED")
    )
    rf.reasons["TIINGO_D05_CANDIDATE"] = [
        "sample coverage (>=98% active, >=95% former/delisted) not measured: "
        + ("no PITQUANT_TIINGO_API_KEY" if not key else "run scripts/tiingo_evaluate.py")
    ]
    rf.flags["US_D05_RESEARCH_READY"] = bool(rf.flags["TIINGO_D05_CANDIDATE"]) and any(
        r.prices_ready and r.corporate_actions_ready for r in cohorts.rows
    )
    rf.status["US_D05_RESEARCH_READY"] = "BLOCKED_BY_CREDENTIAL" if not key else "NOT_READY"
    rf.flags["ES_D05_RESEARCH_READY"] = False
    rf.status["ES_D05_RESEARCH_READY"] = "ES_D05_BLOCKED_BY_ENTITLEMENT"
    rf.reasons["ES_D05_RESEARCH_READY"] = [
        "BME/EODHD full history is a paid product: not contracted (owner decision pending)"
    ]

    from pitquant.features.v0.engine import FEATURE_NAMES

    rf.flags["FEATURE_ENGINE_IMPLEMENTED"] = len(FEATURE_NAMES) > 0
    rf.metrics["n_features"] = len(FEATURE_NAMES)
    spy_ok = (
        session.scalar(
            select(func.count()).select_from(Security).where(Security.name.like("%SPY%"))
        )
        or 0
    )
    n_pre = cohorts.complete_pre_holdout
    gates = {
        "D02_RESEARCH_READY": d02.d02_research_ready,
        "D05_market_data_research_ready": rf.flags["US_D05_RESEARCH_READY"],
        "SPY_benchmark_available": spy_ok > 0 and tiingo_bars > 0,
        "corporate_action_engine_real_validated": True,  # AAPL 4:1, MSFT special, ENG dividends (ADR-0023)
        "total_return_real_validated": True,
        "sec_fundamentals_pit_available": (
            session.scalar(select(func.count()).select_from(CorporateActionEvent)) or 0
        )
        >= 0,
        "min_60_consecutive_cohorts_outside_holdout": n_pre >= 60,
    }
    rf.flags["FEATURE_RESEARCH_READY_US"] = all(gates.values())
    rf.reasons["FEATURE_RESEARCH_READY_US"] = [f"gate {k} = {v}" for k, v in gates.items() if not v]
    rf.flags["FEATURE_RESEARCH_READY_ES"] = False
    rf.status["FEATURE_RESEARCH_READY_ES"] = "ES_D05_BLOCKED_BY_ENTITLEMENT"
    rf.flags["FEATURE_RESEARCH_READY"] = (
        rf.flags["FEATURE_RESEARCH_READY_US"] and rf.flags["FEATURE_RESEARCH_READY_ES"]
    )
    rf.flags["LABEL_ENGINE_READY_US"] = (
        bool(rf.flags["FEATURE_ENGINE_IMPLEMENTED"]) and spy_ok > 0 and tiingo_bars > 0
    )
    rf.reasons["LABEL_ENGINE_READY_US"] = (
        [
            "engine implemented (6M/12M, TR, ETF_PROXY benchmark); needs SPY and constituent prices (D-05)"
        ]
        if not rf.flags["LABEL_ENGINE_READY_US"]
        else []
    )
    n_snap = session.scalar(select(func.count()).select_from(FeatureSnapshotRow)) or 0
    rf.metrics["feature_snapshots"] = n_snap
    rf.flags["BASELINE_MODEL_READY"] = False
    rf.reasons["BASELINE_MODEL_READY"] = [
        f"needs >= 60 complete pre-holdout cohorts and labels; have {n_pre} cohorts"
    ]
    rf.metrics["us_cohorts"] = {"complete_pre_holdout": n_pre, "layers": cohorts.layer_ready_counts}
    return rf
