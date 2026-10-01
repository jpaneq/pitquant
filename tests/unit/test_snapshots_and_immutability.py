"""Snapshots, reproducibility, immutability and leak-free preprocessing (§25–26, §60, §65–67)."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from pitquant.core.errors import ImmutableRecordError, LookAheadError
from pitquant.db.models import FeatureSnapshotRow, ModelRow, ModelVersion, Prediction
from pitquant.features.preprocessing import (
    TrainOnlyMedianImputer,
    TrainOnlyStandardScaler,
    percentile_rank_cross_section,
    winsorize_cross_section,
)
from pitquant.features.snapshot import FeatureValue, SnapshotBuilder, persist_snapshot
from pitquant.security_master.service import SecurityMaster
from tests.conftest import utc

pytestmark = pytest.mark.pit

AS_OF = utc(2020, 6, 15, 20, 0)


def build(order: list[str], code_version: str = "abc") -> SnapshotBuilder:
    vals = {
        "pe": FeatureValue("pe", 14.2, utc(2020, 5, 1), "fact:1"),
        "mom_12_1": FeatureValue("mom_12_1", 0.12, utc(2020, 6, 15, 20, 0), "px"),
        "roic": FeatureValue("roic", None, None),
    }
    b = SnapshotBuilder("sec-1", AS_OF, "fv1", "dv1", code_version)
    for k in order:
        b.add(vals[k])
    return b


def test_reproducible_snapshot() -> None:
    a = build(["pe", "mom_12_1", "roic"]).freeze()
    b = build(["roic", "pe", "mom_12_1"], code_version="refactor-xyz").freeze()
    assert a.content_hash == b.content_hash  # insertion order and code refactors don't matter
    assert a.missing_mask == {"mom_12_1": False, "pe": False, "roic": True}
    assert a.max_available_at == AS_OF


def test_snapshot_rejects_future_feature() -> None:
    b = build(["pe"])
    b.add(FeatureValue("eps_next", 3.1, utc(2020, 6, 15, 20, 0, 1)))
    with pytest.raises(LookAheadError):
        b.freeze()


def _seed_model(session: Session, frozen: bool) -> tuple[str, str]:
    sec = SecurityMaster(session).register(name="X", exchange="XNYS", currency="USD")
    session.add(ModelRow(model_id="base12", horizon="12m", kind="baseline"))
    session.add(
        ModelVersion(
            model_version="base12-v1",
            model_id="base12",
            scoring_version="s",
            feature_version="f",
            code_version="c",
            config_hash="h",
            seed=1,
            frozen=frozen,
        )
    )
    session.flush()
    return sec.security_id, "base12-v1"


def _prediction(session: Session, sec_id: str, mv: str) -> Prediction:
    b = SnapshotBuilder(sec_id, AS_OF, "fv1", "dv1", "c")
    b.add(FeatureValue("pe", 10.0, utc(2020, 5, 1)))
    row = persist_snapshot(session, b.freeze())
    p = Prediction(
        snapshot_id=row.snapshot_id,
        snapshot_hash=row.content_hash,
        security_id=sec_id,
        as_of=AS_OF,
        execution_at=utc(2020, 6, 16, 13, 30),
        horizon="12m",
        model_version=mv,
        signal="HOLD",
        probability=0.5,
        scores={},
        explanation={},
        data_version="dv1",
        feature_version="fv1",
        scoring_version="s",
        config_hash="h",
        code_version="c",
        seed=1,
    )
    session.add(p)
    session.flush()
    return p


def test_predictions_and_snapshots_are_append_only(session: Session) -> None:
    sec_id, mv = _seed_model(session, frozen=True)
    p = _prediction(session, sec_id, mv)
    session.commit()
    p.signal = "BUY"
    with pytest.raises(ImmutableRecordError):
        session.flush()
    session.rollback()
    session.delete(session.get_one(Prediction, p.prediction_id))
    with pytest.raises(ImmutableRecordError):
        session.flush()
    session.rollback()
    with pytest.raises(ImmutableRecordError):
        session.execute(update(FeatureSnapshotRow).values(content_hash="x"))
    with pytest.raises(ImmutableRecordError):
        session.execute(delete(Prediction))


def test_model_version_immutability(session: Session) -> None:
    _seed_model(session, frozen=False)
    session.commit()
    mv = session.get_one(ModelVersion, "base12-v1")
    mv.params = {"w": 1}
    mv.frozen = True  # unfrozen -> frozen is allowed (once)
    session.commit()
    mv.params = {"w": 2}
    with pytest.raises(ImmutableRecordError):
        session.flush()


def test_scaler_train_only() -> None:
    train = pd.DataFrame({"x": [1.0, 2.0, 3.0]}, index=[0, 1, 2])
    test = pd.DataFrame({"x": [100.0, 200.0]}, index=[3, 4])
    s1 = TrainOnlyStandardScaler().fit(train)
    s2 = TrainOnlyStandardScaler().fit(train)
    _ = s2.transform(test * 1000)  # whatever test looks like, fitted params are identical
    assert s1.mean_.equals(s2.mean_) and s1.std_.equals(s2.std_)  # type: ignore[union-attr]
    assert s1.mean_["x"] == 2.0  # type: ignore[index]
    assert s1.fit_fingerprint == s2.fit_fingerprint


def test_imputer_train_only() -> None:
    train = pd.DataFrame({"x": [1.0, 3.0, None]}, index=[0, 1, 2])
    test = pd.DataFrame({"x": [None, 50.0]}, index=[3, 4])
    imp = TrainOnlyMedianImputer().fit(train)
    filled, mask = imp.transform(test)
    assert filled.loc[3, "x"] == 2.0  # train median, not influenced by test's 50
    assert bool(mask.loc[3, "x"]) and not bool(mask.loc[4, "x"])


def test_cross_sectional_transforms_never_mix_dates() -> None:
    df = pd.DataFrame(
        {
            "as_of": ["2020-01"] * 4 + ["2020-02"] * 4,
            "x": [1.0, 2.0, 3.0, 100.0, 1000.0, 2000.0, 3000.0, 4000.0],
        }
    )
    r1 = percentile_rank_cross_section(df.iloc[:4], ["x"])
    r_all = percentile_rank_cross_section(df, ["x"])
    assert r1["x_pct"].tolist() == r_all["x_pct"].iloc[:4].tolist()  # future dates change nothing
    w1 = winsorize_cross_section(df.iloc[:4], ["x"], lower=0.0, upper=0.75)
    w_all = winsorize_cross_section(df, ["x"], lower=0.0, upper=0.75)
    assert w1["x"].tolist() == w_all["x"].iloc[:4].tolist()


# ORM-level counterparts of the PostgreSQL trigger tests (tests/integration/test_postgres.py).


def _committed_prediction(session: Session) -> Prediction:
    sec_id, mv = _seed_model(session, frozen=True)
    p = _prediction(session, sec_id, mv)
    session.commit()
    return p


def test_prediction_update_rejected(session: Session) -> None:
    p = _committed_prediction(session)
    p.probability = 0.9
    with pytest.raises(ImmutableRecordError):
        session.flush()


def test_prediction_delete_rejected(session: Session) -> None:
    p = _committed_prediction(session)
    session.delete(p)
    with pytest.raises(ImmutableRecordError):
        session.flush()


def test_snapshot_update_rejected(session: Session) -> None:
    p = _committed_prediction(session)
    snap = session.get_one(FeatureSnapshotRow, p.snapshot_id)
    snap.features = {"pe": 99.0}
    with pytest.raises(ImmutableRecordError):
        session.flush()


def test_snapshot_delete_rejected(session: Session) -> None:
    p = _committed_prediction(session)
    session.delete(session.get_one(FeatureSnapshotRow, p.snapshot_id))
    with pytest.raises(ImmutableRecordError):
        session.flush()
