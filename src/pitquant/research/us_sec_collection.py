"""Bounded concurrent RAW downloads; global rate controlled by one cache, no DB writes."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from pitquant.data.providers.sec_edgar.client import (
    ARCHIVE_DIR_URL,
    COMPANYFACTS_URL,
    HEADER_URL,
    INDEX_URL,
    SUBMISSIONS_PAGE_URL,
    SUBMISSIONS_URL,
    HttpResponse,
)
from pitquant.data.providers.sec_edgar.parsers import (
    CompanyFact,
    accession_nodash,
    cik10,
    parse_submissions,
    pick_xbrl_instance,
)
from pitquant.data.providers.sec_edgar.provider import SECEdgarFundamentalProvider
from pitquant.research import us_universe_scale as U

BUDGET = 220


def cached_header_facts(
    cache: U.EvidenceCache, cik: str, facts: list[CompanyFact], existing: set[str]
) -> tuple[list[CompanyFact], int]:
    """Aggregate facts the native ingestor would reject for an unavailable header.

    Keep originals in the cache. The native ingestor still validates every kept
    header and reports unavailable filings. Avoid one SQL issue per rejected fact
    when a resource budget has already made the header unavailable.
    """
    valid = set(existing)
    for acc in {fact.accession_number for fact in facts} - existing:
        url = HEADER_URL.format(cik=int(cik), acc_nodash=accession_nodash(acc), acc=acc)
        if cache.records.get(url, {}).get("status") == 200:
            valid.add(acc)
    kept = [fact for fact in facts if fact.accession_number in valid]
    return kept, len(facts) - len(kept)


def prefetch(
    cache: U.EvidenceCache, cik: str, forms: list[str], existing: set[str]
) -> dict[str, Any]:
    attempted = 0
    failures = []

    def fetch(url: str) -> HttpResponse:
        nonlocal attempted
        if url not in cache.records:
            attempted += 1
            if attempted > BUDGET:
                raise RuntimeError("PER_ISSUER_EVIDENCE_BUDGET_EXHAUSTED")
        response = cache.get(url)
        if response.status != 200:
            failures.append({"url": url, "status": response.status})
        if len(failures) >= 5:
            raise RuntimeError("PER_ISSUER_PROVIDER_FAILURE_BUDGET_EXHAUSTED")
        return response

    try:
        response = fetch(SUBMISSIONS_URL.format(cik10=cik))
        if response.status != 200:
            return {"status": "FAILED", "failures": failures, "network_requests": attempted}
        filings, pages = parse_submissions(response.body)
        for name in pages:
            page = fetch(SUBMISSIONS_PAGE_URL.format(name=name))
            if page.status == 200:
                filings.extend(parse_submissions(page.body)[0])
        fetch(COMPANYFACTS_URL.format(cik10=cik))
        selected = sorted(
            (f for f in filings if f.form in forms and U.PRICE_START <= f.filing_date <= U.END),
            key=lambda f: f.accession_number,
        )
        for filing in selected:
            acc = filing.accession_number
            if acc in existing:
                continue
            keys = {"cik": int(cik), "acc_nodash": accession_nodash(acc), "acc": acc}
            header = fetch(HEADER_URL.format(**keys))
            if header.status != 200:
                continue
            index = fetch(INDEX_URL.format(**keys))
            if index.status != 200:
                continue
            instance_name = pick_xbrl_instance(index.body)
            if instance_name:
                fetch(ARCHIVE_DIR_URL.format(**keys) + instance_name)
        return {
            "status": "PREFETCHED" if not failures else "PARTIAL",
            "failures": failures,
            "network_requests": attempted,
            "filings_detected": len(selected),
            "selected_accessions": [f.accession_number for f in selected],
        }
    except (RuntimeError, ValueError, KeyError) as exc:
        return {
            "status": "PARTIAL",
            "failures": failures,
            "network_requests": attempted,
            "error": str(exc),
        }


class OfflineTransport:
    """Ingestion cannot trigger surprise downloads beyond prefetch budgets."""

    def __init__(self, cache: U.EvidenceCache) -> None:
        self.cache = cache

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        if url not in self.cache.records:
            return HttpResponse(404, b"", "CACHE_MISS_BUDGET_EXCLUDED")
        return self.cache.get(url, headers)


class CachedPrimaryInstanceProvider(SECEdgarFundamentalProvider):
    """A genuine cached companyfacts 404 leaves native primary-instance recovery usable.

    Never downgrade header/XBRL failures, 403/429, or an offline budget cache miss.
    No companyfacts value is substituted or inferred. The existing ingestor treats
    these filings as uncited and validates/periodizes their own primary instances.
    """

    def companyfacts(self, session: Session, cik: str) -> list[CompanyFact]:
        transport = self.client.transport
        if isinstance(transport, OfflineTransport):
            entry = transport.cache.records.get(COMPANYFACTS_URL.format(cik10=cik10(cik)))
            if entry and entry["status"] == 404:
                return []
        return super().companyfacts(session, cik)
