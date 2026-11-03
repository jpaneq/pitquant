"""Private GitHub release backup/restore. Dry run by default; never delete during backup.

Source data stay private. Restoring streams assets without storing the full compressed archive.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

REPO = "jpaneq/pitquant-backups"
SKIP = {
    ".git",
    ".venv",
    ".btc-venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".pgdata",
    ".hypothesis",
    "backup-upload-20261103",
    "full-backup-stage",
}


def gh(*args: str) -> Any:
    return json.loads(subprocess.check_output(["gh", "api", *args]))


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


@contextmanager
def stable_file(source: Path, directory: Path):
    if source.suffix != ".db":
        yield source
        return
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
        # A rollback-mode read transaction prevents writes while streaming, avoiding
        # a second 10 GB copy. WAL databases require an online snapshot instead.
        src.execute("BEGIN")
        src.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        if src.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            yield source
        else:
            src.rollback()
            target = directory / "snapshot.db"
            with sqlite3.connect(target) as dst:
                src.backup(dst, pages=4096)
            yield target


class PartWriter:
    def __init__(self, directory: Path, tag: str):
        self.directory, self.tag = directory, tag
        self.parts: list[dict[str, Any]] = []
        self.file: BinaryIO | None = None
        self.path: Path | None = None
        self.size = 0

    def publish(self) -> None:
        if self.file is None or self.path is None:
            return
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()
        digest = file_hash(self.path)
        subprocess.run(
            ["gh", "release", "upload", self.tag, str(self.path), "--repo", REPO], check=True
        )
        release = gh(f"repos/{REPO}/releases/tags/{self.tag}")
        asset = next(a for a in release["assets"] if a["name"] == self.path.name)
        if asset.get("digest") != "sha256:" + digest or asset["size"] != self.size:
            raise RuntimeError("Remote asset integrity not verified; local staging retained")
        self.parts.append(
            {"name": self.path.name, "size": self.size, "sha256": digest, "asset_id": asset["id"]}
        )
        self.path.unlink()  # only our newly generated temporary chunk, after server verification
        print("Uploaded and SHA-256 verified", asset["name"], flush=True)
        self.file = None
        self.path = None
        self.size = 0

    def write(self, data: bytes) -> int:
        count = len(data)
        while data:
            if self.file is None:
                self.path = self.directory / f"workspace.tar.gz.part{len(self.parts) + 1:03}"
                self.file = self.path.open("xb")
            n = min(len(data), 1024**3 - self.size)
            self.file.write(data[:n])
            self.size += n
            data = data[n:]
            if self.size == 1024**3:
                self.publish()
        return count

    def flush(self) -> None:
        if self.file:
            self.file.flush()


class HashReader:
    def __init__(self, file: BinaryIO):
        self.file = file
        self.hash = hashlib.sha256()

    def read(self, n: int = -1) -> bytes:
        data = self.file.read(n)
        self.hash.update(data)
        return data


def eligible(root: Path) -> list[Path]:
    files = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            d for d in dirs if d not in SKIP and not (Path(directory) / d).is_symlink()
        )
        for name in sorted(names):
            p = Path(directory) / name
            if (
                p.is_symlink()
                or name.startswith(".env")
                or p.suffix in {".pem", ".key", ".p12"}
                or name.endswith(("-wal", "-shm"))
            ):
                continue
            if "frontend/dist" in str(p.relative_to(root)):
                continue
            files.append(p)
    return files


def backup(root: Path, tag: str, ready: Path | None) -> None:
    if not gh(f"repos/{REPO}")["private"]:
        raise RuntimeError("Private backup repository required")
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            REPO,
            "--title",
            "PITQuant full project backup " + tag,
            "--notes",
            (
                "Private project archive; manifest and SHA-256 parts. "
                "Credentials and rebuildable environments excluded. Originals not deleted."
            ),
        ],
        check=True,
    )
    stage = root / "data/full-backup-stage"
    stage.mkdir(parents=True, exist_ok=True)
    sources = {"project": root}
    for short in ("btc-engine-v0", "us-research-universe-scale-v1"):
        path = Path.home() / ".codex/worktrees" / short / "pitquant"
        if path.exists():
            sources["worktrees/" + short] = path
    manifest: dict[str, Any] = {
        "status": "UPLOADING",
        "repository": REPO,
        "tag": tag,
        "sources": {k: str(v) for k, v in sources.items()},
        "files": {},
        "excluded": [
            *sorted(SKIP),
            "credentials .env/*.pem/*.key/*.p12",
            "WAL/SHM: SQLite files backed up consistently",
        ],
        "created_at": datetime.now(UTC).isoformat(),
        "originals_deleted": False,
    }
    writer = PartWriter(stage, tag)
    with gzip.GzipFile(fileobj=writer, mode="wb", compresslevel=1, mtime=0) as compressed:  # noqa: SIM117
        with tarfile.open(fileobj=compressed, mode="w|") as archive:

            def add(source: Path, name: str) -> None:
                stat = source.stat()
                old = manifest["files"].get(name)
                if (
                    old
                    and old["source_mtime_ns"] == stat.st_mtime_ns
                    and old["source_size"] == stat.st_size
                ):
                    return
                with tempfile.TemporaryDirectory(prefix="pitquant-sqlite-", dir=stage) as tmp:
                    is_db = source.suffix == ".db"
                    with stable_file(source, Path(tmp)) as actual:
                        info = archive.gettarinfo(str(actual), arcname=name)
                        with actual.open("rb") as file:
                            reader = HashReader(file)
                            archive.addfile(info, reader)
                    manifest["files"][name] = {
                        "sha256": reader.hash.hexdigest(),
                        "bytes": info.size,
                        "sqlite_snapshot": is_db,
                        "source_size": stat.st_size,
                        "source_mtime_ns": stat.st_mtime_ns,
                    }
                    if len(manifest["files"]) % 1000 == 0:
                        print("Archived", len(manifest["files"]), "files", flush=True)

            for prefix, directory in sources.items():
                for file in eligible(directory):
                    add(file, prefix + "/" + str(file.relative_to(directory)))
            if ready:
                print("Waiting for final code/model freeze", str(ready), flush=True)
                while not ready.exists():
                    time.sleep(15)
            # Include files created/changed while immutable archives streamed.
            for prefix, directory in sources.items():
                for file in eligible(directory):
                    add(file, prefix + "/" + str(file.relative_to(directory)))
            bundle = stage / "all-refs.bundle"
            subprocess.run(["git", "bundle", "create", str(bundle), "--all"], cwd=root, check=True)
            add(bundle, "git/all-refs.bundle")
            manifest["code_head"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
    writer.publish()
    manifest.update(
        status="ALL_REMOTE_PARTS_VERIFIED",
        parts=writer.parts,
        completed_at=datetime.now(UTC).isoformat(),
    )
    path = stage / "FULL_MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    subprocess.run(["gh", "release", "upload", tag, str(path), "--repo", REPO], check=True)
    print("BACKUP_COMPLETE", tag, "files", len(manifest["files"]), flush=True)


class RemoteReader(io.RawIOBase):
    def __init__(self, parts: list[dict[str, Any]]):
        self.parts = iter(parts)
        self.proc: Any = None
        self.part: dict[str, Any] | None = None
        self.hash = hashlib.sha256()

    def readable(self) -> bool:
        return True

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            raise ValueError("Unbounded reads forbidden")
        while True:
            if self.proc is None:
                try:
                    self.part = next(self.parts)
                except StopIteration:
                    return b""
                self.hash = hashlib.sha256()
                self.proc = subprocess.Popen(
                    [
                        "gh",
                        "api",
                        f"repos/{REPO}/releases/assets/{self.part['asset_id']}",
                        "-H",
                        "Accept: application/octet-stream",
                    ],
                    stdout=subprocess.PIPE,
                )
            data = self.proc.stdout.read(n)
            if data:
                self.hash.update(data)
                return data
            if (
                self.proc.wait()
                or self.part is None
                or self.hash.hexdigest() != self.part["sha256"]
            ):
                raise RuntimeError("Remote part download hash mismatch")
            self.proc = None


def load_manifest(tag: str) -> dict[str, Any]:
    raw = subprocess.check_output(
        [
            "gh",
            "release",
            "download",
            tag,
            "--repo",
            REPO,
            "--pattern",
            "FULL_MANIFEST.json",
            "--output",
            "-",
        ]
    )
    manifest: dict[str, Any] = json.loads(raw)
    if manifest["status"] != "ALL_REMOTE_PARTS_VERIFIED":
        raise RuntimeError("Incomplete backup")
    return manifest


def restore(tag: str, destination: Path | None, minimal: bool = False) -> None:
    manifest = load_manifest(tag)
    reader = RemoteReader(manifest["parts"])
    got = {}
    with tarfile.open(fileobj=reader, mode="r|gz") as archive:
        for member in archive:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise RuntimeError("Unsafe archive member")
            src = archive.extractfile(member)
            assert src is not None
            h = hashlib.sha256()
            selected = not minimal or member.name.startswith(
                (
                    "project/data/pitquant.db",
                    "project/data/forward-pilots-v1/",
                    "project/data/reports/",
                    "worktrees/btc-engine-v0/data/",
                )
            )
            target = destination / path if destination and selected else None
            if target:
                target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") if target else open(os.devnull, "wb") as output:
                for block in iter(lambda src=src: src.read(4 * 1024**2), b""):
                    h.update(block)
                    output.write(block)
            got[member.name] = {"sha256": h.hexdigest(), "bytes": member.size}
    # Drain gzip/tar trailing bytes so every part's hash is checked too.
    while reader.read(4 * 1024**2):
        pass
    for name, expected in manifest["files"].items():
        if got.get(name) != {k: expected[k] for k in ("sha256", "bytes")}:
            raise RuntimeError("Restored file integrity error: " + name)
    receipt = {
        "status": "EVERY_ARCHIVED_FILE_STREAM_RESTORED_AND_HASH_VERIFIED",
        "files": len(got),
        "tag": tag,
        "verified_at": datetime.now(UTC).isoformat(),
    }
    if destination:
        (destination / "RESTORE_VERIFIED.json").write_text(json.dumps(receipt, indent=2) + "\n")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "FULL_RESTORE_VERIFIED.json"
            p.write_text(json.dumps(receipt, indent=2) + "\n")
            release = gh(f"repos/{REPO}/releases/tags/{tag}")
            if not any(a["name"] == p.name for a in release["assets"]):
                subprocess.run(["gh", "release", "upload", tag, str(p), "--repo", REPO], check=True)
            # A repeated successful verification must not fail or overwrite its
            # first durable receipt merely because that receipt already exists.
    print(json.dumps(receipt))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "backup", "verify", "restore"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--tag", default="full-project-2026-11-03-v2")
    parser.add_argument("--ready", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--minimal", action="store_true")
    args = parser.parse_args()
    if args.action == "backup":
        backup(args.root.resolve(), args.tag, args.ready)
    elif args.action == "verify":
        restore(args.tag, None)
    elif args.action == "restore":
        if not args.destination or args.destination.exists():
            raise ValueError("Choose a NEW empty destination path")
        args.destination.mkdir(parents=True)
        restore(args.tag, args.destination, args.minimal)
    else:
        files = eligible(args.root)
        print(
            json.dumps(
                {
                    "files": len(files),
                    "logical_bytes": sum(p.stat().st_size for p in files),
                    "deletion_performed": False,
                }
            )
        )


if __name__ == "__main__":
    main()
