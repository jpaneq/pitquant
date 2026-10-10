#!/usr/bin/env python3
"""Bounded identity repairs from existing dated primary aliases, never fuzzy matches."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from sqlalchemy import select

from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, SecFiling
from pitquant.db.session import make_engine, make_session_factory
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
from pitquant.research import us_targeted_closure as T
from pitquant.research import us_universe_scale as U

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"
STORE = ArchiveStore(ROOT / "data/archive")


def main() -> None:
    source = json.loads((WORK / "sec5/US_LARGE_CAP_RESEARCH_UNIVERSE_V1.json").read_bytes())
    roster = source["roster"]
    prices = json.loads((WORK / "yahoo_collection.json").read_bytes())
    repairs = []
    factory = make_session_factory(make_engine("sqlite:///" + str(WORK / "candidate.db")))
    cache = U.EvidenceCache(WORK / "cache", STORE, os.environ["PITQUANT_SEC_USER_AGENT"], min_gap=1)
    with factory() as session:
        for r in roster:
            if not r.get("profile_hash"):
                continue
            profile = json.loads(STORE.get(r["profile_hash"]))
            alias = T.dated_alias_candidate(r, profile)
            if not alias or alias["ticker"] == r["ticker_candidate"]:
                continue
            primary = session.scalars(
                select(RawSourceArchive).where(
                    RawSourceArchive.sha256 == alias["source_hash"],
                    RawSourceArchive.provider.like("SEC%"),
                )
            ).first()
            if primary is None:
                continue
            accession = re.search(r"/(\d{18})/", primary.source_identifier)
            if accession is None:
                continue
            digits = accession.group(1)
            filing = session.get(SecFiling, digits[:10] + "-" + digits[10:12] + "-" + digits[12:])
            if not filing or filing.cik != r["cik_candidate"] or filing.available_at.date() > U.END:
                continue
            STORE.get(alias["source_hash"])
            old_symbol = r["ticker_candidate"]
            r["ticker_candidate"] = alias["ticker"]
            r["official_ticker_legs"].append(
                {
                    "ticker": alias["ticker"],
                    "effective_date": alias["from"],
                    "kind": "PRIMARY_DATED_CLASS_ALIAS",
                    "event_id": "source:" + alias["source_hash"],
                }
            )
            okay, reason = U.verify_profile(r, profile)
            if not okay:
                r["ticker_candidate"] = old_symbol
                continue
            r.update(
                identity_status="PRIMARY_MATCH",
                identity_reason=reason,
                issuer_id=r["primary_issuer_id"],
                resolved_issuer_id=r["primary_issuer_id"],
            )
            # Initial issuance, when explicitly evidenced by the first exact class alias.
            if old_symbol is None:
                dated = [
                    a["from"]
                    for a in r["dated_ticker_aliases"]
                    if a.get("bounds") == "EXACT" and a.get("from")
                ]
                r["listing_start"] = min(dated)
            symbol = alias["ticker"]
            if symbol not in prices:
                url = YahooChartMarketDataProvider().url(symbol, U.PRICE_START, date(2026, 10, 7))
                response = cache.get(url)
                if response.status == 200:
                    qa = U.audit_chart(response.body, r["security_id"], symbol, "USD")
                    sha = U.write_revision(WORK, "yahoo-" + symbol, qa)
                    prices[symbol] = {
                        "status": qa["status"],
                        "reasons": qa["reasons"],
                        "source_hash": cache.records[url]["sha256"],
                        "qa_hash": sha,
                        "url": url,
                    }
                else:
                    prices[symbol] = {
                        "status": "BLOCKED",
                        "reasons": ["MARKET_DATA_UNAVAILABLE"],
                        "source_hash": cache.records[url].get("sha256"),
                        "url": url,
                    }
            repairs.append(
                {
                    "security_id": r["security_id"],
                    "old_provider_symbol": old_symbol,
                    "provider_symbol": symbol,
                    "historical_tickers": r["dated_ticker_aliases"],
                    "primary_source_hash": alias["source_hash"],
                    "primary_accession": filing.accession_number,
                    "available_at": filing.available_at.isoformat(),
                    "family": "DATED_PRIMARY_SHARE_CLASS_ALIAS",
                }
            )
    U.exclude_vendor_collisions(roster)
    U.write_revision(WORK, "dated_alias_repairs", repairs)
    (WORK / "dated_alias_repairs.json").write_bytes(U.encoded(repairs))
    for name, value in (("roster", roster), ("yahoo_collection", prices)):
        sha = U.write_revision(WORK, name, value)
        (WORK / (name + ".json")).write_bytes(U.encoded(value))
        (WORK / (name + ".revision")).write_text(sha + "\n")
    cache.http.close()
    print(f"dated primary class repairs: {len(repairs)}")


if __name__ == "__main__":
    main()
