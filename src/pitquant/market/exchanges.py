# ruff: noqa: E501
"""Yahoo-style exchange suffix → (exchange calendar, default currency, ``store_batch`` market tag), shared by provider, ingestion and routine (ADR-0045).

``""`` is a US listing. London prices are quoted in pence (Yahoo currency ``GBp``): the bar keeps the vendor string; returns and ratios are unaffected.
"""

from __future__ import annotations

SUFFIX: dict[str, tuple[str, str, str]] = {
    "": ("XNYS", "USD", "US"),
    "US": ("XNYS", "USD", "US"),
    "MC": ("XMAD", "EUR", "ES"),
    "AS": ("XAMS", "EUR", "EU"),
    "SW": ("XSWX", "CHF", "EU"),
    "DE": ("XETR", "EUR", "EU"),
    "L": ("XLON", "GBP", "EU"),
    "PA": ("XPAR", "EUR", "EU"),
    "MI": ("XMIL", "EUR", "EU"),
    "ST": ("XSTO", "SEK", "EU"),
    "CO": ("XCSE", "DKK", "EU"),
    "BR": ("XBRU", "EUR", "EU"),
    "HE": ("XHEL", "EUR", "EU"),
    "T": ("XTKS", "JPY", "ASIA"),
    "HK": ("XHKG", "HKD", "ASIA"),
    "AX": ("XASX", "AUD", "ASIA"),
    "TO": ("XTSE", "CAD", "NA"),
}


def suffix_of(symbol: str) -> str:
    return symbol.rsplit(".", 1)[-1].upper() if "." in symbol else ""


def calendar_of(symbol: str) -> str:
    try:
        return SUFFIX[suffix_of(symbol)][0]
    except KeyError:
        raise KeyError(f"exchange suffix of {symbol!r} has no calendar mapping") from None
