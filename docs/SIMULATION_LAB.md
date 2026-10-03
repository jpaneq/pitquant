# Simulation Lab — paper trading y validación hacia delante

> **PAPER TRADING — NO REAL MONEY.** Sin broker, sin órdenes, sin dinero real. Mientras el Prediction Engine siga `NOT_YET_VALIDATED` no se muestra
> ninguna probabilidad ni retorno esperado, y el Trade Plan sigue siendo `RULE_BASED · NOT YET BACKTEST VALIDATED`. ADR-0034 (V0) y ADR-0036 (event store).

## 1. Propósito y flujo
`ANALYZER → SIMULATION → FORWARD OUTCOME → POST-MORTEM → RESEARCH HYPOTHESIS → BACKTEST → WALK-FORWARD → CHALLENGER → CHAMPION`. El módulo genera
evidencia; **nunca** modifica el modelo de producción, los datasets, el Feature Engine ni el Champion (garantías en §14).

## 2. Arquitectura
```
create_simulation ──► simulations (T0 inmutable + snapshot_hash + source_provenance) ──► simulation_events #0 SIMULATION_CREATED
simulation-update ──► engine.evaluate (PURO) ──► eventos nuevos (append-only) ──► simulation_outcomes (estado materializado)
                                             └─► simulation_counterfactuals (sólo USER_MODIFIED)
simulation-replay ──► T0 + simulation_events ──► fold_events (independiente) ──► compara con el outcome persistido
```
Tablas append-only (guard ORM + triggers PostgreSQL): `simulations`, `simulation_events`, `simulation_observations`, `simulation_outcomes`,
`simulation_postmortems`, `simulation_counterfactuals`, `research_hypotheses`. **Diferencia event log vs. estado materializado:** el log es la fuente
de verdad; `simulation_outcomes` es una vista materializada que se AÑADE (no se edita) cuando hay eventos nuevos y que `replay` puede reconstruir.

## 3. Snapshot T0
`SimulationDecisionSnapshot` = la fila de `simulations`: precio, features/técnico, fundamental, valoración, S/R, Trade Plan, régimen, calidad de datos,
versiones (analyzer, features, reglas del Trade Plan, modelo = NULL), benchmark, `snapshot_hash` (SHA-256 del contenido canónico) y
`source_provenance`. `prediction_status = NOT_YET_VALIDATED`, `predicted_return = p_outperform = NULL`. Los campos BTC existen y son NULL.
Nunca se actualiza; cualquier edición cambia el hash y `update_simulation` se niega (`SNAPSHOT_TAMPERED`).

## 4. Máquina de estados
`CREATED → WAITING_ENTRY → ENTERED → (PARTIAL_TP) → TP1 | TP2 | TP3 | STOPPED | INVALIDATED | EXPIRED | CLOSED_MANUAL | AMBIGUOUS_INTRABAR`, y
`CANCELLED` (sólo antes de entrar). Cada transición queda en el log. Cierre manual: sólo con posición abierta. `AUTO_PAPER` existe como contrato y
está `DISABLED_NOT_VALIDATED`.

## 5. Event sourcing
Eventos (`sequence_number` único por simulación): `SIMULATION_CREATED`, `BAR_PROCESSED`, `ENTRY_TRIGGERED`, `ENTRY_FILLED`, `TP1/2/3_TOUCHED`,
`PARTIAL_EXIT`, `STOP_TRIGGERED`, `STOP_GAP`, `EXIT_FILLED`, `INVALIDATED`, `EXPIRED`, `MANUAL_CLOSE`, `CANCELLED`, `AMBIGUOUS_INTRABAR`,
`OBSERVATION_RECORDED` (T+1, T+5, T+20, T+60). El motor procesa barras cronológicamente y nunca mira una barra posterior a la actual.

## 6. Entradas (LONG)
| tipo | regla | `fill_method` |
|---|---|---|
| `MARKET_REFERENCE` | precio guardado al crear; entrada en T0 | `MARKET_REFERENCE` |
| `LIMIT` P | `open ≤ P` ⇒ open; si no y `low ≤ P ≤ high` ⇒ P; si no, sin fill | `FAVORABLE_GAP` (open<P) / `EXPLICIT_LIMIT` |
| `ENTRY_ZONE` [lo, hi] | open dentro ⇒ open; open bajo `lo` ⇒ open; entra desde arriba ⇒ `hi` | `OPEN_WITHIN_ZONE` / `FAVORABLE_GAP` / `FIRST_ZONE_TOUCH` |
| `STOP_BUY` / `MARKET` (V0) | ruptura / siguiente open | `STOP_BUY_LEVEL`, `STOP_BUY_GAP`, `MARKET_NEXT_OPEN` |
Nunca se usa el cierre. SHORT existe en el esquema pero la UI lo deshabilita (el Trade Plan no está validado para short).

