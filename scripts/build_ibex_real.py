"""Build the REAL IBEX 35 membership from archived official BME documents, resolve the
identity of every interval with CNMV ANCV evidence (ADR-0020) and write the coverage
report (docs/IBEX_COVERAGE_REPORT.md). No network: everything is read back from
raw_source_archive / security_identity_snapshots.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/build_ibex_real.py

Prerequisite: scripts/ingest_ancv.py (ANCV snapshots + NIF queries).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.errors import UnknownSecurityError  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.providers.cnmv.ancv import parse_nif_query  # noqa: E402
from pitquant.db.models import (  # noqa: E402
    DataQualityIssue,
    IdentifierHistory,
    IndexEvent,
    IndexMembership,
    IssuerIdentifier,
    RawSourceArchive,
)
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.jobs.index_ingest import ingest_event_source  # noqa: E402
from pitquant.security_master.identity import (  # noqa: E402
    BACKTESTABLE,
    IdentityResolutionEngine,
    IdentityResolutionStatus,
    OfficialIdentifier,
    RowOutcome,
    resolve_code_row,
)
from pitquant.security_master.identity_store import (  # noqa: E402
    load_snapshot_index,
    run_identity_resolution,
    snapshots_hash,
)
from pitquant.security_master.service import SecurityMaster  # noqa: E402
from pitquant.universe.index_membership import IndexUniverse  # noqa: E402
from pitquant.universe.sources.bme import (  # noqa: E402
    COMPOIBEX_2026_09,
    COMPOIBEX_2026_09_SHA256,
    RowStyle,
    extract_rows_from_pdf,
)
from pitquant.universe.sources.bme_reconstruction import (  # noqa: E402
    CurrentComposition,
    events_from_official_documents,
)

OBS_ID = "observation:bme-ibex35-constituents:2026-10-01"
COVERAGE_START = date(1995, 1, 2)  # first session in the XMAD calendar
CHECK_DATES = [
    (date(2018, 6, 29), "day before GAS -> NTGY (row 108, 2018-07-02)"),
    (date(2018, 7, 2), "GAS -> NTGY effective (code change proven by ANCV)"),
    (date(2022, 6, 10), "before REE -> RED (row 122, 2022-06-13)"),
    (date(2022, 6, 13), "REE -> RED effective (code change proven by ANCV)"),
    (date(2019, 6, 21), "before ordinary review row 112 (2019-06-24: MAS in, TRE out)"),
    (date(2019, 6, 24), "ordinary review row 112 effective"),
    (date(1998, 12, 31), "before re-entry of ANA (row 22, 1999-01-04; ANA left 1997-07-01)"),
    (date(1999, 1, 4), "ANA re-enters (new identity, IDENTITY_UNRESOLVED)"),
    (date(2017, 6, 6), "before extraordinary exclusion of POP (row 104, 2017-06-07)"),
    (date(2017, 6, 7), "POP excluded (Banco Popular resolution)"),
    (date(2006, 7, 28), "33-member window (rows 55-58)"),
    (date(2012, 3, 1), "36-member window (DIA added 2012-01-02)"),
]


def main() -> int:
    s = get_settings()
    canon = s.canonical_period.start
    store = ArchiveStore(ROOT / s.archive.root)
    factory = make_session_factory(make_engine(s.database.url))
    with factory() as ses:
        obs_row = ses.scalars(
            select(RawSourceArchive).where(RawSourceArchive.source_identifier == OBS_ID)
        ).one()
        obs = json.loads(store.get(obs_row.sha256))
        current = CurrentComposition(
            date.fromisoformat(obs["observed_at"][:10]),
            tuple((t, i) for t, i in obs["constituents"]),
            obs_row.sha256,
        )
        rows = extract_rows_from_pdf(store.get(COMPOIBEX_2026_09_SHA256), COMPOIBEX_2026_09)
        ix = load_snapshot_index(ses)
        if not ix.dates:
            raise SystemExit("no ANCV snapshots: run scripts/ingest_ancv.py first")
        snap_hash = snapshots_hash(ses)

        # 1. rows without a legend marker: classify by ANCV ISIN continuity
        row_res = []
        for r in rows:
            if r.style is RowStyle.UNKNOWN and len(r.additions) == 1 and len(r.deletions) == 1:
                row_res.append(
                    resolve_code_row(
                        ix, r.row_ref, r.deletions[0], r.additions[0], r.effective_date
                    )
                )
        resolutions = {
            rr.row_ref: (
                rr.outcome.value,
                f"ANCV {rr.isin_before} ({rr.evidence[0][:10]}) = {rr.isin_after} "
                f"({rr.evidence[1][:10]}), continuo"[:200],
            )
            for rr in row_res
            if rr.outcome in (RowOutcome.TICKER_CHANGE, RowOutcome.INDEX_TURNOVER)
        }

        # 2. membership build (code space)
        size = s.universe("IBEX35").expected_size
        src, rec = events_from_official_documents(
            rows,
            current,
            COVERAGE_START,
            COMPOIBEX_2026_09_SHA256,
            size,
            row_resolutions=resolutions,
            resolutions_hash=snap_hash,
        )
        rep = ingest_event_source(
            ses, src, exchange="XMAD", currency="EUR", country="ES", expected_size=size
        )

        # 3. official links: CIF <-> ISIN (ANCV query by NIF) and the BME current composition
        links: dict[str, str] = {}
        for a in ses.scalars(
            select(RawSourceArchive).where(RawSourceArchive.provider == "CNMV_ANCV_NIF_QUERY")
        ):
            cif = (a.notes or "").split("cif=")[1].split(";")[0]
            ident = ses.scalars(
                select(IssuerIdentifier).where(
                    IssuerIdentifier.id_type == "CIF", IssuerIdentifier.value == cif
                )
            ).first()
            if ident is None:
                continue
            for ln in parse_nif_query(store.get(a.sha256)).ordinary_shares():
                links[ln.isin] = ident.issuer_id
        official = [
            OfficialIdentifier(
                t,
                i,
                current.observed_on,
                "BME current composition (transcription)",
                obs_row.sha256,
                exact=False,
            )
            for t, i in current.constituents
        ]

        # 4. identity resolution over the build
        engine = IdentityResolutionEngine(ix, official, horizon=current.observed_on)
        res = run_identity_resolution(
            ses,
            index_code="IBEX35",
            build_id=rep.build_id,
            engine=engine,
            canonical_start=canon,
            inputs_hash=snap_hash,
            official=official,
            issuer_links=links,
        )
        sm = SecurityMaster(ses)
        calib: list[str] = []
        for ticker, isin in current.constituents:  # current identity, from the observation
            sid = sm.resolve(ticker, "XMAD", current.observed_on)
            owners = set(
                ses.scalars(
                    select(IdentifierHistory.security_id).where(
                        IdentifierHistory.id_type == "ISIN", IdentifierHistory.value == isin
                    )
                )
            )
            if owners and sid not in owners:
                ses.add(
                    DataQualityIssue(
                        entity="identifier_history",
                        security_id=sid,
                        check_name="current_isin_owned_by_other_security",
                        severity="medium",
                        details={"ticker": ticker, "isin": isin, "owners": sorted(owners)},
                    )
                )
                continue
            try:
                sm.resolve_identifier("ISIN", isin, current.observed_on)
            except UnknownSecurityError:
                sm.add_identifier(sid, "ISIN", isin, current.observed_on)
        # calibration: engine's ISIN on the last ANCV date vs the BME composition
        last = ix.dates[-1]
        u = IndexUniverse(ses)
        engine_isins: dict[str, str | None] = {}
        for m in u.universe("IBEX35", last, rep.build_id):
            seg = next(
                (
                    x
                    for x in res.segments.get(m.membership_id or -1, [])
                    if x.start <= last and (x.end is None or last < x.end)
                ),
                None,
            )
            engine_isins[sm.ticker_as_of(m.security_id, last) or "?"] = seg.isin if seg else None
        agree = mism = miss = 0
        for t, i in current.constituents:
            got = engine_isins.get(t)
            if got is None:
                miss += 1
                calib.append(f"| {t} | {i} | — (sin ISIN probado) |")
            elif got == i:
                agree += 1
            else:
                mism += 1
                calib.append(f"| {t} | {i} | **{got}** (discrepancia) |")
        ses.commit()

        # 5. report
        m, mp = res.metrics, res.metrics_pre
        L = [
            "# IBEX 35 — informe de cobertura del universo real",
            "",
            "Generado con `scripts/build_ibex_real.py` (ADR-0017, ADR-0020). Fuentes:",
            f"- Composición histórica IBEX 35 (BME): `{COMPOIBEX_2026_09_SHA256}`.",
            f"- Composición vigente observada el {current.observed_on}: **transcripción** de "
            "páginas oficiales renderizadas por JavaScript — "
            f"`{obs_row.sha256}`. Por eso el build es PROVISIONAL_RESEARCH_SOURCE.",
            f"- Identidad: {len(ix.dates)} snapshots semestrales ANCV de la CNMV "
            f"({ix.dates[0]} → {ix.dates[-1]}), hash del conjunto `{snap_hash}`.",
            "",
            f"Build `{rep.build_id}`: estado **{rep.status}**, {rep.n_events} eventos, "
            f"{rep.n_intervals} intervalos. Run de identidad `{res.run.run_id}` "
            f"(`{res.run.engine_version}`).",
            "",
            f"## Identidad IBEX 2011+ (periodo canónico V1, desde {canon})",
            "",
            "| Métrica | IBEX_IDENTITY_2011_PLUS | IBEX_IDENTITY_PRE_2011 (archivo) |",
            "|---|---|---|",
        ]
        for k in (
            "intervals_total",
            "resolved_exact",
            "resolved_multi_source",
            "provisional",
            "unresolved",
            "coverage_percentage",
        ):
            L.append(f"| {k} | {m[k]} | {mp[k]} |")
        L += [
            "",
            "Un intervalo cuenta como resuelto sólo si TODOS sus segmentos dentro del periodo "
            "son EXACT_OFFICIAL_IDENTIFIER o MULTI_SOURCE_CONFIRMED. Lo anterior a "
            f"{canon} es ARCHIVAL / NON_CANONICAL_FOR_V1 y no bloquea V1.",
            "",
            "### Calibración contra la composición vigente",
            "",
            f"ISIN del motor en {last} frente a la composición BME observada el "
            f"{current.observed_on}: **{agree} coinciden, {mism} discrepan, {miss} sin ISIN "
            "probado**.",
            "",
        ]
        if calib:
            L += ["| Código | ISIN BME | Motor |", "|---|---|---|", *calib, ""]
        # date-level: backtest_universe fails closed if ANY member is not proven
        from collections import Counter

        from pitquant.data.calendars.market_calendar import get_calendar
        from pitquant.universe.index_membership import IdentityUnresolvedError

        firsts = get_calendar("XMAD").first_sessions_of_months(canon, current.observed_on)
        ok_dates, blockers = 0, Counter()
        for d in firsts:
            try:
                u.backtest_universe("IBEX35", d, rep.build_id, canonical_start=canon)
                ok_dates += 1
            except IdentityUnresolvedError:
                for mm in u.universe("IBEX35", d, rep.build_id):
                    seg = next(
                        (
                            x
                            for x in res.segments.get(mm.membership_id or -1, [])
                            if x.start <= d and (x.end is None or d < x.end)
                        ),
                        None,
                    )
                    if seg is None or seg.status not in BACKTESTABLE:
                        blockers[sm.ticker_as_of(mm.security_id, d) or "?"] += 1
        L += [
            "### Fechas backtestables (fallo cerrado por fecha)",
            "",
            f"`backtest_universe` en el primer día hábil de cada mes desde {canon}: "
            f"**{ok_dates}/{len(firsts)} fechas pasan**. Basta UN miembro sin identidad "
            "probada para que la fecha falle (descartarlo sería sesgo de supervivencia).",
            "",
            "Códigos que bloquean (número de fechas): "
            + (", ".join(f"{k} ({v})" for k, v in blockers.most_common()) or "ninguno"),
            "",
        ]
        L += [
            "## Las 7 filas sin marcador de leyenda",
            "",
            "Clasificadas sólo con evidencia: mismo ISIN (ANCV) bajo la etiqueta antigua antes y "
            "la nueva después, presente en TODOS los snapshots intermedios.",
            "",
            "| Fila | Fecha | Cambio | Resultado | Evidencia |",
            "|---|---|---|---|---|",
        ]
        for rr in row_res:
            L.append(
                f"| {rr.row_ref} | {rr.effective_date} | {rr.old_code}→{rr.new_code} | "
                f"**{rr.outcome.value}** | {'; '.join(rr.evidence)} |"
            )
        L += ["", "## Comprobaciones por fecha", ""]
        for d, label in CHECK_DATES:
            mem = u.universe("IBEX35", d, rep.build_id)
            tick = sorted(sm.ticker_as_of(x.security_id, d) or "?" for x in mem)
            L.append(f"- **{d}** ({label}): {len(mem)} miembros — {', '.join(tick)}")
        L += ["", "## Eventos con tipo no demostrado (UNRESOLVED_EVENT_TYPE)", ""]
        L += [f"- {e}" for e in rec.unresolved_events] or ["- ninguno"]
        L += ["", "## Anomalías del documento", ""]
        L += [f"- {a}" for a in rec.order_anomalies] or ["- ninguna"]
        L += [
            "",
            "## Identidad por intervalo (intervalos que tocan el periodo canónico)",
            "",
            "| Código | Desde | Hasta | Segmentos (estado: ISIN [desde, hasta)) |",
            "|---|---|---|---|",
        ]
        unresolved_rows = []
        ivs = ses.scalars(
            select(IndexMembership)
            .where(IndexMembership.build_id == rep.build_id)
            .order_by(IndexMembership.effective_from, IndexMembership.ticker_at_inclusion)
        ).all()
        for iv in ivs:
            if iv.effective_to is not None and iv.effective_to <= canon:
                continue
            segs = res.segments[iv.id]
            txt = "; ".join(
                f"{x.status.value.split('_')[0]}: {x.isin or '|'.join(x.candidates) or '—'} "
                f"[{x.start}, {x.end or 'abierto'})"
                for x in segs
                if x.end is None or x.end > canon
            )
            L.append(
                f"| {iv.ticker_at_inclusion} | {iv.effective_from} | {iv.effective_to or '—'} "
                f"| {txt} |"
            )
            for x in segs:
                if (x.end is None or x.end > canon) and x.status not in BACKTESTABLE:
                    unresolved_rows.append(
                        f"| {iv.ticker_at_inclusion} | {max(x.start, canon)} | "
                        f"{x.end or 'abierto'} | {x.status.value} | "
                        f"{'; '.join(x.evidence[-2:])} |"
                    )
        L += [
            "",
            "## Identidades no resueltas en el periodo canónico",
            "",
            "| Código | Desde | Hasta | Estado | Motivo |",
            "|---|---|---|---|---|",
            *(unresolved_rows or ["| — | | | | |"]),
            "",
            "## Intervalos anteriores a 2011 (archivo)",
            "",
            "| Ticker | Desde | Hasta | Entrada | Salida |",
            "|---|---|---|---|---|",
        ]
        for iv in ivs:
            if iv.effective_to is None or iv.effective_to > canon:
                continue
            ev = ses.get_one(IndexEvent, iv.source_event_id)
            L.append(
                f"| {iv.ticker_at_inclusion} | {iv.effective_from} | {iv.effective_to} "
                f"| {ev.reason} | {iv.exclusion_reason or '—'} |"
            )
        (ROOT / "docs" / "IBEX_COVERAGE_REPORT.md").write_text("\n".join(L) + "\n")
        print("\n".join(L[:40]))
        st = {x.status for segs in res.segments.values() for x in segs}
        assert IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED in st
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
