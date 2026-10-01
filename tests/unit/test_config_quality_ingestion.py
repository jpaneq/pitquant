"""Configuration, data quality and idempotent ingestion (§84, §58, §88)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from pitquant.config.settings import DEFAULT_CONFIG_PATH, Settings, load_settings
from pitquant.data.providers.base import PriceBar
from pitquant.data.providers.synthetic import SyntheticMarket
from pitquant.data.validation.quality import check_bar
from pitquant.db.models import DataQualityIssue, Price, Security
from pitquant.jobs import ingest
from pitquant.jobs.demo import load_synthetic_market


def test_default_config_is_valid_and_holdout_fixed(settings: Settings) -> None:
    assert settings.validation.final_holdout.start == date(2022, 10, 1)
    assert settings.execution.mode.value == "next_open"
    assert len(settings.config_hash) == 64


def _write(tmp_path: Path, mutate: object) -> Path:
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())
    mutate(raw)  # type: ignore[operator]
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw))
    return p


def test_weights_must_sum_to_one(tmp_path: Path) -> None:
    def bad(r: dict) -> None:  # type: ignore[type-arg]
        r["scoring"]["weights"]["6m"]["technical"] = 0.9

    with pytest.raises(ValidationError):
        load_settings(_write(tmp_path, bad))


def test_hold_band_required(tmp_path: Path) -> None:
    def bad(r: dict) -> None:  # type: ignore[type-arg]
        r["scoring"]["thresholds"]["p_sell"] = 0.7

    with pytest.raises(ValidationError):
        load_settings(_write(tmp_path, bad))


def test_unknown_config_keys_rejected(tmp_path: Path) -> None:
    def bad(r: dict) -> None:  # type: ignore[type-arg]
        r["execution"]["mod"] = "next_close"

    with pytest.raises(ValidationError):
        load_settings(_write(tmp_path, bad))


def test_impossible_ohlc_detected() -> None:
    bar = PriceBar("k", date(2020, 1, 2), 10, 9, 11, 10, 100, "USD")  # high < low
    assert any(f.check == "impossible_ohlc" for f in check_bar(bar))
    assert any(f.check == "currency_mismatch" for f in check_bar(bar, "EUR"))
    bad_close = PriceBar("k", date(2020, 1, 2), 10, 11, 9, -1, 100, "USD")
    assert any(f.blocking for f in check_bar(bad_close))


def test_ingestion_is_idempotent(factory: sessionmaker[Session], settings: Settings) -> None:
    first = load_synthetic_market(factory, settings, start=date(2019, 1, 1), end=date(2019, 12, 31))
    second = load_synthetic_market(
        factory, settings, start=date(2019, 1, 1), end=date(2019, 12, 31)
    )
    assert first["prices"].inserted > 0
    assert second["prices"].inserted == 0
    assert second["securities"].inserted == 0
    assert second["fundamentals"].inserted == 0
    assert second["membership_sp"].inserted == 0
    with factory() as s:
        n = s.scalar(select(func.count()).select_from(Price))
        assert n == first["prices"].inserted


class _BadBars(SyntheticMarket):
    def bars(self, keys, start, end):  # type: ignore[no-untyped-def]
        out = list(super().bars(keys, start, end))
        b = out[0]
        out[0] = PriceBar(
            b.provider_security_key,
            b.session_date,
            b.open,
            b.low,
            b.high,
            b.close,
            b.volume,
            b.currency,
        )  # swap high/low -> impossible
        return out


def test_bad_bars_rejected_and_logged(factory: sessionmaker[Session], settings: Settings) -> None:
    m = _BadBars(seed=settings.seed)
    with factory() as s:
        ingest.ingest_securities(s, m)
        rep = ingest.ingest_prices(s, m, ["S-A"], date(2019, 1, 1), date(2019, 1, 31))
        assert rep.rejected == 1
        issues = s.scalars(select(DataQualityIssue)).all()
        assert any(i.check_name == "impossible_ohlc" for i in issues)
        s.rollback()


def test_synthetic_data_is_labelled(market: Session) -> None:
    secs = market.scalars(select(Security)).all()
    assert secs and all(s.is_synthetic and s.name.startswith("SYNTHETIC") for s in secs)
