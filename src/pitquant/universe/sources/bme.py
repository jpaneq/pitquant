"""IBEX 35 history from BME (D-03).

Primary source: the official BME document "Composición histórica – IBEX 35" (events since
1991), parsed as an event stream. Secondary source: BME "Avisos de Índices" / Comité Asesor
Técnico communications, used to verify events, update incrementally, resolve ambiguous rows
and provide ``announced_at`` (which is NOT the effective date).

Critical rule (TICKER_CHANGE): a row pairing ``deletion X + addition Y`` is NOT assumed to
be two different securities. The BME document marks code/ticker changes visually (row
format/colour). That visual marker is read via a layout calibration; if the marker cannot be
determined reliably, the row MUST be resolved by the corresponding BME aviso — otherwise
the parse fails (``UnresolvedSourceEventError``). We never guess.
"""

from __future__ import annotations

import io
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from pitquant.core.errors import ProviderContractError
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import require_aware
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.universe.events import (
    EventSource,
    EventType,
    IndexEventProvider,
    IndexEventRecord,
    MembershipSequenceError,
    SourceConfidence,
    UnresolvedSourceEventError,
)

INDEX = "IBEX35"
SOURCE = "BME_HISTORICAL_COMPOSITION"
PARSER_VERSION = "bme-ibex-history-1"


class RowStyle(StrEnum):
    INITIAL = "INITIAL"
    ORDINARY = "ORDINARY"
    EXTRAORDINARY = "EXTRAORDINARY"
    TICKER_CHANGE = "TICKER_CHANGE"
    UNKNOWN = "UNKNOWN"  # visual marker not determinable -> aviso required


@dataclass(frozen=True)
class BMEHistoryRow:
    effective_date: date
    additions: tuple[str, ...]
    deletions: tuple[str, ...]
    style: RowStyle
    row_ref: str  # page/line reference into the archived PDF
    raw_text: str = ""
    # (old, new) pairs marked as code changes CELL BY CELL inside a row (the BME document
    # can mix turnover and code changes in one review row)
    ticker_changes: tuple[tuple[str, str], ...] = ()
    review_number: int | None = None  # «Nº» column of the document


@dataclass(frozen=True)
class BMEAviso:
    """A BME index notice. Authoritative for classification and for announced_at."""

    aviso_id: str
    announced_at: datetime
    effective_date: date
    review_type: RowStyle  # ORDINARY | EXTRAORDINARY | TICKER_CHANGE
    additions: tuple[str, ...] = ()
    deletions: tuple[str, ...] = ()
    ticker_changes: tuple[tuple[str, str], ...] = ()  # (old, new)
    identifiers: dict[str, str] = field(default_factory=dict)  # ticker -> ISIN, if published
    url: str = ""

    def __post_init__(self) -> None:
        require_aware(self.announced_at, "announced_at")


# ───────────────────────────── classification ─────────────────────────────


@dataclass
class ParseResult:
    events: list[IndexEventRecord]
    warnings: list[str]
    unresolved_events: list[str] = field(default_factory=list)


