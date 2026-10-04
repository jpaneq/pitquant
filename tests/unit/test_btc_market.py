# ruff: noqa: E501
"""BTC live market display: separation of LIVE quote / 24H rolling / closed MODEL bar; fallbacks; synthetic isolation. Binance responses here are TEST payloads."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pitquant.btc.fixtures import T0, load_synthetic_btc, synthetic_binance_fetch
from pitquant.btc.market import chart_bars, freshness, live_market, split_klines

NOW = datetime(2026, 10, 4, 12, 0, 5, tzinfo=UTC)
DAY = int(datetime(2026, 10, 4, tzinfo=UTC).timestamp() * 1000)
D = 86_400_000


def kline(start: int, o: float, c: float) -> list:
    return [
        start,
        str(o),
        str(max(o, c) + 1),
        str(min(o, c) - 1),
        str(c),
        "10.5",
        start + D - 1,
        "0",
        77,
        "0",
        "0",
        "0",
    ]


KLINES = [
    kline(DAY - 2 * D, 1, 2),
    kline(DAY - D, 2, 3),
    kline(DAY, 3, 4),
]  # the last one is still open at NOW


def fake(price: str = "123.45", klines: list | None = None):
    def fetch(base: str, path: str, params: dict):
        fetch.calls.append((base, path, dict(params)))
        if path.endswith("/ticker/price"):
            return {"symbol": "BTCUSDT", "price": price}
        if path.endswith("/ticker/24hr"):
            return {
                "symbol": "BTCUSDT",
                "lastPrice": price,
                "priceChange": "-5.5",
                "priceChangePercent": "-1.25",
                "highPrice": "130",
                "lowPrice": "120",
                "volume": "50.5",
                "quoteVolume": "6300.1",
                "openTime": DAY,
                "closeTime": DAY + 43_205_000,
            }
        return klines if klines is not None else KLINES

    fetch.calls = []
    return fetch


def test_live_response_parses_quote_24h_and_closed_bar(session):
    f = fake()
    out = live_market(session, f, NOW)
    q = out["quote"]
    assert (
        q["price"] == 123.45
        and q["timestamp_kind"] == "RETRIEVED_AT"
        and q["source"] == "BINANCE_SPOT"
        and out["pair"] == "BTCUSDT"
        and out["model_frequency"] == "1D_UTC"
    )
    assert "exchange_timestamp" not in q and "trade_time" not in q  # no invented trade timestamp
    h = out["rolling_24h"]
    assert (
        h["change"],
        h["change_pct"],
        h["high"],
        h["low"],
        h["volume_btc"],
        h["volume_usdt"],
    ) == (-5.5, -1.25, 130.0, 120.0, 50.5, 6300.1) and h["window"].startswith("24H_ROLLING")
    assert f.calls[0][0] == "https://data-api.binance.vision" and all(
        c[2].get("symbol") == "BTCUSDT" for c in f.calls
    )
    k = next(c for c in f.calls if c[1].endswith("/klines"))[2]
    assert k["interval"] == "1d" and k["timeZone"] == "0" and k["limit"] == 3


def test_last_closed_bar_excludes_the_open_candle():
    closed, forming = split_klines(KLINES, NOW)
    assert (
        closed["close"] == 3.0
        and closed["close_time"] == datetime.fromtimestamp((DAY - 1) / 1000, UTC).isoformat()
    )  # yesterday's bar
    assert (
        forming["close"] == 4.0
        and forming["open_time"] == datetime.fromtimestamp(DAY / 1000, UTC).isoformat()
    )
    # a bar whose closeTime is exactly "now" counts as closed
    assert (
        split_klines(KLINES, datetime.fromtimestamp((DAY + D - 1) / 1000, UTC))[0]["close"] == 4.0
    )


def test_live_payload_marks_the_forming_bar_incomplete_and_model_bar_separate(session):
    out = live_market(session, fake(), NOW)
    assert (
        out["last_closed_daily_bar"]["close"] == 3.0
        and out["last_closed_daily_bar"]["number_of_trades"] == 77
    )
    assert (
        out["forming_daily_bar"]["status"] == "INCOMPLETE"
        and out["forming_daily_bar"]["usage"] == "DISPLAY_ONLY_NOT_MODEL_INPUT"
    )
    assert (
        out["quote"]["price"] != out["last_closed_daily_bar"]["close"]
        and "closed daily bars" in out["model_bar_note"]
    )


@pytest.mark.parametrize(
    ("age", "state"),
    [(0, "LIVE"), (10, "LIVE"), (11, "RECENT"), (60, "RECENT"), (61, "STALE"), (3600, "STALE")],
)
def test_freshness_thresholds(age, state):
    assert freshness(NOW - timedelta(seconds=age), NOW) == state
    assert freshness(None, NOW) == "UNAVAILABLE"


def test_falls_back_to_second_official_base(session):
    calls = []

    def fetch(base, path, params):
        calls.append(base)
        if "vision" in base:
            raise OSError("down")
        return fake()(base, path, params)

    out = live_market(session, fetch, NOW)
    assert (
        out["provenance"]["base_url"] == "https://api.binance.com"
        and out["quote"]["price"] == 123.45
    )


def test_unreachable_without_archive_is_unavailable_never_synthetic(session):
    def down(*a):
        raise OSError("no network")

    out = live_market(session, down, NOW)
    assert (
        out["quote"]["status"] == "UNAVAILABLE"
        and out["quote"]["price"] is None
        and "REAL DATA UNAVAILABLE" in out["reason"]
    )
    assert out["data_mode"] == "REAL" and "SYNTHETIC" not in str(out)


def test_unreachable_with_real_archive_shows_stale_archive(session, tmp_path: Path):
    from types import SimpleNamespace

    from pitquant.btc.contracts import Cohort
    from pitquant.btc.models import BTCDatum
    from pitquant.btc.providers import PublicProvider
    from pitquant.data.archive import ArchiveStore

    load_synthetic_btc(
        session, tmp_path
    )  # saved as SYNTHETIC cohort: must NOT be used as a real fallback

    def down(*a):
        raise OSError("no network")

    assert live_market(session, down, NOW)["quote"]["status"] == "UNAVAILABLE"
    prov = PublicProvider(session, ArchiveStore(tmp_path))
    at = datetime(2026, 10, 4, tzinfo=UTC)
    arch = SimpleNamespace(
        archive_id=session.query(BTCDatum).first().archive_id,
        sha256="a" * 64,
        retrieved_at=at + timedelta(seconds=30),
    )
    prov.save(
        arch,
        "BINANCE_SPOT",
        "spot",
        at,
        {"open": 1.0, "high": 3.0, "low": 0.5, "close": 2.5, "volume": 9.0},
    )
    out = live_market(session, down, NOW)
    assert (
        out["quote"]["status"] == "STALE"
        and out["quote"]["source"] == "BINANCE_SPOT_ARCHIVE"
        and out["quote"]["price"] == 2.5
        and out["quote"]["retrieved_at"] == arch.retrieved_at.isoformat()
    )
    assert (
        out["last_closed_daily_bar"]["close"] == 2.5
        and out["rolling_24h"] is None
        and Cohort.FORWARD_PAPER == "FORWARD_PAPER"
    )


def test_context_series_are_stale_flagged_and_unavailable_keep_reason(session):
    import tempfile
    from types import SimpleNamespace

    from pitquant.btc.models import BTCDatum
    from pitquant.btc.providers import PublicProvider
    from pitquant.data.archive import ArchiveStore

    load_synthetic_btc(session, Path(tempfile.mkdtemp()))
    prov = PublicProvider(session, ArchiveStore(Path(tempfile.mkdtemp())))
    arch = SimpleNamespace(
        archive_id=session.query(BTCDatum).first().archive_id,
        sha256="b" * 64,
        retrieved_at=NOW - timedelta(hours=40),
    )
    prov.save(arch, "BINANCE_FUNDING", "funding_rate", NOW - timedelta(hours=40), {"value": 0.0001})
    prov.save(
        arch, "BINANCE_DERIVATIVES", "open_interest", NOW - timedelta(minutes=30), {"value": 5.0}
    )
    out = live_market(session, fake(), NOW)
    assert (
        out["funding"]["status"] == "STALE"
        and out["funding"]["value"] == 0.0001
        and out["funding"]["as_of"]
        and out["funding"]["source"] == "BINANCE_FUNDING"
    )
    assert (
        out["open_interest"]["status"] == "AVAILABLE" and out["open_interest"]["first_knowledge_at"]
    )
    assert (
        out["basis"]["status"] == "UNAVAILABLE" and out["basis"]["value"] is None
    )  # nothing back-filled
    assert {n["metric"] for n in out["network"]} >= {
        "active_addresses",
        "MVRV",
        "hash_rate",
    } and all(n["status"] == "UNAVAILABLE" and n["reason"] for n in out["network"])


def test_chart_bars_are_real_only_and_mark_gaps(session):
    import tempfile
    from types import SimpleNamespace

    from pitquant.btc.models import BTCDatum
    from pitquant.btc.providers import PublicProvider
    from pitquant.data.archive import ArchiveStore

    load_synthetic_btc(session, Path(tempfile.mkdtemp()))
    assert (
        chart_bars(session, "MAX", NOW)["bars"] == []
    )  # synthetic cohort never reaches the real chart
    prov = PublicProvider(session, ArchiveStore(Path(tempfile.mkdtemp())))
    arch = SimpleNamespace(
        archive_id=session.query(BTCDatum).first().archive_id, sha256="c" * 64, retrieved_at=NOW
    )
    for n in (1, 2, 4):  # day 3 missing
        prov.save(
            arch,
            "BINANCE_SPOT",
            "spot",
            datetime(2026, 10, n, tzinfo=UTC),
            {"open": 1.0, "high": 2.0, "low": 1.0, "close": 1.5, "volume": 1.0},
        )
    bars = chart_bars(session, "1M", NOW)["bars"]
    assert [b["gap_before"] for b in bars] == [False, False, True] and len(bars) == 3
    with pytest.raises(ValueError):
        chart_bars(session, "5Y", NOW)


@pytest.mark.pit
def test_live_quote_never_enters_features_or_snapshots():
    import inspect

    import pitquant.btc.experimental as experimental
    import pitquant.btc.features as features
    import pitquant.btc.research as research

    for mod in (features, research, experimental):
        src = inspect.getsource(mod)
        assert "btc.market" not in src and "live_market" not in src and "LiveQuote" not in src


def test_synthetic_fixture_is_labelled_and_only_through_explicit_mode(session):
    out = live_market(session, synthetic_binance_fetch(NOW), NOW, data_mode="SYNTHETIC_TEST_DATA")
    assert (
        out["data_mode"] == "SYNTHETIC_TEST_DATA"
        and out["warning"] == "SYNTHETIC TEST DATA"
        and out["quote"]["price"] > 0
    )
    assert T0.year == 2026