## 7. Stops, objetivos y gaps
- **Stop gap:** `open ≤ stop` ⇒ fill al open (`STOP_GAP`), no al stop. Stop intrabarra ⇒ fill al stop (`STOP_LEVEL`).
- **Objetivos:** `open ≥ target` ⇒ fill al open (`TARGET_GAP`); si no, `high ≥ target` ⇒ fill al objetivo (`TARGET_LIMIT`).
- **Invalidación:** cierre bajo el nivel de invalidación del Trade Plan ⇒ `INVALIDATED` (distinto del stop), salida al cierre. No se inventan invalidadores.
- **Caducidad:** pasada la fecha, `EXPIRED` con la posición marcada al último cierre dentro del horizonte (`mark_to_market_return_at_expiration`).
- Costes V0: sólo los gaps reales; `commission/slippage/fees` explícitos a 0.

## 8. Parciales y `TRACK_TARGETS_ONLY`
`exit_policy`: `TRACK_TARGETS_ONLY` (defecto de las simulaciones nuevas: tocar TP1/TP2 es un evento, **la posición sigue completa**, no hay retorno realizado
por tocar un objetivo), `PARTIAL_FRACTIONS` (`tp{n}_exit_fraction` ∈ [0,1], suma ≤ 1; cada fill registra la posición restante) y `LEGACY_HALF_AT_TP1`
(sólo filas anteriores al ADR-0036). Se distingue `target_touched` de `target_exit_filled`.

## 9. Ambigüedad intradía
Con OHLC diario no se conoce el orden dentro de la barra. `AMBIGUOUS_INTRABAR` (estado final) cuando: entrada intrabarra + stop/objetivo en la misma barra;
stop + objetivo que cerraría posición; varios objetivos + stop. El payload guarda los escenarios (`STOP_FIRST`, `TARGET_FIRST`, `ENTRY_THEN_STOP`, …) con su R.
Nunca se elige el favorable ni el desfavorable. En `TRACK_TARGETS_ONLY` stop + toque en la misma barra es un stop con `touch_order_unknown`.

## 10. MAE, MFE, R, benchmark
Con `riesgo_inicial = entry − stop_inicial` (fijo):
`MFE_pct = max(high desde la entrada)/entry − 1`, `MAE_pct = min(low desde la entrada)/entry − 1` (**negativo**), `MFE_R = (max_high − entry)/riesgo`,
`MAE_R = (min_low − entry)/riesgo`. Una entrada intrabarra no cuenta la parte de la barra que pudo precederla. `realized_R = Σ fracción_i·(salida_i − entry)/riesgo`
(la parte abierta se marca al último cierre y se etiqueta `UNREALIZED`). Exceso = retorno de la simulación − retorno del benchmark en el mismo intervalo
(`SPY_TOTAL_RETURN_PROXY`; NULL si no hay benchmark, sin bloquear). Las claves V0 `mae`/`mfe` (positivas) se conservan.

## 11. Post-mortem
`GET /simulations/{id}/postmortem`: hechos objetivos (calidad de entrada/stop/objetivos, MAE/MFE/R, `stop_distance_atr`) y **flags deterministas con su definición**
(`STOP_HIT_BEFORE_LATER_TP`, `HIGH_MFE_LOW_REALIZED` = MFE ≥ 1R y R realizada ≤ 0, `TARGET_NEVER_APPROACHED`, `REGIME_CHANGED`, `TREND_REVERSED`,
`FUNDAMENTAL_STATUS_CHANGED`). No se infiere ninguna causa. La clasificación (causa primaria, secundarias, notas, quién y cuándo) es humana y explícita;
`prediction_outcome` es NULL mientras el modelo no esté validado y un stop es un hecho de **ejecución**.

## 12. Plan PITQuant vs plan del usuario y contrafactual
`USER_MODIFIED` conserva `original_pitquant_plan` y `final_simulated_plan`, ambos inmutables. La pestaña *Plan comparison* muestra entrada/stop/objetivos/R esperada
y marca lo que el usuario movió. Si hay barras, `simulation_counterfactuals` ejecuta el plan original sobre las MISMAS barras (`COUNTERFACTUAL — NOT THE REAL OUTCOME`):
disparo, estado final, toques, MAE, MFE y R. No es el resultado real, no entra en el replay y no se usa para entrenar.