def classify_rows(
    rows: Sequence[BMEHistoryRow],
    avisos: Sequence[BMEAviso] = (),
    index_code: str = INDEX,
    identities: Mapping[tuple[str, date], str] | None = None,
    *,
    unproven_as_unresolved_turnover: bool = False,
    row_resolutions: Mapping[str, tuple[str, str]] | None = None,
) -> ParseResult:
    """Turn history rows into events, resolving ambiguity ONLY with avisos.

    ``unproven_as_unresolved_turnover``: a row whose type cannot be proven (no legend
    marker, no aviso) is loaded as an exclusion + inclusion flagged UNRESOLVED_EVENT_TYPE.
    Membership is identical under both readings (code change or turnover); only identity
    differs, and the new code gets a NEW identity that stays IDENTITY_UNRESOLVED — the
    continuity a code change would imply is never assumed. Default: refuse (raise).

    Identity is kept separate from membership. A member is ``RESOLVED`` only when an
    official document gives its ISIN (the aviso, or ``identities[(ticker, date)]`` taken
    from another dated official BME/CNMV document). Otherwise membership is recorded but
    the interval is ``IDENTITY_UNRESOLVED``. A re-entry without ISIN is NEVER assumed to be
    the earlier security: it gets a new lineage key.

    ``row_resolutions``: ``row_ref -> (outcome, evidence)`` for rows WITHOUT a legend marker,
    proven from another official source (ANCV ISIN continuity, ADR-0020). ``TICKER_CHANGE``
    turns the row into a code change; ``INDEX_TURNOVER`` keeps it as turnover with the
    proof as reason. Other outcomes leave the row UNRESOLVED_EVENT_TYPE.
    """
    identities = identities or {}
    row_resolutions = row_resolutions or {}
    by_date: dict[date, list[BMEAviso]] = {}
    for a in avisos:
        by_date.setdefault(a.effective_date, []).append(a)

    events: list[IndexEventRecord] = []
    warnings: list[str] = []
    unresolved: list[str] = []
    unresolved_events: list[str] = []
    lineage_of: dict[str, str] = {}  # current ticker -> lineage key (security identity)
    members: set[str] = set()  # lineage keys currently in the index

    def lineage_for_add(ticker: str, d: date, aviso: BMEAviso | None) -> str:
        isin = (aviso.identifiers.get(ticker) if aviso else None) or identities.get((ticker, d))
        if isin:
            key = f"ISIN:{isin}"
            lineage_of[ticker] = key
            return key
        known = lineage_of.get(ticker)
        if known and known not in members:
            warnings.append(
                f"{d} {ticker}: re-entry without ISIN — NOT assumed to be the earlier "
                f"security ({known}); new identity, IDENTITY_UNRESOLVED"
            )
        key = f"BME:{ticker}:{d.isoformat()}"
        lineage_of[ticker] = key
        return key

    for row in sorted(rows, key=lambda r: (r.effective_date, r.row_ref)):
        d = row.effective_date
        day_avisos = by_date.get(d, [])
        aviso = day_avisos[0] if len(day_avisos) == 1 else None
        if len(day_avisos) > 1:
            unresolved.append(
                f"{row.row_ref} {d}: several avisos for the same date — resolve manually"
            )
            continue

        style = row.style
        proven = row_resolutions.get(row.row_ref) if style is RowStyle.UNKNOWN else None
        proof_reason: str | None = None
        if proven is not None and proven[0] == "TICKER_CHANGE":
            style = RowStyle.TICKER_CHANGE
            proof_reason = f"cambio de código probado: {proven[1]}"
        elif proven is not None and proven[0] == "INDEX_TURNOVER":
            # review type still unknown; only the turnover reading is proven
            proof_reason = f"rotación probada (identidades distintas): {proven[1]}"
        # Code changes marked cell by cell in the document (calibrated layouts only).
        changes: list[tuple[str, str]] = list(row.ticker_changes)
        adds, dels = list(row.additions), list(row.deletions)
        if changes and not adds and not dels and style is RowStyle.ORDINARY:
            style = RowStyle.TICKER_CHANGE  # nothing but code changes on that row
        announced = aviso.announced_at if aviso else None

        if aviso is not None:
            # The aviso is authoritative; the row must agree with it.
            row_adds = set(adds) | {n for _, n in changes}
            row_dels = set(dels) | {o for o, _ in changes}
            changes = list(aviso.ticker_changes)
            a_adds = set(aviso.additions) | {n for _, n in changes}
            a_dels = set(aviso.deletions) | {o for o, _ in changes}
            if row_adds != a_adds or row_dels != a_dels:
                unresolved.append(
                    f"{row.row_ref} {d}: row {adds}/{dels} disagrees with "
                    f"aviso {aviso.aviso_id} {sorted(a_adds)}/{sorted(a_dels)}"
                )
                continue
            only_changes = bool(changes) and not aviso.additions and not aviso.deletions
            aviso_style = RowStyle.TICKER_CHANGE if only_changes else aviso.review_type
            if style not in (RowStyle.UNKNOWN, RowStyle.INITIAL) and style is not aviso_style:
                unresolved.append(
                    f"{row.row_ref} {d}: visual marker {style} contradicts "
                    f"aviso {aviso.aviso_id} ({aviso_style})"
                )
                continue
            style = aviso_style
            adds = sorted(aviso.additions)
            dels = sorted(aviso.deletions)
        elif style is RowStyle.TICKER_CHANGE and not changes:
            if len(adds) != 1 or len(dels) != 1:
                unresolved.append(
                    f"{row.row_ref} {d}: ticker-change row must pair exactly one "
                    f"old and one new code, got {dels}->{adds}"
                )
                continue
            changes = [(dels[0], adds[0])]
            adds, dels = [], []
        elif style is RowStyle.UNKNOWN and not (not members and not dels):
            if not unproven_as_unresolved_turnover:
                unresolved.append(
                    f"{row.row_ref} {d}: visual marker unknown and no BME aviso — "
                    f"cannot tell ticker change from turnover ({dels} -> {adds})"
                )
                continue
            if proof_reason is None:
                unresolved_events.append(f"{row.row_ref} {d}: {dels} -> {adds}")
            warnings.append(
                f"{row.row_ref} {d}: UNRESOLVED_EVENT_TYPE {dels}->{adds} loaded as turnover "
                "(membership exact; identity continuity not assumed)"
            )

        if not members and not dels and not changes:
            style = RowStyle.INITIAL

        parent_id: str | None = None
        if style in (RowStyle.ORDINARY, RowStyle.EXTRAORDINARY) and (adds or dels):
            parent_id = f"{row.row_ref}:review"
            events.append(
                IndexEventRecord(
                    index_code,
                    EventType.EXTRAORDINARY_REVIEW
                    if style is RowStyle.EXTRAORDINARY
                    else EventType.ORDINARY_REVIEW,
                    d,
                    parent_id,
                    announced_at=announced,
                    reason=aviso.aviso_id if aviso else "BME historical composition",
                )
            )

        for old, new in changes:
            key = lineage_of.get(old)
            if key is None or key not in members:
                unresolved.append(f"{row.row_ref} {d}: ticker change {old}->{new} for non-member")
                continue
            events.append(
                IndexEventRecord(
                    index_code,
                    EventType.TICKER_CHANGE,
                    d,
                    f"{row.row_ref}:chg:{old}>{new}",
                    key,
                    old,
                    new_ticker=new,
                    announced_at=announced,
                    reason=proof_reason or "cambio de código",
                    identity_resolved=key.startswith("ISIN:"),
                )
            )
            del lineage_of[old]
            lineage_of[new] = key
        for t in dels:
            key = lineage_of.get(t)
            if key is None or key not in members:
                unresolved.append(f"{row.row_ref} {d}: deletion of non-member {t}")
                continue
            members.discard(key)
            events.append(
                IndexEventRecord(
                    index_code,
                    EventType.INDEX_DELETE,
                    d,
                    f"{row.row_ref}:del:{t}",
                    key,
                    t,
                    announced_at=announced,
                    reason=proof_reason or _reason(style),
                    parent_source_event_id=parent_id,
                    identity_resolved=key.startswith("ISIN:"),
                )
            )
        for t in adds:
            key = lineage_for_add(t, d, aviso)
            if key in members:
                unresolved.append(f"{row.row_ref} {d}: addition of current member {t}")
                continue
            members.add(key)
            kind = EventType.INITIAL_SNAPSHOT if style is RowStyle.INITIAL else EventType.INDEX_ADD
            events.append(
                IndexEventRecord(
                    index_code,
                    kind,
                    d,
                    f"{row.row_ref}:add:{t}",
                    key,
                    t,
                    identifier=key.removeprefix("ISIN:") if key.startswith("ISIN:") else None,
                    announced_at=announced,
                    reason=proof_reason or _reason(style),
                    parent_source_event_id=parent_id,
                    identity_resolved=key.startswith("ISIN:"),
                )
            )
    if unresolved:
        raise UnresolvedSourceEventError(
            f"{len(unresolved)} BME row(s) could not be resolved without guessing:\n  "
            + "\n  ".join(unresolved[:50])
        )
    return ParseResult(events, warnings, unresolved_events)


