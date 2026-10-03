# ruff: noqa: E501
"""Version-pinned simulation engines (ADR-0037).

A simulation is bound to the execution rules it was created under: ``simulations.simulation_engine_version`` is immutable (append-only row). Every
operation that interprets a simulation (update, replay, counterfactual) resolves its engine HERE, by that pinned version, and never by «the latest».

Lifecycle rules (see docs/SIMULATION_LAB.md):
* an existing simulation stays on its original engine FOR EVER; a new simulation uses ``CURRENT_SIMULATION_ENGINE_VERSION`` at creation time;
* no silent migration and no recomputation of a v1 history with v2. To see a simulation under newer rules, run a COUNTERFACTUAL or create a FORK
  (``EngineMigrationContract``): a new simulation or a labelled side evaluation, never an in-place rewrite;
* a version that is not registered fails CLOSED with ``ENGINE_VERSION_UNAVAILABLE`` (it is not «divergence» and it is never run by another engine);
* ``SimulationEngineV1`` wraps ``simulation.engine`` and is FROZEN: its semantics change only through a bug proven by a test, anything else is a new
  engine class (``tests/unit/test_simulation_engine_v1_frozen.py`` pins its output).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import pandas as pd

from pitquant.core.errors import PITQuantError
from pitquant.simulation import engine as _v1


class EngineVersionUnavailable(PITQuantError):
    """``ENGINE_VERSION_UNAVAILABLE``: the pinned engine is not registered in this build. Fail closed."""


class SimulationEngine(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def event_schema_version(self) -> int: ...

    @property
    def event_labels(self) -> tuple[str, ...]:
        """engine_version labels of stored events this engine accepts (v1 also accepts the V1-era label)."""
        ...

    def evaluate(
        self,
        plan: _v1.PlanLevels,
        bars: pd.DataFrame,
        decision_date: date,
        *,
        benchmark: pd.Series | None = None,
        manual_close: tuple[date, float] | None = None,
        reference_price: float | None = None,
        cancel_on: date | None = None,
    ) -> _v1.Evaluation: ...

    def fold_events(self, events: list[dict[str, Any]], plan: _v1.PlanLevels) -> dict[str, Any]: ...


class SimulationEngineV1:
    """The execution rules validated in Simulation Lab V1 (ADR-0036), unchanged."""

    version = "v1"
    event_schema_version = 1
    event_labels = (
        "v1",
        "sim-engine-2",
    )  # rows written before ADR-0037 carry «sim-engine-2» (append-only: never rewritten)

    def evaluate(
        self,
        plan: _v1.PlanLevels,
        bars: pd.DataFrame,
        decision_date: date,
        *,
        benchmark: pd.Series | None = None,
        manual_close: tuple[date, float] | None = None,
        reference_price: float | None = None,
        cancel_on: date | None = None,
    ) -> _v1.Evaluation:
        return _v1.evaluate(
            plan,
            bars,
            decision_date,
            benchmark=benchmark,
            manual_close=manual_close,
            reference_price=reference_price,
            cancel_on=cancel_on,
        )

    def fold_events(self, events: list[dict[str, Any]], plan: _v1.PlanLevels) -> dict[str, Any]:
        return _v1.fold_events(events, plan)


SIMULATION_ENGINES: dict[str, SimulationEngine] = {"v1": SimulationEngineV1()}
CURRENT_SIMULATION_ENGINE_VERSION = "v1"  # used ONLY when a NEW simulation is created


def resolve_engine(version: str) -> SimulationEngine:
    try:
        return SIMULATION_ENGINES[version]
    except KeyError:
        raise EngineVersionUnavailable(
            f"ENGINE_VERSION_UNAVAILABLE: simulation engine {version!r} is not registered in this build (registered: {sorted(SIMULATION_ENGINES)})"
        ) from None


def current_engine() -> SimulationEngine:
    return resolve_engine(CURRENT_SIMULATION_ENGINE_VERSION)


MIGRATION_TYPES = ("COUNTERFACTUAL", "FORK")


@dataclass(frozen=True)
class EngineMigrationContract:
    """CONCEPTUAL contract (no implementation, no UI yet): to evaluate a simulation under other rules, a COUNTERFACTUAL (side evaluation, labelled,
    never the real outcome) or a FORK (a NEW simulation that copies the T0 snapshot and is pinned to the target engine). Never an in-place change."""

    source_simulation_id: str
    source_engine_version: str
    target_engine_version: str
    migration_type: str

    def __post_init__(self) -> None:
        if self.migration_type not in MIGRATION_TYPES:
            raise ValueError(
                f"migration_type must be one of {MIGRATION_TYPES}: there is no in-place migration"
            )
        if self.source_engine_version == self.target_engine_version:
            raise ValueError("a migration needs a different target engine")
