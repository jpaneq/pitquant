"""Rebuild the LOCAL real-data database from official sources (network + contact UA).

    mv data/pitquant.db data/pitquant_prev.db   # keep the previous one: never delete history
    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db PITQUANT_SEC_USER_AGENT="... e-mail" \
        python scripts/rebuild_real_data.py

Steps: schema (alembic) → SEC (MSFT, AAPL) → BME documents → CNMV slice (Enagás) → ANCV
identity snapshots + NIF queries → IBEX build + identity resolution → EDGAR time
investigation → D-05 evidence → real-data demos.
The raw archive is content-addressed, so already-archived bytes are reused.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.providers.cnmv.provider import (  # noqa: E402
    CNMVFundamentalProvider,
    Fetcher,
    ingest_cnmv_report,
)
from pitquant.db.models import DataQualityIssue  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

BME = [
    "https://www.bolsasymercados.es/bme-exchange/docs/SB/compoibex.pdf",
    "https://www.bolsasymercados.es/dam/descargas/indices/composicion-ibex-35-es-en.pdf",
]
NOTICE = (
    "https://www.bolsasymercados.es/dam/descargas/indices/notices/index-manager/"
    "ag1526eng-revision.pdf"
)
OBSERVATION = ROOT / "data" / "sources" / "bme_ibex35_current_constituents_20261001.json"
ENAGAS = ("A-28294726", ["2017082262", "2018023181", "2018085463", "2019025071", "2019090846"])


def run(*cmd: str) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def get(url: str) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "PITQuant research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), r.headers.get("Last-Modified")


def main() -> int:
    run("alembic", "upgrade", "head")
    run("pitquant", "sec-ingest", "789019", "320193", "--register-missing")
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    with make_session_factory(make_engine(s.database.url))() as ses:
        for url in BME:
            data, lm = get(url)
            archive_document(
                ses,
                store,
                provider="BME_HISTORICAL_COMPOSITION",
                source_identifier=url,
                data=data,
                mime_type="application/pdf",
                parser_version="bme-ibex-history-1",
                notes=f"source_type=historical_composition; Last-Modified: {lm}",
            )
        data, lm = get(NOTICE)
        archive_document(
            ses,
            store,
            provider="BME_INDEX_NOTICE",
            source_identifier=NOTICE,
            data=data,
            mime_type="application/pdf",
            parser_version="bme-notice-1",
            notes="source_type=index_manager_notice 15/2026 (SIX CSV is licensed)",
        )
        obs = OBSERVATION.read_bytes()
        archive_document(
            ses,
            store,
            provider="BME_IBEX35_CONSTITUENTS",
            source_identifier="observation:bme-ibex35-constituents:2026-10-01",
            data=obs,
            mime_type="application/json",
            published_at=datetime.fromisoformat(json.loads(obs)["observed_at"]),
            parser_version="bme-current-constituents-1",
            notes="source_type=transcribed_observation_of_rendered_official_pages",
        )
        ses.add(
            DataQualityIssue(
                entity="raw_source_archive",
                check_name="mime_mismatch",
                severity="high",
                details={
                    "detail": "BME Constituents.pdf URL served HTML (IBEX quote page) on "
                    "2026-10-01; not archived as a source.",
                    "source": "https://www.bolsasymercados.es/bme-exchange/docs/SB/"
                    "Constituents.pdf",
                    "recorded_at": datetime.now(UTC).isoformat(),
                },
            )
        )
        prov = CNMVFundamentalProvider(Fetcher(), store)
        prov.list_reports(ses, ENAGAS[0])
        for nreg in ENAGAS[1]:
            print(ingest_cnmv_report(ses, prov, nreg, register_missing=True), flush=True)
        ses.commit()
    run(sys.executable, "scripts/ingest_ancv.py")
    run(sys.executable, "scripts/build_ibex_real.py")
    run(sys.executable, "scripts/edgar_time_investigation.py")
    run(sys.executable, "scripts/verify_contract_cases.py")
    run(sys.executable, "scripts/gen_real_demos.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
