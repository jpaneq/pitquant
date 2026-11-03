"""Prepare or remove only data proven identical to a fully restored private backup.

Default: audit only. Stop the app/automations first. Any unbacked or changed file
blocks execution. Code, credentials and Git history are never deleted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from project_backup import REPO, SKIP, file_hash, load_manifest


def assert_not_open(files: list[Path]) -> None:
    probe = subprocess.run(["lsof", "-nP", "-Fn"], capture_output=True, text=True)
    if probe.returncode not in (0, 1):
        raise RuntimeError("Cannot inspect open files; deletion blocked")
    opened = {line[1:] for line in probe.stdout.splitlines() if line.startswith("n")}
    conflicts = opened.intersection(str(p) for p in files)
    if conflicts:
        raise RuntimeError("Stop local services first; open files: " + ", ".join(sorted(conflicts)))


def plan(tag: str) -> list[Path]:
    manifest = load_manifest(tag)
    receipt = json.loads(
        subprocess.check_output(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                REPO,
                "--pattern",
                "FULL_RESTORE_VERIFIED.json",
                "--output",
                "-",
            ]
        )
    )
    if (
        receipt["status"] != "EVERY_ARCHIVED_FILE_STREAM_RESTORED_AND_HASH_VERIFIED"
        or receipt["tag"] != tag
        or receipt["files"] != len(manifest["files"])
    ):
        raise RuntimeError("Full restore verification required before deletion")
    candidates = []
    errors = []
    sources = {key: Path(value) for key, value in manifest["sources"].items()}
    for prefix, root in sources.items():
        data = root / "data"
        if data.is_symlink() or not data.exists():
            continue
        # Include ignored/untracked new data in this check, never silently remove them.
        for p in data.rglob("*"):
            if p.is_symlink() or not p.is_file() or set(p.relative_to(data).parts) & SKIP:
                continue
            if p.name.endswith(("-wal", "-shm", "-journal")):
                errors.append(f"Database still active or uncheckpointed: {p}")
                continue
            key = prefix + "/" + str(p.relative_to(root))
            expected = manifest["files"].get(key)
            if (
                expected is None
                or p.stat().st_size != expected["bytes"]
                or file_hash(p) != expected["sha256"]
            ):
                errors.append(f"Changed/unbacked file: {p}")
            else:
                candidates.append(p)
    if errors:
        raise RuntimeError("\n".join(errors[:30]) + f"\nBlocked: {len(errors)} files")
    assert_not_open(candidates)
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="full-project-2026-11-03-v2")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    files = plan(args.tag)
    total = sum(p.stat().st_size for p in files)
    print(
        json.dumps(
            {"files": len(files), "bytes": total, "mode": "EXECUTE" if args.execute else "DRY_RUN"}
        )
    )
    if args.execute:
        if args.confirm != "DELETE_BACKED_UP_LOCAL_DATA":
            raise ValueError("Explicit confirmation required; nothing deleted")
        # Single process inventory rather than tens of thousands of lsof calls.
        assert_not_open(files)
        manifest = load_manifest(args.tag)
        expected_by_path = {
            str(Path(root) / name.removeprefix(prefix + "/")): item
            for prefix, root in manifest["sources"].items()
            for name, item in manifest["files"].items()
            if name.startswith(prefix + "/")
        }
        for p in files:
            item = expected_by_path[str(p)]
            if p.stat().st_size != item["bytes"] or file_hash(p) != item["sha256"]:
                raise RuntimeError(f"Changed file, deletion stopped: {p}")
            p.unlink()
        print("Verified data removed. Git, code, credentials and backup receipts preserved.")


if __name__ == "__main__":
    main()
