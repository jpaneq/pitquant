# ruff: noqa: E402, E501
"""Build the S&P 500 anchor-graph reports from the database (ADR-0032/0033). Persists the monthly segments and the proven ticker aliases
(append-only, idempotent); writes docs/SP500_ANCHOR_GRAPH.md, docs/SP500_LOCAL_GAPS.md/.json and docs/US_IDENTITY_BRIDGE.md.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/build_sp500_anchor_graph.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict, deque
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import func, select

from pitquant.config.settings import get_settings
from pitquant.db.models import (
    Sec13FListEntry,
    SecuritySuccession,
    SP500AnchorMember,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.walkforward import WalkForwardConfig, plan_folds
from pitquant.universe.identity_bridge import bridge_name_only
from pitquant.universe.sp500_anchor_graph import (
    CATEGORIES,
    Delta,
    classify_gaps,
    graph_metrics,
    load_anchors,
    persist_graph,
    pre_holdout_limit,
    reconstruct,
)
from pitquant.universe.sp500_rename_links import apply_rename_links

DOCS = ROOT / "docs"
MIN_W, PREF_W = (date(2017, 10, 1), date(2022, 9, 30)), (date(2014, 10, 1), date(2022, 9, 30))
NEEDS = {
    "PRIMARY_EVENT_MISSING": "official effective date of the addition/removal (absent/present at anchor A, opposite at anchor B; no primary event pins it)",
    "PRIMARY_DELTA_UNEXPLAINED": "primary events contradict the anchors for this security",
    "MONTHLY_DATE_AMBIGUITY": "the release states no concrete effective date and the possible interval crosses a monthly decision_at",
    "SECURITY_IDENTITY_ONLY": "identity link (same issuer under a new name/CUSIP?) between the unresolved N-30D security and its counterpart; membership unknown until then",
    "TRANSIENT_EVENT_POSSIBLE": "discovery CSV adds and removes the same ticker inside the segment AND an archived release mentions it: confirm or discard",
}


def esc(x: object) -> str:
    return str(x if x is not None else "—").replace("|", "/").replace("\n", " ")


def main() -> int:
    cfg = get_settings()
    ho = cfg.validation.final_holdout
    with make_session_factory(make_engine(cfg.database.url))() as s:
        # identity first: every later reconstruction reads the same successions (bridge, then S&P rename statements, then reload)
        bridge = bridge_name_only(s)
        apply_rename_links(s, cfg)
        s.commit()
        anchors = load_anchors(s, settings=cfg)
        monthly = reconstruct(s, anchors[0].as_of, pre_holdout_limit(cfg), settings=cfg)
        daily = reconstruct(
            s, anchors[0].as_of, pre_holdout_limit(cfg), settings=cfg, standard="DAILY"
        )
        w60, w96 = reconstruct(s, *MIN_W, settings=cfg), reconstruct(s, *PREF_W, settings=cfg)
        dev = reconstruct(s, date(2011, 1, 1), pre_holdout_limit(cfg), settings=cfg)
        stored = persist_graph(s, monthly)
        succ = list(s.scalars(select(SecuritySuccession)))
        names = {
            m.security_id: m.issuer_name
            for m in s.scalars(select(SP500AnchorMember))
            if m.security_id
        }
        q13 = dict(
            s.execute(
                select(Sec13FListEntry.quarter, func.count()).group_by(Sec13FListEntry.quarter)
            ).all()
        )
    gaps = classify_gaps(dev)
    # Enrich the export from the actual anchor delta, never from discovery guesses.
    deltas: dict[tuple[str, str, str], deque[Delta]] = defaultdict(deque)
    for sg in dev.segments:
        for d in sg.deltas:
            deltas[(f"{sg.a.as_of}→{sg.b.as_of}", d.name, d.difference_type)].append(d)
    for g in gaps:
        matches = deltas.get((g["segment"], g["security"], g["difference_type"]))
        if matches:
            delta = matches.popleft()
            g["security_id"] = delta.security_identifier
            g["anchor_A_status"] = delta.anchor_A_status
            g["anchor_B_status"] = delta.anchor_B_status
            g["expected_event"] = (
                "ADDITION_OR_SECURITY_CONTINUITY"
                if delta.anchor_A_status == "ABSENT" and delta.anchor_B_status == "MEMBER"
                else "REMOVAL_OR_SECURITY_CONTINUITY"
                if delta.anchor_A_status == "MEMBER" and delta.anchor_B_status == "ABSENT"
                else "RECONCILE_PRIMARY_TIMELINE"
            )
        g["missing_evidence"] = NEEDS.get(g["category"], "")
    cat = Counter(g["category"] for g in gaps)
    mem_block = [g for g in gaps if g["blocks_membership"]]
    id_block = [g for g in gaps if g["blocks_identity"]]
    mm, md = graph_metrics(monthly), graph_metrics(daily)
    L = [
        "# S&P 500 — grafo de anclas SEC y estándares mensual/diario (generado)\n",
        "> Generado por `scripts/build_sp500_anchor_graph.py`. No editar a mano. Anclas = composiciones de SPY presentadas a la SEC (`SEC_FILED_INDEX_REPLICATION_ANCHOR`), no `OFFICIAL_SPDJI`.\n",
        f"Holdout {ho.start} → {ho.end} sellado; ningún ancla posterior a {pre_holdout_limit(cfg)}.\n",
        "## Estándares\n",
        "- **D02_MONTHLY_RESEARCH_READY** (puerta del Research Lab): una incertidumbre sobre el día de un evento sólo bloquea las cohortes (decision_at mensuales) que puede cambiar. Las patas del CSV de discovery sin confirmar son `DISCOVERY_UNCORROBORATED` (aviso) y NUNCA invalidan evidencia primaria; una fecha del CSV que discrepa de la oficial es `DISCOVERY_CONFLICT` y no ensancha la fecha primaria.",
        "- **D02_DAILY_CANONICAL_READY**: criterio estricto anterior (cualquier cambio sin resolver o pata de CSV sin confirmar bloquea todo el segmento).\n",
        "| métrica | mensual (Research) | diario canónico |",
        "|---|---|---|",
    ]
    for k in (
        "verified_anchors",
        "segments",
        "validated_segments",
        "forward_validated_segments",
        "backward_validated_segments",
        "monthly_cohorts",
        "monthly_cohorts_reconstructible",
        "longest_continuous_period",
        "post_limit_events_used",
    ):
        L.append(f"| {k} | {mm[k]} | {md[k]} |")
    L += [
        f"| cohortes diarias canónicas / racha | {mm['daily_canonical_cohorts']} / {mm['daily_canonical_longest_run']} | |",
        "",
    ]
    for title, w, win in (
        ("Ventana mínima (60)", w60, MIN_W),
        ("Ventana preferida (96)", w96, PREF_W),
    ):
        L += [
            f"## {title}: {win[0]} → {win[1]}\n",
            f"- monthly_cohorts {len(w.cohorts)} · membership_ready **{w.ready}** · racha continua {w.longest_run} · cohortes sin ancla {sum(1 for c in w.cohorts if c.status == 'NO_ANCHOR')} (anclas extendidas; eventos e identidad se verifican por separado)",
            "",
        ]
    L += [
        "## Cohortes (ventana mínima)\n",
        "| decision_at | estado | segmento | forward = backward | ambigüedad mensual | conflictos primarios |",
        "|---|---|---|---|---|---|",
    ]
    for c in w60.cohorts:
        L.append(
            f"| {c.date} | {c.status} | {c.segment} | {c.sets_equal} | {len(c.monthly_ambiguity)} | {len(c.primary_conflicts)} |"
        )
    L += [
        "",
        "## Reclasificación de gaps\n",
        "Antes (ficha global, ADR-0032): **95** gaps. Tras la reclasificación y las resoluciones de identidad:",
        "",
        "| categoría | n | bloquea membresía | bloquea identidad |",
        "|---|---|---|---|",
    ]
    for c in CATEGORIES:
        L.append(
            f"| {c} | {cat.get(c, 0)} | {sum(1 for g in gaps if g['category'] == c and g['blocks_membership'])} | {sum(1 for g in gaps if g['category'] == c and g['blocks_identity'])} |"
        )
    L += [
        "",
        f"Blockers de membresía reales: **{len(mem_block)}** · de identidad: **{len(id_block)}** + {len(monthly.weak_identity)} securities sin evidencia oficial de CUSIP/ISIN.\n",
    ]
    (DOCS / "SP500_ANCHOR_GRAPH.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    G = [
        "# S&P 500 — blockers PRIMARIOS locales (generado)\n",
        "> Sólo lo que puede cambiar una composición mensual. Generado tras incorporar los originales archivados; las fichas restantes requieren evidencia adicional.\n",
        "| # | segmento | categoría | security | eventos | ventana posible | cohortes bloqueadas | qué falta |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, g in enumerate(mem_block, 1):
        G.append(
            "| "
            + " | ".join(
                esc(x)
                for x in (
                    i,
                    g["segment"],
                    g["category"],
                    g["security"],
                    g["events"],
                    g["window"],
                    ", ".join(g["cohorts_blocked"]),
                    NEEDS.get(g["category"], ""),
                )
            )
            + " |"
        )
    (DOCS / "SP500_LOCAL_GAPS.md").write_text("\n".join(G) + "\n", encoding="utf-8")
    (DOCS / "sp500_local_gaps.json").write_text(
        json.dumps(gaps, indent=1, default=str) + "\n", encoding="utf-8"
    )
    priorities = Counter(g["segment"] for g in mem_block)
    ordered = sorted(mem_block, key=lambda g: (-priorities[g["segment"]], g["segment"]))
    cards = [
        "# D-02 — fichas residuales para investigación documental\n",
        "> Generado desde el archivo local. Las fechas de discovery son pistas, nunca evidencia. "
        "Una diferencia entre anclas puede ser una sucesión; no prueba una entrada/salida real.\n",
        f"Ventana DEV 2011-01 → 2022-09: **{dev.ready}/{len(dev.cohorts)}** cohortes, "
        f"**{len(mem_block)}** bloqueos mensuales; **{len(id_block)}** requieren identidad. "
        "Los bloqueos de identidad se cuentan también como mensuales sólo cuando "
        "impiden determinar la composición.\n",
        "## Prioridad por segmento\n",
        "| Segmento | Bloqueos mensuales |",
        "|---|---|",
    ]
    cards += [f"| {segment} | {count} |" for segment, count in priorities.most_common()]
    for i, g in enumerate(ordered, 1):
        cards += [
            "",
            f"## {i}. {g['security']} — {g.get('security_id', 'sin identificar')}\n",
            f"- Segmento: {g['segment']}.",
            f"- Clasificación: {g['category']}.",
            f"- Estado ancla A → B: {g.get('anchor_A_status')} → {g.get('anchor_B_status')}.",
            f"- Evento esperado por reconciliar: {g.get('expected_event')}.",
            f"- Intervalo candidato: {g['window']} (límite superior excluido para las cohortes ambiguas).",
            f"- Evidencia ausente: {g['missing_evidence']}.",
            "- Por qué bloquea: sin una fecha efectiva o continuidad documentada, "
            "las composiciones posibles difieren en los decision_at indicados.",
            f"- Decision_at afectados: {', '.join(g['blocking_decision_dates'])}.",
            f"- Evidencia de eventos disponible: {g['events']}.",
        ]
        cards += [f"- Pista QA: {hint}." for hint in g["hints"]]
    (DOCS / "SP500_RESIDUAL_GAP_CARDS.md").write_text("\n".join(cards) + "\n", encoding="utf-8")
    (DOCS / "sp500_residual_gap_cards.json").write_text(
        json.dumps(ordered, indent=2, default=str) + "\n", encoding="utf-8"
    )
    B = [
        "# US — puente de identidad con evidencia SEC oficial (generado)\n",
        "## Listas SEC 13(f) ingeridas\n",
        "| trimestre | líneas |",
        "|---|---|",
    ] + [f"| {q} | {n} |" for q, n in sorted(q13.items())]
    ok = [b for b in bridge if b.status == "RESOLVED"]
    B += [
        "",
        f"## N-30D identificadas sólo por nombre: {len(bridge)}\n",
        f"- resueltas por la lista 13F (nombre legal normalizado exacto + clase, candidato único): **{len(ok)}** ({sum(1 for b in ok if b.linked_to)} enlazadas con una security que ya tenía CUSIP)",
        f"- sin resolver: **{len(bridge) - len(ok)}** ({Counter(b.status for b in bridge if b.status != 'RESOLVED')})",
        "",
        "| security | estado | candidatos |",
        "|---|---|---|",
    ]
    B += [
        f"| {b.name} | {b.status} | {', '.join(b.candidates[:3])} |"
        for b in bridge
        if b.status != "RESOLVED"
    ]
    B += [
        "",
        "## Sucesiones y cambios de nombre verificados contra las listas 13F\n",
        "| predecesora | sucesora | tipo | efectivo | ratio | continuidad | fuente |",
        "|---|---|---|---|---|---|---|",
    ]
    for x in succ:
        B.append(
            f"| {names.get(x.security_predecessor_id, x.security_predecessor_id)} | {names.get(x.security_successor_id, x.security_successor_id)} | {x.event_type} | {x.effective_at or '—'} | {x.exchange_ratio or '—'} | {x.membership_continuity} | {x.source} |"
        )
    (DOCS / "US_IDENTITY_BRIDGE.md").write_text("\n".join(B) + "\n", encoding="utf-8")
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
    print(
        json.dumps(
            {
                "monthly": mm,
                "daily": md,
                "w60_ready": w60.ready,
                "w60_longest": w60.longest_run,
                "w96_ready": w96.ready,
                "categories": dict(cat),
                "membership_blockers": len(mem_block),
                "identity_blockers": len(id_block),
                "weak_identity": len(monthly.weak_identity),
                "bridge": dict(Counter(b.status for b in bridge)),
                "successions": len(succ),
                "stored": stored,
                "folds": len(folds),
                "total_gap_records": len(gaps),
            },
            indent=1,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
