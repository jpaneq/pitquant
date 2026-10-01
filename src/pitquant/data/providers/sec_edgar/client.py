"""SEC EDGAR HTTP client: declared User-Agent, rate limit, retries with exponential backoff.

The transport is injectable so tests (and air-gapped deployments replaying the archive)
never touch the network. SEC fair-access policy requires a User-Agent with contact details
and a moderate request rate; both are configuration (``fundamentals.sec``).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from pitquant.core.errors import ProviderContractError

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
ARCHIVE_DIR_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/"
HEADER_URL = ARCHIVE_DIR_URL + "{acc}.hdr.sgml"
INDEX_URL = ARCHIVE_DIR_URL + "index.json"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    content_type: str


class Transport(Protocol):
    def get(self, url: str, headers: dict[str, str]) -> HttpResponse: ...


class UrllibTransport:
    """Standard-library transport (respects HTTPS_PROXY)."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                return HttpResponse(r.status, r.read(), r.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as e:
            return HttpResponse(e.code, e.read() or b"", e.headers.get("Content-Type", ""))


class SECFetchError(ProviderContractError):
    pass


@dataclass
class SECClient:
    transport: Transport
    user_agent: str
    max_requests_per_second: float = 8.0
    max_retries: int = 5
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    _last: float = field(default=-1e9, init=False)
    requests_made: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if "@" not in self.user_agent:
            raise ProviderContractError(
                "SEC requires a User-Agent with contact e-mail (set PITQUANT_SEC_USER_AGENT)"
            )

    def _throttle(self) -> None:
        min_gap = 1.0 / self.max_requests_per_second
        wait = self._last + min_gap - self.clock()
        if wait > 0:
            self.sleep(wait)
        self._last = self.clock()

    def get(self, url: str) -> HttpResponse:
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            self._throttle()
            self.requests_made += 1
            resp = self.transport.get(url, headers)
            if resp.status == 200:
                return resp
            if resp.status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                self.sleep(delay)
                delay = min(delay * 2, 60.0)
                continue
            raise SECFetchError(f"GET {url} -> HTTP {resp.status}")
        raise SECFetchError(f"GET {url} failed after {self.max_retries} retries")
