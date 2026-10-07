#!/usr/bin/env python3
# ruff: noqa: E501
"""Historical discovery/collection/coverage only. Separate DB, no targets or estimators."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.data.providers.sec_edgar.client import SECClient
from pitquant.data.providers.sec_edgar.provider import (
    ingest_sec_company,
)
from pitquant.db.models import (
    RawSourceArchive,
    SecFiling,
    Security,
    SecurityIdentifierEvidence,
    SecurityProfile,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.jobs.sec_ingest import security_for_cik
from pitquant.research import us_universe_scale as U
from pitquant.research.fundamentals_v1 import sic_group
from pitquant.research.us_sec_collection import CachedPrimaryInstanceProvider
from pitquant.universe.sp500_anchor_graph import reconstruct

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-universe-scale-v1"
STORE = ArchiveStore(ROOT / "data/archive")
DB = WORK / "candidate.db"
VERSION = U.VERSION


def session_factory() -> Any:
    if not DB.exists() or DB.resolve() == (ROOT / "data/pitquant.db").resolve():
        raise ValueError("isolated copied database required")
    return make_session_factory(make_engine("sqlite:///" + str(DB)))


def save(name: str, value: Any) -> None:
    sha = U.write_revision(WORK, name, value)
    (WORK / (name + ".json")).write_bytes(U.encoded(value))
    (WORK / (name + ".revision")).write_text(sha + "\n")


def read(name: str) -> Any:
    return json.loads((WORK / (name + ".json")).read_bytes())


def cache_from_database(session: Any) -> U.EvidenceCache:
    cache = U.EvidenceCache(WORK / "cache", STORE, os.environ["PITQUANT_SEC_USER_AGENT"])
    for record in session.scalars(select(RawSourceArchive).order_by(RawSourceArchive.retrieved_at)):
        if record.source_identifier not in cache.records:
            cache.records[record.source_identifier] = {
                "url": record.source_identifier,
                "sha256": record.sha256,
                "status": 200,
                "content_type": record.mime_type,
                "retrieved_at": record.retrieved_at.isoformat(),
                "publisher": "ARCHIVED_PRIMARY",
                "resolver_version": record.parser_version,
            }
    return cache


def initialize() -> None:
    import hashlib
    import sqlite3
    from contextlib import closing

    if DB.exists():
        raise ValueError("candidate database already exists; preserve its revisions")
    source = ROOT / "data/pitquant.db"
    if not source.exists():
        raise ValueError("historical source database required")
    WORK.mkdir(parents=True, exist_ok=True)
    pending = DB.with_suffix(".initializing.db")
    with (
        closing(sqlite3.connect("file:" + str(source) + "?mode=ro", uri=True)) as original,
        closing(sqlite3.connect(pending)) as destination,
    ):
        original.backup(destination)
    pending.replace(DB)
    checksum = hashlib.sha256()
    with DB.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            checksum.update(block)
    save(
        "origin",
        {
            "source": str(source),
            "copied_database_sha256": checksum.hexdigest(),
            "logical_outcomes_read": False,
            "version": VERSION,
            "initial_code_head": "97743c4c05b676ca4aff633a1afb55fa549274fb",
        },
    )


def discovery() -> None:
    cfg = get_settings()
    with session_factory()() as session:
        rep = reconstruct(session, U.START, U.END, settings=cfg, persist=False)
        source = U.latest_archive(session, STORE, "https://www.sec.gov/files/company_tickers.json")
        if source is None:
            raise ValueError("official SEC ticker map missing")
        roster = U.discover(session, rep, json.loads(source[0]))
        save("roster", roster)
        save(
            "discovery",
            {
                "version": VERSION,
                "period": [str(U.START), str(U.END)],
                "historical_security_periods": sum(len(r["potential_sessions"]) for r in roster),
                "unique_securities": len(roster),
                "sec_ticker_map_hash": source[1],
                "raw_anchor_hash": U.digest([r["anchor_instruments"] for r in roster]),
                "known_cik_candidates": sum(r["cik_candidate"] is not None for r in roster),
                "selection": "historical SEC anchors and dated primary membership events, never current survivors",
                "new_fits": 0,
                "holdout_outcomes_accessed": 0,
                "oot_outcomes_accessed": 0,
            },
        )
    print(U.encoded(read("discovery")).decode(), flush=True)


def historical_discovery() -> None:
    roster = read("roster")
    with session_factory()() as session:
        cache = cache_from_database(session)
    url = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
    response = cache.get(url)
    if response.status != 200:
        save("historical_discovery", {"status": "SOURCE_UNAVAILABLE", "source": cache.records[url]})
        return
    matches = U.historical_cik_matches(response.body, roster)
    added = 0
    for r in roster:
        if r["cik_candidate"]:
            continue
        choices = matches[r["security_id"]]
        r["historical_cik_candidates"] = choices
        if len(choices) == 1:
            r["cik_candidate"] = choices[0]
            r["cik_discovery_source_hash"] = cache.records[url]["sha256"]
            r["candidate_reason"] = "PRIMARY_HISTORICAL_SEC_NAME_REGISTRY_UNIQUE_CIK"
            r["identity_status"] = "PENDING_PRIMARY_SUBMISSIONS"
            if r["official_ticker_legs"]:
                leg = max(
                    r["official_ticker_legs"],
                    key=lambda leg: (leg["effective_date"], leg["event_id"]),
                )
                r["ticker_candidate"] = leg["ticker"]
                r["ticker_discovery_reason"] = (
                    "DATED_EXACT_PRIMARY_TERMINAL_TICKER_NOT_PERMANENT_IDENTITY"
                )
            added += 1
        elif len(choices) > 1:
            r["candidate_reason"] = "AMBIGUOUS_HISTORICAL_PRIMARY_CIK"
    save("roster", roster)
    save(
        "historical_discovery",
        {
            "status": "PARSED",
            "source": cache.records[url],
            "new_unique_cik_candidates": added,
            "matches": matches,
        },
    )
    print("historical unique candidates added", added, flush=True)


def identity() -> None:
    roster = read("roster")
    cfg = get_settings()
    with session_factory()() as session:
        cache = cache_from_database(session)
        primary = {}
        official = defaultdict(list)
        for item in session.scalars(
            select(SecurityIdentifierEvidence).where(
                SecurityIdentifierEvidence.kind == "OFFICIAL",
                SecurityIdentifierEvidence.observed_on <= U.END,
            )
        ):
            if item.id_type in ("CUSIP", "ISIN"):
                if item.source_sha256:
                    STORE.get(item.source_sha256)
                official[item.security_id].append(
                    {
                        "id_type": item.id_type,
                        "value": item.value,
                        "observed_on": str(item.observed_on),
                        "source_url": item.source_url,
                        "sha256": item.source_sha256,
                        "evidence_id": item.evidence_id,
                    }
                )
        for r in roster:
            r["official_identifiers"] = official[r["security_id"]]
        for i, r in enumerate(roster):
            cik = r["cik_candidate"]
            if not cik:
                continue
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            response = cache.get(url)
            if response.status != 200:
                r["identity_status"] = "IDENTITY_UNRESOLVED"
                r["identity_reason"] = "SEC_SUBMISSIONS_UNAVAILABLE"
                r["sec_status"] = response.status
                continue
            profile = json.loads(response.body)
            issuer_okay, issuer_reason = U.verify_issuer_profile(r, profile)
            r["issuer_primary_match"] = issuer_okay
            r["issuer_primary_reason"] = issuer_reason
            dates = list(profile.get("filings", {}).get("recent", {}).get("filingDate", []))
            dates += [
                f["filingFrom"]
                for f in profile.get("filings", {}).get("files", [])
                if f.get("filingFrom")
            ]
            r["issuer_history_start_observed"] = min(dates) if dates else None
            if issuer_okay and not r["ticker_candidate"] and len(profile.get("tickers", [])) == 1:
                r["ticker_candidate"] = profile["tickers"][0]
                r["ticker_discovery_reason"] = (
                    "SINGLE_PRIMARY_PROFILE_TICKER_REQUIRES_HISTORICAL_CROSSCHECK"
                )
            okay, reason = U.verify_profile(r, profile)
            r["identity_reason"] = reason
            r["identity_status"] = "PRIMARY_MATCH" if okay else "IDENTITY_UNRESOLVED"
            r["profile_hash"] = cache.records[url]["sha256"]
            r["sic"] = str(profile.get("sic") or "") or None
            r["sector"] = sic_group(r["sic"]) or "UNKNOWN"
            r["primary_exchange"] = profile.get("exchanges")
            r["primary_former_names"] = profile.get("formerNames", [])
            primary[r["security_id"]] = profile
            archive_document(
                session,
                STORE,
                provider="US_SCALE_SEC_SUBMISSIONS",
                source_identifier=url,
                data=response.body,
                mime_type="application/json",
                parser_version=VERSION,
            )
            session.commit()
            if i % 25 == 0:
                save("roster", roster)
                print(f"identity processed {i + 1}/{len(roster)}", flush=True)
        U.exclude_vendor_collisions(roster)
        for r in roster:
            if not r.get("issuer_primary_match"):
                continue
            cik = r["cik_candidate"]
            anchor = security_for_cik(session, cfg, cik, register=True)
            issuer = session.get_one(Security, anchor).issuer_id
            r["primary_issuer_id"] = issuer
            if r["identity_status"] != "PRIMARY_MATCH":
                session.commit()
                continue
            sec = session.get_one(Security, r["security_id"])
            if sec.issuer_id and sec.issuer_id != issuer:
                r["identity_status"] = "IDENTITY_UNRESOLVED"
                r["identity_reason"] = "ISSUER_CONFLICT"
                continue
            if sec.issuer_id is None:
                sec.issuer_id = issuer
            r["issuer_id"] = issuer
            profile = primary[r["security_id"]]
            if not session.scalars(
                select(SecurityProfile).where(
                    SecurityProfile.security_id == r["security_id"],
                    SecurityProfile.source_sha256 == r["profile_hash"],
                )
            ).first():
                ar = session.scalars(
                    select(RawSourceArchive).where(
                        RawSourceArchive.source_identifier
                        == f"https://data.sec.gov/submissions/CIK{cik}.json",
                        RawSourceArchive.sha256 == r["profile_hash"],
                    )
                ).first()
                session.add(
                    SecurityProfile(
                        security_id=r["security_id"],
                        current_ticker=r["ticker_candidate"],
                        display_name=profile["name"],
                        exchange=(profile.get("exchanges") or [None])[0],
                        country="US",
                        sic=r["sic"],
                        sic_description=profile.get("sicDescription"),
                        sector=r["sector"],
                        profile_type="STANDARD_CORPORATE",
                        source="SEC_SUBMISSIONS",
                        source_url=f"https://data.sec.gov/submissions/CIK{cik}.json",
                        archive_id=ar.archive_id,
                        source_sha256=r["profile_hash"],
                    )
                )
            session.commit()
    save("roster", roster)
    print(
        "identity states " + json.dumps(dict(Counter(r["identity_status"] for r in roster))),
        flush=True,
    )


class BoundedSECProvider(CachedPrimaryInstanceProvider):
    """Restrict all primary ingestion to the historical data-availability window."""

    def submissions(self, session: Any, cik: str) -> Any:
        return [
            f for f in super().submissions(session, cik) if U.PRICE_START <= f.filing_date <= U.END
        ]

    def companyfacts(self, session: Any, cik: str) -> Any:
        from pitquant.research.us_sec_collection import OfflineTransport, cached_header_facts

        facts = [f for f in super().companyfacts(session, cik) if U.PRICE_START <= f.filed <= U.END]
        self.excluded_without_cached_header = 0
        if isinstance(self.client.transport, OfflineTransport):
            existing = set(
                session.scalars(select(SecFiling.accession_number).where(SecFiling.cik == cik))
            )
            facts, self.excluded_without_cached_header = cached_header_facts(
                self.client.transport.cache, cik, facts, existing
            )
        return facts


def fundamentals_prefetched() -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from pitquant.research.fundamentals_v1 import sector_status
    from pitquant.research.us_sec_collection import OfflineTransport, prefetch

    cfg = get_settings()
    roster = read("roster")
    done = read("sec_ingestion") if (WORK / "sec_ingestion.json").exists() else {}
    recover = {
        cik: result
        for cik, result in done.items()
        if result.get("status") == "FAILED"
        and "companyfacts/" in result.get("error", "")
        and "HTTP 404" in result.get("error", "")
    }
    if recover:
        save("sec_ingestion_before_primary_instance_recovery", done)
        done = {cik: result for cik, result in done.items() if cik not in recover}
    pending = {
        r["cik_candidate"]: r
        for r in roster
        if r.get("issuer_primary_match")
        and not sector_status(r.get("sic"))
        and r["cik_candidate"] not in done
    }
    with session_factory()() as session:
        cache = cache_from_database(session)
        cache.min_gap = 0.15  # One global limiter for three workers: <=6.67 SEC requests/sec.
        existing_by_cik = defaultdict(set)
        for row in session.scalars(select(SecFiling).where(SecFiling.xbrl_archive_id.is_not(None))):
            existing_by_cik[row.cik].add(row.accession_number)
        offline = OfflineTransport(cache)
        client = SECClient(
            offline,
            os.environ["PITQUANT_SEC_USER_AGENT"],
            max_requests_per_second=6,
            max_retries=0,
            sleep=lambda _: None,
        )
        provider = BoundedSECProvider(
            client, STORE, cfg.fundamentals.sec.model_copy(update={"coverage_start": U.PRICE_START})
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(
                    prefetch, cache, cik, cfg.fundamentals.sec.forms, existing_by_cik[cik]
                ): cik
                for cik in sorted(
                    pending,
                    key=lambda cik: (
                        pending[cik]["candidate_reason"]
                        != "PRIMARY_HISTORICAL_SEC_NAME_REGISTRY_UNIQUE_CIK",
                        -len(pending[cik]["potential_sessions"]),
                        cik,
                    ),
                )
            }
            for future in as_completed(futures):
                cik = futures[future]
                r = pending[cik]
                fetched = future.result()
                try:
                    sid = security_for_cik(session, cfg, cik, register=True)
                    wanted = set(fetched.get("selected_accessions", []))
                    if wanted and wanted <= existing_by_cik[cik]:
                        result = {
                            "status": "REUSED_PRIMARY_ARCHIVE",
                            "filings_existing": len(wanted),
                            "filings_added": 0,
                            "facts_added": 0,
                        }
                    else:
                        report = ingest_sec_company(session, provider, cik, sid)
                        result = {
                            "status": "COMPLETE"
                            if not report.issues
                            and not report.filings_unresolved
                            and not report.facts_rejected
                            else "PARTIAL",
                            "filings_detected": report.filings_detected,
                            "filings_added": report.filings_inserted,
                            "filings_existing": report.filings_skipped_existing,
                            "filings_unresolved": report.filings_unresolved,
                            "facts_added": report.facts_inserted,
                            "facts_rejected": report.facts_rejected,
                            "filings_recovered_from_instance": report.filings_recovered_from_instance,
                            "issues": report.issues,
                            "facts_excluded_without_cached_header": provider.excluded_without_cached_header,
                        }
                    result["prefetch"] = fetched
                    result["companyfacts_discovery_http_status"] = cache.records.get(
                        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", {}
                    ).get("status")
                    result["primary_instance_only"] = (
                        result["companyfacts_discovery_http_status"] == 404
                    )
                    session.commit()
                    done[cik] = result
                except Exception as exc:
                    session.rollback()
                    done[cik] = {
                        "status": "FAILED",
                        "error": type(exc).__name__ + ": " + str(exc)[:180],
                        "prefetch": fetched,
                    }
                save("sec_ingestion", done)
                print(
                    f"SEC completed {len(done)}/{len(done) + len(pending) - len(set(done) & set(pending))} {r['ticker_candidate'] or cik} "
                    + U.encoded(done[cik]).decode()[:200],
                    flush=True,
                )


def prices(*, replay: bool = False) -> None:
    from pitquant.market.providers.yahoo import YahooChartMarketDataProvider

    roster = read("roster")
    done = read("yahoo_collection") if (WORK / "yahoo_collection.json").exists() else {}
    with session_factory()() as session:
        cache = cache_from_database(session)
    # Yahoo collected sequentially at <=1 request/sec; no concurrent writer on candidate DB.
    cache.min_gap = 1.0
    end = date(
        2026, 10, 7
    )  # Client date; later actions needed solely to restore historical RAW units.
    symbols = {r["ticker_candidate"]: r for r in roster if r["ticker_candidate"]}
    for r in roster:
        if not r["ticker_candidate"] and r["official_ticker_legs"]:
            latest = max(
                r["official_ticker_legs"], key=lambda leg: (leg["effective_date"], leg["event_id"])
            )
            symbols.setdefault(latest["ticker"], r)
    for i, (symbol, r) in enumerate(sorted(symbols.items())):
        if symbol in done and not replay:
            continue
        url = YahooChartMarketDataProvider().url(symbol, U.PRICE_START, end)
        if replay and url not in cache.records:
            raise ValueError("offline replay requires pinned source cache")
        response = cache.get(url)
        if response.status != 200:
            done[symbol] = {
                "status": "BLOCKED",
                "reasons": ["MARKET_DATA_UNAVAILABLE"],
                "http_status": response.status,
                "source_url": url,
                "source_hash": cache.records[url].get("sha256"),
            }
        else:
            try:
                qa = U.audit_chart(
                    response.body, r["security_id"], symbol, r["currency"], delisted=r["delisted"]
                )
                U.write_revision(WORK, "yahoo-" + symbol, qa)
                qa_hash = U.digest(qa)
                done[symbol] = {
                    k: v for k, v in qa.items() if k not in ("bars", "splits", "dividends")
                }
                done[symbol].update(
                    source_url=url,
                    qa_hash=qa_hash,
                    bars_count=len(qa["bars"]),
                    splits_count=len(qa["splits"]),
                    dividends_count=len(qa["dividends"]),
                )
            except Exception as exc:
                done[symbol] = {
                    "status": "BLOCKED",
                    "reasons": ["YAHOO_QA_FAILED"],
                    "error": type(exc).__name__ + ": " + str(exc)[:160],
                    "source_url": url,
                    "source_hash": cache.records[url].get("sha256"),
                }
        save("yahoo_collection", done)
        if i % 20 == 0:
            print(f"Yahoo {i + 1}/{len(symbols)} {symbol} {done[symbol]['status']}", flush=True)
    print("Yahoo states " + str(Counter(r["status"] for r in done.values())), flush=True)


def replay_prices() -> None:
    prices(replay=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=[
            "initialize",
            "discover",
            "identity",
            "historical-discovery",
            "fundamentals",
            "fundamentals-prefetched",
            "prices",
            "replay-prices",
        ],
    )
    args = parser.parse_args()
    {
        "initialize": initialize,
        "discover": discovery,
        "identity": identity,
        "historical-discovery": historical_discovery,
        "fundamentals": fundamentals_prefetched,
        "fundamentals-prefetched": fundamentals_prefetched,
        "prices": prices,
        "replay-prices": replay_prices,
    }[args.stage]()


if __name__ == "__main__":
    main()
