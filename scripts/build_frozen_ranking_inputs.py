"""Reconstruct exactly the frozen scientific cohort; sealed future observations are excluded."""

from __future__ import annotations

import gzip
import importlib.util
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select

from pitquant.data.archive import ArchiveStore
from pitquant.db.models import FundamentalFact, Security, TickerHistory
from pitquant.db.session import make_engine, make_session_factory
from pitquant.features.v0 import fundamentals as F
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
from pitquant.research import features_v1 as FT
from pitquant.research import first_ml_contract as C
from pitquant.research import fundamentals_v1 as FV
from pitquant.research import targets_v1 as TG
from pitquant.research import us_coverage_scale as A
from pitquant.research import us_targeted_closure as T
from pitquant.research.dataset_v1 import _bundle, guard_snapshot
from pitquant.research.ranking_preregistration import (
    DATASET,
    EXPERIMENT,
    digest,
    encoded,
    file_digest,
    verify_frozen_dataset,
    verify_manifest,
    write_once,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/equity-ranking-v0"
STORE = ArchiveStore(ROOT / "data/archive")


def source_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "frozen_scientific_auditor", ROOT / "scripts/audit_us_scientific_constructibility.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def target_bundle(symbol: str, sid: str, sha: str, roster: dict[str, Any]) -> FT.SeriesBundle:
    """Extract only pre-holdout OHLC observations. Never normalize sealed price rows."""
    result = json.loads(STORE.get(sha))["chart"]["result"][0]
    ts = result.get("timestamp", [])
    indices = [i for i, t in enumerate(ts) if datetime.fromtimestamp(t, UTC).date() < C.HOLDOUT[0]]
    quote = result["indicators"]["quote"][0]
    # Later split metadata only reverses vendor split adjustment; it is not a feature/outcome.
    clean = {
        "meta": {
            k: result["meta"][k] for k in ("symbol", "currency", "gmtoffset") if k in result["meta"]
        },
        "timestamp": [ts[i] for i in indices],
        "indicators": {"quote": [{k: [values[i] for i in indices] for k, values in quote.items()}]},
        "events": {
            "splits": result.get("events", {}).get("splits", {}),
            "dividends": {
                k: v
                for k, v in result.get("events", {}).get("dividends", {}).items()
                if datetime.fromtimestamp(v["date"], UTC).date() < C.HOLDOUT[0]
            },
        },
    }
    normalized = YahooChartMarketDataProvider().normalize(
        sid,
        symbol,
        encoded({"chart": {"result": [clean], "error": None}}),
        now=datetime(2022, 9, 30, 23, 59, tzinfo=UTC),
    )
    bars = [
        b
        for b in normalized.bars
        if (
            not roster.get("legal_price_start")
            or str(b.session_date) >= roster["legal_price_start"]
        )
        and (
            not roster.get("issuer_history_start_observed")
            or str(b.session_date) >= roster["issuer_history_start_observed"]
        )
        and (
            not roster.get("legal_price_end_exclusive")
            or str(b.session_date) < roster["legal_price_end_exclusive"]
        )
    ]
    frame = pd.DataFrame(
        [
            {"open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume}
            for b in bars
        ],
        index=[b.session_date for b in bars],
    )
    return FT.build_bundle(
        sid,
        symbol,
        "XNYS",
        frame,
        [a for a in normalized.actions if a.available_at.date() < C.HOLDOUT[0]],
    )


def main() -> None:
    d = json.loads((ROOT / "docs" / (DATASET + "_MANIFEST.json")).read_bytes())
    m = json.loads((ROOT / "docs" / (EXPERIMENT + "_MANIFEST.json")).read_bytes())
    verify_manifest(m)
    verify_frozen_dataset(d, ROOT)
    if m["contracts"]["dataset"]["sha256"] != d["dataset_sha256"]:
        raise ValueError("frozen dataset mismatch")
    for path, sha in m["contracts"]["features"]["engine_hashes"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("frozen engine mismatch")
    print("Frozen hashes verified, no outcomes read", flush=True)
    candidate = json.loads(gzip.decompress((ROOT / d["candidate"]["path"]).read_bytes()))
    base_path = ROOT / d["layers"]["price"]["baseline_series_path"]
    if file_digest(base_path) != d["layers"]["price"]["baseline_series_file_sha256"]:
        raise ValueError("baseline prices changed")
    baseline = json.loads(gzip.decompress(base_path.read_bytes()))
    series = {**baseline["historical_market_series"], **candidate["additional_price_series"]}
    del baseline
    roster = {r["security_id"]: r for r in d["layers"]["identity"]["roster"]}
    science = {
        (r["security_id"], r["month"]): r
        for r in candidate["scientific_rows"]
        if r["combined_scientific_eligible"]
    }
    expected = {f"{r['security_id']}:{r['month']}" for r in science.values()}
    by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate["rows"]:
        if row["eligibility"]["COMBINED"]:
            by_sid[row["security_id"]].append(row)
    helpers = source_helpers()
    db = ROOT / d["database_snapshot"]["path"]
    factory = make_session_factory(
        make_engine("sqlite:///file:" + str(db) + "?mode=ro&immutable=1&uri=true")
    )
    qa = d["layers"]["price"]["qa"]
    records = []
    with factory() as session:
        benchmark_sid = session.scalars(
            select(Security.security_id).join(TickerHistory).where(TickerHistory.ticker == "SPY")
        ).one()
        got = _bundle(
            session,
            benchmark_sid,
            "SPY",
            "XNYS",
            datetime(2022, 9, 30, 23, 59, tzinfo=UTC),
            canonical_only=True,
        )
        if got is None:
            raise ValueError("frozen benchmark unavailable")
        benchmark = got[0]
        facts_by_issuer: dict[str, list[F.Fact]] = {}
        for idx, (sid, selected) in enumerate(sorted(by_sid.items())):
            if not any((sid, r["month"]) in science for r in selected):
                continue
            r = roster[sid]
            symbol = selected[0]["price_symbol"]
            issuer = selected[0]["issuer_id"]
            q = series[symbol]
            sha = qa[symbol]["source_hash"]
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
            bars = [
                b
                for b in q["bars"]
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
            bundle = FT.build_bundle(
                sid,
                symbol,
                "XNYS",
                frame,
                helpers.actions_for(q, sha, datetime(2021, 10, 1, tzinfo=UTC)),
            )
            panel = FT.technical_panel(bundle)
            history = FV.ValuationHistory()
            future = target_bundle(symbol, sid, sha, r)
            for row in sorted(selected, key=lambda z: z["decision_at"]):
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
                ft = FT.features_at(bundle, panel, pos)
                ff, fm = FV.fundamental_features(
                    session,
                    sid,
                    T.parent_income_facts(facts_by_issuer[issuer], at),
                    at,
                    sic=r.get("sic"),
                    last_session=frame.index[pos],
                    raw_close=float(frame.close.iloc[pos]),
                    actions=helpers.actions_for(q, sha, at),
                    adj_close=float(frame.close.iloc[pos]),
                    history=history,
                    registered=True,
                )
                ff.update(row["core_fundamentals"])
                features = {**ft, **ff}
                guard_snapshot(features, at)
                if (sid, row["month"]) not in science:
                    continue
                frozen = science[(sid, row["month"])]["feature_and_label_audit"]
                nullable = sorted(n for n in C.M4.features if features[n].get("value") is None)
                if (
                    nullable != frozen["nullable_family_features"]
                    or fm["fundamental_status"] != "OK"
                ):
                    raise ValueError("scientific feature reconstruction mismatch")
                target = TG.compute_targets(
                    future, benchmark, TG.US, at, C.HOLDOUT, horizons=(12,)
                )[0]
                if target["status"] != "OK" or target.get("excess_total_return") is None:
                    raise ValueError(
                        f"frozen label constructibility violated: {sid} {row['month']} {target}"
                    )
                records.append(
                    {
                        "security_id": sid,
                        "issuer_id": issuer,
                        "month": row["month"],
                        "decision_at": row["decision_at"],
                        "sector": row["sector"],
                        "features": {n: features[n] for n in C.M4.features},
                        "target_end": TG.add_months(at, 12).isoformat(),
                        "label_available_at": target["label_available_at"].isoformat(),
                        "actual_target": int(target["outperform"]),
                        "excess_return": target["excess_total_return"],
                        "target_provenance": {
                            "price_source": sha,
                            "benchmark_source": d["database_snapshot"]["sha256"],
                            "entry_session": str(target["entry_session"]),
                            "exit_session": str(target["exit_session"]),
                        },
                    }
                )
            print(f"Frozen reconstruction {idx + 1}/{len(by_sid)} rows={len(records)}", flush=True)
    records.sort(key=lambda z: (z["month"], z["issuer_id"]))
    if {f"{r['security_id']}:{r['month']}" for r in records} != expected or len(records) != 16717:
        raise ValueError("cohort row loss")
    payload = {
        "experiment_id": EXPERIMENT,
        "dataset_sha256": d["dataset_sha256"],
        "rows": records,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
    }
    raw = encoded(payload)
    write_once(OUT / "inputs.json.gz", gzip.compress(raw, mtime=0))
    write_once(
        OUT / "inputs-integrity.json",
        encoded(
            {
                "sha256": digest(payload),
                "compressed_sha256": file_digest(OUT / "inputs.json.gz"),
                "rows": len(records),
                "frozen_dataset_sha256": d["dataset_sha256"],
            }
        ),
    )
    print("Frozen input construction complete", digest(payload), flush=True)


if __name__ == "__main__":
    main()
