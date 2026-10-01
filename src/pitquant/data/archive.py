"""Raw source archive: content-addressed storage of external documents (RAW SOURCE ARCHIVE).

Bytes live on disk at ``<root>/<sha[:2]>/<sha[2:4]>/<sha>``; each retrieval is a row in
``raw_source_archive``. Reads re-verify the SHA-256, so silent corruption or tampering
fails loudly instead of feeding a reconstruction.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.core.timeutils import require_aware, utc_now
from pitquant.db.models import RawSourceArchive


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ArchiveStore:
    root: Path

    def path_for(self, sha: str) -> Path:
        return self.root / sha[:2] / sha[2:4] / sha

    def put(self, data: bytes) -> tuple[str, Path]:
        sha = sha256_hex(data)
        dest = self.path_for(sha)
        if dest.exists():
            if sha256_hex(dest.read_bytes()) != sha:
                raise DataQualityError(f"archive object {sha} is corrupted on disk")
            return sha, dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, dest)  # atomic: never a half-written object
        return sha, dest

    def get(self, sha: str) -> bytes:
        data = self.path_for(sha).read_bytes()
        if sha256_hex(data) != sha:
            raise DataQualityError(f"archive object {sha} failed hash verification")
        return data


def archive_document(
    session: Session,
    store: ArchiveStore,
    *,
    provider: str,
    source_identifier: str,
    data: bytes,
    mime_type: str,
    published_at: datetime | None = None,
    parser_version: str | None = None,
    retrieved_at: datetime | None = None,
    notes: str | None = None,
) -> RawSourceArchive:
    """Store bytes and record the retrieval. Identical (source, hash) retrievals are reused
    so re-running an ingestion is idempotent. The declared MIME type must match the content
    (a URL ending in .pdf can serve an HTML page): a mismatch is refused, not archived."""
    check_mime(data, mime_type, source_identifier)
    sha, path = store.put(data)
    if published_at is not None:
        require_aware(published_at, "published_at")
    existing = session.scalars(
        select(RawSourceArchive).where(
            RawSourceArchive.provider == provider,
            RawSourceArchive.source_identifier == source_identifier,
            RawSourceArchive.sha256 == sha,
        )
    ).first()
    if existing is not None:
        return existing
    row = RawSourceArchive(
        provider=provider,
        source_identifier=source_identifier,
        retrieved_at=retrieved_at or utc_now(),
        published_at=published_at,
        sha256=sha,
        mime_type=mime_type,
        size_bytes=len(data),
        storage_uri=str(path),
        parser_version=parser_version,
        notes=notes,
    )
    session.add(row)
    session.flush()
    return row


_MAGIC = {
    "application/pdf": (b"%PDF-",),
    "application/zip": (b"PK\x03\x04",),
}


def check_mime(data: bytes, mime_type: str, source: str = "") -> None:
    head = data[:1024].lstrip()
    magic = _MAGIC.get(mime_type)
    if magic and not any(head.startswith(m) for m in magic):
        kind = "HTML" if head[:15].lower().startswith((b"<!doctype html", b"<html")) else "other"
        raise DataQualityError(
            f"{source}: declared {mime_type} but content is {kind} — refusing to archive"
        )
    if mime_type in ("application/json", "text/csv", "text/plain", "application/xml") and (
        head[:15].lower().startswith((b"<!doctype html", b"<html"))
    ):
        raise DataQualityError(f"{source}: declared {mime_type} but content is HTML")


def load_archived(session: Session, store: ArchiveStore, archive_id: str) -> bytes:
    row = session.get_one(RawSourceArchive, archive_id)
    return store.get(row.sha256)
