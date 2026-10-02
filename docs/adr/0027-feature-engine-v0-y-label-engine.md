# ADR-0027 — Feature Engine V0 y Label Engine V0

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Amplía:** ADR-0023 · **Migraciones:** ninguna

## Decisión
1. **Decisión mensual US:** `decision_at` = apertura NYSE de la sesión elegida. Precio: sólo sesiones
   anteriores (último cierre previo); fundamentales: sólo hechos con `available_at < decision_at` y la
   última revisión CONOCIDA de cada periodo (restatements sólo tras su presentación). Las fechas del holdout
   (2022-10-01 → 2025-09-30) se rechazan.
2. **Dos series internas separadas, ambas desde precio RAW:** split-adjusted (sólo splits; SMA/EMA/RSI/ATR/
   volumen) y Total Return Index (splits + dividendos en efectivo; momentum, volatilidad, drawdown, beta,
   fuerza relativa, labels). Nunca el adjusted close del proveedor.
3. **51 features RAW** (`FEATURE_NAMES`): 24 técnicas, 22 fundamentales y 5 de valoración. Convenciones
   fijas y versionadas (`FEATURE_VERSION = v0.1`, `TAG_MAP_VERSION = sec-tags-1`): EMA con `adjust=False`,
   RSI/ATR de Wilder, volatilidad anualizada de log-retornos (ddof 1, √252), `mom_12_1` = TR[t-21]/TR[t-252].
4. **Fundamentales SEC** con periodización explícita: TTM = FY(anterior) + YTD(actual) − YTD(mismo periodo del
   año previo), o el FY en cierre de ejercicio; nunca YTD sumados como trimestres. Resolución de tags
   versionada (el candidato con el periodo más reciente gana; dos tags con valores distintos para el mismo
   periodo → `unresolved_tag`, fail closed). Capex = pagos por PP&E; FCF = CFO − capex. Acciones = portada
   dei (nunca promedio ponderado); capitalización = último cierre RAW × acciones alineadas a splits
   posteriores a la portada; `stale_data` si la portada tiene > 400 días.
5. **Sin imputación, winsorización ni estandarización en el motor.** Un valor ausente es NULL con razón
   (`insufficient_history`, `missing_fundamental`, `denominator_invalid`, `unresolved_tag`, `stale_data`,
   `coverage_gap`, `security_not_applicable`). El rango cross-sectional se guarda aparte
   (`cross_sectional_rank`, sólo dentro de una cohorte y fecha).
6. **Snapshots** (`feature_snapshots`, inmutable): se reutiliza `SnapshotBuilder`; cada feature lleva
   `available_at`, `source_ref`, `reason`, `formula` y `provenance`. Cambiar fórmula, tag map, periodización,
   ajuste de acciones, calendario o benchmark exige nueva `feature_version`.
7. **`pitquant explain-feature <security> <fecha> <feature>`** muestra hechos usados, filas de precio,
   corporate actions, fórmula, intermedios, `available_at` y procedencia.
8. **Labels 6M/12M** (`backtest/targets.py`): entrada = apertura de T; salida = cierre de la primera sesión
   NYSE en o tras T + 6/12 meses naturales; retorno total con splits/dividendos/acciones soportadas; la
   acción del día de entrada no se cobra; benchmark SPY con las mismas sesiones; se guardan
   `security_total_return`, `benchmark_total_return`, `excess_total_return`, `outperform`
   (`excess > 0`), `benchmark_type = ETF_PROXY`. Un label sólo es utilizable cuando su resultado ya es
   conocible (`assert_label_usable`). Sin BUY/HOLD/SELL. Un valor deslistado sin evento terminal es
   `UNAVAILABLE`, no cero.
9. **Baseline (Elastic Net / regresión logística) no construido**: no hay muestra (cohortes completas
   pre-holdout) ni scikit-learn instalado; los hiperparámetros predefinidos quedan para entonces. No se
   evalúa el holdout.

## Límites
- Con los datos reales actuales sólo AAPL/MSFT tienen fundamentales; sus precios son ventanas cortas (QA),
  así que los snapshots reales son de investigación NO elegibles (`data_version` lo indica).
- `beta`/`relative_*` requieren SPY ingerido (Tiingo, D-05).
