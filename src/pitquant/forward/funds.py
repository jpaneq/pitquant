"""Investment funds chosen by the owner, by ISIN (ADR-0065).

The owner adds funds from the page. Their daily NAV comes from Yahoo (Morningstar ids, ``.F``)
through the normal price pipeline. Every night the **current equity champion** scores them with
the same features and the same 20-step horizon, and each forecast is frozen in the journal
before its outcome exists. Funds are measured APART (own record kinds): they never enter the
equity exam, refits, policy or statistics. The model was not trained on funds: results say
whether it transfers, nothing more.
"""

from __future__ import annotations

import json
import math
import re
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.core.timeutils import require_aware, utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import Price
from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.engine import append, digest, extra_names, features, probability, records

MARKET = "FUNDS"
HORIZON = 20  # NAV sessions (~1 month), same as equities
REVIEWS = [1, 5, 10, 20]
CALENDAR = "XFRA"
STALE_AFTER_DAYS = 7  # NAVs are published with 1-2 days of delay
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
SEARCH = "https://query2.finance.yahoo.com/v1/finance/search?"


def _get(url: str) -> bytes:
    from pitquant.market.providers.yahoo import _http_get

    return _http_get(url)


def valid_isin(code: str) -> bool:
    """Format and Luhn check digit (letters expanded to numbers, ISO 6166)."""
    code = code.strip().upper()
    if not ISIN.match(code):
        return False
    digits = "".join(str(int(c, 36)) for c in code[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        total += n - 9 if n > 9 else n
    return (10 - total % 10) % 10 == int(code[-1])


def search(isin: str) -> list[dict[str, Any]]:
    """Yahoo listings of a fund ISIN, with name and currency from the chart metadata."""
    isin = isin.strip().upper()
    if not valid_isin(isin):
        raise ValueError("INVALID_ISIN")
    doc = json.loads(
        _get(SEARCH + urllib.parse.urlencode({"q": isin, "quotesCount": 6, "newsCount": 0}))
    )
    out = []
    for q in doc.get("quotes", []):
        symbol = str(q.get("symbol", ""))
        if q.get("quoteType") != "MUTUALFUND" or not symbol.endswith(".F"):
            continue  # only NAV listings whose calendar is mapped
        meta = _meta(symbol)
        out.append(
            {
                "isin": isin,
                "symbol": symbol,
                "name": meta.get("longName")
                or meta.get("shortName")
                or q.get("longname")
                or symbol,
                "currency": meta.get("currency"),
                "first_nav": meta.get("firstTradeDate"),
            }
        )
    return out


def _meta(symbol: str) -> dict[str, Any]:
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
    try:
        meta: dict[str, Any] = json.loads(_get(url))["chart"]["result"][0]["meta"]
        return meta
    except Exception:
        return {}


# ---------------------------------------------------------------- watch list (append-only)


def watched(s: Session) -> dict[str, dict[str, Any]]:
    """Current list: replay add/remove events in order (nothing is ever deleted)."""
    events = sorted(
        records(s, "FUND_WATCH", MARKET) + records(s, "FUND_UNWATCH", MARKET),
        key=lambda r: (r.payload["at"], r.created_at),
    )
    out: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.kind == "FUND_WATCH":
            out[e.payload["isin"]] = e.payload
        else:
            out.pop(e.payload["isin"], None)
    return out


def add(
    s: Session, isin: str, symbol: str, name: str, currency: str | None, now: datetime | None = None
) -> Record:
    now = require_aware(now or utc_now())
    isin = isin.strip().upper()
    if not valid_isin(isin) or not symbol.endswith(".F"):
        raise ValueError("INVALID_FUND")
    payload = {
        "isin": isin,
        "symbol": symbol,
        "name": name,
        "currency": currency,
        "at": now.isoformat(),
    }
    row = append(s, f"fund:add:{isin}:{now.isoformat()}", "FUND_WATCH", MARKET, payload)
    s.commit()
    return row


def remove(s: Session, isin: str, now: datetime | None = None) -> Record:
    now = require_aware(now or utc_now())
    payload = {"isin": isin.strip().upper(), "at": now.isoformat()}
    row = append(
        s, f"fund:remove:{payload['isin']}:{now.isoformat()}", "FUND_UNWATCH", MARKET, payload
    )
    s.commit()
    return row


# ---------------------------------------------------------------- data


def ingest(s: Session, store: Any, only: list[str] | None = None) -> dict[str, str]:
    """Download NAVs (incremental) via the Yahoo pipeline; one failure never stops the rest."""
    from pitquant.data.archive import archive_document
    from pitquant.market.pipeline import store_batch
    from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
    from pitquant.positions.universe_ingest import ensure_security

    provider = YahooChartMarketDataProvider()
    out = {}
    for isin, fund in watched(s).items():
        if only and isin not in only:
            continue
        try:
            sid = ensure_security(s, isin, fund["symbol"])
            last = s.scalar(select(func.max(Price.session_date)).where(Price.security_id == sid))
            first = last - timedelta(days=10) if last else date(2011, 1, 1)
            body, redacted = provider.download(fund["symbol"], first, utc_now().date())
            archive_document(
                s,
                store,
                provider="YAHOO_CHART:eod",
                source_identifier=redacted,
                data=body,
                mime_type="application/json",
                parser_version="yahoo-chart-1",
                notes="owner fund watch list (NAV); VENDOR tier; unofficial, personal use",
            )
            batch = provider.normalize(isin, fund["symbol"], body)
            report = store_batch(s, batch, key_to_security={isin: sid}, market="EU")
            s.commit()
            out[isin] = f"OK navs={len(batch.bars)} inserted={report.bars_inserted}"
        except Exception as exc:
            s.rollback()
            out[isin] = f"FAILED: {str(exc)[:160]}"
    return out


def load_nav(s: Session, isin: str, now: datetime) -> pd.DataFrame:
    """NAV series on its own publication dates (no foreign calendar holes)."""
    from pitquant.data.point_in_time.context import PITContext
    from pitquant.positions.universe_ingest import find_security

    sid = find_security(s, isin)
    if sid is None:
        raise ValueError("FUND_NOT_INGESTED")
    bars = PITContext(s, now, ingested_before=now).raw_bars(sid)
    if bars.empty:
        raise ValueError("NO_NAV_HISTORY")
    nav = bars[["close"]].astype(float).copy()
    nav["high"] = nav["low"] = nav["close"]  # a NAV has no intraday range
    nav["volume"] = np.nan  # nor volume: the model imputes it (as for any missing volume)
    nav["signal_close"] = nav["close"]  # accumulation classes: NAV already includes income
    return nav


def _step(day: date, steps: int) -> date:
    cal = get_calendar(CALENDAR)
    d = cal.session_on_or_after(day)
    for _ in range(steps):
        d = cal.next_session(d)
    return d


def _nav_on_or_after(nav: pd.DataFrame, day: date) -> tuple[date, float] | None:
    later = nav[(nav.index >= day) & (nav.index <= day + timedelta(days=STALE_AFTER_DAYS))]
    if later.empty:
        return None
    return later.index[0], float(later.close.iloc[0])


# ---------------------------------------------------------------- forecasts


def predict(s: Session, model: Record, isin: str, nav: pd.DataFrame, now: datetime) -> Record:
    if digest(model.payload) != model.payload_hash:
        raise ValueError("MODEL_INTEGRITY_ERROR")
    day = nav.index[-1]
    if (now.date() - day).days > STALE_AFTER_DAYS:
        raise ValueError("STALE_NAV")
    x = features(nav).iloc[-1]
    if pd.isna(x.ret60) or pd.isna(x.sma200):
        raise ValueError("NAV_HISTORY_TOO_SHORT_201")
    key = f"fund-prediction:{model.record_id}:{isin}:{day}"
    old = s.scalar(select(Record).where(Record.record_key == key))
    if old is not None:
        return old
    values: list[float | None] = [None if pd.isna(v) else float(v) for v in x]
    values += [None] * len(extra_names(model.payload))  # a fund has no company fundamentals
    target = _step(day, HORIZON)
    payload = {
        "model_id": model.record_id,
        "model_hash": model.payload_hash,
        "version": model.payload["version"],
        "isin": isin,
        "generated_at": now.isoformat(),
        "feature_date": str(day),
        "features": values,
        "reference_nav": float(nav.close.iloc[-1]),
        "target_date": str(target),
        "due_at": datetime.combine(
            target + timedelta(days=1), datetime.min.time(), UTC
        ).isoformat(),
        "horizon": HORIZON,
        "p_up": probability(model.payload, values),
        "status": "EXPERIMENTAL_MODEL_NOT_TRAINED_ON_FUNDS",
        "auto_trade": False,
    }
    return append(s, key, "FUND_PREDICTION", MARKET, payload)


def review(s: Session, prediction: Record, nav: pd.DataFrame, now: datetime) -> list[Record]:
    p = prediction.payload
    start = date.fromisoformat(p["feature_date"])
    if start not in nav.index:
        return []
    created = datetime.fromisoformat(p["generated_at"])
    out = []
    for step in REVIEWS:
        key = f"fund-review:{prediction.record_id}:{step}"
        if s.scalar(select(Record).where(Record.record_key == key)):
            continue
        found = _nav_on_or_after(nav, _step(start, step))
        if found is None or now <= created:
            continue
        day, value = found
        actual = value / float(nav.loc[start, "close"]) - 1
        if not math.isfinite(actual):
            continue
        final = step == HORIZON
        payload = {
            "prediction_id": prediction.record_id,
            "step": step,
            "nav_date": str(day),
            "observed_at": now.isoformat(),
            "nav": value,
            "actual_return": actual,
            "final": final,
            "hit": bool((p["p_up"] >= 0.5) == (actual > 0)) if final else None,
        }
        out.append(append(s, key, "FUND_OUTCOME" if final else "FUND_REVIEW", MARKET, payload))
    return out


def cycle(s: Session, now: datetime | None = None) -> dict[str, Any]:
    """Forecast every watched fund with the equity champion and review the matured ones."""
    from pitquant.forward.learning import champion

    now = require_aware(now or utc_now())
    model = champion(s, "EQUITY")
    summary: dict[str, Any] = {"forecasts": 0, "reviews": 0, "gaps": {}}
    funds = watched(s)
    for isin in funds:
        try:
            nav = load_nav(s, isin, now)
        except ValueError as exc:
            summary["gaps"][isin] = str(exc)
            continue
        if model is not None:
            try:
                predict(s, model, isin, nav, now)
                summary["forecasts"] += 1
            except ValueError as exc:
                summary["gaps"][isin] = str(exc)
        for pred in records(s, "FUND_PREDICTION", MARKET):
            if pred.payload["isin"] == isin:
                summary["reviews"] += len(review(s, pred, nav, now))
    s.commit()
    return summary


def board(s: Session) -> list[dict[str, Any]]:
    """Per fund: the latest forecast, its last checkpoint and the matured scorecard."""
    preds = records(s, "FUND_PREDICTION", MARKET)
    checks: dict[str, dict[str, Any]] = {}
    for r in records(s, "FUND_REVIEW", MARKET) + records(s, "FUND_OUTCOME", MARKET):
        prev = checks.get(r.payload["prediction_id"])
        if prev is None or r.payload["step"] > prev["step"]:
            checks[r.payload["prediction_id"]] = r.payload
    out = []
    for isin, fund in watched(s).items():
        mine = sorted(
            (p for p in preds if p.payload["isin"] == isin), key=lambda p: p.payload["feature_date"]
        )
        matured = [
            (p.payload, checks[p.record_id])
            for p in mine
            if checks.get(p.record_id, {}).get("final")
        ]
        latest = mine[-1] if mine else None
        check = checks.get(latest.record_id) if latest else None
        hits = [c["hit"] for _, c in matured]
        ups = [c["actual_return"] > 0 for _, c in matured]
        out.append(
            {
                **fund,
                "forecasts": len(mine),
                "latest": {
                    "p_up": latest.payload["p_up"],
                    "feature_date": latest.payload["feature_date"],
                    "reference_nav": latest.payload["reference_nav"],
                    "target_date": latest.payload["target_date"],
                    "version": latest.payload["version"],
                    "last_step": check["step"] if check else 0,
                    "last_return": check["actual_return"] if check else None,
                }
                if latest
                else None,
                "matured": len(matured),
                "hits": sum(hits),
                "accuracy": float(np.mean(hits)) if hits else None,
                "always_up_accuracy": float(np.mean(ups)) if ups else None,
                "history": [
                    {
                        "date": p["feature_date"],
                        "p_up": p["p_up"],
                        "return": c["actual_return"],
                        "hit": c["hit"],
                    }
                    for p, c in matured[-60:]
                ],
            }
        )
    return out
