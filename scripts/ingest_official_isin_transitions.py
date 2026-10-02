"""Fetch, archive and verify the official documents behind ISIN transitions and
code <-> ISIN statements (ADR-0022). Claims whose sentences are NOT found in the original
are NOT recorded.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db \
        python scripts/ingest_official_isin_transitions.py [KEY ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.providers.official_identity import (  # noqa: E402
    record_code_evidence,
    record_transition,
)
from pitquant.data.providers.official_identity_registry import (  # noqa: E402
    CODE_EVIDENCE,
    TRANSITIONS,
)
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402


def main(argv: list[str]) -> int:
    only = set(argv)
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    bad = 0
    with make_session_factory(make_engine(s.database.url))() as ses:
        for t in TRANSITIONS:
            if only and t.key not in only:
                continue
            o = record_transition(ses, store, t)
            print(f"{'OK ' if o.ok else 'NO '} {o.key}: {' | '.join(o.notes)}", flush=True)
            bad += not o.ok
            ses.commit()
        for c in CODE_EVIDENCE:
            if only and c.key not in only:
                continue
            o = record_code_evidence(ses, store, c)
            print(f"{'OK ' if o.ok else 'NO '} {o.key}: {' | '.join(o.notes)}", flush=True)
            bad += not o.ok
            ses.commit()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
