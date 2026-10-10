#!/usr/bin/env python3
"""Scientific availability only. Future observations are timestamp/null metadata only."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from pitquant.data.archive import ArchiveStore
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import DataSource, FundamentalFact, Price, Security, TickerHistory
from pitquant.db.session import make_engine, make_session_factory
from pitquant.features.v0 import fundamentals as F
from pitquant.market.normalized import CorporateAction, CorporateActionKind, Provenance, SourceTier
from pitquant.research import features_v1 as FT
from pitquant.research import first_ml_contract as C
from pitquant.research import fundamentals_v1 as FV
from pitquant.research import us_coverage_scale as A
from pitquant.research import us_targeted_closure as T
from pitquant.research import us_universe_scale as U
from pitquant.research.dataset_v1 import guard_snapshot

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"
STORE = ArchiveStore(ROOT / "data/archive")


def label_metadata(source_hash: str) -> list[datetime]:
    """Never normalize or compute with prices after the feature history boundary.

    Retain timestamps only for present closes, strictly before the sealed boundary.
    No future numerical value, amount, adjusted close or target is emitted.
    """
    result = json.loads(STORE.get(source_hash))["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    return sorted(
        datetime.fromtimestamp(t, UTC)
        for t, close in zip(result.get("timestamp", []), closes, strict=True)
        if datetime.fromtimestamp(t, UTC).date() < C.HOLDOUT[0] and close is not None
    )


def constructible(
    timestamps: list[datetime],
    benchmark: list[datetime],
    at: datetime,
    legal_start: str | None,
    legal_end: str | None,
) -> tuple[bool, str | None]:
    end = at + relativedelta(months=12)
    if end.date() >= C.HOLDOUT[0]:
        return False, "HOLDOUT_BOUNDARY"
    cal = get_calendar("XNYS")
    expected_entry = cal.session_on_or_before(at.date())
    if cal.session_close(expected_entry) > at:
        expected_entry = cal.session_on_or_before(expected_entry - relativedelta(days=1))
    expected_exit = cal.session_on_or_before(end.date())
    if cal.session_close(expected_exit) > end:
        expected_exit = cal.session_on_or_before(expected_exit - relativedelta(days=1))
    if legal_start and str(expected_entry) < legal_start:
        return False, "ENTRY_BEFORE_LEGAL_SECURITY"
    if legal_end and str(expected_exit) >= legal_end:
        return False, "SUCCESSOR_OR_TERMINAL_EVENT_WITHIN_HORIZON"
    expected = set(cal.sessions(expected_entry, expected_exit))
    for name, instants in (("SECURITY", timestamps), ("BENCHMARK", benchmark)):
        days = {t.date() for t in instants if expected_entry <= t.date() <= expected_exit}
        if not expected <= days:
            return False, name + "_HORIZON_METADATA_GAP"
    return True, None


def actions_for(qa: dict[str, Any], source_hash: str, at: datetime) -> list[CorporateAction]:
    result = []
    for a in qa.get("splits", []) + qa.get("dividends", []):
        available = datetime.fromisoformat(a["available_at"])
        if available >= at:
            continue
        result.append(
            CorporateAction(
                security_key="RESEARCH",
                kind=CorporateActionKind(a["kind"]),
                ex_date=date.fromisoformat(a["ex_date"]),
                available_at=available,
                ratio=a.get("ratio"),
                cash_amount=a.get("cash_amount"),
                currency="USD",
                provenance=Provenance(
                    "YAHOO_CHART", SourceTier.VENDOR, source_hash, source_hash, "yahoo-chart-v1"
                ),
            )
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    source_docs = ROOT / "docs" if args.baseline else WORK / "aliases"
    universe = json.loads((source_docs / "US_LARGE_CAP_RESEARCH_UNIVERSE_V1.json").read_bytes())
    payload = json.loads(
        gzip.decompress((source_docs / "US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz").read_bytes())
    )
    rows = payload["rows"]
    roster = {r["security_id"]: r for r in universe["roster"]}
    series = payload["historical_market_series"]
    db = (
        ROOT / "data/research/us-universe-scale-v1/candidate.db"
        if args.baseline
        else WORK / "candidate.db"
    )
    factory = make_session_factory(make_engine("sqlite:///" + str(db)))
    meta_by_symbol: dict[str, list[datetime]] = {}
    features: dict[tuple[str, str], dict[str, Any]] = {}
    by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["eligibility"]["COMBINED"]:
            by_sid[row["security_id"]].append(row)
    with factory() as session:
        benchmark_sid = session.scalars(
            select(Security.security_id).join(TickerHistory).where(TickerHistory.ticker == "SPY")
        ).one()
        # SELECT only time metadata, never numerical future prices or target tables.
        benchmark = list(
            session.scalars(
                select(Price.bar_close_at)
                .join(DataSource)
                .where(
                    Price.security_id == benchmark_sid,
                    DataSource.name == "YAHOO_CHART:eod",
                    DataSource.is_synthetic.is_(False),
                    Price.session_date < C.HOLDOUT[0],
                )
                .order_by(Price.bar_close_at)
            )
        )
        facts_by_issuer: dict[str, list[F.Fact]] = {}
        for index, (sid, selected) in enumerate(sorted(by_sid.items())):
            r = roster[sid]
            symbol, issuer = selected[0]["price_symbol"], selected[0]["issuer_id"]
            qa = series[symbol]
            source = universe["price_audits"][symbol]["source_hash"]
            if symbol not in meta_by_symbol:
                meta_by_symbol[symbol] = label_metadata(source)
            if issuer not in facts_by_issuer:
                facts_by_issuer[issuer] = [
                    F.Fact(
                        f.concept,
                        f.period_start,
                        f.period_end,
                        float(f.value),
                        f.unit,
                        f.available_at,
                        f.accession_number,
                        f.form,
                        f.revision_id,
                        f.fact_id,
                    )
                    for f in session.scalars(
                        select(FundamentalFact).where(
                            FundamentalFact.issuer_id == issuer,
                            FundamentalFact.available_at < datetime(2021, 10, 1, tzinfo=UTC),
                            FundamentalFact.value.is_not(None),
                            FundamentalFact.concept.in_(
                                sorted(
                                    A.KNOWN_MAPPED_TAGS
                                    | {
                                        "ProfitLoss",
                                        "NetIncomeLossAttributableToNoncontrollingInterest",
                                    }
                                )
                            ),
                        )
                    )
                ]
            history = FV.ValuationHistory()
            bars = [
                b
                for b in qa["bars"]
                if (not r["legal_price_start"] or b["session"] >= r["legal_price_start"])
                and (
                    not r["issuer_history_start_observed"]
                    or b["session"] >= r["issuer_history_start_observed"]
                )
            ]
            frame = pd.DataFrame(
                [{k: b[k] for k in ("open", "high", "low", "close", "volume")} for b in bars],
                index=[date.fromisoformat(b["session"]) for b in bars],
            )
            # Reuse the native causal rolling panel, whose truncation property is tested.
            # Fundamental valuation below still uses the RAW price and only known actions.
            bundle = FT.build_bundle(
                sid,
                symbol,
                "XNYS",
                frame,
                actions_for(qa, source, datetime(2021, 10, 1, tzinfo=UTC)),
            )
            panel = FT.technical_panel(bundle)
            for row in sorted(selected, key=lambda x: x["decision_at"]):
                at = datetime.fromisoformat(row["decision_at"])
                pos = (
                    int(
                        np.searchsorted(
                            bundle.close_instants,
                            np.datetime64(at.replace(tzinfo=None)),
                            side="left",
                        )
                    )
                    - 1
                )
                actions = actions_for(qa, source, at)
                ft = FT.features_at(bundle, panel, pos)
                ff, fm = FV.fundamental_features(
                    session,
                    sid,
                    facts_by_issuer[issuer]
                    if args.baseline
                    else T.parent_income_facts(facts_by_issuer[issuer], at),
                    at,
                    sic=r.get("sic"),
                    last_session=frame.index[pos],
                    raw_close=float(frame.close.iloc[pos]),
                    actions=actions,
                    adj_close=float(frame.close.iloc[pos]),
                    history=history,
                    registered=True,
                )
                ff.update(row["core_fundamentals"])
                all_features = {**ft, **ff}
                guard_snapshot(all_features, at)
                required = set(C.PRICE_FAMILY + C.FUNDAMENTAL_FAMILY + C.RISK_FAMILY)
                full_schema = required <= all_features.keys() and all(
                    all_features[n].get("value") is not None
                    or all_features[n].get("missing_reason")
                    for n in required
                )
                core_ok = all(
                    all_features[n].get("value") is not None
                    and np.isfinite(all_features[n]["value"])
                    for n in C.CORE_PRICE_FEATURES + C.CORE_FUNDAMENTAL_FEATURES
                )
                okay, reason = constructible(
                    meta_by_symbol[symbol],
                    benchmark,
                    at,
                    r["legal_price_start"],
                    r["legal_price_end_exclusive"],
                )
                # SEC 2016 10-K: this was a distribution of a DIFFERENT class,
                # not a same-class split. The present return engine cannot value
                # the distributed class. Exclude overlapping windows explicitly.
                class_distribution = date(2016, 4, 8)
                primary_class_evidence = (
                    "732bfdfa2214e277fba5bc60b81ed2d80f06e18a512dd49d55a09242e2bc539e"
                )
                cross_class = any(
                    a.get("source_hash") == primary_class_evidence and a["ticker"] == "UAA"
                    for a in r.get("dated_ticker_aliases", [])
                )
                if cross_class:
                    if at.date() <= class_distribution <= (at + relativedelta(months=12)).date():
                        okay, reason = False, "UNSUPPORTED_CROSS_CLASS_DISTRIBUTION_IN_LABEL_WINDOW"
                    if frame.index[max(0, pos - 252)] <= class_distribution <= frame.index[pos]:
                        core_ok = False
                features[(sid, row["month"])] = {
                    "feature_valid": bool(
                        full_schema and core_ok and fm["fundamental_status"] == "OK"
                    ),
                    "label_constructible": okay,
                    "label_reason": reason,
                    "nullable_family_features": sorted(
                        n for n in required if all_features[n].get("value") is None
                    ),
                }
            print(f"scientific feature audit {index + 1}/{len(by_sid)}", flush=True)
    scientific = []
    for row in rows:
        checked = features.get((row["security_id"], row["month"]), {})
        statuses = {
            "membership_valid": "MEMBERSHIP" not in row["blockers"],
            "identity_valid": "IDENTITY" not in row["blockers"],
            "price_valid": "PRICE" not in row["blockers"],
            "benchmark_valid": row["reasons"].get("PRICE") != "BENCHMARK_DATA_UNAVAILABLE",
            "fundamental_valid": "FUNDAMENTALS" not in row["blockers"],
            "feature_valid": checked.get("feature_valid", False),
            "label_constructible": checked.get("label_constructible", False),
        }
        scientific.append(
            {
                "security_id": row["security_id"],
                "issuer_id": row["issuer_id"],
                "month": row["month"],
                "sector": row["sector"],
                **statuses,
                "combined_scientific_eligible": all(statuses.values()),
                "feature_and_label_audit": checked,
            }
        )
    name = "scientific-before" if args.baseline else "scientific"
    U.write_revision(WORK, name, scientific)
    (WORK / (name + ".json")).write_bytes(U.encoded(scientific))


if __name__ == "__main__":
    main()
