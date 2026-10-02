# ruff: noqa: E501
"""Real market data + official corporate actions, with full traceability (ADR-0023).

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_real_market_ca.py

* Alpha Vantage TIME_SERIES_DAILY (AAPL, MSFT, compact = last ~100 sessions) ONLY if
  ``PITQUANT_ALPHAVANTAGE_API_KEY`` is set; otherwise BLOCKED_BY_CREDENTIAL (nothing invented).
* EODHD public ``demo`` token (AAPL.US / MSFT.US only): QA series around the real events.
* Official CA pages: Apple IR (Wayback capture; the live page answers 403 to scripts), Enagás IR,
  Microsoft IR. BME daily bulletins (4 single sessions) for raw Enagás closes.
Everything is archived (URL without keys, retrieved_at, SHA-256) before it is parsed. Idempotent.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.errors import DataQualityError  # noqa: E402
from pitquant.core.timeutils import utc_now  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.providers.bme.bulletin import bulletin_urls, pdf_text  # noqa: E402
from pitquant.data.providers.bme.prices import parse_bulletin_price  # noqa: E402
from pitquant.db.models import DataQualityIssue, Issuer, Security  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.market import official_ca as oca  # noqa: E402
from pitquant.market.credentials import SourceStatus, redact  # noqa: E402
from pitquant.market.normalized import NormalizedBatch  # noqa: E402
from pitquant.market.pipeline import record_ca_ingestion, store_batch  # noqa: E402
from pitquant.market.providers.alphavantage_daily import AlphaVantageDailyProvider  # noqa: E402
from pitquant.market.providers.eodhd import EODHDMarketDataProvider  # noqa: E402

UA = "Mozilla/5.0 (compatible; PITQuant research)"
APPLE_WAYBACK_TS = "20260422063456"
APPLE_URL = "https://investor.apple.com/dividend-history/"
ENAGAS_URL = "https://www.enagas.es/en/investor-relations/share-performance/dividends/"
MSFT_URL = "https://www.microsoft.com/en-us/Investor/dividends-and-stock-history.aspx"
BULLETIN_DAYS = ("20231219", "20231220", "20240701", "20240702")  # around two Enagás ex-dates
EODHD_WINDOWS = {"AAPL": ("2020-06-01", "2020-12-31"), "MSFT": ("2004-10-01", "2004-12-31")}


class _Demo:
    """EODHD's PUBLIC demo token (documented by the vendor; not a secret)."""

    def get(self) -> str:
        return "demo"

    def status(self) -> SourceStatus:
        return SourceStatus.CONFIGURED


def get(url: str, compressed: bool = False) -> bytes:
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"} if compressed else {"User-Agent": UA}
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
        body: bytes = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip

            body = gzip.decompress(body)
    return body


