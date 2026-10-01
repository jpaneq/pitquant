"""CNMVSecurityIdentityProvider: the ANCV semiannual ISIN lists (ADR-0020).

The Agencia Nacional de Codificación de Valores (CNMV) publishes, every June and December
since 2010, a zip with the ISIN codes active in its database. Each distribution carries a
LEAME (read-me) that defines what the lists contain, and the formats CHANGE over time:

* ``LVRVaamm.XML`` (equities, windows-1252) — with a ``<Cfi>`` element from 06/2022;
* ``ILVRV`` (12/2022 only, no extension): ``??``-delimited text, 8 fields, no XML;
* ``LVaamm.txt``: fixed-width ASCII (180 bytes, 186 with CFI). Older LEAMEs say it lists the
  securities ADMITTED TO TRADING on Spanish official markets; newer ones say it lists every
  ISIN ACTIVE in the ANCV database. It carries the «Fecha de emisión» of each ISIN;
* from 12/2018 only ISINs assigned by the ANCV (``ES…``) appear: absence of a foreign ISIN
  is not evidence of anything.

What a snapshot proves: the ISIN was active (or admitted, per the LEAME scope) on the
reference date. It never proves when it started or ended. No network in the parsers;
``discover_distribution_urls`` reads the archived publications page.
"""

from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore, archive_document, sha256_hex
from pitquant.db.models import RawSourceArchive, SecurityIdentitySnapshot

PARSER_VERSION = "cnmv-ancv-1"
SOURCE = "CNMV_ANCV"
PROVIDER = "CNMV_ANCV"
PUBLICATIONS_URL = "https://www.cnmv.es/Portal/Publicaciones/ANCV.aspx"
BASE = "https://www.cnmv.es"

Scope = Literal["ADMITTED_TO_TRADING", "ACTIVE_IN_ANCV"]


def discover_distribution_urls(page: bytes) -> list[str]:
    """Zip links of the semiannual publication, as listed on the CNMV page."""
    s = page.decode("utf-8", errors="replace")
    rel = sorted(set(re.findall(r'href="(/DocPortal/Publicaciones/ANCV/[^"]+\.zip)"', s, re.I)))
    return [BASE + r for r in rel]


# ───────────────────────────── reference date ─────────────────────────────


def _date_from_4digits(d4: str) -> set[date]:
    """Interpretations of a 4-digit stamp (``aamm`` per the LEAME; the 12/2022 PDF uses
    ``mmaa``). Only June/December are valid semiannual references."""
    out = set()
    for yy, mm in ((d4[:2], d4[2:]), (d4[2:], d4[:2])):
        if mm in ("06", "12"):
            y, m = 2000 + int(yy), int(mm)
            out.add(date(y, 6, 30) if m == 6 else date(y, 12, 31))
    return out


def reference_date_of(members: dict[str, bytes]) -> tuple[date, list[str]]:
    """Reference date from the CONTENT and member names, never from the zip name
    (``ANCVSEMESTRAL25.zip`` is December 2025). Every signal must agree (fail closed)."""
    signals: list[tuple[str, set[date]]] = []
    for name, data in members.items():
        base = name.rsplit("/", 1)[-1]
        m = re.fullmatch(r"LV(?:RV)?(\d{4})\.(?:XML|txt|pdf)", base, flags=re.I)
        if m:
            signals.append((base, _date_from_4digits(m.group(1))))
        if base.upper().startswith("LVRV") and base.upper().endswith(".XML"):
            r = re.search(rb"<CODIGOS_ISIN_([12])_(\d{4})>", data[:400])
            if r:
                y = int(r.group(2))
                d = date(y, 6, 30) if r.group(1) == b"1" else date(y, 12, 31)
                signals.append((f"{base}:root", {d}))
    if not signals:
        raise DataQualityError("ANCV distribution: no dated member (LVaamm / LVRVaamm)")
    common = set.intersection(*(s for _, s in signals))
    if len(common) != 1:
        raise DataQualityError(f"ANCV distribution: reference date signals disagree {signals}")
    return common.pop(), [n for n, _ in signals]


# ───────────────────────────── LEAME ─────────────────────────────


@dataclass(frozen=True)
class Leame:
    sha256: str
    txt_scope: Scope
    scope_sentence: str
    only_es_isins: bool
    documents_cfi: bool


