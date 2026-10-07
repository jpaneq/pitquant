"""Outcome-blind historical US expansion, separate from every frozen experiment."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import threading
import time
import urllib.parse
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore
from pitquant.data.providers.sec_edgar.client import HttpResponse
from pitquant.data.providers.sec_edgar.parsers import cik10
from pitquant.db.models import (
    RawSourceArchive,
    Security,
    SecurityIdentifierEvidence,
    SP500AnchorMember,
)
from pitquant.research.membership_bridge import legal_name_key
from pitquant.universe.sp500_anchor_graph import GraphReport

VERSION = "us-large-cap-research-universe-v1"
DATASET = "US_LARGE_CAP_RESEARCH_DATASET_V1"
START, END = date(2014, 9, 1), date(2021, 9, 30)
PRICE_START = date(2011, 1, 1)
EXPECTED_MONTHS = 85


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def write_revision(root: Path, name: str, value: Any) -> str:
    body = encoded(value)
    sha = hashlib.sha256(body).hexdigest()
    path = root / "revisions" / sha / (name + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError("immutable revision corrupted")
    else:
        with path.open("xb") as handle:
            handle.write(body)
    return sha


def check_period(day: date) -> None:
    if not START <= day <= END:
        raise ValueError("outside expansion scope; holdout/OOT prohibited")


def latest_archive(session: Session, store: ArchiveStore, url: str) -> tuple[bytes, str] | None:
    record = session.scalars(
        select(RawSourceArchive)
        .where(RawSourceArchive.source_identifier == url)
        .order_by(RawSourceArchive.retrieved_at.desc())
    ).first()
    return (store.get(record.sha256), record.sha256) if record else None


class EvidenceCache:
    """Append-only source cache; successful replay verifies original SHA, failures stay visible."""

    def __init__(
        self, root: Path, archive: ArchiveStore, user_agent: str, *, min_gap: float = 0.15
    ) -> None:
        self.root, self.archive, self.user_agent = root, archive, user_agent
        self.min_gap = min_gap
        self.last = 0.0
        self.records: dict[str, dict[str, Any]] = {}
        self.path = root / "requests.jsonl"
        root.mkdir(parents=True, exist_ok=True)
        archive.root.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                record = json.loads(line)
                self.records[record["url"]] = record
        self.http = httpx.Client(
            timeout=20,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
        )
        self.requests_made = 0
        self.lock = threading.RLock()
        self.url_locks: dict[str, threading.Lock] = {}

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        with self.lock:
            mutex = self.url_locks.setdefault(url, threading.Lock())
        with mutex:
            return self._get_serial(url, headers)

    def _get_serial(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        prior = self.records.get(url)
        if prior:
            body = self.archive.get(prior["sha256"]) if prior.get("sha256") else b""
            return HttpResponse(prior["status"], body, prior["content_type"])
        status, body, content_type = 0, b"", ""
        error = None
        for attempt in range(3):
            try:
                agent = (
                    self.user_agent
                    if "sec.gov" in urllib.parse.urlparse(url).netloc
                    else "Mozilla/5.0 (PITQuant personal research)"
                )
                with self.lock:
                    delay = max(0.0, self.last + self.min_gap - time.monotonic())
                    if delay:
                        time.sleep(delay)
                    self.last = time.monotonic()
                if shutil.disk_usage(self.archive.root).free < 5 * 1024**3:
                    status, error = 0, "DISK_CAPACITY_RESERVE_5_GIB"
                    break
                with self.lock:
                    self.requests_made += 1
                response = self.http.get(
                    url, headers={"User-Agent": agent, "Accept-Encoding": "identity"}
                )
                status, body, content_type = (
                    response.status_code,
                    response.content,
                    response.headers.get("Content-Type", ""),
                )
                if status != 200:
                    error = f"HTTP_{status}"
            except (OSError, TimeoutError, httpx.HTTPError) as exc:
                status, error = 0, type(exc).__name__
            if status not in (0, 429, 500, 502, 503, 504) or attempt == 2:
                break
            time.sleep(2**attempt)
        sha, _ = self.archive.put(body) if body else (None, None)
        publisher = "SEC" if "sec.gov" in urllib.parse.urlparse(url).netloc else "YAHOO_FINANCE"
        record = {
            "url": url,
            "publisher": publisher,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "status": status,
            "sha256": sha,
            "content_type": content_type,
            "error": error if status != 200 else None,
            "resolver_version": VERSION,
            "role": "RAW_EVIDENCE_NOT_MEMBERSHIP_AUTHORITY"
            if publisher == "YAHOO_FINANCE"
            else "PRIMARY_IDENTITY_OR_FILING",
        }
        with self.lock:
            with self.path.open("a") as handle:
                handle.write(encoded(record).decode() + "\n")
            self.records[url] = record
        return HttpResponse(status, body, content_type)


def discover(
    session: Session, rep: GraphReport, ticker_document: dict[str, Any]
) -> list[dict[str, Any]]:
    names: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for entry in ticker_document.values():
        names[legal_name_key(entry["title"])].add((cik10(str(entry["cik_str"])), entry["ticker"]))
    periods: dict[str, set[str]] = defaultdict(set)
    for cohort in rep.cohorts:
        check_period(cohort.date)
        for sid in set(cohort.forward_set or ()) | set(cohort.backward_set or ()):
            periods[sid].add(str(cohort.date))
    anchor_names: dict[str, set[str]] = defaultdict(set)
    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in session.scalars(select(SP500AnchorMember)):
        if row.security_id in periods:
            anchor_names[row.security_id].add(row.issuer_name)
            evidence[row.security_id].append(
                {
                    "anchor_id": row.anchor_id,
                    "cusip": row.cusip,
                    "isin": row.isin,
                    "title": row.title,
                    "name": row.issuer_name,
                    "identity_basis": row.identity_basis,
                }
            )
    official_ids: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in session.scalars(
        select(SecurityIdentifierEvidence).where(
            SecurityIdentifierEvidence.kind == "OFFICIAL",
            SecurityIdentifierEvidence.observed_on <= END,
        )
    ):
        if item.security_id in periods and item.id_type in ("CUSIP", "ISIN"):
            official_ids[item.security_id].append(
                {
                    "id_type": item.id_type,
                    "value": item.value,
                    "observed_on": str(item.observed_on),
                    "source_url": item.source_url,
                    "sha256": item.source_sha256,
                    "evidence_id": item.evidence_id,
                }
            )
    records = []
    for sid, dates in sorted(periods.items()):
        sec = session.get_one(Security, sid)
        choices = set().union(*(names[legal_name_key(n)] for n in anchor_names[sid]))
        cik, ticker = next(iter(choices)) if len(choices) == 1 else (None, None)
        legs = [
            leg
            for seg in rep.segments
            for leg in seg.legs
            if leg.security_id == sid
            and leg.exact
            and leg.status in ("OFFICIAL_CONFIRMED", "OFFICIAL_REPUBLISHED_CONFIRMED")
            and leg.lo
            and leg.lo <= END
        ]
        official_tickers = sorted({leg.ticker for leg in legs if leg.ticker})
        if not ticker and len(official_tickers) == 1:
            candidates = [
                (cik10(str(v["cik_str"])), v["ticker"])
                for v in ticker_document.values()
                if v["ticker"] == official_tickers[0]
            ]
            if len(candidates) == 1:
                cik, ticker = candidates[0]
        records.append(
            {
                "security_id": sid,
                "issuer_id": sec.issuer_id,
                "names": sorted(anchor_names[sid] or {sec.name}),
                "cik_candidate": cik,
                "ticker_candidate": ticker,
                "identity_status": "PENDING_PRIMARY_SUBMISSIONS" if cik else "IDENTITY_UNRESOLVED",
                "candidate_reason": "EXACT_UNIQUE_NAME_OR_OFFICIAL_TICKER_DISCOVERY"
                if cik
                else "NO_UNIQUE_PRIMARY_CIK_TICKER_MATCH",
                "potential_sessions": sorted(dates),
                "official_ticker_legs": [
                    {
                        "ticker": leg.ticker,
                        "event_id": leg.event_id,
                        "effective_date": str(leg.lo),
                        "kind": leg.kind,
                    }
                    for leg in legs
                ],
                "anchor_instruments": evidence[sid],
                "official_identifiers": official_ids[sid],
                "exchange": sec.exchange,
                "currency": sec.currency,
                "listing_start": str(sec.listing_start) if sec.listing_start else None,
                "listing_end": str(sec.listing_end) if sec.listing_end else None,
                "delisted": sec.delisted,
                "delisting_reason": sec.delisting_reason,
                "successor_security_id": sec.successor_security_id,
                "acquirer_security_id": sec.acquirer_security_id,
            }
        )
    return records


def historical_cik_matches(body: bytes, roster: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Primary SEC historical name registry is discovery only, never membership."""
    wanted = {legal_name_key(n) for r in roster for n in r["names"]}
    names: dict[str, set[str]] = defaultdict(set)
    for line in body.decode("utf-8-sig").splitlines():
        fields = line.rsplit(":", 2)
        if len(fields) == 3 and fields[1].isdigit():
            key = legal_name_key(fields[0])
            if key and key in wanted:
                names[key].add(cik10(fields[1]))
    return {
        r["security_id"]: sorted(set().union(*(names[legal_name_key(n)] for n in r["names"])))
        for r in roster
    }


