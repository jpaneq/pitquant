"""Availability only: reuse existing core metrics, never build labels or select on scores."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from pitquant.analyzer import fundamental_v1 as FV
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0.engine import _debt
from pitquant.research import fundamental_recovery as FR
from pitquant.research import us_universe_scale as U
from pitquant.research.fundamentals_v1 import sector_status

CORE_TAGS = frozenset(
    F.TAGS["revenue"]
    + F.TAGS["net_income"]
    + F.TAGS["assets"]
    + F.DEBT_TAGS
    + ("DebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligations")
)
KNOWN_MAPPED_TAGS = CORE_TAGS | frozenset(
    tag for family in (*F.TAGS.values(), *FV.EXTRA_TAGS.values()) for tag in family
)


def validate_collection(
    roster: list[dict[str, Any]],
    ingestion: dict[str, Any],
    prices: dict[str, Any],
) -> dict[str, Any]:
    """Do not publish coverage while a provider case still awaits classification."""
    issuers = {
        r["cik_candidate"]
        for r in roster
        if r.get("issuer_primary_match") and not sector_status(r.get("sic"))
    }
    symbols = {r["ticker_candidate"] for r in roster if r.get("ticker_candidate")}
    for r in roster:
        if not r.get("ticker_candidate") and r.get("official_ticker_legs"):
            latest = max(
                r["official_ticker_legs"], key=lambda leg: (leg["effective_date"], leg["event_id"])
            )
            symbols.add(latest["ticker"])
    if issuers - ingestion.keys() or symbols - prices.keys():
        raise ValueError("collection incomplete: finish classifying SEC and Yahoo cases first")
    allowed = {"COMPLETE", "PARTIAL", "FAILED", "REUSED_PRIMARY_ARCHIVE"}
    if any(ingestion[cik]["status"] not in allowed for cik in issuers):
        raise ValueError("SEC case has no final classification")
    if any(prices[symbol]["status"] not in {"READY", "BLOCKED"} for symbol in symbols):
        raise ValueError("Yahoo case has no final classification")
    return {
        "expected_sec_issuers": len(issuers),
        "expected_yahoo_symbols": len(symbols),
        "sec_states": dict(Counter(ingestion[cik]["status"] for cik in sorted(issuers))),
        "yahoo_states": dict(Counter(prices[symbol]["status"] for symbol in sorted(symbols))),
        "stop_rule_met": True,
        "all_ready_required": False,
    }


def core_fundamentals(facts: list[F.Fact], decision_at: datetime) -> dict[str, Any]:
    """Exact existing sec-tags-4 three-field subset; no substitute or new mapping."""
    vis = F.visible(facts, decision_at)
    revenue, ni = FV._flow(vis, "revenue"), FV._flow(vis, "net_income")
    end = FV._end(revenue)
    prior = (
        FV._flow(vis, "revenue", FV._years_before(end, 1))
        if end
        else F.Metric.missing("missing_fundamental")
    )
    metrics = {
        "fund_net_margin": F.safe_div(ni, revenue, "net margin", den_positive=True),
        "fund_revenue_yoy": FV._growth(revenue, prior, "revenue yoy"),
        "fund_debt_to_assets": F.safe_div(
            _debt(vis), FV._inst(vis, "assets"), "debt / assets", den_positive=True
        ),
    }
    fields = {
        name: {
            "value": m.value,
            "missing_reason": "MAPPING_GAP"
            if m.reason in ("missing_fundamental", "conflicting_tags")
            else (
                "INSUFFICIENT_HISTORY"
                if m.reason in ("insufficient_history", "stale_data")
                else m.reason
            ),
            "raw_missing_reason": m.reason,
            "available_at": m.available_at.isoformat() if m.available_at else None,
            "provenance": m.provenance,
            "formula": m.formula,
        }
        for name, m in metrics.items()
    }
    return FR.repair_features(fields, facts, decision_at, supported=True)


def price_window(qa: dict[str, Any] | None, decision_at: datetime) -> tuple[bool, str | None]:
    """D05 plus contiguous 253 known closes for the EXISTING 252-session features.

    No numerical technical indicator or return is calculated here. Actions and
    RAW reconstruction are pinned separately in the vendor audit.
    """
    if not qa:
        return False, "MARKET_DATA_UNAVAILABLE"
    if qa["status"] != "READY":
        return False, ";".join(qa["reasons"])
    bars = [b for b in qa["bars"] if datetime.fromisoformat(b["close_at"]) < decision_at]
    if len(bars) < 253:
        return False, "INSUFFICIENT_PRICE_HISTORY"
    cal = get_calendar("XNYS")
    last = cal.session_on_or_before(decision_at.date())
    if cal.session_close(last) >= decision_at:
        last = cal.session_on_or_before(last.fromordinal(last.toordinal() - 1))
    from datetime import date

    expected = cal.sessions(date.fromisoformat(bars[-253]["session"]), last)
    if [b["session"] for b in bars[-253:]] != [str(d) for d in expected]:
        return False, "PRICE_LOOKBACK_GAP_OR_STALE"
    if any(b["close"] is None or b["close"] <= 0 for b in bars[-253:]):
        return False, "PRICE_LOOKBACK_INVALID"
    return True, None


def blocker_ranking(rows: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
    known: dict[str, set[tuple[str, str]]] = defaultdict(set)
    unknown: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for r in rows:
        if category not in r["blockers"]:
            continue
        reason = r["reasons"].get(category) or category
        if r["issuer_id"]:
            known[reason].add((r["issuer_id"], r["month"]))
        else:
            unknown[reason].add((r["security_id"], r["month"]))
    return sorted(
        [
            {
                "reason": k,
                "lost_known_issuer_months": len(known[k]),
                "unresolved_security_periods": len(unknown[k]),
            }
            for k in known.keys() | unknown.keys()
        ],
        key=lambda r: (
            -r["lost_known_issuer_months"],
            -r["unresolved_security_periods"],
            r["reason"],
        ),
    )


def mapping_debt(
    rows: list[dict[str, Any]], concepts: dict[str, dict[str, datetime]]
) -> list[dict[str, Any]]:
    """Outcome-blind, PIT concept presence, without claiming semantic equivalence."""
    missing = [
        r
        for r in rows
        if r["issuer_id"]
        and "FUNDAMENTALS" in r["blockers"]
        and "UNSUPPORTED_SECTOR" not in r["blockers"]
    ]
    ranked = []
    for concept, first_available in concepts.items():
        name = concept.lower()
        if concept in KNOWN_MAPPED_TAGS:
            continue
        families = []
        if "debt" in name or "borrowing" in name or "lease" in name:
            families.append("fund_debt_to_assets")
        if ("revenue" in name or "sales" in name) and not any(
            term in name for term in ("cost", "tax", "receivable", "deferred")
        ):
            families += ["fund_net_margin", "fund_revenue_yoy"]
        if any(term in name for term in ("netincome", "netearnings", "profitloss")) and not any(
            term in name for term in ("comprehensive", "tax", "otherincome")
        ):
            families.append("fund_net_margin")
        if not families:
            continue
        units = {
            (r["issuer_id"], r["month"])
            for r in missing
            if r["issuer_id"] in first_available
            and first_available[r["issuer_id"]] < datetime.fromisoformat(r["decision_at"])
            and any(
                r.get("core_fundamentals", {}).get(field, {}).get("value") is None
                and r.get("core_fundamentals", {}).get(field, {}).get("missing_reason")
                == "MAPPING_GAP"
                for field in families
            )
        }
        if units:
            ranked.append(
                {
                    "concept": concept,
                    "issuer_count": len({i for i, _ in units}),
                    "issuer_month_impact": len(units),
                    "classification": "UNMAPPED_CONCEPT_CANDIDATE_NOT_PROVEN_CAUSE",
                    "core_families_for_semantic_review": families,
                }
            )
    return sorted(ranked, key=lambda r: (-r["issuer_month_impact"], r["concept"]))


def validate_candidate(rows: list[dict[str, Any]]) -> None:
    seen = set()
    for r in rows:
        day = datetime.fromisoformat(r["decision_at"])
        U.check_period(day.date())
        if day.tzinfo is None:
            raise ValueError("naive decision time")
        key = r["security_id"], r["month"]
        if key in seen:
            raise ValueError("duplicate security-period")
        seen.add(key)
        for field in r.get("core_fundamentals", {}).values():
            available = field.get("available_at")
            if available and datetime.fromisoformat(available) >= day:
                raise ValueError("future fundamental")
        if r["eligibility"]["COMBINED"] and (
            not r["issuer_id"] or r["blockers"] or not all(r["eligibility"].values())
        ):
            raise ValueError("invalid research inclusion")
