# ruff: noqa: E501
"""Generate, ONLY from stored evidence and identity-resolution segments (no manual text per
case):

* docs/ISSUER_SECURITY_CHANGES.md — issuer/security changes detected in the IBEX build;
* docs/IDENTITY_BLOCKERS.md — which security blocks which backtest date and what evidence
  is missing (the work queue of the next iteration).

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/gen_identity_reports.py

Nothing is relaxed: classification rules are mechanical and anything the evidence does not
settle is UNRESOLVED. Identity QA only: no returns, scores or metrics are computed.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.calendars.market_calendar import get_calendar  # noqa: E402
from pitquant.db.models import (  # noqa: E402
    IndexMembership,
    Issuer,
    MembershipIdentitySegment,
    OfficialCodeIsinEvidence,
    OfficialIsinTransition,
    RawSourceArchive,
    SecurityIdentitySnapshot,
)
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.security_master.identity import BACKTESTABLE, normalize_name  # noqa: E402
from pitquant.security_master.identity_store import (  # noqa: E402
    latest_run,
    load_snapshot_index,
    load_transitions,
)
from pitquant.security_master.service import SecurityMaster  # noqa: E402
from pitquant.universe.index_membership import IndexUniverse  # noqa: E402

# Required cases (brief): label -> (ticker as in the build, year of the change)
REQUIRED = {
    "POP 2013": ("POP", 2013),
    "ITX 2014": ("ITX", 2014),
    "BKIA 2013": ("BKIA", 2013),
    "BKIA 2017": ("BKIA", 2017),
    "AENA 2025": ("AENA", 2025),
    "Ferrovial": ("FER", None),
    "MTS 2017": ("MTS", 2017),
    "GRF 2016": ("GRF", 2016),
    "REE 2016": ("REE", 2016),
    "PHM 2020": ("PHM", 2020),
}
OBS_ID = "observation:bme-ibex35-constituents:2026-10-01"


@dataclass
class Seg:
    start: date
    end: date | None
    status: str
    isin: str | None
    evidence: list[str]
    candidates: list[str]

    @property
    def ok(self) -> bool:
        return self.status in {s.value for s in BACKTESTABLE}


@dataclass
class Case:
    ticker: str
    kind: str
    status: str
    when: date
    interval: str
    sec_before: str
    sec_after: str
    isin_before: str | None
    isin_after: str | None
    issuer_before: str | None
    issuer_after: str | None
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""


def _hash(h: str | None) -> str:
    return f"`{h[:12]}…`" if h else "—"


def _snap(ses: Session, isin: str, side: str, around: date) -> SecurityIdentitySnapshot | None:
    q = select(SecurityIdentitySnapshot).where(SecurityIdentitySnapshot.isin == isin)
    rows = sorted(ses.scalars(q), key=lambda r: r.reference_date)
    if side == "last_before":
        c = [r for r in rows if r.reference_date <= around]
        return c[-1] if c else None
    c = [r for r in rows if r.reference_date >= around]
    return c[0] if c else None


def _line(ses: Session, r: SecurityIdentitySnapshot | None) -> str:
    if r is None:
        return "sin snapshot"
    arch = ses.get(RawSourceArchive, r.archive_id)
    return (
        f"{r.isin} @ {r.reference_date} [{r.scope}] «{r.instrument_name}» / «{r.issuer_legal_name}»"
        f"{f' emitido {r.issue_date}' if r.issue_date else ''}; miembro {_hash(r.source_hash)} "
        f"zip {_hash(arch.sha256 if arch else None)} ({arch.source_identifier.rsplit('/', 1)[-1] if arch else '?'})"
    )


def main() -> int:
    s = get_settings()
    canon = s.canonical_period.start
    store = ArchiveStore(ROOT / s.archive.root)
    with make_session_factory(make_engine(s.database.url))() as ses:
        u = IndexUniverse(ses)
        build = u.active_build("IBEX35")
        run = latest_run(ses, build.build_id)
        assert run is not None, "run scripts/build_ibex_real.py first"
        sm = SecurityMaster(ses)
        obs_row = ses.scalars(
            select(RawSourceArchive).where(RawSourceArchive.source_identifier == OBS_ID)
        ).one()
        obs = json.loads(store.get(obs_row.sha256))
        horizon = date.fromisoformat(obs["observed_at"][:10])
        current_isin = {t: i for t, i in obs["constituents"]}

        transitions = {(t.old_isin, t.new_isin): t for t in load_transitions(ses)}
        tr_docs = {
            (r.old_isin, r.new_isin): list(r.documents or [])
            for r in ses.scalars(select(OfficialIsinTransition))
        }
        ivs = {
            i.id: i
            for i in ses.scalars(
                select(IndexMembership).where(IndexMembership.build_id == build.build_id)
            )
        }
        segs: dict[int, list[Seg]] = defaultdict(list)
        seg_rows = ses.scalars(
            select(MembershipIdentitySegment)
            .where(MembershipIdentitySegment.run_id == run.run_id)
            .order_by(
                MembershipIdentitySegment.membership_id, MembershipIdentitySegment.segment_from
            )
        ).all()
        sec_of: dict[tuple[int, date], str | None] = {}
        iss_of: dict[tuple[int, date], str | None] = {}
        for r in seg_rows:
            cands = [e.removeprefix("candidate:") for e in r.evidence if e.startswith("candidate:")]
            segs[r.membership_id].append(
                Seg(
                    r.segment_from,
                    r.segment_to,
                    r.status,
                    r.isin,
                    [e for e in r.evidence if not e.startswith("candidate:")],
                    cands,
                )
            )
            sec_of[(r.membership_id, r.segment_from)] = r.security_id
            iss_of[(r.membership_id, r.segment_from)] = r.issuer_id

        def code_at(mid: int, d: date) -> str:
            iv = ivs[mid]
            t = sm.ticker_as_of(iv.security_id, min(max(d, iv.effective_from), horizon))
            return t or iv.ticker_at_inclusion or "?"

        def name_of(iss: str | None) -> str:
            return ses.get_one(Issuer, iss).name if iss else "—"

        cases: list[Case] = []
        # ── within one interval: ISIN changes and unproven tails ────────────────────────
        for mid, L in segs.items():
            iv = ivs[mid]
            last_ok: Seg | None = None
            gap: list[Seg] = []
            for sg in L:
                if sg.ok and sg.isin:
                    if last_ok is not None and last_ok.isin != sg.isin:
                        t = code_at(mid, sg.start)
                        sec_a = sec_of.get((mid, last_ok.start)) or iv.security_id
                        sec_b = sec_of.get((mid, sg.start)) or iv.security_id
                        tr = transitions.get((last_ok.isin, sg.isin))
                        explained = any(
                            "ISIN change" in e
                            for e in last_ok.evidence
                            + sg.evidence
                            + [x for g in gap for x in g.evidence]
                        )
                        if gap or not (tr or explained or sg.start == (last_ok.end or sg.start)):
                            kind, st = "ISIN_CHANGE_WINDOW_UNEXPLAINED", "UNRESOLVED"
                        elif sec_a != sec_b:
                            kind, st = "ISIN_CHANGE_NEW_SECURITY", sg.status
                        elif tr is not None:
                            kind, st = "ISIN_CHANGE_OFFICIAL_TRANSITION", sg.status
                        else:
                            kind, st = "ISIN_CHANGE_ANCV_ISSUE_DATE", sg.status
                        a = _snap(ses, last_ok.isin, "last_before", sg.start)
                        b = _snap(ses, sg.isin, "first_after", sg.start)
                        c = Case(
                            t,
                            kind,
                            st,
                            tr.effective_date if tr else sg.start,
                            f"[{iv.effective_from}, {iv.effective_to or 'abierto'})",
                            sec_a,
                            sec_b,
                            last_ok.isin,
                            sg.isin,
                            iss_of.get((mid, last_ok.start)),
                            iss_of.get((mid, sg.start)),
                        )
                        c.evidence = [
                            "último snapshot con el ISIN antiguo: " + _line(ses, a),
                            "primer snapshot con el ISIN nuevo: " + _line(ses, b),
                            *[f"segmento: {e}" for e in (last_ok.evidence[-1:] + sg.evidence[:1])],
                            *[
                                f"ventana [{g.start}, {g.end}): {g.status} candidatos {g.candidates} — {'; '.join(g.evidence)}"
                                for g in gap
                            ],
                        ]
                        if tr is not None:
                            c.evidence += [
                                f"documento oficial ({d.get('role')}): {d.get('url')} "
                                f"[{d.get('via')}{' ' + str(d.get('wayback_ts')) if d.get('wayback_ts') else ''}] "
                                f"{_hash(d.get('sha256'))} extracción {d.get('extraction')}; "
                                f"cita: «{(d.get('excerpts') or [''])[0][:160]}»"
                                for d in tr_docs.get((tr.old_isin, tr.new_isin), [])
                            ]
                        if kind == "ISIN_CHANGE_NEW_SECURITY":
                            c.explanation = (
                                "Fusión por absorción / redomiciliación: cambia la entidad jurídica emisora del valor, "
                                "así que es una security NUEVA enlazada a su predecesora (ADR-0020, "
                                "`successor_security_id`); el ISIN antiguo cotiza hasta la víspera de la fecha efectiva "
                                "y el nuevo desde ella. Continuidad ECONÓMICA del emisor (mismo issuer_id), no "
                                "identidad jurídica."
                            )
                        elif kind == "ISIN_CHANGE_OFFICIAL_TRANSITION":
                            c.explanation = (
                                f"Cambio de ISIN de la MISMA entidad ({tr.kind if tr else ''}, política ADR-0020: "
                                "cambio de nominal = misma security). La fecha es la de INICIO DE CONTRATACIÓN "
                                "declarada en los documentos oficiales archivados, no la fecha de emisión ANCV; "
                                "el security_id se mantiene."
                            )
                        elif kind == "ISIN_CHANGE_ANCV_ISSUE_DATE":
                            c.explanation = (
                                "La ANCV fecha la emisión del ISIN nuevo entre la última evidencia del antiguo y la "
                                "primera del nuevo, el antiguo desaparece y la razón social no cambia (cambio de "
                                "nominal = misma security). La fecha es la de EMISIÓN ANCV (administrativa), no una "
                                "fecha oficial de inicio de contratación: frontera con incertidumbre de días."
                            )
                        else:
                            c.explanation = (
                                "Entre la última evidencia del ISIN antiguo y la primera del nuevo no hay fecha oficial "
                                "del cambio: no se puede decidir si es continuidad o sustitución de security. "
                                "Queda UNRESOLVED; la ventana sigue PROVISIONAL en el motor."
                            )
                        cases.append(c)
                    last_ok, gap = sg, []
                elif last_ok is not None:
                    gap.append(sg)
            if last_ok is not None and gap and iv.effective_to is None:
                t = code_at(mid, horizon)
                cur = current_isin.get(t)
                a = _snap(ses, last_ok.isin or "", "last_before", horizon)
                later = [g for g in gap if g.start >= (last_ok.end or last_ok.start)]
                if cur and cur != last_ok.isin:
                    kind, st = "ISIN_CHANGE_UNRESOLVED", "UNRESOLVED"
                    expl = (
                        f"El ISIN probado ({last_ok.isin}) deja de aparecer en ANCV y la composición vigente BME "
                        f"(transcripción, no documento exacto) da {cur} para el código {t}. Sin documento oficial "
                        "fechado del ISIN nuevo no se concluye si es redomiciliación (mismo emisor, nueva security), "
                        "cambio de nominal u otra cosa: UNRESOLVED. Nota: desde 12/2018 ANCV sólo lista ISIN ES, así "
                        "que la ausencia de un ISIN extranjero no prueba nada."
                    )
                else:
                    kind, st = "TAIL_UNPROVEN", "UNRESOLVED"
                    expl = "El tramo final no se confirma con fuente independiente."
                c = Case(
                    t,
                    kind,
                    st,
                    later[0].start if later else horizon,
                    f"[{iv.effective_from}, abierto)",
                    iv.security_id,
                    iv.security_id,
                    last_ok.isin,
                    cur,
                    iss_of.get((mid, last_ok.start)),
                    None,
                )
                c.evidence = [
                    "último snapshot con el ISIN probado: " + _line(ses, a),
                    f"composición vigente BME ({horizon}, transcripción {_hash(obs_row.sha256)}): {t} → {cur}",
                    *[
                        f"segmento [{g.start}, {g.end or 'abierto'}): {g.status} — {'; '.join(g.evidence)}"
                        for g in gap
                    ],
                ]
                c.explanation = expl
                cases.append(c)
        # ── across intervals of the same legal entity (re-entry under another ISIN) ───────
        ix = load_snapshot_index(ses)
        by_name: dict[str, list[tuple[int, Seg, Seg]]] = defaultdict(list)
        for mid, L in segs.items():
            ok = [x for x in L if x.ok and x.isin]
            if not ok:
                continue
            ln = ix.latest_line(ok[0].isin or "")
            if ln is not None:
                by_name[normalize_name(ln.issuer_legal_name)].append((mid, ok[0], ok[-1]))
        for name, items in by_name.items():
            items.sort(key=lambda x: ivs[x[0]].effective_from)
            for (m1, _f1, l1), (m2, f2, _l2) in pairwise(items):
                if l1.isin == f2.isin or ivs[m1].security_id == ivs[m2].security_id:
                    continue
                i1, i2 = ivs[m1], ivs[m2]
                t = code_at(m2, f2.start)
                iss1, iss2 = iss_of.get((m1, l1.start)), iss_of.get((m2, f2.start))
                same_issuer = iss1 is not None and iss1 == iss2
                a = _snap(ses, l1.isin or "", "last_before", date.max)
                b = _snap(ses, f2.isin or "", "first_after", date.min)
                c = Case(
                    t,
                    "REENTRY_UNDER_DIFFERENT_ISIN",
                    "UNRESOLVED",
                    i1.effective_to or i2.effective_from,
                    f"[{i1.effective_from}, {i1.effective_to or 'abierto'}) → [{i2.effective_from}, {i2.effective_to or 'abierto'})",
                    i1.security_id,
                    i2.security_id,
                    l1.isin,
                    f2.isin,
                    iss1,
                    iss2,
                )
                c.evidence = [
                    "último snapshot del ISIN del primer intervalo: " + _line(ses, a),
                    "primer snapshot del ISIN del segundo intervalo: " + _line(ses, b),
                    f"razón social normalizada idéntica en ANCV: «{name}» (igualdad de nombre, NO un identificador oficial)",
                ]
                c.explanation = (
                    (
                        "Mismo issuer_id en ambos intervalos. "
                        if same_issuer
                        else "issuer_id distintos: el sistema no tiene un vínculo oficial (CIF) entre ambos ISIN, sólo la igualdad de "
                        "razón social. "
                    )
                    + "El ISIN y el security_id cambian entre intervalos. No se infiere por nombre que sea el mismo emisor ni que "
                    "sea la misma security: UNRESOLVED hasta tener el CIF (consulta ANCV por NIF) o un hecho relevante de "
                    "canje/agrupación."
                )
                cases.append(c)

        # ── report 1 ──────────────────────────────────────────────────────────────────
        cases.sort(key=lambda c: (c.when, c.ticker))
        L1 = [
            "# Cambios emisor / security detectados en el IBEX (generado)",
            "",
            "Generado con `scripts/gen_identity_reports.py` **sólo** desde la base local: segmentos "
            f"del run `{run.run_id}` (`{run.engine_version}`), snapshots ANCV y la observación BME "
            f"`{obs_row.sha256}`. Las reglas de clasificación son mecánicas; lo que la evidencia no "
            "decide queda `UNRESOLVED`. Identidad: no se calcula ningún retorno ni métrica.",
            "",
            "## Casos solicitados",
            "",
            "| Caso | Detectado | Tipo | Estado |",
            "|---|---|---|---|",
        ]
        for label, (tk, yr) in REQUIRED.items():
            hit = [
                c
                for c in cases
                if c.ticker == tk
                and (
                    yr is None
                    or c.when.year == yr
                    or (c.kind == "REENTRY_UNDER_DIFFERENT_ISIN" and yr in (c.when.year,))
                )
            ]
            L1.append(
                f"| {label} | {'sí' if hit else '**NO DETECTADO**'} | "
                f"{', '.join(sorted({h.kind for h in hit})) or '—'} | "
                f"{', '.join(sorted({h.status for h in hit})) or '—'} |"
            )
        L1 += ["", "## Detalle", ""]
        for c in cases:
            L1 += [
                f"### {c.ticker} — {c.when} — {c.kind}",
                "",
                f"- **Estado:** {c.status}",
                f"- **Intervalo de membership:** {c.interval}",
                f"- **security_id:** antes `{c.sec_before}` → después `{c.sec_after}`"
                + (" (misma)" if c.sec_before == c.sec_after else " (**distinta**)"),
                f"- **ISIN:** antes {c.isin_before or '—'} → después {c.isin_after or '—'}",
                f"- **issuer_id:** antes `{c.issuer_before or '—'}` ({name_of(c.issuer_before)}) → después "
                f"`{c.issuer_after or '—'}` ({name_of(c.issuer_after)})",
                "- **Evidencia y hashes:**",
                *[f"  - {e}" for e in c.evidence],
                f"- **Por qué:** {c.explanation}",
                "",
            ]
        L1 += ["## Transiciones oficiales de ISIN registradas", ""]
        L1 += [
            "| Efecto | ISIN antiguo → nuevo | Tipo | Continuidad | Uso en el universo IBEX | Documentos |",
            "|---|---|---|---|---|---|",
        ]
        for t in sorted(transitions.values(), key=lambda t: t.effective_date):
            used = [c for c in cases if c.isin_before == t.old_isin and c.isin_after == t.new_isin]
            where = (
                "; ".join(f"{c.ticker} {c.interval}" for c in used)
                if used
                else "fuera de los intervalos IBEX (el valor entra o sale después/antes de la transición)"
            )
            docs = "; ".join(
                f"{d.get('role')} {_hash(d.get('sha256'))}"
                for d in tr_docs.get((t.old_isin, t.new_isin), [])
            )
            L1.append(
                f"| {t.effective_date} | {t.old_isin} → {t.new_isin} | {t.kind} | {t.continuity} "
                f"| {where} | {docs} |"
            )
        L1.append("")
        (ROOT / "docs" / "ISSUER_SECURITY_CHANGES.md").write_text("\n".join(L1) + "\n")

        # ── report 2: blockers ────────────────────────────────────────────────────────
        cal = get_calendar("XMAD")
        dates = cal.first_sessions_of_months(canon, horizon)
        members_by_date = {d: u.universe("IBEX35", d, build.build_id) for d in dates}
        rows: dict[tuple[str, str, str], list[date]] = defaultdict(list)
        for d in dates:
            for m in members_by_date[d]:
                mid = m.membership_id or -1
                sg = next(
                    (x for x in segs.get(mid, []) if x.start <= d and (x.end is None or d < x.end)),
                    None,
                )
                if sg is not None and sg.ok:
                    continue
                code = sm.ticker_as_of(m.security_id, d) or "?"
                if sg is None:
                    reason = "UNRESOLVED: sin segmento"
                else:
                    reason = f"{sg.status}: " + (sg.evidence[-1] if sg.evidence else "")
                    if sg.candidates:
                        reason += f" (candidatos {', '.join(sg.candidates)})"
                rows[(code, sg.status if sg else "UNRESOLVED", reason)].append(d)

        def missing(status: str, reason: str) -> str:
            if "unexplained window" in reason:
                return (
                    "fecha oficial del cambio de ISIN (hecho relevante/aviso de canje o cambio de "
                    "nominal) o fecha de emisión ANCV del ISIN nuevo"
                )
            if "ambiguous" in reason:
                return (
                    "dos líneas ordinarias comparten etiqueta ANCV: falta un documento oficial "
                    "exacto (aviso/folleto) que fije cuál es la clase cotizada en el IBEX"
                )
            if "leading edge" in reason:
                return "snapshot ANCV previo o fecha oficial de admisión/alta del ISIN"
            if "trailing edge" in reason or "after the last ANCV" in reason:
                return (
                    "corroboración oficial exacta del ISIN tras el último snapshot ANCV "
                    "(composición BME archivada, no transcrita)"
                )
            if status == "UNRESOLVED" and "none" in reason:
                return (
                    "ninguna línea ordinaria ANCV con la etiqueta del código BME dentro del "
                    "intervalo: falta un documento oficial fechado código BME ↔ ISIN (boletín "
                    "BME, ficha archivada o ISIN extranjero del emisor)"
                )
            return "evidencia oficial adicional (ver informe de identidad)"

        L2 = [
            "# Bloqueos de identidad por security (generado)",
            "",
            f"Generado con `scripts/gen_identity_reports.py` desde el run `{run.run_id}`. Fechas candidatas: "
            f"primer día hábil de cada mes entre {canon} y {horizon} ({len(dates)}). "
            "`backtest_universe` falla cerrado si UN miembro no tiene identidad probada; este informe "
            "no relaja nada, sólo registra qué security bloquea qué fechas. Entrada de trabajo de la "
            "siguiente iteración.",
            "",
            f"Fechas backtestables: **{sum(1 for d in dates if not any(d in v for v in rows.values()))}/{len(dates)}**.",
            "",
            "| security | blocked_dates | first_blocked_date | last_blocked_date | reason | missing_evidence |",
            "|---|---|---|---|---|---|",
        ]
        agg: dict[str, list[tuple[str, str, list[date]]]] = defaultdict(list)
        for (code, st, reason), ds in rows.items():
            agg[code].append((st, reason, ds))
        order = sorted(agg, key=lambda c: -len({d for _, _, ds in agg[c] for d in ds}))
        for code in order:
            alld = sorted({d for _, _, ds in agg[code] for d in ds})
            for st, reason, ds in sorted(agg[code], key=lambda x: min(x[2])):
                L2.append(
                    f"| {code} | {len(ds)} | {min(ds)} | {max(ds)} | {reason.replace('|', '/')} | "
                    f"{missing(st, reason)} |"
                )
            if len(agg[code]) > 1:
                L2.append(
                    f"| **{code} (total únicas)** | {len(alld)} | {alld[0]} | {alld[-1]} | | |"
                )
        only = defaultdict(int)
        for d in dates:
            bl = frozenset(c for c in agg if any(d in x for _, _, ds in agg[c] for x in [ds]))
            if bl:
                only[bl] += 1
        L2 += [
            "",
            "## Combinaciones de bloqueos por fecha",
            "",
            "| security(es) bloqueantes | fechas |",
            "|---|---|",
        ]
        for k, v in sorted(only.items(), key=lambda kv: -kv[1]):
            L2.append(f"| {', '.join(sorted(k))} | {v} |")
        base = json.loads((ROOT / "docs" / "identity_blockers_baseline_8d2993e.json").read_text())
        n_ev: dict[str, int] = defaultdict(int)
        for e in ses.scalars(select(OfficialCodeIsinEvidence)):
            n_ev[e.code] += 1
        after_by_code = {c: len({d for _, _, ds in agg[c] for d in ds}) for c in agg}
        alone: dict[str, int] = defaultdict(int)
        for d in dates:
            bl = {c for c in agg if any(d in ds for _, _, ds in agg[c])}
            if len(bl) == 1:
                alone[next(iter(bl))] += 1
        L2 += [
            "",
            "## Evolución frente a la línea base (8d2993e)",
            "",
            "Los conteos por security se solapan: una misma fecha podía estar bloqueada por varias.",
            "",
            f"Fechas elegibles: **{base['dates_backtestable']}/{base['dates_total']} → "
            f"{sum(1 for d in dates if not any(d in v for v in rows.values()))}/{len(dates)}**.",
            "",
            "| security | blocked_dates_before | blocked_dates_after | newly_eligible_dates | "
            "dates_unlocked_if_resolved_alone_now | evidence_status |",
            "|---|---|---|---|---|---|",
        ]
        for code, before in sorted(base["blocked_dates"].items(), key=lambda kv: -kv[1]):
            after = after_by_code.get(code, 0)
            L2.append(
                f"| {code} | {before} | {after} | {before - after} | {alone.get(code, 0)} | "
                f"{'RESOLVED' if after == 0 else 'BLOCKED'}: {n_ev.get(code, 0)} official "
                "code<->ISIN statements stored |"
            )
        (ROOT / "docs" / "IDENTITY_BLOCKERS.md").write_text("\n".join(L2) + "\n")
        # ── report 3: inventory of the official evidence ─────────────────────────────
        from sqlalchemy import func

        L3 = [
            "# Inventario de evidencia oficial de identidad (generado)",
            "",
            "Generado con `scripts/gen_identity_reports.py` desde las tablas `official_code_isin_evidence` "
            "y `official_isin_transitions` (ADR-0022). Cada fila apunta a un documento archivado en "
            "`raw_source_archive` con SHA-256.",
            "",
            "## Declaraciones código ↔ ISIN por tipo de fuente",
            "",
            "| Fuente | Filas | Desde | Hasta | Códigos distintos |",
            "|---|---|---|---|---|",
        ]
        for kind, n, a, b, nc in ses.execute(
            select(
                OfficialCodeIsinEvidence.source_kind,
                func.count(),
                func.min(OfficialCodeIsinEvidence.observed_on),
                func.max(OfficialCodeIsinEvidence.observed_on),
                func.count(func.distinct(OfficialCodeIsinEvidence.code)),
            ).group_by(OfficialCodeIsinEvidence.source_kind)
        ):
            L3.append(f"| {kind} | {n} | {a} | {b} | {nc} |")
        L3 += ["", "## Documentos de transiciones (verificados contra el original)", ""]
        for t in sorted(transitions.values(), key=lambda t: t.effective_date):
            L3.append(
                f"### {t.old_isin} → {t.new_isin} ({t.kind}, {t.continuity}, efecto {t.effective_date})"
            )
            L3.append("")
            for d in tr_docs.get((t.old_isin, t.new_isin), []):
                L3.append(
                    f"- **{d.get('role')}** — {d.get('url')} "
                    f"[{d.get('via')}{' ' + str(d.get('wayback_ts')) if d.get('wayback_ts') else ''}], "
                    f"SHA-256 `{d.get('sha256')}`, extracción {d.get('extraction')}"
                )
                for ex in d.get("excerpts") or []:
                    L3.append(f"  - «{ex[:200]}»")
            L3.append("")
        (ROOT / "docs" / "OFFICIAL_IDENTITY_EVIDENCE.md").write_text("\n".join(L3) + "\n")
        print(f"{len(cases)} cases; blockers: {len(order)} securities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