def _record_unresolved(ses, sid, prov, sha, rows) -> None:  # type: ignore[no-untyped-def]
    """Dividends without a published ex-date become DQ issues: a total-return window they may
    fall into is refused (``PITContext.total_return``), never silently computed without them."""
    for r in rows:
        if r.get("kind") != "CASH_DIVIDEND" or not r.get("payment_date"):
            continue
        pay = r["payment_date"]
        pay_d = (
            date.fromisoformat(pay)
            if "-" in pay
            else date(int(pay[6:]), int(pay[3:5]), int(pay[:2]))
        )
        frm = r.get("announcement_date") or str(date(pay_d.year - 1, pay_d.month, pay_d.day))
        key = {"provider": prov, "payment_date": str(pay_d), "source_hash": sha}
        dup = [
            i
            for i in ses.scalars(
                select(DataQualityIssue).where(
                    DataQualityIssue.security_id == sid,
                    DataQualityIssue.check_name == "ca_unresolved_ex_date",
                )
            )
            if i.details.get("provider") == prov
            and i.details.get("payment_date") == str(pay_d)
            and i.details.get("source_hash") == sha
        ]
        if dup:
            continue
        ses.add(DataQualityIssue(entity="corporate_action_events", security_id=sid,
            check_name="ca_unresolved_ex_date", severity="medium",
            details={**key, "window_from": frm, "window_to": str(pay_d), "reason": r["reason"], "row": r}))  # fmt: skip


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    report: dict[str, object] = {}
    with make_session_factory(make_engine(s.database.url))() as ses:

        def archive(
            provider: str, ident: str, data: bytes, mime: str, notes: str
        ) -> tuple[str, str]:
            row = archive_document(
                ses, store, provider=provider, source_identifier=ident, data=data,
                mime_type=mime, parser_version=provider, notes=notes,
            )  # fmt: skip
            return row.archive_id, row.sha256

        def sec_by_name(name: str) -> str:
            return ses.scalars(select(Security.security_id).where(Security.name == name)).one()

        aapl = sec_by_name("CIK 0000320193 (SEC EDGAR)")
        msft = sec_by_name("CIK 0000789019 (SEC EDGAR)")
        eng = ses.scalars(
            select(Security.security_id)
            .join(Issuer, Issuer.issuer_id == Security.issuer_id)
            .where(Issuer.name == "ENAGAS, S.A.")
        ).one()
        ids = {"AAPL": aapl, "MSFT": msft, "ENG": eng}

        # ---------------------------------------------------------- Alpha Vantage (free key)
        av = AlphaVantageDailyProvider()
        if av.status() is SourceStatus.SOURCE_NOT_CONFIGURED:
            report["alphavantage"] = "BLOCKED_BY_CREDENTIAL (PITQUANT_ALPHAVANTAGE_API_KEY not set)"
        else:
            for sym in ("AAPL", "MSFT"):
                body, red = av.download(sym, "compact")
                aid, sha = archive(
                    "ALPHAVANTAGE:TIME_SERIES_DAILY",
                    red,
                    body,
                    "application/json",
                    "outputsize=compact",
                )
                batch = av.normalize(sym, body)
                rep = store_batch(ses, batch, key_to_security={sym: ids[sym]}, market="US")
                report[f"alphavantage_{sym}"] = {"sha256": sha, "bars": len(batch.bars),
                    "inserted": rep.bars_inserted, "warnings": batch.warnings}  # fmt: skip

        # ------------------------------------------------------------- EODHD demo (QA only)
        vendor_div: dict[str, tuple[bytes, str]] = {}
        eod = EODHDMarketDataProvider(credential=_Demo())  # type: ignore[arg-type]
        for sym, (a, b) in EODHD_WINDOWS.items():
            sym_e = f"{sym}.US"
            raw = {}
            for ep in ("eod", "splits", "div"):
                body, red = eod.download(ep, sym_e, **{"from": a, "to": b})
                aid, sha = archive(f"EODHD:{ep}", red, body, "application/json", "demo token; QA")
                raw[ep] = body
                if ep == "div":
                    vendor_div[sym] = (body, sha)
            batch = eod.normalize(sym, sym_e, raw["eod"], raw["splits"], raw["div"])
            vendor_actions = [
                (x.kind.value, str(x.anchor_date), x.ratio, x.cash_amount) for x in batch.actions
            ]
            batch.actions.clear()  # vendor events are QA: the official page is the source
            rep = store_batch(ses, batch, key_to_security={sym: ids[sym]}, market="US")
            report[f"eodhd_{sym}"] = {"bars": len(batch.bars), "inserted": rep.bars_inserted,
                "vendor_actions_qa": vendor_actions}  # fmt: skip

        # ------------------------------------------------- official corporate-action pages
        pages = {
            "APPLE": (
                oca.APPLE,
                f"http://web.archive.org/web/{APPLE_WAYBACK_TS}id_/{APPLE_URL}",
                f"original_url={APPLE_URL}; wayback_ts={APPLE_WAYBACK_TS}; live page 403 to scripts",
                lambda d: oca.parse_apple(d, "AAPL"),
                aapl,
            ),
            "ENAGAS": (oca.ENAGAS, ENAGAS_URL, "official issuer page", lambda d: oca.parse_enagas(d, "ENG"), eng),
            "MICROSOFT": (oca.MICROSOFT, MSFT_URL, "official issuer page", lambda d: oca.parse_microsoft(d, "MSFT"), msft),
        }  # fmt: skip
        for name, (prov, url, notes, parse, sid) in pages.items():
            data = get(url, compressed=True)
            aid, sha = archive(prov, url, data, "text/html", notes)
            parsed = parse(data)
            sk = {"APPLE": "AAPL", "ENAGAS": "ENG", "MICROSOFT": "MSFT"}[name]
            batch = NormalizedBatch()
            batch.actions = [
                replace(a, provenance=replace(a.provenance, archive_id=aid)) for a in parsed.actions
            ]
            if (
                name == "APPLE"
            ):  # ex-date from a structured source, only on a full date+amount match
                extra, parsed.unresolved = oca.merge_vendor_ex_dates(
                    parsed.unresolved,
                    *vendor_div["AAPL"],
                    sha,
                    "AAPL",
                    "XNYS",
                    "APPLE_IR+EODHD_EXDATE",
                )
                batch.actions += [
                    replace(a, provenance=replace(a.provenance, archive_id=aid)) for a in extra
                ]
                parsed.actions += extra
                for a in extra:
                    for i in ses.scalars(
                        select(DataQualityIssue).where(
                            DataQualityIssue.security_id == sid,
                            DataQualityIssue.check_name == "ca_unresolved_ex_date",
                            DataQualityIssue.resolved_at.is_(None),
                        )
                    ):
                        if i.details.get("payment_date") == str(a.payment_date):
                            i.resolved_at = utc_now()
            rep = store_batch(
                ses, batch, key_to_security={sk: sid}, market="ES" if sk == "ENG" else "US"
            )
            dates = [a.anchor_date for a in parsed.actions if a.anchor_date]
            report[name] = {"sha256": sha, "actions": len(parsed.actions), "inserted": rep.actions_inserted,
                "unresolved": len(parsed.unresolved),
                "first_anchor": str(min(dates)) if dates else None, "rejected": rep.rejected}  # fmt: skip
            # coverage trace: Apple dividends carry no ex-date -> the ingestion is NOT complete
            if name == "APPLE":
                complete, start, why = (
                    False,
                    date(2011, 1, 1),
                    "dividends without ex_date (unresolved)",
                )
            elif name == "ENAGAS":
                complete, start = True, min(dates)
                why = "cash dividends only (no splits/capital increases); ex-dates only from 2016-06-30"
            else:
                complete, start, why = False, date(2003, 2, 19), "page lists only 2003-2004 rows"
            record_ca_ingestion(ses, security_id=sid, provider=prov, period_start=start,
                period_end=utc_now().date(), completed=complete, events_found=len(parsed.actions),
                source_hash=sha, detail=why)  # fmt: skip
            _record_unresolved(ses, sid, prov, sha, parsed.unresolved)
            report[name]["unresolved_rows"] = len(parsed.unresolved)  # type: ignore[index]

        # ------------------------------------------------------ BME bulletins: raw ENG closes
        bars = []
        for ymd in BULLETIN_DAYS:
            u38, _ = bulletin_urls(ymd)
            data = get(u38)
            aid, sha = archive("BME_BOLETIN_DIARIO", u38, data, "application/pdf", f"session={ymd}")
            d = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
            bar, _prev = parse_bulletin_price(pdf_text(data), data, "ENG", d, "ENG")
            bars.append(replace(bar, provenance=replace(bar.provenance, archive_id=aid)))
        batch = NormalizedBatch()
        batch.bars = bars
        rep = store_batch(ses, batch, key_to_security={"ENG": eng}, market="ES")
        report["BME_ENG_bars"] = {"inserted": rep.bars_inserted, "rejected": rep.rejected}
        ses.commit()
    print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DataQualityError as e:
        print(f"REFUSED: {redact(str(e))}")
        raise SystemExit(2) from e
