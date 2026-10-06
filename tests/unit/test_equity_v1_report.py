"""Presentation regression checks on archived research outputs; no fits."""

from __future__ import annotations

import json
from pathlib import Path


def test_probability_distribution_markdown_columns_follow_headers() -> None:
    docs = Path(__file__).resolve().parents[2] / "docs"
    # Archived outputs are not available before the research run.
    source = docs / "FIRST_EQUITY_ML_12M_V1_REPORT.json"
    if not source.exists():
        return
    report = json.loads(source.read_text())
    markdown = (docs / "FIRST_EQUITY_ML_12M_V1_REPORT.md").read_text()
    section = markdown.split("## Distribuciones de probabilidad")[1].split(
        "## Quintiles mensuales"
    )[0]
    for fid in ("F1", "F2", "F3"):
        for model in ("M3", "M3R", "M3RC", "M4", "M4R", "M4RC"):
            expected = report["per_fold"][fid][model]["probability_distribution"]
            row = next(
                line for line in section.splitlines() if line.startswith(f"| {fid} | {model} |")
            )
            values = [float(x.strip()) for x in row.split("|")[3:-1]]
            assert values == [
                round(expected[k], 6) for k in ("min", "p05", "p25", "median", "p75", "p95", "max")
            ]
