"""SYNTHETIC evidence: outcome-blind expansion, PIT and fail-soft exclusions."""

import ast
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from pitquant.analyzer import fundamental_v1 as FV
from pitquant.data.archive import ArchiveStore
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import fundamental_recovery as FR
from pitquant.research import membership_evidence as M
from pitquant.research import us_coverage_scale as A
from pitquant.research import us_universe_scale as U
from pitquant.research.us_sec_collection import OfflineTransport
from tests.unit.test_first_ml_fundamental_recovery import facts as debt_facts
from tests.unit.test_fundamental_period_tolerance import fact

AT = datetime(2015, 2, 2, 14, tzinfo=UTC)


def profile_pair():
    r = {
        "cik_candidate": "0000999999",
        "names": ["SYNTHETIC CORP"],
        "ticker_candidate": "SYN",
        "anchor_instruments": [{"cusip": "FIXTURE", "isin": None}],
    }
    p = {
        "cik": 999999,
        "name": "SYNTHETIC CORP",
        "tickers": ["SYN"],
        "formerNames": [],
        "filings": {"files": [{"filingFrom": "2010-01-01"}]},
    }
    return r, p


def test_primary_identity_exact_and_former_name():
    r, p = profile_pair()
    assert U.verify_profile(r, p)[0]
    p["name"] = "NEW SYNTHETIC CORP"
    assert not U.verify_profile(r, p)[0]
    p["formerNames"] = [{"name": "SYNTHETIC CORP"}]
    assert U.verify_profile(r, p)[0]


@pytest.mark.parametrize(
    "key,value", [("cik", 888888), ("tickers", ["OTHER"]), ("name", "SIMILAR SYNTHETIC CORP")]
)
def test_primary_near_match_or_different_class_never_resolves(key, value):
    r, p = profile_pair()
    p[key] = value
    assert not U.verify_profile(r, p)[0]


def test_identifier_required_and_new_issuer_not_projected_backwards():
    r, p = profile_pair()
    r["anchor_instruments"] = []
    assert not U.verify_profile(r, p)[0]
    r, p = profile_pair()
    p["filings"]["files"][0]["filingFrom"] = "2023-10-01"
    assert U.verify_profile(r, p)[1] == "PRIMARY_ISSUER_HISTORY_STARTS_AFTER_RESEARCH_PERIOD"


@pytest.mark.pit
@pytest.mark.parametrize(
    "day", [date(2014, 8, 31), date(2021, 10, 1), date(2022, 10, 1), date(2025, 10, 1)]
)
def test_period_cannot_enter_holdout_or_oot(day):
    with pytest.raises(ValueError):
        U.check_period(day)


def test_independence_not_copies_or_yahoo_membership():
    claims = [
        M.Claim("SYN", "ADD", date(2015, 1, 1), "SEC", "a" * 64),
        M.Claim("SYN", "ADD", date(2015, 1, 1), "YAHOO", "b" * 64),
    ]
    assert M.classify(claims, identity_supported=True) == "UNVERIFIED"
    claims[1] = M.Claim("SYN", "ADD", date(2015, 1, 1), "SEC", "b" * 64)
    assert M.classify(claims, identity_supported=True) == "UNVERIFIED"
    claims[1] = M.Claim("SYN", "ADD", date(2015, 1, 1), "CLENOW", "b" * 64)
    assert M.classify(claims, identity_supported=True) == "CORROBORATED_HISTORICAL"
    assert M.classify(claims, identity_supported=True, conflicted=True) == "CONFLICTED"


def test_discovery_includes_removed_without_current_registry(session):
    from pitquant.db.models import Security

    sec = Security(
        security_id="SYN-REMOVED", name="SYN DISAPPEARED", exchange="XNYS", currency="USD"
    )
    session.add(sec)
    session.flush()
    rep = SimpleNamespace(
        cohorts=[
            SimpleNamespace(
                date=date(2015, 1, 2), forward_set={sec.security_id}, backward_set=set()
            )
        ],
        segments=[],
    )
    records = U.discover(session, rep, {})
    assert len(records) == 1 and records[0]["security_id"] == sec.security_id
    assert records[0]["identity_status"] == "IDENTITY_UNRESOLVED"


