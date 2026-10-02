"""Parsers for OFFICIAL investor-relations corporate-action tables (ADR-0023).

Each page publishes a different subset of dates; ONLY what the page states is mapped:

* Apple IR «Dividend History»: declared / record / payable / amount / type. NO ex-date → a
  dividend without ex-date is returned in ``unresolved`` (it cannot enter the total-return
  engine); a split row's «first date shares trade split-adjusted» is ``effective_date``.
* Enagás «Dividends»: payment / gross / net / type / fiscal year / ex-dividend date (no
  announcement date → ``available_at`` is the ex-date close, conservative).
* Microsoft IR «Dividends and Stock History»: amount / announcement / ex / record / payable.

Parsers are pure (bytes in, records out); archiving and storage live in the ingestion script.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import sha256_hex
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.normalized import CorporateAction, CorporateActionKind, Provenance, SourceTier

_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}
_EN_DATE = r"([A-Z][a-z]{2,8}) (\d{1,2}) ?, ?(\d{4})"


def en_date(month: str, day: str, year: str) -> date:
    m = _MONTHS.get(month[:3].lower())
    if m is None:
        raise DataQualityError(f"unknown month {month!r}")
    return date(int(year), m, int(day))


def page_text(data: bytes) -> str:
    s = data.decode("utf-8", errors="replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


@dataclass
class ParsedActions:
    actions: list[CorporateAction] = field(default_factory=list)
    unresolved: list[dict[str, str]] = field(default_factory=list)  # rows we cannot normalize


def _known_at(exchange: str, d: date) -> datetime:
    cal = get_calendar(exchange)
    return cal.session_close(cal.session_on_or_after(d))


def _outside(exchange: str, d: date) -> bool:
    """Before the calendar's coverage the event is reported, never silently dropped."""
    return d < get_calendar(exchange).first_session


def _prov(provider: str, raw_id: str, sha: str, parser: str) -> Provenance:
    return Provenance(provider, SourceTier.OFFICIAL, raw_id, sha, parser)


# ------------------------------------------------------------------------------- Apple
APPLE = "APPLE_IR:dividend-history"
_APPLE_ROW = re.compile(
    rf"{_EN_DATE} {_EN_DATE} {_EN_DATE}(\*?) (\$?\s?[\d.]+|N/A) "
    r"(Regular Cash|\d+-for-\d+ Stock Split)"
)


def parse_apple(data: bytes, security_key: str, min_rows: int = 20) -> ParsedActions:
    sha, text = sha256_hex(data), page_text(data)
    if "Dividend History" not in text or "Declared Record Payable Amount Type" not in text:
        raise DataQualityError("Apple IR: layout not recognised")
    out = ParsedActions()
    rows = list(_APPLE_ROW.finditer(text))
    if len(rows) < min_rows:
        raise DataQualityError(f"Apple IR: only {len(rows)} rows parsed")
    for m in rows:
        g = m.groups()
        declared = en_date(*g[0:3])
        record = en_date(*g[3:6])
        third = en_date(*g[6:9])  # payable (cash) | first split-adjusted trading day (split)
        star, amount, kind = g[9], g[10], g[11]
        if _outside("XNYS", declared):
            out.unresolved.append(
                {
                    "kind": kind,
                    "reason": "before calendar coverage",
                    "announcement_date": str(declared),
                }
            )
            continue
        prov = _prov(APPLE, f"{declared}:{kind}", sha, "apple-ir-1")
        if "Split" in kind:
            if not star:
                raise DataQualityError(f"Apple split {declared}: no «first adjusted date» mark")
            new, old = (int(x) for x in kind.split(" ")[0].split("-for-"))
            out.actions.append(
                CorporateAction(
                    security_key,
                    CorporateActionKind.SPLIT if new > old else CorporateActionKind.REVERSE_SPLIT,
                    _known_at("XNYS", declared),
                    prov,
                    announcement_date=declared,
                    record_date=record,
                    effective_date=third,
                    ratio=new / old,
                    details={"third_column": "first date shares trade split-adjusted"},
                )
            )
        else:
            out.unresolved.append(
                {
                    "kind": "CASH_DIVIDEND",
                    "reason": "ex_date not published by Apple IR",
                    "announcement_date": str(declared),
                    "record_date": str(record),
                    "payment_date": str(third),
                    "cash_amount": amount.replace("$", "").strip(),
                }
            )
    return out


# ----------------------------------------------------------------------------- Enagás
ENAGAS = "ENAGAS_IR:dividends"
_TR = re.compile(r"<tr>(.*?)</tr>", re.S)
_TD = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)


def _es_date(s: str) -> date | None:
    s = s.replace("\xa0", " ").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
    if not m:
        raise DataQualityError(f"Enagás date {s!r}")
    return date(int(m[3]), int(m[2]), int(m[1]))


def _num(s: str) -> float:
    return float(s.replace("\xa0", "").strip().replace(",", "."))


