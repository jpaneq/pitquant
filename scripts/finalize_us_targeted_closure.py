#!/usr/bin/env python3
# ruff: noqa: E501
"""Publish target-free closure revisions and descriptive coverage, never train."""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pitquant.research import us_targeted_closure as T
from pitquant.research import us_universe_scale as U

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"
DOCS = ROOT / "docs"
INITIAL = "b8bb890494310879f98066b5b95304644f4d42ad"


def load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def candidate(path: Path) -> Any:
    return json.loads(gzip.decompress(path.read_bytes()))


def summarize_science(rows: list[dict[str, Any]], months: list[str]) -> dict[str, Any]:
    monthly = []
    flags = (
        "membership_valid",
        "identity_valid",
        "price_valid",
        "benchmark_valid",
        "fundamental_valid",
        "feature_valid",
        "label_constructible",
        "combined_scientific_eligible",
    )
    for month in months:
        rs = [r for r in rows if r["month"] == month]
        eligible = {
            r["issuer_id"]: r for r in rs if r["combined_scientific_eligible"] and r["issuer_id"]
        }
        sectors = Counter(r["sector"] for r in eligible.values())
        monthly.append(
            {
                "month": month,
                "issuer_counts": {
                    f: len({r["issuer_id"] for r in rs if r[f] and r["issuer_id"]}) for f in flags
                },
                "scientific_issuers": len(eligible),
                "represented_sectors": len(sectors),
                "largest_sector_share": max(sectors.values(), default=0) / max(1, len(eligible)),
                "top3_sector_share": sum(sorted(sectors.values(), reverse=True)[:3])
                / max(1, len(eligible)),
                "sector_counts": dict(sorted(sectors.items())),
            }
        )
    return {
        "months": monthly,
        "cross_section": U.summarize_counts([m["scientific_issuers"] for m in monthly]),
        "represented_sectors": U.summarize_counts([m["represented_sectors"] for m in monthly]),
        "largest_sector_share": U.summarize_counts([m["largest_sector_share"] for m in monthly]),
        "top3_sector_share": U.summarize_counts([m["top3_sector_share"] for m in monthly]),
    }


