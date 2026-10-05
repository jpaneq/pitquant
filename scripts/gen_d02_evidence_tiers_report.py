# ruff: noqa: E501
"""Generate membership validity/completeness and outcome-blind selection audit."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pitquant.research.membership_evidence import classify

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs"


def main() -> None:
    readiness = json.loads((DOC / "DATA_READINESS_FIRST_ML.json").read_text())
    projection = json.loads((DOC / "D02_MEMBERSHIP_ELIGIBILITY.json").read_text())
    baseline = json.loads((DOC / "D02_CRITICAL_PATH_RESULT_PRE_EVIDENCE_TIERS.json").read_text())
    manifest = json.loads((DOC / "D02_MEMBERSHIP_SOURCE_MANIFEST.json").read_text())
    cards = []
    for original in baseline["inside_critical_cards"]:
        ua = original["gap_id"] == "6c5a95f6a607858fc601"
        conflict = original["evidence_availability"] == "ARCHIVED_PRIMARY_INCONSISTENT"
        tier = classify([], identity_supported=False, conflicted=conflict)
        if ua:
            tier = projection["under_armour"]["evidence_tier"]
        cards.append(
            {
                **original,
                "evidence_tier": tier,
                "evidence_version": projection["evidence_version"],
                "effective_date": "2016-04-08" if ua else None,
                "research_disposition": "ACCEPTED_DATED_CLASS_C_EVENT"
                if ua
                else "EXCLUDE_UNCERTAIN_SECURITY_PERIOD",
                "blocks_research_month": False,
                "provenance": manifest["under_armour"]
                if ua
                else {
                    "cache_checked": True,
                    "cache_inventory": "D02_CRITICAL_PATH_RESULT_PRE_EVIDENCE_TIERS.json:membership_provenance,critical_weak_identity_proofs",
                    "historical_sources_checked": [
                        manifest["sources"][k]["archive_id"]
                        for k in ("clenow_original", "wikipedia_history")
                    ],
                    "primary_evidence": "Existing dated anchors and identifier cache do not establish this missing event/identity link.",
                    "budget_stop": "Exact class-preserving event/date not established in bounded cache/history pass. No ticker/name guesses or prolonged search.",
                },
            }
        )
    rows = projection["rows"]
    excluded = [r for r in rows if not r["membership_research_eligible"]]
    evidence_excluded = [r for r in excluded if r["evidence_tier"] in ("UNVERIFIED", "CONFLICTED")]
    monthly = projection["months"]
    bias = {
        "outcome_blind": True,
        "future_returns_used_for_selection": False,
        "configured_security_periods": len(rows),
        "excluded_security_periods": len(excluded),
        "excluded_for_missing_or_conflicting_evidence": len(evidence_excluded),
        "verified_nonmember_periods": len(excluded) - len(evidence_excluded),
        "securities_affected": sorted({r["security_id"] for r in excluded}),
        "tickers_affected": sorted({r["ticker_label"] for r in excluded}),
        "evidence_tickers_affected": sorted({r["ticker_label"] for r in evidence_excluded}),
        "issuers_affected": sorted({r["issuer_id"] for r in excluded if r["issuer_id"]}),
        "sectors_affected": dict(sorted(Counter(r["sector"] for r in excluded).items())),
        "evidence_sectors_affected": dict(
            sorted(Counter(r["sector"] for r in evidence_excluded).items())
        ),
        "sector_metadata_note": "Current descriptive sector grouping, diagnostic only; UNKNOWN retained; no predictor or historical sector assertion.",
        "rows_lost": sum(m["rows_lost"] for m in monthly),
        "rows_lost_evidence": sum(m["rows_lost_evidence"] for m in monthly),
        "months": monthly,
        "survivorship_caveat": "Configured research universe remains the existing 55 US securities, not a complete historical S&P universe. This iteration does not certify statistical coverage or remove that limitation.",
    }
    result = {
        "version": "d02-membership-evidence-tiers-v1",
        "initial_head": "01eb216ccbffac248ccc270f88ef05498e797b63",
        "before": baseline["after"],
        "after": readiness["d02"],
        "required_history": readiness["required_history"],
        "required_months": len(monthly),
        "required_months_blocked": sum(m["status"] != "READY" for m in monthly),
        "classified_cards": cards,
        "evidence_tier_counts": {
            tier: sum(c["evidence_tier"] == tier for c in cards)
            for tier in ("OFFICIAL_DIRECT", "CORROBORATED_HISTORICAL", "UNVERIFIED", "CONFLICTED")
        },
        "strict_unresolved_cards_preserved": len(cards),
        "membership_validity": readiness["membership_validity"],
        "membership_completeness": bias,
        "folds": readiness["folds"],
        "fold_readiness": readiness["fold_readiness"],
        "gates": readiness["gates"],
        "under_armour": projection["under_armour"],
        "newly_valid_months": [
            m["month"]
            for m in monthly
            if m["strict_status"] != "MEMBERSHIP_READY" and m["status"] == "READY"
        ],
        "required_securities": readiness["coverage"]["required"],
        "models_trained": False,
        "stop_reason": "Three LABEL_SAFE folds certified; statistical coverage remains unapproved."
        if readiness["fold_readiness"]["label_safe_folds"] >= 3
        else "Required temporal folds remain blocked; no training.",
    }
    (DOC / "D02_CRITICAL_PATH_RESULT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    (DOC / "D02_MEMBERSHIP_COMPLETENESS.json").write_text(
        json.dumps(bias, indent=2, sort_keys=True) + "\n"
    )
    md = [
        "# D02: evidence tiers y exclusiones temporales\n",
        f"{readiness['d02']['required_months_ready']}/{len(monthly)} meses requeridos válidos; {readiness['d02']['calendar_folds']} CALENDAR_FOLD y {readiness['d02']['label_safe_folds']} LABEL_SAFE_FOLD. ML_ELIGIBLE_FOLD sigue NOT_YET_EVALUATED. Ningún modelo entrenado.\n",
        "La validez se refiere a todas las filas incluidas. La completitud se informa por separado: las securities UNVERIFIED/CONFLICTED se excluyen por fecha. La reconstrucción estricta anterior conserva sus 49 fichas y no se transforma en universo diario canónico.\n",
        "Under Armour Class C: ADD 2016-04-08 CORROBORATED_HISTORICAL, nunca OFFICIAL_DIRECT. Dos orígenes: Clenow/Trading Evolved pre-2019 y Wikipedia (snapshot 2021 archivado por Analyzing Alpha); SEC/OCC prueban la identidad/clase. Las actualizaciones FJA posteriores a 2019 comparten Wikipedia y no cuentan como otra corroboración independiente. No se sigue buscando S&P para UA.\n",
        "## Fichas críticas\n",
        "| gap_id | security | tier | disposición |",
        "|---|---|---|---|",
    ]
    md += [
        f"| {c['gap_id']} | {c['security']} | {c['evidence_tier']} | {c['research_disposition']} |"
        for c in cards
    ]
    md += [
        "\n## Completitud por mes\n",
        "| mes | configuradas | elegibles | issuers | UNVERIFIED | CONFLICTED | no miembro verificado | filas perdidas | cobertura % |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    md += [
        f"| {m['month']} | {m['configured_relevant_securities']} | {m['eligible_securities']} | {m['eligible_issuers']} | {m['unverified_excluded']} | {m['conflicted_excluded']} | {m['verified_nonmember_excluded']} | {m['rows_lost']} | {m['coverage_pct']} |"
        for m in monthly
    ]
    md += [
        "\n## Sesgo de selección\n",
        f"{len(excluded)} security-periods excluidos; {len(evidence_excluded)} por evidencia insuficiente/conflictiva. {bias['rows_lost']} filas perdidas, {bias['rows_lost_evidence']} por evidencia. Securities: {', '.join(bias['tickers_affected'])}. Sectores descriptivos: {bias['sectors_affected']}.\n",
        "El catálogo sigue siendo un subconjunto configurado, con limitación de supervivencia. No se miraron retornos, drawdowns, scores ni performance para seleccionar. La suficiencia y el ESS quedan para el coverage gate.\n",
        "## Folds\n",
    ]
    for fold in readiness["fold_readiness"]["folds"]:
        f = fold["dates"]
        md.append(
            f"F{fold['index'] + 1}: TRAIN {f['train_start']}→{f['train_end']}; purge {f['excluded_decision_start']}→{f['excluded_decision_end']}; embargo {f['embargo_start']}→{f['embargo_end']}; TEST {f['test_start']}→{f['test_end']}; LABEL_SAFE={fold['label_safe']}; TEST filas={fold['TEST']['eligible_rows']}, securities={fold['TEST']['eligible_securities']}, issuers={fold['TEST']['eligible_issuers']}.\n"
        )
    md += [
        "\nProvenance completo: D02_MEMBERSHIP_SOURCE_MANIFEST.json y D02_MEMBERSHIP_ELIGIBILITY.json. Ledger inmutable en raw_source_archive (hash y versión fijados). ADR-0056. Holdout/OOT, targets, features y required_securities=100 intactos.\n"
    ]
    (DOC / "D02_CRITICAL_PATH_FIRST_ML.md").write_text("\n".join(md))


if __name__ == "__main__":
    main()
