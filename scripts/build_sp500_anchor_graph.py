# ruff: noqa: E402, E501
"""Build the S&P 500 anchor graph reports from the database (ADR-0032). Read-mostly: persists the strict segments and the
proven ticker aliases (append-only, idempotent); writes docs/SP500_ANCHOR_GRAPH.md and docs/SP500_LOCAL_GAPS.md/.json.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/build_sp500_anchor_graph.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import func, select

from pitquant.config.settings import get_settings
from pitquant.db.models import SP500Anchor, SP500AnchorCrossCheck, SP500AnchorMember
from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.walkforward import WalkForwardConfig, plan_folds
from pitquant.universe.sp500_anchor_graph import (
    graph_metrics,
    load_anchors,
    persist_graph,
    pre_holdout_limit,
    reconstruct,
)

DOCS = ROOT / "docs"
MIN_W, PREF_W = (date(2017, 10, 1), date(2022, 9, 30)), (date(2014, 10, 1), date(2022, 9, 30))
MISSING = {
    "MISSING_ADDITION_EVENT": "effective date (official source) of the ADDITION: absent at anchor A, member at anchor B, no event pins it",
    "MISSING_REMOVAL_EVENT": "effective date (official source) of the REMOVAL: member at anchor A, absent at anchor B, no event pins it",
    "SECURITY_IDENTITY_GAP": "identity: is this the same issuer under a new CUSIP/name (rename, re-domiciliation, holding-company reorganisation)? or resolve the ticker of a discovery leg to a company",
    "DATE_CONFLICT": "which effective date is right (official release vs discovery CSV); the cohorts between the two dates are blocked",
    "DATE_MISSING_IN_RELEASE": "the release announcing the change states no concrete effective date: a follow-up release or the actual date",
    "TRANSIENT_HOLDING": "the discovery CSV adds AND removes the same ticker inside the segment (a transient member the anchors cannot see): confirm or discard",
    "UNEXPLAINED": "events and anchors contradict each other for this security",
    "PARSER_MISS": "an archived release mentions it but the clause was not parsed",
    "TICKER_ALIAS_ONLY": "none: ticker/class artifact of the discovery CSV (QA)",
}


def esc(x: object) -> str:
    return str(x if x is not None else "—").replace("|", "/").replace("\n", " ")


def main() -> int:
    cfg = get_settings()
    ho = cfg.validation.final_holdout
    with make_session_factory(make_engine(cfg.database.url))() as s:
        anchors = load_anchors(s, settings=cfg)
        raw = {a.anchor_id: a for a in s.scalars(select(SP500Anchor))}
        strict = reconstruct(s, anchors[0].as_of, pre_holdout_limit(cfg), settings=cfg)
        lenient = reconstruct(
            s, anchors[0].as_of, pre_holdout_limit(cfg), settings=cfg, strict=False
        )
        w60 = reconstruct(s, *MIN_W, settings=cfg)
        w96 = reconstruct(s, *PREF_W, settings=cfg)
        stored = persist_graph(s, strict)
        s.commit()
        counts = {}
        for a in raw.values():
            if a.form != "NPORT-P" and any(
                x.as_of_date == a.as_of_date and x.form == "NPORT-P" for x in raw.values()
            ):
                continue
            n_cusip = s.scalar(
                select(func.count())
                .select_from(SP500AnchorMember)
                .where(
                    SP500AnchorMember.anchor_id == a.anchor_id,
                    SP500AnchorMember.classification == "INDEX_EQUITY_CANDIDATE",
                    SP500AnchorMember.cusip.is_not(None),
                )
            )
            n_isin = s.scalar(
                select(func.count())
                .select_from(SP500AnchorMember)
                .where(
                    SP500AnchorMember.anchor_id == a.anchor_id,
                    SP500AnchorMember.classification == "INDEX_EQUITY_CANDIDATE",
                    SP500AnchorMember.cusip.is_(None),
                    SP500AnchorMember.isin.is_not(None),
                )
            )
            counts[a.anchor_id] = (n_cusip, n_isin)
        cross = list(s.scalars(select(SP500AnchorCrossCheck)))
    L = [
        "# S&P 500 — grafo de anclas históricas SEC (generado)\n",
        "> Generado por `scripts/build_sp500_anchor_graph.py` desde la base. No editar a mano. Las anclas son composiciones de SPY presentadas a la SEC (`SEC_FILED_INDEX_REPLICATION_ANCHOR`), **no** listas oficiales de S&P DJI; `as_of_date` y `source_available_at` son relojes distintos y los anclajes nunca alimentan features.\n",
        f"Holdout {ho.start} → {ho.end} sellado: ningún ancla posterior a {pre_holdout_limit(cfg)} se carga.\n",
        "## Anclas verificadas\n",
        "| as_of | formulario | accession | tier | publicado (SEC) | miembros | con CUSIP | solo ISIN | sin resolver | excluidos (stubs/no-equity) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a in sorted(raw.values(), key=lambda x: (x.as_of_date, x.form)):
        cu, isn = counts.get(a.anchor_id, (None, None))
        L.append(
            f"| {a.as_of_date} | {a.form} | {a.accession} | {a.evidence_tier} | {str(a.source_available_at)[:16]} | {a.member_count} | {cu if cu is not None else '—'} | {isn if isn is not None else '—'} | {a.unresolved_count} | {a.excluded_count} |"
        )
    L += [
        "",
        "## Cross-check NPORT-P vs N-30D (misma fecha)\n",
        "| fecha | NPORT equities | schedule equities | matched | nport_only | schedule_only | identity_unresolved |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in sorted(cross, key=lambda x: x.metrics["anchor_date"]):
        m = c.metrics
        L.append(
            f"| {m['anchor_date']} | {m['nport_equities']} | {m['schedule_equities']} | {m['matched']} | {m['nport_only']} | {m['schedule_only']} | {m['identity_unresolved']} |"
        )
    L += [
        "",
        "La discrepancia de 2022-09-30 (`schedule_only` = EQT y PG&E) NO es un error: el N-30D es la cartera tras las operaciones de cierre del día y SPY ya había comprado las altas que entraban en el índice el 2022-10-03 (S&P: EQT por Duke Realty, PG&E por Citrix), mientras que el NPORT-P refleja el índice a esa fecha. Para un ancla Tier B se retiran de su conjunto las altas CONFIRMADAS con efecto en la sesión siguiente.\n",
        "## Métricas principales\n",
        "| métrica | estricto | indulgente (QA) |",
        "|---|---|---|",
    ]
    ms, ml = graph_metrics(strict), graph_metrics(lenient)
    for k in (
        "verified_anchors",
        "segments",
        "validated_segments",
        "forward_validated_segments",
        "backward_validated_segments",
        "local_unresolved_segments",
        "monthly_cohorts",
        "monthly_cohorts_reconstructible",
        "longest_continuous_period",
        "post_limit_events_used",
    ):
        L.append(f"| {k} | {ms[k]} | {ml[k]} |")
    L.append(f"| security_identity_resolution | {ms['security_identity_resolution']} | |")
    L += [
        "",
        "El modo ESTRICTO es el de la puerta: una pata sin confirmar del CSV de discovery sin ticker resoluble bloquea su segmento si excede los cambios visibles en las anclas, o si el mismo ticker se añade y se retira dentro del segmento. El porcentaje de eventos del CSV confirmados es sólo QA.\n",
    ]
    for title, w, win in (
        ("Ventana mínima (60)", w60, MIN_W),
        ("Ventana preferida (96)", w96, PREF_W),
    ):
        m = graph_metrics(w)
        blocked = [c for c in w.cohorts if c.status != "MEMBERSHIP_READY"]
        L += [
            f"## {title}: {win[0]} → {win[1]}\n",
            f"- monthly_cohorts {m['monthly_cohorts']} · membership_ready **{w.ready}** · bloqueadas {len(blocked)} · racha continua {w.longest_run} · identity (miembros de ancla sin resolver) {m['security_identity_resolution']['unresolved_lines']}",
            f"- cohortes sin ancla a uno de los lados: {sum(1 for c in w.cohorts if c.status == 'NO_ANCHOR')} (no se han buscado anclas anteriores a 2017-09: la ventana mínima aún no está completa)",
            "",
        ]
    L += [
        "## Segmentos\n",
        "| desde | hasta | estado | forward | backward | patas confirmadas | gaps por tipo |",
        "|---|---|---|---|---|---|---|",
    ]
    gaps: list[dict[str, object]] = []
    for sg in strict.segments:
        kinds = Counter(
            d.difference_type for d in sg.deltas if d.difference_type != "TICKER_ALIAS_ONLY"
        )
        L.append(
            f"| {sg.a.as_of} | {sg.b.as_of} | {sg.status} | {sg.forward_ok} | {sg.backward_ok} | {sg.n_confirmed_legs} | {dict(kinds)} |"
        )
        for d in sg.deltas:
            if d.difference_type == "TICKER_ALIAS_ONLY":
                continue
            gaps.append({"segment": f"{sg.a.as_of}→{sg.b.as_of}", "difference_type": d.difference_type, "security": d.name, "security_identifier": d.security_identifier, "anchor_A": d.anchor_A_status, "events": d.events_status, "anchor_B": d.anchor_B_status,
                         "expected": d.expected, "observed": d.observed, "window": d.window, "missing_evidence": MISSING[d.difference_type], "hints": d.hints})  # fmt: skip
    cnt = Counter(str(g["difference_type"]) for g in gaps)
    L += [
        "",
        f"Aliases de ticker / transiciones de identidad persistidos: {stored['aliases']} (límites `PARTIAL`: no se infiere ninguna fecha). Segmentos persistidos: {stored['segments']}.",
        "",
        "## Gaps locales (resumen)\n",
        "| tipo | n |",
        "|---|---|",
    ]
    L += [f"| {k} | {v} |" for k, v in cnt.most_common()]
    L += [
        "",
        "Detalle completo para investigación externa: `docs/SP500_LOCAL_GAPS.md` y `docs/sp500_local_gaps.json`.\n",
    ]
    # walk-forward feasibility (train_min stays 60)
    run = [c.date for c in w96.cohorts if c.status == "MEMBERSHIP_READY"]
    folds = (
        plan_folds(
            run,
            WalkForwardConfig(
                train_min_months=60, purge_months=1, embargo_months=1, label_horizon_months=6
            ),
            (ho.start, ho.end),
        )
        if run
        else []
    )
    L += [
        "## Walk-forward (train_min = 60 meses, sin cambios)\n",
        f"Con las cohortes reconstruibles actuales: {len(run)} cohortes, {len(folds)} folds OOS. `BASELINE_TRAINING_READY` exige ≥96 cohortes consecutivas y ≥2 folds.",
    ]
    (DOCS / "SP500_ANCHOR_GRAPH.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    G = [
        "# S&P 500 — gaps LOCALES por segmento (generado)\n",
        "> Un gap = una security cuyo cambio de membresía entre dos anclas SEC consecutivas no queda fijado por evidencia oficial. Sólo bloquea las cohortes de SU segmento y dentro de su ventana. No se ha buscado nada fuera del archivo existente.\n",
        "| # | segmento | tipo | security | anclaje A | eventos | anclaje B | ventana de efectividad posible | qué falta | pistas |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, g in enumerate(gaps, 1):
        G.append(
            "| "
            + " | ".join(
                esc(x)
                for x in (
                    i,
                    g["segment"],
                    g["difference_type"],
                    g["security"],
                    g["anchor_A"],
                    g["events"],
                    g["anchor_B"],
                    g["window"],
                    g["missing_evidence"],
                    "; ".join(g["hints"])[:260],
                )
            )
            + " |"
        )  # type: ignore[arg-type,attr-defined]
    (DOCS / "SP500_LOCAL_GAPS.md").write_text("\n".join(G) + "\n", encoding="utf-8")
    (DOCS / "sp500_local_gaps.json").write_text(
        json.dumps(gaps, indent=1, default=str) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "strict": ms,
                "lenient": ml,
                "w60_ready": w60.ready,
                "w96_ready": w96.ready,
                "gaps": dict(cnt),
                "stored": stored,
                "folds": len(folds),
            },
            indent=1,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