def _reason(style: RowStyle) -> str:
    if style is RowStyle.UNKNOWN:
        return "UNRESOLVED_EVENT_TYPE: code change or turnover not proven (no aviso)"
    return style.value


# ───────────────────────────── PDF extraction ─────────────────────────────

_DATE = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$")
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.&-]{0,9}$")


def _parse_date(tok: str) -> date | None:
    m = _DATE.match(tok)
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    if y < 100:
        y += 1900 if y >= 80 else 2000
    return date(y, mo, d)


Color = tuple[float, ...]


@dataclass(frozen=True)
class BMELayoutCalibration:
    """Maps visual markers to row styles for ONE version of the BME document.

    Must be produced once by inspecting the official PDF (docs/BME_PARSER.md). An empty
    calibration — or one made for a different document hash — yields UNKNOWN styles, which
    then require avisos. This is deliberate: the default is to refuse, not to guess.

    * ``style_by_color``: fill/text colour of the row marker (number/date cells, or the
      text itself) → row style.
    * ``change_cell_color``: fill of an INDIVIDUAL ticker cell marking a code change; the
      highlighted addition and deletion cells of a row are paired left to right.
    * ``neutral_colors``: grid/header/empty-cell fills that carry no meaning.
    Any other colour found on a row makes it UNKNOWN (never silently ORDINARY).
    """

    header_additions: str = "Altas"
    header_deletions: str = "Bajas"
    style_by_color: dict[Color, RowStyle] = field(default_factory=dict)
    change_cell_color: Color | None = None
    neutral_colors: frozenset[Color] = frozenset()
    calibrated_for_sha256: str | None = None
    color_tolerance: float = 0.02