def mock_cache(tmp_path, handler):
    cache = U.EvidenceCache(
        tmp_path / "cache",
        ArchiveStore(tmp_path / "raw"),
        "SYNTHETIC contact@example.test",
        min_gap=0,
    )
    cache.http.close()
    cache.http = httpx.Client(transport=httpx.MockTransport(handler))
    return cache


def test_cache_replay_and_concurrent_dedup_hash(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200, content=b'{"FIXTURE":true}', headers={"content-type": "application/json"}
        )

    cache = mock_cache(tmp_path, handler)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(cache.get, ["https://data.sec.gov/FIXTURE"] * 4))
    assert len(calls) == 1 and all(r.status == 200 for r in responses)
    assert "contact@example.test" not in cache.path.read_text()
    assert cache.records[calls[0]]["publisher"] == "SEC"
    assert cache.get(calls[0]).body == responses[0].body
    sha = cache.records[calls[0]]["sha256"]
    cache.archive.path_for(sha).write_bytes(b"CORRUPTED")
    with pytest.raises(Exception, match="hash verification"):
        cache.get(calls[0])


def test_cache_backoff_errors_and_offline_budget(tmp_path, monkeypatch):
    sleeps, statuses = [], iter([503, 429, 200])
    monkeypatch.setattr(U.time, "sleep", sleeps.append)
    cache = mock_cache(tmp_path, lambda req: httpx.Response(next(statuses), content=b"FIXTURE"))
    assert cache.get("https://data.sec.gov/FIXTURE").status == 200
    assert sleeps == [1, 2] and cache.requests_made == 3
    transport = OfflineTransport(cache)
    assert transport.get("https://data.sec.gov/NO_BUDGET", {}).status == 404
    assert cache.requests_made == 3


def test_failed_cache_not_retried_repeatedly(tmp_path):
    cache = mock_cache(tmp_path, lambda req: httpx.Response(404, content=b"NOT_FOUND"))
    assert cache.get("https://query1.finance.yahoo.com/FIXTURE").status == 404
    assert cache.get("https://query1.finance.yahoo.com/FIXTURE").status == 404
    assert cache.requests_made == 1


def test_revision_preserved_hash_and_corruption(tmp_path):
    sha = U.write_revision(tmp_path, "FIXTURE", {"b": 2, "a": 1})
    assert sha == U.write_revision(tmp_path, "FIXTURE", {"a": 1, "b": 2})
    other = U.write_revision(tmp_path, "FIXTURE", {"a": 3})
    assert other != sha
    (tmp_path / "revisions" / sha / "FIXTURE.json").write_text("CORRUPTED")
    with pytest.raises(ValueError, match="corrupted"):
        U.write_revision(tmp_path, "FIXTURE", {"a": 1, "b": 2})


@pytest.mark.pit
def test_core_subset_equals_existing_engine_and_sec4_overlay(session):
    fs = [
        *debt_facts(),
        fact("Revenues", date(2014, 1, 1), date(2014, 12, 31), 200, AT - timedelta(days=5)),
        fact("Revenues", date(2013, 1, 1), date(2013, 12, 31), 100, AT - timedelta(days=20)),
        fact("NetIncomeLoss", date(2014, 1, 1), date(2014, 12, 31), 20, AT - timedelta(days=5)),
    ]
    full = FV.compute_fundamentals(session, "SYN", AT, facts=fs)
    fields = {
        "fund_net_margin": deepcopy(full["profitability"]["net_margin"]),
        "fund_revenue_yoy": deepcopy(full["growth"]["revenue_yoy"]),
        "fund_debt_to_assets": deepcopy(full["balance"]["debt_to_assets"]),
    }
    for v in fields.values():
        v["missing_reason"] = v.pop("reason", None)
    expected = FR.repair_features(fields, fs, AT, supported=True)
    actual = A.core_fundamentals(fs, AT)
    assert {k: v["value"] for k, v in actual.items()} == {
        k: v["value"] for k, v in expected.items()
    }
    assert actual["fund_debt_to_assets"]["value"] == 0.5
    future = fact("Revenues", date(2014, 1, 1), date(2014, 12, 31), 999999, AT)
    assert A.core_fundamentals([*fs, future], AT) == actual


