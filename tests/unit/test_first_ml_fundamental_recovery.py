from copy import deepcopy
from datetime import UTC, date, datetime, timedelta

import pytest

from pitquant.features.v0 import fundamentals as F
from pitquant.research.fundamental_recovery import TAG_VERSION, repair_features, reported_total_debt

AT = datetime(2015, 2, 2, 14, tzinfo=UTC)


def facts():
    return [
        F.Fact(
            tag,
            None,
            date(2014, 11, 28),
            value,
            "USD",
            AT - timedelta(days=10),
            "SYNTHETIC-ACC",
            "10-K",
        )
        for tag, value in (
            ("DebtAndCapitalLeaseObligations", 100),
            ("CapitalLeaseObligations", 10),
            ("Assets", 200),
            ("StockholdersEquity", 100),
        )
    ]


def features():
    return {
        "fund_debt_to_assets": {"value": None, "available_at": None},
        "fund_debt_to_equity": {"value": None, "available_at": None},
        "ret_12m": {"value": 0.3, "available_at": None},
        "fund_current_ratio": {"value": None, "available_at": None},
    }


@pytest.mark.pit
def test_latest_known_state_propagates_and_future_revision_does_not_backdate():
    fs = facts()
    before = reported_total_debt(fs, AT)
    assert before.value == 100
    fs.append(
        F.Fact(
            "DebtAndCapitalLeaseObligations",
            None,
            date(2014, 11, 28),
            130,
            "USD",
            AT + timedelta(days=10),
            "SYNTHETIC-RESTATED",
            "10-K/A",
        )
    )
    assert reported_total_debt(fs, AT).value == 100
    assert reported_total_debt(fs, AT + timedelta(days=20)).value == 130
    assert reported_total_debt(fs, AT - timedelta(days=20)).value is None


@pytest.mark.pit
def test_available_at_equality_keeps_existing_strict_semantics():
    assert reported_total_debt(facts(), AT - timedelta(days=10)).value is None


def test_no_missing_as_zero_or_stale_period_substitution():
    assert (
        reported_total_debt(
            [f for f in facts() if f.concept != "DebtAndCapitalLeaseObligations"], AT
        ).value
        is None
    )
    fs = [f for f in facts() if f.concept != "DebtAndCapitalLeaseObligations"]
    fs.append(
        F.Fact(
            "DebtAndCapitalLeaseObligations",
            None,
            date(2013, 11, 28),
            100,
            "USD",
            AT - timedelta(days=10),
            "SYN",
            "10-K",
        )
    )
    assert reported_total_debt(fs, AT).value == 100
    fs.append(
        F.Fact(
            "LongTermDebtAndCapitalLeaseObligations",
            None,
            date(2014, 11, 28),
            100,
            "USD",
            AT - timedelta(days=10),
            "SYN",
            "10-K",
        )
    )
    assert reported_total_debt(fs, AT).value == 100


def test_mapping_versioned_no_global_imputation_price_unchanged():
    original = features()
    prior = deepcopy(original)
    a = repair_features(original, facts(), AT, supported=True)
    assert original == prior
    assert a["fund_debt_to_assets"]["value"] == 0.5
    assert a["fund_debt_to_equity"]["value"] == 1.0
    assert a["fund_current_ratio"]["value"] is None
    assert a["ret_12m"] == original["ret_12m"]
    assert a["fund_debt_to_assets"]["mapping_version"] == TAG_VERSION == "sec-tags-4"
    assert a == repair_features(original, facts(), AT, supported=True)


def test_supported_only_and_existing_version_never_mutated():
    original = features()
    assert repair_features(original, facts(), AT, supported=False) == original
    original["fund_debt_to_assets"]["value"] = 0.1
    assert (
        repair_features(original, facts(), AT, supported=True)["fund_debt_to_assets"]["value"]
        == 0.5
    )
    assert original["fund_debt_to_assets"]["value"] == 0.1


def test_optional_missing_eligible_but_mandatory_missing_blocks():
    from pitquant.research.first_ml import first_ml_eligibility
    from tests.unit.test_first_ml_readiness import ctx, snap, tgt

    s = snap()
    s["features"]["fund_current_ratio"] = None
    assert first_ml_eligibility(ctx(), s, tgt(), family="FUNDAMENTALS")["eligible"]
    s["features"]["fund_debt_to_assets"] = None
    assert not first_ml_eligibility(ctx(), s, tgt(), family="FUNDAMENTALS")["eligible"]


