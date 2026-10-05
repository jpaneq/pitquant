"""Synthetic evidence only; never presented as historical observations."""

from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from pitquant.core.errors import DataQualityError, ImmutableRecordError
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive
from pitquant.research import first_ml as FM
from pitquant.research.membership_evidence import (
    UA_C,
    UA_EFFECTIVE,
    VERSION,
    Claim,
    build_projection,
    classify,
    historical_states,
    load_projection,
    persist_projection,
)
from pitquant.universe.sp500_anchor_graph import AnchorNode, Cohort, GraphReport, SegmentResult
from tests.unit.test_first_ml_readiness import D, ctx, snap, tgt

pytestmark = pytest.mark.pit


def claim(**kwargs):
    return replace(Claim("SYN-A", "ADD", date(2016, 4, 8), "SYN-PRODUCER-A", "a" * 64), **kwargs)


@pytest.mark.parametrize(
    "tier,expected",
    [
        ("OFFICIAL_DIRECT", True),
        ("CORROBORATED_HISTORICAL", True),
        ("UNVERIFIED", False),
        ("CONFLICTED", False),
    ],
)
def test_eligibility_tiers_are_security_period_specific(tier, expected):
    period = {
        "security_id": "S1",
        "decision_session": str(D),
        "membership_research_eligible": expected,
        "evidence_tier": tier,
        "evidence_version": VERSION,
        "provenance": [{"synthetic": True}],
    }
    context = ctx(
        extra={
            "membership_policy_version": VERSION,
            "membership_periods": {("S1", D): period},
            "membership_projection_dates": {D},
        }
    )
    result = FM.first_ml_eligibility(context, snap(), tgt())
    assert result["eligible"] is expected
    if not expected:
        assert "MEMBERSHIP_" + tier in result["reasons"]
    # The rejected security does not contaminate another security at this open.
    other = {
        **period,
        "security_id": "S3",
        "evidence_tier": "OFFICIAL_DIRECT",
        "membership_research_eligible": True,
    }
    context.extra["membership_periods"][("S3", D)] = other
    assert FM.first_ml_eligibility(context, snap("S3"), tgt())["eligible"]
    assert context.cohorts[D]["status"] == "MEMBERSHIP_READY"


def test_official_and_two_independent_historical_claims():
    assert classify([claim(official_direct=True)], identity_supported=True) == "OFFICIAL_DIRECT"
    assert (
        classify(
            [claim(), claim(upstream="SYN-PRODUCER-B", source_hash="b" * 64)],
            identity_supported=True,
        )
        == "CORROBORATED_HISTORICAL"
    )
    assert (
        classify(
            [claim(), claim(upstream="SYN-PRODUCER-B", source_hash="b" * 64)],
            identity_supported=False,
        )
        == "UNVERIFIED"
    )


@pytest.mark.parametrize(
    "second",
    [
        claim(upstream="SYN-PRODUCER-A", source_hash="b" * 64),
        claim(upstream="SYN-MIRROR", source_hash="a" * 64),
        claim(upstream=None, source_hash="b" * 64),
    ],
)
def test_mirrors_and_unknown_upstreams_do_not_establish_independence(second):
    assert classify([claim(), second], identity_supported=True) == "UNVERIFIED"


@pytest.mark.parametrize(
    "changes",
    [{"security_id": "SYN-CLASS-C"}, {"effective_date": date(2016, 4, 11)}, {"event": "REMOVE"}],
)
def test_relevant_contradictions_fail_closed_locally(changes):
    assert (
        classify(
            [claim(), claim(upstream="SYN-PRODUCER-B", source_hash="b" * 64, **changes)],
            identity_supported=True,
        )
        == "CONFLICTED"
    )


def test_yahoo_is_market_data_not_membership_authority():
    assert (
        classify([claim(upstream="YAHOO", official_direct=True)], identity_supported=True)
        == "UNVERIFIED"
    )
    assert (
        classify([claim(membership_authority=False, official_direct=True)], identity_supported=True)
        == "UNVERIFIED"
    )


