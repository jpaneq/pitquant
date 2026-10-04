"""Public, read-only official endpoints; original bytes are archived, no trading credentials."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort, digest
from pitquant.btc.models import BTCDatum
from pitquant.core.timeutils import utc_now
from pitquant.data.archive import ArchiveStore, archive_document

SPOT = "https://data-api.binance.vision"
FUTURES = "https://fapi.binance.com"
COMMUNITY = "https://community-api.coinmetrics.io/v4"
NETWORK_CANDIDATES = {
    "active_addresses": "AdrActCnt",
    "transaction_count": "TxCnt",
    "transaction_volume": "TxTfrValNtv",
    "fees": "FeeTotNtv",
    "hash_rate": "HashRate",
    "difficulty": "DiffMean",
    "supply": "SplyCur",
    "market_cap": "CapMrktCurUSD",
    "realized_cap": "CapRealUSD",
    "MVRV": "CapMVRVCur",
}
# Raw transaction transfer volume in BTC; no entity labels.
DERIVATIVE_ENDPOINTS = {
    "open_interest": ("/futures/data/openInterestHist", "sumOpenInterest"),
    "basis": ("/futures/data/basis", "basis"),
    "taker_buy_sell_ratio": ("/futures/data/takerlongshortRatio", "buySellRatio"),
    "long_short_ratio": ("/futures/data/globalLongShortAccountRatio", "longShortRatio"),
}


@dataclass
class FetchResult:
    url: str
    status: str
    reason: str | None = None
    earliest: str | None = None
    latest: str | None = None
    raw_hash: str | None = None
    count: int = 0


class PublicProvider:
    def __init__(self, session: Session, store: ArchiveStore):
        self.session, self.store = session, store

    def get(self, base: str, path: str, params: dict[str, Any]) -> tuple[Any, Any]:
        url = base + path + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url, headers={"User-Agent": "PITQuant-BTC-V0", "Accept": "application/json"}
        )
        raw = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == 2:
                    raise
                time.sleep(min(float(exc.headers.get("Retry-After", "1")), 5))
        if raw is None:
            raise ValueError("empty provider response")
        payload = json.loads(raw)
        retrieved = utc_now()
        archive = archive_document(
            self.session,
            self.store,
            provider="BTC_PUBLIC",
            source_identifier=url,
            data=raw,
            mime_type="application/json",
            retrieved_at=retrieved,
            parser_version="btc-provider-v0",
        )
        return payload, archive

    def save(
        self, archive: Any, source: str, metric: str, at: datetime, payload: dict[str, Any]
    ) -> None:
        value_hash = digest(payload)
        latest = self.session.scalar(
            select(BTCDatum)
            .where(
                BTCDatum.source == source,
                BTCDatum.metric == metric,
                BTCDatum.cohort == Cohort.FORWARD_PAPER,
                BTCDatum.exchange_timestamp == at,
            )
            .order_by(BTCDatum.retrieved_at.desc(), BTCDatum.datum_id.desc())
            .limit(1)
        )
        if latest and latest.value_hash == value_hash:
            return
        self.session.add(
            BTCDatum(
                source=source,
                metric=metric,
                cohort=Cohort.FORWARD_PAPER,
                exchange_timestamp=at,
                available_at=max(at, archive.retrieved_at),
                retrieved_at=archive.retrieved_at,
                payload=payload,
                raw_hash=archive.sha256,
                archive_id=archive.archive_id,
                value_hash=value_hash,
            )
        )
        self.session.flush()

    def spot(self, *, earliest: bool = False) -> FetchResult:
        params: dict[str, Any] = {"symbol": "BTCUSDT", "interval": "1d", "limit": 1000}
        if earliest:
            params["startTime"] = 0
        rows, archive = self.get(SPOT, "/api/v3/klines", params)
        closed = [r for r in rows if timestamp(r[6]) < archive.retrieved_at]
        for r in closed:
            # Binance closeTime is the final millisecond; decision boundary is the next midnight.
            self.save(
                archive,
                "BINANCE_SPOT",
                "spot",
                timestamp(r[6] + 1),
                {
                    k: float(v)
                    for k, v in zip(("open", "high", "low", "close", "volume"), r[1:6], strict=True)
                },
            )
        return coverage(archive, [timestamp(r[6] + 1) for r in closed])

    def funding(self, *, earliest: bool = False) -> FetchResult:
        params: dict[str, Any] = {"symbol": "BTCUSDT", "limit": 1000}
        if earliest:
            params["startTime"] = 1
        rows, archive = self.get(FUTURES, "/fapi/v1/fundingRate", params)
        for r in rows:
            self.save(
                archive,
                "BINANCE_FUNDING",
                "funding_rate",
                timestamp(r["fundingTime"]),
                {"value": float(r["fundingRate"]), "symbol": r["symbol"]},
            )
        return coverage(archive, [timestamp(r["fundingTime"]) for r in rows])

    def derivatives(self, metric: str) -> FetchResult:
        path, field = DERIVATIVE_ENDPOINTS[metric]
        params = {"symbol": "BTCUSDT", "period": "1h", "limit": 500}
        if metric == "basis":
            params = {"pair": "BTCUSDT", "contractType": "PERPETUAL", "period": "1h", "limit": 500}
        rows, archive = self.get(FUTURES, path, params)
        for r in rows:
            extra = {"value": float(r[field]), "symbol": "BTCUSDT"}
            for key in ("basisRate", "annualizedBasisRate"):
                if r.get(key) not in (None, ""):
                    extra[key] = float(r[key])
            self.save(archive, "BINANCE_DERIVATIVES", metric, timestamp(r["timestamp"]), extra)
        return coverage(archive, [timestamp(r["timestamp"]) for r in rows])

    def catalog(self) -> tuple[dict[str, Any], FetchResult]:
        obj, archive = self.get(COMMUNITY, "/catalog-all/asset-metrics", {})
        metrics = {
            r["metric"]: r
            for r in obj.get("data", [])
            if any(
                f.get("frequency") == "1d" and "btc" in f.get("assets", [])
                for f in r.get("frequencies", [])
            )
        }
        if not metrics:
            raise ValueError("catalog has no confirmed BTC daily metrics")
        return metrics, FetchResult(
            archive.source_identifier, "AVAILABLE", raw_hash=archive.sha256, count=len(metrics)
        )

    def network(self, metric: str, catalog: dict[str, Any]) -> FetchResult:
        code = NETWORK_CANDIDATES[metric]
        if code not in catalog:
            return FetchResult(COMMUNITY, "UNAVAILABLE", "NOT_IN_COMMUNITY_CATALOG")
        params = {"assets": "btc", "metrics": code, "frequency": "1d", "page_size": 10000}
        latest = self.session.scalar(
            select(func.max(BTCDatum.exchange_timestamp)).where(
                BTCDatum.metric == metric,
                BTCDatum.source == "COIN_METRICS",
                BTCDatum.cohort == Cohort.FORWARD_PAPER,
            )
        )
        if latest:
            params["start_time"] = (
                (latest - timedelta(days=3)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
        obj, archive = self.get(COMMUNITY, "/timeseries/asset-metrics", params)
        times = []
        for r in obj.get("data", []):
            if r.get(code) is not None:
                at = datetime.fromisoformat(r["time"].replace("Z", "+00:00"))
                self.save(
                    archive,
                    "COIN_METRICS",
                    metric,
                    at + timedelta(days=1),
                    {"value": float(r[code]), "metric_id": code, "period_start": at.isoformat()},
                )
                times.append(at)
        result = coverage(archive, times)
        if obj.get("next_page_url"):
            result.status, result.reason = "PARTIAL", "PAGINATION_REMAINS"
        return result


def timestamp(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, UTC)


def coverage(archive: Any, times: list[datetime]) -> FetchResult:
    return FetchResult(
        archive.source_identifier,
        "AVAILABLE" if times else "UNAVAILABLE",
        earliest=min(times).isoformat() if times else None,
        latest=max(times).isoformat() if times else None,
        raw_hash=archive.sha256,
        count=len(times),
    )