def parse_enagas(data: bytes, security_key: str) -> ParsedActions:
    sha = sha256_hex(data)
    s = data.decode("utf-8", errors="replace")
    out = ParsedActions()
    header_ok = False
    for tr in _TR.findall(s):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
            for c in _TD.findall(tr)
        ]
        if cells[:1] == ["Payment date"]:
            if cells != [
                "Payment date",
                "Gross Payment (€/share)",
                "Net Payment (€/share)",
                "Type",
                "For",
                "Ex dividend date",
            ]:
                raise DataQualityError(f"Enagás table header changed: {cells}")
            header_ok = True
            continue
        if not header_ok or len(cells) != 6:
            continue
        pay, gross, net, typ, fy, ex = cells
        pay_d, ex_d = _es_date(pay), _es_date(ex)
        if ex_d is None or pay_d is None:
            out.unresolved.append(
                {"kind": "CASH_DIVIDEND", "reason": "no ex-date", "payment_date": pay, "for": fy}
            )
            continue
        if ex_d >= pay_d:
            raise DataQualityError(f"Enagás {pay}: ex-date {ex_d} not before payment")
        out.actions.append(
            CorporateAction(
                security_key,
                CorporateActionKind.CASH_DIVIDEND,
                _known_at("XMAD", ex_d),
                _prov(ENAGAS, f"{pay_d}:{typ}:{fy}", sha, "enagas-ir-1"),
                ex_date=ex_d,
                payment_date=pay_d,
                cash_amount=_num(gross),
                currency="EUR",
                details={"type": typ, "for": fy, "net_per_share": _num(net), "gross": True},
            )
        )
    if not header_ok or not out.actions:
        raise DataQualityError("Enagás: dividend table not found")
    return out


# --------------------------------------------------------------------------- Microsoft
MICROSOFT = "MICROSOFT_IR:dividends"
_MS_ROW = re.compile(rf"(\d{{4}}|Special) \$([\d.]+) {_EN_DATE} {_EN_DATE} {_EN_DATE} {_EN_DATE}")


def parse_microsoft(data: bytes, security_key: str) -> ParsedActions:
    sha, text = sha256_hex(data), page_text(data)
    out = ParsedActions()
    for m in _MS_ROW.finditer(text):
        g = m.groups()
        ann, ex, rec, pay = (en_date(*g[i : i + 3]) for i in (2, 5, 8, 11))
        if not ann <= ex <= pay:
            raise DataQualityError(f"Microsoft row {g[0]}: dates out of order")
        out.actions.append(
            CorporateAction(
                security_key,
                CorporateActionKind.SPECIAL_DIVIDEND
                if g[0] == "Special"
                else CorporateActionKind.CASH_DIVIDEND,
                _known_at("XNYS", ann),
                _prov(MICROSOFT, f"{g[0]}:{ex}", sha, "microsoft-ir-1"),
                announcement_date=ann,
                ex_date=ex,
                record_date=rec,
                payment_date=pay,
                cash_amount=float(g[1]),
                currency="USD",
                details={"period": g[0]},
            )
        )
    if not out.actions:
        raise DataQualityError("Microsoft IR: no dividend rows found")
    return out


# ------------------------------------------------- ex-date from a structured source
def merge_vendor_ex_dates(
    unresolved: list[dict[str, str]],
    vendor_div_json: bytes,
    vendor_sha: str,
    official_sha: str,
    security_key: str,
    exchange: str,
    provider: str,
) -> tuple[list[CorporateAction], list[dict[str, str]]]:
    """Dividends whose OFFICIAL row has no ex-date get it from a structured vendor payload, only
    when declaration, record and payment dates AND the paid amount all match the official row.
    The result is tier VENDOR (its weakest field) and records the origin of every date; rows that
    do not match stay unresolved (never guessed)."""
    import json

    vendor = json.loads(vendor_div_json)
    if not isinstance(vendor, list):
        raise DataQualityError("vendor dividends: expected a JSON array")
    actions: list[CorporateAction] = []
    left: list[dict[str, str]] = []
    for r in unresolved:
        hit = None
        if r.get("kind") == "CASH_DIVIDEND" and r.get("payment_date"):
            for v in vendor:
                try:
                    same = (
                        str(v.get("declarationDate")) == r["announcement_date"]
                        and str(v.get("recordDate")) == r["record_date"]
                        and str(v.get("paymentDate")) == r["payment_date"]
                        and abs(float(v["unadjustedValue"]) - float(r["cash_amount"])) < 1e-9
                    )
                except (KeyError, TypeError, ValueError):
                    same = False
                if same:
                    hit = v
                    break
        if hit is None:
            left.append(r)
            continue
        ex, pay = date.fromisoformat(hit["date"]), date.fromisoformat(r["payment_date"])
        if not ex < pay:
            left.append(r)
            continue
        actions.append(
            CorporateAction(
                security_key,
                CorporateActionKind.CASH_DIVIDEND,
                _known_at(exchange, ex),
                Provenance(
                    provider,
                    SourceTier.VENDOR,
                    f"{r['payment_date']}:exdate",
                    vendor_sha,
                    "ex-date-merge-1",
                ),
                announcement_date=date.fromisoformat(r["announcement_date"]),
                ex_date=ex,
                record_date=date.fromisoformat(r["record_date"]),
                payment_date=pay,
                cash_amount=float(r["cash_amount"]),
                currency="USD",
                details={
                    "field_sources": {
                        "announcement/record/payment/amount": f"official sha {official_sha}",
                        "ex_date": f"structured vendor sha {vendor_sha}",
                    }
                },
            )
        )
    return actions, left
