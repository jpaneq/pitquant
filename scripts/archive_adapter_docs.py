# ruff: noqa: E501  (regexes quote official text verbatim)
"""Archive the OFFICIAL documentation pages the vendor adapters are built on and record, per
adapter field, the exact sentence that justifies its interpretation (or UNVERIFIED).

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/archive_adapter_docs.py

Each page goes through raw_source_archive (URL, retrieved_at, SHA-256, parser version).
Output: docs/ADAPTER_FIELD_EVIDENCE.md (generated; do not edit by hand). Network: 6 pages.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

PARSER = "adapter-docs-1"
UA = "Mozilla/5.0 (compatible; PITQuant research)"
PAGES = {
    "SHARADAR:stocks": "https://sharadar.com/docs/stocks",
    "SHARADAR:actions": "https://sharadar.com/docs/actions",
    "SHARADAR:tickers": "https://sharadar.com/docs/tickers",
    "SHARADAR:sp500": "https://sharadar.com/docs/sp500",
    "EODHD:eod": "https://eodhd.com/financial-apis/api-for-historical-data-and-volumes",
    "EODHD:div_splits": "https://eodhd.com/financial-apis/api-splits-dividends",
}
# (page, adapter field, what the adapter does with it, regex that must match official text)
FIELDS = [
    (
        "SHARADAR:stocks",
        "SEP.open/high/low/close",
        "SPLIT-adjusted; raw = closeunadj",
        r"Close Price - Split Adjusted",
    ),
    ("SHARADAR:stocks", "SEP.closeunadj", "RAW close (base series)", r"Close Price - Unadjusted"),
    (
        "SHARADAR:stocks",
        "SEP.closeadj",
        "QA only (vendor adjusted)",
        r"Close Price - Adjusted for Splits,? Dividends,? and Spinoffs",
    ),
    (
        "SHARADAR:stocks",
        "SEP.volume",
        "split-adjusted; de-adjusted with closeunadj/close",
        r"Volume - Split Adjusted",
    ),
    ("SHARADAR:stocks", "SEP.lastupdated", "vendor_last_updated (QA)", r"Last Updated Date"),
    (
        "SHARADAR:stocks",
        "pagination limit",
        "default 10000: a full page may be truncated",
        r"limit The number of records to return\. 10000",
    ),
    (
        "SHARADAR:stocks",
        "pagination offset",
        "skip, alias offset",
        r"skip The number of results to skip before returning data\. Alias: offset",
    ),
    (
        "SHARADAR:actions",
        "ACTIONS.dividend value basis (split-adjusted?)",
        "kept as value_basis=UNVERIFIED",
        r"dividend[^.]{0,80}(split[- ]adjusted|adjusted for)",
    ),
    (
        "SHARADAR:actions",
        "ACTIONS.date semantics (ex vs effective)",
        "treated as the action date",
        r"[^.]{0,80}\bex-?(dividend )?date\b[^.]{0,80}",
    ),
    (
        "SHARADAR:actions",
        "ACTIONS.tickerchangefrom/to direction",
        "pairing check only",
        r"tickerchange(from|to)[^.]{0,120}",
    ),
    (
        "SHARADAR:actions",
        "ACTIONS.acquisition counterpart",
        "contraticker = acquirer; no consideration type, so MERGER + delisting ACQUIRED",
        r"delisted as a result of an acquisition will specify the aquiring company in the contraticker",
    ),
    (
        "SHARADAR:actions",
        "ACTIONS.spinoff value meaning",
        "value kept as vendor ratio; valuation needed for total return",
        r"spinoff(dividend)?[^.]{0,40}\bvalue\b[^.]{0,120}",
    ),
    (
        "SHARADAR:tickers",
        "TICKERS.permaticker",
        "permanent id of a share class",
        r"permaticker, a unique and unchanging identifier for a security \(share class\)",
    ),
    (
        "SHARADAR:tickers",
        "TICKERS.ticker reuse",
        "never an identity: resolved by date",
        r"[^.]{0,100}\bre-?used?\b[^.]{0,100}",
    ),
    (
        "SHARADAR:tickers",
        "TICKERS.first/lastpricedate",
        "life window for (ticker, date)",
        r"First Price Date",
    ),
    (
        "SHARADAR:sp500",
        "SP500.date semantics",
        "EFFECTIVE date of the change",
        r"effective date of the change",
    ),
    (
        "SHARADAR:sp500",
        "SP500.historical rows",
        "historical QUARTERLY snapshots (checked vs events)",
        r"historical quarterly snapshots of the index constituents",
    ),
    (
        "SHARADAR:sp500",
        "SP500.contraticker",
        "counterpart of an add/remove",
        r"Contra Ticker Symbol contraticker",
    ),
    ("EODHD:eod", "eod.open/high/low/close", "RAW as traded", r"close number[^.]{0,60}as traded"),
    (
        "EODHD:eod",
        "eod.adjusted_close",
        "QA only",
        r"adjusted_close number Closing price adjusted for both splits and dividends",
    ),
    (
        "EODHD:eod",
        "eod.volume",
        "adjusted for splits only; de-adjusted",
        r"volume integer Traded volume, adjusted for splits",
    ),
    (
        "EODHD:eod",
        "renamed symbols",
        "a ticker is not an identity",
        r"A renamed ticker does not[^.]{0,120}",
    ),
    ("EODHD:div_splits", "div.date", "ex-dividend date", r"Ex-dividend date[^.]{0,80}"),
    (
        "EODHD:div_splits",
        "div.unadjustedValue",
        "actual payout (used as amount)",
        r"unadjustedValue number The amount actually paid",
    ),
    (
        "EODHD:div_splits",
        "div.value",
        "split-adjusted (QA only)",
        r"Split-adjusted amount per share",
    ),
    (
        "EODHD:div_splits",
        "div.declaration/record/payment dates",
        "announcement/record/payment",
        r"declarationDate[^.]{0,200}",
    ),
    ("EODHD:div_splits", "splits.split", "'new/old' ratio", r"\"split\": \"\d\.\d+/\d\.\d+\""),
]


def text_of(body: bytes) -> str:
    s = body.decode("utf-8", errors="replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s)


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    texts: dict[str, str] = {}
    meta: dict[str, tuple[str, str, str]] = {}
    with make_session_factory(make_engine(s.database.url))() as ses:
        for key, url in PAGES.items():
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
                lm = r.headers.get("Last-Modified") or "not stated"
            row = archive_document(
                ses,
                store,
                provider="VENDOR_DOCS",
                source_identifier=url,
                data=body,
                mime_type="text/html",
                parser_version=PARSER,
                notes=f"source_type=adapter_documentation; page={key}; Last-Modified: {lm}",
            )
            texts[key] = text_of(body)
            meta[key] = (url, row.sha256, row.retrieved_at.isoformat())
            time.sleep(1.0)
        ses.commit()
    L = [
        "# Evidencia documental de los adapters (generado)",
        "",
        "Generado con `scripts/archive_adapter_docs.py`. Cada página oficial está en "
        "`raw_source_archive` (proveedor `VENDOR_DOCS`). Para cada campo que el adapter "
        "interpreta, se cita la frase oficial que lo justifica; si la página no la contiene, "
        "el campo es **UNVERIFIED** y el adapter lo marca así.",
        "",
        "## Páginas archivadas",
        "",
        "| Página | URL | retrieved_at | SHA-256 |",
        "|---|---|---|---|",
        *(f"| {k} | {u} | {t} | `{h}` |" for k, (u, h, t) in meta.items()),
        "",
        "## Campos",
        "",
        "| Campo | Uso en el adapter | Estado | Frase oficial |",
        "|---|---|---|---|",
    ]
    for page, field, use, rx in FIELDS:
        m = re.search(rx, texts[page], flags=re.I)
        if m:
            ex = m.group(0).strip()[:220].replace("|", "\\|")
            L.append(f"| {field} | {use} | VERIFIED | «{ex}» ({page}) |")
        else:
            L.append(f"| {field} | {use} | **UNVERIFIED** | no aparece en {page} |")
    (ROOT / "docs" / "ADAPTER_FIELD_EVIDENCE.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[-len(FIELDS) - 1 :]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
