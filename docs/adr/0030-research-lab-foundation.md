# ADR-0030 — Fundación del Research Lab y consolidación del Analyzer V0

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Migración:** `0012`

## Contexto
El Analyzer V0 funciona con datos reales parciales. D-02 (universo S&P 500) y D-05 (precios
canónicos) siguen abiertos. Objetivo: que el primer experimento predictivo pueda ejecutarse sin
rehacer arquitectura en cuanto existan, sin entrenar nada ni mostrar resultados inventados.

## Decisión
1. **Tres niveles separados:** `raw_features` (Feature Engine, PIT) → `human_analysis` (etiquetas
   reglas del Analyzer) → `prediction` (siempre `NOT_YET_VALIDATED`). Las etiquetas humanas **nunca**
   son feature ni target (`DatasetSpec` rechaza cualquier nombre fuera de `FEATURE_NAMES`;
   `FORBIDDEN_TARGETS` en baselines).
2. **Modelo de datos** (migración 0012, todo append-only con trigger PG): `feature_set_versions`,
   `label_definitions`, `model_configs`, `dataset_versions`, `research_experiments`, `research_folds`,
   `research_predictions` (CHECK `decision_at <= generated_at`, sin campo de señal),
   `realized_outcomes`, `metric_sets`, `champion_challenger_comparisons`.
3. **Walk-forward** (`research/walkforward.py`): expanding/rolling, purge y embargo en meses, y
   **la ventana de la etiqueta también debe acabar antes del holdout**. `assert_fold_clear_of_holdout`
   lanza `HoldoutAccessError`. `pitquant research-dry-run` planifica folds solo con el calendario.
4. **Dataset Builder** (`research/dataset_builder.py`): una fila por (security, fecha de decisión);
   las no elegibles se **conservan** con `blocking_reason` (`NO_PRICE_HISTORY`, `FEATURES_TOO_SPARSE`,
   `LABEL_WINDOW_TOUCHES_HOLDOUT`, `BENCHMARK_UNAVAILABLE`, `LABEL_UNAVAILABLE:*`). Nunca se calcula una
   etiqueta cuya ventana toca el holdout. Hash de contenido + JSONL.
5. **Missingness** por feature, año, security y sector; **baselines** predefinidos (ElasticNet,
   regresión logística; sin XGBoost) con transformadores ajustados sólo en train; **métricas** con
   esquema fijo; **contrato de predicción** (`PredictionRecord`: snapshot exacto, `decision_at`,
   calibración obligatoria si hay probabilidad).
6. **Registro de experimentos** (`research/registry.py`): commit, hash de dataset, versiones de
   feature/label/modelo/universo/benchmark, fechas, purge/embargo, semilla, librerías. Con puertas de
   datos cerradas el experimento se guarda `BLOCKED` con motivos; no se entrena.
7. **Backtest de Trade Plan** (`research/trade_plan_backtest.py`): máquina de estados con velas diarias;
   si entrada+stop/objetivo o stop+objetivo caben en la misma vela → `AMBIGUOUS_INTRABAR` (nunca el caso
   favorable); los gaps se resuelven en la apertura.
8. **Flags separados:** `RESEARCH_LAB_IMPLEMENTED=true` (software) ≠ `RESEARCH_DATA_READY=false`
   (derivado de `FEATURE_RESEARCH_READY_US`).
9. **Analyzer:** provenance bajo demanda (`/analyzer/{sec}/explain`, `explain-analysis`,
   `explain-trade-plan`), metadatos por indicador técnico, S/R con `zone_low/zone_high/method/recency/
   strength_raw/calculation_at`, valoración en tres lecturas (absoluta, propia historia, pares =
   `NOT_AVAILABLE`), Trade Plan con `setup_type/target_1/2/risk_reward_1/2/inputs/rules_version/explanation`.
10. **E2E de navegador** (Playwright) sobre una BD sintética (`tests/e2e/serve.py`, tickers `SYN*`,
    banner DEMO DATA), sin APIs externas.

## Consecuencias
- Nada de esto produce resultados: sin D-02/D-05 el laboratorio muestra estados vacíos.
- Los campos nuevos del Analyzer son aditivos (no rompen DTOs anteriores).
- El E2E usa tickers `SYN*` en lugar de AAPL/KO: un fixture con tickers reales sería indistinguible
  de un dato histórico.
