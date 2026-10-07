#!/usr/bin/env python3
# ruff: noqa: E501
"""Offline coverage audit of the expanded, isolated data candidate; no outcome reads."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    DataSource,
    FundamentalFact,
    Price,
    RawSourceArchive,
    SecFiling,
    Security,
    SecurityProfile,
    SecuritySuccession,
    SecurityTickerAlias,
    SP500Anchor,
    TickerHistory,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.features.v0 import fundamentals as F
from pitquant.research import membership_evidence as M
from pitquant.research import us_coverage_scale as A
from pitquant.research import us_universe_scale as U
from pitquant.research.fundamentals_v1 import sector_status
from pitquant.universe.identity_bridge import succession_map
from pitquant.universe.sp500_anchor_graph import reconstruct

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-universe-scale-v1"
STORE = ArchiveStore(ROOT / "data/archive")
DOCS = ROOT / "docs"
BASE = "97743c4c05b676ca4aff633a1afb55fa549274fb"


def read(name: str) -> Any:
    return json.loads((WORK / (name + ".json")).read_bytes())


def frozen_ledger() -> dict[str, str]:
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE, "docs"], cwd=ROOT, text=True
    ).splitlines()
    out = {}
    for path in paths:
        if "first_equity" in path.lower() or "return_model_failure_audit" in path.lower():
            old = subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)
            if (ROOT / path).read_bytes() != old:
                raise ValueError("frozen scientific artifact modified: " + path)
            out[path] = hashlib.sha256(old).hexdigest()
    return out


def primary_recheck(roster: list[dict[str, Any]], cache: dict[str, Any]) -> None:
    for r in roster:
        if not r.get("profile_hash"):
            continue
        doc = json.loads(STORE.get(r["profile_hash"]))
        issuer_okay, issuer_reason = U.verify_issuer_profile(r, doc)
        r["issuer_primary_match"] = issuer_okay
        r["issuer_primary_reason"] = issuer_reason
        if r["identity_status"] != "PRIMARY_MATCH":
            continue
        okay, reason = U.verify_profile(r, doc)
        if not okay:
            r.update(identity_status="IDENTITY_UNRESOLVED", identity_reason=reason)
    U.exclude_vendor_collisions(roster)
    for r in roster:
        r["resolved_issuer_id"] = (
            r["issuer_id"] if r["identity_status"] == "PRIMARY_MATCH" else None
        )
        r["identity_scope"] = (
            "RESEARCH_ONLY_EXACT_PRIMARY_LINK" if r["resolved_issuer_id"] else "EXCLUDED_LOCALLY"
        )
        r["sector_metadata_role"] = "CURRENT_PROFILE_NOT_PIT"


def old_comparison(session: Any, months: list[str]) -> dict[str, Any]:
    # Whitelist only membership/observation keys; never use archived labels/performance.
    audit = json.loads((DOCS / "FIRST_ML_COVERAGE_AUDIT.json").read_bytes())
    keys = set()
    for fold in audit["folds"]:
        for phase in ("TRAIN", "TEST"):
            keys.update(tuple(k) for k in fold["PRIMARY_COMMON_COHORT"][phase]["observation_keys"])
    securities = {s.security_id: s for s in session.scalars(select(Security))}
    profiles = {
        p.security_id: p
        for p in session.scalars(select(SecurityProfile).order_by(SecurityProfile.ingested_at))
    }
    units: dict[str, set[str]] = defaultdict(set)
    sectors: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for sid, at in keys:
        month = at[:7]
        issuer = securities[sid].issuer_id
        if month in months and issuer:
            units[month].add(issuer)
            sector = profiles[sid].sector if sid in profiles else "UNKNOWN"
            sector = {
                "Retail Trade": "Retail",
                "Transportation, Communications & Utilities": "Transport, Comms, Utilities",
                "Wholesale Trade": "Wholesale",
            }.get(sector, sector)
            sectors[sector or "UNKNOWN"].add((issuer, month))
    # Original configured price security IDs from the frozen security coverage document.
    configured_audit = json.loads((DOCS / "FIRST_ML_FOLD_AUDIT.json").read_bytes())
    configured_sids = {
        r["security_id"]
        for fold in configured_audit["folds"]
        for phase in ("TRAIN", "TEST")
        for r in fold[phase]["rows"]
    }
    configured = len(
        {securities[sid].issuer_id for sid in configured_sids if securities[sid].issuer_id}
    )
    return {
        "source_sha256": hashlib.sha256(
            (DOCS / "FIRST_ML_COVERAGE_AUDIT.json").read_bytes()
        ).hexdigest(),
        "eligible_issuers": len(set().union(*units.values())),
        "configured_issuers": configured,
        "configured_securities": len(configured_sids),
        "monthly": {m: len(units[m]) for m in months},
        "cross_section": U.summarize_counts([len(units[m]) for m in months]),
        "issuer_months": sum(len(units[m]) for m in months),
        "sector_distribution": {
            s: {"issuers": len({i for i, _ in v}), "issuer_months": len(v)}
            for s, v in sectors.items()
        },
        "comparison_limit": "Frozen PRIMARY_COMMON_COHORT includes the previous label-safe contract; expanded candidate measures data availability only, without labels or training gates.",
    }


def markdown_reports(universe: dict[str, Any], coverage: dict[str, Any]) -> None:
    expanded, old = coverage["expanded"], coverage["current_first_ml"]
    lines = [
        "# US Large Cap Research Universe V1",
        "",
        "Expansión de datos desde `97743c4`; ningún modelo, target ni resultado futuro nuevo.",
        "",
        f"Período: 2014-09 → 2021-09 (85 meses). {universe['historical_membership_records']:,} security-periods candidatos; {universe['unique_securities']} securities históricas; {universe['unique_verified_issuers']} emisores con vínculo primario validado. Los CIK candidatos no resueltos no cuentan como emisores verificados.",
        "",
        "## Procedencia y selección",
        "",
        "La selección nace de las anclas históricas SEC/State Street y los eventos fechados del grafo D02. Se aplica ADR-0056 con el mismo clasificador: réplica de anclas más historia Clenow/Wikipedia de productor independiente. Dos copias de una fuente no añaden independencia. Yahoo es exclusivamente proveedor de mercado.",
        "",
        "Los períodos UNVERIFIED/CONFLICTED se excluyen localmente. El informe conserva sus filas, hashes, motivos y casos ambiguos. El identificador de un instrumento no se sustituye por un ticker actual. Nombre legal exacto y ticker de clase en submissions SEC, identificador oficial del instrumento, historial del emisor anterior al período y ausencia de colisión se verifican antes de enlazar el issuer. El registro SEC histórico cik-lookup-data.txt aporta emisores desaparecidos del mapa actual; sólo descubre CIK candidatos. Filings y nombre legal primario deben confirmar historia compatible con el período del instrumento. Una compañía con ticker actual vacío puede usar una pata histórica exacta, pero Yahoo no se acepta para ese ticker terminal sin concordancia de nombre con la identidad primaria. Los enlaces de investigación no certifican completitud global de identidad.",
        "",
        "Las sucesiones de securities diferentes no habilitan continuidad de precios: la ventana de 253 sesiones se corta en el inicio legal de la sucesora. Los aliases fechados y las transiciones parciales se conservan como tales. GE/GOOGL/RTX/XOM mantienen los bloqueos de la auditoría anterior.",
        "",
        "## Mercado y fundamentales",
        "",
        "D05 conserva OHLC RAW, divisa, sesiones, acciones corporativas y reconstrucción determinista. Para deshacer el ajuste retrospectivo de Yahoo se archiva la respuesta completa hasta 2026-10-07; los precios posteriores a 2021-09-30 se descartan antes de normalizar. Sólo los splits posteriores pueden intervenir para recuperar las unidades RAW originales. No se construyen targets ni outcomes. El candidato comprimido contiene únicamente las barras históricas normalizadas.",
        "",
        "SEC se procesa con el ingestor existente: accession, header ACCEPTANCE-DATETIME, XBRL primario, available_at, originales y hashes. Companyfacts sigue siendo descubrimiento/validación. Un 404 real cacheado permite usar la recuperación nativa de filings no citados desde su propio XBRL y header; un cache miss, 403, 429 o fallo primario no se convierte en esa excepción. Se mantiene sec-tags-4 sin mappings nuevos. La auditoría calcula exactamente los tres campos fundamentales existentes de First ML; no certifica disponibilidad de todo el feature set ni de labels.",
        "",
        "Los sectores SIC no soportados continúan excluidos de fundamentales. SIC y sector actuales son CURRENT_PROFILE_NOT_PIT, metadatos descriptivos, sin features sectoriales nuevas. Todos los cortes de hechos y barras son estrictamente anteriores a la apertura mensual.",
        "",
        "## Supervivencia",
        "",
        f"Referencia descriptiva fechada {universe['current_reference']['date']}, {universe['current_reference']['members']} tickers; no se declara composición oficial actual. Resultados sobre securities históricas: `{json.dumps(universe['survivorship'], sort_keys=True)}`.",
        "",
        universe["lifecycle_limit"],
        "",
        "La inclusión en el roster no depende de sobrevivir. Sin embargo, la cobertura usable sigue condicionada por resolver identidad histórica y obtener Yahoo: este sesgo residual se cuantifica y no se oculta como un universo sin survivorship bias.",
        "",
        "## Reproducción y presupuesto",
        "",
        "Usar un checkout aislado desde el HEAD de referencia y el entorno de desarrollo. Crear la copia con `python scripts/scale_us_research_universe.py initialize`. El script rechaza una copia existente y nunca escribe en data/pitquant.db. Configurar PITQUANT_SEC_USER_AGENT sólo en el entorno con un contacto válido; no se almacena en código, artefactos ni logs.",
        "",
        "Ejecutar, por orden: `discover`, `historical-discovery`, `identity`, `prices`, `fundamentals` y `python scripts/audit_us_research_scale.py`. fundamentals usa tres descargadores RAW y un único escritor SQL. SEC comparte un límite global de 6,67 solicitudes/s; Yahoo es secuencial, máximo 1/s. Timeout 20s, hasta tres intentos con backoff; 220 documentos nuevos por issuer y cinco fallos de proveedor antes de cerrar su ficha. Se conserva además una reserva operativa de 5 GiB: si se alcanza, las descargas restantes se clasifican como bloqueadas por capacidad, sin borrar originales. Los límites son de ingeniería, no gates científicos.",
        "",
        "La copia candidate.db, el archivo content-addressed y data/research/us-universe-scale-v1/cache/requests.jsonl permiten repetir sin red. Las respuestas fallidas también quedan cacheadas; una nueva colección requiere otra revisión explícita, sin borrar originales. Las versiones inmutables se guardan por SHA-256. Reproducir hashes requiere las mismas fuentes archivadas y la copia registrada; una revisión remota distinta es otro candidato.",
        "",
        "Todos los casos quedan clasificados y el impacto residual se mide. No se exige evidencia perfecta ni se sustituyen silenciosamente empresas desaparecidas por supervivientes.",
        "",
        "## Artefactos",
        "",
        "- [Universo y fichas](US_LARGE_CAP_RESEARCH_UNIVERSE_V1.json)",
        "- [Cobertura mensual](US_LARGE_CAP_RESEARCH_COVERAGE_V1.md)",
        "- [Candidato sin targets](US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz)",
        "- [ADR-0063](adr/0063-scale-cross-sectional-us-universe.md)",
        "",
        f"Dataset candidate SHA-256: `{universe['candidate']['sha256']}`. No reemplaza V0/V1; training_ready=false. Los {len(universe['frozen_artifact_hashes'])} artefactos científicos protegidos coinciden byte a byte con el HEAD inicial.",
        "",
        "dev_adaptive_iteration=2; holdout outcomes=0; OOT outcomes=0; new_fits=0.",
    ]
    (DOCS / "US_LARGE_CAP_RESEARCH_UNIVERSE_V1.md").write_text("\n".join(lines) + "\n")
    lines = [
        "# US Large Cap Research Coverage V1",
        "",
        "Auditoría de disponibilidad, identidad y missingness. No es un nuevo coverage contract científico ni un resultado de modelo.",
        "",
        "## Comparación",
        "",
        "| Medida | Current First ML | Universo ampliado |",
        "|---|---:|---:|",
        f"| Configured issuers verificados | {old['configured_issuers']} | {coverage['configured_verified_issuers']} |",
        f"| Emisores elegibles en algún mes | {old['eligible_issuers']} | {coverage['eligible_issuers']} |",
        f"| Mediana mensual | {old['cross_section']['median']} | {expanded['cross_section']['COMBINED']['median']} |",
        f"| Mínimo mensual | {old['cross_section']['minimum']} | {expanded['cross_section']['COMBINED']['minimum']} |",
        f"| Issuer-months | {old['issuer_months']} | {expanded['combined_issuer_months']} |",
        f"| Sectores representados | {len(old['sector_distribution'])} | {len(expanded['sector_distribution'])} |",
        "",
        old["comparison_limit"],
        "",
        f"Incremento de mediana: {coverage['median_percentage_increase']:.2f}%. Es una comparación de tamaño, con contratos distintos: no demuestra que esas observaciones sean entrenables.",
        "",
        "## Distribuciones de emisores mensuales",
        "",
        "| Etapa | Mínimo | P10 | Mediana | P90 | Máximo |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for stage, stats in expanded["cross_section"].items():
        lines.append(
            "| "
            + stage
            + " | "
            + " | ".join(
                str(round(stats[k], 2)) for k in ("minimum", "p10", "median", "p90", "maximum")
            )
            + " |"
        )
    lines += [
        "",
        "MEMBERSHIP cuenta emisores identificados con período aceptado. membership_verified en la tabla siguiente cuenta securities corroboradas aunque falte resolver su emisor. PRICE/FUNDAMENTALS incluyen identidad y membresía; COMBINED es su intersección. Clases de un emisor se deduplican; los pendientes de identidad nunca son emisores ficticios.",
        "",
        f"Milestone de ingeniería ≥200 en cada mes: {expanded['engineering_milestone_200']}. Scientific coverage gate: NOT_DEFINED.",
        "",
        "## Los 85 meses",
        "",
        "| Mes | Candidatos | Membresía verificada | Precio | Fundamentales | Combinado issuers | Securities | Excl. membership | Identidad | Precio | Fund. | Unsupported |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in expanded["months"]:
        keys = (
            "historical_membership_count",
            "membership_verified",
            "price_eligible",
            "fundamental_eligible",
            "combined_eligible",
            "unique_securities",
            "excluded_membership",
            "excluded_identity",
            "excluded_price",
            "excluded_fundamentals",
            "unsupported_sector",
        )
        lines.append("| " + m["month"] + " | " + " | ".join(str(m[k]) for k in keys) + " |")
    lines += [
        "",
        "Los motivos de exclusión se solapan; no deben sumarse para estimar pérdidas marginales. Los detalles de cada security-period están en el candidato comprimido.",
        "",
        "## Sectores",
        "",
        "| Sector SIC descriptivo | Issuers | Issuer-months | Porcentaje |",
        "|---|---:|---:|---:|",
    ]
    for sector, stats in expanded["sector_distribution"].items():
        lines.append(
            f"| {sector} | {stats['issuers']} | {stats['issuer_months']} | {stats['percentage']:.2f}% |"
        )
    lines += [
        "",
        "## Bloqueos ordenados",
        "",
        "Para identidades sin resolver se informa security-periods, no issuer-months inventados. Los impactos por causa/concepto se solapan y no equivalen a observaciones recuperables automáticamente.",
    ]
    for category, ranking in coverage["blockers"].items():
        lines += [
            "",
            "### " + category,
            "",
            "| Motivo | Issuer-months conocidos afectados | Security-periods sin issuer |",
            "|---|---:|---:|",
        ]
        for r in ranking[:15]:
            lines.append(
                f"| {r['reason']} | {r['lost_known_issuer_months']} | {r['unresolved_security_periods']} |"
            )
    lines += [
        "",
        "## Deuda de conceptos XBRL",
        "",
        coverage["mapping_debt_limit"],
        "",
        "No se declara XBRL_TAG_UNMAPPED por mera ausencia de un ratio. Se agrupan conceptos no usados como candidatos de revisión semántica; falta de historia, datos no comparables, conflictos y problemas de ingesta conservan sus propios motivos. No hay mappings nuevos.",
        "",
        "| Concepto candidato | Issuers con campo incompleto | Issuer-months afectados |",
        "|---|---:|---:|",
    ]
    for r in coverage["mapping_debt"][:30]:
        lines.append(f"| {r['concept']} | {r['issuer_count']} | {r['issuer_month_impact']} |")
    lines += [
        "",
        "## Decisión",
        "",
        "La muestra ampliada aumenta materialmente la información transversal disponible. Antes de un experimento estructural único conviene resolver los mayores vacíos de identidad/membresía histórica y fijar explícitamente el próximo coverage contract. El alcance actual no permite afirmar tamaño efectivo independiente, estabilidad de señal o aptitud estadística: no se han inspeccionado outcomes.",
        "",
        "Recomendación única: **CONTINUE_DATA_EXPANSION**. Priorizar períodos históricos excluidos y disponibilidad de empresas desaparecidas, según el ranking; no seguir cambiando algoritmos sobre el dataset anterior ni iniciar otro entrenamiento en esta tarea.",
        "",
        "## Hashes del candidato",
        "",
    ]
    lines += [f"- {k}: `{v}`" for k, v in coverage["hashes"].items()]
    lines += ["", "dev_adaptive_iteration=2; holdout outcomes=0; OOT outcomes=0; new_fits=0."]
    (DOCS / "US_LARGE_CAP_RESEARCH_COVERAGE_V1.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    preserved = frozen_ledger()
    implementation = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in (
            "src/pitquant/research/us_universe_scale.py",
            "src/pitquant/research/us_coverage_scale.py",
            "src/pitquant/research/us_sec_collection.py",
            "scripts/scale_us_research_universe.py",
            "scripts/audit_us_research_scale.py",
        )
    }
    roster, prices, ingestion = read("roster"), read("yahoo_collection"), read("sec_ingestion")
    cache = {}
    for line in (WORK / "cache/requests.jsonl").read_text().splitlines():
        record = json.loads(line)
        cache[record["url"]] = record
    primary_recheck(roster, cache)
    by_sid = {r["security_id"]: r for r in roster}
    manifest = json.loads((DOCS / "D02_MEMBERSHIP_SOURCE_MANIFEST.json").read_bytes())
    factory = make_session_factory(make_engine("sqlite:///" + str(WORK / "candidate.db")))
    with factory() as session:
        rep = reconstruct(session, U.START, U.END, settings=get_settings(), persist=False)
        manifest["anchor_provenance"] = {}
        for anchor in rep.anchors:
            meta = session.get_one(SP500Anchor, anchor.anchor_id)
            source = session.get_one(RawSourceArchive, meta.archive_id)
            STORE.get(source.sha256)
            manifest["anchor_provenance"][anchor.anchor_id] = {
                "as_of": str(anchor.as_of),
                "accession": meta.accession,
                "source_url": source.source_identifier,
                "publisher": "STATE_STREET_SEC_ANCHOR_REPLAY",
                "retrieved_at": source.retrieved_at.isoformat(),
                "source_available_at": meta.source_available_at.isoformat(),
                "sha256": source.sha256,
                "resolver_version": meta.parser_version,
            }
        cal = get_calendar("XNYS")
        months = [str(c.date)[:7] for c in rep.cohorts]
        if len(months) != U.EXPECTED_MONTHS:
            raise ValueError("85 decision months required")
        successors = list(session.scalars(select(SecuritySuccession)))
        lineage = succession_map(session)
        configured = {
            r["security_id"]: {
                "ticker": r["ticker_candidate"] or "",
                "issuer_id": r["resolved_issuer_id"],
                "sector": r.get("sector", "UNKNOWN"),
            }
            for r in roster
        }
        bridge = {
            r["security_id"]: frozenset((r["security_id"],))
            for r in roster
            if any(i["cusip"] or i["isin"] for i in r["anchor_instruments"])
            or r.get("official_identifiers")
        }
        projection = M.build_projection(
            rep, bridge, configured, lineage, manifest, STORE, start=U.START, end=U.END
        )
        membership = [
            m
            for m in projection["rows"]
            if m["decision_session"] in by_sid[m["security_id"]]["potential_sessions"]
        ]
        print("membership rows", len(membership), flush=True)
        aliases = defaultdict(list)
        for a in session.scalars(select(SecurityTickerAlias)):
            if a.security_id in by_sid:
                aliases[a.security_id].append(
                    {
                        "ticker": a.ticker,
                        "from": str(a.valid_from) if a.valid_from else None,
                        "to": str(a.valid_to) if a.valid_to else None,
                        "bounds": a.bounds,
                        "source_hash": a.source_hash,
                    }
                )
        for r in roster:
            r["dated_ticker_aliases"] = aliases[r["security_id"]]
            r["share_class_evidence"] = sorted(
                {i["title"] for i in r["anchor_instruments"] if i["title"]}
            )
            incoming = [
                edge.effective_at
                for edge in successors
                if edge.security_successor_id == r["security_id"]
                and edge.event_type in ("SECURITY_REPLACEMENT_SUCCESSOR", "SHARE_CLASS_CHANGE")
                and edge.effective_at
            ]
            outgoing = [
                edge.effective_at
                for edge in successors
                if edge.security_predecessor_id == r["security_id"]
                and edge.event_type in ("SECURITY_REPLACEMENT_SUCCESSOR", "SHARE_CLASS_CHANGE")
                and edge.effective_at
            ]
            r["legal_price_start"] = (
                max(incoming).date().isoformat() if incoming else r["listing_start"]
            )
            r["legal_price_end_exclusive"] = min(outgoing).date().isoformat() if outgoing else None
            r["corporate_lineage"] = [
                {
                    "predecessor": s.security_predecessor_id,
                    "successor": s.security_successor_id,
                    "event_type": s.event_type,
                    "effective_at": s.effective_at.isoformat() if s.effective_at else None,
                    "source_hash": s.source_hash,
                    "primary_note": s.note,
                }
                for s in successors
                if r["security_id"] in (s.security_predecessor_id, s.security_successor_id)
            ]
        qa_by_symbol = {}
        vendor_meta_by_symbol = {}
        for symbol, source in prices.items():
            if source.get("status") == "READY" and source.get("source_hash"):
                raw = json.loads(STORE.get(source["source_hash"]))
                meta = raw["chart"]["result"][0]["meta"]
                vendor_meta_by_symbol[symbol] = {
                    k: meta[k] for k in ("longName", "shortName") if meta.get(k)
                }
        for symbol, summary in prices.items():
            if summary.get("qa_hash"):
                path = WORK / "revisions" / summary["qa_hash"] / ("yahoo-" + symbol + ".json")
                body = path.read_bytes()
                if hashlib.sha256(body).hexdigest() != summary["qa_hash"]:
                    raise ValueError("market audit hash mismatch")
                qa_by_symbol[symbol] = json.loads(body)
        # Benchmark availability, not benchmark future performance. Original canonical Yahoo SPY only.
        spy = list(
            session.scalars(
                select(Security).join(TickerHistory).where(TickerHistory.ticker == "SPY")
            )
        )
        if len(spy) != 1:
            raise ValueError("unique canonical benchmark required")
        benchmark = {}
        for c in rep.cohorts:
            at = cal.session_open(c.date)
            bars = list(
                session.scalars(
                    select(Price)
                    .join(DataSource)
                    .where(
                        DataSource.name == "YAHOO_CHART:eod",
                        DataSource.is_synthetic.is_(False),
                        Price.security_id == spy[0].security_id,
                        Price.bar_close_at < at,
                        Price.session_date <= c.date,
                    )
                    .order_by(Price.session_date.desc())
                    .limit(253)
                )
            )
            benchmark[str(c.date)] = A.price_window(
                {
                    "status": "READY",
                    "reasons": [],
                    "bars": [
                        {
                            "session": str(p.session_date),
                            "close_at": p.bar_close_at.isoformat(),
                            "close": p.close,
                        }
                        for p in reversed(bars)
                    ],
                },
                at,
            )[0]
        fund_cache = {}
        debt_candidates: dict[str, dict[str, datetime]] = defaultdict(dict)
        for i, r in enumerate(roster):
            issuer = r["resolved_issuer_id"]
            if not issuer or issuer in fund_cache or sector_status(r.get("sic")):
                continue
            fact_rows = list(
                session.scalars(
                    select(FundamentalFact).where(
                        FundamentalFact.issuer_id == issuer,
                        FundamentalFact.available_at < datetime(2021, 10, 1, tzinfo=UTC),
                        FundamentalFact.value.is_not(None),
                    )
                )
            )
            facts = [
                F.Fact(
                    f.concept,
                    f.period_start,
                    f.period_end,
                    float(f.value),
                    f.unit,
                    f.available_at,
                    f.accession_number,
                    f.form,
                    f.revision_id,
                    f.fact_id,
                )
                for f in fact_rows
                if f.concept in A.CORE_TAGS
            ]
            fund_cache[issuer] = {
                str(c.date): A.core_fundamentals(facts, cal.session_open(c.date))
                for c in rep.cohorts
            }
            first_fact = min((f.available_at for f in fact_rows), default=None)
            for c in rep.cohorts:
                if first_fact is None or first_fact >= cal.session_open(c.date):
                    for field in fund_cache[issuer][str(c.date)].values():
                        field["missing_reason"] = (
                            "NO_PRIMARY_FACTS_ARCHIVED"
                            if first_fact is None
                            else "INSUFFICIENT_HISTORY"
                        )
            # Candidates are descriptive unused concepts, not automatically accepted equivalences.
            for f in fact_rows:
                if f.concept not in A.CORE_TAGS and any(
                    k in f.concept.lower() for k in ("debt", "revenue", "income", "sales")
                ):
                    current = debt_candidates[f.concept].get(issuer)
                    if current is None or f.available_at < current:
                        debt_candidates[f.concept][issuer] = f.available_at
            if i % 25 == 0:
                print("fundamental coverage", i + 1, flush=True)
        rows = []
        for m in membership:
            r = by_sid[m["security_id"]]
            issuer, day = r["resolved_issuer_id"], m["decision_session"]
            at = cal.session_open(date.fromisoformat(day))
            identity_ok = (
                bool(issuer)
                and not (
                    r.get("issuer_history_start_observed")
                    and day < r["issuer_history_start_observed"]
                )
                and not (r["legal_price_start"] and day < r["legal_price_start"])
                and not (r["legal_price_end_exclusive"] and day >= r["legal_price_end_exclusive"])
            )
            member = m["membership_research_eligible"]
            symbol = r["ticker_candidate"]
            qa = qa_by_symbol.get(symbol)
            supported_starts = [
                d for d in (r["legal_price_start"], r.get("issuer_history_start_observed")) if d
            ]
            if qa and supported_starts:
                qa = {
                    **qa,
                    "bars": [b for b in qa["bars"] if b["session"] >= max(supported_starts)],
                }
            price_ok, price_reason = (
                A.price_window(qa, at) if identity_ok else (False, "IDENTITY_UNRESOLVED")
            )
            vendor_binding = None
            if price_ok:
                profile = json.loads(STORE.get(r["profile_hash"]))
                binding_ok, vendor_binding = U.terminal_vendor_binding(
                    r, profile, vendor_meta_by_symbol.get(symbol, {})
                )
                if not binding_ok:
                    price_ok, price_reason = False, vendor_binding
            if not benchmark[day]:
                price_ok, price_reason = False, "BENCHMARK_DATA_UNAVAILABLE"
            unsupported = sector_status(r.get("sic"))
            fields = fund_cache.get(issuer, {}).get(day, {})
            fund_ok = (
                bool(fields)
                and all(v["value"] is not None for v in fields.values())
                and not unsupported
            )
            blockers, reasons = [], {}
            for category, okay, reason in (
                ("MEMBERSHIP", member, m["exclusion_reason"]),
                ("IDENTITY", identity_ok, r.get("identity_reason") or r["candidate_reason"]),
                ("PRICE", price_ok, price_reason),
                (
                    "FUNDAMENTALS",
                    fund_ok,
                    unsupported
                    or (
                        ";".join(
                            sorted(
                                {
                                    v["missing_reason"] or "UNAVAILABLE"
                                    for v in fields.values()
                                    if v["value"] is None
                                }
                            )
                        )
                        if fields
                        else "NO_VERIFIED_PRIMARY_FACTS"
                    ),
                ),
            ):
                if not okay:
                    blockers.append(category)
                    reasons[category] = reason
            if unsupported:
                blockers.append("UNSUPPORTED_SECTOR")
                reasons["UNSUPPORTED_SECTOR"] = r.get("sic", "UNKNOWN")[:2]
            rows.append(
                {
                    "security_id": r["security_id"],
                    "issuer_id": issuer,
                    "month": day[:7],
                    "decision_at": at.isoformat(),
                    "sector": r.get("sector", "UNKNOWN"),
                    "membership_tier": m["evidence_tier"],
                    "membership_state": m["membership_state"],
                    "membership_provenance": m["provenance"],
                    "membership_exclusion_provenance": m["exclusion_provenance"],
                    "identity_status": r["identity_status"],
                    "price_symbol": symbol,
                    "price_qa_hash": prices.get(symbol, {}).get("qa_hash"),
                    "vendor_binding_audit": vendor_binding,
                    "core_fundamentals": fields,
                    "eligibility": {
                        "MEMBERSHIP": member and identity_ok,
                        "PRICE": member and identity_ok and price_ok,
                        "FUNDAMENTALS": member and identity_ok and fund_ok,
                        "COMBINED": member and identity_ok and price_ok and fund_ok,
                    },
                    "blockers": blockers,
                    "reasons": reasons,
                }
            )
        A.validate_candidate(rows)
        expanded = U.aggregate(rows, months)
        baseline = old_comparison(session, months)
        filing_index = []
        for f in session.scalars(
            select(SecFiling).where(
                SecFiling.cik.in_(set(ingestion)),
                SecFiling.filed_date >= U.PRICE_START,
                SecFiling.filed_date <= U.END,
            )
        ):
            header = session.get_one(RawSourceArchive, f.header_archive_id)
            instance = (
                session.get(RawSourceArchive, f.xbrl_archive_id) if f.xbrl_archive_id else None
            )
            filing_index.append(
                {
                    "accession": f.accession_number,
                    "cik": f.cik,
                    "issuer_id": f.issuer_id,
                    "filed_date": str(f.filed_date),
                    "accepted_at": f.accepted_at.isoformat(),
                    "available_at": f.available_at.isoformat(),
                    "header": {
                        "url": header.source_identifier,
                        "sha256": header.sha256,
                        "retrieved_at": header.retrieved_at.isoformat(),
                    },
                    "xbrl": {
                        "url": instance.source_identifier,
                        "sha256": instance.sha256,
                        "retrieved_at": instance.retrieved_at.isoformat(),
                    }
                    if instance
                    else None,
                }
            )
        filing_index.sort(key=lambda f: f["accession"])
    current_source = manifest["sources"]["clenow_updated"]
    states = M.historical_states(STORE.get(current_source["sha256"]), until=date(2026, 10, 7))
    current_at, current = states[-1]
    survival = Counter()
    for r in roster:
        symbols = (
            {r["ticker_candidate"]}
            | {a["ticker"] for a in r["dated_ticker_aliases"]}
            | {leg["ticker"] for leg in r["official_ticker_legs"]}
        )
        replaced = r["legal_price_end_exclusive"] and r["legal_price_end_exclusive"] <= str(
            current_at
        )
        verified_current = (
            r["identity_status"] == "PRIMARY_MATCH" and symbols & current and not replaced
        )
        last_leg = (
            max(r["official_ticker_legs"], key=lambda leg: (leg["effective_date"], leg["event_id"]))
            if r["official_ticker_legs"]
            else None
        )
        removed_leg = (
            last_leg
            and last_leg["kind"] == "REMOVE"
            and last_leg["effective_date"] > max(r["potential_sessions"])
        )
        if verified_current:
            status = "CURRENT_REFERENCE_MEMBER"
        elif replaced:
            status = "REMOVED_OR_REPLACED_HISTORICAL_SECURITY"
        elif not symbols.intersection(current) and (
            r["identity_status"] == "PRIMARY_MATCH" or removed_leg
        ):
            status = "REMOVED_FROM_CURRENT_REFERENCE"
        else:
            status = "CURRENT_STATUS_UNRESOLVED"
        r["survivorship_status"] = status
        survival[status] += 1
        replacements = [
            edge
            for edge in r["corporate_lineage"]
            if edge["predecessor"] == r["security_id"]
            and edge["event_type"] in ("SECURITY_REPLACEMENT_SUCCESSOR", "SHARE_CLASS_CHANGE")
        ]
        if replacements:
            survival["PRIMARY_REPLACEMENT_PREDECESSOR"] += 1
            if any(
                "merger" in (edge.get("primary_note") or "").lower()
                or "combine" in (edge.get("primary_note") or "").lower()
                for edge in replacements
            ):
                survival["PRIMARY_MERGER_PREDECESSOR"] += 1
        if r["delisted"]:
            survival["EXPLICIT_DELISTED"] += 1
        if r["acquirer_security_id"] or r["successor_security_id"]:
            survival["EXPLICIT_ACQUIRED_OR_SUCCESSOR"] += 1
        if "bankrupt" in (r["delisting_reason"] or "").lower():
            survival["EXPLICIT_BANKRUPT"] += 1
    for key in (
        "CURRENT_REFERENCE_MEMBER",
        "REMOVED_FROM_CURRENT_REFERENCE",
        "REMOVED_OR_REPLACED_HISTORICAL_SECURITY",
        "CURRENT_STATUS_UNRESOLVED",
        "EXPLICIT_DELISTED",
        "EXPLICIT_ACQUIRED_OR_SUCCESSOR",
        "EXPLICIT_BANKRUPT",
        "PRIMARY_REPLACEMENT_PREDECESSOR",
        "PRIMARY_MERGER_PREDECESSOR",
    ):
        survival.setdefault(key, 0)
    mapping = A.mapping_debt(rows, debt_candidates)
    hashes = {
        "membership": U.digest(membership),
        "identity": U.digest(roster),
        "price_universe": U.digest(prices),
        "fundamental_universe": U.digest({"ingestion": ingestion, "coverage": fund_cache}),
        "coverage": U.digest(rows),
    }
    candidate = {
        "dataset": U.DATASET,
        "version": U.VERSION,
        "period": [str(U.START), str(U.END)],
        "hashes": hashes,
        "rows": rows,
        "historical_market_series": qa_by_symbol,
        "has_targets": False,
        "training_ready": False,
    }
    data = gzip.compress(U.encoded(candidate), mtime=0)
    output = DOCS / (U.DATASET + ".json.gz")
    output.write_bytes(data)
    universe = {
        "universe": "US_LARGE_CAP_RESEARCH_UNIVERSE_V1",
        "version": U.VERSION,
        "initial_head": BASE,
        "period": candidate["period"],
        "historical_membership_records": len(rows),
        "unique_securities": len(roster),
        "unique_primary_issuers": len(
            {
                r.get("primary_issuer_id")
                for r in roster
                if r.get("issuer_primary_match") and r.get("primary_issuer_id")
            }
        ),
        "unique_verified_issuers": len(
            {r["resolved_issuer_id"] for r in roster if r["resolved_issuer_id"]}
        ),
        "cik_candidates_not_all_verified": len(
            {r["cik_candidate"] for r in roster if r["cik_candidate"]}
        ),
        "evidence_tiers": dict(Counter(r["membership_tier"] for r in rows)),
        "identity_states": dict(Counter(r["identity_status"] for r in roster)),
        "global_identity_completeness": all(r["resolved_issuer_id"] for r in roster),
        "research_identity_validity": all(
            r["issuer_id"] for r in rows if r["eligibility"]["COMBINED"]
        ),
        "survivorship": dict(survival),
        "lifecycle_limit": "Explicit lifecycle counts are lower bounds. Removal, a replacement, or a Yahoo 404 does not by itself prove delisting/acquisition/bankruptcy. Unknown cases remain unknown.",
        "current_reference": {
            "date": str(current_at),
            "sha256": current_source["sha256"],
            "members": len(current),
            "authority": "DESCRIPTIVE_HISTORICAL_REFERENCE_NOT_OFFICIAL_CURRENT_MEMBERSHIP",
        },
        "hashes": hashes,
        "evidence_manifest": manifest,
        "source_index": sorted(cache.values(), key=lambda r: r["url"]),
        "price_audits": prices,
        "sec_ingestion": ingestion,
        "primary_filing_index": filing_index,
        "roster": roster,
        "frozen_artifact_hashes": preserved,
        "implementation_hashes": implementation,
        "candidate": {
            "path": output.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "rows": len(rows),
            "no_targets": True,
        },
    }
    gain = (
        100
        * (
            expanded["cross_section"]["COMBINED"]["median"] / baseline["cross_section"]["median"]
            - 1
        )
        if baseline["cross_section"]["median"]
        else None
    )
    coverage = {
        "version": U.VERSION,
        "dataset": U.DATASET,
        "hashes": hashes,
        "expanded": expanded,
        "current_first_ml": baseline,
        "median_percentage_increase": gain,
        "eligible_issuers": len({r["issuer_id"] for r in rows if r["eligibility"]["COMBINED"]}),
        "configured_verified_issuers": universe["unique_verified_issuers"],
        "blockers": {
            k: A.blocker_ranking(rows, k)
            for k in ("MEMBERSHIP", "IDENTITY", "PRICE", "FUNDAMENTALS", "UNSUPPORTED_SECTOR")
        },
        "mapping_debt": mapping,
        "mapping_debt_limit": "Unused concept presence does not prove semantic equivalence or that mapping it repairs missing coverage; impacts overlap.",
        "fundamental_family": "Existing First ML core, sec-tags-4; not full-feature training readiness",
        "price_family": "Existing D05 RAW QA + contiguous 253 historical closes + benchmark availability; no forward outcomes",
        "recommendation": "CONTINUE_DATA_EXPANSION",
        "scientific_coverage_gate": "NOT_DEFINED",
        "dev_adaptive_iteration": 2,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "new_fits": 0,
    }
    for name, doc in (
        ("US_LARGE_CAP_RESEARCH_UNIVERSE_V1", universe),
        ("US_LARGE_CAP_RESEARCH_COVERAGE_V1", coverage),
    ):
        U.write_revision(WORK, name, doc)
        (DOCS / (name + ".json")).write_text(
            json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    markdown_reports(universe, coverage)
    if frozen_ledger() != preserved:
        raise ValueError("frozen artifacts changed during expansion")
    print(
        json.dumps(
            {
                "tiers": universe["evidence_tiers"],
                "coverage": expanded["cross_section"],
                "old": baseline["cross_section"],
                "hashes": hashes,
                "survival": dict(survival),
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
