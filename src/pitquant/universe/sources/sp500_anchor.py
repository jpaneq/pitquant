# ruff: noqa: E501
"""SP500_CURRENT_ANCHOR from two ETF holdings files (ADR-0026). Never labelled OFFICIAL_SPDJI.

* SPY (State Street ``holdings-daily-us-en-spy.xlsx``): name, ticker, CUSIP («Identifier»), SEDOL.
* IVV (iShares ``latest-holdings.csv``): ticker, name, asset class, exchange. NOTE: the file the
  owner described has CUSIP/ISIN/SEDOL columns; the public CSV actually served does NOT, so the
  IVV side is reconciled by ticker + name and the report says so (key level TICKER_NAME).
* Non-equity lines are removed by RULE (never by count): asset class != Equity, cash lines, an
  invalid CUSIP check digit (placeholders such as CVRs), exchange «NO MARKET». The SPY and IVV
  counts are NOT required to be equal.
* Different as-of dates: the older snapshot is advanced with the CONFIRMED events effective in
  (older, newer] before comparing; an unexplained difference is a CONFLICT.
"""

from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from io import BytesIO

from pitquant.core.errors import DataQualityError


class AnchorStatus(StrEnum):
    OFFICIAL_SPDJI = "OFFICIAL_SPDJI"
    MULTI_SOURCE_CONFIRMED = "MULTI_SOURCE_CONFIRMED"
    CONFLICT = "CONFLICT"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Holding:
    ticker: str
    name: str
    cusip: str | None
    sedol: str | None
    isin: str | None
    asset_class: str
    exchange: str | None
    weight: float | None


@dataclass
class HoldingsSnapshot:
    source: str  # SPY | IVV
    as_of: date
    holdings: list[Holding]
    key_level: str  # CUSIP | TICKER_NAME
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (ticker/name, reason)

    @property
    def equities(self) -> list[Holding]:
        return self.holdings


def cusip_valid(c: str) -> bool:
    """CUSIP check digit (modulus 10 double-add-double). Placeholders like «436CVR021» fail."""
    if len(c) != 9 or not re.fullmatch(r"[0-9A-Z*@#]{8}[0-9]", c):
        return False
    tot = 0
    for i, ch in enumerate(c[:8]):
        v = (
            int(ch)
            if ch.isdigit()
            else ord(ch) - 55
            if ch.isalpha()
            else {"*": 36, "@": 37, "#": 38}[ch]
        )
        if i % 2 == 1:
            v *= 2
        tot += v // 10 + v % 10
    return (10 - tot % 10) % 10 == int(c[8])


def norm_ticker(t: str) -> str:
    """BRK.B / BRK-B / BRK B -> BRKB. Only a SUPPORT key: equality is proven by name + CUSIP."""
    return re.sub(r"[^A-Z0-9]", "", t.upper())


def _words(name: str) -> set[str]:
    stop = {
        "INC",
        "CORP",
        "CO",
        "CORPORATION",
        "COMPANY",
        "LTD",
        "PLC",
        "THE",
        "CLASS",
        "CL",
        "HOLDINGS",
        "GROUP",
        "A",
        "B",
        "C",
        "NV",
        "SA",
        "LLC",
        "LP",
        "AND",
        "OF",
    }
    return {w for w in re.findall(r"[A-Z0-9]+", name.upper()) if w not in stop}


def names_compatible(name_a: str, name_b: str) -> bool:
    wa, wb = _words(name_a), _words(name_b)
    if not wa or not wb:
        return False
    if wa & wb and (wa <= wb or wb <= wa or len(wa & wb) / min(len(wa), len(wb)) >= 0.5):
        return True
    sa, sb = re.sub(r"[^A-Z0-9]", "", name_a.upper()), re.sub(r"[^A-Z0-9]", "", name_b.upper())
    return (
        len(sa) >= 5 and len(sb) >= 5 and sa[:5] == sb[:5]
    )  # «LOWE S» vs «LOWES», «EXPEDITORS INTL» vs «EXPEDITORS INTERNATIONAL»


