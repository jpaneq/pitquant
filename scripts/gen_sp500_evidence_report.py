# ruff: noqa: E501, E402
"""docs/SP500_MEMBERSHIP_EVIDENCE.md from the latest evidence run (never by hand). ADR-0025."""

from __future__ import annotations

import collections
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import func, select

from pitquant.config.settings import get_settings
from pitquant.db.models import (
    RawSourceArchive,
    SP500Announcement,
    SP500DiscoveryRow,
    SP500MembershipEvent,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.sources.sp500_evidence import CANONICAL_STATUSES, EventStatus


def main() -> int:
    s = get_settings()
    with make_session_factory(make_engine(s.database.url))() as ses:
        run_id = ses.scalars(
            select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
        ).first()
        if run_id is None:
            print("no evidence run")
            return 1
        ev = ses.scalars(
            select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == run_id)
        ).all()
        anns = ses.scalars(select(SP500Announcement)).all()
        by_status = collections.Counter(e.status for e in ev)
        conf1 = sum(1 for e in ev if e.status == "OFFICIAL_CONFIRMED")
        conf2 = sum(1 for e in ev if e.status == "OFFICIAL_REPUBLISHED_CONFIRMED")
        n = len(ev)
        canon = conf1 + conf2
        cov = 100 * canon / n if n else 0.0
        by_year: dict[int, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for e in ev:
            by_year[e.discovery_date.year]["total"] += 1  # type: ignore[union-attr]
            if EventStatus(e.status) in CANONICAL_STATUSES:
                by_year[e.discovery_date.year]["confirmed"] += 1  # type: ignore[union-attr]
        first_gap = min(
            (
                e.discovery_date
                for e in ev
                if EventStatus(e.status) not in CANONICAL_STATUSES and e.discovery_date
            ),
            default=None,
        )
        added = {e.added_ticker for e in ev if e.added_ticker}
        removed = {e.removed_ticker for e in ev if e.removed_ticker}
        docs = collections.Counter(a.source_tier for a in anns)
        arch = ses.scalars(
            select(RawSourceArchive).where(RawSourceArchive.provider == "SP500_DISCOVERY:chinobing")
        ).first()
        matched_ann = {e.announcement_row_id for e in ev if e.announcement_row_id}
        extras = [
            a
            for a in anns
            if a.announcement_row_id not in matched_ann
            and (a.stated_change_date or a.announcement_at.date()) >= date(2011, 1, 1)
        ]
        n_disc_rows = ses.scalar(select(func.count()).select_from(SP500DiscoveryRow))

        L = [
            "# Evidencia de membresía S&P 500 (D-02, candidato construido desde fuentes públicas)",
            "",
            "> Generado por `scripts/gen_sp500_evidence_report.py` (ADR-0025). **No es canónico**: la lista comunitaria sólo descubre;",
            "> cada cambio necesita un comunicado de S&P (tier 1) o su copia en PRNewswire (tier 2). Ningún evento se corrige para",
            "> que coincida con GitHub/Wikipedia.",
            "",
            "## Resumen",
            "",
            "```",
            f"discovery_events_2011_present        = {n}   (filas del CSV: {n_disc_rows})",
            f"official_confirmed (tier 1 S&P)      = {conf1}",
            f"official_republished_confirmed (t2)  = {conf2}",
            f"date_tba                             = {by_status.get('DATE_TBA', 0)}",
            f"conflicts                            = {by_status.get('CONFLICT', 0)}",
            f"unresolved                           = {by_status.get('UNRESOLVED', 0)}",
            f"discovery_only (sin evidencia)       = {by_status.get('DISCOVERY_ONLY', 0)}",
            f"coverage_pct                         = {cov:.1f}%",
            "```",
            "",
            "## Estados D-02",
            "",
            "- `SP500_MEMBERSHIP_DISCOVERY_READY` = **true** (CSV archivado "
            + (f"sha256 `{arch.sha256}`" if arch else "")
            + ").",
            f"- `SP500_MEMBERSHIP_EVIDENCE_COVERAGE` = **{cov:.1f}%** ({canon}/{n} eventos con evidencia oficial concordante).",
            "- `SP500_MEMBERSHIP_CANONICAL_READY` = **false**: (1) `CURRENT_ANCHOR_BLOCKED` (la página de S&P DJI devuelve 403 y su `Full Constituents List` no se puede archivar automáticamente: sin ancla no hay reconstrucción hacia atrás ni comprobación de reversibilidad sobre datos reales), y (2) quedan eventos sin evidencia (ver gaps).",
            "",
            f"Primer evento sin confirmar: **{first_gap}**. Sin ancla actual no hay primera fecha reconstruible ni año completo reconstruible; con ancla, las fechas anteriores a ese evento dependerían de él y no podrían declararse canónicas (fail-closed).",
            "",
            "## Documentos de evidencia",
            "",
            f"- Tier 1 `OFFICIAL_SPDJI` (press.spglobal.com): {docs.get('OFFICIAL_SPDJI', 0)} cláusulas «will replace … in the S&P 500» parseadas.",
            f"- Tier 2 `OFFICIAL_REPUBLISHED` (PRNewswire vía Wayback): {docs.get('OFFICIAL_REPUBLISHED', 0)} cláusulas.",
            "- El archivo de prensa de S&P Global sólo contiene comunicados de cambios de índice desde ~2014; PRNewswire sólo es localizable por el índice CDX de Wayback (2010–2011 sobre todo).",
            "",
            "## Cobertura por año",
            "",
            "| año | eventos discovery | confirmados | % |",
            "|---|---|---|---|",
        ]
        for y in sorted(by_year):
            c = by_year[y]
            L.append(
                f"| {y} | {c['total']} | {c['confirmed']} | {100 * c['confirmed'] / c['total']:.0f}% |"
            )
        L += [
            "",
            "## Universo",
            "",
            f"- Tickers distintos añadidos en eventos 2011+: {len(added)}; eliminados: {len(removed)}; unión (sin ancla no se conoce la composición inicial): {len(added | removed)}.",
            f"- Former constituents con eliminación confirmada oficialmente: {len({e.removed_ticker for e in ev if e.removed_ticker and EventStatus(e.status) in CANONICAL_STATUSES})}.",
            "- Resolución ticker → `security_id`: **no resuelta** (el Security Master sólo contiene AAPL y MSFT del S&P 500). Evidencia de membresía e identidad de la security son capas separadas.",
            "",
            "## Comparación con el CSV de descubrimiento (QA, nunca corrige lo oficial)",
            "",
            f"- Coinciden (fecha efectiva oficial = fecha CSV): {canon}.",
            f"- Diferencia de fecha (CONFLICT): {by_status.get('CONFLICT', 0)}; diferencia de ticker / un solo lado (UNRESOLVED): {by_status.get('UNRESOLVED', 0)}.",
            f"- Faltan en lo oficial (DISCOVERY_ONLY + TBA sin fecha posterior): {by_status.get('DISCOVERY_ONLY', 0) + by_status.get('DATE_TBA', 0)}.",
            f"- Anuncios oficiales ≥ 2011 sin fila CSV correspondiente (sobrantes): {len(extras)} (pueden ser anuncios TBA reemplazados, cambios de otro índice mal clasificados o rectificaciones).",
            "",
        ]
        if extras:
            L += [
                "| anuncio | cambio declarado | tipo | añadida | eliminada | tier |",
                "|---|---|---|---|---|---|",
            ]
            for a in sorted(extras, key=lambda x: x.announcement_at)[:60]:
                L.append(
                    f"| {a.announcement_at.date()} | {a.stated_change_date} {a.timing} | {a.reason_class} | {a.added_ticker} | {a.removed_ticker} | {a.source_tier} |"
                )
            L.append("")
        L += [
            "## Gaps (eventos sin evidencia oficial concordante)",
            "",
            "| fecha | añadida | eliminada | fuente discovery | fuente oficial | estado | motivo |",
            "|---|---|---|---|---|---|---|",
        ]
        for e in sorted(
            ev,
            key=lambda x: (
                x.discovery_date or date.min,
                x.added_ticker or "",
                x.removed_ticker or "",
            ),
        ):
            if EventStatus(e.status) in CANONICAL_STATUSES:
                continue
            off = (e.source_url or "—")[:70]
            L.append(
                f"| {e.discovery_date} | {e.added_ticker or '—'} | {e.removed_ticker or '—'} | chinobing CSV | {off} | {e.status} | {e.reason} |"
            )
    Path(ROOT / "docs" / "SP500_MEMBERSHIP_EVIDENCE.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8"
    )
    print(f"wrote docs/SP500_MEMBERSHIP_EVIDENCE.md: {n} events, {canon} confirmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