def _norm(c: object) -> Color | None:
    if c is None:
        return None
    if isinstance(c, int | float):
        return (float(c),)
    if isinstance(c, list | tuple) and all(isinstance(x, int | float) for x in c):
        return tuple(float(x) for x in c)
    return None


def _close_color(a: Color, b: Color, tol: float) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def _match(color: Color | None, cal: BMELayoutCalibration) -> RowStyle | None:
    if color is None:
        return None
    for ref, style in cal.style_by_color.items():
        if _close_color(ref, color, cal.color_tolerance):
            return style
    return None


def _neutral(color: Color | None, cal: BMELayoutCalibration) -> bool:
    if color is None or all(x == 0.0 for x in color) or color in ((1.0,), (1.0, 1.0, 1.0)):
        return True  # no fill / white
    if len(color) == 4 and color[:3] == (0.0, 0.0, 0.0) and color[3] == 1.0:
        return True  # black text
    if len(color) in (1, 3) and all(x == 0.0 for x in color):
        return True
    return any(_close_color(color, n, cal.color_tolerance) for n in cal.neutral_colors)


def _column_starts(
    page: Any, hdr_add: dict[str, Any], hdr_del: dict[str, Any]
) -> tuple[float, float]:
    """x where the additions / deletions columns start: the header CELL containing each
    header word (headers are centred over their cells). Falls back to the word itself."""

    def cell_x0(w: dict[str, Any]) -> float:
        cx = (float(w["x0"]) + float(w["x1"])) / 2
        cy = (float(w["top"]) + float(w["bottom"])) / 2
        cells = [
            r
            for r in page.rects
            if float(r["x0"]) <= cx <= float(r["x1"])
            and float(r["top"]) <= cy <= float(r["bottom"])
        ]
        if not cells:
            return float(w["x0"])
        # the most specific cell: a table-wide background rect also contains the word
        best = min(cells, key=lambda r: float(r["x1"]) - float(r["x0"]))
        return float(best["x0"])

    return cell_x0(hdr_add), cell_x0(hdr_del)


