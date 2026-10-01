"""Time utilities. All instants inside the platform are timezone-aware and normalised to UTC."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from pitquant.core.errors import NaiveDatetimeError


def require_aware(ts: datetime, name: str = "timestamp") -> datetime:
    """Return ``ts`` converted to UTC, refusing naive datetimes.

    A naive datetime is ambiguous by construction (which market's 16:00?) and therefore a
    latent look-ahead risk; we never guess.
    """
    if not isinstance(ts, datetime):
        raise TypeError(f"{name} must be a datetime, got {type(ts).__name__}")
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise NaiveDatetimeError(f"{name}={ts!r} is timezone-naive; supply an aware datetime")
    return ts.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


def at_local(d: date, t: time, tz: str) -> datetime:
    """Build an aware instant from a local date/time in an IANA zone, returned in UTC."""
    return datetime.combine(d, t, tzinfo=ZoneInfo(tz)).astimezone(UTC)


def to_iso_utc(ts: datetime) -> str:
    return require_aware(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def as_utc_from_db(ts: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; values written by this codebase are always UTC."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)
