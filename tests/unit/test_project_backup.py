"""Synthetic backup/restore and deletion refusal; no user files or network calls."""

from __future__ import annotations

import importlib
import io
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest
from scripts import project_backup as backup


def test_stable_sqlite_stream_prevents_writer_without_full_copy(tmp_path):
    p = tmp_path / "source.db"
    with sqlite3.connect(p) as conn:
        conn.execute("CREATE TABLE x (value INTEGER)")
        conn.execute("INSERT INTO x VALUES (1)")
    before = backup.file_hash(p)
    with backup.stable_file(p, tmp_path) as actual:
        assert actual == p
        with (
            pytest.raises(sqlite3.OperationalError, match="locked"),
            sqlite3.connect(p, timeout=0) as writer,
        ):
            writer.execute("UPDATE x SET value = 2")
            writer.commit()
    assert backup.file_hash(p) == before


def test_restore_stream_checks_every_member_and_duplicate_latest(tmp_path, monkeypatch):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as archive:
        for value in [b"old", b"new"]:
            info = tarfile.TarInfo("project/data/example.txt")
            info.size = len(value)
            archive.addfile(info, io.BytesIO(value))
    import hashlib

    manifest = {
        "status": "ALL_REMOTE_PARTS_VERIFIED",
        "parts": [],
        "files": {
            "project/data/example.txt": {"sha256": hashlib.sha256(b"new").hexdigest(), "bytes": 3}
        },
    }
    monkeypatch.setattr(backup, "load_manifest", lambda _: manifest)
    monkeypatch.setattr(backup, "RemoteReader", lambda _: io.BytesIO(b.getvalue()))
    backup.restore("synthetic", tmp_path)
    assert (tmp_path / "project/data/example.txt").read_bytes() == b"new"
    assert (tmp_path / "RESTORE_VERIFIED.json").exists()
    manifest["files"]["project/data/example.txt"]["sha256"] = "bad"
    with pytest.raises(RuntimeError, match="integrity"):
        backup.restore("synthetic", tmp_path)


def cleanup_module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("local_data_cleanup")


@pytest.mark.parametrize("changed", [False, True])
def test_cleanup_is_plan_only_and_refuses_unbacked_changes(tmp_path, monkeypatch, changed):
    module = cleanup_module(monkeypatch)
    data = tmp_path / "data"
    data.mkdir()
    p = data / "original.txt"
    p.write_text("keep")
    manifest = {
        "sources": {"project": str(tmp_path)},
        "files": {"project/data/original.txt": {"bytes": 4, "sha256": backup.file_hash(p)}},
    }
    receipt = {
        "status": "EVERY_ARCHIVED_FILE_STREAM_RESTORED_AND_HASH_VERIFIED",
        "tag": "synthetic",
        "files": 1,
    }
    monkeypatch.setattr(module, "load_manifest", lambda _: manifest)
    monkeypatch.setattr(module.subprocess, "check_output", lambda _: json.dumps(receipt).encode())
    monkeypatch.setattr(module, "assert_not_open", lambda _: None)
    if changed:
        p.write_text("changed")
        with pytest.raises(RuntimeError, match="Changed/unbacked"):
            module.plan("synthetic")
    else:
        assert module.plan("synthetic") == [p]
    assert p.exists()


def test_cleanup_missing_restore_receipt_blocks(tmp_path, monkeypatch):
    module = cleanup_module(monkeypatch)
    monkeypatch.setattr(module, "load_manifest", lambda _: {"files": {}})
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda _: json.dumps({"status": "UPLOADED_ONLY", "tag": "synthetic", "files": 0}).encode(),
    )
    with pytest.raises(RuntimeError, match="restore verification"):
        module.plan("synthetic")
