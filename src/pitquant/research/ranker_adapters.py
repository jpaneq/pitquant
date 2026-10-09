"""Narrow research estimators; PITQuant owns data, cohorts, folds and evaluation."""

from __future__ import annotations

import importlib.metadata
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pitquant.research.ranking_preregistration import encoded, file_digest, write_once

Matrix = NDArray[np.float64]
Groups = NDArray[np.int64]


def validate_inputs(x: Matrix, groups: Groups, y: Matrix | None = None) -> None:
    if x.ndim != 2 or groups.ndim != 1 or len(x) != len(groups) or len(x) == 0:
        raise ValueError("invalid grouped input shape")
    if np.isinf(x).any() or not np.isfinite(groups).all():
        raise ValueError("invalid values")
    if (np.diff(groups) < 0).any():
        raise ValueError("qid must be sorted")
    if y is not None and (
        y.shape != groups.shape
        or not np.isfinite(y).all()
        or (y < 0).any()
        or (y > 9).any()
        or (y != np.floor(y)).any()
    ):
        raise ValueError("integer relevance 0..9 required")


class CrossSectionalRankerAdapter(ABC):
    @abstractmethod
    def fit(self, x: Matrix, y: Matrix, group: Groups) -> None: ...

    @abstractmethod
    def predict(self, x: Matrix, group: Groups) -> Matrix: ...

    @abstractmethod
    def serialize(self, directory: Path) -> dict[str, Any]: ...

    @classmethod
    @abstractmethod
    def load(cls, directory: Path) -> CrossSectionalRankerAdapter: ...

    @abstractmethod
    def metadata(self) -> dict[str, Any]: ...

    @abstractmethod
    def capabilities(self) -> dict[str, Any]: ...


class XGBRankerAdapter(CrossSectionalRankerAdapter):
    """Only executable challenger. Optional import does not make XGBoost core."""

    def __init__(self, params: dict[str, Any]) -> None:
        from xgboost import XGBRanker

        if importlib.metadata.version("xgboost") != "3.1.3":
            raise ValueError("exact XGBoost 3.1.3 required")
        self.params = dict(params)
        if params.get("objective") != "rank:ndcg" or params.get("ndcg_exp_gain") is not False:
            raise ValueError("frozen rank objective required")
        if params.get("lambdarank_unbiased") is not False:
            raise ValueError("click-bias correction forbidden")
        self.model = XGBRanker(**params, missing=np.nan)
        self.fitted = False

    def fit(self, x: Matrix, y: Matrix, group: Groups) -> None:
        validate_inputs(x, group, y)
        if np.isnan(x).all(axis=0).any():
            raise ValueError("all-missing TRAIN feature")
        self.model.fit(x, y, qid=group)
        self.fitted = True

    def predict(self, x: Matrix, group: Groups) -> Matrix:
        validate_inputs(x, group)
        if not self.fitted:
            raise ValueError("not fitted")
        values: Matrix = np.asarray(self.model.predict(x), dtype=np.float64)
        if not np.isfinite(values).all() or values.shape != group.shape:
            raise ValueError("invalid model scores")
        return values

    def serialize(self, directory: Path) -> dict[str, Any]:
        if not self.fitted:
            raise ValueError("not fitted")
        write_once(
            directory / "model.ubj", bytes(self.model.get_booster().save_raw(raw_format="ubj"))
        )
        meta = {**self.metadata(), "model_sha256": file_digest(directory / "model.ubj")}
        write_once(directory / "metadata.json", encoded(meta))
        return meta

    @classmethod
    def load(cls, directory: Path) -> XGBRankerAdapter:
        meta = json.loads((directory / "metadata.json").read_bytes())
        if file_digest(directory / "model.ubj") != meta["model_sha256"]:
            raise ValueError("model integrity failure")
        adapter = cls(meta["parameters"])
        adapter.model.load_model(directory / "model.ubj")
        adapter.fitted = True
        return adapter

    def metadata(self) -> dict[str, Any]:
        return {
            "adapter": "XGBRankerAdapter",
            "library": "xgboost",
            "version": "3.1.3",
            "parameters": self.params,
            "missing": "native NaN",
            "license": "Apache-2.0",
            "upstream": "https://github.com/dmlc/xgboost",
            "booster_config": json.loads(self.model.get_booster().save_config())
            if self.fitted
            else None,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_group_ranking": True,
            "requires_sequence": False,
            "requires_relation_graph": False,
            "supports_missing_native": True,
            "supports_categorical": False,
            "requires_gpu": False,
            "requires_market_context": False,
            "requires_online_updates": False,
            "integration_status": "IMPLEMENTED_RESEARCH_ONLY",
        }


class FutureRankerSpecification:
    """Dependency-free contract only. Cannot consume research data or fit any model."""

    def __init__(self, name: str, capabilities: dict[str, Any]) -> None:
        self.name, self._capabilities = name, dict(capabilities)

    def capabilities(self) -> dict[str, Any]:
        return dict(self._capabilities)

    def fit(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError(
            f"{self.name} is specification-only; separate human review required"
        )
