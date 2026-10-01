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


def classify_rows(
    rows: Sequence[BMEHistoryRow],
    avisos: Sequence[BMEAviso] = (),
    index_code: str = INDEX,
    identities: Mapping[tuple[str, date], str] | None = None,
) -> ParseResult:
    """Turn history rows into events, resolving ambiguity ONLY with avisos.

    Identity is kept separate from membership. A member is ``RESOLVED`` only when an
    official document gives its ISIN (the aviso, or ``identities[(ticker, date)]`` taken
    from another dated official BME/CNMV document). Otherwise membership is recorded but
    the interval is ``IDENTITY_UNRESOLVED``. A re-entry without ISIN is NEVER assumed to be
    the earlier security: it gets a new lineage key.
    """
    identities = identities or {}
    by_date: dict[date, list[BMEAviso]] = {}
    for a in avisos:
        by_date.setdefault(a.effective_date, []).append(a)

    events: list[IndexEventRecord] = []
    warnings: list[str] = []
    unresolved: list[str] = []
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
        changes: list[tuple[str, str]] = []
        adds, dels = list(row.additions), list(row.deletions)
        announced = aviso.announced_at if aviso else None

        if aviso is not None:
            # The aviso is authoritative; the row must agree with it.
            changes = list(aviso.ticker_changes)
            a_adds = set(aviso.additions) | {n for _, n in changes}
            a_dels = set(aviso.deletions) | {o for o, _ in changes}
            if set(adds) != a_adds or set(dels) != a_dels:
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
        elif style is RowStyle.TICKER_CHANGE:
            if len(adds) != 1 or len(dels) != 1:
                unresolved.append(
                    f"{row.row_ref} {d}: ticker-change row must pair exactly one "
                    f"old and one new code, got {dels}->{adds}"
                )
                continue
            changes = [(dels[0], adds[0])]
            adds, dels = [], []
        elif style is RowStyle.UNKNOWN and not (not members and not dels):
            unresolved.append(
                f"{row.row_ref} {d}: visual marker unknown and no BME aviso — "
                f"cannot tell ticker change from turnover ({dels} -> {adds})"
            )
            continue

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
                    reason="cambio de código",
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
                    reason=style.value,
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
                    reason=style.value,
                    parent_source_event_id=parent_id,
                    identity_resolved=key.startswith("ISIN:"),
                )
            )
    if unresolved:
        raise UnresolvedSourceEventError(
            f"{len(unresolved)} BME row(s) could not be resolved without guessing:\n  "
            + "\n  ".join(unresolved[:50])
        )
    return ParseResult(events, warnings)


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
    """

    header_additions: str = "Altas"
    header_deletions: str = "Bajas"
    style_by_color: dict[Color, RowStyle] = field(default_factory=dict)
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


def _match(color: Color | None, cal: BMELayoutCalibration) -> RowStyle | None:
    if color is None:
        return None
    for ref, style in cal.style_by_color.items():
        if len(ref) == len(color) and all(
            abs(a - b) <= cal.color_tolerance for a, b in zip(ref, color, strict=True)
        ):
            return style
    return None


def extract_rows_from_pdf(pdf: bytes, cal: BMELayoutCalibration) -> list[BMEHistoryRow]:
    """Extract (date, additions, deletions, visual style) rows from the BME PDF.

    Columns are located from the header words; each word is assigned to the column whose
    x-range contains it. The style of a row comes from the colour of its characters or of
    a filled rectangle behind it, mapped through the calibration.
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
            x_add, x_del = float(hdr_add["x0"]), float(hdr_del["x0"])
            lines: dict[int, list[dict[str, object]]] = {}
            for w in words:
                if float(w["top"]) <= float(hdr_add["bottom"]):
                    continue
                lines.setdefault(round(float(w["top"])), []).append(w)
            rects = page.rects
            for top in sorted(lines):
                ws = sorted(lines[top], key=lambda w: float(w["x0"]))  # type: ignore[arg-type]
                d = _parse_date(str(ws[0]["text"]))
                if d is None:
                    continue
                adds: list[str] = []
                dels: list[str] = []
                lo, hi = min(x_add, x_del), max(x_add, x_del)
                for w in ws[1:]:
                    tok = str(w["text"]).strip(",;")
                    if not _TICKER.match(tok):
                        continue
                    x = float(w["x0"])  # type: ignore[arg-type]
                    if x >= hi - 1:
                        (dels if hi == x_del else adds).append(tok)
                    elif x >= lo - 1:
                        (adds if lo == x_add else dels).append(tok)
                style = RowStyle.UNKNOWN
                if trusted:
                    found: set[RowStyle] = set()
                    for w in ws:
                        s = _match(_norm(w.get("non_stroking_color")), cal)
                        if s:
                            found.add(s)
                    y0, y1 = float(ws[0]["top"]), float(ws[0]["bottom"])  # type: ignore[arg-type]
                    for r in rects:
                        if float(r["top"]) <= y1 and float(r["bottom"]) >= y0:
                            s = _match(_norm(r.get("non_stroking_color")), cal)
                            if s:
                                found.add(s)
                    if len(found) == 1:
                        style = found.pop()
                    elif not found:
                        style = RowStyle.ORDINARY
                rows.append(
                    BMEHistoryRow(
                        d,
                        tuple(adds),
                        tuple(dels),
                        style,
                        f"p{pno}:y{top}",
                        " ".join(str(w["text"]) for w in ws),
                    )
                )
    return rows


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
