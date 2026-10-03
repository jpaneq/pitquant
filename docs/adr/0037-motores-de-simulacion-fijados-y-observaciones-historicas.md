# ADR-0037 — Version-pinned Simulation Engines and Historical Observation Snapshots

Estado: aceptada (2026-10-03). Complementa ADR-0034 y ADR-0036 (no los sustituye). Migración `0019`.

## Contexto
`simulation-update` evaluaba con el motor vigente: tras un cambio de reglas, toda simulación abierta divergía (`EVENT_LOG_DIVERGENCE`). Además las
observaciones T+n sólo guardaban precio, retorno y benchmark, y `bars_to_entry` era siempre NULL.

## Decisiones
1. **Pin inmutable.** `simulations.simulation_engine_version` (fila append-only). Las simulaciones previas reciben `v1` por backfill determinista de la migración
   (`server_default`, sin UPDATE: compatible con los triggers de PostgreSQL). Las nuevas usan `CURRENT_SIMULATION_ENGINE_VERSION` al crearse y no cambian jamás.
2. **Registry explícito** (`simulation/registry.py`): `SIMULATION_ENGINES = {"v1": SimulationEngineV1}`. Update, replay y contrafactual resuelven el motor por el pin;
   nunca por «el último». Una versión no registrada ⇒ `ENGINE_VERSION_UNAVAILABLE` (fail closed): no es `DIVERGED` y no la ejecuta otro motor.
3. **V1 congelado.** `SimulationEngineV1` envuelve `simulation/engine.py` sin cambiar reglas. `test_simulation_engine_v1_frozen.py` fija un digest del output (eventos, métricas,
   salidas y fold) sobre una batería de escenarios: cambiarlo = cambiar las reglas de todas las simulaciones v1, prohibido. Un cambio de comportamiento ⇒ `SimulationEngineV2`.
4. **Ciclo de vida.** simulación existente ⇒ su motor original para siempre; simulación nueva ⇒ motor actual; sin migración silenciosa ni recálculo del historial v1 con v2.
   Para ver una simulación con reglas nuevas: COUNTERFACTUAL o FORK. Contrato conceptual (`EngineMigrationContract`: `source_simulation_id`, `source_engine_version`,
   `target_engine_version`, `migration_type ∈ {COUNTERFACTUAL, FORK}`); no hay función de migración in situ.
5. **Eventos.** `event_schema_version` (columna nueva, separada de `engine_version`). Las filas previas llevan la etiqueta de la era V1 (`sim-engine-2`): `v1` la acepta como etiqueta
   propia (las filas son append-only y no se reescriben). `simulation-replay --verify` falla si algún evento fue escrito por otro motor.
6. **Contrafactual** con el MISMO motor pinneado y con `simulation_engine_version` guardado.
7. **Observaciones históricas** (`kind = PERIODIC` en `simulation_observations`, columnas `horizon_label`, `source_bar_date`, `observation_schema_version`, `analyzer_version`,
   `feature_version`; única por simulación y etiqueta). Cadencia: T+1, T+5, T+20, cada 20 BARS, eventos clave (entrada, stop, toques, invalidación, caducidad, cierre manual,
   ambigüedad, cancelación) y estado final; varios hitos del mismo día comparten una observación; nada en o antes de la fecha de decisión. Contenido: precio, retorno, benchmark,
   técnico, fundamental, valoración, S/R, régimen y calidad de datos. **Point in time:** se calcula al CIERRE de la sesión de la fecha (barras, filings por `available_at`, S/R y
   régimen sólo con la historia de entonces). **Inmutables:** una observación existente no se recalcula aunque cambie el Analyzer; una versión nueva sólo produce observaciones nuevas.
   Un fallo del Analyzer se informa (`observation_errors`) y se reintenta; nunca bloquea el event log.
8. **Hechos de tesis** (`thesis_facts`): `trend_changed`, `support_broken`, `resistance_broken`, `volatility_expanded`, `valuation_expanded/compressed`,
   `fundamental_snapshot_changed`, `regime_changed`, cada uno con definición, valores y observación de origen; ninguno es una causa. El post-mortem los usa
   (`TREND_REVERSED` sólo si hay vuelco arriba↔abajo) con `source_observation_ids`.
9. **`bars_to_entry`** = barras de mercado procesadas desde `decision_at` hasta la barra de entrada (MARKET_REFERENCE ⇒ 0; primera barra ⇒ 1); se deduce también de los eventos
   (replay) y no cambia ningún payload de evento v1. `days_waiting_entry` no cambia.
10. **UI:** *Current analysis* (calculado ahora, «NOT known on any earlier date») separado de *Recorded observations* (históricas); *Changes* compara T0, cualquier observación o
    el análisis actual (etiquetado) y omite métricas inexistentes; *Provenance* muestra Simulation Engine y Event Schema; Insights segmenta por `simulation_engine_version` y avisa
    cuando los segmentos mezclan motores.
11. **Rendimiento.** Se mantiene la relectura de barras desde T0 (corrección > rendimiento: reanudar desde un checkpoint pondría en riesgo MAE/MFE, ambigüedad y replay). Se mide
    (`bars_loaded`, `bars_new`, `events_new`, `observations_new` en CLI y API).

## Consecuencias
Un cambio futuro de reglas no rompe ninguna simulación abierta. Una simulación v1 y una v2 se procesan en la misma ejecución, cada una con su motor y su savepoint.
Límite: una corrección de barras históricas sigue siendo `EVENT_LOG_DIVERGENCE` (dato, no reglas).
