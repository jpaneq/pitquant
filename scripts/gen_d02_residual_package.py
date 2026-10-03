# ruff: noqa: E402, E501
"""D-02 residual documentary package (ADR-0035), generated from the database and the local archive; never edited by hand.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/gen_d02_residual_package.py

Writes docs/D02_RESIDUAL_PACKAGE.md and docs/d02_residual_cards.json: before/after readiness, per-segment summary, identity summary,
one card per residual membership/identity blocker (stable ``gap_id``) and the copyable prompt for external research.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict, deque
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.db.models import RawSourceArchive, SecuritySuccession, SP500Anchor
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.sources.spy_sec_anchors import norm_name
from pitquant.universe.sp500_anchor_graph import Delta, classify_gaps, load_anchors, reconstruct
from pitquant.universe.sp500_rename_links import iter_releases

MIN_W = (date(2017, 10, 1), date(2022, 9, 30))
BEFORE = {
    "ready": 27,
    "longest": 15,
    "membership_blockers": 21,
    "identity_blockers": 3,
    "weak_identity": 2,
}  # measured at HEAD f84f38d
PROMPT = (
    "Busca fuentes oficiales para estas fichas. Devuelve por caso URL, accession si aplica, fecha de publicación/acceptance, cita breve que demuestra "
    "el evento, fecha efectiva y evidencia de continuidad/clase. Separa lo probado de lo incierto. No uses CSV comunitarios como prueba."
)


def key_words(name: str) -> list[str]:
    return [w for w in norm_name(name).split() if len(w) >= 4 and w not in {"class", "series"}]


def main() -> int:
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as s:
        w60 = reconstruct(s, *MIN_W, settings=cfg)
        gaps = classify_gaps(w60)
        anchors = {a.as_of: a for a in load_anchors(s, settings=cfg)}
        rows = {a.anchor_id: a for a in s.scalars(select(SP500Anchor))}
        arch = {
            r.archive_id: r
            for r in s.scalars(
                select(RawSourceArchive).where(RawSourceArchive.provider == "SEC_SPY_ANCHOR")
            )
        }
        releases = iter_releases(s, cfg)
        n_succ = len(list(s.scalars(select(SecuritySuccession))))
        deltas: dict[tuple[str, str, str], deque[Delta]] = defaultdict(deque)
        for sg in w60.segments:
            for d in sg.deltas:
                deltas[(f"{sg.a.as_of}→{sg.b.as_of}", d.name, d.difference_type)].append(d)
        cards: list[dict[str, object]] = []
        for g in gaps:
            if not (g["blocks_membership"] or g["blocks_identity"]):
                continue
            m = deltas.get((g["segment"], g["security"], g["difference_type"]))
            dl = m.popleft() if m else None
            a_d, b_d = (date.fromisoformat(x) for x in g["segment"].split("→"))

            def anchor_info(d: date) -> dict[str, object]:
                node = anchors[d]
                row = rows[node.anchor_id]
                ar = arch.get(row.archive_id)
                return {
                    "as_of": str(d),
                    "form": row.form,
                    "accession": row.accession,
                    "source_sha256": row.source_sha256,
                    "source_url": ar.source_identifier if ar else None,
                }

            words = key_words(g["security"])
            mentioned = [
                {"announced_on": str(r.announced_on), "url": r.url}
                for r in releases
                if a_d <= r.announced_on <= b_d
                and words
                and all(re.search(rf"\b{re.escape(w)}", r.text, re.I) for w in words[:2])
            ]
            sid = dl.security_identifier if dl else None
            gap_id = (
                "D02-"
                + hashlib.sha256(
                    f"{sid}|{g['segment']}|{g['difference_type']}|{g['security']}".encode()
                ).hexdigest()[:12]
            )
            archived = bool(mentioned)
            cards.append(
                {
                    "gap_id": gap_id,
                    "security_id": sid,
                    "company_and_class": g["security"],
                    "segment": g["segment"],
                    "anchor_A": anchor_info(a_d) | {"status": dl.anchor_A_status if dl else None},
                    "anchor_B": anchor_info(b_d) | {"status": dl.anchor_B_status if dl else None},
                    "event_to_reconcile": "ADDITION_OR_SECURITY_CONTINUITY"
                    if dl and dl.anchor_A_status == "ABSENT"
                    else "REMOVAL_OR_SECURITY_CONTINUITY",
                    "candidate_interval": g["window"],
                    "category": g["category"],
                    "blocks_membership": g["blocks_membership"],
                    "blocks_identity": g["blocks_identity"],
                    "reason": "membership: the possible compositions differ at the listed decision_at"
                    if g["blocks_membership"]
                    else "identity only: the security cannot be joined to its counterpart",
                    "affected_decision_at": g["blocking_decision_dates"],
                    "primary_events_found": g["events"],
                    "local_documentation": "ARCHIVED_BUT_PARSER_OR_RULES_INSUFFICIENT"
                    if archived
                    else "DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE",
                    "archived_releases_mentioning_it": mentioned[:5],
                    "discovery_hints_NON_PROBATIVE": g["hints"],
                    "missing_evidence": "an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues",
                    "closing_condition": "a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it",
                }
            )
        cards.sort(key=lambda c: (str(c["segment"]), str(c["company_and_class"])))
        by_seg: dict[str, list[dict[str, object]]] = defaultdict(list)
        for c in cards:
            by_seg[str(c["segment"])].append(c)
        id_cards = [c for c in cards if c["blocks_identity"]]
        mem = [c for c in cards if c["blocks_membership"]]
        path = ROOT / "docs"
        (path / "d02_residual_cards.json").write_text(
            json.dumps({"prompt": PROMPT, "cards": cards}, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        L = [
            "# D-02 — paquete documental residual (generado)\n",
            "> Generado por `scripts/gen_d02_residual_package.py` desde la base y el archivo local. No editar a mano. Las pistas de discovery NO son evidencia.\n",
            "## Antes / después (ventana 2017-10 → 2022-09)\n",
            "| métrica | inicio de la iteración (HEAD f84f38d) | ahora |",
            "|---|---|---|",
            f"| cohortes mensuales listas | {BEFORE['ready']}/60 | {w60.ready}/60 |",
            f"| racha continua máxima | {BEFORE['longest']} | {w60.longest_run} |",
            f"| bloqueos de membresía | {BEFORE['membership_blockers']} | {len(mem)} |",
            f"| bloqueos sólo de identidad | {BEFORE['identity_blockers']} | {len(id_cards)} |",
            f"| securities con identidad débil | {BEFORE['weak_identity']} | {len(w60.weak_identity)} |",
            f"\nSucesiones persistidas: {n_succ}. `D02_MONTHLY_MEMBERSHIP_READY` = {w60.ready == 60}; `US_SECURITY_IDENTITY_READY` = {not w60.weak_identity and not id_cards}.\n",
            "## Resumen por segmento\n",
            "| segmento | bloqueos membresía | bloqueos identidad | documento ausente | archivado pero insuficiente |",
            "|---|---|---|---|---|",
        ]
        for seg, cs in sorted(by_seg.items()):
            L.append(
                f"| {seg} | {sum(bool(c['blocks_membership']) for c in cs)} | {sum(bool(c['blocks_identity']) for c in cs)} | {sum(c['local_documentation'].startswith('DOCUMENT') for c in cs)} | {sum(c['local_documentation'].startswith('ARCHIVED') for c in cs)} |"
            )  # type: ignore[attr-defined]
        L += [
            "",
            "## Identidad (aparte de la membresía)\n",
            f"- Identidad débil: {len(w60.weak_identity)} securities; bloqueos sólo de identidad: {len(id_cards)}.",
            f"- Categorías de fichas: {dict(Counter(str(c['category']) for c in cards))}.\n",
        ]
        L += [
            "## Prompt para investigación externa (copiar tal cual)\n",
            f"```\n{PROMPT}\n```\n",
            "## Fichas\n",
        ]
        for c in cards:
            A, B = c["anchor_A"], c["anchor_B"]
            L += [
                f"### {c['gap_id']} — {c['company_and_class']}",
                f"- security_id: `{c['security_id']}`; segmento {c['segment']}; categoría {c['category']}.",
                f"- Ancla A ({A['as_of']}, {A['form']}, accession {A['accession']}, sha256 `{str(A['source_sha256'])[:16]}…`): {A['status']}. [{A['source_url']}]",  # type: ignore[index]
                f"- Ancla B ({B['as_of']}, {B['form']}, accession {B['accession']}, sha256 `{str(B['source_sha256'])[:16]}…`): {B['status']}. [{B['source_url']}]",  # type: ignore[index]
                f"- Evento por reconciliar: {c['event_to_reconcile']}; intervalo candidato {c['candidate_interval']}.",
                f"- Motivo: {c['reason']}. decision_at afectados: {', '.join(c['affected_decision_at'])}.",  # type: ignore[arg-type]
                f"- Documentación local: **{c['local_documentation']}**; eventos primarios hallados: {c['primary_events_found']}.",
                f"- Evidencia que falta: {c['missing_evidence']}.",
                f"- Condición de cierre: {c['closing_condition']}.",
            ]
            L += [f"- Pista (NO probatoria): {h}" for h in c["discovery_hints_NON_PROBATIVE"]]  # type: ignore[attr-defined]
            L.append("")
        (path / "D02_RESIDUAL_PACKAGE.md").write_text("\n".join(L) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ready": w60.ready,
                    "longest": w60.longest_run,
                    "cards": len(cards),
                    "membership": len(mem),
                    "identity": len(id_cards),
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
