# ruff: noqa: E501
"""Filing Intelligence Layer: CONTRACT ONLY (ADR-0048, ``docs/FILING_INTELLIGENCE.md``). No model is called here and none can be: ``LLM_CALLS_ENABLED`` is False and ``analyze_filing`` refuses.

A ``FilingAnalysisSnapshot`` is a structured, versioned reading of ONE SEC filing. Rules enforced by validation:
* 18 normalised blocks; every block value is an ENUM (no free-text feature). The optional ``note`` is display only and never enters ``feature_vector``.
* A non-``NOT_STATED`` block MUST carry evidence (section + a short quote + character offsets in the archived document). No evidence => the block cannot assert anything.
* PIT: a snapshot is knowable at T only if ``filing_available_at <= T`` AND ``analysis_available_at <= T``; an analysis produced after the filing is ``is_retrospective`` and is excluded from any PIT research (``usable_at``).
* Versions (schema, prompt, model provider/name/version) are part of the identity; a new prompt or model is a NEW snapshot, never an edit.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pitquant.core.hashing import content_hash

ANALYSIS_SCHEMA_VERSION = "filing-analysis-1"
LLM_CALLS_ENABLED = False
MAX_QUOTE_WORDS = 30


class Signal(StrEnum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DETERIORATING = "DETERIORATING"
    MIXED = "MIXED"
    NOT_STATED = "NOT_STATED"


class Magnitude(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NOT_STATED = "NOT_STATED"


class Change(StrEnum):
    NEW = "NEW"
    INCREASED = "INCREASED"
    UNCHANGED = "UNCHANGED"
    DECREASED = "DECREASED"
    REMOVED = "REMOVED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


BLOCKS = (
    "business_model", "revenue_drivers", "segments", "geographic_exposure", "customer_concentration", "competition", "moat_signals", "growth_outlook", "margin_outlook",
    "capex_plans", "capital_allocation", "debt_liquidity", "new_risk_factors", "removed_risk_factors", "legal_regulatory", "accounting_quality", "management_tone", "guidance_changes",
)  # fmt: skip
SIGNAL_ENC = {Signal.DETERIORATING: -1, Signal.MIXED: 0, Signal.STABLE: 0, Signal.IMPROVING: 1}
MAG_ENC = {Magnitude.NONE: 0, Magnitude.LOW: 1, Magnitude.MEDIUM: 2, Magnitude.HIGH: 3}
CHANGE_ENC = {
    Change.REMOVED: -1,
    Change.DECREASED: -1,
    Change.UNCHANGED: 0,
    Change.INCREASED: 1,
    Change.NEW: 1,
}


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    section: str = Field(min_length=1, description="e.g. 'Item 1A', 'Item 7'")
    quote: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def _short_and_ordered(self) -> Evidence:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be > char_start")
        if len(self.quote.split()) > MAX_QUOTE_WORDS:
            raise ValueError(
                f"quote longer than {MAX_QUOTE_WORDS} words: evidence is a pointer, not a copy of the filing"
            )
        return self


class Block(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    signal: Signal = Signal.NOT_STATED
    magnitude: Magnitude = Magnitude.NOT_STATED
    change_vs_prior: Change = Change.NOT_COMPARABLE
    evidence: tuple[Evidence, ...] = ()
    note: str | None = Field(
        default=None, max_length=300, description="display only; never a feature"
    )

    @model_validator(mode="after")
    def _assertion_needs_evidence(self) -> Block:
        asserts = (
            self.signal != Signal.NOT_STATED
            or self.magnitude != Magnitude.NOT_STATED
            or self.change_vs_prior != Change.NOT_COMPARABLE
        )
        if asserts and not self.evidence:
            raise ValueError("a block that asserts anything must carry evidence")
        return self


class FilingAnalysisSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    accession_number: str
    security_id: str
    issuer_id: str | None = None
    form: str
    period_end: date | None = None
    accepted_at: datetime
    filing_available_at: datetime
    document_hash: str = Field(min_length=64, max_length=64)
    analysis_schema_version: str = ANALYSIS_SCHEMA_VERSION
    prompt_version: str
    model_provider: str
    model_name: str
    model_version: str
    analysis_available_at: datetime
    status: str = "COMPLETE"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: tuple[str, ...] = ()
    blocks: dict[str, Block]

    @model_validator(mode="after")
    def _validate(self) -> FilingAnalysisSnapshot:
        for d in (self.accepted_at, self.filing_available_at, self.analysis_available_at):
            if d.tzinfo is None:
                raise ValueError("naive datetime")
        if self.filing_available_at < self.accepted_at:
            raise ValueError("filing_available_at before accepted_at")
        if set(self.blocks) != set(BLOCKS):
            raise ValueError(
                f"blocks must be exactly the {len(BLOCKS)} normalised blocks: missing {sorted(set(BLOCKS) - set(self.blocks))}, extra {sorted(set(self.blocks) - set(BLOCKS))}"
            )
        if self.status not in ("COMPLETE", "PARTIAL", "FAILED"):
            raise ValueError("status")
        return self

    @property
    def is_retrospective(self) -> bool:
        """The analysis was produced after the filing became public (always true for a backfill): it only counts from ``analysis_available_at`` on."""
        return self.analysis_available_at > self.filing_available_at

    def usable_at(self, t: datetime) -> bool:
        """The PIT rule: the filing AND this analysis must both exist by ``t``. A backfill run in 2026 over a 2015 filing is therefore NOT usable for a 2015 decision (``is_retrospective``)."""
        if t.tzinfo is None:
            raise ValueError("naive datetime")
        return (
            self.status != "FAILED"
            and self.filing_available_at <= t
            and self.analysis_available_at <= t
        )

    def feature_vector(self) -> dict[str, float | None]:
        """Numeric encoding of the enums only (free text never enters). NOT_STATED => None, never 0."""
        out: dict[str, float | None] = {}
        for name in BLOCKS:
            b = self.blocks[name]
            out[f"fi_{name}_signal"] = (
                None if b.signal == Signal.NOT_STATED else float(SIGNAL_ENC[b.signal])
            )
            out[f"fi_{name}_magnitude"] = (
                None if b.magnitude == Magnitude.NOT_STATED else float(MAG_ENC[b.magnitude])
            )
            out[f"fi_{name}_change"] = (
                None
                if b.change_vs_prior == Change.NOT_COMPARABLE
                else float(CHANGE_ENC[b.change_vs_prior])
            )
        return out

    def analysis_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


def analyze_filing(*_a: Any, **_k: Any) -> FilingAnalysisSnapshot:
    raise NotImplementedError(
        "Filing Intelligence is a contract only: no LLM is called in this build (LLM_CALLS_ENABLED=False). See docs/FILING_INTELLIGENCE.md"
    )


def pit_snapshots(snaps: list[FilingAnalysisSnapshot], t: datetime) -> list[FilingAnalysisSnapshot]:
    """Snapshots a decision at ``t`` may use: latest per (accession) among the usable ones, deterministic by analysis time."""
    best: dict[str, FilingAnalysisSnapshot] = {}
    for s in sorted(snaps, key=lambda x: (x.analysis_available_at, x.analysis_hash())):
        if s.usable_at(t):
            best[s.accession_number] = s
    return list(best.values())
