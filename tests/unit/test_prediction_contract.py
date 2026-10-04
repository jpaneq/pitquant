# ruff: noqa: E501
"""Prediction contract V1 (ADR-0038): NULL while unavailable, PIT timestamps, no VALIDATED, immutability, outcomes, calibration. SYNTHETIC fixtures only."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pitquant.core.errors import ImmutableRecordError, PITQuantError
from pitquant.db.models import Security
from pitquant.db.models_lab import PredictionSnapshot
from pitquant.prediction import contract
from pitquant.prediction.contract import (
    PredictionContractError,
    PredictionFields,
    record_not_yet_validated,
    validate,
    write_snapshot,
)
from pitquant.prediction.outcomes import CALIBRATION_BUCKETS, calibration, error_fields
from tests.support.synthetic_predictions import synthetic_prediction

T = datetime(2016, 6, 30, 13, 30, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sid(session: Session) -> str:
    s = Security(name="SYN PRED CO", exchange="XNYS", currency="USD")
    session.add(s)
    session.flush()
    return s.security_id


def fields(sid: str, **over: object) -> PredictionFields:
    base: dict[str, object] = {
        "security_id": sid,
        "decision_at": T,
        "generated_at": T,
        "horizon_months": 6,
        "model_id": "EQUITY_6M_BASELINE",
        "model_version": "NOT_TRAINED",
        "feature_set_version": "v0.2:51f",
    }
    base.update(over)
    return PredictionFields(**base)  # type: ignore[arg-type]


def test_not_yet_validated_stores_every_predictive_field_as_null(
    session: Session, sid: str
) -> None:
    row = record_not_yet_validated(
        session,
        sid,
        T,
        6,
        generated_at=T,
        model_id="EQUITY_6M_BASELINE",
        model_version="NOT_TRAINED",
        feature_set_version="v0.2:51f",
    )
    assert row.prediction_status == "NOT_YET_VALIDATED" and not row.is_synthetic
    assert all(getattr(row, k) is None for k in contract.PREDICTIVE_FIELDS)
    assert "NOT_YET_VALIDATED" in row.warnings[0]


def test_a_predictive_value_on_a_not_yet_validated_snapshot_is_refused_in_python_and_by_the_database(
    session: Session, sid: str
) -> None:
    with pytest.raises(PredictionContractError, match="must be NULL"):
        write_snapshot(session, fields(sid, p_outperform=0.7), contract.NOT_YET_VALIDATED)
    # the CHECK constraint is the second line of defence: bypass the Python validator
    sp = session.begin_nested()
    session.add(
        PredictionSnapshot(
            security_id=sid,
            decision_at=T,
            generated_at=T,
            horizon_months=6,
            model_id="m",
            model_version="v",
            feature_set_version="f",
            p_outperform=0.7,
            benchmark="b",
            data_quality={},
            warnings=[],
            prediction_status="NOT_YET_VALIDATED",
            is_synthetic=False,
            provenance={},
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    sp.rollback()


def test_nothing_in_this_build_can_write_validated(session: Session, sid: str) -> None:
    with pytest.raises(PredictionContractError, match="VALIDATED"):
        write_snapshot(
            session,
            fields(sid, p_outperform=0.7, warnings=[contract.SYNTHETIC_WARNING]),
            "VALIDATED",
        )
    sp = session.begin_nested()
    session.add(
        PredictionSnapshot(
            security_id=sid,
            decision_at=T,
            generated_at=T,
            horizon_months=6,
            model_id="m",
            model_version="v",
            feature_set_version="f",
            p_outperform=0.7,
            benchmark="b",
            data_quality={},
            warnings=[],
            prediction_status="VALIDATED",
            is_synthetic=False,
            provenance={},
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    sp.rollback()


def test_no_source_module_assigns_validated_or_writes_synthetic_predictions() -> None:
    """A static guard: product code never assigns status VALIDATED and never creates SYNTHETIC_FIXTURE rows (only the test helper does)."""
    out = subprocess.run(
        [
            "grep",
            "-rnE",
            r"prediction_status\s*=\s*[\"']VALIDATED[\"']|write_snapshot\(.*SYNTHETIC",
            str(ROOT / "src"),
        ],
        capture_output=True,
        text=True,
    ).stdout
    assert out.strip() == "", out
    writers = subprocess.run(
        ["grep", "-rln", "--include=*.py", "write_snapshot", str(ROOT / "src")],
        capture_output=True,
        text=True,
    ).stdout.split()
    assert {Path(p).name for p in writers} <= {"contract.py", "replay.py"} or all(
        "contract.py" in p or "replay.py" in p for p in writers
    )


def test_pit_timestamps_a_prediction_cannot_precede_its_decision_or_use_later_inputs(
    session: Session, sid: str
) -> None:
    with pytest.raises(PredictionContractError, match="before its decision_at"):
        validate(fields(sid, generated_at=T - timedelta(minutes=1)), contract.NOT_YET_VALIDATED)
    with pytest.raises(PredictionContractError, match="look-ahead"):
        validate(
            fields(sid, data_available_at=T + timedelta(seconds=1)), contract.NOT_YET_VALIDATED
        )
    with pytest.raises(PITQuantError, match=r"timezone-naive"):
        validate(
            fields(
                sid,
                decision_at=datetime(2016, 6, 30, 13, 30),
                generated_at=datetime(2016, 6, 30, 13, 30),
            ),
            contract.NOT_YET_VALIDATED,
        )
    with pytest.raises(PredictionContractError, match="horizon"):
        validate(fields(sid, horizon_months=3), contract.NOT_YET_VALIDATED)
    # and the database refuses a look-ahead input even if Python is bypassed
    sp = session.begin_nested()
    session.add(
        PredictionSnapshot(
            security_id=sid,
            decision_at=T,
            generated_at=T,
            horizon_months=6,
            model_id="m",
            model_version="v",
            feature_set_version="f",
            benchmark="b",
            data_quality={},
            warnings=[],
            prediction_status="NOT_YET_VALIDATED",
            is_synthetic=False,
            provenance={},
            data_available_at=T + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    sp.rollback()


def test_a_synthetic_fixture_is_always_labelled_and_internally_coherent(
    session: Session, sid: str
) -> None:
    row = synthetic_prediction(session, sid, T)
    assert (
        row.prediction_status == "SYNTHETIC_FIXTURE"
        and row.is_synthetic
        and "SYNTHETIC TEST DATA" in row.warnings
        and row.provenance["synthetic"] is True
    )
    with pytest.raises(PredictionContractError, match="SYNTHETIC TEST DATA"):
        write_snapshot(session, fields(sid, p_outperform=0.7), contract.SYNTHETIC_FIXTURE)
    with pytest.raises(PredictionContractError, match="non-decreasing"):
        synthetic_prediction(
            session, sid, T + timedelta(days=1), quantiles=(0.1, 0.0, 0.05, 0.2, 0.3)
        )
    with pytest.raises(PredictionContractError, match=r"\[0, 1\]"):
        synthetic_prediction(session, sid, T + timedelta(days=2), p=1.2)
    # a non-synthetic row cannot carry the fixture status and vice versa (CHECK)
    sp = session.begin_nested()
    session.add(
        PredictionSnapshot(
            security_id=sid,
            decision_at=T,
            generated_at=T,
            horizon_months=6,
            model_id="m",
            model_version="v",
            feature_set_version="f",
            benchmark="b",
            data_quality={},
            warnings=[],
            prediction_status="SYNTHETIC_FIXTURE",
            is_synthetic=False,
            provenance={},
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    sp.rollback()


def test_a_snapshot_and_its_model_version_are_immutable(session: Session, sid: str) -> None:
    row = synthetic_prediction(session, sid, T)
    sp = session.begin_nested()
    row.model_version = "synthetic-fixture-2"
    with pytest.raises(ImmutableRecordError):
        session.flush()
    sp.rollback()
    session.refresh(row)
    # a newer model version is a NEW row; the old one is untouched
    a = synthetic_prediction(session, sid, T)
    assert (
        len(
            session.scalars(
                select(PredictionSnapshot).where(PredictionSnapshot.security_id == sid)
            ).all()
        )
        >= 2
        and a.model_version == "synthetic-fixture-1"
    )


def test_postgres_style_bulk_update_is_blocked_by_the_orm_guard(session: Session, sid: str) -> None:
    synthetic_prediction(session, sid, T)
    with pytest.raises(ImmutableRecordError):
        session.execute(PredictionSnapshot.__table__.update().values(model_version="x"))


# ───────────────────────────────────────────── prediction error and calibration (pure)
def test_prediction_error_and_classification_correctness() -> None:
    f = error_fields(0.08, 0.72, 0.03)
    assert (
        f["prediction_error"] == pytest.approx(0.03 - 0.08)
        and f["predicted_outperform"] is True
        and f["classification_correct"] is True
        and f["direction_correct"] is True
    )
    g = error_fields(0.08, 0.72, -0.02)
    assert (
        g["classification_correct"] is False
        and g["direction_correct"] is False
        and g["prediction_error"] == pytest.approx(-0.10)
    )
    assert (
        error_fields(None, 0.4, 0.05)["predicted_outperform"] is False
        and error_fields(None, 0.4, 0.05)["prediction_error"] is None
    )
    assert all(
        v is None for v in error_fields(0.1, 0.7, None).values()
    )  # no actual outcome: nothing is computed


def test_calibration_buckets_compare_predicted_probability_with_observed_frequency() -> None:
    rows = (
        [(0.72, i < 7) for i in range(10)] + [(0.56, i < 5) for i in range(10)] + [(0.52, True)] * 3
    )
    cal = {b["bucket"]: b for b in calibration(rows)}
    assert (
        cal["70-75"]["n"] == 10
        and cal["70-75"]["mean_predicted"] == pytest.approx(0.72)
        and cal["70-75"]["observed_rate"] == pytest.approx(0.7)
        and cal["70-75"]["gap"] == pytest.approx(-0.02)
    )
    assert cal["55-60"]["observed_rate"] == pytest.approx(0.5)
    assert (
        cal["50-55"]["n"] == 3
        and cal["50-55"]["sample"] == "INSUFFICIENT_SAMPLE"
        and cal["50-55"]["observed_rate"] is None
    )  # no rate from 3 observations
    assert [b[0] for b in CALIBRATION_BUCKETS] == [
        "<50",
        "50-55",
        "55-60",
        "60-65",
        "65-70",
        "70-75",
        "75+",
    ]
    assert sum(b["n"] for b in calibration(rows)) == len(rows)
