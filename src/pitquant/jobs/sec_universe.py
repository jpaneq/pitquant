# ruff: noqa: E501
"""SEC fundamentals for the daily-routine universe (ADR-0046). Official source only: SEC EDGAR (company_tickers + submissions + filings). The contact User-Agent is read from the environment by the
SEC client and never stored. Fundamentals attach to the ISSUER (ADR-0020); the security that carries the Yahoo prices is LINKED to that issuer (``securities.issuer_id``), so facts apply to the traded security
without mixing identities. No ticker→CIK guess: the mapping comes from the SEC's own file, archived with its SHA-256.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.data.providers.sec_edgar.parsers import cik10
from pitquant.data.providers.sec_edgar.provider import SECEdgarFundamentalProvider
from pitquant.db.models import Security, SecurityProfile
from pitquant.jobs.sec_ingest import ingest_ciks, security_for_cik

DIVISIONS = [
    (1, 9, "Agriculture, Forestry & Fishing"),
    (10, 14, "Mining"),
    (15, 17, "Construction"),
    (20, 39, "Manufacturing"),
    (40, 49, "Transportation, Communications & Utilities"),
    (50, 51, "Wholesale Trade"),
    (52, 59, "Retail Trade"),
    (60, 67, "Finance, Insurance & Real Estate"),
    (70, 89, "Services"),
    (91, 99, "Public Administration"),
]
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# Non-financial US large caps of the routine universe (banks, insurers and managed-care plans need a specialised fundamental profile that is not supported yet).
DEFAULT_TICKERS = [
    "JNJ",
    "PG",
    "XOM",
    "AMZN",
    "GOOGL",
    "NVDA",
    "META",
    "V",
    "LLY",
    "HD",
    "WMT",
    "MRK",
    "CVX",
    "MA",
    "COST",
]


def division(sic: str | None) -> str | None:
    if not sic or not sic.isdigit():
        return None
    two = int(sic[:2]) if len(sic) >= 3 else int(sic)
    return next((n for a, b, n in DIVISIONS if a <= two <= b), None)


def profile_type(sic: str | None) -> str:
    if not sic or not sic.isdigit():
        return "STANDARD_CORPORATE"
    n = int(sic)
    if n in (6021, 6022, 6029, 6035, 6036, 6111, 6199) or (6700 <= n <= 6726 and n != 6798):
        return "BANK" if n in (6021, 6022, 6029, 6035, 6036) else "OTHER_SPECIAL"
    if 6311 <= n <= 6399 or n == 6411:
        return "INSURER"
    if n == 6798:
        return "REIT"
    return "STANDARD_CORPORATE"


def _get(url: str, ua: str) -> bytes:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"}),
        timeout=60,
    ) as r:
        data: bytes = r.read()
    time.sleep(0.25)  # SEC fair-access: well under 10 requests per second
    return data


def ticker_map(session: Session, store: ArchiveStore, ua: str) -> dict[str, str]:
    body = _get(TICKERS_URL, ua)
    archive_document(
        session,
        store,
        provider="SEC_COMPANY_TICKERS",
        source_identifier=TICKERS_URL,
        data=body,
        mime_type="application/json",
        parser_version="sec-tickers-1",
        notes="official ticker→CIK map",
    )
    return {str(v["ticker"]).upper(): cik10(str(v["cik_str"])) for v in json.loads(body).values()}


def link_price_security(session: Session, price_sid: str | None, anchor_sid: str) -> str:
    """Link the security that carries the prices to the SEC issuer (facts apply to every security of the issuer). Returns a status string."""
    if price_sid is None or price_sid == anchor_sid:
        return "SAME_SECURITY" if price_sid == anchor_sid else "NO_PRICE_SECURITY"
    anchor, price = session.get_one(Security, anchor_sid), session.get_one(Security, price_sid)
    if price.issuer_id is None:
        price.issuer_id = anchor.issuer_id
        return "LINKED"
    return "ALREADY_LINKED" if price.issuer_id == anchor.issuer_id else "CONFLICT_DIFFERENT_ISSUER"


def add_profile(
    session: Session, store: ArchiveStore, ua: str, cik: str, security_id: str, ticker: str
) -> str | None:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    body = _get(url, ua)
    row = archive_document(
        session,
        store,
        provider="SEC_SUBMISSIONS",
        source_identifier=url,
        data=body,
        mime_type="application/json",
        parser_version="profile-1",
        notes="company profile",
    )
    if session.scalars(
        select(SecurityProfile.profile_id).where(
            SecurityProfile.security_id == security_id, SecurityProfile.source_sha256 == row.sha256
        )
    ).first():
        return None
    j = json.loads(body)
    sic = str(j.get("sic") or "") or None
    session.add(
        SecurityProfile(
            security_id=security_id, current_ticker=ticker, display_name=j["name"], exchange=(j.get("exchanges") or [None])[0], country="US", sic=sic, sic_description=j.get("sicDescription"), sector=division(sic),
            industry=j.get("sicDescription"), profile_type=profile_type(sic), source="SEC_SUBMISSIONS", source_url=url, archive_id=row.archive_id, source_sha256=row.sha256,
        )
    )  # fmt: skip
    return f"{j['name']} · SIC {sic} {j.get('sicDescription')} → {profile_type(sic)}"


def ingest_fundamentals(
    session: Session,
    settings: Settings,
    provider: SECEdgarFundamentalProvider,
    store: ArchiveStore,
    tickers: list[str],
    progress: Any = None,
) -> dict[str, dict[str, Any]]:
    """Per ticker: SEC ticker→CIK, issuer + filings + facts (point-in-time by accession), link to the priced security, SEC profile. One ticker at a time: a failure keeps earlier work."""
    from pitquant.positions.universe_ingest import find_security

    ua = os.environ.get("PITQUANT_SEC_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "SOURCE_NOT_CONFIGURED: export PITQUANT_SEC_USER_AGENT with your name and e-mail (SEC fair-access policy); it is never stored"
        )
    cmap = ticker_map(session, store, ua)
    session.commit()
    out: dict[str, dict[str, Any]] = {}
    for t in tickers:
        t = t.upper()
        cik = cmap.get(t)
        if cik is None:
            out[t] = {"status": "NO_CIK_IN_SEC_TICKER_MAP"}
            continue
        try:
            price_sid = find_security(session, t)
            reports = ingest_ciks(session, provider, settings, [cik], register_missing=True)
            anchor_sid = security_for_cik(session, settings, cik, register=False)
            link = link_price_security(session, price_sid, anchor_sid)
            prof = add_profile(session, store, ua, cik, price_sid or anchor_sid, t)
            session.commit()
            out[t] = {
                "status": "OK",
                "cik": cik,
                "link": link,
                "profile": prof,
                "report": str(reports[0])[:300],
            }
        except Exception as exc:  # one failing issuer never stops the others
            session.rollback()
            out[t] = {"status": "FAILED", "cik": cik, "error": str(exc)[:200]}
        if progress:
            progress(t, out[t])
    return out
