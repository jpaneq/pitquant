"""Archive and ingest every CNMV ANCV semiannual ISIN distribution (06/2010 → latest), and
the ANCV «query by NIF» for every issuer with a CIF in the database (ADR-0020).

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_ancv.py

Zips are cached in data/sources/ancv/ (not versioned); every zip goes through
raw_source_archive with its URL, filename, reference date, member hashes and the LEAME
scope. Network: the CNMV publications page, the zips not cached yet, the NIF queries.
"""

from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.providers.cnmv.ancv import (  # noqa: E402
    NIF_QUERY_URL,
    PARSER_VERSION,
    PUBLICATIONS_URL,
    CNMVSecurityIdentityProvider,
    discover_distribution_urls,
    parse_nif_query,
)
from pitquant.db.models import IssuerIdentifier  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

CACHE = ROOT / "data" / "sources" / "ancv"
UA = "Mozilla/5.0 (compatible; PITQuant research)"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        body: bytes = r.read()
    time.sleep(1.0)
    return body


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    prov = CNMVSecurityIdentityProvider(store)
    CACHE.mkdir(parents=True, exist_ok=True)
    with make_session_factory(make_engine(s.database.url))() as ses:
        page = get(PUBLICATIONS_URL)
        archive_document(
            ses,
            store,
            provider="CNMV_ANCV_INDEX",
            source_identifier=PUBLICATIONS_URL,
            data=page,
            mime_type="text/html",
            parser_version=PARSER_VERSION,
            notes="source_type=ancv_publications_page",
        )
        urls = discover_distribution_urls(page)
        print(f"{len(urls)} distributions listed")
        for url in urls:
            local = CACHE / url.rsplit("/", 1)[-1]
            if not local.exists():
                local.write_bytes(get(url))
            rep = prov.ingest_distribution(ses, url, local.read_bytes())
            print(
                f"{rep.reference_date} {rep.equity_format:16} lines={rep.lines} "
                f"inserted={rep.inserted} {local.name}",
                flush=True,
            )
            ses.commit()
        for ident in ses.scalars(select(IssuerIdentifier).where(IssuerIdentifier.id_type == "CIF")):
            url = NIF_QUERY_URL.format(nif=ident.value)
            body = get(url)
            res = parse_nif_query(body)
            archive_document(
                ses,
                store,
                provider="CNMV_ANCV_NIF_QUERY",
                source_identifier=url,
                data=body,
                mime_type="text/html",
                parser_version=PARSER_VERSION,
                notes=f"source_type=ancv_query_by_nif; cif={ident.value}; issuer={res.issuer_name}",
            )
            print(f"NIF {ident.value}: {res.issuer_name} -> {[x.isin for x in res.lines]}")
        ses.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
