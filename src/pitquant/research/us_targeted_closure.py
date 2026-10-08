"""Target-blind, versioned targeted closure; no estimator or target builder imports."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from pitquant.features.v0 import fundamentals as F
from pitquant.research import us_coverage_scale as A

TAG_VERSION = "sec-tags-5"
BASE_CORE = A.core_fundamentals
PRIMARY_TAXONOMY = "https://xbrl.fasb.org/impdocs/OCI_TIG/othercompincome.htm"


def parent_income_facts(facts: list[F.Fact], decision_at: datetime) -> list[F.Fact]:
    """Parent income = consolidated income minus NCI, same accession/unit/period.

    No direct substitution of consolidated profit or common-stock income. An
    absent NCI component is never zero. Original facts/maps remain unchanged.
    """
    visible = F.visible(facts, decision_at)
    by_key = {(f.concept, f.unit, f.period_start, f.period_end, f.accession): f for f in visible}
    result = list(facts)
    for total in visible:
        if total.concept != "ProfitLoss" or total.unit != "USD" or not total.period_start:
            continue
        key = (total.unit, total.period_start, total.period_end, total.accession)
        nci = by_key.get(("NetIncomeLossAttributableToNoncontrollingInterest", *key))
        reported = by_key.get(("NetIncomeLoss", *key))
        if nci is None or reported is not None or not total.accession:
            continue
        result.append(
            F.Fact(
                "NetIncomeLoss",
                total.period_start,
                total.period_end,
                total.value - nci.value,
                total.unit,
                max(total.available_at, nci.available_at),
                total.accession,
                total.form,
                max(total.revision_id, nci.revision_id),
                f"{TAG_VERSION}:ProfitLoss({total.fact_id})-NCI({nci.fact_id})",
            )
        )
    return result


def core_fundamentals(facts: list[F.Fact], decision_at: datetime) -> dict[str, Any]:
    result = BASE_CORE(parent_income_facts(facts, decision_at), decision_at)
    for field in result.values():
        if any(str(p.get("fact_id", "")).startswith(TAG_VERSION) for p in field["provenance"]):
            field["mapping_version"] = TAG_VERSION
            field["mapping_formula"] = (
                "NetIncomeLoss = ProfitLoss - NCI (same accession/period/USD)"
            )
    return result


def semantic_review(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Explicitly review high-impact concepts; lexical inventory is NOT a tag map."""
    result = []
    for row in inventory:
        if row["issuer_month_impact"] < 100 and row["issuer_count"] < 5:
            continue
        name = row["concept"]
        family, status, candidate, confidence = (
            "NON_EQUIVALENT_COMPONENT_OR_DISCLOSURE",
            "REJECTED_DIRECT_MAPPING",
            None,
            "HIGH",
        )
        if name in {"ProfitLoss", "NetIncomeLossAttributableToNoncontrollingInterest"}:
            family = "CONSOLIDATED_INCOME" if name == "ProfitLoss" else "NONCONTROLLING_INCOME"
            status, candidate = "ACCEPTED_SAME_ACCESSION_COMPOSITE_ONLY", "fund_net_margin"
        elif (
            name.startswith("AvailableForSale")
            or name.startswith("Availableforsale")
            or "AvailableForSale" in name
            or "Availableforsale" in name
        ):
            family = "INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW"
        elif "NetIncomeLossAvailableToCommonStockholders" in name:
            family = "COMMON_STOCKHOLDER_EARNINGS_AFTER_PREFERRED_ADJUSTMENTS"
        elif "ProForma" in name or "BusinessAcquisition" in name:
            family = "ACQUISITION_PRO_FORMA_OR_ACQUIREE_COMPONENT"
        elif "Noncontrolling" in name:
            family = "NONCONTROLLING_INCOME_COMPONENT"
        elif (
            "Segment" in name
            or "Geographic" in name
            or "MajorCustomer" in name
            or "RelatedPart" in name
        ):
            family = "SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT"
        elif "Revenue" in name or "Sales" in name:
            family = "REVENUE_COMPONENT_OR_OTHER_FLOW"
            if name in {
                "SalesRevenueGoodsNet",
                "SalesRevenueServicesNet",
                "OtherSalesRevenueNet",
                "ElectricUtilityRevenue",
                "OilAndGasRevenue",
                "ContractsRevenue",
                "HealthCareOrganizationPatientServiceRevenue",
            }:
                status, candidate, confidence = (
                    "DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT",
                    "fund_net_margin;fund_revenue_yoy",
                    "CONDITIONAL",
                )
        elif "Adjustments" in name or "Accounting" in name:
            family = "CASH_FLOW_RECONCILIATION_OR_ACCOUNTING_CHANGE"
        elif "ProfitLoss" in name or "NetIncome" in name:
            family = "INCOME_COMPONENT_NOT_PARENT_NET_INCOME"
        result.append(
            {
                **row,
                "semantic_family": family,
                "candidate_standard_feature": candidate,
                "semantic_confidence": confidence,
                "mapping_possible": status == "ACCEPTED_SAME_ACCESSION_COMPOSITE_ONLY",
                "mapping_status": status,
                "source": PRIMARY_TAXONOMY,
                "impact_is_association_not_recovery": True,
            }
        )
    return result


def recovery(before: list[dict[str, Any]], after: list[dict[str, Any]], stage: str) -> int:
    def keys(rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
        return {
            (r["issuer_id"], r["month"]) for r in rows if r["issuer_id"] and r["eligibility"][stage]
        }

    return len(keys(after) - keys(before))


def ranked_cases(rows: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
    cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if category in r["blockers"]:
            cases[r["security_id"]].append(r)
    return sorted(
        [
            {
                "security_id": sid,
                "security_periods": len(rs),
                "membership_eligible_periods": sum("MEMBERSHIP" not in r["blockers"] for r in rs),
                "potential_combined_periods": sum(
                    not ({"MEMBERSHIP", "FUNDAMENTALS"} & set(r["blockers"])) for r in rs
                ),
                "reasons": sorted({r["reasons"].get(category, category) for r in rs}),
                "symbols": sorted({r["price_symbol"] for r in rs if r["price_symbol"]}),
            }
            for sid, rs in cases.items()
        ],
        key=lambda c: (
            -c["potential_combined_periods"],
            -c["membership_eligible_periods"],
            -c["security_periods"],
            c["security_id"],
        ),
    )


def dated_alias_candidate(record: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any] | None:
    """A primary exact dated alias can bind a class; a current ticker alone cannot."""
    if not record.get("issuer_primary_match") or not record.get("primary_issuer_id"):
        return None
    aliases = [
        a
        for a in record.get("dated_ticker_aliases", [])
        if a.get("bounds") == "EXACT"
        and a.get("from")
        and a["from"] <= "2021-09-30"
        and a.get("source_hash")
        and a["ticker"] in profile.get("tickers", [])
    ]
    return max(aliases, key=lambda a: (a["from"], a["ticker"])) if aliases else None
