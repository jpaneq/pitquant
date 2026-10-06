#!/usr/bin/env python3
# ruff: noqa: E501
"""Prepare/freeze first; a separate explicit run command fits only frozen DEV rows."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import get_settings
from pitquant.core.hashing import content_hash
from pitquant.db.models import Security
from pitquant.db.models_research import ResearchFeatureSnapshot, ResearchTarget
from pitquant.db.session import make_engine, make_session_factory
from pitquant.positions import review as V0
from pitquant.positions.backtest import context_at
from pitquant.research import equity_baseline as E
from pitquant.research import first_ml_contract as C

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ART = ROOT / "data/research/FIRST_EQUITY_ML_12M_V0"
MANIFEST = DOCS / "FIRST_EQUITY_ML_12M_V0_MANIFEST.json"


def code_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def prepare() -> None:
    if MANIFEST.exists():
        raise ValueError("manifest already frozen; run or verify, never overwrite")
    coverage = json.loads((DOCS / "FIRST_ML_COVERAGE_AUDIT.json").read_text())
    audit = json.loads((DOCS / "FIRST_ML_FOLD_AUDIT.json").read_text())
    if not coverage["ready"] or len(coverage["folds"]) != 3:
        raise ValueError("readiness not certified")
    code = code_sha()
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    ).strip():
        raise ValueError("commit experiment code before freezing")
    created = datetime.now(UTC).isoformat()
    factory = make_session_factory(make_engine(f"sqlite:///{ROOT / 'data/pitquant.db'}"))
    folds = []
    with factory() as session:
        svc = AnalyzerService(session, get_settings())
        for cf, af in zip(coverage["folds"], audit["folds"], strict=True):
            if not cf["passes"] or not af["label_safe"]:
                raise ValueError("invalid frozen fold")
            fold: dict[str, Any] = {
                "index": cf["index"] + 1,
                "fit_at": cf["fit_at"],
                "dates": cf["dates"],
                "test_cohort_hash": cf["PRIMARY_COMMON_COHORT"]["TEST"]["cohort_sha256"],
            }
            for role in ("TRAIN", "TEST"):
                cohort = cf["PRIMARY_COMMON_COHORT"][role]
                if E.digest(cohort["observation_keys"]) != cohort["cohort_sha256"]:
                    # Frozen cohort hash uses compact JSON observation keys.
                    raise ValueError("cohort hash mismatch")
                audited = {(r["security_id"], r["decision_at"]): r for r in af[role]["rows"]}
                rows = []
                for sid, at in cohort["observation_keys"]:
                    a = datetime.fromisoformat(at)
                    ar = audited[sid, at]
                    if not ar["label_eligible"] or ar["touches_holdout"] or ar["touches_oot"]:
                        raise ValueError("unsafe frozen row")
                    # Key-bounded queries: neither holdout nor OOT outcome rows are fetched.
                    snap = session.scalars(
                        select(ResearchFeatureSnapshot).where(
                            ResearchFeatureSnapshot.security_id == sid,
                            ResearchFeatureSnapshot.decision_at == a,
                            ResearchFeatureSnapshot.feature_set_version
                            == coverage["feature_set_version"],
                        )
                    ).one()
                    if content_hash(snap.features) != snap.feature_hash:
                        raise ValueError("feature hash mismatch")
                    target = session.scalars(
                        select(ResearchTarget).where(
                            ResearchTarget.security_id == sid,
                            ResearchTarget.decision_at == a,
                            ResearchTarget.target_set_version == coverage["target_set_version"],
                            ResearchTarget.horizon_months == 12,
                            ResearchTarget.exit_session < C.HOLDOUT[0],
                        )
                    ).one()
                    security = session.get_one(Security, sid)
                    if (
                        security.issuer_id != ar["issuer_id"]
                        or target.status != "OK"
                        or target.excess_total_return is None
                    ):
                        raise ValueError("identity/target mismatch")
                    row = {
                        "security_id": sid,
                        "issuer_id": security.issuer_id,
                        "decision_at": at,
                        "snapshot_id": snap.snapshot_id,
                        "feature_hash": snap.feature_hash,
                        "features": snap.features,
                        "ranks_hash": content_hash(snap.ranks),
                        "actual_target": int(target.outperform),
                        "excess_return": target.excess_total_return,
                        "benchmark_id": target.benchmark_id,
                        "target_id": target.target_id,
                        "target_end": ar["target_end"],
                        "label_available_at": target.label_available_at.isoformat(),
                        "regime": snap.meta.get("regime"),
                        "source_meta": snap.meta,
                    }
                    E.assert_row(row, role, fold["fit_at"])
                    if role == "TEST":
                        tech = svc.technicals(sid, a)
                        price = tech.get("last_close_split_adjusted")
                        if price is None:
                            raise ValueError("V0 historical context unavailable")
                        ctx = context_at(svc, sid, a, price, with_labels=True)
                        if ctx is None:
                            raise ValueError("V0 context unavailable")
                        rv = V0.review(V0.Position(price, 1.0, a, 12), ctx, a)
                        row["v0_score"] = rv["score"]
                        row["v0_trace"] = rv
                        row["v0_context"] = asdict(ctx)
                    # Full source validated above; only frozen family inputs enter models.
                    row["features"] = {name: snap.features[name] for name in C.M4.features}
                    rows.append(row)
                fold[role] = rows
                print(f"F{fold['index']} {role}: {len(rows)}", flush=True)
            folds.append(fold)
    data = {
        "scope": "PRIMARY_COMMON_COHORT",
        "folds": folds,
        "holdout_outcome_rows_accessed": 0,
        "oot_outcome_rows_accessed": 0,
    }
    data_hash = E.immutable_json(ART / "dataset.json", data)
    contracts = {
        "feature": {m.model_id: list(m.features) for m in C.MODELS},
        "target": {
            "target": coverage["target"],
            "version": coverage["target_set_version"],
            "source": (ROOT / "src/pitquant/research/targets_v2.py").read_text(),
        },
        "coverage": {
            "version": coverage["version"],
            "thresholds": coverage["thresholds"],
            "audit_hash": E.digest(coverage),
        },
        "fold": [
            {"dates": f["dates"], "fit_at": f["fit_at"], "common": f["PRIMARY_COMMON_COHORT"]}
            for f in coverage["folds"]
        ],
    }
    manifest = {
        "experiment_id": C.EXPERIMENT_ID,
        "created_at": created,
        "source_sha": "9f1bf55e0a2f46f0181ba9925a96d5523ad9981b",
        "branch": "codex/first-equity-ml-baseline-12m",
        "code_sha": code,
        "data_snapshot_hash": data_hash,
        **{
            name + "_contract_hash" if name != "fold" else "fold_hash": E.digest(contract)
            for name, contract in contracts.items()
        },
        "contracts": contracts,
        "dataset_version": coverage["feature_set_version"],
        "coverage_version": coverage["version"],
        "membership_version": "d02-membership-evidence-v1",
        "sec_mapping_version": "sec-tags-4",
        "market_version": "yahoo-market-data-v1",
        "benchmark_source_hash": content_hash(
            (ROOT / "src/pitquant/research/benchmark_contract.py").read_text()
        ),
        "model_specs": {
            "M0": "TRAIN mean label; constant TEST probability",
            "M1": {
                "engine": V0.ENGINE_VERSION,
                "source_sha256": E.digest((ROOT / "src/pitquant/positions/review.py").read_text()),
                "adapter": (
                    "positions.backtest.context_at / AnalyzerService; "
                    "12M fresh hypothetical position; raw score, no probability"
                ),
            },
            "M2": E.PARAMS,
            "M3": E.PARAMS,
            "M4": E.PARAMS,
        },
        "model_spec_hash": E.digest(E.PARAMS),
        "benchmark_contract_version": "benchmark-contract-1",
        "interpretation_rule": {
            "STRONG_PROMISING_SIGNAL": "At least one ML improves AUC and Brier vs M0 in every fold, with paired pooled AUC CI entirely positive and Brier CI entirely negative",
            "PROMISING_BUT_UNSTABLE": "Otherwise at least one ML paired pooled AUC CI entirely positive, with positive AUC delta in >=2 folds",
            "WEAK_SIGNAL": "Otherwise at least one ML pooled AUC > 0.50 with positive AUC delta in >=2 folds",
            "NO_MEANINGFUL_SIGNAL": "Otherwise",
            "warning": "Exploratory 36-month DEV evidence; no production validation",
        },
        "preprocessing": E.PREPROCESSING,
        "preprocessing_hash": E.digest(E.PREPROCESSING),
        "seeds": {"model": E.SEED, "bootstrap": E.SEED},
        "bootstrap_repetitions": 1000,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in (
                    "numpy",
                    "scipy",
                    "scikit-learn",
                    "pandas",
                    "sqlalchemy",
                    "threadpoolctl",
                )
            },
        },
        "status": E.STATUS,
        "secondary_native": "NOT_RUN_OPTIONAL_DIAGNOSTIC",
        "no_selection": True,
        "no_rebalancing": True,
        "no_threshold_tuning": True,
    }
    manifest["model_spec_hash"] = E.digest(manifest["model_specs"])
    manifest["manifest_hash"] = E.digest(manifest)
    E.immutable_json(MANIFEST, manifest)
    print("FROZEN", manifest["manifest_hash"])


def run() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if code_sha() != manifest["code_sha"]:
        raise ValueError("run exactly frozen code SHA; changed code requires revision")
    if (
        E.digest({k: v for k, v in manifest.items() if k != "manifest_hash"})
        != manifest["manifest_hash"]
    ):
        raise ValueError("manifest altered")
    data = json.loads((ART / "dataset.json").read_text())
    if E.digest(data) != manifest["data_snapshot_hash"]:
        raise ValueError("dataset altered")
    E.immutable_json(ART / "TRAINING_STARTED.json", {"manifest_hash": manifest["manifest_hash"]})
    report, predictions, artifacts = E.run_models(data, manifest)
    report["oof_hash"] = E.immutable_json(ART / "oof_predictions.json", predictions)
    report["model_artifacts_hash"] = E.immutable_json(ART / "model_artifacts.json", artifacts)
    E.immutable_json(DOCS / "FIRST_EQUITY_ML_12M_V0_REPORT.json", report)
    E.immutable_json(DOCS / "FIRST_EQUITY_ML_12M_V0_OOF.json", predictions)
    E.immutable_json(DOCS / "FIRST_EQUITY_ML_12M_V0_MODELS.json", artifacts)
    print("OOF", report["oof_hash"])
    for name, values in report["POOLED_DEV_OOF"].items():
        print(name, {k: values[k] for k in ("auc", "ap", "brier", "log_loss", "rank_ic")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "run"])
    args = parser.parse_args()
    prepare() if args.action == "prepare" else run()
