# ADR-0039 — Strategy Engine, runs y comparación

Estado: aceptada (2026-10-04). Migración `0020`. Separado del Prediction Engine.

## Decisión
1. `StrategyDefinition` versionada e inmutable (`strategy_id` + `strategy_version`); editar = versión nueva. Familias: `TRADE_PLAN_ONLY` (operativa), `BUY_AND_HOLD` (línea base, siempre incluida), `PREDICTION_ONLY` e `HYBRID` (`DISABLED_NOT_VALIDATED`: una corrida forward se rechaza). Umbrales etiquetados `UNVALIDATED_STRATEGY_PARAMETER`.
2. `evaluate_strategy` es una función pura (reglas ENTRY/EXIT/GATE) y cada paso persiste un `StrategyDecision` inmutable (ENTER/HOLD/EXIT/NO_ACTION, `rule_inputs`, reglas evaluadas/superadas/falladas, `exit_reason`). Una decisión por (run, security, periodo).
3. Runs: `SYNTHETIC` (sólo con `PITQUANT_E2E_FIXTURE=1`, excluidos de evidencia), `HISTORICAL` (puerta de datos evaluada una vez; BLOCKED si está cerrada, no ejecuta nada) y `FORWARD_PAPER` (estrategia congelada, activada por el reloj del servidor, rechaza instantes anteriores a la activación).
4. AUTO_PAPER sólo por autoridad (`AutoPaperAuthority`): crea simulaciones del Simulation Lab con el motor fijado; no hay broker ni dinero real.
5. Comparación sobre las MISMAS entradas (`input_series_hash` independiente de lo que decida la estrategia): `NOT_COMPARABLE_INPUTS` si difieren; cartera de tramos iguales (1/`max_positions`), RF=0, costes en bps (`COSTS_NOT_MODELED` si son 0), `INSUFFICIENT_SAMPLE` (<10 operaciones), `UNDERPERFORMS_BUY_AND_HOLD`.
