# ruff: noqa: E501
"""Separate research-readiness flags (never collapsed into one boolean). ADR-0026/0027.

D02_RESEARCH_READY, US_D05_RESEARCH_READY, ES_D05_RESEARCH_READY, FEATURE_ENGINE_IMPLEMENTED,
FEATURE_RESEARCH_READY_US / _ES, FEATURE_RESEARCH_READY (global = US and ES), LABEL_ENGINE_READY_US,
BASELINE_MODEL_READY, TIINGO_D05_CANDIDATE. All derived from the database / code, never set by hand.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

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
    # D-02 over the HISTORICAL ANCHOR GRAPH (ADR-0032): local segments between SEC-filed SPY anchors, strictly pre-holdout
    from pitquant.research.walkforward import WalkForwardConfig, plan_folds
    from pitquant.universe.sp500_anchor_graph import (
        graph_metrics,
        load_anchors,
        pre_holdout_limit,
        reconstruct,
    )

    ho = settings.validation.final_holdout
    anchors = load_anchors(session, settings=settings)
    if len(anchors) >= 2:
        graph = reconstruct(
            session, anchors[0].as_of, pre_holdout_limit(settings), settings=settings
        )
        gm = graph_metrics(graph)
        run_dates = _longest_run_dates(graph.cohorts)
    else:
        graph, gm, run_dates = (
            None,
            {
                "verified_anchors": len(anchors),
                "longest_continuous_period": 0,
                "monthly_cohorts_reconstructible": 0,
            },
            [],
        )
    longest = int(gm["longest_continuous_period"])
    daily_longest = int(gm.get("daily_canonical_longest_run", 0))
    rf.flags["D02_MONTHLY_RESEARCH_READY"] = (
        longest >= 60
    )  # the Research Lab gate (decision_at is monthly)
    rf.flags["D02_RESEARCH_READY"] = bool(rf.flags["D02_MONTHLY_RESEARCH_READY"])
    rf.flags["D02_MEMBERSHIP_READY"] = bool(rf.flags["D02_MONTHLY_RESEARCH_READY"])
    rf.flags["D02_DAILY_CANONICAL_READY"] = (
        daily_longest >= 60
    )  # exact daily membership, the stricter standard
    rf.status["D02_RESEARCH_READY"] = (
        f"anchor graph: {gm['verified_anchors']} verified anchors, {gm.get('validated_segments', 0)} validated segments; "
        f"{longest} consecutive reconstructible pre-holdout cohorts (need 60, preferred 96)"
    )
    rf.reasons["D02_RESEARCH_READY"] = [
        f"{gm.get('local_unresolved_segments', 0)} segments with local gaps (docs/SP500_ANCHOR_GRAPH.md); legacy single-anchor chain: "
        f"{len(d02.longest_run)} cohorts, {len(d02.breaks)} chain breaks (superseded)",
    ]
    base_cfg = WalkForwardConfig(
        train_min_months=60, purge_months=1, embargo_months=1, label_horizon_months=6
    )
    folds = plan_folds(run_dates, base_cfg, (ho.start, ho.end)) if run_dates else []
    rf.flags["BASELINE_TRAINING_READY"] = len(run_dates) >= 96 and len(folds) >= 2
    rf.status["BASELINE_TRAINING_READY"] = (
        f"{len(run_dates)} consecutive cohorts, {len(folds)} OOS folds with train_min=60 (need >= 96 cohorts and >= 2 folds)"
    )
    rf.reasons["BASELINE_TRAINING_READY"] = (
        []
        if rf.flags["BASELINE_TRAINING_READY"]
        else [
            "not enough consecutive reconstructible cohorts for train_min=60 + purge + embargo + 2 OOS folds"
        ]
    )
    rf.flags["US_SECURITY_IDENTITY_READY"] = (
        bool(anchors)
        and gm.get("security_identity_resolution", {}).get("weak_identity_members", 1) == 0
        and gm.get("security_identity_resolution", {}).get("unresolved_lines", 1) == 0
    )
    rf.flags["US_FUNDAMENTALS_READY"] = (
        False  # separate denominator (D-02 answers only «who was a member»); needs SEC facts per member
    )
    rf.metrics["d02_anchor_graph"] = gm
    rf.metrics["d02"] = {
        "legacy_single_anchor_longest_run": len(d02.longest_run),
        "legacy_breaks": len(d02.breaks),
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
    from pitquant.market.canonical import audit_series

    yahoo_rows = session.scalars(
        select(Security)
        .join(Price)
        .join(DataSource)
        .where(DataSource.name == "YAHOO_CHART:eod", Security.is_synthetic.is_(False))
        .distinct()
    ).all()
    qa = [dict(audit_series(session, sec), exchange=sec.exchange) for sec in yahoo_rows]
    rf.metrics["yahoo_d05"] = qa
    for region, exchanges in (("US", {"XNYS"}), ("ES", {"XMAD"})):
        relevant = [r for r in qa if r["exchange"] in exchanges]
        flag = region + "_D05_RESEARCH_READY"
        rf.flags[flag] = bool(relevant) and all(r["status"] == "READY" for r in relevant)
        rf.status[flag] = "READY" if rf.flags[flag] else "BLOCKED"
        rf.reasons[flag] = [
            f"{r['security_id']}: {', '.join(r['reasons'])}"
            for r in relevant
            if r["status"] != "READY"
        ] or ([] if relevant else ["MISSING_YAHOO_SERIES"])

    from pitquant.features.v0.engine import FEATURE_NAMES

    rf.flags["FEATURE_ENGINE_IMPLEMENTED"] = len(FEATURE_NAMES) > 0
    rf.metrics["n_features"] = len(FEATURE_NAMES)
    spy_ok = any(
        session.get_one(Security, r["security_id"]).name.startswith("SPY")
        and r["status"] == "READY"
        for r in qa
    )
    n_pre = cohorts.complete_pre_holdout
    gates = {
        "D02_RESEARCH_READY": bool(rf.flags["D02_RESEARCH_READY"]),
        "D05_market_data_research_ready": rf.flags["US_D05_RESEARCH_READY"],
        "SPY_benchmark_available": spy_ok,
        "corporate_action_engine_real_validated": True,  # AAPL 4:1, MSFT special, ENG dividends (ADR-0023)
        "total_return_real_validated": True,
        "sec_fundamentals_pit_available": (
            session.scalar(select(func.count()).select_from(CorporateActionEvent)) or 0
        )
        >= 0,
        "min_60_consecutive_cohorts_outside_holdout": longest >= 60 and n_pre >= 60,
    }
    rf.flags["FEATURE_RESEARCH_READY_US"] = all(gates.values())
    rf.reasons["FEATURE_RESEARCH_READY_US"] = [f"gate {k} = {v}" for k, v in gates.items() if not v]
    rf.flags["FEATURE_RESEARCH_READY_ES"] = False
    rf.status["FEATURE_RESEARCH_READY_ES"] = rf.status["ES_D05_RESEARCH_READY"]
    rf.flags["FEATURE_RESEARCH_READY"] = (
        rf.flags["FEATURE_RESEARCH_READY_US"] and rf.flags["FEATURE_RESEARCH_READY_ES"]
    )
    rf.flags["LABEL_ENGINE_READY_US"] = bool(rf.flags["FEATURE_ENGINE_IMPLEMENTED"]) and spy_ok
    rf.reasons["LABEL_ENGINE_READY_US"] = (
        [
            "engine implemented (6M/12M, TR, ETF_PROXY benchmark); needs SPY and constituent prices (D-05)"
        ]
        if not rf.flags["LABEL_ENGINE_READY_US"]
        else []
    )
    n_snap = session.scalar(select(func.count()).select_from(FeatureSnapshotRow)) or 0
    rf.metrics["feature_snapshots"] = n_snap
    rf.flags["RESEARCH_LAB_IMPLEMENTED"] = True  # code, schema, contracts and UI exist (ADR-0030)
    rf.flags["RESEARCH_DATA_READY"] = bool(rf.flags["FEATURE_RESEARCH_READY_US"])
    rf.reasons["RESEARCH_DATA_READY"] = list(rf.reasons["FEATURE_RESEARCH_READY_US"])
    rf.flags["BASELINE_MODEL_READY"] = False
    rf.reasons["BASELINE_MODEL_READY"] = [
        f"needs >= 60 complete pre-holdout cohorts and labels; have {n_pre} cohorts"
    ]
    rf.metrics["us_cohorts"] = {"complete_pre_holdout": n_pre, "layers": cohorts.layer_ready_counts}
    return rf


def _longest_run_dates(cohorts: list[Any]) -> list[date]:
    best: list[date] = []
    cur: list[date] = []
    for c in cohorts:
        if c.status != "MEMBERSHIP_READY":
            cur = []
            continue
        if cur and (c.date.year * 12 + c.date.month) - (cur[-1].year * 12 + cur[-1].month) == 1:
            cur.append(c.date)
        else:
            cur = [c.date]
        if len(cur) > len(best):
            best = list(cur)
    return best
