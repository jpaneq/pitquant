"""Reviewed primary corporate releases for D-02 (ADR-0036).

Closed, auditable evidence specifications, not inferred corporate events. Each application
requires the archived original, all declared clauses and both official 13(f) identifiers.
The network is confined to the ingestion script; this module only reads the archive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, SecurityTickerAlias
from pitquant.universe.identity_bridge import (
    ResolutionResult,
    _entry,
    add_cusip_evidence,
    link_same_security,
)
from pitquant.universe.identity_events import _find
from pitquant.universe.sp500_rename_links import _plain

VERSION = "d02-documentary-1"


@dataclass(frozen=True)
class DocumentaryEvent:
    key: str
    url: str
    published: date
    clauses: tuple[str, ...]
    old_name: str
    old_cusip: str
    new_cusip: str
    old_quarter: str
    new_quarter: str
    legal_date: date | None
    ticker_date: date
    old_ticker: str
    new_ticker: str
    event_type: str = "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY"
    ratio: float | None = None
    new_isin: str | None = None
    old_isin: str | None = None
    mime: str = "text/html"
    support: tuple[tuple[str, date, tuple[str, ...]], ...] = ()


EVENTS: tuple[DocumentaryEvent, ...] = (
    DocumentaryEvent(
        "QUINTILES_IQVIA",
        "https://ir.iqvia.com/press-releases/press-release-details/2017/QuintilesIMS-is-now-IQVIA/default.aspx",
        date(2017, 11, 6),
        ("effective November 6, 2017", "Beginning on November 15, 2017", "QuintilesIMS"),
        "Quintiles IMS Holdings, Inc.",
        "74876Y101",
        "46266C105",
        "2017Q3",
        "2018Q1",
        date(2017, 11, 6),
        date(2017, 11, 15),
        "Q",
        "IQV",
    ),
    DocumentaryEvent(
        "KORS_CAPRI",
        "https://www.capriholdings.com/news/news-details/2018/Capri-Holdings-Limited-Completes-Acquisition-of-Versace/default.aspx",
        date(2018, 12, 31),
        (
            "December 31, 2018",
            "changed its name from Michael Kors Holdings Limited",
            "January 2, 2019",
        ),
        "Michael Kors Holdings, Ltd.",
        "G60754101",
        "G1890L107",
        "2018Q3",
        "2019Q1",
        date(2018, 12, 31),
        date(2019, 1, 2),
        "KORS",
        "CPRI",
        new_isin="VGG1890L1076",
    ),
    DocumentaryEvent(
        "TORCHMARK_GLOBE",
        "https://investors.globelifeinsurance.com/news-releases/2019/august/torchmark-corporation-has-officially-been-renamed-globe-life-inc?accessibility=true",
        date(2019, 8, 9),
        (
            "As of August 8, 2019",
            "Torchmark Corporation has officially been renamed Globe Life Inc.",
            "August 9, 2019",
        ),
        "Torchmark Corp.",
        "891027104",
        "37959E102",
        "2019Q1",
        "2019Q3",
        date(2019, 8, 8),
        date(2019, 8, 9),
        "TMK",
        "GL",
    ),
    DocumentaryEvent(
        "HARRIS_L3HARRIS",
        "https://investors.l3harris.com/news/news-details/2019/L3Harris-Technologies-Merger-Successfully-Completed-Board-of-Directors-Leadership-and-Organization-Structure-Announced-07-01-2019/default.aspx",
        date(2019, 7, 1),
        ("June 29, 2019", "Shares of Harris common stock", "will begin trading today", "LHX"),
        "Harris Corp.",
        "413875105",
        "502431109",
        "2019Q1",
        "2019Q3",
        date(2019, 6, 29),
        date(2019, 7, 1),
        "HRS",
        "LHX",
    ),
    DocumentaryEvent(
        "LEUCADIA_JEFFERIES",
        "https://www.miaxglobal.com/sites/default/files/alert-files/LUK_Symbol_Name___43106.pdf",
        date(2018, 5, 23),
        ("Leucadia National Corporation", "47233W109", "May 24, 2018", "Jefferies Financial Group"),
        "Leucadia National Corp.",
        "527288104",
        "47233W109",
        "2018Q1",
        "2018Q3",
        None,
        date(2018, 5, 24),
        "LUK",
        "JEF",
        mime="application/pdf",
    ),
    DocumentaryEvent(
        "MYLAN_VIATRIS",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2020-208",
        date(2020, 11, 16),  # updated body, not the stale November 9 heading
        (
            "closed today, November 16, 2020",
            "One share of Viatris Inc. common stock for each share held.",
            "Regular Way Trading Begins: November 17, 2020",
            "N59465109",
            "92556V106",
        ),
        "Mylan NV",
        "N59465109",
        "92556V106",
        "2020Q3",
        "2021Q1",
        date(2020, 11, 16),
        date(2020, 11, 17),
        "MYL",
        "VTRS",
        event_type="SECURITY_REPLACEMENT_SUCCESSOR",
        ratio=1.0,
        old_isin="NL0011031208",
    ),
)
WBD_CLOSE = "https://ir.wbd.com/news-and-events/financial-news/financial-news-details/2022/Combination-of-Discovery-and-WarnerMedia-Creates-Warner-Bros.-Discovery-Global-Leader-in-Entertainment-and-Streaming/"
WBD_RESULTS = "https://ir.wbd.com/news-and-events/financial-news/financial-news-details/2022/WARNER-BROS.-DISCOVERY-INC.-REPORTS-FIRST-QUARTER-2022-RESULTS/default.aspx"
WBD_SP = "https://press.spglobal.com/2022-04-07-S-P-Dow-Jones-Indices-Announces-Treatment-of-AT-T-Transaction-with-Discovery"
EVENTS += tuple(
    DocumentaryEvent(
        f"DISCOVERY_{kind}_WBD",
        WBD_CLOSE,
        date(2022, 4, 8),
        ("have closed their transaction", "Monday, April 11", "WBD"),
        "Discovery Inc.",
        cusip,
        "934423104",
        "2022Q1",
        "2022Q2",
        date(2022, 4, 8),
        date(2022, 4, 11),
        ticker,
        "WBD",
        event_type="SHARE_CLASS_CHANGE",
        ratio=1.0,
        support=(
            (
                WBD_RESULTS,
                date(2022, 4, 26),
                ("Series A common stock", "Series C common stock", "into one share"),
            ),
            (WBD_SP, date(2022, 4, 7), ("single share class", "remain in the S&P 500")),
        ),
    )
    for kind, cusip, ticker in (("A", "25470F104", "DISCA"), ("C", "25470F302", "DISCK"))
)


def source_specs(events: tuple[DocumentaryEvent, ...] = EVENTS) -> list[tuple[str, date, str, str]]:
    sources = {}
    for event in events:
        sources[event.url] = (
            event.url,
            event.published,
            "D02_PRIMARY_CORPORATE_RELEASE",
            event.mime,
        )
        for url, published, _clauses in event.support:
            provider = (
                "SP_PRESS:press.spglobal.com"
                if url.startswith("https://press.spglobal.com/")
                else "D02_PRIMARY_CORPORATE_RELEASE"
            )
            sources[url] = (url, published, provider, "text/html")
    return list(sources.values())


def verified_source(
    session: Session, store: ArchiveStore, url: str, clauses: tuple[str, ...], limit: date
) -> RawSourceArchive | None:
    valid = []
    for row in session.scalars(
        select(RawSourceArchive).where(RawSourceArchive.source_identifier == url)
    ):
        if row.provider not in ("D02_PRIMARY_CORPORATE_RELEASE", "SP_PRESS:press.spglobal.com"):
            continue
        if row.published_at is None or row.published_at.date() > limit:
            continue
        raw = store.get(row.sha256)
        text = (
            re.sub(
                r"\s+",
                " ",
                " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages),
            ).strip()
            if row.mime_type == "application/pdf"
            else _plain(raw)
        )
        if all(clause in text for clause in clauses):
            valid.append(row)
    return valid[0] if len({row.sha256 for row in valid}) == 1 else None


def apply_documentary_events(
    session: Session,
    store: ArchiveStore,
    *,
    limit: date,
    events: tuple[DocumentaryEvent, ...] = EVENTS,
) -> list[ResolutionResult]:
    results = []
    for event in events:
        if (
            event.published > limit
            or (event.legal_date is not None and event.legal_date > limit)
            or event.ticker_date > limit
        ):
            results.append(ResolutionResult(event.key, False, "outside pre-holdout limit"))
            continue
        row = verified_source(session, store, event.url, event.clauses, limit)
        supporting = [
            verified_source(session, store, url, clauses, limit) if published <= limit else None
            for url, published, clauses in event.support
        ]
        if row is None or any(r is None for r in supporting):
            results.append(
                ResolutionResult(event.key, False, "missing/ambiguous primary original or clauses")
            )
            continue
        old_entry = _entry(session, event.old_quarter, event.old_cusip)
        new_entry = _entry(session, event.new_quarter, event.new_cusip)
        old = _find(session, cusip=event.old_cusip, isin=event.old_isin) or _find(
            session, name=event.old_name
        )
        new = _find(session, cusip=event.new_cusip, isin=event.new_isin)
        if not old_entry or not new_entry or not old or not new or old == new:
            results.append(
                ResolutionResult(event.key, False, "13F/anchor identities not uniquely verified")
            )
            continue
        note = (
            f"{event.key}: primary original {row.archive_id}; legal {event.legal_date}; "
            f"ticker {event.ticker_date}; CUSIP transition PARTIAL; no index exit/entry; "
            f"support hashes {','.join(r.sha256 for r in supporting if r)}"
        )
        add_cusip_evidence(session, old, old_entry, note)
        add_cusip_evidence(session, new, new_entry, note)
        link_same_security(
            session,
            old,
            new,
            "D02_PRIMARY_CORPORATE_RELEASE+SEC_13F_LIST",
            row.sha256,
            event_type=event.event_type,
            effective=datetime.combine(
                event.ticker_date
                if event.event_type in {"SECURITY_REPLACEMENT_SUCCESSOR", "SHARE_CLASS_CHANGE"}
                else (event.legal_date or event.ticker_date),
                datetime.min.time(),
                UTC,
            ),
            ratio=event.ratio,
            note=note,
        )
        have = {
            (a.security_id, a.ticker, a.valid_from, a.valid_to, a.source_hash)
            for a in session.scalars(select(SecurityTickerAlias))
        }
        owner = (
            old
            if event.event_type in {"SECURITY_REPLACEMENT_SUCCESSOR", "SHARE_CLASS_CHANGE"}
            else new
        )
        for sid, ticker, start, end in (
            (owner, event.old_ticker, None, event.ticker_date - timedelta(days=1)),
            (new, event.new_ticker, event.ticker_date, None),
        ):
            if (sid, ticker, start, end, row.sha256) not in have:
                session.add(
                    SecurityTickerAlias(
                        security_id=sid,
                        ticker=ticker,
                        valid_from=start,
                        valid_to=end,
                        bounds="EXACT",
                        source="D02_PRIMARY_CORPORATE_RELEASE",
                        source_hash=row.sha256,
                        confidence="HIGH",
                        note=note[:300],
                    )
                )
        results.append(ResolutionResult(event.key, True, note))
    session.flush()
    return results
