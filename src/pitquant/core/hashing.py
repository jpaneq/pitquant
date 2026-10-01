"""Canonical serialisation and hashing, so that a snapshot regenerated years later
produces byte-identical content and therefore the same hash."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pitquant.core.timeutils import to_iso_utc


def _canon(obj: Any) -> Any:
    if obj is None or isinstance(obj, bool | str | int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return {"__float__": "nan"}
        if math.isinf(obj):
            return {"__float__": "inf" if obj > 0 else "-inf"}
        return {"__float__": repr(obj)}  # repr is the shortest round-trippable form
    if isinstance(obj, Decimal):
        return {"__decimal__": str(obj)}
    if isinstance(obj, datetime):
        return {"__ts__": to_iso_utc(obj)}
    if isinstance(obj, date):
        return {"__date__": obj.isoformat()}
    if isinstance(obj, Enum):
        return _canon(obj.value)
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, list | tuple):
        return [_canon(v) for v in obj]
    raise TypeError(f"Cannot canonicalise {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    return json.dumps(_canon(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
