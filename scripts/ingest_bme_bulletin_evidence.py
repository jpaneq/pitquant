"""Archive BME daily bulletins and record the official «code <-> ISIN» links they publish
(ADR-0022). Default dates: the first session of every month from 2022-10 to the last
observation, plus 2023-06-15/16 (Ferrovial ES -> NL).

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db \
        python scripts/ingest_bme_bulletin_evidence.py [YYYYMMDD ...]

Both sections of each issue are archived (URL, retrieved_at, SHA-256). Only codes that belong to
the IBEX membership build are stored. An issue whose two sections disagree is skipped.
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.errors import DataQualityError  # noqa: E402
from pitquant.core.hashing import content_hash  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.calendars.market_calendar import get_calendar  # noqa: E402
from pitquant.data.providers.bme.bulletin import (  # noqa: E402
    PARSER_VERSION,
    bulletin_urls,
    join_bulletin,
    pdf_text,
)
from pitquant.db.models import OfficialCodeIsinEvidence, TickerHistory  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

UA = "Mozilla/5.0 (compatible; PITQuant research)"


def _get(url: str) -> bytes | None:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                body: bytes = r.read()
            time.sleep(0.8)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(3 * (i + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(3 * (i + 1))
    raise DataQualityError(f"fetch failed {url}")


def default_dates(last: date) -> list[str]:
    cal = get_calendar("XMAD")
    ds = cal.first_sessions_of_months(date(2022, 10, 1), last)
    extra = [date(2023, 6, 15), date(2023, 6, 16)]
    return sorted({d.strftime("%Y%m%d") for d in [*ds, *extra]})


def main(argv: list[str]) -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    n_new = n_skip = 0
    with make_session_factory(make_engine(s.database.url))() as ses:
        wanted = {t.upper() for t in ses.scalars(select(TickerHistory.ticker))}
        dates = argv or default_dates(datetime.now(UTC).date())
        for ymd in dates:
            u38, u49 = bulletin_urls(ymd)
            b38, b49 = _get(u38), _get(u49)
            if b38 is None or b49 is None:
                print(f"{ymd}: no bulletin", flush=True)
                n_skip += 1
                continue
            try:
                links = join_bulletin(pdf_text(b38), pdf_text(b49))
            except DataQualityError as e:
                print(f"{ymd}: refused ({e})", flush=True)
                n_skip += 1
                continue
            rows = [
                archive_document(
                    ses,
                    store,
                    provider="BME_BOLETIN_DIARIO",
                    source_identifier=u,
                    data=b,
                    mime_type="application/pdf",
                    parser_version=PARSER_VERSION,
                    notes=f"source_type=bme_daily_bulletin; session={ymd}",
                )
                for u, b in ((u38, b38), (u49, b49))
            ]
            observed = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
            sha = content_hash([r.sha256 for r in rows])
            added = 0
            for link in links:
                if link.code.upper() not in wanted:
                    continue
                exists = ses.scalars(
                    select(OfficialCodeIsinEvidence).where(
                        OfficialCodeIsinEvidence.source_sha256 == sha,
                        OfficialCodeIsinEvidence.code == link.code,
                        OfficialCodeIsinEvidence.isin == link.isin,
                    )
                ).first()
                if exists is not None:
                    continue
                ses.add(
                    OfficialCodeIsinEvidence(
                        code=link.code,
                        isin=link.isin,
                        observed_on=observed,
                        issuer_name=link.name,
                        market="Mercado Continuo (bulletin)",
                        source_kind="BME_BOLETIN_JOIN",
                        source_url=f"{u38} + {u49}",
                        capture_timestamp=None,
                        archive_id=rows[1].archive_id,
                        source_sha256=sha,
                        parser_version=PARSER_VERSION,
                    )
                )
                added += 1
            n_new += added
            ses.commit()
            print(f"{ymd}: {len(links)} securities, {added} stored", flush=True)
    print(f"added {n_new}; skipped dates {n_skip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
