"""SEC fundamentals → Feature Engine V0 metrics (ADR-0027). PIT, accession-aware, fail-closed.

* Only facts with ``available_at < decision_at`` are visible; among revisions of the same period
  the latest REVISION KNOWN at the decision wins (restatements are applied only after filing).
* Flows are periodized explicitly: TTM = FY(prev) + YTD(current) - YTD(same period, prior year),
  or the FY value itself at a fiscal year end. YTD facts are never summed as if they were quarters.
* A concept is resolved through a VERSIONED tag map: the candidate with the freshest period wins;
  two candidates with different values for the same period -> ``unresolved_tag`` (fail closed).
* Missing stays missing: ``Metric.value is None`` with a reason; nothing is imputed.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

TAG_MAP_VERSION = "sec-tags-1"

TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": ("StockholdersEquity",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "shares_out": ("EntityCommonStockSharesOutstanding",),
}
DEBT_TAGS = ("LongTermDebt", "DebtCurrent", "LongTermDebtNoncurrent", "LongTermDebtCurrent")


@dataclass(frozen=True)
class Fact:
    concept: str
    period_start: date | None
    period_end: date
    value: float
    unit: str
    available_at: datetime
    accession: str | None
    form: str | None
    revision_id: int = 0
    fact_id: str | None = None


@dataclass
class Metric:
    value: float | None
    reason: str | None = None
    available_at: datetime | None = None
    provenance: list[dict[str, object]] = field(default_factory=list)
    formula: str = ""

    @staticmethod
    def missing(reason: str, formula: str = "") -> Metric:
        return Metric(None, reason, None, [], formula)


def _months(s: date, e: date, tol: int = 12) -> int | None:
    """Nominal months (3/6/9/12) of a period; ``tol`` days: 12 in V0 (frozen), 25 for 52/53-week."""
    d = (e - s).days + 1
    for m in (3, 6, 9, 12):
        if abs(d - round(m * 30.4375)) <= tol:
            return m
    return None


def _near(a: date, b: date, tol: int = 7) -> bool:
    return abs((a - b).days) <= tol


def visible(facts: Iterable[Fact], decision_at: datetime) -> list[Fact]:
    """Latest known revision of each (concept, unit, period) with available_at < decision_at."""
    best: dict[tuple[str, str, date | None, date], Fact] = {}
    for f in facts:
        if f.available_at >= decision_at:
            continue
        k = (f.concept, f.unit, f.period_start, f.period_end)
        cur = best.get(k)
        if cur is None or (f.available_at, f.revision_id) > (cur.available_at, cur.revision_id):
            best[k] = f
    return list(best.values())


def _prov(f: Fact, role: str) -> dict[str, object]:
    return {
        "role": role,
        "concept": f.concept,
        "period": f"{f.period_start}..{f.period_end}",
        "value": f.value,
        "accession": f.accession,
        "form": f.form,
        "available_at": f.available_at.isoformat(),
        "fact_id": f.fact_id,
    }


def _ttm_one(vis: Sequence[Fact], concept: str, unit: str = "USD", tol: int = 12) -> Metric | None:
    fs = [f for f in vis if f.concept == concept and f.unit == unit and f.period_start is not None]
    if not fs:
        return None
    ends = sorted(
        {f.period_end for f in fs if f.period_start and _months(f.period_start, f.period_end, tol)},
        reverse=True,
    )
    for e in ends[:1]:  # only the freshest period end: an older TTM would be stale
        at_e = [
            f
            for f in fs
            if f.period_end == e and f.period_start and _months(f.period_start, f.period_end, tol)
        ]
        fy = next((f for f in at_e if _months(f.period_start, f.period_end, tol) == 12), None)  # type: ignore[arg-type]
        if fy is not None:
            return Metric(
                fy.value, None, fy.available_at, [_prov(fy, "FY")], f"TTM = FY ending {e}"
            )
        cur = max(at_e, key=lambda f: _months(f.period_start, f.period_end, tol) or 0)  # type: ignore[arg-type]
        m = _months(cur.period_start, cur.period_end, tol)  # type: ignore[arg-type]
        assert cur.period_start is not None and m is not None
        prev_fy_end = cur.period_start - timedelta(days=1)
        fy_prev = next(
            (
                f
                for f in fs
                if f.period_start
                and _months(f.period_start, f.period_end, tol) == 12
                and _near(f.period_end, prev_fy_end, 5)
            ),
            None,
        )
        ytd_prior = next(
            (
                f
                for f in fs
                if f.period_start
                and _months(f.period_start, f.period_end, tol) == m
                and _near(f.period_end, _minus_year(e))
                and _near(f.period_start, _minus_year(cur.period_start))
            ),
            None,
        )
        if fy_prev is None or ytd_prior is None:
            return Metric.missing(
                "missing_fundamental",
                f"TTM at {e}: needs FY ending {prev_fy_end} and YTD of the prior year",
            )
        v = fy_prev.value + cur.value - ytd_prior.value
        av = max(f.available_at for f in (fy_prev, cur, ytd_prior))
        return Metric(
            v,
            None,
            av,
            [
                _prov(fy_prev, "FY_prev"),
                _prov(cur, f"YTD_{m}M"),
                _prov(ytd_prior, f"YTD_{m}M_prior_year"),
            ],
            f"TTM = FY({fy_prev.period_end}) + YTD({cur.period_end}) - YTD({ytd_prior.period_end})",
        )
    return None


def _minus_year(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)


def resolve_flow_ttm(
    vis: Sequence[Fact],
    key: str,
    as_of_end: date | None = None,
    tags: tuple[str, ...] | None = None,
    tol: int = 12,
    prefer: tuple[str, ...] | None = None,
) -> Metric:
    """TTM of ``key`` through the versioned tag map. ``as_of_end``: compute the TTM that ENDS at
    that date (used for the prior-year TTM): facts of later periods are ignored."""
    pool = [f for f in vis if as_of_end is None or f.period_end <= as_of_end + timedelta(days=7)]
    res: list[tuple[str, Metric]] = []
    cand = tags if tags is not None else TAGS[key]
    for tag in cand:
        m = _ttm_one(pool, tag, tol=tol)
        if m is not None:
            res.append((tag, m))
    good = [(t, m) for t, m in res if m.value is not None]
    if not good:
        return (
            res[0][1]
            if res
            else Metric.missing("missing_fundamental", f"no fact for any of {cand}")
        )
    freshest = max(_end_of(m) for _, m in good)
    top = [(t, m) for t, m in good if _end_of(m) == freshest]
    if len(top) > 1:
        a, b = top[0][1].value, top[1][1].value
        assert a is not None and b is not None
        if abs(a - b) > 0.01 * max(abs(a), abs(b), 1.0):
            ranked = [x for p in (prefer or ()) for x in top if x[0] == p]
            if (
                ranked
            ):  # explicit, versioned priority; the chosen tag and the discarded value are recorded
                t, m = ranked[0]
                others = ", ".join(f"{ot}={om.value}" for ot, om in top if ot != t)
                m.formula = f"[{t}] (conflict resolved by priority over {others}) " + m.formula
                return m
            return Metric.missing(
                "unresolved_tag",
                f"{key}: {top[0][0]}={a} vs {top[1][0]}={b} for the same period (fail closed)",
            )
    t, m = top[0]
    m.formula = f"[{t}] " + m.formula
    return m


def _end_of(m: Metric) -> str:
    return max(str(p["period"]).split("..")[-1] for p in m.provenance)


def latest_instant(
    vis: Sequence[Fact], key: str, unit: str = "USD", tags: tuple[str, ...] | None = None
) -> Metric:
    best: Fact | None = None
    for tag in tags if tags is not None else TAGS[key]:
        for f in vis:
            if (
                f.concept == tag
                and f.unit == unit
                and f.period_start is None
                and (
                    best is None
                    or (f.period_end, f.available_at) > (best.period_end, best.available_at)
                )
            ):
                best = f
    if best is None:
        return Metric.missing("missing_fundamental", f"no instant fact for {key}")
    return Metric(
        best.value,
        None,
        best.available_at,
        [_prov(best, "instant")],
        f"latest {best.concept} at {best.period_end}",
    )


def instant_near(
    vis: Sequence[Fact], key: str, target: date, unit: str = "USD", tol: int = 25
) -> Fact | None:
    c = [
        f
        for tag in TAGS[key]
        for f in vis
        if f.concept == tag
        and f.unit == unit
        and f.period_start is None
        and abs((f.period_end - target).days) <= tol
    ]
    return min(c, key=lambda f: abs((f.period_end - target).days), default=None)


def average_instant(vis: Sequence[Fact], key: str) -> Metric:
    """(latest + same date one year earlier) / 2 — both known at the decision."""
    cur = latest_instant(vis, key)
    if cur.value is None:
        return cur
    end = date.fromisoformat(str(cur.provenance[0]["period"]).split("..")[-1])
    prior = instant_near(vis, key, _minus_year(end))
    if prior is None:
        return Metric.missing(
            "insufficient_history", f"average {key}: no value one year before {end}"
        )
    return Metric(
        (cur.value + prior.value) / 2.0,
        None,
        max(cur.available_at or prior.available_at, prior.available_at),
        [*cur.provenance, _prov(prior, "prior_year")],
        f"average of {key} at {end} and {prior.period_end}",
    )


def shares_outstanding(vis: Sequence[Fact]) -> Metric:
    """Latest cover-page shares outstanding (dei). Weighted-average shares are NEVER substituted."""
    best: Fact | None = None
    for f in vis:
        if (
            f.concept in TAGS["shares_out"]
            and f.unit in ("shares", "SHARES")
            and (
                best is None
                or (f.period_end, f.available_at) > (best.period_end, best.available_at)
            )
        ):
            best = f
    if best is None:
        return Metric.missing("missing_fundamental", "no EntityCommonStockSharesOutstanding")
    return Metric(
        best.value,
        None,
        best.available_at,
        [_prov(best, "cover_shares")],
        f"shares outstanding at {best.period_end}",
    )


def safe_div(num: Metric, den: Metric, name: str, *, den_positive: bool = False) -> Metric:
    for m in (num, den):
        if m.value is None:
            return Metric.missing(m.reason or "missing_fundamental", f"{name}: input unavailable")
    assert num.value is not None and den.value is not None
    if den.value == 0 or (den_positive and den.value <= 0):
        return Metric.missing("denominator_invalid", f"{name}: denominator {den.value}")
    ats = [m.available_at for m in (num, den) if m.available_at]
    return Metric(
        num.value / den.value,
        None,
        max(ats) if ats else None,
        num.provenance + den.provenance,
        name,
    )


def linear(a: Metric, b: Metric, sign: int, name: str) -> Metric:
    if a.value is None or b.value is None:
        return Metric.missing(a.reason or b.reason or "missing_fundamental", name)
    ats = [m.available_at for m in (a, b) if m.available_at]
    return Metric(
        a.value + sign * b.value, None, max(ats) if ats else None, a.provenance + b.provenance, name
    )


def split_factor_between(actions: Sequence[object], start: date, end: date) -> float:
    """Product of split ratios whose anchor date lies in (start, end]: share counts reported at
    ``start`` must be multiplied by it to be on the share basis of ``end``."""
    f = 1.0
    for a in actions:
        kind = getattr(a, "kind", None)
        ratio = getattr(a, "ratio", None)
        anchor = getattr(a, "anchor_date", None)
        if (
            kind is not None
            and str(getattr(kind, "value", kind)) in ("SPLIT", "REVERSE_SPLIT")
            and ratio
            and anchor
            and start < anchor <= end
        ):
            f *= ratio
    return f
