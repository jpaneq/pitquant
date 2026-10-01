"""Total-return engine on RAW prices + normalized corporate actions (ADR-0021).

Only raw closes and actions known at ``as_of`` (``available_at <= as_of``) are used; a
vendor's adjusted series is never an input. Daily gross return on session t (one share
held at t-1):

    R_t = s_t · (P_t + D_t) / P_{t-1} + V_t / P_{t-1}

* s_t: shares received per share held on a split / reverse split / stock dividend ex-date;
* D_t: cash per (post-split) share on its ex-date (ordinary, special, return of capital) —
  reinvested at the close of t;
* V_t: value per held share distributed in kind (spin-off) on its ex-date. It needs a
  valuation: the vendor/official value per share, or the spun-off security's first close ×
  ratio. Without one the engine FAILS (no silent zero).

Terminal events end the position (never dropped as missing data):
* CASH_ACQUISITION: cash per share at the effective date;
* STOCK_ACQUISITION: ratio × acquirer close at the effective date (acquirer price needed);
* BANKRUPTCY: recovery per share if stated, else 0;
* DELISTING / MERGER without stated consideration: last traded close, flagged.

Rights issues and scrip dividends need the official terms (subscription price, ratio,
rights value) and are refused unless their valuation is given (``details`` →
``value_per_share``), as complex Spanish events must come from BME/CNMV.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from pitquant.core.errors import DataQualityError, PITQuantError
from pitquant.core.timeutils import require_aware
from pitquant.market.normalized import CorporateAction, CorporateActionKind

K = CorporateActionKind
SHARE_KINDS = {K.SPLIT, K.REVERSE_SPLIT, K.STOCK_DIVIDEND}
CASH_KINDS = {K.CASH_DIVIDEND, K.SPECIAL_DIVIDEND, K.RETURN_OF_CAPITAL}
IN_KIND = {K.SPINOFF, K.RIGHTS_ISSUE, K.SCRIP_DIVIDEND}
TERMINAL = {K.CASH_ACQUISITION, K.STOCK_ACQUISITION, K.BANKRUPTCY, K.DELISTING, K.MERGER}


class InsufficientValuationError(PITQuantError):
    """An action changes value but its valuation is unknown: total return is undefined."""


@dataclass(frozen=True)
class DailyStep:
    session: date
    close: float
    gross: float  # R_t
    notes: tuple[str, ...] = ()


@dataclass
class TotalReturnResult:
    start: date
    end: date  # last session actually used (terminal date if the position ended)
    total_return: float  # Π R_t − 1
    steps: list[DailyStep] = field(default_factory=list)
    terminal: str | None = None
    flags: list[str] = field(default_factory=list)


def total_return(
    closes: Mapping[date, float],
    actions: Sequence[CorporateAction],
    start: date,
    end: date,
    as_of: datetime,
    *,
    acquirer_close: Callable[[str, date], float | None] | None = None,
    spun_off_close: Callable[[str, date], float | None] | None = None,
) -> TotalReturnResult:
    """Total return of one share bought at the close of ``start`` until the close of
    ``end`` (or the terminal event), using only actions known at ``as_of``."""
    as_of = require_aware(as_of, "as_of")
    sessions = sorted(d for d in closes if start <= d <= end)
    if not sessions or sessions[0] != start:
        raise DataQualityError(f"no raw close on the start session {start}")
    for d in sessions:
        if not closes[d] > 0:
            raise DataQualityError(f"non-positive raw close on {d}")
    known = [a for a in actions if a.available_at <= as_of]
    by_day: dict[date, list[CorporateAction]] = {}
    for a in known:
        if (anchor := a.anchor_date) is not None:
            by_day.setdefault(anchor, []).append(a)
    res = TotalReturnResult(start, start, 0.0)
    growth = 1.0
    prev_close = closes[start]
    # terminal events dated strictly after start
    for d in sessions[1:]:
        acts = by_day.get(d, [])
        term = [a for a in acts if a.kind in TERMINAL]
        if term:
            value, note = _terminal_value(term, d, closes, prev_close, acquirer_close)
            g = value / prev_close
            growth *= g
            res.steps.append(DailyStep(d, value, g, (note,)))
            res.end, res.terminal = d, note
            res.total_return = growth - 1.0
            return res
        s, cash, inkind, notes = 1.0, 0.0, 0.0, []
        for a in acts:
            if a.kind in SHARE_KINDS:
                assert a.ratio is not None
                s *= a.ratio
                notes.append(f"{a.kind} x{a.ratio}")
            elif a.kind in CASH_KINDS:
                assert a.cash_amount is not None
                cash += a.cash_amount
                notes.append(f"{a.kind} {a.cash_amount}")
            elif a.kind in IN_KIND:
                v = _in_kind_value(a, d, spun_off_close)
                inkind += v
                notes.append(f"{a.kind} value {v}")
        p = closes[d]
        g = s * (p + cash) / prev_close + inkind / prev_close
        growth *= g
        res.steps.append(DailyStep(d, p, g, tuple(notes)))
        prev_close, res.end = p, d
    # an action dated after the last available close inside the window is an error
    missing = [
        a
        for a in known
        if a.anchor_date
        and start < a.anchor_date <= end
        and a.anchor_date not in closes
        and a.kind not in TERMINAL
    ]
    if missing:
        raise DataQualityError(
            f"actions on days without a raw close: {[str(a.anchor_date) for a in missing]}"
        )
    res.total_return = growth - 1.0
    return res


def _in_kind_value(
    a: CorporateAction, d: date, spun_off_close: Callable[[str, date], float | None] | None
) -> float:
    for k in ("value_per_share", "value_per_share_usd"):
        v = a.details.get(k)
        if v is not None:
            return float(v)
    if a.kind is K.SPINOFF and a.target_key and a.ratio and spun_off_close is not None:
        px = spun_off_close(a.target_key, d)
        if px is not None:
            return a.ratio * px
    raise InsufficientValuationError(
        f"{a.kind} {a.security_key} {d}: no valuation (value_per_share or spun-off price)"
    )


def _terminal_value(
    term: list[CorporateAction],
    d: date,
    closes: Mapping[date, float],
    prev_close: float,
    acquirer_close: Callable[[str, date], float | None] | None,
) -> tuple[float, str]:
    a = term[0]
    if len(term) > 1 and len({t.kind for t in term}) > 1:
        kinds = sorted(t.kind.value for t in term)
        if set(kinds) not in (
            {"DELISTING", "CASH_ACQUISITION"},
            {"DELISTING", "STOCK_ACQUISITION"},
            {"DELISTING", "BANKRUPTCY"},
            {"DELISTING", "MERGER"},
        ):
            raise DataQualityError(f"conflicting terminal events on {d}: {kinds}")
        a = next(t for t in term if t.kind is not K.DELISTING)
    if a.kind is K.CASH_ACQUISITION:
        assert a.cash_amount is not None
        return a.cash_amount, f"CASH_ACQUISITION {a.cash_amount}/share"
    if a.kind is K.STOCK_ACQUISITION:
        if acquirer_close is None or a.target_key is None or a.ratio is None:
            raise InsufficientValuationError(f"STOCK_ACQUISITION {d}: acquirer price needed")
        px = acquirer_close(a.target_key, d)
        if px is None:
            raise InsufficientValuationError(f"STOCK_ACQUISITION {d}: no acquirer close")
        return a.ratio * px, f"STOCK_ACQUISITION {a.ratio} x {a.target_key}@{px}"
    if a.kind is K.BANKRUPTCY:
        rec = float(a.details.get("recovery_per_share", 0.0))
        return rec, f"BANKRUPTCY recovery {rec}"
    last = closes.get(d, prev_close)
    return last, f"{a.kind} without stated consideration: last traded close {last} (flagged)"