def window():
    cal = get_calendar("XNYS")
    days = cal.sessions(date(2013, 1, 1), date(2014, 9, 1))[-253:]
    return {
        "status": "READY",
        "reasons": [],
        "bars": [
            {"session": str(d), "close_at": cal.session_close(d).isoformat(), "close": 100}
            for d in days
        ],
    }, cal.session_open(date(2014, 9, 2))


@pytest.mark.pit
def test_price_window_closed_only_contiguous_and_stale():
    qa, at = window()
    assert A.price_window(qa, at)[0]
    incomplete = deepcopy(qa)
    incomplete["bars"].pop(100)
    assert A.price_window(incomplete, at)[1] == "INSUFFICIENT_PRICE_HISTORY"
    assert not A.price_window(qa, at + timedelta(days=2))[0]
    future = deepcopy(qa)
    future["bars"].append({"session": "2014-09-02", "close_at": at.isoformat(), "close": 9999})
    assert A.price_window(future, at) == A.price_window(qa, at)


@pytest.mark.pit
def test_historical_prices_cut_future_values_keep_only_restoration_splits():
    def stamp(d):
        return int(datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp())

    doc = {
        "chart": {
            "result": [
                {
                    "timestamp": [stamp("2021-09-29"), stamp("2022-12-01")],
                    "indicators": {
                        "quote": [{"close": [100, "FORBIDDEN_FUTURE_VALUE"]}],
                        "adjclose": [{"adjclose": [99, 999]}],
                    },
                    "events": {
                        "splits": {
                            "later": {"date": stamp("2023-01-01"), "numerator": 2, "denominator": 1}
                        },
                        "dividends": {"future": {"date": stamp("2023-01-01"), "amount": 2}},
                    },
                }
            ]
        }
    }
    trimmed = U.historical_chart(json.dumps(doc).encode())
    parsed = json.loads(trimmed)["chart"]["result"][0]
    assert parsed["indicators"]["quote"][0]["close"] == [100]
    assert "later" in parsed["events"]["splits"] and not parsed["events"]["dividends"]
    assert b"FORBIDDEN_FUTURE_VALUE" not in trimmed


