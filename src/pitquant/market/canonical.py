"""Versioned methodological provider choice; per-series quality remains independent."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import CorporateActionIngestion, DataSource, Price, Security

PROVIDER = "YAHOO_FINANCE"
ROLE = "CANONICAL_MARKET_PRICE_SOURCE"
CONTRACT_VERSION = "yahoo-market-data-v1"
SOURCE = "YAHOO_CHART:eod"
FEATURE_VERSION = "research-features-v1-yahoo-v1"
TARGET_VERSION = "research-targets-v2-yahoo-v2"


def source_status(name: str, synthetic: bool = False) -> str:
    if synthetic or "FIXTURE" in name.upper() or "SYNTHETIC" in name.upper():
        return "SYNTHETIC_EXCLUDED"
    if name == SOURCE:
        return "YAHOO_CANONICAL"
    if name.startswith(("EODHD", "TIINGO", "SHARADAR")):
        return "LEGACY_EXCLUDED"
    return "UNKNOWN_SOURCE_BLOCKED"


def audit_series(session: Session, security: Security) -> dict[str, Any]:
    rows = list(
        session.scalars(
            select(Price)
            .join(DataSource)
            .where(
                Price.security_id == security.security_id,
                DataSource.name == SOURCE,
                DataSource.is_synthetic.is_(False),
            )
            .order_by(Price.session_date)
        )
    )
    reasons = []
    if security.is_synthetic:
        reasons.append("SYNTHETIC_EXCLUDED")
    if not rows:
        reasons.append("MISSING_YAHOO_SERIES")
    invalid = [
        str(p.session_date)
        for p in rows
        if not all(
            x is not None and math.isfinite(x) and x > 0 for x in (p.open, p.high, p.low, p.close)
        )
        or (p.high is not None and p.low is not None and not p.low <= p.close <= p.high)
        or (
            p.high is not None
            and p.low is not None
            and p.open is not None
            and not p.low <= p.open <= p.high
        )
    ]
    if invalid:
        reasons.append("IMPOSSIBLE_OHLC")
    if any(p.currency != security.currency for p in rows):
        reasons.append("CURRENCY_MISMATCH")
    cal = get_calendar(security.exchange)
    if any(p.bar_close_at < cal.session_close(p.session_date) for p in rows):
        reasons.append("TIMESTAMP_BEFORE_SESSION_CLOSE")
    coverage = 0.0
    missing: list[str] = []
    if rows:
        expected = cal.sessions(
            max(rows[0].session_date, cal.first_session),
            min(rows[-1].session_date, cal.last_session),
        )
        present = {p.session_date for p in rows}
        missing = [str(d) for d in expected if d not in present]
        coverage = len(present & set(expected)) / max(len(expected), 1)
        threshold = 0.95 if security.listing_end else 0.98
        if coverage < threshold:
            reasons.append("MISSING_SESSIONS")
        if rows[0].session_date > cal.session_on_or_after(
            max(date(2011, 1, 1), security.listing_start or date(2011, 1, 1))
        ) and not documented_inception(session, rows, cal):
            reasons.append("LEADING_HISTORY_UNVERIFIED")
        ingestions = list(
            session.scalars(
                select(CorporateActionIngestion).where(
                    CorporateActionIngestion.security_id == security.security_id,
                    CorporateActionIngestion.provider == "YAHOO_CHART",
                    CorporateActionIngestion.status == "COMPLETED",
                    CorporateActionIngestion.period_start <= rows[0].session_date,
                    CorporateActionIngestion.period_end >= rows[-1].session_date,
                )
            )
        )
        if not ingestions:
            reasons.append("CORPORATE_ACTION_COVERAGE_UNVERIFIED")
        elif not verify_rebuild(session, rows, ingestions):
            reasons.append("DETERMINISTIC_REBUILD_UNVERIFIED")
        elif any(not i.source_hash for i in ingestions):
            reasons.append("SOURCE_PROVENANCE_MISSING")
    return {
        "security_id": security.security_id,
        "status": "READY" if not reasons else "BLOCKED",
        "bars": len(rows),
        "first": str(rows[0].session_date) if rows else None,
        "last": str(rows[-1].session_date) if rows else None,
        "coverage": coverage,
        "missing_sessions": missing,
        "invalid_dates": invalid,
        "reasons": reasons,
        "provider": PROVIDER,
        "provider_role": ROLE,
        "contract_version": CONTRACT_VERSION,
    }


def verify_rebuild(session: Session, rows: list[Price], ingestions: list[Any]) -> bool:
    """A stored series must match an archived vintage, not merely a provider label."""
    import json
    from pathlib import Path

    from pitquant.data.archive import sha256_hex
    from pitquant.db.models import RawSourceArchive
    from pitquant.market.providers.yahoo import YahooChartMarketDataProvider

    for record in ingestions:
        archive = session.scalars(
            select(RawSourceArchive).where(
                RawSourceArchive.sha256 == record.source_hash,
                RawSourceArchive.provider == SOURCE,
            )
        ).first()
        if archive is None:
            continue
        try:
            body = Path(archive.storage_uri).read_bytes()
            if sha256_hex(body) != archive.sha256:
                continue
            symbol = json.loads(body)["chart"]["result"][0]["meta"]["symbol"]
            batch = YahooChartMarketDataProvider().normalize(symbol, symbol, body)
            by_date = {bar.session_date: bar for bar in batch.bars}
            if all(
                p.session_date in by_date
                and all(
                    getattr(p, field) == getattr(by_date[p.session_date], field)
                    for field in ("open", "high", "low", "close", "volume", "currency")
                )
                for p in rows
            ):
                return True
        except (ValueError, KeyError, OSError, TypeError, IndexError):
            continue
    return False


def documented_inception(session: Session, rows: list[Price], calendar: Any) -> bool:
    """Vendor listing metadata can establish the first price date, never issuer succession."""
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    from pitquant.data.archive import sha256_hex
    from pitquant.db.models import RawSourceArchive

    for i in session.scalars(
        select(CorporateActionIngestion).where(
            CorporateActionIngestion.security_id == rows[0].security_id,
            CorporateActionIngestion.provider == "YAHOO_CHART",
            CorporateActionIngestion.status == "COMPLETED",
        )
    ):
        ar = session.scalars(
            select(RawSourceArchive).where(
                RawSourceArchive.sha256 == i.source_hash, RawSourceArchive.provider == SOURCE
            )
        ).first()
        if ar is None:
            continue
        try:
            body = Path(ar.storage_uri).read_bytes()
            if sha256_hex(body) != ar.sha256:
                continue
            meta = json.loads(body)["chart"]["result"][0]["meta"]
            listed = datetime.fromtimestamp(meta["firstTradeDate"], UTC).date()
            if calendar.session_on_or_after(listed) == rows[0].session_date:
                return True
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return False
