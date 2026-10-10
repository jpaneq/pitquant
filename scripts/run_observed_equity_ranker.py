"""V0R2 draft entry point: real execution remains disabled before reading research inputs."""

from __future__ import annotations

from typing import NoReturn

from pitquant.research.ranking_observability import PendingHumanApproval


def run() -> NoReturn:
    raise PendingHumanApproval(
        "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R2 is PROPOSED_NOT_APPROVED. "
        "Freeze an explicitly approved new manifest/execution identity before any real fit. "
        "Use ranking_observability.fit_synthetic_inner for synthetic lifecycle verification only."
    )


if __name__ == "__main__":
    run()