def row(sid="SYN1", issuer="ISSUER", month="2014-09", combined=True):
    return {
        "security_id": sid,
        "issuer_id": issuer,
        "month": month,
        "decision_at": "2014-09-02T13:30:00+00:00",
        "membership_tier": "CORROBORATED_HISTORICAL",
        "sector": "Manufacturing",
        "eligibility": {s: combined for s in ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED")},
        "blockers": [],
        "reasons": {},
    }


def test_issuer_dedup_classes_and_zero_months_engineering_not_science():
    rows = [row(), row("SYN2")]
    result = U.aggregate(rows, ["2014-09", "2014-10"])
    assert result["combined_issuer_months"] == 1
    assert result["months"][0]["unique_securities"] == 2
    assert result["cross_section"]["COMBINED"]["minimum"] == 0
    assert result["cross_section"]["COMBINED"]["median"] == 0.5
    assert result["scientific_coverage_gate"] == "NOT_DEFINED"


def test_unknown_identity_impact_never_counted_as_fake_issuer():
    r = row(issuer=None, combined=False)
    r.update(blockers=["IDENTITY"], reasons={"IDENTITY": "NO_PRIMARY"})
    rank = A.blocker_ranking([r], "IDENTITY")[0]
    assert rank["lost_known_issuer_months"] == 0 and rank["unresolved_security_periods"] == 1
    assert U.aggregate([r], ["2014-09"])["blocker_issuer_months"] == {}


@pytest.mark.pit
def test_candidate_guard_rejects_future_fact_duplicate_or_false_inclusion():
    r = row()
    r["core_fundamentals"] = {
        "fund_net_margin": {"value": 1, "available_at": "2014-09-02T13:30:00+00:00"}
    }
    with pytest.raises(ValueError, match="future"):
        A.validate_candidate([r])
    r = row()
    with pytest.raises(ValueError, match="duplicate"):
        A.validate_candidate([r, r])
    r["issuer_id"] = None
    with pytest.raises(ValueError, match="invalid research"):
        A.validate_candidate([r])


@pytest.mark.pit
def test_new_pipeline_has_no_outcome_reads_training_or_simulation_imports():
    paths = [
        Path("src/pitquant/research") / f
        for f in ("us_universe_scale.py", "us_coverage_scale.py", "us_sec_collection.py")
    ]
    paths += [
        Path("scripts/scale_us_research_universe.py"),
        Path("scripts/audit_us_research_scale.py"),
    ]
    forbidden = {
        "ResearchTarget",
        "Prediction",
        "Simulation",
        "RandomForestRegressor",
        "XGBRegressor",
        "ElasticNet",
        "LogisticRegression",
        "GradientBoostingRegressor",
    }
    for path in paths:
        tree = ast.parse(path.read_text())
        assert not {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & forbidden
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in {"fit", "predict", "predict_proba"}
            for n in ast.walk(tree)
        )


def test_vendor_collision_and_partial_audit_local_exclusion():
    roster = [
        {
            "security_id": sid,
            "cik_candidate": cik,
            "ticker_candidate": ticker,
            "identity_status": "PRIMARY_MATCH",
        }
        for sid, cik, ticker in (
            ("OLD", "1", "SYN"),
            ("NEW", "2", "SYN"),
            ("UNRELATED", "3", "OTHER"),
            ("PARTIAL", "4", "XOM"),
        )
    ]
    U.exclude_vendor_collisions(roster)
    assert [r["identity_status"] for r in roster] == [
        "IDENTITY_UNRESOLVED",
        "IDENTITY_UNRESOLVED",
        "PRIMARY_MATCH",
        "IDENTITY_UNRESOLVED",
    ]


def test_disk_reserve_classifies_without_network(tmp_path, monkeypatch):
    calls = []
    cache = mock_cache(
        tmp_path, lambda req: calls.append(req) or httpx.Response(200, content=b"SYN")
    )
    monkeypatch.setattr(U.shutil, "disk_usage", lambda _: SimpleNamespace(free=1024))
    assert cache.get("https://data.sec.gov/FIXTURE").status == 0
    assert calls == [] and cache.requests_made == 0
    assert cache.records["https://data.sec.gov/FIXTURE"]["error"] == "DISK_CAPACITY_RESERVE_5_GIB"


@pytest.mark.pit
def test_d05_raw_restore_later_split_and_historical_dividends():
    from tests.unit.test_yahoo_provider import body, row, ts

    doc = json.loads(
        body(
            [row(27, 10)],
            splits=[{"date": ts(2023, 1, 3), "numerator": 2, "denominator": 1}],
            divs=[{"date": ts(2020, 8, 27), "amount": 0.2}],
        )
    )
    doc["chart"]["result"][0]["meta"].update(
        instrumentType="EQUITY", firstTradeDate=ts(2020, 8, 27)
    )
    qa = U.audit_chart(json.dumps(doc).encode(), "SYN", "TST", "USD")
    assert qa["status"] == "READY" and qa["bars"][0]["close"] == 20
    assert qa["bars"][0]["volume"] is None and qa["splits"] == []
    assert qa["dividends"][0]["cash_amount"] == 0.4
    assert all(b["session"] <= "2021-09-30" for b in qa["bars"])
    assert U.audit_chart(json.dumps(doc).encode(), "SYN", "TST", "EUR")["status"] == "BLOCKED"
    assert U.audit_chart(json.dumps(doc).encode(), "SYN", "OTHER", "USD")["reasons"] == [
        "VENDOR_INSTRUMENT_MISMATCH"
    ]


def test_official_identifiers_can_support_name_only_holding():
    r, p = profile_pair()
    r["anchor_instruments"] = [{"cusip": None, "isin": None}]
    assert not U.verify_profile(r, p)[0]
    r["official_identifiers"] = [{"id_type": "CUSIP", "value": "SYNTHETIC", "sha256": "a" * 64}]
    assert U.verify_profile(r, p)[0]


@pytest.mark.pit
def test_mapping_debt_no_later_concept_or_financial_family_backfill():
    before, after = row(month="2014-09", combined=False), row(month="2014-10", combined=False)
    after["decision_at"] = "2014-10-01T13:30:00+00:00"
    for r in (before, after):
        r["blockers"] = ["FUNDAMENTALS"]
    concepts = {"SYN_UNMAPPED": {"ISSUER": datetime(2014, 9, 10, tzinfo=UTC)}}
    rank = A.mapping_debt([before, after], concepts)
    assert rank[0]["issuer_month_impact"] == 1 and rank[0]["issuer_count"] == 1
    after["blockers"].append("UNSUPPORTED_SECTOR")
    assert A.mapping_debt([before, after], concepts) == []


def test_historical_cik_registry_exact_unique_and_ambiguous():
    roster = [
        {"security_id": "OLD", "names": ["SYNTHETIC REMOVED INC"]},
        {"security_id": "AMB", "names": ["SYNTHETIC SAME CORP"]},
    ]
    raw = (
        b"SYNTHETIC REMOVED INC:0000999999:\nSYNTHETIC SAME CORP:0000888888:\n"
        b"SYNTHETIC SAME CORP:0000777777:\nSYNTHETIC NEAR INC:0000666666:\n"
    )
    result = U.historical_cik_matches(raw, roster)
    assert result == {"OLD": ["0000999999"], "AMB": ["0000777777", "0000888888"]}


@pytest.mark.pit
def test_primary_history_must_overlap_security_period():
    r, p = profile_pair()
    r["potential_sessions"] = ["2014-09-02", "2017-09-01"]
    p["filings"]["files"] = [{"filingFrom": "2018-01-01", "filingTo": "2021-01-01"}]
    assert U.verify_issuer_profile(r, p)[1] == "PRIMARY_ISSUER_HISTORY_STARTS_AFTER_SECURITY_PERIOD"
    p["filings"]["files"] = [{"filingFrom": "2000-01-01", "filingTo": "2005-01-01"}]
    assert U.verify_issuer_profile(r, p)[1] == "PRIMARY_ISSUER_HISTORY_ENDS_BEFORE_SECURITY_PERIOD"


def test_retired_primary_ticker_and_vendor_recycling_guard():
    r, p = profile_pair()
    p["tickers"] = []
    assert not U.verify_profile(r, p)[0]
    r["official_ticker_legs"] = [{"ticker": "SYN", "effective_date": "2017-01-02"}]
    assert U.verify_profile(r, p)[0]
    assert not U.terminal_vendor_binding(r, p, {"longName": "OTHER COMPANY"})[0]
    assert not U.terminal_vendor_binding(r, p, {})[0]
    assert U.terminal_vendor_binding(r, p, {"longName": "Synthetic Corp."})[0]


@pytest.mark.pit
@pytest.mark.parametrize("status", [404, 403, 0])
def test_only_real_cached_discovery_404_enables_primary_instance_recovery(
    tmp_path, session, settings, status
):
    from pitquant.data.providers.sec_edgar.client import COMPANYFACTS_URL, SECClient, SECFetchError
    from pitquant.research.us_sec_collection import CachedPrimaryInstanceProvider

    cache = mock_cache(tmp_path, lambda req: httpx.Response(404, content=b"SYNTHETIC_404"))
    url = COMPANYFACTS_URL.format(cik10="0000999999")
    cache.get(url)
    cache.records[url]["status"] = status
    client = SECClient(
        OfflineTransport(cache), "SYN fixture@example.test", max_retries=0, sleep=lambda _: None
    )
    provider = CachedPrimaryInstanceProvider(client, cache.archive, settings.fundamentals.sec)
    if status == 404:
        assert provider.companyfacts(session, "999999") == []
    else:
        with pytest.raises(SECFetchError):
            provider.companyfacts(session, "999999")
    with pytest.raises(SECFetchError):
        provider.companyfacts(session, "888888")  # offline cache miss is NOT a real SEC 404
