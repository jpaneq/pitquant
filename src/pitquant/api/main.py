"""ASGI entrypoint: ``uvicorn pitquant.api.main:app``.

With ``PITQUANT_DEMO=1`` and an in-memory SQLite URL, the clearly-labelled SYNTHETIC
market is loaded at startup so the API can be explored without any real data.
"""

from __future__ import annotations

import os

from pitquant.api.app import create_app
from pitquant.config.settings import get_settings
from pitquant.db.session import create_all, make_engine, make_session_factory
from pitquant.jobs.demo import load_synthetic_market

_settings = get_settings()
_engine = make_engine(_settings.database.url)
_factory = make_session_factory(_engine)

if os.environ.get("PITQUANT_DEMO") == "1":
    if not _settings.database.url.startswith("sqlite"):
        raise RuntimeError(
            "PITQUANT_DEMO=1 is only allowed with SQLite (never mix synthetic data into a real DB)"
        )
    create_all(_engine)
    load_synthetic_market(_factory, _settings)

app = create_app(_factory, _settings)