def extract_rows_from_pdf(pdf: bytes, cal: BMELayoutCalibration) -> list[BMEHistoryRow]:
    """Extract (date, additions, deletions, style, cell-level code changes) rows.

    Columns start at the header cells; a leading review number («Nº») is kept apart; «—»
    or «-» mean "no change". Styles are read only with a calibration made for THIS
    document (by hash); anything not explained by the calibration yields UNKNOWN.
    """
    import pdfplumber

    from pitquant.data.archive import sha256_hex

    doc_sha = sha256_hex(pdf)
    trusted = bool(cal.style_by_color) and cal.calibrated_for_sha256 == doc_sha
    rows: list[BMEHistoryRow] = []
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for pno, page in enumerate(doc.pages, start=1):
            words = page.extract_words(extra_attrs=["non_stroking_color"], keep_blank_chars=False)
            hdr_add = next((w for w in words if w["text"] == cal.header_additions), None)
            hdr_del = next((w for w in words if w["text"] == cal.header_deletions), None)
            if hdr_add is None or hdr_del is None:
                continue
            x_add, x_del = _column_starts(page, hdr_add, hdr_del)
            lo, hi = min(x_add, x_del), max(x_add, x_del)
            header_bottom = max(float(hdr_add["bottom"]), float(hdr_del["bottom"]))
            lines: dict[int, list[dict[str, Any]]] = {}
            for w in words:
                if float(w["top"]) <= header_bottom:
                    continue
                lines.setdefault(round(float(w["top"])), []).append(w)
            for top in sorted(lines):
                ws = sorted(lines[top], key=lambda w: float(w["x0"]))
                number: int | None = None
                if len(ws) > 1 and str(ws[0]["text"]).isdigit() and _parse_date(str(ws[1]["text"])):
                    number = int(str(ws[0]["text"]))
                    ws = ws[1:]
                d = _parse_date(str(ws[0]["text"]))
                if d is None:
                    continue
                y0 = min(float(w["top"]) for w in ws)
                y1 = max(float(w["bottom"]) for w in ws)
                tickers: list[tuple[str, float, float, str]] = []  # (tok, x0, x1, column)
                for w in ws[1:]:
                    tok = str(w["text"]).strip(",;")
                    if not _TICKER.match(tok):
                        continue  # «—», «-», notes
                    x = float(w["x0"])
                    if x >= hi - 1:
                        col = "del" if hi == x_del else "add"
                    elif x >= lo - 1:
                        col = "add" if lo == x_add else "del"
                    else:
                        continue
                    tickers.append((tok, x, float(w["x1"]), col))
                adds = [t for t, _, _, c in tickers if c == "add"]
                dels = [t for t, _, _, c in tickers if c == "del"]
                style = RowStyle.UNKNOWN
                changes: tuple[tuple[str, str], ...] = ()
                if trusted:
                    style, changes = _row_style(page, ws, tickers, y0, y1, lo, cal)
                    for old, new in changes:
                        dels.remove(old)
                        adds.remove(new)
                rows.append(
                    BMEHistoryRow(
                        d,
                        tuple(adds),
                        tuple(dels),
                        style,
                        f"p{pno}:y{top}",
                        " ".join(str(w["text"]) for w in ws),
                        changes,
                        number,
                    )
                )
    return rows


def _row_style(
    page: Any,
    ws: list[dict[str, Any]],
    tickers: list[tuple[str, float, float, str]],
    y0: float,
    y1: float,
    first_col_x: float,
    cal: BMELayoutCalibration,
) -> tuple[RowStyle, tuple[tuple[str, str], ...]]:
    found: set[RowStyle] = set()
    unexplained = False
    for w in ws:  # coloured text
        c = _norm(w.get("non_stroking_color"))
        s = _match(c, cal)
        if s:
            found.add(s)
        elif not _neutral(c, cal):
            unexplained = True
    hl_add: list[tuple[float, str]] = []
    hl_del: list[tuple[float, str]] = []
    for r in page.rects:
        if not (float(r["top"]) <= y1 and float(r["bottom"]) >= y0):
            continue
        c = _norm(r.get("non_stroking_color"))
        rx0, rx1 = float(r["x0"]), float(r["x1"])
        if (
            cal.change_cell_color
            and c
            and _close_color(c, cal.change_cell_color, cal.color_tolerance)
        ):
            inside = [t for t in tickers if rx0 - 1 <= (t[1] + t[2]) / 2 <= rx1 + 1]
            if len(inside) != 1:
                return RowStyle.UNKNOWN, ()  # a highlighted cell must hold exactly one code
            tok, x, _, col = inside[0]
            (hl_add if col == "add" else hl_del).append((x, tok))
            continue
        s = _match(c, cal)
        if s and rx1 <= first_col_x + 1:
            found.add(s)
        elif not _neutral(c, cal):
            unexplained = True
    if unexplained or len(found) > 1 or len(hl_add) != len(hl_del):
        return RowStyle.UNKNOWN, ()
    changes = tuple(
        (old, new) for (_, old), (_, new) in zip(sorted(hl_del), sorted(hl_add), strict=True)
    )
    style = found.pop() if found else RowStyle.ORDINARY
    return style, changes


