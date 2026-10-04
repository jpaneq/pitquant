# ruff: noqa: E501
"""Bridge between a RESEARCH security (SEC issuer, Yahoo prices) and the S&P 500 anchor members (CUSIP-based securities), for the first-ML eligibility only (ADR-0049).

The anchor graph knows members by anchor security_id; research securities hang from the SEC issuer, and no official identifier links the two yet. The only rule used is the one the project already sanctions for anchors
(``identity_bridge.bridge_name_only``): the EXACT normalised legal name (SEC submissions display name vs the name filed in the anchor) with EXACTLY ONE candidate security. Several candidates or none => UNRESOLVED (the security is
not eligible: ``SECURITY_IDENTITY_NOT_READY``); similarity is never enough. The evidence class is DERIVED (never OFFICIAL), so it cannot close ``US_SECURITY_IDENTITY_READY`` by itself. Nothing is written to the identity tables.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.db.models import Security, SecurityProfile, SP500AnchorMember
from pitquant.universe.sources.spy_sec_anchors import norm_name

EVIDENCE_CLASS = "DERIVED_EXACT_NAME_UNIQUE"


def build_bridge(session: Session) -> tuple[dict[str, frozenset[str]], dict[str, str]]:
    """(bridge: research security_id -> anchor security_ids, unresolved: research security_id -> reason)."""
    by_name: dict[str, set[str]] = {}
    for m in session.scalars(select(SP500AnchorMember)):
        if m.security_id:
            by_name.setdefault(norm_name(m.issuer_name), set()).add(m.security_id)
    bridge: dict[str, frozenset[str]] = {}
    unresolved: dict[str, str] = {}
    for s in session.scalars(
        select(Security).where(
            Security.exchange == "XNYS",
            Security.issuer_id.is_not(None),
            Security.is_synthetic.is_(False),
        )
    ):
        sibs = [
            x.security_id
            for x in session.scalars(select(Security).where(Security.issuer_id == s.issuer_id))
        ]
        p = session.scalars(
            select(SecurityProfile)
            .where(SecurityProfile.security_id.in_(sibs))
            .order_by(SecurityProfile.ingested_at.desc())
        ).first()
        if p is None:
            unresolved[s.security_id] = "NO_SEC_PROFILE_NAME"
            continue
        cands = by_name.get(norm_name(p.display_name), set())
        if len(cands) == 1:
            bridge[s.security_id] = frozenset(cands)
        else:
            unresolved[s.security_id] = (
                f"{'AMBIGUOUS_NAME_MATCH' if cands else 'NO_EXACT_NAME_MATCH'}: {p.display_name}"
            )
    return bridge, unresolved
