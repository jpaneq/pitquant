# ruff: noqa: E501
"""Research dataset builder V1 (ADR-0048): continuous features + same-date cross-sectional ranks + targets, written append-only.

* Cohort = the securities of ONE exchange that have a snapshot at the same decision session (first session of the month). Ranks use only features known at that session's open; a cohort smaller than
  ``MIN_COHORT`` gets no rank (``COHORT_TOO_SMALL``). The universe is the CURRENT research universe (survivorship caveat, ``UNIVERSE_NOT_PIT_MEMBERSHIP``): it is not an index membership and never canonical.
* Decision dates inside the sealed holdout are NOT generated. A target whose window touches it is UNAVAILABLE and its outcome is never read (``targets_v1``). Dates from 2025-10-01 are out-of-time (``OOT``) diagnostics.
* A row is written with its feature hash; a second run skips existing (security, decision_at, version): corrections are new versions, never updates.
* Write-time PIT guard: every feature ``available_at`` must be <= ``decision_at``; otherwise ``LookAheadError`` and nothing is written.
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.config.settings import get_settings
from pitquant.core.errors import LookAheadError
from pitquant.core.hashing import content_hash
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import Price, Security, SecurityProfile, TickerHistory
from pitquant.db.models_research import ResearchFeatureSnapshot, ResearchTarget
from pitquant.features.v0.engine import load_facts
from pitquant.market.exchanges import SUFFIX
from pitquant.research import features_v1 as FT
from pitquant.research import fundamentals_v1 as FU
from pitquant.research import targets_v1 as TG

MIN_COHORT = 5
BENCH_TICKERS = ("SPY", "VTI", "URTH", "^IBEX")
COHORT_DEFINITION = "EXCHANGE_SAME_SESSION_OPEN_V1"
REGION = {cal: m for cal, _, m in SUFFIX.values()}
OOT_START = date(2025, 10, 1)


def _commit() -> str | None:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            or None
        )
    except Exception:
        return None


def _ticker(session: Session, sid: str) -> str | None:
    return session.scalars(
        select(TickerHistory.ticker).where(TickerHistory.security_id == sid)
    ).first()


def _profile_sic(session: Session, sec: Security) -> tuple[str | None, str | None]:
    ids = [sec.security_id]
    if sec.issuer_id:
        ids += list(
            session.scalars(select(Security.security_id).where(Security.issuer_id == sec.issuer_id))
        )
    p = session.scalars(
        select(SecurityProfile)
        .where(SecurityProfile.security_id.in_(ids))
        .order_by(SecurityProfile.ingested_at.desc())
    ).first()
    return (p.sic, p.sic_description) if p else (None, None)


def _bundle(
    session: Session, sid: str, ticker: str, exchange: str, now: datetime, *, is_index: bool = False
) -> tuple[FT.SeriesBundle, Any] | None:
    md = load_market(session, sid, now, exchange)
    if md.bars.empty or len(md.bars) < 30:
        return None
    return FT.build_bundle(
        sid,
        ticker,
        exchange,
        md.bars[["open", "high", "low", "close", "volume"]],
        md.actions,
        is_index=is_index,
    ), md


def guard_snapshot(features: dict[str, dict[str, Any]], decision_at: datetime) -> None:
    for name, f in features.items():
        a = f.get("available_at")
        if a is not None and datetime.fromisoformat(a) > decision_at:
            raise LookAheadError(
                f"feature {name}: available_at {a} > decision_at {decision_at.isoformat()}"
            )


def rank_cohort(rows: list[dict[str, Any]]) -> None:
    """Fill ``ranks`` in place: percentile rank in [0, 1] among the NON-missing members, average ties; None with the reason in ``rank_reasons``."""
    n = len(rows)
    names = sorted({k for r in rows for k in r["features"]})
    for r in rows:
        r["ranks"], r["rank_reasons"] = {}, {}
    for name in names:
        vals = [(i, r["features"].get(name, {}).get("value")) for i, r in enumerate(rows)]
        ok = [(i, v) for i, v in vals if v is not None]
        for i, v in vals:
            if v is None:
                rows[i]["ranks"][name], rows[i]["rank_reasons"][name] = None, "MISSING_VALUE"
        if n < MIN_COHORT or len(ok) < MIN_COHORT:
            for i, _ in ok:
                rows[i]["ranks"][name], rows[i]["rank_reasons"][name] = None, "COHORT_TOO_SMALL"
            continue
        s = pd.Series({i: v for i, v in ok}).rank(method="average")
        for i, rk in s.items():
            rows[int(i)]["ranks"][name] = float((rk - 1) / (len(ok) - 1))


def build_research_dataset(
    session: Session,
    *,
    tickers: list[str] | None = None,
    now: datetime | None = None,
    write: bool = True,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    ho = get_settings().validation.final_holdout
    hold = (ho.start, ho.end)
    commit = _commit()
    sec_ids = [sid for (sid,) in session.execute(select(Price.security_id).distinct())]
    secs = [session.get_one(Security, s) for s in sec_ids]
    named = [(s, _ticker(session, s.security_id)) for s in secs if not s.is_synthetic]
    bench: dict[str, tuple[FT.SeriesBundle, pd.DataFrame] | None] = {}
    for t in ("SPY", "URTH", "^IBEX"):
        sid = next((s.security_id for s, tk in named if tk == t), None)
        if sid is None:
            bench[t] = None
            continue
        sec = session.get_one(Security, sid)
        got = _bundle(session, sid, t, sec.exchange, now, is_index=t.startswith("^"))
        bench[t] = (got[0], FT.technical_panel(got[0])) if got else None
    members = [
        (s, tk)
        for s, tk in named
        if tk and tk not in BENCH_TICKERS and (tickers is None or tk in tickers)
    ]
    by_cohort: dict[tuple[str, date], list[dict[str, Any]]] = defaultdict(list)
    skipped: dict[str, str] = {}
    for sec, tk in members:
        got = _bundle(session, sec.security_id, tk, sec.exchange, now)
        if got is None:
            skipped[tk] = "NO_OR_TOO_FEW_BARS"
            continue
        b, md = got
        panel = FT.technical_panel(b)
        contract = TG.benchmark_for(sec.exchange, sec.currency)
        bb = bench.get(contract.ticker)
        facts = load_facts(session, sec.security_id, now)
        sic, sic_desc = _profile_sic(session, sec)
        hist = FU.ValuationHistory()
        cal = get_calendar(sec.exchange)
        d0 = max(b.index[0], cal.first_session)
        for d in cal.first_sessions_of_months(d0, min(b.index[-1], cal.last_session)):
            if hold[0] <= d <= hold[1]:
                continue
            decision_at = cal.session_open(d)
            pos = TG._pos_at(b, decision_at)
            if pos is None:
                continue
            feats = FT.features_at(b, panel, pos)
            prev_day = b.index[pos]
            acts = [a for a in md.actions if a.available_at <= decision_at]
            ff, fmeta = FU.fundamental_features(
                session, sec.security_id, facts, decision_at, sic=sic, last_session=prev_day, raw_close=float(md.bars["close"].iloc[pos]), actions=acts,
                adj_close=float(b.adj["close"].iloc[pos]), history=hist, registered=bool(facts),
            )  # fmt: skip
            feats.update(ff)
            guard_snapshot(feats, decision_at)
            regime = None
            if bb is not None:
                bpos = TG._pos_at(bb[0], decision_at)
                if bpos is not None and not pd.isna(bb[1]["distance_sma200"].iloc[bpos]):
                    regime = "BULL" if bb[1]["distance_sma200"].iloc[bpos] > 0 else "BEAR"
            targets = TG.compute_targets(b, bb[0] if bb else None, contract, decision_at, hold)
            by_cohort[(sec.exchange, d)].append(
                {
                    "security_id": sec.security_id, "decision_at": decision_at, "decision_session": d, "exchange": sec.exchange, "features": feats, "targets": targets,
                    "meta": {
                        "ticker": tk, "currency": sec.currency, "country": sec.country, "region": REGION.get(sec.exchange), "sic": sic, "sic_description": sic_desc, "sector_group": FU.sic_group(sic),
                        "metadata_note": "CURRENT_PROFILE_NOT_PIT: stratification only, not a predictor", "return_type": b.return_type, "benchmark": contract.ticker, "benchmark_type": contract.benchmark_type,
                        "regime": regime, "segment": "OOT" if d >= OOT_START else "DEV", "series_warnings": b.warnings, **fmeta,
                    },
                }
            )  # fmt: skip
    n_snap = n_tgt = 0
    for (_ex, _d), rows in by_cohort.items():
        rank_cohort(rows)
        if not write:
            continue
        for r in rows:
            exists = session.scalar(
                select(ResearchFeatureSnapshot.snapshot_id).where(ResearchFeatureSnapshot.security_id == r["security_id"], ResearchFeatureSnapshot.decision_at == r["decision_at"], ResearchFeatureSnapshot.feature_set_version == FT.FEATURE_SET_VERSION)
            )  # fmt: skip
            if exists:
                continue
            session.add(
                ResearchFeatureSnapshot(
                    security_id=r["security_id"], decision_at=r["decision_at"], decision_session=r["decision_session"], exchange=r["exchange"], feature_set_version=FT.FEATURE_SET_VERSION, cohort_definition=COHORT_DEFINITION,
                    cohort_size=len(rows), features=r["features"], ranks={"ranks": r["ranks"], "reasons": r["rank_reasons"]}, meta=r["meta"], feature_hash=content_hash(r["features"]), code_commit=commit,
                )
            )  # fmt: skip
            n_snap += 1
            for t in r["targets"]:
                session.add(
                    ResearchTarget(
                        security_id=r["security_id"], decision_at=r["decision_at"], horizon_months=t["horizon_months"], target_set_version=TG.TARGET_SET_VERSION, benchmark_id=None, benchmark_ticker=t.get("benchmark_ticker", r["meta"]["benchmark"]),
                        benchmark_type=t.get("benchmark_type", r["meta"]["benchmark_type"]), benchmark_source=t.get("benchmark_source"), entry_session=t.get("entry_session"), exit_session=t.get("exit_session"), label_available_at=t["label_available_at"],
                        status=t["status"], reason=t["reason"], security_total_return=t.get("security_total_return"), benchmark_total_return=t.get("benchmark_total_return"), excess_total_return=t.get("excess_total_return"),
                        outperform=t.get("outperform"), direction_up=t.get("direction_up"), max_drawdown=t.get("max_drawdown"), drawdown_10=t.get("drawdown_10"), drawdown_15=t.get("drawdown_15"), drawdown_20=t.get("drawdown_20"),
                        details=t.get("details", {}),
                    )
                )  # fmt: skip
                n_tgt += 1
    if write:
        session.flush()
    return {
        "_cohorts": by_cohort if not write else None,
        "securities": len(members),
        "skipped": skipped,
        "cohorts": len(by_cohort),
        "snapshots_written": n_snap,
        "targets_written": n_tgt,
        "benchmarks_available": {k: v is not None for k, v in bench.items()},
    }