def test_membership_selection_does_not_depend_on_outcome():
    claims = [claim(), claim(upstream="SYN-B", source_hash="b" * 64)]
    before = classify(claims, identity_supported=True)
    for outcome in (True, False, None):
        target = tgt(outperform=outcome)
        assert "outperform" in target  # No outcome is passed to the classifier.
        assert classify(claims, identity_supported=True) == before


def fixture_projection(tmp_path, *, ua=False, missing=False, conflict=False):
    """A two-security, incomplete, entirely synthetic anchor interval."""
    store = ArchiveStore(tmp_path)
    raw = b'date,tickers\n2016-03-31,"SYN-A,SYN-B,UAA"\n2016-04-08,"SYN-A,SYN-B,UAA,UA"\n'
    sha, path = store.put(raw)
    other_sha, other_path = store.put(b"SYNTHETIC independent membership claim")
    primary_sha, primary_path = store.put(b"SYNTHETIC identity evidence")
    sources = {
        k: {
            "sha256": sha,
            "archive_id": "SYN-HIST",
            "raw_document": str(path),
            "upstream": "SYN-HISTORY",
        }
        for k in ("clenow_original", "clenow_updated")
    }
    membership_sources = [
        {**sources["clenow_original"], "upstream": "SYN-ROOT-A"},
        {"sha256": other_sha, "raw_document": str(other_path), "upstream": "SYN-ROOT-B"},
    ]
    for source in membership_sources:
        source["effective_date"] = str(UA_EFFECTIVE)
    manifest = {
        "sources": sources,
        "under_armour": {
            "membership_sources": membership_sources,
            "primary_identity_supported": True,
            "primary_sources": [{"sha256": primary_sha, "raw_document": str(primary_path)}],
        },
    }
    sid_b = UA_C if ua else "SYN-ANCHOR-B"
    a = AnchorNode(
        "SYN-ANCHOR-1",
        date(2016, 3, 31),
        "B",
        "N-30D",
        None,
        frozenset({"SYN-ANCHOR-A"}),
        0,
        {},
        {},
        {},
    )
    b = AnchorNode(
        "SYN-ANCHOR-2",
        date(2016, 9, 30),
        "B",
        "N-30D",
        None,
        frozenset({"SYN-ANCHOR-A", sid_b}),
        0,
        {},
        {},
        {},
    )
    seg = SegmentResult(
        a,
        b,
        0,
        False,
        False,
        "LOCAL_GAPS",
        [],
        {sid_b: (date(2016, 4, 1), date(2016, 9, 30))},
        None,
        [],
    )
    if conflict:
        seg.deltas = [
            SimpleNamespace(
                difference_type="DATE_CONFLICT",
                security_identifier=sid_b,
                window=("2016-04-01", "2016-09-30"),
            )
        ]
    cohort = Cohort(
        date(2016, 5, 2),
        "BLOCKED",
        "2016-03-31→2016-09-30",
        None,
        members=None,
        forward_set=a.members,
        backward_set=b.members,
    )
    rep = GraphReport([a, b], [seg], [cohort], False, 0, 0)
    configured = {
        "SYN-RESEARCH-A": {"ticker": "SYN-A", "issuer_id": "SYN-ISSUER-A"},
        "SYN-RESEARCH-B": {"ticker": "UA" if ua else "SYN-B", "issuer_id": "SYN-ISSUER-B"},
    }
    bridge = {"SYN-RESEARCH-A": frozenset({"SYN-ANCHOR-A"}), "SYN-RESEARCH-B": frozenset({sid_b})}
    if missing:
        configured = {"SYN-RESEARCH-B": configured["SYN-RESEARCH-B"]}
    return rep, bridge, configured, manifest, store


def project(tmp_path, **kwargs):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path, **kwargs)
    return build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )


def test_unverified_security_period_does_not_block_month(tmp_path):
    result = project(tmp_path)
    assert result["months"][0]["status"] == "READY"
    assert result["months"][0]["eligible_securities"] == 1
    assert result["months"][0]["coverage_pct"] == 50
    assert result["months"][0]["unverified_excluded"] == 1
    assert result["rows"][1]["exclusion_reason"] == "UNRESOLVED_SECURITY_PERIOD_OR_IDENTITY"


def test_empty_supported_cohort_is_not_vacuously_ready(tmp_path):
    assert project(tmp_path, missing=True)["months"][0]["status"] == "BLOCKED"


