"""Small immutable artifact publication, verified before journal references."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def publish(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("ARTIFACT_CONFLICT")
        return
    fd, name = tempfile.mkstemp(prefix=".pilot-", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.link(tmp, path)  # exclusive publication, never overwrite
        if path.read_bytes() != data:
            raise ValueError("ARTIFACT_INTEGRITY_ERROR")
    finally:
        tmp.unlink(missing_ok=True)
