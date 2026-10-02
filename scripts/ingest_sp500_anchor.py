# ruff: noqa: E501
"""SP500_CURRENT_ANCHOR from SPY (State Street) and IVV (iShares) holdings (ADR-0026). Idempotent.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_sp500_anchor.py

Archives (URL, retrieved_at, SHA-256) the SPY holdings workbook, the IVV holdings CSV and both
product pages BEFORE parsing; reconciles equities (not counts) after advancing the older file with
the S&P events confirmed by official announcements; writes docs/SP500_CURRENT_ANCHOR.md.
"""

from __future__ import annotations

import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.models import (  # noqa: E402
    IndexAnchorSnapshot,
    IndexCurrentAnchor,
    SP500Announcement,
)
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.sources.sp500_anchor import (  # noqa: E402
    AnchorEvent,
    HoldingsSnapshot,
    parse_ivv_csv,
    parse_spy_xlsx,
    reconcile,
)
from pitquant.universe.sources.sp500_evidence import Timing, effective_session  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
SPY_PAGE = "https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy"
SPY_FILE = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
)
IVV_PAGE = "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf"
IVV_FILE = "https://www.ishares.com/us/products/239726/ishares-core-s-p-500-etf/latest-holdings.csv"


def get(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120
        ) as r:
            body: bytes = r.read()
        return body
    except Exception:
        return None


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    with make_session_factory(make_engine(s.database.url))() as ses:
        files: dict[str, tuple[bytes, str, str]] = {}
        for src, page, f, mime in (
            (
                "SPY",
                SPY_PAGE,
                SPY_FILE,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("IVV", IVV_PAGE, IVV_FILE, "text/csv"),
        ):
            pb = get(page)
            if pb is not None:
                archive_document(
                    ses,
                    store,
                    provider=f"ETF_PAGE:{src}",
                    source_identifier=page,
                    data=pb,
                    mime_type="text/html",
                    parser_version="anchor-1",
                    notes="product page (benchmark declaration)",
                )
            fb = get(f)
            if fb is None:
                print(f"{src}: holdings file unavailable -> BLOCKED")
                continue
            row = archive_document(
                ses,
                store,
                provider=f"ETF_HOLDINGS:{src}",
                source_identifier=f,
                data=fb,
                mime_type=mime,
                parser_version="anchor-1",
                notes="daily holdings file",
            )
            files[src] = (fb, row.archive_id, row.sha256)
        if set(files) != {"SPY", "IVV"}:
            ses.add(
                IndexCurrentAnchor(
                    index_code="SP500",
                    as_of=None,
                    status="BLOCKED",
                    key_level="",
                    members=[],
                    spy_snapshot_id=None,
                    ivv_snapshot_id=None,
                    reconciled=0,
                    applied_events=[],
                    differences=["a holdings file could not be retrieved"],
                    notes=[],
                )
            )
            ses.commit()
            return 1
        spy = parse_spy_xlsx(files["SPY"][0])
        ivv = parse_ivv_csv(files["IVV"][0])
        snaps: dict[str, str] = {}
        for snap, url in ((spy, SPY_FILE), (ivv, IVV_FILE)):
            _, aid, sha = files[snap.source]
            ex = ses.scalars(
                select(IndexAnchorSnapshot).where(IndexAnchorSnapshot.source_sha256 == sha)
            ).first()
            if ex is None:
                ex = IndexAnchorSnapshot(
                    source=snap.source,
                    as_of=snap.as_of,
                    source_url=url,
                    archive_id=aid,
                    source_sha256=sha,
                    key_level=snap.key_level,
                    holdings=_rows(snap),
                    excluded=[list(x) for x in snap.excluded],
                    parser_version="anchor-1",
                )
                ses.add(ex)
                ses.flush()
            snaps[snap.source] = ex.snapshot_id
        # confirmed events: OFFICIAL announcements with a computable effective session (ticker level)
        events: list[AnchorEvent] = []
        seen: set[tuple[date, str | None, str | None]] = set()
        for a in ses.scalars(select(SP500Announcement)):
            try:
                eff = effective_session(Timing(a.timing), a.stated_change_date)
            except Exception:
                continue
            if eff is None:
                continue
            k = (eff, a.added_ticker or None, a.removed_ticker or None)
            if k not in seen:
                seen.add(k)
                events.append(AnchorEvent(eff, a.added_ticker or None, a.removed_ticker or None))
        res = reconcile(spy, ivv, events)
        applied = [
            f"{e.effective_session} +{e.added or '-'} -{e.removed or '-'}"
            for e in events
            if min(spy.as_of, ivv.as_of) < e.effective_session <= max(spy.as_of, ivv.as_of)
        ]
        ses.add(
            IndexCurrentAnchor(
                index_code="SP500",
                as_of=res.as_of,
                status=res.status.value,
                key_level=res.key_level,
                members=[
                    {"ticker": h.ticker, "name": h.name, "cusip": h.cusip, "sedol": h.sedol}
                    for h in res.members
                ],
                spy_snapshot_id=snaps["SPY"],
                ivv_snapshot_id=snaps["IVV"],
                reconciled=res.reconciled,
                applied_events=applied,
                differences=res.differences,
                notes=res.notes,
            )
        )
        ses.commit()
        _doc(spy, ivv, res, applied, files)
        print(
            f"{res.status} as_of={res.as_of} members={len(res.members)} reconciled={res.reconciled} differences={len(res.differences)}"
        )
    return 0


def _rows(snap: HoldingsSnapshot) -> list[dict[str, object]]:
    return [
        {
            "ticker": h.ticker,
            "name": h.name,
            "cusip": h.cusip,
            "sedol": h.sedol,
            "isin": h.isin,
            "asset_class": h.asset_class,
            "exchange": h.exchange,
            "weight": h.weight,
        }
        for h in snap.holdings
    ]


def _doc(spy: HoldingsSnapshot, ivv: HoldingsSnapshot, res, applied, files) -> None:  # type: ignore[no-untyped-def]
    L = [
        "# SP500_CURRENT_ANCHOR",
        "",
        "> Generado por `scripts/ingest_sp500_anchor.py` (ADR-0026). Procede de dos ETF, **no** de S&P DJI: nunca se etiqueta `OFFICIAL_SPDJI`.",
        "",
        f"## Estado: **{res.status}**  (as_of {res.as_of}, nivel de clave `{res.key_level}`)",
        "",
        "| fuente | fichero | as_of | equities | excluidas | sha256 |",
        "|---|---|---|---|---|---|",
    ]
    for snap in (spy, ivv):
        L.append(
            f"| {snap.source} | {'holdings-daily-us-en-spy.xlsx' if snap.source == 'SPY' else 'latest-holdings.csv'} | {snap.as_of} | {len(snap.holdings)} | {len(snap.excluded)} | `{files[snap.source][2]}` |"
        )
    L += [
        "",
        f"- Equities reconciladas security a security: **{res.reconciled}**; miembros del ancla: **{len(res.members)}**.",
        "- Los recuentos de SPY e IVV NO se exigen iguales: las líneas no-equity se eliminan por regla, no por cantidad.",
        "",
        "## Líneas excluidas (por regla)",
        "",
    ]
    for snap in (spy, ivv):
        for n, why in snap.excluded:
            L.append(f"- {snap.source}: `{n}` — {why}")
    L += ["", "## Reconciliación", ""] + [f"- {n}" for n in res.notes]
    L += [
        "",
        f"- Eventos S&P confirmados aplicados entre ambas fechas: {applied or 'ninguno'}",
        "",
        "## Diferencias",
        "",
    ]
    L += [f"- {d}" for d in res.differences] or ["- ninguna"]
    L += [
        "",
        "## Discrepancia con la descripción del propietario",
        "",
        "El CSV público de iShares (`latest-holdings.csv`) NO trae CUSIP/ISIN/SEDOL (columnas: Ticker, Name, Sector, Asset Class, Market Value, Weight, Notional Value, Quantity, Price, Location, Exchange, Currency, FX Rate, Market Currency, Accrual Date). Por eso la reconciliación IVV↔SPY es por ticker normalizado + nombre (soporte), con CUSIP sólo en el lado SPY. Las variantes `.ajax` del mismo producto devuelven la página HTML, no un CSV con identificadores.",
        "",
    ]
    Path(ROOT / "docs" / "SP500_CURRENT_ANCHOR.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
