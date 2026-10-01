"""Half-open interval helpers ``[start, end)`` with ``None`` meaning open-ended."""

from __future__ import annotations

from datetime import date


def overlaps(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    a_end = a_to or date.max
    b_end = b_to or date.max
    return a_from < b_end and b_from < a_end


def contains(start: date, end: date | None, d: date) -> bool:
    return start <= d and (end is None or d < end)
