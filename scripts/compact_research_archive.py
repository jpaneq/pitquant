#!/usr/bin/env python3
"""Lossless APFS archive compaction; paths and original document hashes stay intact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact(path: Path) -> dict[str, int | str]:
    """Verify both copies before atomic replacement; never unlink the source first."""
    expected = path.name
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("only content-addressed source objects can be compacted")
    if checksum(path) != expected:
        raise ValueError(f"original source hash mismatch: {expected}")
    before = path.stat()
    temporary = path.with_name(path.name + ".compacting")
    if temporary.exists():
        raise ValueError(f"unfinished compaction requires inspection: {temporary}")
    try:
        subprocess.run(
            ["ditto", "--hfsCompression", "--noclone", str(path), str(temporary)],
            check=True,
            capture_output=True,
        )
        after = temporary.stat()
        if after.st_size != before.st_size or checksum(temporary) != expected:
            raise ValueError(f"compressed source hash mismatch: {expected}")
        if after.st_blocks < before.st_blocks:
            os.replace(temporary, path)
        else:
            temporary.unlink()
        final = path.stat()
        return {
            "sha256": expected,
            "logical_bytes": final.st_size,
            "allocated_before": before.st_blocks * 512,
            "allocated_after": final.st_blocks * 512,
            "bytes_saved": (before.st_blocks - final.st_blocks) * 512,
        }
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--target-free-gib", type=float, default=20)
    args = parser.parse_args()
    if platform.system() != "Darwin":
        parser.error("APFS compaction requires macOS; no archive mutation attempted")
    root = args.archive.resolve()
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    objects = sorted(
        (p for p in root.glob("*/*/*") if p.is_file() and len(p.name) == 64),
        key=lambda p: (-p.stat().st_blocks, str(p)),
    )
    with args.ledger.open("a") as ledger:
        for path in objects:
            if shutil.disk_usage(root).free >= args.target_free_gib * 1024**3:
                break
            result = compact(path)
            ledger.write(json.dumps(result, sort_keys=True) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
    print(json.dumps({"free_bytes": shutil.disk_usage(root).free, "ledger": str(args.ledger)}))


if __name__ == "__main__":
    main()
