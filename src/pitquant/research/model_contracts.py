# ruff: noqa: E501
"""Future model contracts (ADR-0048): what a first research model WOULD be, and the data gates that must be READY before any training. Nothing is trained here: ``train`` refuses while any gate is BLOCKED.

The models are deliberately simple, linear and interpretable (elastic net for a continuous excess return, logistic for a binary event). They exist to be compared with the naive baselines of
``effectiveness_v1.naive_baselines``; a model that does not beat them out of sample is discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError
from pitquant.db.models_research import ResearchFeatureSnapshot, ResearchTarget
from pitquant.research import targets_v1 as TG

MIN_DEV_ROWS = 5000
MIN_SECURITIES = 100
MIN_US_FUNDAMENTAL_SECURITIES = 30
MIN_MONTHS_PER_FOLD = 36


class ModelBlockedError(PITQuantError):
    """A model was requested while a data gate is BLOCKED."""


@dataclass(frozen=True)
class ModelContract:
    model_id: str
    algorithm: str  # ELASTIC_NET | LOGISTIC
    target: str  # a column of ResearchTarget
    horizon_months: int
    feature_policy: str = "continuous RAW features + same-date ranks; missing kept as NaN + indicator, never 0; no human-analysis labels"
    split: str = "EXPANDING_WINDOW_PURGED: train on decisions whose label_available_at <= fold start; gap = H months; DEV only; the sealed holdout is never touched"
    regularisation: str = (
        "L1/L2 strength chosen by inner purged time-series CV on the training window only"
    )
    must_beat: tuple[str, ...] = ("base_rate_outperform", "auc_momentum_12_1", "auc_low_vol_63")
    status: str = "CONTRACT_ONLY"
    notes: tuple[str, ...] = field(default_factory=tuple)


CONTRACTS = (
    ModelContract("EQUITY_6M_ELASTIC_NET_V0", "ELASTIC_NET", "excess_total_return", 6),
    ModelContract("EQUITY_12M_ELASTIC_NET_V0", "ELASTIC_NET", "excess_total_return", 12),
    ModelContract("EQUITY_6M_LOGISTIC_V0", "LOGISTIC", "outperform", 6),
    ModelContract("EQUITY_12M_LOGISTIC_V0", "LOGISTIC", "outperform", 12),
    ModelContract(
        "DOWNSIDE_6M_LOGISTIC_V0",
        "LOGISTIC",
        "drawdown_15",
        6,
        notes=("risk model: P(max drawdown >= 15%); RISK_ALERT is only one candidate input",),
    ),
)


def gate_status(session: Session) -> list[dict[str, Any]]:
    n_sec = (
        session.scalar(select(func.count(func.distinct(ResearchFeatureSnapshot.security_id)))) or 0
    )
    n_ok = (
        session.scalar(
            select(func.count())
            .select_from(ResearchTarget)
            .where(ResearchTarget.status == "OK", ResearchTarget.horizon_months == 12)
        )
        or 0
    )
    bench = {
        t: bool(
            session.scalar(
                select(func.count())
                .select_from(ResearchTarget)
                .where(
                    ResearchTarget.benchmark_ticker == t,
                    ResearchTarget.excess_total_return.is_not(None),
                )
            )
        )
        for t in (TG.US.ticker, TG.ES.ticker, TG.WORLD.ticker)
    }
    months: dict[str, int] = {}
    for sid, meta in session.execute(
        select(ResearchFeatureSnapshot.security_id, ResearchFeatureSnapshot.meta)
    ):
        if meta.get("fundamental_status") == "OK":
            months[sid] = months.get(sid, 0) + 1
    n_fund = sum(1 for m in months.values() if m >= MIN_MONTHS_PER_FOLD)
    gates = [
        (
            "DEV_ROWS",
            n_ok >= MIN_DEV_ROWS,
            f"{n_ok} dev rows with a 12M target (need >= {MIN_DEV_ROWS})",
        ),
        (
            "SECURITIES",
            n_sec >= MIN_SECURITIES,
            f"{n_sec} securities with snapshots (need >= {MIN_SECURITIES})",
        ),
        ("BENCHMARKS", all(bench.values()), f"benchmarks with excess returns: {bench}"),
        (
            "CANONICAL_UNIVERSE",
            False,
            "the universe is the CURRENT research set (survivorship, UNIVERSE_NOT_PIT_MEMBERSHIP); D02_MONTHLY_RESEARCH_READY=false",
        ),
        (
            "FUNDAMENTAL_COVERAGE",
            n_fund >= MIN_US_FUNDAMENTAL_SECURITIES,
            f"{n_fund} securities with >= {MIN_MONTHS_PER_FOLD} months of OK fundamentals (need >= {MIN_US_FUNDAMENTAL_SECURITIES})",
        ),
        ("FILING_INTELLIGENCE_NOT_REQUIRED", True, "contract only; not an input to V0 models"),
    ]
    return [{"gate": g, "status": "READY" if ok else "BLOCKED", "detail": d} for g, ok, d in gates]


def train(model_id: str, session: Session) -> None:
    blocked = [g for g in gate_status(session) if g["status"] != "READY"]
    if blocked:
        raise ModelBlockedError(f"{model_id}: BLOCKED by {[g['gate'] for g in blocked]}")
    raise NotImplementedError("training is out of scope for RUN 3")