def parse_leame(pdf: bytes) -> Leame:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in doc.pages))
    m = re.search(r"Ambos ficheros contienen[^.]*\.|Un fichero con[^.]*\.", text)
    if m is None:
        raise DataQualityError("LEAME: sentence defining the TXT listing not found")
    sentence = m.group(0)
    if "admitidos a cotización" in sentence:
        scope: Scope = "ADMITTED_TO_TRADING"
    elif "ISIN activo en la base de datos de la ANCV" in sentence:
        scope = "ACTIVE_IN_ANCV"
    else:
        raise DataQualityError(f"LEAME: unknown listing scope: {sentence!r}")
    return Leame(
        sha256_hex(pdf),
        scope,
        sentence,
        only_es_isins="(códigos que comienzan por ES)" in text,
        documents_cfi=" CFI " in f" {text} ",
    )


# ───────────────────────────── equity lines ─────────────────────────────


@dataclass(frozen=True)
class AncvEquityLine:
    isin: str
    issuer_legal_name: str
    instrument_name: str
    series: str
    nominal: str | None
    currency: str | None
    cfi: str | None

    @property
    def short_code(self) -> str:
        """ANCV's abbreviation before ``/`` (e.g. ``ENG`` in ``ENG/AC 1,50``). It is an
        ANCV label, NOT the exchange ticker (Redeia: ``REDEIA/AC`` while BME code = RED)."""
        return self.instrument_name.split("/", 1)[0].strip()

    @property
    def share_kind(self) -> str:
        """``AC`` ordinary share, ``ACNV`` new shares pending admission, ``AOC``... ."""
        rest = self.instrument_name.split("/", 1)[1] if "/" in self.instrument_name else ""
        return rest.split()[0] if rest.split() else ""


_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


