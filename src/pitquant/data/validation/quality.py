"""Data Quality engine: row-level checks that log issues instead of silently fixing (§58, §89)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from pitquant.core.types import DQSeverity
from pitquant.data.providers.base import PriceBar


@dataclass(frozen=True)
class DQFinding:
    check: str
    severity: DQSeverity
    detail: str

    @property
    def blocking(self) -> bool:
        return self.severity in (DQSeverity.HIGH, DQSeverity.BLOCKING)


def _bad(x: float | None) -> bool:
    return x is not None and (math.isnan(x) or math.isinf(x))


def check_bar(bar: PriceBar, expected_currency: str | None = None) -> list[DQFinding]:
    f: list[DQFinding] = []
    o, h, lo, c, v = bar.open, bar.high, bar.low, bar.close, bar.volume
    if any(_bad(x) for x in (o, h, lo, c, v)):
        f.append(DQFinding("non_finite", DQSeverity.BLOCKING, f"{bar.session_date}"))
        return f
    if c is None or c <= 0:
        f.append(DQFinding("non_positive_close", DQSeverity.BLOCKING, f"close={c}"))
    for name, x in (("open", o), ("high", h), ("low", lo)):
        if x is not None and x <= 0:
            f.append(DQFinding(f"non_positive_{name}", DQSeverity.HIGH, f"{name}={x}"))
    if h is not None and lo is not None:
        if h < lo:
            f.append(DQFinding("impossible_ohlc", DQSeverity.HIGH, f"high {h} < low {lo}"))
        for name, x in (("open", o), ("close", c)):
            if x is not None and not (lo - 1e-9 <= x <= h + 1e-9):
                f.append(
                    DQFinding("impossible_ohlc", DQSeverity.HIGH, f"{name} {x} outside [{lo},{h}]")
                )
    if v is not None and v < 0:
        f.append(DQFinding("negative_volume", DQSeverity.HIGH, f"volume={v}"))
    if expected_currency and bar.currency != expected_currency:
        f.append(
            DQFinding(
                "currency_mismatch", DQSeverity.BLOCKING, f"{bar.currency} != {expected_currency}"
            )
        )
    return f


def check_series_gaps(
    sessions_expected: list[date], sessions_present: list[date], max_missing_ratio: float = 0.0
) -> list[DQFinding]:
    present = set(sessions_present)
    missing = [d for d in sessions_expected if d not in present]
    extra = sorted(present - set(sessions_expected))
    out: list[DQFinding] = []
    if extra:
        out.append(
            DQFinding("bar_on_non_session", DQSeverity.HIGH, f"{len(extra)} e.g. {extra[0]}")
        )
    if missing and len(missing) / max(1, len(sessions_expected)) > max_missing_ratio:
        out.append(
            DQFinding("missing_sessions", DQSeverity.MEDIUM, f"{len(missing)} e.g. {missing[0]}")
        )
    return out


def check_price_jump(prev_close: float, close: float, threshold: float = 0.5) -> DQFinding | None:
    """Flags |return| > threshold that is not explained by a recorded corporate action."""
    r = close / prev_close - 1.0
    if abs(r) > threshold:
        return DQFinding("unexplained_price_jump", DQSeverity.MEDIUM, f"return {r:.2%}")
    return None
