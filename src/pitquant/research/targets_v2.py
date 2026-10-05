# ruff: noqa: E501
"""Research targets V2 (ADR-0049): ``targets_v1`` computation on a COMPARABLE return basis, with the full benchmark contract stored per row.

The security series is converted to USD at every instant with PIT FX when the benchmark is a USD ETF and the security is not; a benchmark that is not total return (^IBEX price index) never produces an excess
(``NOT_COMPARABLE_RETURN_BASIS``: security return and drawdown are kept, ``excess_total_return`` / ``outperform`` stay NULL). V1 rows are kept (append-only) and superseded by this version.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import get_settings
from pitquant.db.models import Security
from pitquant.db.models_research import FxRate, ResearchFeatureSnapshot, ResearchTarget
from pitquant.research import benchmark_contract as BC
from pitquant.research import dataset_v1 as DS
from pitquant.research import features_v1 as FT
from pitquant.research import targets_v1 as TG
from pitquant.research.fx import FxTable

TARGET_SET_VERSION_V2 = "research-targets-v2"


def to_usd(
    sec: FT.SeriesBundle, currency: str, fx: FxTable
) -> tuple[FT.SeriesBundle, pd.Series, pd.Series]:
    """Security total-return level in USD: level x USD-per-unit known at each bar close (NaN where no rate was known). Returns (bundle, rate date per bar, rate available_at per bar)."""
    rates, rdates, ravail = [], [], []
    for inst in sec.close_instants:
        got = fx.usd_per_unit_at(currency, pd.Timestamp(inst).tz_localize("UTC").to_pydatetime())
        rates.append(np.nan if got is None else got[0])
        rdates.append(None if got is None else got[1])
        ravail.append(None if got is None else got[2])
    r = pd.Series(rates, index=sec.index)
    return (
        replace(sec, level=sec.level * r),
        pd.Series(rdates, index=sec.index, dtype=object),
        pd.Series(ravail, index=sec.index, dtype=object),
    )


def choose(
    exchange: str, currency: str, return_type: str, fx_ready: bool
) -> tuple[BC.BenchmarkSpec, dict[str, str | None], list[str]]:
    """First approved benchmark in preference order; if none is approved, the first candidate with its (non-approved) assessment. ``skipped`` documents the rejected ones."""
    skipped: list[str] = []
    first: tuple[BC.BenchmarkSpec, dict[str, str | None]] | None = None
    for spec in BC.candidates(exchange):
        a = BC.assess(spec, currency, return_type, fx_ready)
        first = first or (spec, a)
        if a["quality_status"] in BC.APPROVED_FOR_ML:
            return spec, a, skipped
        skipped.append(f"{spec.ticker}: {a['quality_status']} ({a['reason']})")
    assert first is not None
    return first[0], first[1], skipped


def build_targets_v2(
    session: Session,
    *,
    now: datetime | None = None,
    tickers: list[str] | None = None,
    canonical_only: bool = False,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    from pitquant.market.canonical import FEATURE_VERSION, TARGET_VERSION

    feature_version = FEATURE_VERSION if canonical_only else FT.FEATURE_SET_VERSION
    target_version = TARGET_VERSION if canonical_only else TARGET_SET_VERSION_V2
    ho = get_settings().validation.final_holdout
    hold = (ho.start, ho.end)
    fx = FxTable.load(session)
    benches: dict[str, tuple[FT.SeriesBundle, Any, str] | None] = {}
    for spec in (BC.SPY, BC.URTH, BC.IBEX_PRICE):
        sid = next(
            (
                s.security_id
                for s in session.scalars(select(Security))
                if DS._ticker(session, s.security_id) == spec.ticker
            ),
            None,
        )
        got = (
            DS._bundle(
                session,
                sid,
                spec.ticker,
                session.get_one(Security, sid).exchange,
                now,
                is_index=spec.ticker.startswith("^"),
                canonical_only=canonical_only,
            )
            if sid
            else None
        )
        benches[spec.ticker] = (got[0], got[1], sid) if got and sid else None
    snaps: dict[str, list[ResearchFeatureSnapshot]] = {}
    for sn in session.scalars(
        select(ResearchFeatureSnapshot).where(
            ResearchFeatureSnapshot.feature_set_version == feature_version
        )
    ):
        snaps.setdefault(sn.security_id, []).append(sn)
    existing = {
        (t.security_id, t.decision_at, t.horizon_months)
        for t in session.scalars(
            select(ResearchTarget).where(ResearchTarget.target_set_version == target_version)
        )
    }
    stats: dict[str, int] = {
        "written": 0,
        "comparable": 0,
        "not_comparable": 0,
        "ok": 0,
        "unavailable": 0,
    }
    by_status: dict[str, int] = {}
    for sid, rows in snaps.items():
        sec = session.get_one(Security, sid)
        tk = DS._ticker(session, sid)
        if tickers and tk not in tickers:
            continue
        got = DS._bundle(session, sid, tk or sid, sec.exchange, now, canonical_only=canonical_only)
        if got is None:
            continue
        b, md = got
        fx_ready = sec.currency == "USD" or sec.currency in fx.series
        spec, assess, skipped = choose(sec.exchange, sec.currency, b.return_type, fx_ready)
        use_usd = assess["return_currency_basis"] == "USD" and sec.currency != "USD"
        bsec, rd, ra = to_usd(b, sec.currency, fx) if use_usd else (b, None, None)
        bench = benches.get(spec.ticker)
        contract = TG.BenchmarkContract(spec.ticker, spec.benchmark_type, spec.source, spec.notes)
        by_status[str(assess["quality_status"])] = (
            by_status.get(str(assess["quality_status"]), 0) + 1
        )
        for sn in rows:
            for t in TG.compute_targets(
                bsec, bench[0] if bench else None, contract, sn.decision_at, hold
            ):
                if (sid, sn.decision_at, t["horizon_months"]) in existing:
                    continue
                comparable = (
                    assess["comparability"] == "COMPARABLE"
                    and t["status"] == "OK"
                    and t.get("benchmark_total_return") is not None
                )
                d: dict[str, Any] = dict(t.get("details", {}))
                d["benchmark_contract"] = {
                    "contract_version": BC.BENCHMARK_CONTRACT_VERSION, "benchmark_id": spec.benchmark_id, "benchmark_security_id": bench[2] if bench else None, "benchmark_name": spec.name, "benchmark_type": spec.benchmark_type,
                    "benchmark_return_type": spec.return_type.value, "benchmark_currency": spec.currency, "security_currency": sec.currency, "return_currency_basis": assess["return_currency_basis"],
                    "currency_conversion_method": assess["currency_conversion_method"], "fx_source": "YAHOO_CHART:fx (CANONICAL_SOURCE, VENDOR)" if use_usd else None, "benchmark_source": spec.source, "benchmark_version": BC.BENCHMARK_CONTRACT_VERSION,
                    "benchmark_provenance": md.sources if md is not None else None, "benchmark_quality_status": assess["quality_status"], "comparability": "COMPARABLE" if comparable else (assess["comparability"] if assess["comparability"] != "COMPARABLE" else "BENCHMARK_UNAVAILABLE_IN_WINDOW"),
                    "skipped_candidates": skipped, "reason": assess["reason"], "security_return_basis": f"{b.return_type}_{assess['return_currency_basis'] or sec.currency}", "benchmark_return_basis": f"{spec.return_type.value}_{spec.currency}",
                }  # fmt: skip
                if t["status"] == "OK" and bench:
                    be, bx = (
                        TG._pos_at(bench[0], sn.decision_at),
                        TG._pos_at(bench[0], TG.add_months(sn.decision_at, t["horizon_months"])),
                    )
                    if be is not None and bx is not None:
                        bc = d["benchmark_contract"]
                        bc.update(
                            benchmark_start_price=float(bench[0].adj["close"].iloc[be]),
                            benchmark_end_price=float(bench[0].adj["close"].iloc[bx]),
                            benchmark_total_return=t.get("benchmark_total_return"),
                        )
                    if use_usd and rd is not None and ra is not None:
                        ei, xi = (
                            b.index.get_loc(t["entry_session"]),
                            b.index.get_loc(t["exit_session"]),
                        )
                        d["benchmark_contract"].update(
                            fx_available_at={
                                "entry": ra.iloc[ei].isoformat()
                                if ra.iloc[ei] is not None
                                else None,
                                "exit": ra.iloc[xi].isoformat()
                                if ra.iloc[xi] is not None
                                else None,
                            },
                            fx_rate_date={"entry": str(rd.iloc[ei]), "exit": str(rd.iloc[xi])},
                        )
                excess = t.get("excess_total_return") if comparable else None
                outp = t.get("outperform") if comparable else None
                stats["written"] += 1
                stats["comparable" if comparable else "not_comparable"] += 1
                stats["ok" if t["status"] == "OK" else "unavailable"] += 1
                session.add(
                    ResearchTarget(
                        security_id=sid, decision_at=sn.decision_at, horizon_months=t["horizon_months"], target_set_version=target_version, benchmark_id=bench[2] if bench else None, benchmark_ticker=spec.ticker, benchmark_type=spec.benchmark_type,
                        benchmark_source=spec.source, entry_session=t.get("entry_session"), exit_session=t.get("exit_session"), label_available_at=t["label_available_at"], status=t["status"], reason=t["reason"], security_total_return=t.get("security_total_return"),
                        benchmark_total_return=t.get("benchmark_total_return") if comparable else None, excess_total_return=excess, outperform=outp, direction_up=t.get("direction_up"), max_drawdown=t.get("max_drawdown"), drawdown_10=t.get("drawdown_10"),
                        drawdown_15=t.get("drawdown_15"), drawdown_20=t.get("drawdown_20"), details=d,
                    )
                )  # fmt: skip
    session.flush()
    return {**stats, "benchmark_quality_by_security": by_status, "fx_currencies": sorted(fx.series)}


__all__ = ["TARGET_SET_VERSION_V2", "FxRate", "build_targets_v2", "choose", "to_usd"]
