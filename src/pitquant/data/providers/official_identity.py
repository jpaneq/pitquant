"""Official identity documents: fetch, archive, verify, record (ADR-0022).

A claim (an ISIN transition, or a «code ↔ ISIN» statement) is recorded ONLY if every
regular expression of its ``Doc.checks`` matches the text of the archived original (PDF text
layer, or OCR for scanned PDFs). The registry only says WHERE to look and WHICH sentences must
be there; it is never evidence by itself. No match → no row (the case stays UNRESOLVED).

Documents may be fetched directly or from an Internet Archive capture of the official URL
(``via="wayback"``: the original official URL moved or was withdrawn); both are archived with
URL, retrieved_at and SHA-256 in ``raw_source_archive``.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models import (
    OfficialCodeIsinEvidence,
    OfficialIsinTransition,
    SecurityIdentitySnapshot,
)

PARSER_VERSION = "official-identity-1"
PROVIDER = "OFFICIAL_IDENTITY_DOCS"
UA = "Mozilla/5.0 (compatible; PITQuant research)"
ROOT = Path(__file__).resolve().parents[4]
OCR_SRC = ROOT / "scripts" / "tools" / "ocr_pdf.swift"


@dataclass(frozen=True)
class Doc:
    role: str
    url: str
    checks: tuple[str, ...]
    via: Literal["direct", "wayback"] = "direct"
    wayback_ts: str | None = None  # 14-digit capture stamp when via == "wayback"


@dataclass(frozen=True)
class TransitionSpec:
    key: str
    issuer: str
    old_isin: str
    new_isin: str
    kind: str
    continuity: Literal["SAME_SECURITY", "NEW_SECURITY"]
    effective: date
    docs: tuple[Doc, ...]
    # cross-check with the ANCV snapshots already ingested: (old nominal, new nominal) as
    # published in ``Valor_Nominal`` (e.g. ("2,00", "0,50")); None = no nominal change
    nominals: tuple[str, str] | None = None


@dataclass(frozen=True)
class CodeEvidenceSpec:
    key: str
    code: str
    isin: str
    observed_on: date
    issuer: str
    doc: Doc
    kind: str = "OFFICIAL_DOCUMENT"


@dataclass
class VerifiedDoc:
    doc: Doc
    sha256: str
    archive_id: str
    method: str  # TEXT_LAYER | OCR_APPLE_VISION | HTML
    excerpts: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _http(url: str) -> bytes:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                body: bytes = r.read()
            time.sleep(1.0)
            return body
        except Exception as e:
            last = e
            time.sleep(4 * (i + 1))
    raise DataQualityError(f"fetch failed {url}: {last}")


def fetch(doc: Doc) -> tuple[bytes, str]:
    """(bytes, source_identifier). Wayback captures use the raw ``id_`` form."""
    if doc.via == "wayback":
        if not doc.wayback_ts:
            raise DataQualityError(f"{doc.url}: wayback capture stamp missing")
        u = f"http://web.archive.org/web/{doc.wayback_ts}id_/{doc.url}"
        return _http(u), u
    return _http(doc.url), doc.url


def ocr_binary() -> Path:
    """Apple Vision OCR tool, compiled on first use (macOS only)."""
    out = Path(os.environ.get("PITQUANT_OCR_BIN", ROOT / "data" / "tools" / "ocr_pdf"))
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["swiftc", "-O", str(OCR_SRC), "-o", str(out)], capture_output=True, text=True
        )
        if r.returncode != 0:
            raise DataQualityError(f"OCR tool unavailable: {r.stderr[:200]}")
    return out


def extract_text(data: bytes) -> tuple[str, str]:
    if data[:5] == b"%PDF-":
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = " ".join((p.extract_text() or "") for p in pdf.pages)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 120:
            return text, "TEXT_LAYER"
        with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
            fh.write(data)
            fh.flush()
            r = subprocess.run(
                [str(ocr_binary()), fh.name], capture_output=True, text=True, timeout=300
            )
        if r.returncode != 0:
            raise DataQualityError(f"OCR failed: {r.stderr[:200]}")
        return re.sub(r"\s+", " ", r.stdout).strip(), "OCR_APPLE_VISION"
    s = data.decode("utf-8", errors="replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip(), "HTML"


def verify_doc(session: Session, store: ArchiveStore, doc: Doc) -> VerifiedDoc:
    data, source_id = fetch(doc)
    if data[:5] != b"%PDF-" and "<title>La Bolsa es ahora BME Exchange" in data[:4000].decode(
        "utf-8", "replace"
    ):
        raise DataQualityError(f"{doc.url}: BME redirected to its home page (document moved)")
    text, method = extract_text(data)
    mime = "application/pdf" if data[:5] == b"%PDF-" else "text/html"
    row = archive_document(
        session,
        store,
        provider=PROVIDER,
        source_identifier=source_id,
        data=data,
        mime_type=mime,
        parser_version=PARSER_VERSION,
        notes=json.dumps(
            {
                "role": doc.role,
                "via": doc.via,
                "original_url": doc.url,
                "wayback_ts": doc.wayback_ts,
                "extraction": method,
            }
        ),
    )
    v = VerifiedDoc(doc, row.sha256, row.archive_id, method)
    for rx in doc.checks:
        m = re.search(rx, text, flags=re.I)
        if m:
            v.excerpts.append(text[max(0, m.start() - 20) : m.end() + 20][:300])
        else:
            v.failed.append(rx)
    return v


def _ancv_nominals(session: Session, isin: str) -> set[str]:
    return {
        n
        for n in session.scalars(
            select(SecurityIdentitySnapshot.nominal).where(SecurityIdentitySnapshot.isin == isin)
        )
        if n
    }


@dataclass
class Outcome:
    key: str
    ok: bool
    notes: list[str]


def record_transition(session: Session, store: ArchiveStore, t: TransitionSpec) -> Outcome:
    notes: list[str] = []
    verified: list[VerifiedDoc] = []
    for d in t.docs:
        try:
            v = verify_doc(session, store, d)
        except DataQualityError as e:
            return Outcome(t.key, False, [f"{d.role}: {e}"])
        verified.append(v)
        if v.failed:
            notes.append(f"{d.role} ({v.method}): NOT SUPPORTED — missing {v.failed}")
    if any(v.failed for v in verified):
        return Outcome(t.key, False, notes)
    if t.nominals is not None:
        old_n, new_n = _ancv_nominals(session, t.old_isin), _ancv_nominals(session, t.new_isin)
        if t.nominals[0] not in old_n or t.nominals[1] not in new_n:
            return Outcome(
                t.key,
                False,
                [
                    f"ANCV nominal cross-check failed: old {old_n} vs {t.nominals[0]}, "
                    f"new {new_n} vs {t.nominals[1]}"
                ],
            )
        notes.append(f"ANCV nominals confirm {t.nominals[0]} -> {t.nominals[1]}")
    exists = session.scalars(
        select(OfficialIsinTransition).where(
            OfficialIsinTransition.old_isin == t.old_isin,
            OfficialIsinTransition.new_isin == t.new_isin,
            OfficialIsinTransition.effective_date == t.effective,
        )
    ).first()
    if exists is None:
        session.add(
            OfficialIsinTransition(
                issuer_name=t.issuer,
                old_isin=t.old_isin,
                new_isin=t.new_isin,
                kind=t.kind,
                continuity=t.continuity,
                effective_date=t.effective,
                documents=[
                    {
                        "role": v.doc.role,
                        "url": v.doc.url,
                        "via": v.doc.via,
                        "wayback_ts": v.doc.wayback_ts,
                        "sha256": v.sha256,
                        "archive_id": v.archive_id,
                        "extraction": v.method,
                        "excerpts": v.excerpts,
                    }
                    for v in verified
                ],
                parser_version=PARSER_VERSION,
            )
        )
        session.flush()
    return Outcome(t.key, True, [*notes, f"{len(verified)} documents verified"])


def record_code_evidence(session: Session, store: ArchiveStore, c: CodeEvidenceSpec) -> Outcome:
    try:
        v = verify_doc(session, store, c.doc)
    except DataQualityError as e:
        return Outcome(c.key, False, [str(e)])
    if v.failed:
        return Outcome(c.key, False, [f"{c.doc.role} ({v.method}): NOT SUPPORTED — {v.failed}"])
    exists = session.scalars(
        select(OfficialCodeIsinEvidence).where(
            OfficialCodeIsinEvidence.source_sha256 == v.sha256,
            OfficialCodeIsinEvidence.code == c.code,
            OfficialCodeIsinEvidence.isin == c.isin,
            OfficialCodeIsinEvidence.observed_on == c.observed_on,
        )
    ).first()
    if exists is None:
        session.add(
            OfficialCodeIsinEvidence(
                code=c.code,
                isin=c.isin,
                observed_on=c.observed_on,
                issuer_name=c.issuer,
                market=None,
                source_kind=c.kind,
                source_url=c.doc.url,
                capture_timestamp=c.doc.wayback_ts,
                archive_id=v.archive_id,
                source_sha256=v.sha256,
                parser_version=PARSER_VERSION,
            )
        )
        session.flush()
    return Outcome(c.key, True, [f"{v.method}; excerpt: {v.excerpts[0][:120]}"])
