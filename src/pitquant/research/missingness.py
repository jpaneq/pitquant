"""Missingness report: per feature, overall and by year / security / sector. No imputation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


def _blank() -> dict[str, Any]:
    return {"observations": 0, "available": 0, "missing": 0, "missing_pct": None, "reasons": {}}


def _finish(b: dict[str, Any]) -> dict[str, Any]:
    b["missing"] = b["observations"] - b["available"]
    b["missing_pct"] = None if b["observations"] == 0 else b["missing"] / b["observations"]
    b["reasons"] = dict(sorted(b["reasons"].items(), key=lambda kv: -kv[1]))
    return b


def _add(b: dict[str, Any], value: object, reason: str | None) -> None:
    b["observations"] += 1
    if value is not None:
        b["available"] += 1
    else:
        b["reasons"][reason or "unspecified"] = b["reasons"].get(reason or "unspecified", 0) + 1


def missingness_report(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    sectors: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in feature_names:
        overall = _blank()
        by_year: dict[str, dict[str, Any]] = {}
        by_sec: dict[str, dict[str, Any]] = {}
        by_sector: dict[str, dict[str, Any]] = {}
        for r in rows:
            v, why = r["features"].get(f), r["feature_reasons"].get(f)
            year = str(str(r["decision_session"])[:4])
            _add(overall, v, why)
            _add(by_year.setdefault(year, _blank()), v, why)
            _add(by_sec.setdefault(r["security_id"], _blank()), v, why)
            if sectors is not None:
                _add(
                    by_sector.setdefault(sectors.get(r["security_id"], "UNKNOWN"), _blank()), v, why
                )
        out[f] = {
            **_finish(overall),
            "by_year": {k: _finish(v) for k, v in sorted(by_year.items())},
            "by_security": {k: _finish(v) for k, v in by_sec.items()},
            "by_sector": {k: _finish(v) for k, v in by_sector.items()}
            if sectors is not None
            else None,
        }
    return out


def blocking_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for r in rows:
        for x in r["blocking_reason"]:
            c[x.split(":")[0]] += 1
    return dict(c.most_common())
