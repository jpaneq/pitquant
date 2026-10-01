"""Enagás end-to-end Spanish identity demo (ADR-0020) from the LOCAL real database:

    CNMV issuer → issuer_id → historical ISIN → security_id → historical ticker →
    IBEX membership → CNMV fundamentals → PITContext → audit explain

Writes docs/REAL_DATA_SPANISH_IDENTITY_DEMO.md. No network.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/gen_spanish_identity_demo.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.audit.explain import explain_fact  # noqa: E402
from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.point_in_time.engine import facts_as_of  # noqa: E402
from pitquant.data.providers.cnmv.ancv import parse_nif_query  # noqa: E402
from pitquant.db.models import (  # noqa: E402
    CnmvFiling,
    IdentifierHistory,
    IndexMembership,
    Issuer,
    IssuerIdentifier,
    MembershipIdentitySegment,
    RawSourceArchive,
    Security,
    SecurityIdentitySnapshot,
    TickerHistory,
)
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.security_master.identity_store import latest_run  # noqa: E402
from pitquant.universe.index_membership import IndexUniverse  # noqa: E402

CIF, ISIN = "A-28294726", "ES0130960018"
MAD = ZoneInfo("Europe/Madrid")
T = datetime(2018, 7, 18, 9, 0, tzinfo=MAD)  # day the 2018 S1 report became usable
CONCEPT = "I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos]"


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    with make_session_factory(make_engine(s.database.url))() as ses:
        ident = ses.scalars(
            select(IssuerIdentifier).where(
                IssuerIdentifier.id_type == "CIF", IssuerIdentifier.value == CIF
            )
        ).one()
        issuer = ses.get_one(Issuer, ident.issuer_id)
        filings = ses.scalars(
            select(CnmvFiling)
            .where(CnmvFiling.issuer_id == issuer.issuer_id)
            .order_by(CnmvFiling.period_end)
        ).all()
        nif = ses.scalars(
            select(RawSourceArchive).where(
                RawSourceArchive.provider == "CNMV_ANCV_NIF_QUERY",
                RawSourceArchive.notes.like(f"%cif={CIF}%"),
            )
        ).first()
        assert nif is not None, "run scripts/ingest_ancv.py first"
        q = parse_nif_query(store.get(nif.sha256))
        snaps = ses.scalars(
            select(SecurityIdentitySnapshot)
            .where(SecurityIdentitySnapshot.isin == ISIN)
            .order_by(SecurityIdentitySnapshot.reference_date)
        ).all()
        owner = ses.scalars(
            select(IdentifierHistory).where(
                IdentifierHistory.id_type == "ISIN", IdentifierHistory.value == ISIN
            )
        ).all()
        sid = owner[0].security_id
        sec = ses.get_one(Security, sid)
        ticks = ses.scalars(
            select(TickerHistory)
            .where(TickerHistory.security_id == sid)
            .order_by(TickerHistory.valid_from)
        ).all()
        u = IndexUniverse(ses)
        build = u.active_build("IBEX35")
        run = latest_run(ses, build.build_id)
        assert run is not None
        ivs = ses.scalars(
            select(IndexMembership).where(
                IndexMembership.build_id == build.build_id, IndexMembership.security_id == sid
            )
        ).all()
        segs = ses.scalars(
            select(MembershipIdentitySegment)
            .where(
                MembershipIdentitySegment.run_id == run.run_id,
                MembershipIdentitySegment.membership_id.in_([i.id for i in ivs]),
            )
            .order_by(MembershipIdentitySegment.segment_from)
        ).all()
        on = T.date()
        members = u.universe("IBEX35", on, build.build_id)
        in_universe = [m for m in members if m.security_id == sid]
        seg_t = next(
            x for x in segs if x.segment_from <= on and (x.segment_to is None or on < x.segment_to)
        )
        facts = facts_as_of(ses, sid, T)
        hit = [
            f
            for k, f in facts.items()
            if k.concept == CONCEPT and k.period_end == date(2017, 6, 30)
        ]
        ex = explain_fact(ses, sid, CONCEPT, date(2017, 6, 30), T, exchange="XMAD")
        bt: str
        try:
            got = u.backtest_universe(
                "IBEX35", on, build.build_id, canonical_start=s.canonical_period.start
            )
            bt = f"pasa ({len(got)} miembros)"
        except Exception as e:
            bt = f"FALLA CERRADO: {e}"

    same_issuer = (
        "= el emisor CNMV" if sec.issuer_id == issuer.issuer_id else "DISTINTO del emisor CNMV"
    )
    code_t = next(
        (t.ticker for t in ticks if t.valid_from <= on and (t.valid_to is None or on < t.valid_to)),
        "?",
    )
    L = [
        "# Enagás de extremo a extremo: identidad española con datos REALES",
        "",
        "Generado con `scripts/gen_spanish_identity_demo.py` sobre la base local real "
        "(ADR-0018, ADR-0020). Pregunta: **¿por qué sabemos que este filing, este ticker y "
        "este membership corresponden al mismo emisor y a la misma security en "
        f"T = {T.isoformat()}?**",
        "",
        "## 1. Emisor CNMV → `issuer_id`",
        "",
        f"- Emisor `{issuer.issuer_id}` «{issuer.name}», identificado por **CIF {CIF}** "
        f"(fuente: {ident.source}). Ningún ticker ni security se crea a partir del CIF.",
        f"- Informes periódicos CNMV de ese CIF ingeridos: {len(filings)} — "
        + ", ".join(
            f"nreg {f.nreg} ({f.period_label}, publicado {f.publication_date})" for f in filings
        )
        + ".",
        "",
        "## 2. `issuer_id` → ISIN (documento oficial)",
        "",
        f"- Consulta ANCV por NIF (`{nif.source_identifier}`, archivada SHA-256 `{nif.sha256}`, "
        f"{nif.retrieved_at.date()}): «{q.issuer_name}» → "
        + ", ".join(f"**{x.isin}** {x.fisn} (emitido {x.issue_date}, CFI {x.cfi})" for x in q.lines)
        + ".",
        "- Es un vínculo CIF ↔ ISIN de la propia CNMV; no un parecido de nombre.",
        "",
        "## 3. ISIN histórico (snapshots ANCV)",
        "",
        f"- {ISIN} aparece en **{len(snaps)}** snapshots semestrales ANCV "
        f"({snaps[0].reference_date} → {snaps[-1].reference_date}), siempre con etiqueta "
        f"{sorted({x.instrument_name.split('/')[0] for x in snaps})} y razón social "
        f"{sorted({x.issuer_legal_name for x in snaps})}.",
        "- Un snapshot prueba que el ISIN estaba activo en su fecha de referencia; NO es una "
        "fecha de alta ni de baja.",
        "",
        "| Fecha ref. | Alcance (LEAME) | Etiqueta | SHA-256 del miembro |",
        "|---|---|---|---|",
        *(
            f"| {x.reference_date} | {x.scope} | {x.instrument_name} | `{x.source_hash[:16]}…` |"
            for x in snaps
        ),
        "",
        "## 4. ISIN → `security_id`",
        "",
        f"- Security `{sid}` ({sec.name}), emisor enlazado `{sec.issuer_id}` ({same_issuer}).",
        "- Validez probada del ISIN en esa security: "
        + ", ".join(f"[{o.valid_from}, {o.valid_to or 'abierto'})" for o in owner)
        + " — la unión de los segmentos MULTI_SOURCE_CONFIRMED, nunca un alta inventada.",
        "",
        "## 5. Ticker histórico (BME)",
        "",
        *(
            f"- `{t.ticker}` [{t.valid_from}, {t.valid_to or 'abierto'}) — acotado a la membership "
            "(el histórico BME sólo prueba el código mientras es miembro)"
            for t in ticks
        ),
        "",
        "## 6. Membership IBEX y su identidad",
        "",
        *(
            f"- Intervalo [{i.effective_from}, {i.effective_to or 'abierto'}) código "
            f"{i.ticker_at_inclusion} (build `{build.build_id[:8]}`, {build.source_confidence})"
            for i in ivs
        ),
        f"- Segmentos de identidad (run `{run.run_id[:8]}`):",
        *(
            f"  - [{x.segment_from}, {x.segment_to or 'abierto'}) **{x.status}** {x.isin or '—'} "
            f"({x.period_class}); evidencia: {'; '.join(x.evidence[-3:])}"
            for x in segs
        ),
        "",
        f"## 7. En T = {T.isoformat()}",
        "",
        f"- `universe('IBEX35', {on})`: {len(members)} miembros; Enagás "
        f"{'presente' if in_universe else 'AUSENTE'} (código "
        f"{code_t}).",
        f"- Segmento de identidad en T: **{seg_t.status}** → {seg_t.isin} → "
        f"security `{seg_t.security_id}`.",
        f"- `facts_as_of(security, T)`: {len(facts)} hechos visibles, del EMISOR (issuer_id) por "
        f"ser fundamentales CNMV; {CONCEPT} @ 2017-06-30 = "
        f"{hit[0].value if hit else '—'} (nreg del filing que lo aporta en el explain).",
        f"- `backtest_universe('IBEX35', {on})`: {bt}",
        "",
        "### `explain` en T",
        "```",
        ex.to_text(),
        "```",
        "",
        "## Por qué es la misma entidad",
        "",
        "1. **Filing → emisor:** el informe CNMV lleva el CIF A-28294726 en su ficha oficial.",
        "2. **Emisor → ISIN:** la ANCV (CNMV) devuelve para ese NIF el ISIN ES0130960018.",
        "3. **ISIN → security:** el motor de identidad ancla ES0130960018 al intervalo IBEX "
        "porque, DENTRO del intervalo, la única acción ordinaria con etiqueta ANCV `ENG` es ese "
        "ISIN, y está presente en todos los snapshots (MULTI_SOURCE_CONFIRMED: BME + ANCV).",
        "4. **Security → ticker/membership:** el código ENG es el que el histórico oficial BME "
        "da a ese miembro en esas fechas.",
        "",
        "Lo que NO se afirma: fechas de alta/baja del ISIN (los snapshots no las prueban), ni "
        "identidad anterior al primer snapshot (2010-06-30, ARCHIVAL). Si `backtest_universe` "
        "falla en T, es porque OTRO miembro del índice no tiene identidad probada (fallo "
        "cerrado por fecha), no por Enagás.",
    ]
    (ROOT / "docs" / "REAL_DATA_SPANISH_IDENTITY_DEMO.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:12]))
    print(json.dumps({"segments": len(segs), "snapshots": len(snaps)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
