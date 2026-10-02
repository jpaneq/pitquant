"""Raw ES daily prices from the OFFICIAL BME daily bulletin (section 2_38_0), ADR-0023.

Row: ``MC <CODE> <NAME> F <prev_close> <prev_date dd-mm-yy> <max> <min> <close> <vwap> <volume>
<effective>``. The bulletin has NO open, so ``open`` stays ``None`` (never imputed). Evidence
for single sessions; NOT a bulk historical price feed (licence/coverage not reviewed).
"""

from __future__ import annotations

import re
from datetime import date

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.normalized import MarketBar, Provenance, SourceTier

PROVIDER = "BME:boletin-diario:2_38_0"
PARSER_VERSION = "bme-bulletin-prices-1"
_NUM = r"(\d[\d.]*,\d+)"


def _n(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse_bulletin_price(
    pdf_text: str, raw: bytes, code: str, session: date, security_key: str
) -> tuple[MarketBar, float]:
    """(bar for ``session``, previous close as printed). Cross-checked: the printed previous
    session date must be the calendar's previous session."""
    m = re.search(
        rf"MC {re.escape(code)} (\S+) F {_NUM} (\d{{2}})-(\d{{2}})-(\d{{2}}) {_NUM} {_NUM} {_NUM} "
        rf"{_NUM} (\d[\d.]*)",
        pdf_text,
    )
    if m is None:
        raise DataQualityError(f"bulletin {session}: no price row for {code}")
    prev, dd, mm, yy, hi, lo, close, _vwap, vol = m.groups()[1:]
    prev_date = date(2000 + int(yy), int(mm), int(dd))
    cal = get_calendar("XMAD")
    if cal.previous_session(session) != prev_date:
        raise DataQualityError(f"bulletin {session}: previous date {prev_date} unexpected")
    bar = MarketBar(
        security_key,
        session,
        None,
        _n(hi),
        _n(lo),
        _n(close),
        float(vol.replace(".", "")),
        "EUR",
        cal.session_close(session),
        Provenance(
            PROVIDER, SourceTier.OFFICIAL, f"{code}:{session}", sha256_hex(raw), PARSER_VERSION
        ),
    )
    return bar, _n(prev)
