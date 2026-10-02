"""Vendor vs OFFICIAL corporate actions (ADR-0024): the official event always wins.

``compare_with_official`` never edits either side. A vendor event that differs from the
official one is reported as ``VENDOR_DISAGREEMENT`` with the exact fields; the difference is
NOT explained unless the data prove it (a vendor amount is never decomposed into guessed
components). Kind differences between a special and a regular dividend are informational:
vendors rarely label specials.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from sqlalchemy.orm import Session

from pitquant.db.models import DataQualityIssue
from pitquant.market.normalized import CorporateAction, CorporateActionKind

_DIV = {CorporateActionKind.CASH_DIVIDEND, CorporateActionKind.SPECIAL_DIVIDEND}
_SPLIT = {CorporateActionKind.SPLIT, CorporateActionKind.REVERSE_SPLIT}


class Agreement(StrEnum):
    MATCH = "MATCH"
    VENDOR_DISAGREEMENT = "VENDOR_DISAGREEMENT"
    MISSING_IN_VENDOR = "MISSING_IN_VENDOR"


@dataclass
class Comparison:
    official: CorporateAction
    vendor: CorporateAction | None
    status: Agreement
    differences: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    explanation: str = "none attempted: a vendor value is not decomposed without separate events"


def _cls(a: CorporateAction) -> str:
    return "DIV" if a.kind in _DIV else "SPLIT" if a.kind in _SPLIT else a.kind.value


def compare_with_official(
    official: Sequence[CorporateAction],
    vendor: Sequence[CorporateAction],
    *,
    window_days: int = 5,
    cash_tol: float = 1e-6,
) -> list[Comparison]:
    out: list[Comparison] = []
    for o in official:
        oa = o.anchor_date
        cands = [
            v
            for v in vendor
            if _cls(v) == _cls(o)
            and oa is not None
            and v.anchor_date is not None
            and abs((v.anchor_date - oa).days) <= window_days
        ]
        if not cands:
            out.append(Comparison(o, None, Agreement.MISSING_IN_VENDOR))
            continue
        v = min(cands, key=lambda x: abs((x.anchor_date or date.min) - oa))  # type: ignore[operator]
        diffs: list[str] = []
        info: list[str] = []
        if v.anchor_date != oa:
            diffs.append(f"anchor date: official {oa} vs vendor {v.anchor_date}")
        if o.ratio is not None and (v.ratio is None or abs(v.ratio - o.ratio) > 1e-9):
            diffs.append(f"ratio: official {o.ratio} vs vendor {v.ratio}")
        if o.cash_amount is not None and (
            v.cash_amount is None or abs(v.cash_amount - o.cash_amount) > cash_tol
        ):
            diffs.append(f"cash_amount: official {o.cash_amount} vs vendor {v.cash_amount}")
        for f in ("announcement_date", "record_date", "payment_date"):
            ov, vv = getattr(o, f), getattr(v, f)
            if ov is not None and vv is not None and ov != vv:
                diffs.append(f"{f}: official {ov} vs vendor {vv}")
        if o.kind is not v.kind:
            info.append(f"kind: official {o.kind.value} vs vendor {v.kind.value}")
        out.append(
            Comparison(
                o, v, Agreement.VENDOR_DISAGREEMENT if diffs else Agreement.MATCH, diffs, info
            )
        )
    return out


def record_disagreements(session: Session, security_id: str, comps: Sequence[Comparison]) -> int:
    n = 0
    for c in comps:
        if c.status is Agreement.MATCH:
            continue
        session.add(
            DataQualityIssue(
                entity="corporate_action_events",
                security_id=security_id,
                check_name=c.status.value,
                severity="medium",
                details={
                    "official_provider": c.official.provenance.provider,
                    "official_anchor": str(c.official.anchor_date),
                    "vendor_provider": c.vendor.provenance.provider if c.vendor else None,
                    "differences": c.differences,
                    "info": c.info,
                    "explanation": c.explanation,
                    "winner": "OFFICIAL",
                },
            )
        )
        n += 1
    session.flush()
    return n
