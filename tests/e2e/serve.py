# ruff: noqa: E501
"""Serve the SPA + API over a SYNTHETIC fixture database for browser E2E (no external APIs, no secrets).

``python -m tests.e2e.serve [port]``. Tickers are SYN*: synthetic, labelled, never real history. The server
sets ``PITQUANT_E2E_FIXTURE=1`` so the UI shows the DEMO DATA banner.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

os.environ["PITQUANT_E2E_FIXTURE"] = "1"
_db = Path(tempfile.mkdtemp(prefix="pitquant-e2e-")) / "fixture.db"
os.environ["PITQUANT_DATABASE_URL"] = f"sqlite:///{_db}"

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from pitquant.api.app import create_app  # noqa: E402
from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.db.session import create_all, make_engine, make_session_factory  # noqa: E402
from pitquant.market.normalized import MarketBar, NormalizedBatch  # noqa: E402
from pitquant.market.pipeline import store_batch  # noqa: E402
from pitquant.security_master.service import SecurityMaster  # noqa: E402
from tests.unit.test_feature_engine_v0 import (  # noqa: E402
    CAL,
    NOW,
    PROV,
    SESSIONS,
    add_fact,
    closes_path,
    load_bars,
)


def build() -> FastAPI:
    settings = get_settings()
    engine = make_engine(settings.database.url)
    create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        sm = SecurityMaster(s)
        a = sm.register(name="SYN FULL CO (FIXTURE)", exchange="XNYS", currency="USD").security_id
        sm.add_ticker(a, "SYNF", "XNYS", date(2010, 1, 4))
        load_bars(s, a, "F", closes_path(SESSIONS, 100.0, 0.0006))
        for y, rev in ((2014, 1000.0), (2015, 1200.0)):
            for tag, v in (("Revenues", rev), ("NetIncomeLoss", rev * 0.1)):
                add_fact(
                    s,
                    a,
                    tag,
                    date(y, 1, 1),
                    date(y, 12, 31),
                    v,
                    datetime(y + 1, 2, 20, 21, tzinfo=UTC),
                    form="10-K",
                )
        b = sm.register(
            name="SYN FUNDAMENTAL ONLY (FIXTURE)", exchange="XNYS", currency="USD"
        ).security_id
        sm.add_ticker(b, "SYNO", "XNYS", date(2010, 1, 4))
        add_fact(
            s,
            b,
            "Revenues",
            date(2015, 1, 1),
            date(2015, 12, 31),
            500.0,
            datetime(2016, 2, 20, tzinfo=UTC),
            form="10-K",
        )
        # SYNSIM: the same synthetic path plus SCRIPTED future sessions (relative to the last close C0), so the Simulation Lab E2E can
        # exercise a full lifecycle deterministically. Never real market data.
        c = sm.register(name="SYN SIM CO (FIXTURE)", exchange="XNYS", currency="USD").security_id
        sm.add_ticker(c, "SYNSIM", "XNYS", date(2010, 1, 4))
        path = closes_path(SESSIONS, 100.0, 0.0006)
        load_bars(s, c, "S", path)
        c0 = list(path.values())[-1]
        scripted = [  # (open, high, low, close) as multiples of C0
            (1.000, 1.010, 0.995, 1.000),  # no touch of a 0.99 limit
            (0.995, 0.996, 0.985, 0.990),  # touches 0.99: entry at the limit
            (0.990, 1.010, 0.985, 1.005),
            (1.005, 1.040, 1.000, 1.035),  # target 1.03 touched
            (1.035, 1.040, 0.940, 0.960),  # stop 0.95 hit after the touch
            (1.000, 1.060, 0.900, 1.000),  # wide bar: stop AND target inside it
        ]
        days = CAL.sessions(date(2017, 1, 3), date(2017, 1, 31))[: len(scripted)]
        store_batch(
            s,
            NormalizedBatch(
                bars=[
                    MarketBar(
                        "S",
                        d,
                        round(c0 * o, 4),
                        round(c0 * h, 4),
                        round(c0 * lo, 4),
                        round(c0 * cl, 4),
                        1000.0,
                        "USD",
                        CAL.session_close(d),
                        PROV,
                    )
                    for d, (o, h, lo, cl) in zip(days, scripted, strict=True)
                ],
                actions=[],
            ),
            key_to_security={"S": c},
            market="US",
            now=NOW,
        )
        s.commit()
    return create_app(factory, settings)


if __name__ == "__main__":
    uvicorn.run(
        build(),
        host="127.0.0.1",
        port=int(sys.argv[1]) if len(sys.argv) > 1 else 8765,
        log_level="warning",
    )
