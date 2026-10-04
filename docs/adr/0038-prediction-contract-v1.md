# ADR-0038 — Prediction contract V1 (`prediction_snapshots`)

Estado: aceptada (2026-10-04). Migración `0020`.

## Decisión
`PredictionSnapshot` es el dato de una SALIDA DE MODELO por (security, `decision_at`, horizonte 6M/12M): `expected_excess_return`, `p_outperform`, cuantiles 10/25/50/75/90, incertidumbre, benchmark `SPY_TOTAL_RETURN_PROXY`, calidad de datos, contribuciones, avisos y procedencia (`model_id/version`, `feature_set_version`, `dataset_version`, `commit_sha`). No es BUY/HOLD/SELL.
1. Mientras el estado es `NOT_YET_VALIDATED`, todos los campos predictivos son NULL (CHECK `no_invented_predictions`). Ningún código del producto escribe `VALIDATED`: sólo existen `NOT_YET_VALIDATED` y `SYNTHETIC_FIXTURE`.
2. `SYNTHETIC_FIXTURE` (siempre `is_synthetic`, aviso «SYNTHETIC TEST DATA») sólo lo escribe `tests/support/synthetic_predictions.py`; ni API ni CLI pueden crearlo.
3. PIT: `decision_at <= generated_at`; las entradas disponibles ≤ `decision_at`. Tabla append-only (guard ORM + trigger PostgreSQL); un modelo nuevo es una fila nueva.
4. Resultados (`prediction_outcomes`) aparte: PENDING/RESOLVED/UNAVAILABLE/HOLDOUT_SEALED; nunca resuelve una ventana de etiqueta que toque el holdout.
5. Relación con `predictions`/`research_predictions` (legado): independientes; el contrato nuevo no las lee ni las reescribe.
6. Modelos base por horizonte (`EQUITY_6M_BASELINE`, `EQUITY_12M_BASELINE`: Elastic Net + Logistic, mismas 51 features, walk-forward con purga/embargo, `train_min=60`) quedan DEFINIDOS; `attempt_training` registra un experimento BLOCKED mientras no estén abiertos `D02_MONTHLY_RESEARCH_READY`, `US_D05_RESEARCH_READY`, `US_SECURITY_IDENTITY_READY` y `US_FUNDAMENTALS_READY`. scikit-learn no es dependencia de esta build.
