# ruff: noqa: E501
"""Public-demo market data for the Analyzer golden path (ADR-0029): AAPL and MSFT, full EOD history.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_analyzer_demo_data.py

Source: EODHD's PUBLIC ``demo`` token (documented by the vendor; only AAPL.US / MSFT.US). It is a
VENDOR/QA tier source: bars are stored as RAW OHLCV, splits and dividends as VENDOR corporate actions
(official events keep priority: ``market.ca_resolve``). Raw payloads are archived (URL without token,
SHA-256). Idempotent. With ``PITQUANT_EODHD_API_KEY`` set the real key is used instead (any ticker).
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
from pitquant.core.timeutils import utc_now  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.models import DataQualityIssue, Security  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.market.credentials import SourceStatus  # noqa: E402
from pitquant.market.pipeline import store_batch  # noqa: E402
from pitquant.market.providers.eodhd import EODHDMarketDataProvider  # noqa: E402


class _Demo:
    def get(self) -> str:
        return "demo"

    def status(self) -> SourceStatus:
        return SourceStatus.CONFIGURED


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    prov = EODHDMarketDataProvider()
    if prov.status() is SourceStatus.SOURCE_NOT_CONFIGURED:
        prov = EODHDMarketDataProvider(credential=_Demo())  # type: ignore[arg-type]
    with make_session_factory(make_engine(s.database.url))() as ses:
        for sym, cik in (("AAPL", "0000320193"), ("MSFT", "0000789019"), ("VTI", None)):
            if cik is not None:
                sid = ses.scalars(
                    select(Security.security_id).where(Security.name == f"CIK {cik} (SEC EDGAR)")
                ).one()
            else:  # SPY is not served by the demo token: VTI is the only broad US ETF available (labelled FALLBACK proxy)
                from pitquant.db.models import TickerHistory
                from pitquant.security_master.service import SecurityMaster

                sid = (
                    ses.scalars(
                        select(TickerHistory.security_id).where(TickerHistory.ticker == sym)
                    ).first()
                    or ""
                )
                if not sid:
                    sm = SecurityMaster(ses)
                    sid = sm.register(
                        name="VANGUARD TOTAL STOCK MARKET ETF (VTI) - benchmark ETF_PROXY (fallback: SPY unavailable)",
                        exchange="XNYS",
                        currency="USD",
                        listing_start=date(2001, 6, 15),
                    ).security_id
                    sm.add_ticker(sid, sym, "XNYS", date(2001, 6, 15))
            raw = {}
            for ep in ("eod", "splits", "div"):
                body, red = prov.download(
                    ep, f"{sym}.US", **{"from": "1995-01-03", "to": utc_now().date().isoformat()}
                )
                archive_document(
                    ses,
                    store,
                    provider=f"EODHD:{ep}",
                    source_identifier=red,
                    data=body,
                    mime_type="application/json",
                    parser_version="analyzer-demo-1",
                    notes="public demo token; VENDOR tier",
                )
                raw[ep] = body
            batch = prov.normalize(sym, f"{sym}.US", raw["eod"], raw["splits"], raw["div"])
            rep = store_batch(ses, batch, key_to_security={sym: sid}, market="US")
            # vendor dividends resolve the «unknown ex-date» refusals they fully match (payment + record date)
            vend = {
                (str(r.get("paymentDate")), str(r.get("recordDate")))
                for r in json.loads(raw["div"])
            }
            n_res = 0
            for i in ses.scalars(
                select(DataQualityIssue).where(
                    DataQualityIssue.security_id == sid,
                    DataQualityIssue.check_name == "ca_unresolved_ex_date",
                    DataQualityIssue.resolved_at.is_(None),
                )
            ):
                row = i.details.get("row", {})
                if (str(i.details.get("payment_date")), str(row.get("record_date"))) in vend:
                    i.resolved_at = utc_now()
                    n_res += 1
            first = batch.bars[0].session_date if batch.bars else None
            print(
                f"{sym}: bars {len(batch.bars)} ({first}..{batch.bars[-1].session_date if batch.bars else None}), inserted {rep.bars_inserted}; actions inserted {rep.actions_inserted}; ex-date refusals resolved {n_res}; warnings {len(batch.warnings)}"
            )
        ses.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
