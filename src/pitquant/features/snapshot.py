"""Feature snapshots: the exact, immutable input of every prediction (§25, §60, §94)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import require_aware, to_iso_utc
from pitquant.data.point_in_time.engine import PITGuard
from pitquant.db.models import FeatureSnapshotRow


@dataclass(frozen=True)
class FeatureValue:
    name: str
    value: float | None
    available_at: datetime | None  # None only when the value is missing
    source_ref: str | None = None  # lineage pointer: raw_record_id / fact_id / computation id
    imputed: bool = False
    # Feature Engine V0 audit fields (optional; absent keys keep old snapshot hashes unchanged)
    reason: str | None = None
    formula: str | None = None
    provenance: list[dict[str, Any]] | None = None

    @property
    def is_missing(self) -> bool:
        return self.value is None or (isinstance(self.value, float) and math.isnan(self.value))


@dataclass(frozen=True)
class FrozenSnapshot:
    security_id: str
    as_of: datetime
    feature_version: str
    data_version: str
    code_version: str
    features: dict[str, float | None]
    availability: dict[str, dict[str, Any]]
    missing_mask: dict[str, bool]
    imputed_mask: dict[str, bool]
    dq_warnings: list[dict[str, Any]]
    max_available_at: datetime | None
    is_synthetic: bool
    content_hash: str

    def payload(self) -> dict[str, Any]:
        return _payload(
            self.security_id,
            self.as_of,
            self.feature_version,
            self.data_version,
            self.features,
            self.availability,
            self.missing_mask,
            self.imputed_mask,
            self.dq_warnings,
            self.is_synthetic,
        )


def _payload(
    security_id: str,
    as_of: datetime,
    feature_version: str,
    data_version: str,
    features: dict[str, float | None],
    availability: dict[str, dict[str, Any]],
    missing: dict[str, bool],
    imputed: dict[str, bool],
    warnings: list[dict[str, Any]],
    is_synthetic: bool,
) -> dict[str, Any]:
    # code_version is deliberately NOT hashed: identical inputs must hash identically even
    # after an unrelated refactor; code_version is stored alongside for traceability.
    return {
        "security_id": security_id,
        "as_of": as_of,
        "feature_version": feature_version,
        "data_version": data_version,
        "features": features,
        "availability": availability,
        "missing_mask": missing,
        "imputed_mask": imputed,
        "dq_warnings": warnings,
        "is_synthetic": is_synthetic,
    }


@dataclass
class SnapshotBuilder:
    security_id: str
    as_of: datetime
    feature_version: str
    data_version: str
    code_version: str
    is_synthetic: bool = False
    _values: dict[str, FeatureValue] = field(default_factory=dict, init=False)
    _warnings: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.as_of = require_aware(self.as_of, "as_of")

    def add(self, fv: FeatureValue) -> None:
        if fv.name in self._values:
            raise DataQualityError(f"duplicate feature {fv.name}")
        if not fv.is_missing and fv.available_at is None:
            raise DataQualityError(f"feature {fv.name} has a value but no available_at")
        self._values[fv.name] = fv

    def warn(self, check: str, severity: str, detail: str) -> None:
        self._warnings.append({"check": check, "severity": severity, "detail": detail})

    def freeze(self) -> FrozenSnapshot:
        guard = PITGuard(self.as_of, context=f"snapshot:{self.security_id}")
        guard.check_all(
            (v.name, v.available_at) for v in self._values.values() if v.available_at is not None
        )
        names = sorted(self._values)
        features = {
            n: (None if self._values[n].is_missing else self._values[n].value) for n in names
        }
        availability = {
            n: {
                "available_at": to_iso_utc(av) if (av := self._values[n].available_at) else None,
                "source_ref": self._values[n].source_ref,
                **{
                    k: v
                    for k, v in (
                        ("reason", self._values[n].reason),
                        ("formula", self._values[n].formula),
                        ("provenance", self._values[n].provenance),
                    )
                    if v is not None
                },
            }
            for n in names
        }
        missing = {n: self._values[n].is_missing for n in names}
        imputed = {n: self._values[n].imputed for n in names}
        ts = [v.available_at for v in self._values.values() if v.available_at is not None]
        max_av = max(ts) if ts else None
        warnings = sorted(self._warnings, key=lambda w: (w["check"], w["detail"]))
        h = content_hash(
            _payload(
                self.security_id,
                self.as_of,
                self.feature_version,
                self.data_version,
                features,
                availability,
                missing,
                imputed,
                warnings,
                self.is_synthetic,
            )
        )
        return FrozenSnapshot(
            security_id=self.security_id,
            as_of=self.as_of,
            feature_version=self.feature_version,
            data_version=self.data_version,
            code_version=self.code_version,
            features=features,
            availability=availability,
            missing_mask=missing,
            imputed_mask=imputed,
            dq_warnings=warnings,
            max_available_at=max_av,
            is_synthetic=self.is_synthetic,
            content_hash=h,
        )


def persist_snapshot(session: Session, snap: FrozenSnapshot) -> FeatureSnapshotRow:
    row = FeatureSnapshotRow(
        security_id=snap.security_id,
        as_of=snap.as_of,
        feature_version=snap.feature_version,
        data_version=snap.data_version,
        code_version=snap.code_version,
        features=snap.features,
        availability=snap.availability,
        missing_mask=snap.missing_mask,
        imputed_mask=snap.imputed_mask,
        dq_warnings=snap.dq_warnings,
        max_available_at=snap.max_available_at,
        content_hash=snap.content_hash,
        is_synthetic=snap.is_synthetic,
    )
    session.add(row)
    session.flush()
    return row