def test_conflicted_security_is_excluded_without_contaminating_other(tmp_path):
    result = project(tmp_path, conflict=True)
    assert result["months"][0]["status"] == "READY"
    assert result["rows"][1]["evidence_tier"] == "CONFLICTED"
    assert not result["rows"][1]["membership_research_eligible"]
    assert result["rows"][0]["membership_research_eligible"]


def test_under_armour_class_c_exact_date_and_separate_class_a(tmp_path):
    result = project(tmp_path, ua=True)
    row = result["rows"][1]
    assert date(2016, 4, 8) == UA_EFFECTIVE
    assert row["evidence_tier"] == "CORROBORATED_HISTORICAL"
    assert row["anchor_security_ids"] == [UA_C]
    assert row["membership_research_eligible"]
    assert result["rows"][0]["anchor_security_ids"] != row["anchor_security_ids"]


def test_corroborated_addition_does_not_override_later_verified_removal(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path, ua=True)
    # Later segment contains neither class C membership nor unresolved C window.
    seg = rep.segments[0]
    seg.windows = {}
    rep.cohorts[0].backward_set = rep.cohorts[0].forward_set
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert not result["rows"][1]["membership_research_eligible"]


def test_security_lineage_is_not_permission_to_merge_legal_securities(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    bridge["SYN-RESEARCH-A"] = frozenset({"SYN-NEW-LEGAL-SECURITY"})
    result = build_projection(
        rep,
        bridge,
        configured,
        {"SYN-ANCHOR-A": "SYN-NEW-LEGAL-SECURITY"},
        manifest,
        store,
        start=date(2016, 4, 1),
        end=date(2016, 9, 30),
    )
    assert not result["rows"][0]["membership_research_eligible"]


def test_ticker_label_never_resolves_a_missing_security_identity(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    bridge.pop("SYN-RESEARCH-A")
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert not result["rows"][0]["membership_research_eligible"]


def test_projection_has_no_holdout_or_oot(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    with pytest.raises(ValueError, match="sealed holdout/OOT"):
        build_projection(
            rep,
            bridge,
            configured,
            {},
            manifest,
            store,
            start=date(2016, 4, 1),
            end=date(2022, 10, 1),
        )
    assert (
        len(
            historical_states(
                b"date,tickers\n2021-09-01,SYN-A\n2022-10-01,SYN-B\n2025-10-01,SYN-C\n",
                until=date(2021, 9, 30),
            )
        )
        == 1
    )


def test_conflicting_reference_states_are_not_arbitrarily_selected():
    with pytest.raises(ValueError, match="conflicting"):
        historical_states(
            b"date,tickers\n2016-04-08,SYN-A\n2016-04-08,SYN-B\n", until=date(2021, 9, 30)
        )


def test_projection_ignores_performance_and_is_deterministic(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    a = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    for value in configured.values():
        value.update(future_return=-100, score=999, drawdown=0.9)
    b = build_projection(
        rep,
        bridge,
        dict(reversed(list(configured.items()))),
        {},
        manifest,
        store,
        start=date(2016, 4, 1),
        end=date(2016, 9, 30),
    )
    assert a == b


def test_ledger_is_append_only_idempotent_and_hash_verified(session, tmp_path):
    store = ArchiveStore(tmp_path)
    projection = {"evidence_version": VERSION, "rows": [], "months": []}
    first = persist_projection(session, store, projection)
    assert persist_projection(session, store, projection) == first
    assert load_projection(store, first["sha256"]) == projection
    row = session.get_one(RawSourceArchive, first["archive_id"])
    session.commit()
    row.notes = "SYNTHETIC attempted edit"
    with pytest.raises(ImmutableRecordError):
        session.flush()
    session.rollback()
    store.path_for(first["sha256"]).write_bytes(b"SYNTHETIC corruption")
    with pytest.raises(DataQualityError):
        load_projection(store, first["sha256"])


def test_ledger_revision_preserves_previous_version(session, tmp_path):
    store = ArchiveStore(tmp_path)
    first = persist_projection(session, store, {"evidence_version": VERSION, "rows": []})
    second = persist_projection(
        session, store, {"evidence_version": VERSION, "rows": [{"synthetic": True}]}
    )
    assert first["archive_id"] != second["archive_id"]
    assert load_projection(store, first["sha256"])["rows"] == []


def test_missing_or_wrong_evidence_version_excludes_only_period():
    context = ctx(extra={"membership_policy_version": VERSION, "membership_projection_dates": {D}})
    assert "MEMBERSHIP_UNVERIFIED" in FM.first_ml_eligibility(context, snap(), tgt())["reasons"]


def test_three_label_safe_folds_accept_partial_membership_without_coverage(monkeypatch):
    from pitquant.research import first_ml_contract as contract
    from pitquant.research.fold_readiness import audit_folds
    from tests.unit.test_first_ml_fold_readiness import AS_OF
    from tests.unit.test_label_safe_history_v2 import world

    plan, samples, targets, context = world()
    context.extra = {
        "membership_policy_version": VERSION,
        "membership_projection_dates": set(context.cohorts),
        "membership_periods": {},
    }
    additional = []
    for sample in samples:
        day = sample["decision_session"]
        for sid, eligible in (("S1", True), ("S3", False)):
            context.extra["membership_periods"][(sid, day)] = {
                "security_id": sid,
                "decision_session": str(day),
                "evidence_version": VERSION,
                "evidence_tier": "CORROBORATED_HISTORICAL" if eligible else "UNVERIFIED",
                "membership_research_eligible": eligible,
                "provenance": [{"synthetic": True}],
            }
        additional.append({**sample, "security_id": "S3"})
        targets[("S3", sample["decision_at"])] = targets[("S1", sample["decision_at"])]
    monkeypatch.setattr(contract, "REQUIRED_SECURITIES", 100000)
    result = audit_folds(plan, samples + additional, targets, context, as_of=AS_OF)
    assert result["label_safe_folds"] == 3
    assert not result["coverage_evaluated"]
    assert all(fold["TEST"]["eligible_securities"] == 1 for fold in result["folds"])
    assert all("MEMBERSHIP_UNVERIFIED" in fold["TEST"]["excluded_by"] for fold in result["folds"])


def test_ticker_change_preserves_security_identity(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    before = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    # A label changes, never the class/security link; both labels in reference.
    configured["SYN-RESEARCH-A"]["ticker"] = "SYN-RENAMED"
    sha, path = store.put(b'date,tickers\n2016-03-31,"SYN-RENAMED,SYN-B"\n')
    for key in ("clenow_original", "clenow_updated"):
        manifest["sources"][key].update(sha256=sha, raw_document=str(path))
    after = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert before["rows"][0]["security_id"] == after["rows"][0]["security_id"]
    assert before["rows"][0]["anchor_security_ids"] == after["rows"][0]["anchor_security_ids"]
    assert after["rows"][0]["membership_research_eligible"]


def test_context_projection_rejects_unsupported_included_rows(tmp_path):
    from pitquant.research.membership_evidence import context_extra

    projection = project(tmp_path)
    assert len(context_extra(projection)["membership_periods"]) == 2
    projection["rows"][1]["membership_research_eligible"] = True
    with pytest.raises(ValueError, match="lacks supported evidence"):
        context_extra(projection)


def test_context_projection_rejects_duplicate_periods_and_sealed_dates(tmp_path):
    from pitquant.research.membership_evidence import context_extra

    projection = project(tmp_path)
    projection["rows"].append(projection["rows"][0])
    with pytest.raises(ValueError, match="duplicate"):
        context_extra(projection)
    projection["rows"].pop()
    projection["rows"][0]["decision_session"] = "2022-10-01"
    with pytest.raises(ValueError, match="sealed holdout/OOT"):
        context_extra(projection)


def test_verified_nonmember_is_not_reported_as_missing_evidence():
    period = {
        "security_id": "S1",
        "decision_session": str(D),
        "membership_research_eligible": False,
        "membership_state": "NON_MEMBER",
        "evidence_tier": "CORROBORATED_HISTORICAL",
        "evidence_version": VERSION,
        "provenance": [{"synthetic": True}],
    }
    context = ctx(
        extra={
            "membership_policy_version": VERSION,
            "membership_periods": {("S1", D): period},
            "membership_projection_dates": {D},
        }
    )
    result = FM.first_ml_eligibility(context, snap(), tgt())
    assert "NOT_INDEX_MEMBER_AT_T" in result["reasons"]
    assert "MEMBERSHIP_UNVERIFIED" not in result["reasons"]


def test_claim_without_archived_hash_cannot_be_official_or_corroborated():
    assert (
        classify([claim(official_direct=True, source_hash="")], identity_supported=True)
        == "UNVERIFIED"
    )
    assert (
        classify(
            [claim(), claim(upstream="SYN-B", source_hash="not-a-sha256")], identity_supported=True
        )
        == "UNVERIFIED"
    )


def test_under_armour_insufficient_independence_excludes_only_class_c(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path, ua=True)
    manifest["under_armour"]["membership_sources"][1]["upstream"] = "SYN-ROOT-A"
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert result["months"][0]["status"] == "READY"
    assert result["under_armour"]["evidence_tier"] == "UNVERIFIED"
    assert not result["rows"][1]["membership_research_eligible"]


def test_later_official_contradiction_cannot_be_overridden_by_ua_acceptance(tmp_path):
    from pitquant.universe.sp500_anchor_graph import Leg

    rep, bridge, configured, manifest, store = fixture_projection(tmp_path, ua=True)
    rep.segments[0].legs.append(
        Leg(
            "SYN-OFFICIAL",
            "OFFICIAL_CONFIRMED",
            "ADD",
            "UA.C",
            "SYN UA C",
            date(2016, 4, 11),
            date(2016, 4, 11),
            True,
            None,
            security_id=UA_C,
        )
    )
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert result["months"][0]["status"] == "READY"
    assert result["under_armour"]["evidence_tier"] == "CONFLICTED"
    assert not result["rows"][1]["membership_research_eligible"]


def test_ua_official_promotion_preserves_class_and_effective_date(tmp_path):
    rep, bridge, configured, manifest, store = fixture_projection(tmp_path, ua=True)
    manifest["under_armour"]["membership_sources"][0]["official_direct"] = True
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert result["rows"][1]["evidence_tier"] == "OFFICIAL_DIRECT"
    assert result["rows"][1]["anchor_security_ids"] == [UA_C]
    assert result["under_armour"]["official_direct"] is True


def test_archived_official_ticker_identity_crosscheck_handles_historical_label(tmp_path):
    from pitquant.universe.sp500_anchor_graph import Leg

    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    configured["SYN-RESEARCH-A"]["ticker"] = "SYN-CURRENT-LABEL"
    rep.segments[0].legs.append(
        Leg(
            "SYN-OFFICIAL-TICKER",
            "OFFICIAL_CONFIRMED",
            "ADD",
            "SYN-A",
            "SYN-A",
            date(2016, 3, 1),
            date(2016, 3, 1),
            True,
            None,
            security_id="SYN-ANCHOR-A",
        )
    )
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert result["rows"][0]["membership_research_eligible"]
    assert result["rows"][0]["anchor_security_ids"] == ["SYN-ANCHOR-A"]
    rep.segments[0].legs[0].lo = date(2017, 1, 1)
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert not result["rows"][0]["membership_research_eligible"]


def test_class_set_membership_does_not_prove_ticker_class_pairing(tmp_path):
    from pitquant.universe.sp500_anchor_graph import Leg

    rep, bridge, configured, manifest, store = fixture_projection(tmp_path)
    configured["SYN-RESEARCH-A"]["ticker"] = "SYN-OTHER-CLASS-LABEL"
    rep.segments[0].legs.append(
        Leg(
            "SYN-CLASS-SET",
            "OFFICIAL_CONFIRMED",
            "ADD",
            "SYN-A",
            "SYN-A",
            date(2016, 3, 1),
            date(2016, 3, 1),
            True,
            None,
            security_id="SYN-ANCHOR-A",
            resolution="CLASS_SET",
        )
    )
    result = build_projection(
        rep, bridge, configured, {}, manifest, store, start=date(2016, 4, 1), end=date(2016, 9, 30)
    )
    assert not result["rows"][0]["membership_research_eligible"]
