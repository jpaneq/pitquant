"""Archive copies of the legacy OFFICIAL Bolsa de Madrid «Ficha de valor» pages (Internet
Archive captures) and record each as a dated «BME code ↔ ISIN» statement (ADR-0022).

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_bme_ficha_evidence.py \
        [ISIN ...]

* the page's own render stamp is the observation date; a capture whose stamp differs from the
  Wayback timestamp by more than 3 days is NOT used (cached/stale), and is reported;
* every page goes through raw_source_archive (URL, retrieved_at, SHA-256, parser version);
* one capture per month at most; politeness delay between requests.

The ISIN list defaults to the securities behind today's blockers in docs/IDENTITY_BLOCKERS.md.
No engine rule is special-cased: this only adds evidence rows.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.errors import DataQualityError  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.providers.bme.ficha import PARSER_VERSION, parse_ficha  # noqa: E402
from pitquant.db.models import OfficialCodeIsinEvidence  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

UA = "Mozilla/5.0 (compatible; PITQuant research)"
BASE = "www.bolsamadrid.es/esp/aspx/Empresas/FichaValor.aspx?ISIN={isin}"
DEFAULT_ISINS = [
    "LU0323134006",  # MTS (old)
    "LU1598757687",  # MTS (after the 2017 consolidation)
    "ES0105200002",  # ABG.P
    "ES0171996012",  # GRF
    "ES0171996087",
    "ES0173093115",  # REE
    "ES0173093024",
    "ES0169501022",  # PHM
    "ES0105027009",  # LOG
    "ES0160973014",
    "ES0105777009",  # PUIG
    "ES0105777017",
    "ES0118900010",  # FER
]
MAX_STAMP_GAP_DAYS = 3
START_YEAR = 2010


def _get(url: str, retries: int = 3) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                body: bytes = r.read()
            time.sleep(1.0)
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(3 * (i + 1))
    raise DataQualityError(f"fetch failed {url}: {last}")


def captures(isin: str) -> list[tuple[str, str]]:
    q = urllib.parse.urlencode(
        {
            "url": BASE.format(isin=isin) + "*",
            "output": "txt",
            "fl": "timestamp,original",
            "filter": "statuscode:200",
            "collapse": "timestamp:6",
        },
        safe="*",
    )
    body = _get("http://web.archive.org/cdx/search/cdx?" + q).decode()
    out = []
    for line in body.splitlines():
        ts, orig = line.split(" ", 1)
        if int(ts[:4]) >= START_YEAR:
            out.append((ts, orig))
    return out


def main(argv: list[str]) -> int:
    isins = argv or DEFAULT_ISINS
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    n_new = n_skip = 0
    with make_session_factory(make_engine(s.database.url))() as ses:
        for isin in isins:
            caps = captures(isin)
            print(f"{isin}: {len(caps)} captures", flush=True)
            for ts, orig in caps:
                url = f"http://web.archive.org/web/{ts}id_/{orig}"
                known = ses.scalars(
                    select(OfficialCodeIsinEvidence).where(
                        OfficialCodeIsinEvidence.capture_timestamp == ts,
                        OfficialCodeIsinEvidence.source_url == url,
                    )
                ).first()
                if known is not None:
                    continue
                try:
                    body = _get(url)
                    ev = parse_ficha(body)
                except DataQualityError as e:
                    print(f"  {ts}: skipped ({e})")
                    n_skip += 1
                    continue
                cap = datetime.strptime(ts[:8], "%Y%m%d").replace(tzinfo=UTC).date()
                gap = abs((cap - ev.page_date).days)
                if not ev.is_live_listing():
                    print(
                        f"  {ts}: not a presence claim (last price {ev.last_price_date}, "
                        f"stamp {ev.page_date})"
                    )
                    n_skip += 1
                    continue
                if gap > MAX_STAMP_GAP_DAYS or ev.isin != isin:
                    print(f"  {ts}: not used (page stamp {ev.page_date}, isin {ev.isin})")
                    n_skip += 1
                    continue
                row = archive_document(
                    ses,
                    store,
                    provider="BME_FICHA_WAYBACK",
                    source_identifier=url,
                    data=body,
                    mime_type="text/html",
                    published_at=datetime.combine(ev.page_date, datetime.min.time()).replace(
                        tzinfo=UTC
                    ),
                    parser_version=PARSER_VERSION,
                    notes=json.dumps(
                        {
                            "source_type": "wayback_copy_of_official_bme_ficha",
                            "capture_timestamp": ts,
                            "original_url": orig,
                            "page_stamp": ev.page_date.isoformat(),
                        }
                    ),
                )
                ses.add(
                    OfficialCodeIsinEvidence(
                        code=ev.code,
                        isin=ev.isin,
                        observed_on=ev.page_date,
                        issuer_name=ev.issuer_name,
                        market=ev.market,
                        source_kind="BME_FICHA_WAYBACK",
                        source_url=url,
                        capture_timestamp=ts,
                        archive_id=row.archive_id,
                        source_sha256=row.sha256,
                        parser_version=PARSER_VERSION,
                    )
                )
                n_new += 1
            ses.commit()
    print(f"evidence rows added: {n_new}; skipped: {n_skip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
