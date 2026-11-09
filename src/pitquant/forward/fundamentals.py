"""Company fundamentals as inputs of the forward model v3 (ADR-0066).

Six indicators chosen BEFORE looking at any result, from the value/quality literature already
reviewed (docs/research/QUANT_ALGORITHM_EVIDENCE_2026-11-01.md), and computed by the SAME
point-in-time engine as the research dataset (``research.fundamentals_v1``): each filing counts
from its SEC acceptance instant, never from its period end.

They are evaluated on the first session of every month (at the open, with the previous close)
and carried forward to the daily rows of that month: a value is only used on dates after it was
computable. Banks/insurers (unsupported sector) and gaps stay missing and are imputed by the
model like any missing input; missing is never 0.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from sqlalchemy.orm import Session

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import Security

FUND_SET = "forward-fund-v1"
FUND_FEATURES = [
    "fund_operating_margin",  # profitability
    "fund_roa",  # profitability
    "fund_revenue_yoy",  # growth
    "fund_debt_to_assets",  # leverage
    "val_earnings_yield",  # value: earnings / price
    "val_fcf_yield",  # value: free cash flow / price
]


def fund_table(s: Session, ticker: str, now: datetime, since: date | None = None) -> pd.DataFrame:
    """Monthly fundamentals of one stock as known at each month's first open (index = session)."""
    from pitquant.features.v0.engine import load_facts
    from pitquant.positions.universe_ingest import find_security
    from pitquant.research import fundamentals_v1 as FU
    from pitquant.research import targets_v1 as TG
    from pitquant.research.dataset_v1 import _bundle, _profile_sic, guard_snapshot

    empty = pd.DataFrame(columns=FUND_FEATURES, dtype=float)
    sid = find_security(s, ticker)
    if sid is None:
        return empty
    sec = s.get_one(Security, sid)
    got = _bundle(s, sid, ticker, sec.exchange, now)
    if got is None:
        return empty
    bundle, market = got
    facts = load_facts(s, sid, now)
    sic, _ = _profile_sic(s, sec)
    history = FU.ValuationHistory()
    cal = get_calendar(sec.exchange)
    start = max(bundle.index[0], cal.first_session)
    rows: dict[date, dict[str, float | None]] = {}
    for d in cal.first_sessions_of_months(start, min(bundle.index[-1], cal.last_session)):
        if since is not None and d < since:
            continue
        decision_at = cal.session_open(d)
        if decision_at > now:
            break
        pos = TG._pos_at(bundle, decision_at)
        if pos is None:
            continue
        actions = [a for a in market.actions if a.available_at <= decision_at]
        feats, _meta = FU.fundamental_features(
            s, sid, facts, decision_at, sic=sic, last_session=bundle.index[pos],
            raw_close=float(market.bars["close"].iloc[pos]), actions=actions,
            adj_close=float(bundle.adj["close"].iloc[pos]), history=history, registered=bool(facts),
        )  # fmt: skip
        guard_snapshot(feats, decision_at)  # LookAheadError if any input postdates the decision
        rows[d] = {n: feats[n]["value"] for n in FUND_FEATURES}
    if not rows:
        return empty
    return pd.DataFrame.from_dict(rows, orient="index", columns=FUND_FEATURES).astype(float)


def attach(bars: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """Daily rows take the latest month value whose first session is on or before the row."""
    out = bars.copy()
    if table.empty:
        for name in FUND_FEATURES:
            out[name] = float("nan")
        return out
    monthly = table.sort_index()
    idx = pd.Index(monthly.index)
    pos = idx.searchsorted(pd.Index(out.index), side="right") - 1
    for name in FUND_FEATURES:
        values = monthly[name].to_numpy(float)
        out[name] = [values[p] if p >= 0 else float("nan") for p in pos]
    return out
