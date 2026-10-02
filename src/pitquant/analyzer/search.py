# ruff: noqa: E501
"""Global search for the Analyzer: ticker, company name, CUSIP, ISIN. Resolves to ``security_id`` (the ticker
is only an alias). A non-exact match is flagged ``FUZZY`` so the UI asks the user to confirm: ``APPL`` is
NEVER silently analysed as ``AAPL``. Not restricted to S&P 500 / IBEX."""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.db.models import (
    FundamentalFact,
    IdentifierHistory,
    Price,
    Security,
    SecurityIdentifierEvidence,
    SecurityProfile,
    TickerHistory,
)


@dataclass
class Hit:
    security_id: str
    ticker: str | None
    name: str
    exchange: str | None
    country: str | None
    asset_class: str
    status: str
    match_type: str  # EXACT | IDENTIFIER | PREFIX | NAME | FUZZY
    score: float
    n_bars: int = 0
    has_fundamentals: bool = False


def _catalog(s: Session) -> list[dict[str, str | None]]:
    prof: dict[str, SecurityProfile] = {}
    for pr in s.scalars(select(SecurityProfile).order_by(SecurityProfile.ingested_at)):
        prof[pr.security_id] = pr
    rows = []
    for sec in s.scalars(select(Security).where(Security.is_synthetic.is_(False))):
        p = prof.get(sec.security_id)
        tick = (
            p.current_ticker
            if p and p.current_ticker
            else s.scalars(
                select(TickerHistory.ticker).where(
                    TickerHistory.security_id == sec.security_id, TickerHistory.valid_to.is_(None)
                )
            ).first()
        )
        name = p.display_name if p else sec.name
        if sec.name.startswith("CIK ") and not p:
            continue  # SEC anchor without a profile: nothing human-readable to show
        rows.append(
            {
                "security_id": sec.security_id,
                "ticker": tick,
                "name": name,
                "exchange": (p.exchange if p else None) or sec.exchange,
                "country": (p.country if p else None) or sec.country,
                "asset_class": "ETF" if re.search(r"\bETF\b", name.upper()) else "Equity",
            }
        )
    return rows


def _status(s: Session, sid: str) -> tuple[str, int, bool]:
    nb = s.scalar(select(func.count()).select_from(Price).where(Price.security_id == sid)) or 0
    nf = (
        s.scalar(
            select(func.count())
            .select_from(FundamentalFact)
            .join(Security, Security.security_id == sid)
            .where(
                (FundamentalFact.security_id == sid)
                | (
                    (FundamentalFact.issuer_id == Security.issuer_id)
                    & (Security.issuer_id.is_not(None))
                )
            )
        )
        or 0
    ) > 0
    st = (
        "PRICES+FUNDAMENTALS"
        if nb >= 60 and nf
        else "PRICES_ONLY"
        if nb >= 60
        else "FUNDAMENTALS_ONLY"
        if nf
        else "NO_DATA"
    )
    return st, nb, nf


def search(s: Session, q: str, limit: int = 10) -> dict[str, object]:
    raw = q.strip()
    qu = raw.upper()
    if not raw:
        return {"query": q, "exact": False, "results": []}
    cat = _catalog(s)
    by_id = {c["security_id"]: c for c in cat}
    hits: dict[str, Hit] = {}

    def add(sid: str, mt: str, score: float) -> None:
        c = by_id.get(sid)
        if c is None:
            return
        if sid not in hits or hits[sid].score < score:
            st, nb, nf = _status(s, sid)
            hits[sid] = Hit(
                sid,
                c["ticker"],
                c["name"] or "",
                c["exchange"],
                c["country"],
                c["asset_class"] or "Equity",
                st,
                mt,
                score,
                nb,
                nf,
            )

    for c in cat:
        t = (c["ticker"] or "").upper()
        nm = (c["name"] or "").upper()
        if t and t == qu:
            add(c["security_id"] or "", "EXACT", 100.0)
        elif t and t.startswith(qu) and len(qu) >= 2:
            add(c["security_id"] or "", "PREFIX", 80.0 - len(t) + len(qu))
        if qu in nm and len(qu) >= 3:
            add(c["security_id"] or "", "NAME", 70.0 + 10.0 * (nm.startswith(qu)))
    ident = re.sub(r"[\s-]", "", qu)
    if len(ident) >= 9:
        for sid in set(
            s.scalars(select(IdentifierHistory.security_id).where(IdentifierHistory.value == ident))
        ) | set(
            s.scalars(
                select(SecurityIdentifierEvidence.security_id).where(
                    SecurityIdentifierEvidence.value == ident
                )
            )
        ):
            add(sid, "IDENTIFIER", 99.0)
    if not hits:  # moderate fuzzy: close tickers / names, always a SUGGESTION
        pool = {(c["ticker"] or "").upper(): c["security_id"] for c in cat if c["ticker"]} | {
            (c["name"] or "").upper(): c["security_id"] for c in cat
        }
        for m in difflib.get_close_matches(qu, list(pool), n=limit, cutoff=0.6):
            add(pool[m] or "", "FUZZY", 100.0 * difflib.SequenceMatcher(None, qu, m).ratio() / 2)
    res = sorted(hits.values(), key=lambda h: -h.score)[:limit]
    return {
        "query": q,
        "exact": any(h.match_type in ("EXACT", "IDENTIFIER") for h in res),
        "needs_confirmation": bool(res) and all(h.match_type == "FUZZY" for h in res),
        "results": [asdict(h) for h in res],
    }
