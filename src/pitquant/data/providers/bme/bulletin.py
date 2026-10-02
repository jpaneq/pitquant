"""BME daily bulletin (Boletín de Cotización, Renta Variable): official code <-> ISIN (ADR-0022).

One bulletin issue publishes the same set of continuous-market (MC) securities in two
sections: *prices* (``2_38``): ``MC <CODE> <SHORT NAME> F <prices>`` and *gross dividends /
capital increases* (``2_49``): ``MC <SHORT NAME> <ISIN> F <shares> ...``. The short name is
BME's own key inside ONE dated issue. The join is accepted only if both sections list EXACTLY
the same names, each name once: otherwise the issue is refused (fail closed). It proves
«code C was assigned to ISIN I on the bulletin's session date», for every listed security.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pitquant.core.errors import DataQualityError

PARSER_VERSION = "bme-bulletin-1"
BASE = "https://www.bolsasymercados.es/descargas/boletines/barcelona/{y}/{m}/{d}/{sec}_{ymd}.pdf"
SEC_PRICES, SEC_ISIN = "2_38_0", "2_49_0"
_PRICES = re.compile(r"MC ([A-Z0-9.]+) (\S+) F ")
_ISIN = re.compile(r"MC (\S+) ([A-Z]{2}[A-Z0-9]{9}\d) F ")


@dataclass(frozen=True)
class BulletinLink:
    code: str
    name: str
    isin: str


def bulletin_urls(ymd: str) -> tuple[str, str]:
    y, m, d = ymd[:4], ymd[4:6], ymd[6:]
    return (
        BASE.format(y=y, m=m, d=d, sec=SEC_PRICES, ymd=ymd),
        BASE.format(y=y, m=m, d=d, sec=SEC_ISIN, ymd=ymd),
    )


def pdf_text(data: bytes) -> str:
    import pdfplumber

    if data[:5] != b"%PDF-":
        raise DataQualityError("bulletin is not a PDF")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in pdf.pages))


def join_bulletin(prices_text: str, isin_text: str, min_matched: float = 0.9) -> list[BulletinLink]:
    """Join the two sections of ONE issue by BME's short name: an EXACT name wins; otherwise a
    name that is a prefix of exactly one other (the ISIN section abbreviates long names) and
    claimed by exactly one. Anything ambiguous is skipped (never guessed). The issue is refused
    if a name repeats inside a section or fewer than ``min_matched`` of the ISIN rows match."""
    codes = _PRICES.findall(prices_text)
    isins = _ISIN.findall(isin_text)
    if not codes or not isins:
        raise DataQualityError("bulletin layout not recognised (no MC rows)")
    names_c = [n for _, n in codes]
    names_i = [n for n, _ in isins]
    if len(set(names_c)) != len(names_c) or len(set(names_i)) != len(names_i):
        raise DataQualityError("bulletin: a short name appears twice in a section")
    code_of = {n: c for c, n in codes}
    claimed: dict[str, list[str]] = {}
    pick: dict[str, str] = {}
    for b, _isin in isins:
        if b in code_of:
            pick[b] = b
            continue
        cands = [a for a in names_c if a.startswith(b) or b.startswith(a)]
        if len(cands) == 1:
            pick[b] = cands[0]
            claimed.setdefault(cands[0], []).append(b)
    # a prefix match claimed by two ISIN rows (or also matched exactly elsewhere) is ambiguous
    exact_targets = {a for b, a in pick.items() if a == b}
    out: list[BulletinLink] = []
    for b, isin in isins:
        a = pick.get(b)
        if a is None:
            continue
        if a != b and (len(claimed.get(a, [])) != 1 or a in exact_targets):
            continue
        out.append(BulletinLink(code_of[a], a, isin))
    if len(out) < min_matched * len(isins):
        raise DataQualityError(f"bulletin: only {len(out)}/{len(isins)} ISIN rows matched")
    codes_out = [x.code for x in out]
    if len(set(codes_out)) != len(codes_out):
        raise DataQualityError("bulletin: a code matched two ISIN rows")
    return out