def test_component_periods_must_match():
    fs = [f for f in facts() if f.concept != "DebtAndCapitalLeaseObligations"]
    fs.append(
        F.Fact(
            "LongTermDebtAndCapitalLeaseObligations",
            None,
            date(2014, 11, 28),
            90,
            "USD",
            AT - timedelta(days=10),
            "SYN",
            "10-K",
        )
    )
    assert reported_total_debt(fs, AT).value is None
    fs.append(
        F.Fact(
            "DebtCurrent",
            None,
            date(2013, 11, 28),
            10,
            "USD",
            AT - timedelta(days=10),
            "SYN",
            "10-K",
        )
    )
    assert reported_total_debt(fs, AT).value is None
    fs.append(
        F.Fact(
            "DebtCurrent",
            None,
            date(2014, 11, 28),
            10,
            "USD",
            AT - timedelta(days=10),
            "SYN",
            "10-K",
        )
    )
    assert reported_total_debt(fs, AT).value == 100


@pytest.mark.pit
def test_rebuild_append_only_idempotent_excludes_holdout_oot(session, monkeypatch):
    from sqlalchemy import select

    from pitquant.core.hashing import content_hash
    from pitquant.db.models import Security
    from pitquant.db.models_research import ResearchFeatureSnapshot
    from pitquant.market.canonical import FEATURE_VERSION as BASE
    from pitquant.research import fundamental_recovery as R

    sec = Security(name="SYNTHETIC RECOVERY", exchange="XNYS", currency="USD", is_synthetic=True)
    session.add(sec)
    session.flush()
    original_features = features()
    for at in (AT, datetime(2023, 1, 2, 14, tzinfo=UTC), datetime(2026, 1, 2, 14, tzinfo=UTC)):
        session.add(
            ResearchFeatureSnapshot(
                security_id=sec.security_id,
                decision_at=at,
                decision_session=at.date(),
                exchange="XNYS",
                feature_set_version=BASE,
                cohort_definition="SYNTHETIC",
                cohort_size=1,
                features=deepcopy(original_features),
                ranks={"ranks": {"ret_12m": 0.42}, "reasons": {}},
                meta={"fundamental_status": "OK"},
                feature_hash=content_hash(original_features),
            )
        )
    session.commit()
    monkeypatch.setattr(R, "load_facts", lambda *args: facts())
    result = R.rebuild(session)
    session.commit()
    assert result["rows_added"] == 1
    assert R.rebuild(session)["rows_added"] == 0
    new = session.scalars(
        select(ResearchFeatureSnapshot).where(
            ResearchFeatureSnapshot.feature_set_version == R.FEATURE_VERSION
        )
    ).one()
    assert new.decision_at == AT
    assert new.ranks["ranks"]["ret_12m"] == 0.42
    original = session.scalars(
        select(ResearchFeatureSnapshot).where(
            ResearchFeatureSnapshot.feature_set_version == BASE,
            ResearchFeatureSnapshot.decision_at == AT,
        )
    ).one()
    assert original.features == original_features
    assert new.features["fund_current_ratio"]["value"] is None


def test_unknown_absence_not_misrepresented_as_true_pit_or_recoverable():
    from scripts.gen_first_ml_fundamental_gap import primary_reason

    reason, category = primary_reason({"visible_facts": 0})
    assert reason == "NO_SEC_IDENTITY"
    assert category == "UNVERIFIED_HISTORICAL_ISSUER_COVERAGE"
    reason, category = primary_reason(
        {
            "visible_facts": 10,
            "core": {"fund_debt_to_assets": {"value": None, "reason": "unresolved_tag"}},
        }
    )
    assert reason == "XBRL_TAG_UNMAPPED"
    assert category != "RECOVERABLE_PIPELINE_MISSINGNESS"
    assert primary_reason({"unsupported": True}) == (
        "UNSUPPORTED_SECTOR",
        "STRUCTURAL_CONTRACT_EXCLUSION",
    )
