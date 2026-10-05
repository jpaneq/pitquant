"""Outcome-blind, security-period research membership (ADR-0056).

Strict index reconstruction remains unchanged. This projection is a research
selection ledger, never an index event, feature, daily universe or price source.
Revisions are content-addressed JSON documents in the existing append-only raw
archive. A caller pins the archive hash/version; no latest-state mutation occurs.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from pitquant.core.hashing import content_hash
from pitquant.data.archive import ArchiveStore, archive_document, sha256_hex
from pitquant.research import first_ml_contract as C
from pitquant.universe.sp500_anchor_graph import GraphReport

VERSION = "d02-membership-evidence-v1"
Tier = Literal["OFFICIAL_DIRECT", "CORROBORATED_HISTORICAL", "UNVERIFIED", "CONFLICTED"]
ACCEPTED = frozenset(("OFFICIAL_DIRECT", "CORROBORATED_HISTORICAL"))
UA_C = "ea33aaa6-2990-475f-b03d-3852d591c274"
UA_EFFECTIVE = date(2016, 4, 8)


@dataclass(frozen=True)
class Claim:
    """One independently produced statement about an exact security/event/date.

    ``upstream`` identifies the producer, not the website serving a copy. Unknown
    upstreams are not counted. Hash duplicates also cannot add independence.
    """

    security_id: str
    event: str
    effective_date: date
    upstream: str | None
    source_hash: str
    official_direct: bool = False
    membership_authority: bool = True


def classify(claims: list[Claim], *, identity_supported: bool, conflicted: bool = False) -> Tier:
    if conflicted:
        return "CONFLICTED"
    usable = [
        c
        for c in claims
        if c.membership_authority
        and "YAHOO" not in (c.upstream or "").upper()
        and len(c.source_hash) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in c.source_hash)
    ]
    if not usable or not identity_supported:
        return "UNVERIFIED"
    keys = {(c.security_id, c.event, c.effective_date) for c in usable}
    if len(keys) != 1:
        return "CONFLICTED"
    if any(c.official_direct for c in usable):
        return "OFFICIAL_DIRECT"
    roots = {c.upstream for c in usable if c.upstream}
    hashes = {c.source_hash for c in usable if c.upstream}
    return "CORROBORATED_HISTORICAL" if len(roots) >= 2 and len(hashes) >= 2 else "UNVERIFIED"


def historical_states(raw: bytes, *, until: date) -> list[tuple[date, frozenset[str]]]:
    """Membership-only reference; discard sealed/post-limit rows before use."""
    out = []
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        day = date.fromisoformat(row["date"])
        if day <= until:
            out.append((day, frozenset(row["tickers"].split(","))))
    by_date: dict[date, frozenset[str]] = {}
    for day, members in out:
        if day in by_date and by_date[day] != members:
            raise ValueError("conflicting historical membership states on one date")
        by_date[day] = members
    return sorted(by_date.items())


def state_at(states: list[tuple[date, frozenset[str]]], day: date) -> frozenset[str]:
    prior = [members for d, members in states if d <= day]
    return prior[-1] if prior else frozenset()


def build_projection(
    rep: GraphReport,
    bridge: dict[str, frozenset[str]],
    configured: dict[str, dict[str, Any]],
    lineage: dict[str, str],
    manifest: dict[str, Any],
    store: ArchiveStore,
    *,
    start: date,
    end: date,
) -> dict[str, Any]:
    """Accept only evidence inputs: no target, price, score or outcome argument.

    Stable periods require the exact-name/class identity bridge, official
    instrument identifiers, agreement of both SEC anchor replays, and agreement
    with an independently produced membership history. Any uncertain lineage is
    excluded locally even if forward/backward happen to agree. Explicit dated
    Tier-2 events may repair their own window, never unrelated securities.
    """
    if end >= C.HOLDOUT[0]:
        raise ValueError("research membership projection cannot enter sealed holdout/OOT")
    sources = manifest["sources"]
    histories = {
        key: historical_states(store.get(sources[key]["sha256"]), until=end)
        for key in ("clenow_original", "clenow_updated")
    }
    ua = manifest["under_armour"]
    ua_claims = [
        Claim(
            UA_C,
            "ADD",
            date.fromisoformat(s["effective_date"]),
            s["upstream"],
            s["sha256"],
            official_direct=s.get("official_direct", False),
        )
        for s in ua["membership_sources"]
        if s.get("effective_date")
    ]
    ua_tier = classify(ua_claims, identity_supported=ua["primary_identity_supported"])
    # A later material official contradiction excludes UA locally; it cannot
    # be overridden by the owner's previous Tier-2 acceptance.
    ua_official_dates = {
        leg.lo
        for segment in rep.segments
        for leg in segment.legs
        if leg.security_id == UA_C
        and leg.kind == "ADD"
        and leg.exact
        and leg.status in ("OFFICIAL_CONFIRMED", "OFFICIAL_REPUBLISHED_CONFIRMED")
        and leg.lo is not None
        and leg.lo <= end
    }
    if any(day != UA_EFFECTIVE for day in ua_official_dates):
        ua_tier = "CONFLICTED"
    resolved_ua = {
        **ua,
        "evidence_tier": ua_tier,
        "official_direct": ua_tier == "OFFICIAL_DIRECT",
        "official_conflicting_dates": sorted(
            str(day) for day in ua_official_dates if day != UA_EFFECTIVE
        ),
    }
    # Verify originals; manifest claims are not a substitute for archived bytes.
    for source in sources.values():
        store.get(source["sha256"])
    for source in ua["primary_sources"] + ua["membership_sources"]:
        store.get(source["sha256"])
    weak = set(rep.weak_identity)
    segs = {f"{s.a.as_of}→{s.b.as_of}": s for s in rep.segments}
    rows: list[dict[str, Any]] = []
    monthly = []
    anchor_exclusions: list[dict[str, Any]] = []
    for cohort in rep.cohorts:
        d = cohort.date
        if not start <= d <= end:
            continue
        seg = segs.get(cohort.segment or "")
        common = set(cohort.forward_set or ()) & set(cohort.backward_set or ())
        uncertain: set[str] = set()
        conflicts: set[str] = set()
        if seg:
            uncertain = {sid for sid, (lo, hi) in seg.windows.items() if lo <= d < hi}
            conflicts = {
                delta.security_identifier
                for delta in seg.deltas
                if (
                    delta.difference_type == "DATE_CONFLICT"
                    or (
                        delta.difference_type == "UNEXPLAINED" and "OFFICIAL" in delta.events_status
                    )
                )
                and delta.window
                and delta.window[0] is not None
                and delta.window[1] is not None
                and delta.window[0] <= str(d) < delta.window[1]
            }
        if UA_C in uncertain and d >= UA_EFFECTIVE and ua_tier in ACCEPTED:
            uncertain.remove(UA_C)
            common.add(UA_C)
        weak_here = {sid for sid in common if lineage.get(sid, sid) in weak}
        for sid in sorted(uncertain | conflicts | weak_here):
            anchor_exclusions.append(
                {
                    "security_id": sid,
                    "decision_session": str(d),
                    "evidence_tier": "CONFLICTED" if sid in conflicts else "UNVERIFIED",
                    "exclusion_reason": "UNRESOLVED_SECURITY_PERIOD",
                    "evidence_version": VERSION,
                }
            )
        if ua_tier == "CONFLICTED" and UA_C in (
            set(cohort.forward_set or ()) | set(cohort.backward_set or ()) | uncertain
        ):
            conflicts.add(UA_C)
        canonical_bad = {lineage.get(s, s) for s in uncertain | conflicts} | weak
        history_key = "clenow_original" if d <= date(2019, 9, 30) else "clenow_updated"
        reference = sources[history_key]
        historical = state_at(histories[history_key], d)
        for sid, security in sorted(configured.items()):
            links = bridge.get(sid, frozenset())
            linked = {lineage.get(s, s) for s in links}
            # Histories often normalize tickers. A dated, exact official leg can
            # cross-check a historical label for the SAME already-linked security;
            # no current ticker or lineage is allowed to resolve identity.
            ticker_legs = [
                leg
                for segment in rep.segments
                for leg in segment.legs
                if leg.security_id in links
                and leg.resolution != "CLASS_SET"
                and leg.exact
                and leg.status in ("OFFICIAL_CONFIRMED", "OFFICIAL_REPUBLISHED_CONFIRMED")
                and leg.lo is not None
                and leg.lo <= d
            ]
            ticker_candidates = {security["ticker"]} | {leg.ticker for leg in ticker_legs}
            matched_tickers = sorted(ticker_candidates & historical)
            positive = bool(links & common)
            identity = bool(links) and not bool(linked & weak)
            bad = bool(linked & canonical_bad)
            row_conflict = bool(linked & {lineage.get(s, s) for s in conflicts})
            proofs: list[dict[str, Any]] = []
            tier: Tier = "UNVERIFIED"
            reason = "NO_SUPPORTED_MEMBERSHIP_AT_T"
            if positive and identity and not bad and seg:
                # Ticker is only a cross-check AFTER instrument identity is proved;
                # it never resolves a link or replaces dated graph security IDs.
                ticker = matched_tickers[0] if matched_tickers else None
                claims = []
                if ticker is not None:
                    anchor_hash = content_hash([seg.a.anchor_id, seg.b.anchor_id, sorted(common)])
                    claims = [
                        Claim(
                            sid,
                            "MEMBER_AT_SESSION_OPEN",
                            d,
                            "STATE_STREET_SEC_ANCHOR_REPLAY",
                            anchor_hash,
                        ),
                        Claim(
                            sid,
                            "MEMBER_AT_SESSION_OPEN",
                            d,
                            reference["upstream"],
                            reference["sha256"],
                        ),
                    ]
                    proofs = [
                        {
                            "anchor_ids": [seg.a.anchor_id, seg.b.anchor_id],
                            "replay_hash": anchor_hash,
                            "event": "MEMBER_AT_SESSION_OPEN",
                            "effective_date": str(d),
                            "upstream": "STATE_STREET_SEC_ANCHOR_REPLAY",
                        },
                        {
                            "archive_id": reference["archive_id"],
                            "sha256": reference["sha256"],
                            "upstream": reference["upstream"],
                            "ticker_crosscheck": ticker,
                            "official_ticker_event_ids": sorted(
                                {leg.event_id for leg in ticker_legs if leg.ticker == ticker}
                            ),
                            "effective_date": str(d),
                            "event": "MEMBER_AT_SESSION_OPEN",
                        },
                    ]
                tier = classify(claims, identity_supported=identity)
                reason = (
                    "HISTORICAL_REFERENCE_DISAGREEMENT_OR_MISSING" if tier == "UNVERIFIED" else ""
                )
            if row_conflict:
                tier, reason = "CONFLICTED", "CONTRADICTORY_MEMBERSHIP_SOURCES"
            elif bad:
                reason = "UNRESOLVED_SECURITY_PERIOD_OR_IDENTITY"
            if UA_C in links and positive and identity and not bad and d >= UA_EFFECTIVE and seg:
                tier, reason, proofs = ua_tier, "", ua["membership_sources"] + ua["primary_sources"]
            state = "MEMBER" if tier in ACCEPTED else "UNKNOWN"
            # Known non-membership is not missing evidence or selection bias.
            if (
                not positive
                and links.isdisjoint(cohort.forward_set or ())
                and links.isdisjoint(cohort.backward_set or ())
                and identity
                and not bad
                and seg
                and not matched_tickers
            ):
                absent_hash = content_hash([seg.a.anchor_id, seg.b.anchor_id, sorted(common)])
                tier = classify(
                    [
                        Claim(
                            sid,
                            "NON_MEMBER_AT_SESSION_OPEN",
                            d,
                            "STATE_STREET_SEC_ANCHOR_REPLAY",
                            absent_hash,
                        ),
                        Claim(
                            sid,
                            "NON_MEMBER_AT_SESSION_OPEN",
                            d,
                            reference["upstream"],
                            reference["sha256"],
                        ),
                    ],
                    identity_supported=identity,
                )
                state = "NON_MEMBER" if tier in ACCEPTED else "UNKNOWN"
                reason = (
                    "NOT_INDEX_MEMBER_AT_T"
                    if state == "NON_MEMBER"
                    else "NONMEMBERSHIP_NOT_CORROBORATED"
                )
                proofs = [
                    {
                        "anchor_ids": [seg.a.anchor_id, seg.b.anchor_id],
                        "effective_date": str(d),
                        "event": "NON_MEMBER_AT_SESSION_OPEN",
                        "upstream": "STATE_STREET_SEC_ANCHOR_REPLAY",
                    },
                    {
                        "archive_id": reference["archive_id"],
                        "sha256": reference["sha256"],
                        "effective_date": str(d),
                        "event": "NON_MEMBER_AT_SESSION_OPEN",
                        "upstream": reference["upstream"],
                    },
                ]
            if tier == "CONFLICTED":
                state = "CONFLICTED"
            included = tier in ACCEPTED and state == "MEMBER"
            rows.append(
                {
                    "security_id": sid,
                    "issuer_id": security.get("issuer_id"),
                    "sector": security.get("sector") or "UNKNOWN",
                    "ticker_label": security["ticker"],
                    "decision_session": str(d),
                    "membership_research_eligible": included,
                    "evidence_tier": tier,
                    "membership_state": state,
                    "exclusion_reason": reason or None,
                    "evidence_version": VERSION,
                    "anchor_security_ids": sorted(links),
                    "provenance": proofs,
                    "exclusion_provenance": {
                        "anchor_ids": [seg.a.anchor_id, seg.b.anchor_id] if seg else [],
                        "uncertain_lineages": sorted(linked & canonical_bad),
                        "identity_bridge_present": bool(links),
                        "historical_reference_archive_id": reference["archive_id"],
                        "historical_reference_sha256": reference["sha256"],
                    }
                    if not included
                    else None,
                }
            )
        month_rows = [r for r in rows if r["decision_session"] == str(d)]
        included_rows = [r for r in month_rows if r["membership_research_eligible"]]
        counts = Counter(r["evidence_tier"] for r in month_rows)
        # A non-empty fully supported cohort is temporally valid; no statistical
        # sample threshold is asserted. Empty months remain blocked, not vacuous.
        valid = bool(included_rows) and bool(seg)
        monthly.append(
            {
                "month": d.strftime("%Y-%m"),
                "decision_session": str(d),
                "configured_relevant_securities": len(month_rows),
                "official_direct": counts["OFFICIAL_DIRECT"],
                "corroborated_historical": counts["CORROBORATED_HISTORICAL"],
                "unverified_excluded": counts["UNVERIFIED"],
                "conflicted_excluded": counts["CONFLICTED"],
                "verified_nonmember_excluded": sum(
                    r["membership_state"] == "NON_MEMBER" for r in month_rows
                ),
                "resolved_securities": counts["OFFICIAL_DIRECT"]
                + counts["CORROBORATED_HISTORICAL"],
                "eligible_securities": len(included_rows),
                "eligible_issuers": len({r["issuer_id"] for r in included_rows if r["issuer_id"]}),
                "eligible_rows": None,
                "rows_lost": None,
                "coverage_pct": round(100 * len(included_rows) / max(1, len(month_rows)), 2),
                "issuers_lost": sorted(
                    {
                        r["issuer_id"]
                        for r in month_rows
                        if not r["membership_research_eligible"] and r["issuer_id"]
                    }
                    - {r["issuer_id"] for r in included_rows if r["issuer_id"]}
                ),
                "status": "READY" if valid else "BLOCKED",
                "strict_status": cohort.status,
                "validity_status": "READY" if valid else "BLOCKED",
            }
        )
    return {
        "evidence_version": VERSION,
        "resolver_code_hash": sha256_hex(Path(__file__).read_bytes()),
        "start": str(start),
        "end": str(end),
        "sources": sources,
        "anchor_provenance": manifest.get("anchor_provenance", {}),
        "under_armour": resolved_ua,
        "accepted_membership_events": [resolved_ua] if ua_tier in ACCEPTED else [],
        "evidence_role": "RETROSPECTIVE_REFERENCE_NOT_A_FEATURE",
        "rows": rows,
        "months": monthly,
        "anchor_security_period_exclusions": anchor_exclusions,
        "outcome_blind": True,
        "coverage_evaluated": False,
    }


def persist_projection(
    session: Session, store: ArchiveStore, projection: dict[str, Any]
) -> dict[str, str]:
    resolver = Path(__file__).read_bytes()
    if projection.get("resolver_code_hash") == sha256_hex(resolver):
        code = archive_document(
            session,
            store,
            provider="D02_MEMBERSHIP_RESOLVER_SOURCE",
            source_identifier=VERSION + ":" + sha256_hex(resolver),
            data=resolver,
            mime_type="text/plain",
            parser_version=VERSION,
        )
        projection["resolver_archive"] = {
            "archive_id": code.archive_id,
            "sha256": code.sha256,
            "raw_document": code.storage_uri,
        }
    raw = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
    row = archive_document(
        session,
        store,
        provider="D02_RESEARCH_MEMBERSHIP_LEDGER",
        source_identifier=VERSION + ":" + content_hash(projection),
        data=raw,
        mime_type="application/json",
        parser_version=VERSION,
    )
    return {
        "archive_id": row.archive_id,
        "sha256": row.sha256,
        "raw_document": row.storage_uri,
        "evidence_version": VERSION,
    }


def load_projection(store: ArchiveStore, sha256: str) -> dict[str, Any]:
    projection: dict[str, Any] = json.loads(store.get(sha256))
    if projection.get("evidence_version") != VERSION:
        raise ValueError("unsupported membership evidence version")
    return projection


def source_manifest(path: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(path.read_text())
    if manifest.get("evidence_version") != VERSION:
        raise ValueError("unsupported membership evidence manifest")
    return manifest


def context_extra(projection: dict[str, Any]) -> dict[str, Any]:
    """Expose a pinned projection to the unique first-ML eligibility function."""
    if projection.get("evidence_version") != VERSION:
        raise ValueError("unsupported membership evidence version")
    periods = {}
    for row in projection["rows"]:
        day = date.fromisoformat(row["decision_session"])
        if day >= C.HOLDOUT[0]:
            raise ValueError("membership ledger enters sealed holdout/OOT")
        key = (row["security_id"], day)
        if key in periods:
            raise ValueError("duplicate security-period in membership ledger")
        if row.get("membership_research_eligible") and (
            row.get("evidence_tier") not in ACCEPTED
            or row.get("evidence_version") != VERSION
            or not row.get("provenance")
        ):
            raise ValueError("included membership row lacks supported evidence")
        periods[key] = row
    return {
        "membership_policy_version": VERSION,
        "membership_periods": periods,
        "membership_projection_dates": {
            date.fromisoformat(m["decision_session"]) for m in projection["months"]
        },
        "membership_ledger_hash": projection.get("ledger", {}).get("sha256")
        or content_hash(projection),
    }
