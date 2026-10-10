"""Semantic and causal safeguards for the isolated closure revision."""

from datetime import UTC, date, datetime, timedelta

import pytest

from pitquant.features.v0 import fundamentals as F
from pitquant.research import us_targeted_closure as T

AT = datetime(2018, 4, 2, tzinfo=UTC)


def fact(concept, value, *, available=None, accession="a", unit="USD"):
    return F.Fact(
        concept,
        date(2017, 1, 1),
        date(2017, 12, 31),
        value,
        unit,
        available or AT - timedelta(days=30),
        accession,
        "10-K",
        fact_id=concept,
    )


@pytest.mark.pit
def test_consolidated_parent_income_requires_matched_primary_components():
    total = fact("ProfitLoss", 100)
    nci = fact("NetIncomeLossAttributableToNoncontrollingInterest", 20)
    derived = T.parent_income_facts([total, nci], AT)
    assert derived[-1].concept == "NetIncomeLoss"
    assert derived[-1].value == 80
    assert derived[-1].available_at < AT
    assert total.value == 100 and nci.value == 20
    assert "sec-tags-5" in derived[-1].fact_id


@pytest.mark.pit
@pytest.mark.parametrize(
    "nci",
    [
        None,
        fact("NetIncomeLossAttributableToNoncontrollingInterest", 20, available=AT),
        fact("NetIncomeLossAttributableToNoncontrollingInterest", 20, accession="b"),
        fact("NetIncomeLossAttributableToNoncontrollingInterest", 20, unit="EUR"),
    ],
)
def test_missing_future_cross_accession_and_cross_currency_are_not_zero(nci):
    facts = [fact("ProfitLoss", 100)] + ([nci] if nci else [])
    assert T.parent_income_facts(facts, AT) == facts


def test_reported_parent_income_is_never_overwritten():
    facts = [
        fact("ProfitLoss", 100),
        fact("NetIncomeLossAttributableToNoncontrollingInterest", 20),
        fact("NetIncomeLoss", 70),
    ]
    assert T.parent_income_facts(facts, AT) == facts


@pytest.mark.pit
def test_new_known_partial_period_never_falls_back_to_stale_income_for_coverage():
    from pitquant.analyzer import fundamental_v1 as FV

    at = datetime(2015, 8, 1, tzinfo=UTC)
    known_fy = F.Fact(
        "NetIncomeLoss",
        date(2014, 1, 1),
        date(2014, 12, 31),
        10.0,
        "USD",
        datetime(2015, 3, 1, tzinfo=UTC),
        "old",
        "10-K",
    )
    total = F.Fact(
        "ProfitLoss",
        date(2015, 1, 1),
        date(2015, 6, 30),
        100.0,
        "USD",
        datetime(2015, 7, 1, tzinfo=UTC),
        "new",
        "10-Q",
    )
    nci = F.Fact(
        "NetIncomeLossAttributableToNoncontrollingInterest",
        date(2015, 1, 1),
        date(2015, 6, 30),
        20.0,
        "USD",
        datetime(2015, 7, 1, tzinfo=UTC),
        "new",
        "10-Q",
    )
    assert FV._flow(F.visible([known_fy], at), "net_income").value == 10.0
    revised = FV._flow(
        F.visible(T.parent_income_facts([known_fy, total, nci], at), at), "net_income"
    )
    assert revised.value is None
    assert "YTD of the prior year" in revised.formula


def test_common_stockholder_and_investment_asset_are_not_debt_or_total_income():
    concepts = [
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "AvailableForSaleSecuritiesDebtSecurities",
        "SalesRevenueGoodsNet",
    ]
    rows = T.semantic_review(
        [{"concept": c, "issuer_count": 5, "issuer_month_impact": 150} for c in concepts]
    )
    assert all(not r["mapping_possible"] for r in rows)
    assert rows[0]["semantic_family"].startswith("COMMON_STOCKHOLDER")
    assert rows[1]["semantic_family"].startswith("INVESTMENT_ASSET")
    assert rows[2]["mapping_status"].startswith("DEFERRED")


def test_recovery_deduplicates_share_classes_and_does_not_sum_associations():
    row = {"issuer_id": "issuer", "month": "2017-01", "eligibility": {"COMBINED": True}}
    assert T.recovery([], [row, row], "COMBINED") == 1
    assert T.recovery([row], [row, row], "COMBINED") == 0


def test_current_ticker_without_primary_dated_alias_cannot_repair_identity():
    r = {"issuer_primary_match": True, "primary_issuer_id": "id", "dated_ticker_aliases": []}
    assert T.dated_alias_candidate(r, {"tickers": ["NEW"]}) is None
    r["dated_ticker_aliases"] = [
        {"ticker": "NEW", "from": "2022-10-01", "bounds": "EXACT", "source_hash": "s"}
    ]
    assert T.dated_alias_candidate(r, {"tickers": ["NEW"]}) is None
    r["dated_ticker_aliases"][0]["from"] = "2018-01-01"
    assert T.dated_alias_candidate(r, {"tickers": ["NEW"]}) is not None


def script(name):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[2] / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compaction_rejects_corrupt_original_without_replacing_it(tmp_path):
    c = script("compact_research_archive")
    original = tmp_path / ("a" * 64)
    original.write_bytes(b"primary evidence")
    with pytest.raises(ValueError, match="original source hash mismatch"):
        c.compact(original)
    assert original.read_bytes() == b"primary evidence"


@pytest.mark.pit
def test_label_metadata_cannot_cross_sealed_boundary_or_successor():
    s = script("audit_us_scientific_constructibility")
    at = datetime(2021, 10, 1, tzinfo=UTC)
    assert s.constructible([], [], at, None, None) == (False, "HOLDOUT_BOUNDARY")
    at = datetime(2020, 10, 1, tzinfo=UTC)
    assert (
        s.constructible([], [], at, None, "2021-01-01")[1]
        == "SUCCESSOR_OR_TERMINAL_EVENT_WITHIN_HORIZON"
    )


def test_scientific_code_never_imports_target_builders_or_estimators():
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "scripts/audit_us_scientific_constructibility.py"
    tree = ast.parse(source.read_text())
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any("targets" in i or "sklearn" in i or "equity_baseline" in i for i in imports)
