# ruff: noqa: E501
"""``pitquant explain-feature``: audit ONE feature without reading code (ADR-0027)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from pitquant.data.point_in_time.context import PITContext
from pitquant.features.v0.engine import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    compute_features,
    decision_time,
)
from pitquant.features.v0.fundamentals import TAG_MAP_VERSION
from pitquant.reconstruct import resolve_security


def explain_feature(
    session: Session,
    security_ref: str,
    decision_session: date,
    feature: str,
    *,
    benchmark_ref: str | None = None,
) -> str:
    if feature not in FEATURE_NAMES:
        raise SystemExit(f"unknown feature {feature!r}; known: {', '.join(FEATURE_NAMES)}")
    sec = resolve_security(session, security_ref)
    bench = resolve_security(session, benchmark_ref).security_id if benchmark_ref else None
    dt = decision_time(decision_session)
    res = next(
        r
        for r in compute_features(
            session, sec.security_id, decision_session, benchmark_security_id=bench
        )
        if r.name == feature
    )
    ctx = PITContext(session, dt)
    bars = ctx.raw_bars(sec.security_id)
    bars = bars[bars.index < decision_session]
    out = [
        f"{sec.name} [{sec.security_id}]  feature={feature}  version={FEATURE_VERSION}  tag_map={TAG_MAP_VERSION}",
        f"decision_at (NYSE open): {dt.isoformat()}   (every input must be available strictly before it)",
        f"formula: {res.formula or '-'}",
        f"VALUE: {res.value!r}   coverage={res.coverage_status}"
        + (f"   reason={res.reason}" if res.reason else ""),
        f"available_at: {res.available_at.isoformat() if res.available_at else None}",
    ]
    if res.intermediates:
        out.append(f"intermediates: {res.intermediates}")
    if res.provenance:
        out.append("fundamental / valuation inputs:")
        for p in res.provenance:
            out.append("  - " + ", ".join(f"{k}={v}" for k, v in p.items() if v is not None))
    if res.intermediates.get("series"):
        if bars.empty:
            out.append("price rows: none before the decision session")
        else:
            n = int(res.intermediates.get("bars_needed", len(bars)))
            used = bars.tail(n)
            out.append(
                f"price rows used ({len(used)} of {len(bars)} available; last = previous session close {bars.index[-1]}, nothing of {decision_session} or later):"
            )
            for d, r in (
                list(used.iterrows())[:3]
                + ([("...", None)] if len(used) > 6 else [])
                + list(used.iterrows())[-3:]
            ):
                if r is None:
                    out.append("    ...")
                else:
                    out.append(
                        f"    {d}  open={r['open']} high={r['high']} low={r['low']} close={r['close']} volume={r['volume']}"
                    )
        acts = [
            a
            for a in ctx.market_actions(sec.security_id)
            if (a.anchor_date or date.min) < decision_session
        ]
        out.append(f"corporate actions known at decision_at: {len(acts)}")
        for a in acts[-5:]:
            out.append(
                f"    {a.kind.value} anchor={a.anchor_date} ratio={a.ratio} cash={a.cash_amount} [{a.provenance.tier.value} {a.provenance.provider}]"
            )
    return "\n".join(out)
