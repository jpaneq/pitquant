# ruff: noqa: E501
"""SimulationEngineV1 is FROZEN (ADR-0037): its output over a fixed battery of synthetic scenarios is pinned by a digest. Changing this digest means
changing the execution rules of every v1 simulation: that is forbidden. A behaviour change belongs in a NEW engine (v2) registered next to v1."""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd

from pitquant.simulation import registry
from pitquant.simulation.engine import PlanLevels

T0 = date(2024, 1, 2)


def bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["d", "open", "high", "low", "close"])
    df.index = [date.fromisoformat(x) for x in df.pop("d")]
    return df


SCENARIOS = {
    "stop": [("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 99, 100, 94, 96)],
    "stop_gap": [("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 90, 92, 88, 91)],
    "track_open": [
        ("2024-01-03", 100, 101, 99.5, 100),
        ("2024-01-04", 101, 111, 100, 109),
        ("2024-01-05", 109, 110, 105, 106),
    ],
    "ambiguous_entry": [("2024-01-03", 103, 104, 94, 100)],
    "ambiguous_exit": [("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 100, 112, 94, 100)],
    "waiting": [("2024-01-03", 103, 105, 101, 104)],
    "favourable_gap_target": [("2024-01-03", 97, 99, 96, 98), ("2024-01-04", 112, 114, 111, 113)],
    "wait_then_enter": [
        ("2024-01-03", 104, 105, 102, 103),
        ("2024-01-04", 103, 104, 101, 102),
        ("2024-01-05", 102, 103, 99, 100),
    ],
}
PLANS = {
    "limit_track": PlanLevels(
        "LIMIT", 100.0, 100.0, 95.0, 110.0, 120.0, exit_policy="TRACK_TARGETS_ONLY"
    ),
    "zone_partial": PlanLevels(
        "ENTRY_ZONE",
        98.0,
        100.0,
        95.0,
        110.0,
        120.0,
        invalidation=94.0,
        exit_policy="PARTIAL_FRACTIONS",
        exit_fractions=(0.5, 0.5, 0.0),
    ),
    "legacy": PlanLevels("LIMIT", 98.0, 100.0, 95.0, 110.0, 120.0),
    "market_ref": PlanLevels(
        "MARKET_REFERENCE",
        100.0,
        100.0,
        95.0,
        110.0,
        exit_policy="PARTIAL_FRACTIONS",
        exit_fractions=(1.0, 0.0, 0.0),
    ),
}


def digest() -> str:
    e = registry.resolve_engine("v1")
    out = {}
    for pn, plan in PLANS.items():
        for sn, rows in SCENARIOS.items():
            ev = e.evaluate(plan, bars(rows), T0, reference_price=100.0)
            out[f"{pn}/{sn}"] = {
                "events": ev.events,
                "state": ev.state.value,
                "metrics": ev.metrics,
                "exits": ev.exits,
                "fold": e.fold_events(ev.events, plan),
            }
    return hashlib.sha256(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()


V1_DIGEST = "83849ff8369337a916dbbc7349cb84cb604de4d304aa051a48962350db02c637"


def test_v1_output_is_frozen() -> None:
    assert digest() == V1_DIGEST, (
        "SimulationEngineV1 changed: create a NEW engine version instead of editing v1 (ADR-0037)"
    )


def test_v1_identity() -> None:
    e = registry.resolve_engine("v1")
    assert (e.version, e.event_schema_version) == ("v1", 1) and set(e.event_labels) == {
        "v1",
        "sim-engine-2",
    }