# ───────────────────────────────────────── parsers ───────────────────────────────────────
def parse_spy_xlsx(data: bytes) -> HoldingsSnapshot:
    z = zipfile.ZipFile(BytesIO(data))
    ss = [
        re.sub(r"<[^>]+>", "", x)
        for x in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), flags=re.S)
    ]
    ss = [x.replace("&amp;", "&") for x in ss]
    rows = re.findall(
        r"<row [^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode(), flags=re.S
    )
    table: list[dict[str, str]] = []
    for r in rows:
        d: dict[str, str] = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', r, flags=re.S):
            col, attr, inner = m.groups()
            v = re.search(r"<v>(.*?)</v>", inner or "")
            if v:
                d[col] = ss[int(v.group(1))] if 't="s"' in attr else v.group(1)
        table.append(d)
    as_of = None
    for d in table[:6]:
        if d.get("A", "").startswith("Holdings"):
            dm = re.search(r"(\d{2}-[A-Za-z]{3}-\d{4})", d.get("B", ""))
            if dm:
                as_of = datetime.strptime(dm.group(1), "%d-%b-%Y").replace(tzinfo=UTC).date()
    hdr = next(
        (i for i, d in enumerate(table) if d.get("A") == "Name" and d.get("B") == "Ticker"), None
    )
    if as_of is None or hdr is None:
        raise DataQualityError("SPY holdings file: layout not recognised (as-of date / header)")
    snap = HoldingsSnapshot("SPY", as_of, [], "CUSIP")
    for d in table[hdr + 1 :]:
        name, tick, cusip = d.get("A"), d.get("B"), d.get("C")
        if not name or tick is None or cusip is None:
            continue  # footer / disclaimers
        if tick in ("-", ""):
            snap.excluded.append((name, "no ticker (cash/other line)"))
            continue
        if tick[:1].isdigit():
            snap.excluded.append(
                (
                    f"{tick} {name}",
                    f"numeric placeholder ticker (CUSIP {cusip}, weight {d.get('E')}): not a listed equity",
                )
            )
            continue
        if not cusip_valid(cusip):
            snap.excluded.append(
                (
                    f"{tick} {name}",
                    f"invalid CUSIP check digit ({cusip}): placeholder, not an equity line",
                )
            )
            continue
        snap.holdings.append(
            Holding(
                tick.upper(),
                name,
                cusip,
                d.get("D") if d.get("D") != "-" else None,
                None,
                "Equity",
                None,
                float(d["E"]) if d.get("E") else None,
            )
        )
    return snap


def parse_ivv_csv(data: bytes) -> HoldingsSnapshot:
    lines = data.decode("utf-8-sig").splitlines()
    as_of = None
    for ln in lines[:8]:
        mm = re.match(r'Fund Holdings as of,"?([A-Za-z]{3} \d{1,2}, \d{4})', ln)
        if mm:
            as_of = datetime.strptime(mm.group(1), "%b %d, %Y").replace(tzinfo=UTC).date()
    hi = next((i for i, ln in enumerate(lines) if ln.startswith("Ticker,")), None)
    if as_of is None or hi is None:
        raise DataQualityError("IVV holdings file: layout not recognised (as-of date / header)")
    rd = list(csv.DictReader(lines[hi:]))
    has_ids = any(k in rd[0] for k in ("CUSIP", "ISIN"))
    snap = HoldingsSnapshot("IVV", as_of, [], "CUSIP" if has_ids else "TICKER_NAME")
    for r in rd:
        tick, name = (r.get("Ticker") or "").strip(), (r.get("Name") or "").strip()
        if not tick:
            continue
        ac = (r.get("Asset Class") or "").strip()
        ex = (r.get("Exchange") or "").strip()
        if ac != "Equity":
            snap.excluded.append((f"{tick} {name}", f"asset class {ac}"))
        elif "NO MARKET" in ex.upper():
            snap.excluded.append(
                (
                    f"{tick} {name}",
                    "equity line with no market (unlisted remnant of a delisted holding)",
                )
            )
        else:
            w = (r.get("Weight (%)") or "").replace(",", "")
            snap.holdings.append(
                Holding(
                    tick.upper(),
                    name,
                    (r.get("CUSIP") or None),
                    (r.get("SEDOL") or None),
                    (r.get("ISIN") or None),
                    ac,
                    ex,
                    float(w) if w else None,
                )
            )
    return snap


