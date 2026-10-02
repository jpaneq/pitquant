"""Official identity documents: ficha parser (REAL excerpt of a Bolsa de Madrid page copy) and
the verify-then-record rule (documents are FIXTURES; only text that is really in the
document may become evidence)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore
from pitquant.data.providers import official_identity as oi
from pitquant.data.providers.bme.ficha import parse_ficha
from pitquant.db.models import (
    OfficialCodeIsinEvidence,
    OfficialIsinTransition,
    SecurityIdentitySnapshot,
)

pytestmark = pytest.mark.pit
REAL = Path(__file__).resolve().parents[1] / "fixtures" / "bme_real"


def test_real_ficha_excerpt_states_code_isin_and_its_own_date() -> None:
    e = parse_ficha((REAL / "ficha_MTS_20130711_excerpt.html").read_bytes())
    assert (e.code, e.isin, e.issuer_name) == ("MTS", "LU0323134006", "ARCELORMITTAL, S.A.")
    assert e.page_date == date(2013, 7, 11) and e.is_live_listing()


def test_stale_page_of_a_cancelled_security_is_not_a_presence_claim() -> None:
    page = (REAL / "ficha_MTS_20130711_excerpt.html").read_text()
    stale = page.replace("11/07/2013 0:02:32", "02/03/2018 0:02:32")  # served later, prices old
    e = parse_ficha(stale.encode())
    assert e.page_date == date(2018, 3, 2) and not e.is_live_listing()


def test_unknown_layout_fails_closed() -> None:
    with pytest.raises(DataQualityError):
        parse_ficha(b"<html><title>other</title></html>")


# ───────────────────────── verify-then-record ─────────────────────────


def _pdf(text: str) -> bytes:
    """A tiny valid PDF carrying ``text`` (text layer), built in memory."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return out


TEXT = (
    "Instruccion Operativa 26/2023 FERROVIAL SE codigo ISIN NL0015001FS8 bajo el codigo FER "
    "a partir del dia de su admision prevista para el dia 16 de junio. "
    "Texto de relleno para superar el umbral de la capa de texto del extractor documental."
)


def _fake(monkeypatch: pytest.MonkeyPatch, data: bytes) -> None:
    monkeypatch.setattr(oi, "fetch", lambda doc: (data, doc.url))


def test_claim_is_recorded_only_when_every_sentence_is_in_the_document(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake(monkeypatch, _pdf(TEXT))
    store = ArchiveStore(tmp_path)
    good = oi.CodeEvidenceSpec(
        "k",
        "FER",
        "NL0015001FS8",
        date(2023, 6, 16),
        "FERROVIAL SE",
        oi.Doc("IO", "https://x/io.pdf", (r"codigo ISIN NL0015001FS8", r"bajo el codigo FER")),
    )
    assert oi.record_code_evidence(session, store, good).ok
    row = session.scalars(select(OfficialCodeIsinEvidence)).one()
    assert (row.code, row.isin, row.observed_on) == ("FER", "NL0015001FS8", date(2023, 6, 16))
    assert len(row.source_sha256) == 64
    again = oi.record_code_evidence(session, store, good)  # idempotent
    assert again.ok and session.query(OfficialCodeIsinEvidence).count() == 1
    bad = oi.CodeEvidenceSpec(
        "k2",
        "FER",
        "ES0118900010",
        date(2023, 6, 16),
        "FERROVIAL",
        oi.Doc("IO", "https://x/io.pdf", (r"codigo ISIN ES0118900010",)),
    )
    out = oi.record_code_evidence(session, store, bad)
    assert not out.ok and "NOT SUPPORTED" in out.notes[0]
    assert session.query(OfficialCodeIsinEvidence).count() == 1  # nothing recorded


def test_transition_needs_documents_and_the_ancv_nominal_crosscheck(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake(monkeypatch, _pdf(TEXT))
    store = ArchiveStore(tmp_path)
    doc = oi.Doc("IO", "https://x/io.pdf", (r"ISIN NL0015001FS8",))
    spec = oi.TransitionSpec(
        "t",
        "FERROVIAL",
        "ES0118900010",
        "NL0015001FS8",
        "CROSS_BORDER_MERGER",
        "NEW_SECURITY",
        date(2023, 6, 16),
        (doc,),
    )
    assert oi.record_transition(session, store, spec).ok
    t = session.scalars(select(OfficialIsinTransition)).one()
    assert t.continuity == "NEW_SECURITY" and t.documents[0]["sha256"]
    # nominal cross-check: ANCV must show the stated nominals or nothing is recorded
    split = oi.TransitionSpec(
        "s",
        "RED",
        "ES0173093115",
        "ES0173093024",
        "SPLIT",
        "SAME_SECURITY",
        date(2016, 7, 11),
        (oi.Doc("IO", "https://x/io.pdf", (r"FERROVIAL",)),),
        nominals=("2,00", "0,50"),
    )
    refused = oi.record_transition(session, store, split)
    assert not refused.ok and "nominal cross-check failed" in refused.notes[0]
    from pitquant.db.models import RawSourceArchive

    arch = session.query(RawSourceArchive).first()
    assert arch is not None
    for isin, nom in (("ES0173093115", "2,00"), ("ES0173093024", "0,50")):
        session.add(
            SecurityIdentitySnapshot(
                source="CNMV_ANCV",
                reference_date=date(2016, 6, 30),
                scope="ADMITTED_TO_TRADING",
                isin=isin,
                issuer_legal_name="FIXTURE",
                instrument_name="REE/AC",
                instrument_class="RV",
                nominal=nom,
                member_name="f",
                source_hash="0" * 64,
                archive_id=arch.archive_id,
                parser_version="fixture",
            )
        )
    session.flush()
    assert oi.record_transition(session, store, split).ok


def test_bme_homepage_instead_of_the_pdf_is_refused(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake(monkeypatch, b"<!doctype html><html><head><title>La Bolsa es ahora BME Exchange</title>")
    spec = oi.CodeEvidenceSpec(
        "h", "FER", "NL0015001FS8", date(2023, 6, 16), "F", oi.Doc("IO", "https://x", (r"x",))
    )
    out = oi.record_code_evidence(session, ArchiveStore(tmp_path), spec)
    assert not out.ok and "home page" in out.notes[0]
