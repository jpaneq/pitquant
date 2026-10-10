#!/usr/bin/env python3
"""Ingest only the capacity-affected CIKs, exclusively from the bounded retry cache."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from pitquant.config.settings import get_settings
from pitquant.data.providers.sec_edgar.client import SECClient
from pitquant.data.providers.sec_edgar.provider import ingest_sec_company
from pitquant.jobs.sec_ingest import security_for_cik
from pitquant.research import us_universe_scale as U
from pitquant.research.us_sec_collection import OfflineTransport

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"


def pipeline() -> Any:
    spec = importlib.util.spec_from_file_location(
        "scale_pipeline", ROOT / "scripts/scale_us_research_universe.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.WORK, module.DB = WORK, WORK / "candidate.db"
    return module


def main() -> None:
    retry = json.loads((WORK / "storage_retry.json").read_bytes())
    ciks = sorted({r["cik"] for r in retry if r["cik"]})
    if len(ciks) != 39:
        raise ValueError("exact frozen 39 CIKs required")
    stage = pipeline()
    cfg = get_settings()
    done_path = WORK / "capacity_ingestion.json"
    done = json.loads(done_path.read_bytes()) if done_path.exists() else {}
    with stage.session_factory()() as session:
        cache = stage.cache_from_database(session)
        client = SECClient(
            OfflineTransport(cache),
            os.environ["PITQUANT_SEC_USER_AGENT"],
            max_requests_per_second=6,
            max_retries=0,
            sleep=lambda _: None,
        )
        provider = stage.BoundedSECProvider(
            client,
            stage.STORE,
            cfg.fundamentals.sec.model_copy(update={"coverage_start": U.PRICE_START}),
        )
        for cik in ciks:
            if cik in done:
                continue
            try:
                sid = security_for_cik(session, cfg, cik, register=True)
                report = ingest_sec_company(session, provider, cik, sid)
                done[cik] = {
                    "status": "COMPLETE"
                    if not report.issues
                    and not report.filings_unresolved
                    and not report.facts_rejected
                    else "PARTIAL",
                    "filings_added": report.filings_inserted,
                    "facts_added": report.facts_inserted,
                    "filings_unresolved": report.filings_unresolved,
                    "facts_rejected": report.facts_rejected,
                    "issues": report.issues,
                    "facts_excluded_without_cached_header": provider.excluded_without_cached_header,
                }
                session.commit()
            except Exception as exc:
                session.rollback()
                done[cik] = {
                    "status": "FAILED",
                    "error": type(exc).__name__ + ": " + str(exc)[:180],
                }
            U.write_revision(WORK, "capacity_ingestion", done)
            done_path.write_bytes(U.encoded(done))
            print(
                f"capacity ingestion {len(done)}/39 {cik} " + U.encoded(done[cik]).decode()[:180],
                flush=True,
            )
        cache.http.close()


if __name__ == "__main__":
    main()