def _isin_ok(s: str) -> bool:
    if not _ISIN.match(s):
        return False
    digits = "".join(str(int(c, 36)) for c in s[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(s[-1])


def _clean(s: str | None) -> str:
    return (s or "").strip()


def parse_lvrv_xml(data: bytes) -> list[AncvEquityLine]:
    root = ET.fromstring(data)  # encoding taken from the declaration (windows-1252)
    out = []
    for e in root.iter("EMISION_RV"):
        f = {c.tag: _clean(c.text) for c in e}
        if "Isin" not in f or "Nombre_Valor" not in f or "Nombre_Entidad" not in f:
            raise DataQualityError(f"LVRV XML: unexpected EMISION_RV fields {sorted(f)}")
        out.append(
            AncvEquityLine(
                f["Isin"],
                f["Nombre_Entidad"],
                f["Nombre_Valor"],
                f.get("Serie", ""),
                f.get("Valor_Nominal") or None,
                f.get("Moneda") or None,
                f.get("Cfi") or None,
            )
        )
    return out


def parse_ilvrv(data: bytes) -> list[AncvEquityLine]:
    """12/2022 layout: entity??ISIN??name??series??number??nominal??currency??CFI."""
    out = []
    for raw in data.decode("cp1252").splitlines():
        if not raw.strip():
            continue
        f = [x.strip() for x in raw.split("??")]
        if len(f) != 8:
            raise DataQualityError(f"ILVRV: expected 8 fields, got {len(f)}: {raw[:80]!r}")
        out.append(AncvEquityLine(f[1], f[0], f[2], f[3], f[5] or None, f[6] or None, f[7] or None))
    return out


def parse_fixed_width_txt(data: bytes) -> dict[str, date | None]:
    """ISIN -> «Fecha de emisión» from ``LVaamm.txt`` (positions per the LEAME)."""
    out: dict[str, date | None] = {}
    for raw in data.split(b"\r\n"):
        if not raw:
            continue
        if len(raw) not in (180, 186) and raw[180:].strip() == b"" and len(raw) < 186:
            raw = raw[:180]  # a few records (funds, certificates) carry trailing blanks
        if len(raw) not in (180, 186):
            raise DataQualityError(f"LV txt: record length {len(raw)} not in (180, 186)")
        isin = raw[:12].decode("ascii")
        d = raw[121:129].decode("ascii")
        issued = None
        if re.fullmatch(r"\d{8}", d):
            try:
                issued = date(int(d[:4]), int(d[4:6]), int(d[6:]))
            except ValueError:
                issued = None
        out[isin] = issued
    return out


# ───────────────────────────── distribution ─────────────────────────────


@dataclass
class AncvDistribution:
    reference_date: date
    date_signals: list[str]
    leame: Leame
    equity_member: str
    equity_format: str  # LVRV_XML | ILVRV_DELIMITED
    equity_lines: list[AncvEquityLine]
    txt_member: str | None
    txt_issue_dates: dict[str, date | None]
    member_hashes: dict[str, str] = field(default_factory=dict)
    rejected_isins: list[str] = field(default_factory=list)

    def scope_of(self, isin: str) -> Scope:
        """ADMITTED_TO_TRADING only when the LEAME says the TXT lists admitted securities
        AND the ISIN is in that TXT; otherwise the weaker 'active in the ANCV database'."""
        if self.leame.txt_scope == "ADMITTED_TO_TRADING" and isin in self.txt_issue_dates:
            return "ADMITTED_TO_TRADING"
        return "ACTIVE_IN_ANCV"


def parse_distribution(zip_bytes: bytes) -> AncvDistribution:
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    members = {n: zf.read(n) for n in zf.namelist() if not n.endswith("/")}
    hashes = {n: sha256_hex(b) for n, b in members.items()}
    leames = [n for n in members if n.rsplit("/", 1)[-1].upper() == "LEAME.PDF"]
    if len(leames) != 1:
        raise DataQualityError(f"ANCV distribution: expected one LEAME, got {leames}")
    leame = parse_leame(members[leames[0]])
    ref, signals = reference_date_of(members)
    xml = [n for n in members if re.search(r"(^|/)LVRV\d{4}\.XML$", n, re.I)]
    delim = [n for n in members if re.search(r"(^|/)ILVRV$", n)]
    if len(xml) == 1 and not delim:
        member, fmt, lines = xml[0], "LVRV_XML", parse_lvrv_xml(members[xml[0]])
    elif len(delim) == 1 and not xml:
        member, fmt, lines = delim[0], "ILVRV_DELIMITED", parse_ilvrv(members[delim[0]])
    else:
        raise DataQualityError(f"ANCV distribution: equity list not found/ambiguous {xml}{delim}")
    txts = [n for n in members if re.search(r"(^|/)LV\d{4}\.txt$", n, re.I)]
    if len(txts) > 1:
        raise DataQualityError(f"ANCV distribution: several TXT lists {txts}")
    txt_dates = parse_fixed_width_txt(members[txts[0]]) if txts else {}
    good: list[AncvEquityLine] = []
    bad: list[AncvEquityLine] = []
    for ln in lines:
        (good if _isin_ok(ln.isin) else bad).append(ln)
    return AncvDistribution(
        ref,
        signals,
        leame,
        member,
        fmt,
        good,
        txts[0] if txts else None,
        txt_dates,
        hashes,
        [b.isin for b in bad],
    )


# ───────────────────────────── ingestion ─────────────────────────────


@dataclass
class AncvIngestReport:
    url: str
    reference_date: date | None = None
    equity_format: str = ""
    lines: int = 0
    inserted: int = 0
    rejected_isins: int = 0
    status: str = "pending"


@dataclass
class CNMVSecurityIdentityProvider:
    store: ArchiveStore

    def ingest_distribution(self, session: Session, url: str, zip_bytes: bytes) -> AncvIngestReport:
        rep = AncvIngestReport(url)
        dist = parse_distribution(zip_bytes)
        rep.reference_date, rep.equity_format = dist.reference_date, dist.equity_format
        notes = json.dumps(
            {
                "source_type": "ancv_semiannual",
                "reference_date": dist.reference_date.isoformat(),
                "date_signals": dist.date_signals,
                "filename": url.rsplit("/", 1)[-1],
                "leame_sha256": dist.leame.sha256,
                "leame_txt_scope": dist.leame.txt_scope,
                "leame_scope_sentence": dist.leame.scope_sentence,
                "leame_only_es_isins": dist.leame.only_es_isins,
                "equity_member": dist.equity_member,
                "equity_format": dist.equity_format,
                "txt_member": dist.txt_member,
                "member_sha256": dist.member_hashes,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        row = archive_document(
            session,
            self.store,
            provider=PROVIDER,
            source_identifier=url,
            data=zip_bytes,
            mime_type="application/zip",
            parser_version=PARSER_VERSION,
            notes=notes,
        )
        member_hash = dist.member_hashes[dist.equity_member]
        seen = set(
            session.scalars(
                select(SecurityIdentitySnapshot.isin).where(
                    SecurityIdentitySnapshot.source == SOURCE,
                    SecurityIdentitySnapshot.reference_date == dist.reference_date,
                    SecurityIdentitySnapshot.source_hash == member_hash,
                )
            )
        )
        rep.lines, rep.rejected_isins = len(dist.equity_lines), len(dist.rejected_isins)
        for ln in dist.equity_lines:
            if ln.isin in seen:
                continue
            seen.add(ln.isin)
            session.add(
                SecurityIdentitySnapshot(
                    source=SOURCE,
                    reference_date=dist.reference_date,
                    scope=dist.scope_of(ln.isin),
                    isin=ln.isin,
                    issuer_legal_name=ln.issuer_legal_name[:300],
                    instrument_name=ln.instrument_name[:300],
                    instrument_class="RV",
                    cfi=ln.cfi,
                    currency=ln.currency,
                    nominal=ln.nominal,
                    issue_date=dist.txt_issue_dates.get(ln.isin),
                    member_name=dist.equity_member[:200],
                    source_hash=member_hash,
                    archive_id=row.archive_id,
                    parser_version=PARSER_VERSION,
                )
            )
            rep.inserted += 1
        session.flush()
        rep.status = "ok"
        return rep


def archived_distributions(session: Session) -> list[RawSourceArchive]:
    return list(
        session.scalars(
            select(RawSourceArchive)
            .where(RawSourceArchive.provider == PROVIDER)
            .order_by(RawSourceArchive.source_identifier)
        )
    )


# ───────────────────────────── ANCV query by NIF ─────────────────────────────

NIF_QUERY_URL = BASE + "/portal/ancv/isin?nif={nif}"


@dataclass(frozen=True)
class NifQueryLine:
    isin: str
    fisn: str
    issue_date: date | None
    cfi: str | None


@dataclass(frozen=True)
class NifQueryResult:
    issuer_name: str
    lines: tuple[NifQueryLine, ...]

    def ordinary_shares(self) -> list[NifQueryLine]:
        return [
            ln
            for ln in self.lines
            if "/AC " in f"{ln.fisn} " and (ln.cfi is None or ln.cfi.startswith("E"))
        ]


def parse_nif_query(page: bytes) -> NifQueryResult:
    """The CNMV ANCV «Consulta de códigos ISIN» by NIF: the ISINs currently ACTIVE for the
    issuer with that NIF (CIF). An official CIF ↔ ISIN link — current only: a retired ISIN
    is not listed, so it proves the link for ISINs active on the retrieval date."""
    import html as _html

    text = _html.unescape(re.sub(r"<[^>]+>", "\n", page.decode("utf-8", errors="replace")))
    toks = [t.strip() for t in text.splitlines() if t.strip()]
    try:
        i = toks.index("Información de códigos ISIN")
    except ValueError as e:
        raise DataQualityError("ANCV NIF query: result block not found") from e
    if any("no ha sido encontrado" in t for t in toks[i : i + 6]):
        raise DataQualityError("ANCV NIF query: no ISIN for that NIF")
    name = toks[i + 2] if toks[i + 1].startswith("Todos los tipos") else toks[i + 1]
    lines = []
    starts = [j for j, t in enumerate(toks) if _ISIN.match(t) and _isin_ok(t)]
    for n, j in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(toks)
        cells = []
        for c in toks[j + 1 : end]:
            if c.startswith("Para más"):
                break
            cells.append(c)
        if not cells:
            continue
        d = next((c for c in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c)), None)
        cfi = next((c for c in reversed(cells) if re.fullmatch(r"[A-Z]{6}", c)), None)
        lines.append(
            NifQueryLine(
                toks[j],
                cells[0],
                date(int(d[6:]), int(d[3:5]), int(d[:2])) if d else None,
                cfi,
            )
        )
    if not lines:
        raise DataQualityError("ANCV NIF query: no ISIN rows parsed")
    return NifQueryResult(name, tuple(lines))