@dataclass
class BMEHistoricalCompositionProvider(IndexEventProvider):
    """CANONICAL IBEX 35 source: official PDF + avisos (both archived)."""

    pdf: bytes
    pdf_url: str
    calibration: BMELayoutCalibration
    store: ArchiveStore
    avisos: Sequence[BMEAviso] = ()
    aviso_documents: Sequence[tuple[str, bytes, datetime]] = ()  # (url, bytes, announced_at)
    # ISIN for (ticker, effective_date) taken from dated official documents
    identities: Mapping[tuple[str, date], str] = field(default_factory=dict)

    @property
    def membership_source(self) -> str:
        return SOURCE

    @property
    def confidence(self) -> SourceConfidence:
        return SourceConfidence.CANONICAL

    def load(self, session: Session, index_code: str = INDEX) -> EventSource:
        main = archive_document(
            session,
            self.store,
            provider=SOURCE,
            source_identifier=self.pdf_url,
            data=self.pdf,
            mime_type="application/pdf",
            parser_version=PARSER_VERSION,
        )
        hashes = [main.sha256]
        for url, data, ann in self.aviso_documents:
            a = archive_document(
                session,
                self.store,
                provider="BME_AVISOS",
                source_identifier=url,
                data=data,
                mime_type="application/pdf",
                published_at=ann,
                parser_version=PARSER_VERSION,
            )
            hashes.append(a.sha256)
        rows = extract_rows_from_pdf(self.pdf, self.calibration)
        if not rows:
            raise ProviderContractError("no rows extracted from the BME document — layout changed?")
        result = classify_rows(rows, self.avisos, index_code, self.identities)
        return EventSource(
            SOURCE,
            self.confidence,
            result.events,
            content_hash(hashes),
            main.archive_id,
            tuple(result.warnings),
        )


def events_from_rows(
    rows: Sequence[BMEHistoryRow],
    avisos: Sequence[BMEAviso],
    raw_source_hash: str,
    index_code: str = INDEX,
    identities: Mapping[tuple[str, date], str] | None = None,
) -> EventSource:
    """Build an EventSource from already-extracted rows (tests, manual corrections)."""
    res = classify_rows(rows, avisos, index_code, identities)
    if not res.events:
        raise MembershipSequenceError("empty event stream")
    return EventSource(
        SOURCE,
        SourceConfidence.CANONICAL,
        res.events,
        raw_source_hash,
        warnings=tuple(res.warnings),
    )


# ───────────────────────────── calibrations (versioned, one per document hash) ──────────

COMPOIBEX_2026_09_SHA256 = "5c028420d39c9d6e2205fa88d15627865dc217de867bc86987ca8f9fddba3695"

# «Composición histórica – IBEX 35», BME, Last-Modified 2026-09-21 (rows 1–137, 3 pages).
# Measured on the archived PDF (docs/BME_PARSER.md):
# * legend «Revisión extraordinaria»: fill CMYK (0.149, 0.13, 0, 0) on the Nº/fecha cells;
# * legend «Cambio de código»: fill 0.5 on INDIVIDUAL ticker cells (rows 16, 18, 25, 32, 34,
#   42 — sometimes inside an ordinary review row);
# * neutral: (0, 0, 0, 0.15) header/empty-cell grey.
# A third fill, CMYK (0.048, 0.176, 0.285, 0), marks the Nº/fecha cells of rows 62, 76, 80,
# 91, 106, 108 and 122 but is NOT in the legend: it is deliberately left unmapped, so those
# rows come out UNKNOWN and need their BME aviso.
COMPOIBEX_2026_09 = BMELayoutCalibration(
    header_additions="Inclusiones",
    header_deletions="Exclusiones",
    style_by_color={(0.149, 0.13, 0.0, 0.0): RowStyle.EXTRAORDINARY},
    change_cell_color=(0.5,),
    neutral_colors=frozenset({(0.0, 0.0, 0.0, 0.15), (0.0, 0.0, 0.0, 0.75)}),
    calibrated_for_sha256=COMPOIBEX_2026_09_SHA256,
)