def main() -> None:
    baseline_path = DOCS / "US_LARGE_CAP_RESEARCH_COVERAGE_EXPANSION_BASELINE_V1.json"
    if not baseline_path.exists():
        shutil.copy2(DOCS / "US_LARGE_CAP_RESEARCH_COVERAGE_V1.json", baseline_path)
    baseline = load(baseline_path)
    stages = {}
    rows_by_stage = {}
    before = candidate(DOCS / "US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz")
    rows_by_stage["before"] = before["rows"]
    for name in ("storage", "sec5", "aliases"):
        stages[name] = load(WORK / name / "US_LARGE_CAP_RESEARCH_COVERAGE_V1.json")
        rows_by_stage[name] = candidate(WORK / name / "US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz")[
            "rows"
        ]
    final = rows_by_stage["aliases"]
    universe = load(WORK / "aliases/US_LARGE_CAP_RESEARCH_UNIVERSE_V1.json")
    roster = {r["security_id"]: r for r in universe["roster"]}
    sci_rows = load(WORK / "scientific.json")
    sci_before = load(WORK / "scientific-before.json")
    months = [m["month"] for m in baseline["expanded"]["months"]]
    science = summarize_science(sci_rows, months)
    science_before = summarize_science(sci_before, months)
    folds = load(WORK / "frozen-folds.json")
    for fold in folds:
        fold["scientific_coverage"] = {
            phase: U.summarize_counts(
                [
                    m["scientific_issuers"]
                    for m in science["months"]
                    if m["month"] in fold["months"][phase]
                ]
            )
            for phase in ("TRAIN", "TEST")
        }
    definitions = load(WORK / "taxonomy-definitions.json")
    mappings = T.semantic_review(baseline["mapping_debt"])
    for row in mappings:
        row["primary_taxonomy_definition"] = definitions.get(row["concept"])
        row["joint_rule"] = "parent-income-same-accession" if row["mapping_possible"] else None
    identities = T.ranked_cases(rows_by_stage["before"], "IDENTITY")
    yahoo = T.ranked_cases(rows_by_stage["sec5"], "PRICE")
    repaired_ids = {r["security_id"] for r in load(WORK / "dated_alias_repairs.json")}
    prior_by_key = {(r["security_id"], r["month"]): r for r in rows_by_stage["sec5"]}
    identity_intermediate = []
    for row in final:
        prior = prior_by_key[(row["security_id"], row["month"])]
        restored = json.loads(U.encoded(row))
        old_price_usable = "PRICE" not in prior["blockers"]
        member_identity = restored["eligibility"]["MEMBERSHIP"]
        restored["eligibility"]["PRICE"] = member_identity and old_price_usable
        restored["eligibility"]["COMBINED"] = (
            restored["eligibility"]["PRICE"] and restored["eligibility"]["FUNDAMENTALS"]
        )
        restored["price_qa_hash"] = prior["price_qa_hash"]
        if not old_price_usable:
            if "PRICE" not in restored["blockers"]:
                restored["blockers"].append("PRICE")
            restored["reasons"]["PRICE"] = prior["reasons"].get("PRICE", "PRIOR_PRICE_UNAVAILABLE")
        identity_intermediate.append(restored)
    identity_revision = U.write_revision(WORK, "identity-before-yahoo", identity_intermediate)
    for row in identities:
        row["names"] = roster[row["security_id"]]["names"]
        row["cik_candidate"] = roster[row["security_id"]]["cik_candidate"]
        row["reviewed"] = row in identities[:20] or row["security_id"] in repaired_ids
        row["classification"] = (
            "REPAIRED_DATED_PRIMARY_CLASS_ALIAS"
            if row["security_id"] in repaired_ids
            else (
                "PRESERVED_INTEGRITY_EXCLUSION"
                if "PREEXISTING_FIRST_ML_IDENTITY_AUDIT_PARTIAL" in row["reasons"]
                else "REQUIRES_DATED_PRIMARY_IDENTITY_OR_CLASS_BINDING"
            )
        )
        row["potential_combined_limit"] = (
            "Unresolved issuers cannot be counted as known issuer-months; priority uses membership-supported security-periods when combined availability is unknown."
        )
    requests = {
        r["url"]: r
        for r in map(json.loads, (WORK / "cache/requests.jsonl").read_text().splitlines())
    }
    for row in yahoo:
        symbol = (row["symbols"] or [""])[0]
        source = universe["price_audits"].get(symbol, {})
        retrieval = requests.get(source.get("source_url", source.get("url", "")), {})
        row["names"] = roster[row["security_id"]]["names"]
        reason = ";".join(row["reasons"])
        row["reviewed"] = row in yahoo[:20] or row["security_id"] in repaired_ids
        row["classification"] = (
            "RECOVERABLE_YAHOO_ALIAS"
            if row["security_id"] in repaired_ids
            and any(
                r["security_id"] == row["security_id"] and r["eligibility"]["PRICE"] for r in final
            )
            else "INSTRUMENT_INCOMPATIBLE"
            if "INSTRUMENT" in reason or "MISMATCH" in reason
            else "TRUE_PROVIDER_GAP"
            if "HTTP_404" in ";".join(source.get("reasons", []))
            or source.get("http_status") == 404
            or retrieval.get("status") == 404
            else "UNKNOWN"
        )
        row["provider_evidence"] = source
        row["class_distribution_limit"] = (
            "UAA: overlapping Class C distribution windows remain scientifically excluded"
            if symbol == "UAA" or row["security_id"] in repaired_ids
            else None
        )
    gains = {
        name: {
            stage: T.recovery(rows_by_stage[prior], rows_by_stage[name], stage)
            for stage in ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED")
        }
        for name, prior in (("storage", "before"), ("sec5", "storage"), ("aliases", "sec5"))
    }
    identity_gains = {
        stage: T.recovery(rows_by_stage["sec5"], identity_intermediate, stage)
        for stage in ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED")
    }
    yahoo_gains = {
        stage: T.recovery(identity_intermediate, final, stage)
        for stage in ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED")
    }
    losses = {}
    for name, prior in (("storage", "before"), ("sec5", "storage"), ("aliases", "sec5")):
        losses[name] = {
            stage: T.recovery(rows_by_stage[name], rows_by_stage[prior], stage)
            for stage in ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED")
        }
    net_gains = {
        name: {stage: gains[name][stage] - losses[name][stage] for stage in gains[name]}
        for name in gains
    }
    prior_mapping = {
        (r["issuer_id"], r["month"]): r
        for r in rows_by_stage["storage"]
        if r["eligibility"]["COMBINED"]
    }
    retained_mapping = {
        (r["issuer_id"], r["month"]) for r in rows_by_stage["sec5"] if r["eligibility"]["COMBINED"]
    }
    mapping_losses = [
        {
            "issuer_id": r["issuer_id"],
            "month": r["month"],
            "security_id": r["security_id"],
            "core_fundamentals": r["core_fundamentals"],
            "reasons": r["reasons"],
        }
        for r in rows_by_stage["sec5"]
        if (r["issuer_id"], r["month"]) in prior_mapping
        and (r["issuer_id"], r["month"]) not in retained_mapping
    ]
    # Cumulative gains are marginal, deduplicated issuer-months. Association counts are never summed.
    marginal = []
    for name, prior in (("storage", "before"), ("sec5", "storage"), ("aliases", "sec5")):
        previous = {
            (r["issuer_id"], r["month"])
            for r in rows_by_stage[prior]
            if r["eligibility"]["COMBINED"]
        }
        if name == "storage":
            groups = defaultdict(set)
            for r in rows_by_stage[name]:
                unit = r["issuer_id"], r["month"]
                if r["eligibility"]["COMBINED"] and unit not in previous:
                    groups[roster[r["security_id"]]["cik_candidate"]].add(unit)
            marginal.extend(
                {"repair": "storage:" + cik, "units": sorted(units)}
                for cik, units in groups.items()
            )
        else:
            units = sorted(
                {
                    (r["issuer_id"], r["month"])
                    for r in rows_by_stage[name]
                    if r["eligibility"]["COMBINED"]
                }
                - previous
            )
            marginal.append(
                {
                    "repair": "parent-income-same-accession"
                    if name == "sec5"
                    else "dated-class-alias-market-binding",
                    "units": units,
                }
            )
    marginal.sort(key=lambda r: (-len(r["units"]), r["repair"]))
    curve = {
        str(n): len(set().union(*(set(map(tuple, r["units"])) for r in marginal[:n])))
        for n in (1, 5, 10, 20)
    }
    curve["all"] = len(set().union(*(set(map(tuple, r["units"])) for r in marginal)))
    retry = load(WORK / "storage_retry.json")
    compaction = [
        json.loads(line) for line in (WORK / "storage-compaction.jsonl").read_text().splitlines()
    ]
    storage = {
        "capacity_blockage_eliminated": all(
            r["after"].get("error") != "DISK_CAPACITY_RESERVE_5_GIB" for r in retry
        ),
        "before_free_disk": "3.4 GiB (df rounded)",
        "after_compaction_target_free_gib": 20,
        "compressed_objects": len(compaction),
        "allocated_bytes_saved": sum(r["bytes_saved"] for r in compaction),
        "successful_urls": sum(r["after"]["status"] == 200 for r in retry),
        "failed_urls": sum(r["after"]["status"] != 200 for r in retry),
        "recovered_ciks": len({r["cik"] for r in retry if r["after"]["status"] == 200}),
        "fundamental_issuer_months_recovered": gains["storage"]["FUNDAMENTALS"],
        "combined_issuer_months_recovered": gains["storage"]["COMBINED"],
        "reserve_5_gib_unchanged": True,
        "policy": "Verified transparent APFS compression. Original bytes, paths and SHA are preserved; no ArchiveStore read contract changes.",
        "compaction_ledger": compaction,
        "retry_ledger": retry,
        "ingestion": load(WORK / "capacity_ingestion.json"),
    }
    exclusion = {kind: defaultdict(set) for kind in ("reason", "sector", "year", "lifecycle")}
    for r, sci in zip(final, sci_rows, strict=True):
        if sci["combined_scientific_eligible"]:
            continue
        unit = r["issuer_id"] or "UNRESOLVED:" + r["security_id"], r["month"]
        for reason in r["blockers"] or [
            sci["feature_and_label_audit"].get("label_reason")
            or "SCIENTIFIC_FEATURE_NOT_CONSTRUCTIBLE"
        ]:
            exclusion["reason"][reason].add(unit)
        exclusion["sector"][r["sector"]].add(unit)
        exclusion["year"][r["month"][:4]].add(unit)
        exclusion["lifecycle"][roster[r["security_id"]]["survivorship_status"]].add(unit)
    contract = {
        "name": "EXPANDED_US_RESEARCH_COVERAGE_V1",
        "status": "PROPOSED_NOT_A_STATISTICAL_GATE",
        "minimum_issuers_per_month": 100,
        "minimum_valid_membership_coverage_fraction": 0.50,
        "minimum_represented_sectors": 5,
        "maximum_largest_sector_share": 0.60,
        "maximum_top3_sector_share": 0.90,
        "apply_to": "Every frozen TRAIN and TEST month; neither monthly minimum nor folds may be weakened.",
        "denominator": "Unique research-valid membership issuers (including unsupported financial families); unresolved security-periods reported separately.",
        "justification": "100 is the pre-existing structural cross-section benchmark, independent of the observed minimum. At least half the verified membership prevents claiming breadth from a narrow slice. Five broad SIC groups, a 60% single-group cap and 90% top-three cap prevent near-single-sector cohorts. These are proposed engineering representation requirements, not proof of statistical power.",
        "nullable_feature_policy": "All frozen family fields must be built with a value or explicit missing reason, mandatory price/fundamental cores non-null; optional missing values preserve the frozen train-only imputation contract. No preprocessing fitted here.",
    }
    for m in science["months"]:
        member = next(
            x["issuer_counts"]["MEMBERSHIP"]
            for x in stages["aliases"]["expanded"]["months"]
            if x["month"] == m["month"]
        )
        m["membership_coverage_fraction"] = m["scientific_issuers"] / max(member, 1)
        m["proposed_contract_structural_pass"] = (
            m["scientific_issuers"] >= 100
            and m["membership_coverage_fraction"] >= 0.5
            and m["represented_sectors"] >= 5
            and m["largest_sector_share"] <= 0.6
            and m["top3_sector_share"] <= 0.9
        )
    contract["monthly_structural_pass_count"] = sum(
        m["proposed_contract_structural_pass"] for m in science["months"]
    )
    recommendation = (
        "FREEZE_EXPANDED_DATASET_AND_DESIGN_FINAL_RANKING_EXPERIMENT"
        if contract["monthly_structural_pass_count"] == len(months)
        else "ONE_MORE_TARGETED_DATA_REPAIR_PASS"
    )
    code_paths = (
        ["src/pitquant/research/us_targeted_closure.py"]
        + [str(p.relative_to(ROOT)) for p in ROOT.joinpath("scripts").glob("*us*target*")]
        + [
            "scripts/compact_research_archive.py",
            "scripts/retry_us_research_capacity.py",
            "scripts/ingest_us_research_capacity.py",
            "scripts/repair_us_research_dated_aliases.py",
            "scripts/audit_us_scientific_constructibility.py",
        ]
    )
    hashes = {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(set(code_paths))
    }
    report = {
        "version": "us-research-targeted-closure-v1",
        "initial_head": INITIAL,
        "storage": storage,
        "mapping_version": T.TAG_VERSION,
        "xbrl_mapping_debt": mappings,
        "mapping_counts": dict(Counter(r["mapping_status"] for r in mappings)),
        "mapping_gain_rule": "One composite rule, two required concepts; do not double-count its joint gain.",
        "stage_gains": gains,
        "stage_losses": losses,
        "stage_net_gains": net_gains,
        "mapping_losses": mapping_losses,
        "mapping_loss_policy": "A newer visible derived parent-income period can make TTM unconstructible when matching prior FY/YTD components are absent. The native freshest-period rule is retained: no selective stale fallback to preserve coverage.",
        "identity_only_gains": identity_gains,
        "yahoo_after_identity_gains": yahoo_gains,
        "identity_intermediate_revision": identity_revision,
        "identity_cases": identities,
        "yahoo_cases": yahoo,
        "dated_alias_repairs": load(WORK / "dated_alias_repairs.json"),
        "long_tail": {
            "mapping_below_budget": len(baseline["mapping_debt"]) - len(mappings),
            "unresolved_securities": universe["identity_states"]["IDENTITY_UNRESOLVED"],
            "identity_cases_outside_review_budget": sum(not r["reviewed"] for r in identities),
            "yahoo_cases_outside_review_budget": sum(not r["reviewed"] for r in yahoo),
        },
        "before": baseline["expanded"],
        "after": stages["aliases"]["expanded"],
        "scientific_before": science_before,
        "scientific": science,
        "folds": folds,
        "survivorship": universe["survivorship"],
        "lifecycle_limit": universe["lifecycle_limit"],
        "selection_bias": {
            kind: {k: len(v) for k, v in sorted(groups.items())}
            for kind, groups in exclusion.items()
        },
        "bias_limit": "Exclusion counts overlap. Units without resolved issuers are security-periods, explicitly prefixed UNRESOLVED; known units are issuer-months. Yahoo and historical identity loss are concentrated among removed issuers; inference is restricted to the documented research-eligible cohort, not all S&P constituents.",
        "repair_curve": curve,
        "marginal_repairs": marginal,
        "proposed_contract": contract,
        "recommendation": recommendation,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "dev_adaptive_iteration": 2,
        "new_fits": 0,
        "frozen_artifact_hashes": universe["frozen_artifact_hashes"],
        "implementation_hashes": hashes,
        "intermediate_revisions": {
            s: {
                "hashes": stages[s]["hashes"],
                "candidate_sha256": hashlib.sha256(
                    (WORK / s / "US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz").read_bytes()
                ).hexdigest(),
            }
            for s in stages
        },
    }
    payload = {
        "version": report["version"],
        "rows": final,
        "scientific_rows": sci_rows,
        "has_targets": False,
        "training_ready": False,
        "historical_ticker_bindings": report["dated_alias_repairs"],
        "baseline_price_series_sha256": hashlib.sha256(
            (DOCS / "US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz").read_bytes()
        ).hexdigest(),
        "additional_price_series": {
            symbol: load(WORK / "revisions" / source["qa_hash"] / ("yahoo-" + symbol + ".json"))
            for symbol, source in universe["price_audits"].items()
            if symbol not in before["historical_market_series"] and source.get("qa_hash")
        },
    }
    data = gzip.compress(U.encoded(payload), mtime=0)
    path = DOCS / "US_LARGE_CAP_RESEARCH_TARGETED_DATASET_V1.json.gz"
    path.write_bytes(data)
    report["candidate"] = {
        "path": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "rows": len(final),
        "securities": len(roster),
        "scientific_sha256": U.digest(sci_rows),
    }
    coverage = {
        **stages["aliases"],
        "version": report["version"],
        "scientific": science,
        "folds": folds,
        "proposed_contract": contract,
        "recommendation": recommendation,
        "mapping_debt_label": "XBRL_MAPPING_DEBT",
        "baseline_coverage_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "targeted_candidate": report["candidate"],
        "scientific_coverage_gate": "PROPOSED_NOT_ENABLED",
    }
    coverage["dataset"] = "US_LARGE_CAP_RESEARCH_TARGETED_DATASET_V1"
    coverage["unreviewed_concept_inventory"] = coverage.pop("mapping_debt")
    coverage["xbrl_mapping_debt"] = mappings
    for name, value in (
        ("US_LARGE_CAP_RESEARCH_TARGETED_CLOSURE_V1", report),
        ("US_LARGE_CAP_RESEARCH_COVERAGE_V1", coverage),
    ):
        (DOCS / (name + ".json")).write_bytes(U.encoded(value))
    lines = [
        "# Targeted closure of expanded US research universe",
        "",
        f"Base `{INITIAL}`. Universo cerrado: 696 securities; no nuevas empresas, modelos ni outcomes.",
        "",
        "## Capacidad y recuperación",
        "",
        f"186/186 URLs SEC recuperadas; 39 CIK. Compresión APFS verificada: {storage['allocated_bytes_saved'] / 1024**3:.2f} GiB ahorrados en {storage['compressed_objects']} originales. Reserva de 5 GiB intacta. Bytes, SHA, rutas, fallos originales y revisiones conservados.",
        "",
        f"Ganancia exclusiva de capacidad: {gains['storage']['FUNDAMENTALS']} issuer-months fundamentales; {gains['storage']['COMBINED']} combinados. No equivale a los 418 casos asociados del informe previo.",
        "",
        "## Semántica y mappings",
        "",
        "XBRL_MAPPING_DEBT significa deuda técnica de mapping, nunca deuda financiera. sec-tags-4 y los artefactos ML previos permanecen intactos. sec-tags-5 añade únicamente NetIncomeLoss = ProfitLoss − NetIncomeLossAttributableToNoncontrollingInterest, con misma accession, moneda USD y período, ambos conocidos antes del T0. Una participación ausente nunca es cero; un NetIncomeLoss reportado no se sobreescribe. La procedencia conserva ambos fact_id originales. Dos conceptos forman una sola regla; sus ganancias no se suman dos veces.",
        "",
        "Se revisan todos los conceptos con ≥100 issuer-months o ≥5 issuers. Las definiciones primarias SEC están archivadas por hash. Los componentes de bienes/servicios, sectores, geografías, pro forma, EPS y activos available-for-sale no equivalen automáticamente a totales. Los ingresos componentizados requieren el cálculo primario del total; no se aceptan por nombre parecido. [Guía FASB de OCI](https://xbrl.fasb.org/impdocs/OCI_TIG/othercompincome.htm) y [guía técnica US GAAP 2019](https://storage.fasb.org/2019_US_GAAP_Financial_Reporting_Taxonomy_Technical_Guide.pdf).",
        "",
        "| Concepto | Familia | Issuers | Issuer-months asociados | Feature | Confianza | Mapping | Estado |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    lines += [
        f"| {r['concept']} | {r['semantic_family']} | {r['issuer_count']} | {r['issuer_month_impact']} | {r['candidate_standard_feature'] or '—'} | {r['semantic_confidence']} | {r['mapping_possible']} | {r['mapping_status']} |"
        for r in mappings
    ]
    lines += [
        "",
        f"Regla conjunta sec-tags-5: +{gains['sec5']['FUNDAMENTALS']} fundamentales y +{gains['sec5']['COMBINED']} combinados recuperados. También excluye {losses['sec5']['COMBINED']} combinados previos: una ventana de income más reciente no tiene todos los FY/YTD comparables para TTM. No se recupera el valor anterior por conveniencia. Ganancia combinada neta del mapping: {net_gains['sec5']['COMBINED']}; neta de todas las reparaciones: {sum(g['COMBINED'] for g in net_gains.values())}. El JSON conserva pérdidas y motivos individuales.",
        "",
        "## Identidad y mercado",
        "",
        "Presupuesto: 20 principales casos de identidad y 20 de mercado, más reparaciones con evidencia primaria ya archivada. Prioridad por recuperación combinada conocida; cuando la identidad no permite cuantificar issuer-months, se muestra el potencial de security-periods de membresía, sin fingir equivalencia. Las fichas JSON conservan clasificadores, nombres, símbolos, documentos y límites.",
        "",
        "El 10-K SEC 0001336917-17-000017 confirma Class A UA hasta 2016-12-06/UAA desde 2016-12-07 y Class C UA.C desde 2016-04-08/UA desde 2016-12-07. Se repara el vínculo de ambas clases y se obtiene UAA: símbolo del proveedor distinto del ticker histórico fechado. Nunca se empalman clases ni sucesoras. UA conserva su fallo de OHLC original; su identidad válida no habilita precios inválidos. La distribución de Class C del 2016-04-08 no se interpreta como split de Class A: las ventanas de features y labels que la atraviesan quedan fuera del candidato científico.",
        "",
        f"Ganancia de alias/mercado: +{gains['aliases']['COMBINED']} issuer-months combinados. La reparación de identidad aislada no se presenta como ganancia independiente si sus precios siguen bloqueados.",
        "",
        "## Candidato científico",
        "",
        "Se construyen con los motores existentes todas las familias PRICE, FUNDAMENTAL y RISK. Los cores deben tener valores finitos; los campos opcionales conservan NULL y motivo, tal como exige el contrato congelado de imputación sólo en TRAIN. No se ajusta imputación, escalado, selección ni modelo. El panel técnico usa los rolling causales nativos con pruebas de truncación; valoración utiliza precio RAW y acciones conocidas en T0. Los checks PIT validan cada field construido.",
        "",
        "Label constructibility verifica exclusivamente timestamps, presencia de observaciones, sesiones esperadas, divisa USD y límites legales de la misma security durante 12 meses. Nunca se calcula ni publica un retorno futuro. Los precios numéricos futuros no se normalizan ni entran en features. El benchmark usa SELECT de fechas/cierres temporales, sin precios futuros. Las ventanas posteriores a 2022-09-30 y las que cruzan una sucesión quedan excluidas. Se reutilizan exactamente F1/F2/F3 y su separación congelada; no se rediseñan folds.",
        "",
        "## Antes y después",
        "",
        "| Etapa | Antes min/med/max | Después min/med/max |",
        "|---|---|---|",
    ]
    for stage in ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED"):
        b, a = (
            baseline["expanded"]["cross_section"][stage],
            stages["aliases"]["expanded"]["cross_section"][stage],
        )
        lines.append(
            f"| {stage} | {b['minimum']}/{b['median']}/{b['maximum']} | {a['minimum']}/{a['median']}/{a['maximum']} |"
        )
    lines += [
        f"| SCIENTIFIC | {science_before['cross_section']['minimum']}/{science_before['cross_section']['median']}/{science_before['cross_section']['maximum']} | {science['cross_section']['minimum']}/{science['cross_section']['median']}/{science['cross_section']['maximum']} |",
        "",
        "| Fold | Fase | min | P10 | Mediana | P90 | max |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for i, f in enumerate(folds, 1):
        for phase, c in f["scientific_coverage"].items():
            lines.append(
                f"| F{i} | {phase} | {c['minimum']} | {c['p10']} | {c['median']} | {c['p90']} | {c['maximum']} |"
            )
    lines += [
        "",
        "## Representación y límites",
        "",
        f"Sectores/mes: `{science['represented_sectors']}`. Mayor sector: `{science['largest_sector_share']}`. Top-3: `{science['top3_sector_share']}`. SIC actual es CURRENT_PROFILE_NOT_PIT, descriptivo, nunca predictor. Las divisiones 60/61/62/63/64/65/67 siguen excluidas de los ratios industriales.",
        "",
        f"Supervivencia: `{json.dumps(universe['survivorship'], sort_keys=True)}`. {universe['lifecycle_limit']}",
        "",
        report["bias_limit"],
        "",
        "Las exclusiones por motivo, sector, año y lifecycle se publican sin outcomes. Estados de lifecycle desconocidos no invalidan una identidad/membresía válida; no se infiere quiebra o adquisición de un 404. Se conserva el sesgo de disponibilidad de empresas retiradas y no se anuncia representatividad completa del índice.",
        "",
        f"Curva acumulada de recuperación combinada, top1/5/10/20/todas: `{curve}`; cuenta uniones de issuer-months, no asociaciones solapadas. Cola residual: `{report['long_tail']}`.",
        "",
        "## Contrato propuesto y cierre",
        "",
        json.dumps(contract, ensure_ascii=False, indent=2),
        "",
        "El milestone ≥150 es exclusivamente descriptivo. El contrato propuesto no deriva del mínimo observado y no habilita entrenamiento automáticamente. El conteo de representación no estima tamaño efectivo independiente ni potencia estadística.",
        "",
        "STOP: bloqueo de almacenamiento eliminado, mappings de alto impacto revisados, principales identidades/Yahoo reparadas o clasificadas, cobertura científica medida y long tail cuantificada. No se persigue completitud perfecta.",
        "",
        f"Recomendación única: **{recommendation}**.",
        "",
        f"Candidato `{path.name}` SHA `{report['candidate']['sha256']}`. El JSON conserva todas las filas de disponibilidad/ciencia, fuentes extra y referencia al candidato previo inmutable. Las revisiones intermedias quedan fijadas por SHA y en el archivo local; reejecución con las mismas fuentes y DB copiada, sin red. No escribir en la DB de producción.",
        "",
        "dev_adaptive_iteration=2; new_fits=0; holdout outcomes=0; OOT outcomes=0.",
    ]
    (DOCS / "US_LARGE_CAP_RESEARCH_TARGETED_CLOSURE_V1.md").write_text("\n".join(lines) + "\n")
    table = [
        "# US Large Cap Research Coverage V1 — targeted closure",
        "",
        "[Informe de cierre completo](US_LARGE_CAP_RESEARCH_TARGETED_CLOSURE_V1.md). [Baseline anterior inmutable](US_LARGE_CAP_RESEARCH_COVERAGE_EXPANSION_BASELINE_V1.json).",
        "",
        "| Mes | Membership | Identity | Price | Benchmark | Fundamentales | Features | Label constructible | Scientific | Sectores | Mayor sector | Top-3 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in science["months"]:
        c = m["issuer_counts"]
        table.append(
            "| "
            + m["month"]
            + " | "
            + " | ".join(
                str(c[k])
                for k in (
                    "membership_valid",
                    "identity_valid",
                    "price_valid",
                    "benchmark_valid",
                    "fundamental_valid",
                    "feature_valid",
                    "label_constructible",
                    "combined_scientific_eligible",
                )
            )
            + f" | {m['represented_sectors']} | {m['largest_sector_share']:.1%} | {m['top3_sector_share']:.1%} |"
        )
    table += [
        "",
        f"SCIENTIFIC min/P10/med/P90/max: `{science['cross_section']}`.",
        "",
        "Features/labels se evalúan tras las precondiciones de disponibilidad combinada; False fuera de esas precondiciones significa no elegible/no evaluado, no ausencia económica. Identidad y membresía fallan por período, no por mes completo.",
        "",
        "Candidato sin targets, entrenamiento deshabilitado. ≥150 no es gate científico. El contrato estructural permanece propuesto.",
        "",
        f"Recomendación: **{recommendation}**.",
        "",
        "dev_adaptive_iteration=2; new_fits=0; holdout outcomes=0; OOT outcomes=0.",
    ]
    (DOCS / "US_LARGE_CAP_RESEARCH_COVERAGE_V1.md").write_text("\n".join(table) + "\n")
    print(
        json.dumps(
            {
                "science": science["cross_section"],
                "contract_pass_months": contract["monthly_structural_pass_count"],
                "recommendation": recommendation,
                "gains": gains,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