def verify_issuer_profile(record: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(profile.get("name"), str) or not profile.get("cik"):
        return False, "PRIMARY_PROFILE_SCHEMA_INVALID"
    if cik10(str(profile["cik"])) != record["cik_candidate"]:
        return False, "CIK_CONFLICT"
    known = {legal_name_key(profile["name"])} | {
        legal_name_key(n["name"]) for n in profile.get("formerNames", []) if n.get("name")
    }
    if not {legal_name_key(n) for n in record["names"]} & known:
        return False, "NO_EXACT_OFFICIAL_CURRENT_OR_FORMER_NAME"
    filings = profile.get("filings", {})
    dates = list(filings.get("recent", {}).get("filingDate", []))
    dates += [f["filingFrom"] for f in filings.get("files", []) if f.get("filingFrom")]
    ends = list(filings.get("recent", {}).get("filingDate", []))
    ends += [f["filingTo"] for f in filings.get("files", []) if f.get("filingTo")]
    if dates and min(dates) > str(END):
        return False, "PRIMARY_ISSUER_HISTORY_STARTS_AFTER_RESEARCH_PERIOD"
    if not dates:
        return False, "PRIMARY_ISSUER_HISTORY_UNAVAILABLE"
    periods = record.get("potential_sessions", [])
    if periods and min(dates) > max(periods):
        return False, "PRIMARY_ISSUER_HISTORY_STARTS_AFTER_SECURITY_PERIOD"
    if periods and ends and max(ends) < min(periods):
        return False, "PRIMARY_ISSUER_HISTORY_ENDS_BEFORE_SECURITY_PERIOD"
    return True, "PRIMARY_EXACT_ISSUER_NAME_AND_HISTORY"


def verify_profile(record: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str]:
    okay, reason = verify_issuer_profile(record, profile)
    if not okay:
        return okay, reason
    # Retired issuers need not have a CURRENT ticker. A native exact official
    # dated leg may identify their terminal class; this is never a price splice.
    dated = any(
        leg["ticker"] == record["ticker_candidate"] and leg["effective_date"] <= str(END)
        for leg in record.get("official_ticker_legs", [])
    )
    if not record["ticker_candidate"] or not (
        record["ticker_candidate"] in profile.get("tickers", []) or dated
    ):
        return False, "COMMON_CLASS_TICKER_NOT_IN_PRIMARY_SUBMISSIONS_OR_DATED_EVENT"
    if not (
        any(i["cusip"] or i["isin"] for i in record["anchor_instruments"])
        or record.get("official_identifiers")
    ):
        return False, "NO_PRIMARY_INSTRUMENT_IDENTIFIER"
    return True, "PRIMARY_EXACT_NAME_AND_INSTRUMENT_MATCH"


def terminal_vendor_binding(
    record: dict[str, Any], profile: dict[str, Any], vendor_meta: dict[str, Any]
) -> tuple[bool, str]:
    """Reject recycled vendor tickers; Yahoo names cannot resolve primary identity."""
    names = {legal_name_key(profile["name"])} | {
        legal_name_key(n["name"]) for n in profile.get("formerNames", []) if n.get("name")
    }
    vendor = {
        legal_name_key(str(vendor_meta[k])) for k in ("longName", "shortName") if vendor_meta.get(k)
    }
    if names & vendor:
        return True, "PRIMARY_NAME_VENDOR_QA_AGREEMENT"
    if record["ticker_candidate"] in profile.get("tickers", []):
        return True, "CURRENT_PRIMARY_TICKER_LINK"
    return False, "TERMINAL_VENDOR_ISSUER_BINDING_UNVERIFIED"


def exclude_vendor_collisions(roster: list[dict[str, Any]]) -> None:
    """No typed membership succession alone authorizes survivor price substitution."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in roster:
        if r["identity_status"] == "PRIMARY_MATCH":
            groups[r["ticker_candidate"]].append(r)
    for ticker, group in groups.items():
        reason = None
        if ticker in {"GE", "GOOGL", "RTX", "XOM"}:
            reason = "PREEXISTING_FIRST_ML_IDENTITY_AUDIT_PARTIAL"
        elif len(group) > 1:
            reason = "MULTIPLE_HISTORICAL_INSTRUMENTS_REQUIRE_DATED_VENDOR_BINDING"
        if reason:
            for r in group:
                r.update(identity_status="IDENTITY_UNRESOLVED", identity_reason=reason)


def summarize_counts(values: list[int]) -> dict[str, Any]:
    return {
        "minimum": min(values, default=0),
        "p10": float(np.quantile(values, 0.1)) if values else 0,
        "median": float(np.median(values)) if values else 0,
        "p90": float(np.quantile(values, 0.9)) if values else 0,
        "maximum": max(values, default=0),
    }


def aggregate(rows: list[dict[str, Any]], months: list[str]) -> dict[str, Any]:
    by_month = []
    stages = ("MEMBERSHIP", "PRICE", "FUNDAMENTALS", "COMBINED")
    for month in months:
        group = [r for r in rows if r["month"] == month]
        ids = {
            stage: {r["issuer_id"] for r in group if r["issuer_id"] and r["eligibility"][stage]}
            for stage in stages
        }
        counts = {
            "historical_membership_count": len(group),
            "membership_verified": sum(
                r["membership_tier"] in ("OFFICIAL_DIRECT", "CORROBORATED_HISTORICAL")
                for r in group
            ),
            "price_eligible": len(ids["PRICE"]),
            "fundamental_eligible": len(ids["FUNDAMENTALS"]),
            "combined_eligible": len(ids["COMBINED"]),
            "unique_issuers": len(ids["COMBINED"]),
            "unique_securities": sum(r["eligibility"]["COMBINED"] for r in group),
        }
        for reason, key in (
            ("MEMBERSHIP", "excluded_membership"),
            ("IDENTITY", "excluded_identity"),
            ("PRICE", "excluded_price"),
            ("FUNDAMENTALS", "excluded_fundamentals"),
            ("UNSUPPORTED_SECTOR", "unsupported_sector"),
        ):
            counts[key] = sum(reason in r["blockers"] for r in group)
        by_month.append(
            {
                "month": month,
                **counts,
                "issuer_counts": {stage: len(ids[stage]) for stage in stages},
            }
        )
    stats = {
        stage: summarize_counts([m["issuer_counts"][stage] for m in by_month]) for stage in stages
    }
    impact: dict[str, set[tuple[str, str]]] = defaultdict(set)
    sectors: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        unit = (row["issuer_id"], row["month"])
        if not row["issuer_id"]:
            continue
        for reason in row["blockers"]:
            impact[reason].add(unit)
        if row["eligibility"]["COMBINED"]:
            sectors[row["sector"]].add(unit)
    total = sum(len(s) for s in sectors.values())
    return {
        "months": by_month,
        "cross_section": stats,
        "combined_issuer_months": total,
        "sector_distribution": {
            s: {
                "issuers": len({i for i, _ in units}),
                "issuer_months": len(units),
                "percentage": 100 * len(units) / total if total else None,
            }
            for s, units in sorted(sectors.items())
        },
        "blocker_issuer_months": dict(
            sorted(((r, len(units)) for r, units in impact.items()), key=lambda p: (-p[1], p[0]))
        ),
        "exclusion_counts_overlap": True,
        "scientific_coverage_gate": "NOT_DEFINED",
        "engineering_milestone_200": stats["COMBINED"]["minimum"] >= 200,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "new_fits": 0,
        "dev_adaptive_iteration": 2,
    }


def historical_chart(body: bytes) -> bytes:
    """Keep historical quotations only; retain later splits solely to undo vendor adjustment.

    Later quote values are never examined or transformed. The original download is
    opaque archived evidence. No future return/label is constructed from any bar.
    """
    doc = json.loads(body)
    result = doc["chart"]["result"][0]
    allowed_meta = {
        "symbol",
        "currency",
        "instrumentType",
        "firstTradeDate",
        "exchangeTimezoneName",
        "gmtoffset",
        "exchangeName",
        "fullExchangeName",
        "timezone",
    }
    result["meta"] = {k: v for k, v in result.get("meta", {}).items() if k in allowed_meta}
    timestamps = result.get("timestamp") or []
    idx = [
        i
        for i, t in enumerate(timestamps)
        if PRICE_START <= datetime.fromtimestamp(t, UTC).date() <= END
    ]
    result["timestamp"] = [timestamps[i] for i in idx]
    for kind in ("quote", "adjclose"):
        for fields in (result.get("indicators") or {}).get(kind, []):
            for key, values in list(fields.items()):
                fields[key] = [values[i] if i < len(values) else None for i in idx]
    events = result.get("events") or {}
    for kind in ("dividends", "capitalGains"):
        if kind in events:
            events[kind] = {
                k: v
                for k, v in events[kind].items()
                if datetime.fromtimestamp(v["date"], UTC).date() <= END
            }
    return encoded(doc)


def audit_chart(
    body: bytes, sid: str, symbol: str, currency: str, *, delisted: bool = False
) -> dict[str, Any]:
    from pitquant.data.calendars.market_calendar import get_calendar
    from pitquant.market.providers.yahoo import YahooChartMarketDataProvider

    doc = json.loads(body)
    result = doc["chart"]["result"][0]
    meta = result["meta"]
    if meta.get("symbol") != symbol or meta.get("instrumentType") != "EQUITY":
        return {
            "status": "BLOCKED",
            "reasons": ["VENDOR_INSTRUMENT_MISMATCH"],
            "bars": [],
            "splits": [],
            "dividends": [],
        }
    trimmed = historical_chart(body)
    batch = YahooChartMarketDataProvider().normalize(sid, symbol, trimmed)
    replay = YahooChartMarketDataProvider().normalize(sid, symbol, trimmed)
    if batch != replay:
        raise ValueError("Yahoo deterministic replay mismatch")
    bars = [b for b in batch.bars if PRICE_START <= b.session_date <= END]
    reasons = []
    if not bars:
        reasons.append("MARKET_DATA_UNAVAILABLE")
    if meta.get("currency") != currency:
        reasons.append("CURRENCY_MISMATCH")
    invalid = [
        str(b.session_date)
        for b in bars
        if not all(
            v is not None and math.isfinite(v) and v > 0 for v in (b.open, b.high, b.low, b.close)
        )
        or b.low is None
        or b.high is None
        or b.open is None
        or b.close is None
        or not b.low <= b.open <= b.high
        or not b.low <= b.close <= b.high
    ]
    if invalid:
        reasons.append("IMPOSSIBLE_OHLC")
    cal = get_calendar("XNYS")
    missing = []
    coverage = 0.0
    if bars:
        present = {b.session_date for b in bars}
        expected = cal.sessions(bars[0].session_date, bars[-1].session_date)
        missing = [str(d) for d in expected if d not in present]
        coverage = len(present & set(expected)) / max(len(expected), 1)
        if coverage < (0.95 if delisted else 0.98):
            reasons.append("MISSING_SESSIONS")
        first = meta.get("firstTradeDate")
        inception = datetime.fromtimestamp(first, UTC).date() if first else None
        needed = cal.session_on_or_after(max(PRICE_START, inception or PRICE_START))
        if bars[0].session_date > needed:
            reasons.append("LEADING_HISTORY_UNVERIFIED")
    actions: list[dict[str, Any]] = [
        {
            "kind": a.kind.value,
            "ex_date": str(a.ex_date),
            "ratio": a.ratio,
            "cash_amount": a.cash_amount,
            "available_at": a.available_at.isoformat(),
        }
        for a in batch.actions
        if a.ex_date and a.ex_date <= END
    ]
    return {
        "status": "READY" if not reasons else "BLOCKED",
        "reasons": reasons,
        "first_date": str(bars[0].session_date) if bars else None,
        "last_date": str(bars[-1].session_date) if bars else None,
        "coverage": coverage,
        "missing_periods": missing,
        "invalid_dates": invalid,
        "currency": meta.get("currency"),
        "provider_contract": "yahoo-market-data-v1",
        "raw_adjusted_semantics": (
            "split-adjusted OHLC restored using all archived splits; "
            "adjusted close QA only; pre-split volume withheld"
        ),
        "deterministic_replay": True,
        "source_hash": hashlib.sha256(body).hexdigest(),
        "trimmed_hash": hashlib.sha256(trimmed).hexdigest(),
        "bars": [
            {
                "session": str(b.session_date),
                "close_at": b.available_at.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ],
        "splits": [a for a in actions if "SPLIT" in a["kind"]],
        "dividends": [a for a in actions if a["kind"] == "CASH_DIVIDEND"],
    }
