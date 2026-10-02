"""One economic event, one corporate action: tier-based resolution across sources (ADR-0029).

The same split/dividend may arrive from the issuer page (OFFICIAL) and from a data vendor
(VENDOR). Applying both would count it twice. ``collapse_equivalent`` keeps the highest-tier
record of each economic event and DROPS the others from the calculation (they stay in the
database for QA / ``VENDOR_DISAGREEMENT``):

* splits: same class, anchors within 5 calendar days (and same ratio, else both kept: a
  contradiction must be visible, not silently resolved);
* cash dividends: same class and the same anchor (ex) date -> one event (the official amount wins
  even when the vendor amount differs; the disagreement is recorded elsewhere);
* every other kind is never collapsed.
Ties inside a tier: the earliest known (``available_at``) record wins.
"""

from __future__ import annotations

from collections.abc import Sequence

from pitquant.market.normalized import CorporateAction, CorporateActionKind, SourceTier

_RANK = {SourceTier.OFFICIAL: 2, SourceTier.VENDOR: 1, SourceTier.FIXTURE: 0}
_DIV = {CorporateActionKind.CASH_DIVIDEND, CorporateActionKind.SPECIAL_DIVIDEND}
_SPLIT = {CorporateActionKind.SPLIT, CorporateActionKind.REVERSE_SPLIT}


def _same_event(a: CorporateAction, b: CorporateAction) -> bool:
    da, db = a.anchor_date, b.anchor_date
    if da is None or db is None:
        return False
    if a.kind in _SPLIT and b.kind in _SPLIT:
        return (
            abs((da - db).days) <= 5
            and a.ratio is not None
            and b.ratio is not None
            and abs(a.ratio - b.ratio) < 1e-9
        )
    if a.kind in _DIV and b.kind in _DIV:
        return da == db
    return False


def collapse_equivalent(actions: Sequence[CorporateAction]) -> list[CorporateAction]:
    ordered = sorted(actions, key=lambda x: (-_RANK[x.provenance.tier], x.available_at))
    kept: list[CorporateAction] = []
    for a in ordered:
        if any(_same_event(a, k) for k in kept):
            continue
        kept.append(a)
    return sorted(kept, key=lambda x: (x.anchor_date or x.available_at.date(), x.kind.value))
