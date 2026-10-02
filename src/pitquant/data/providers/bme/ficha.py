"""Parser of the legacy official «Bolsa de Madrid — Ficha de valor» page (ADR-0022).

The page states, in its own HTML, ``ISIN``, ``Ticker`` (the BME exchange code, e.g. MTS) and
``Mercado`` for ONE security, plus the render timestamp of the page. It is a DATED official
statement «code C ↔ ISIN I on day D» (the day D is the page's own stamp, never the date we
downloaded it). Layout changes fail closed.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date

from pitquant.core.errors import DataQualityError

PARSER_VERSION = "bme-ficha-legacy-1"
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


@dataclass(frozen=True)
class FichaEvidence:
    isin: str
    code: str
    issuer_name: str
    market: str
    page_date: date  # the date the page states about itself (render stamp)
    last_price_date: date | None  # date of the latest price row; None = no prices shown

    def is_live_listing(self, max_gap_days: int = 7) -> bool:
        """The security was TRADING when the page was rendered: the latest price is at most
        ``max_gap_days`` before the render stamp. A page of an excluded/cancelled security can
        still be served with a current stamp and stale prices; that is not a presence claim."""
        return (
            self.last_price_date is not None
            and 0 <= (self.page_date - self.last_price_date).days <= max_gap_days
        )


def _cell(s: str, pattern: str) -> str | None:
    m = re.search(pattern, s, flags=re.S)
    return html.unescape(m.group(1)).replace("\xa0", " ").strip() if m else None


def parse_ficha(page: bytes) -> FichaEvidence:
    s = page.decode("utf-8", errors="replace")
    title = _cell(s, r"<title>\s*Bolsa de Madrid - Ficha de (.*?)\s*</title>")
    isin = _cell(s, r'<td class="etq">ISIN</td>\s*<td>(.*?)</td>')
    code = _cell(s, r'id="ctl00_Contenido_TickerDat">(.*?)</td>')
    market = _cell(s, r'id="ctl00_Contenido_MercadoDat"[^>]*>(.*?)</td>')
    stamp = re.findall(
        r"font-size: 9px; color: #999999; text-align: right;\">\s*"
        r"(\d{2})/(\d{2})/(\d{4})\s+\d{1,2}:\d{2}:\d{2}\s*</div>",
        s,
    )
    if not (title and isin and code and market and stamp):
        raise DataQualityError("BME legacy ficha layout not recognised (missing fields)")
    if not _ISIN.match(isin):
        raise DataQualityError(f"BME ficha: malformed ISIN {isin!r}")
    d, m, y = stamp[-1]
    lp = re.search(r'tblPrecios.*?<td align="center">(\d{2})/(\d{2})/(\d{4})</td>', s, flags=re.S)
    last = date(int(lp.group(3)), int(lp.group(2)), int(lp.group(1))) if lp else None
    return FichaEvidence(isin, code, title, market, date(int(y), int(m), int(d)), last)
