# ADR-0036 — Simulation Lab: event store, replay, política de salidas y contrafactual

Estado: aceptada (2026-10-03). Complementa (no sustituye) ADR-0034. Motor `sim-engine-2`, migración `0018`.

## Contexto
La auditoría de V0 contra la especificación encontró: estado materializado como única fuente de verdad (no reconstruible), sin `fill_method`,
un esquema de parciales inventado (50 % en el objetivo 1), sin `TRACK_TARGETS_ONLY`, sin zona/limit/`MARKET_REFERENCE` explícitos, MAE positivo,
sin `simulation-update`/`simulation-replay`, sin comparación PITQuant vs usuario, sin Insights y rutas SPA que chocaban con la API.

## Decisiones
1. **Event store append-only** `simulation_events` (`simulation_id`, `sequence_number` único, tipo, fecha de sesión, `payload_json`,
   `engine_version`). El motor es PURO y determinista: re-evaluar las barras completas produce el mismo prefijo de eventos. `update_simulation` añade
   sólo los eventos posteriores a los guardados; un evento guardado que el motor no reproduce lanza `EVENT_LOG_DIVERGENCE` (nunca reescribe historia).
   La segunda ejecución sin barras nuevas añade 0 eventos y 0 outcomes. El estado materializado (`simulation_outcomes`) sigue existiendo por rendimiento
   y guarda `event_count` y `engine_version`.
2. **Replay** (`pitquant simulation-replay [--verify]`): T0 + eventos, sin datos de mercado, con un `fold_events` INDEPENDIENTE de `evaluate`.
   Compara estado, entrada, salidas, posición restante, MAE, MFE, R, drawdown y exceso vs benchmark con el outcome persistido (`MATCH` o diferencias).
3. **Política de salidas explícita.** `TRACK_TARGETS_ONLY` (por defecto en las simulaciones nuevas: tocar un objetivo se registra, la posición sigue
   completa), `PARTIAL_FRACTIONS` (fracciones por objetivo en [0,1], suma ≤ 1) y `LEGACY_HALF_AT_TP1` (sólo para filas anteriores a este ADR, que no
   guardan política). `target_touched` ≠ `target_exit_filled`.
4. **Entradas y fills**: `MARKET_REFERENCE` (precio guardado al crear, entrada en T0), `LIMIT` (un precio) y `ENTRY_ZONE`; métodos
   `EXPLICIT_LIMIT`, `FAVORABLE_GAP`, `OPEN_WITHIN_ZONE`, `FIRST_ZONE_TOUCH`; salidas `STOP_GAP`, `STOP_LEVEL`, `TARGET_GAP`, `TARGET_LIMIT`,
   `INVALIDATION_CLOSE`, `EXPIRY_LAST_CLOSE`, `MANUAL`. Nunca se usa el cierre para llenar una entrada.
5. **Ambigüedad intradía**: entrada y stop/objetivo en la misma barra, o stop y objetivo que cerraría posición, ⇒ `AMBIGUOUS_INTRABAR` con los escenarios
   posibles (`STOP_FIRST`, `TARGET_FIRST`, …) y su R en el payload; no se elige ninguno. En `TRACK_TARGETS_ONLY` un stop y un toque en la misma barra
   es un stop (el resultado no depende del orden) con `touch_order_unknown`. Una entrada intrabarra no cuenta la parte de la barra que pudo precederla
   para MFE/MAE.
6. **MAE/MFE/R**: `mae_pct` NEGATIVO, `mfe_pct`, `mae_r`/`mfe_r` sobre el riesgo INICIAL (nunca recalculado). Las claves V0 `mae`/`mfe` se conservan.
7. **Snapshot T0**: `snapshot_hash` (SHA-256 del contenido congelado) y `source_provenance`; `verify_snapshot` detecta cualquier edición y
   `update_simulation` se niega (`SNAPSHOT_TAMPERED`).
8. **Contrafactual**: para `USER_MODIFIED` se evalúa el plan PITQuant original sobre LAS MISMAS barras en `simulation_counterfactuals` (append-only,
   etiqueta `COUNTERFACTUAL`). No forma parte del log real ni del replay y nunca se usa para entrenar.
9. **Predicción vs ejecución**: `prediction_outcome` (NULL mientras el modelo no esté validado) y `execution_outcome` son campos separados; un stop es un
   hecho de ejecución. Los flags del post-mortem son HECHOS con su definición (`STOP_HIT_BEFORE_LATER_TP`, `HIGH_MFE_LOW_REALIZED`,
   `TARGET_NEVER_APPROACHED`, `REGIME_CHANGED`, `TREND_REVERSED`, `FUNDAMENTAL_STATUS_CHANGED`); `stop_distance_atr` se guarda, `STOP_TOO_TIGHT` jamás se infiere.
10. **Insights** descriptivos por segmento con `INSUFFICIENT_SAMPLE` (N < 10 entradas) y sin recomendaciones. Hipótesis siempre `UNTESTED` al crearse.
11. **Transiciones validadas**: cancelar sólo antes de entrar; cierre manual sólo con posición abierta (`CANCELLED` es un estado nuevo).
12. **SPA**: las rutas `/simulations*` comparten ruta con la API; una navegación de navegador (`Accept: text/html`) recibe el SPA y las llamadas
    JSON la API, con `Vary: Accept` (V0 devolvía JSON al recargar el detalle).

## Consecuencias
Nada de esto cambia modelos, datasets, Feature Engine, holdout ni D-02. Las simulaciones V0 se siguen evaluando con su comportamiento original.
Limitación: `simulation-update` re-evalúa todas las barras posteriores a T0 y añade sólo los eventos nuevos (el motor no se reanuda desde un
checkpoint); el resultado es idéntico y el coste es lineal en el horizonte (≤ 60 sesiones).