## 13. Insights
`GET /simulations/insights?by=` segmenta por `setup_type`, `rules_version`, `origin`, `security`, `sector`, `trend_state`, `valuation_state`, `volatility_regime`
(terciles de la muestra, descriptivo), `market_regime`, `horizon`. Métricas: N, retorno/R/MAE/MFE (media y mediana), tasas de stop, de toque de objetivo, de caducidad y
ambiguas. Con menos de 10 entradas: `INSUFFICIENT_SAMPLE` y sin números. Sin recomendaciones.

## 14. Research Lab y no-leakage
- Research Lab sólo LEE `evidence_summary` / `SimulationEvidenceSummary`; las tablas de simulación no son features ni targets ni se importan desde el Dataset Builder (test).
- `ResearchHypothesis` nace `UNTESTED` (`TESTING`, `SUPPORTED`, `NOT_SUPPORTED` pertenecen al Research Lab); jamás toca `DatasetVersion`, `FeatureSetVersion`, `ModelVersion` ni Champion.
- T0 sólo contiene lo conocido en `decision_at`; sólo el update engine consume el futuro (barras con `available_at ≤ as_of`); el holdout 2022-10-01→2025-09-30 se rechaza.
- Sin auto-entrenamiento, sin auto-promoción, sin LLM que decida causas.

## 15. CLI, replay, idempotencia
```bash
pitquant simulation-update [--simulation-id ID] [--as-of ISO] [--json]   # "new_events = 0" en la segunda pasada
pitquant simulation-replay ID [--verify]                                 # MATCH o diferencias; --verify sale 1 si no coincide
```
`simulation-update` re-evalúa las barras posteriores a T0 (≤ 60 sesiones) y sólo añade los eventos nuevos; si el motor no reproduce un evento guardado falla con
`EVENT_LOG_DIVERGENCE`. Una evaluación a un instante anterior no añade nada ni materializa un estado más viejo.

## 16. API
`POST /simulations`, `GET /simulations`, `GET /simulations/{id}`, `POST …/update`, `POST …/evaluate` (compat.), `POST …/cancel`, `POST …/close`, `GET …/events`,
`GET …/observations`, `GET|POST …/postmortem`, `GET …/explain`, `GET …/compare`, `GET …/replay`, `POST …/hypothesis`, `GET /simulations/summary|insights|hypotheses`.
Holdout ⇒ 403, sin precios ⇒ 409 `PRICE_DATA_REQUIRED`, `AUTO_PAPER` ⇒ 409, plan inválido ⇒ 422.

## 17. Provenance
*Explain Simulation* (`GET …/explain`, pestaña *Provenance*): fuente y marca del precio, filing/versión fundamental, versiones de analyzer/features/reglas del Trade Plan/modelo,
benchmark, versión del motor de eventos, hash del snapshot y si verifica.

## 18. Auditoría de V0 (matriz inicial → estado)
| requisito | V0 | ahora |
|---|---|---|
| creación, T0 inmutable, origen y planes original/final | IMPLEMENTED | + `snapshot_hash`, provenance |
| MARKET_REFERENCE / ENTRY_ZONE / LIMIT con `fill_method` | PARTIAL (LIMIT/STOP_BUY/MARKET sin método) | IMPLEMENTED |
| stop/target gap | PARTIAL (precio ok, sin método) | IMPLEMENTED |
| ambigüedad | PARTIAL (sin escenarios; ignoraba stop tras gap de apertura) | IMPLEMENTED |
| parciales / `TRACK_TARGETS_ONLY` | PARTIAL (50 % inventado) | IMPLEMENTED |
| MAE / MFE / R | PARTIAL (MAE positivo, sin R) | IMPLEMENTED |
| event store, `simulation-update`, `simulation-replay` | MISSING | IMPLEMENTED |
| contrafactual y comparación de planes | MISSING | IMPLEMENTED |
| Insights, post-mortem con hechos, hipótesis `UNTESTED`, cancelar | MISSING / PARTIAL | IMPLEMENTED |
| UI: timeline por eventos, pestañas, wizard, dashboard con filtros | PARTIAL | IMPLEMENTED |
| SIZING `FIXED_NOTIONAL`, `target_3` | MISSING | IMPLEMENTED |
| rutas SPA `/simulations*` al recargar | BUG (devolvía JSON) | corregido |

## 19. Limitaciones conocidas
Sólo LONG y EQUITY (BTC: columnas NULL, sin conectores); sólo barras diarias (la ambigüedad intradía es real, no se resuelve); sin dividendos, comisiones ni
slippage más allá de los gaps; benchmark = proxy sin total return real; `volatility_regime` de Insights = terciles de la muestra (descriptivo); la UI muestra T0 y niveles
actuales sólo como tabla de cambios, no como segunda capa del gráfico.