# ───────────────────────────────────────── reconciliation ────────────────────────────────
@dataclass(frozen=True)
class AnchorEvent:
    """A CONFIRMED S&P 500 membership event (ticker level), effective on ``effective_session``."""

    effective_session: date
    added: str | None
    removed: str | None


@dataclass
class AnchorResult:
    status: AnchorStatus
    as_of: date | None
    members: list[Holding] = field(default_factory=list)
    reconciled: int = 0
    key_level: str = ""
    differences: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def reconcile(
    spy: HoldingsSnapshot, ivv: HoldingsSnapshot, events: list[AnchorEvent]
) -> AnchorResult:
    older, newer = (spy, ivv) if spy.as_of <= ivv.as_of else (ivv, spy)
    notes = [
        f"{spy.source} as of {spy.as_of} ({len(spy.holdings)} equities), {ivv.source} as of {ivv.as_of} ({len(ivv.holdings)} equities); counts are not required to match"
    ]
    names: dict[str, str] = {}
    older_set = {norm_ticker(h.ticker) for h in older.holdings}
    for h in older.holdings + newer.holdings:
        names[norm_ticker(h.ticker)] = h.name
    if older.as_of != newer.as_of:
        applied = [e for e in events if older.as_of < e.effective_session <= newer.as_of]
        for e in sorted(applied, key=lambda x: x.effective_session):
            if e.removed:
                older_set.discard(norm_ticker(e.removed))
            if e.added:
                older_set.add(norm_ticker(e.added))
        notes.append(
            f"{older.source} advanced {older.as_of} -> {newer.as_of} with {len(applied)} confirmed event(s): "
            + ", ".join(
                f"{e.effective_session} +{e.added or '-'} -{e.removed or '-'}" for e in applied
            )
        )
    newer_set = {norm_ticker(h.ticker) for h in newer.holdings}
    diffs: list[str] = []
    for t in sorted(newer_set - older_set):
        diffs.append(f"only in {newer.source} {newer.as_of}: {t} ({names.get(t, '?')})")
    adv = " (advanced)" if older.as_of != newer.as_of else f" {older.as_of}"
    for t in sorted(older_set - newer_set):
        diffs.append(f"only in {older.source}{adv}: {t} ({names.get(t, '?')})")
    by_t_spy = {norm_ticker(h.ticker): h for h in spy.holdings}
    by_t_ivv = {norm_ticker(h.ticker): h for h in ivv.holdings}
    mism: list[str] = []
    weight_only: list[str] = []
    common = set(by_t_spy) & set(by_t_ivv)
    for t in sorted(common):
        a, b = by_t_spy[t], by_t_ivv[t]
        if a.cusip and b.cusip and a.cusip != b.cusip:
            mism.append(f"{t}: CUSIP {a.cusip} != {b.cusip}")
        elif not (a.cusip and b.cusip) and not names_compatible(a.name, b.name):
            wa, wb = a.weight, b.weight
            if wa and wb and abs(wa - wb) / max(wa, wb) <= 0.2:
                weight_only.append(
                    f"{t} ({a.name!r} / {b.name!r})"
                )  # renamed issuer: same ticker, same weight
            else:
                mism.append(f"{t}: names incompatible ({a.name!r} vs {b.name!r})")
    key_level = "CUSIP" if spy.key_level == ivv.key_level == "CUSIP" else "TICKER_NAME"
    if key_level == "TICKER_NAME":
        notes.append(
            "IVV file has no CUSIP/ISIN: tickers are matched and every pair name-checked (BRK.B/BRK-B/BRK B normalised only because names agree)"
        )
    if weight_only:
        notes.append(
            f"{len(weight_only)} pair(s) with different issuer names corroborated by ticker + weight (±20 %): "
            + "; ".join(weight_only)
        )
    members = list(newer.holdings if newer.source == "SPY" else spy.holdings)
    if diffs or mism:
        return AnchorResult(
            AnchorStatus.CONFLICT,
            newer.as_of,
            members,
            len(common) - len(mism),
            key_level,
            diffs + mism,
            notes,
        )
    return AnchorResult(
        AnchorStatus.MULTI_SOURCE_CONFIRMED, newer.as_of, members, len(common), key_level, [], notes
    )
