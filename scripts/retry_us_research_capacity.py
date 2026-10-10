#!/usr/bin/env python3
"""Retry the frozen capacity-only SEC URL list; append revisions, no new discovery."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pitquant.data.archive import ArchiveStore
from pitquant.research import us_universe_scale as U

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"


def main() -> None:
    before = json.loads((WORK / "storage-retry-before.json").read_bytes())
    urls = {r["url"] for r in before}
    if len(urls) != 186 or any(r.get("error") != "DISK_CAPACITY_RESERVE_5_GIB" for r in before):
        raise ValueError("the frozen 186 capacity failures are required")
    original = ROOT / "data/research/us-universe-scale-v1/cache/requests.jsonl"
    ledger = WORK / "cache/requests.jsonl"
    if not ledger.exists():
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_bytes(original.read_bytes())
    cache = U.EvidenceCache(
        ledger.parent, ArchiveStore(ROOT / "data/archive"), os.environ["PITQUANT_SEC_USER_AGENT"]
    )
    results = []
    try:
        for url in sorted(urls):
            prior = cache.records[url]
            if prior.get("error") == "DISK_CAPACITY_RESERVE_5_GIB":
                del cache.records[url]
                cache.get(url)
            current = cache.records[url]
            match = re.search(r"(?:CIK|/data/)(\d+)", url)
            results.append(
                {
                    "url": url,
                    "cik": match.group(1).zfill(10) if match else None,
                    "before": next(r for r in before if r["url"] == url),
                    "after": current,
                }
            )
            U.write_revision(WORK, "storage_retry", results)
            print(f"capacity retry {len(results)}/186 status={current['status']}", flush=True)
    finally:
        cache.http.close()
    (WORK / "storage_retry.json").write_bytes(U.encoded(results))


if __name__ == "__main__":
    main()
