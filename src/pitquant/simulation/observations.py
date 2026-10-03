# ruff: noqa: E501
"""HISTORICAL observations of a simulation (ADR-0037): what the Analyzer knew at a later bar date, recorded once and never rewritten.

* **Cadence** (no daily snapshot spam): T+1, T+5, T+20 and every 20 trading BARS after that, the key events of the log (entry, stop, target touches,
  invalidation, expiry, manual close, ambiguity, cancellation) and the FINAL state. Several milestones of the same date share ONE observation.
* **Point in time**: the analysis of the bar date ``d`` is computed at the CLOSE of that session. Bars, filings (``available_at``), valuation inputs, support/
  resistance and regime are exactly those the PIT context exposes at that instant: nothing later can enter.
* **Immutable**: rows are append-only and unique per ``(simulation, label)`` and per bar date; an existing observation is never recomputed, even if
  the Analyzer changes. A newer Analyzer produces a NEW observation only for a date that has none, tagged with its own versions.
* **Facts, not causes**: ``thesis_facts`` compares an observation with T0 and states what differs (trend, support, volatility, valuation, fundamentals, regime).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import Settings
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import Simulation, SimulationObservation
from pitquant.simulation.engine import CLOSED

OBSERVATION_SCHEMA_VERSION = 1
ANALYZER_VERSION = "analyzer-v0"
KEY_EVENTS = (
    "ENTRY_FILLED", "STOP_TRIGGERED", "TP1_TOUCHED", "TP2_TOUCHED", "TP3_TOUCHED", "INVALIDATED", "EXPIRED", "MANUAL_CLOSE", "AMBIGUOUS_INTRABAR", "CANCELLED",
)  # fmt: skip
CLOSED_VALUES = {s.value for s in CLOSED}


def is_horizon(k: int) -> bool:
    """T+1, T+5, T+20 and every 20 trading bars after that."""
    return k in (1, 5, 20) or (k > 20 and k % 20 == 0)


def milestones(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    """PURE: ``{iso date: sorted labels}`` of the observations the event log calls for. ``k`` counts processed BARS from the decision (not calendar days)."""
    out: dict[str, set[str]] = {}
    k = 0
    last_state = None
    last_date = None
    for e in events:
        t, d = e["type"], e["date"]
        if t == "BAR_PROCESSED":
            k += 1
            if is_horizon(k):
                out.setdefault(d, set()).add(f"T+{k}")
        elif t in KEY_EVENTS:
            out.setdefault(d, set()).add(f"EVENT:{t}")
        if "state_after" in e["payload"]:
            last_state = e["payload"]["state_after"]
        if t != "SIMULATION_CREATED":
            last_date = d
    if last_state in CLOSED_VALUES and last_date is not None:
        out.setdefault(last_date, set()).add("FINAL")
    return {d: sorted(v) for d, v in sorted(out.items())}


def _session_for(cal: Any, d: date) -> date:
    return d if cal.is_session(d) else cal.session_on_or_before(d)


@dataclass
class RecordResult:
    created: list[SimulationObservation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _context(events: list[dict[str, Any]], d: str) -> dict[str, Any]:
    """Price / return / benchmark / state AS OF the bar date, from the event log alone."""
    close = state = None
    entry = bench_entry = bench_now = None
    entry_date = None
    for e in events:
        if e["date"] > d:
            break
        p = e["payload"]
        if "state_after" in p:
            state = p["state_after"]
        if e["type"] == "ENTRY_FILLED":
            entry, entry_date = p["price"], e["date"]
        if e["type"] == "BAR_PROCESSED":
            close = p["close"]
            if p.get("bench_close") is not None:
                bench_now = p["bench_close"]
                if entry_date == e["date"]:
                    bench_entry = p["bench_close"]
    return {
        "price": close,
        "state": state,
        "return_since_entry": (close / entry - 1.0) if close and entry else None,
        "benchmark_return": (bench_now / bench_entry - 1.0) if bench_now and bench_entry else None,
    }


def record_observations(
    session: Session,
    settings: Settings,
    sim: Simulation,
    events: list[dict[str, Any]],
    as_of: datetime,
) -> RecordResult:
    """Create the MISSING observations (idempotent: a date or label that already has one is skipped). Each date runs in its own savepoint and a failure
    is REPORTED, never raised: the event log is the source of truth and must not be blocked by an Analyzer problem."""
    res = RecordResult()
    plan = milestones(events)
    if not plan:
        return res
    have = {
        (o.source_bar_date, o.horizon_label)
        for o in session.scalars(
            select(SimulationObservation).where(
                SimulationObservation.simulation_id == sim.simulation_id,
                SimulationObservation.kind == "PERIODIC",
            )
        )
    }
    have_dates = {d for d, _ in have}
    have_labels = {lbl for _, lbl in have}
    exchange = load_market(session, sim.security_id, as_of).exchange
    cal = get_calendar(exchange)
    svc = AnalyzerService(session, settings)
    from pitquant.simulation.service import _guard

    for d_iso, labels in plan.items():
        d = date.fromisoformat(d_iso)
        label = "|".join(labels)
        if d in have_dates or label in have_labels:
            continue
        sess = _session_for(cal, d)
        at = cal.session_close(sess)
        if at > as_of:
            continue  # the session had not closed at the evaluation instant
        try:
            _guard(at, settings)
            with session.begin_nested():
                tech, fund, val = (
                    svc.technicals(sim.security_id, at),
                    svc.fundamentals(sim.security_id, at),
                    svc.valuation(sim.security_id, at),
                )
                ctx = _context(events, d_iso)
                body = {
                    **ctx, "labels": labels, "bar_date": d_iso, "analysis_session": str(sess), "as_of": at.isoformat(), "quote": svc.quote(sim.security_id, at),
                    "technical_snapshot": tech, "fundamental_snapshot": fund, "valuation_snapshot": val, "support_resistance_snapshot": tech.get("support_resistance") or {},
                    "market_regime_snapshot": {"trend": tech.get("trend"), "risk": tech.get("risk"), "volume": tech.get("volume"), "overextension": tech.get("overextension")},
                    "data_quality_snapshot": svc.data_quality(sim.security_id, at),
                }  # fmt: skip
                body["content_hash"] = hashlib.sha256(
                    json.dumps(body, sort_keys=True, default=str).encode()
                ).hexdigest()
                row = SimulationObservation(
                    simulation_id=sim.simulation_id, observed_at=at, kind="PERIODIC", payload=body, horizon_label=label, source_bar_date=d,
                    observation_schema_version=OBSERVATION_SCHEMA_VERSION, analyzer_version=ANALYZER_VERSION, feature_version=svc.versions()["feature_engine_version"],
                )  # fmt: skip
                session.add(row)
                session.flush()
            res.created.append(row)
        except Exception as e:
            res.errors.append(f"{d_iso} {label}: {type(e).__name__}: {e}")
    return res


# ───────────────────────────────────────────── descriptive facts: T0 vs an observation
def _at(o: Any, path: str) -> Any:
    for k in path.split("."):
        if not isinstance(o, dict):
            return None
        o = o.get(k)
    return o


def _num(x: Any) -> float | None:
    return float(x) if isinstance(x, int | float) and not isinstance(x, bool) else None


def _regime(m: dict[str, Any] | None) -> dict[str, Any]:
    m = m or {}
    return {
        k: (m.get(k) or {}).get("state")
        for k in ("trend", "overextension", "volume")
        if isinstance(m.get(k), dict) and (m.get(k) or {}).get("state") is not None
    }


def thesis_facts(
    sim: Simulation, obs: dict[str, Any], observation_id: str | None = None
) -> list[dict[str, Any]]:
    """What differs between T0 and an observation. Each fact carries its definition and both values; none is a cause."""
    f: list[dict[str, Any]] = []

    def add(flag: str, definition: str, t0: Any, now: Any) -> None:
        f.append(
            {
                "fact": flag,
                "definition": definition,
                "t0": t0,
                "observed": now,
                "source_observation_id": observation_id,
            }
        )

    tr0, tr1 = (
        _at(sim.technical_snapshot, "trend.state"),
        _at(obs.get("technical_snapshot"), "trend.state"),
    )
    if tr0 and tr1 and tr0 != tr1:
        add("trend_changed", "the trend state differs from T0", tr0, tr1)
    price = _num(obs.get("price"))
    sup = ((sim.support_resistance_snapshot or {}).get("supports") or [{}])[0].get("lower")
    res = ((sim.support_resistance_snapshot or {}).get("resistances") or [{}])[0].get("upper")
    p0 = _num((sim.price_snapshot or {}).get("price"))
    if price is not None and p0 is not None and _num(sup) is not None and p0 >= float(sup) > price:
        add(
            "support_broken",
            "price is below the nearest T0 support zone (it was above it at T0)",
            sup,
            price,
        )
    if price is not None and p0 is not None and _num(res) is not None and p0 <= float(res) < price:
        add(
            "resistance_broken",
            "price is above the nearest T0 resistance zone (it was below it at T0)",
            res,
            price,
        )
    v0, v1 = (
        _num(_at(sim.technical_snapshot, "risk.vol63")),
        _num(_at(obs.get("technical_snapshot"), "risk.vol63")),
    )
    if v0 and v1 and v1 > v0:
        add(
            "volatility_expanded",
            "63-day realised volatility is higher than at T0 (ratio carried; no threshold is validated)",
            v0,
            v1,
        )
    pe0, pe1 = (
        _num(_at(sim.valuation_snapshot, "current.pe")),
        _num(_at(obs.get("valuation_snapshot"), "current.pe")),
    )
    if pe0 and pe1 and pe1 > pe0:
        add("valuation_expanded", "P/E is higher than at T0", pe0, pe1)
    if pe0 and pe1 and pe1 < pe0:
        add("valuation_compressed", "P/E is lower than at T0", pe0, pe1)
    fs0 = (
        _at(sim.fundamental_snapshot, "latest_period"),
        _at(sim.fundamental_snapshot, "latest_filing_available_at"),
    )
    fs1 = (
        _at(obs.get("fundamental_snapshot"), "latest_period"),
        _at(obs.get("fundamental_snapshot"), "latest_filing_available_at"),
    )
    if fs1 != fs0 and fs1 != (None, None):
        add(
            "fundamental_snapshot_changed",
            "a newer fundamental period / filing is known than at T0 (not a judgement of improvement or deterioration)",
            list(fs0),
            list(fs1),
        )
    r0, r1 = _regime(sim.market_regime_snapshot), _regime(obs.get("market_regime_snapshot"))
    if r0 and r1 and r0 != r1:
        add(
            "regime_changed",
            "a market-regime component state (trend / overextension / volume) differs from T0",
            r0,
            r1,
        )
    return f


def trend_flip(t0: str | None, now: str | None) -> bool:
    """UP* -> DOWN* or DOWN* -> UP* (a REVERSAL, not any change)."""
    return bool(t0 and now and (("UP" in t0 and "DOWN" in now) or ("DOWN" in t0 and "UP" in now)))


def horizon_date(start: date, k: int, cal: Any) -> date:  # helper for tests/docs
    d = start
    for _ in range(k):
        d = cal.next_session(d)
    return d


__all__ = [
    "OBSERVATION_SCHEMA_VERSION",
    "milestones",
    "record_observations",
    "thesis_facts",
    "timedelta",
]
