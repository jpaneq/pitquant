# Flujo point-in-time y flujo de backtest

## A. Flujo point-in-time de un análisis (`POST /analysis` y Time Machine)

```
entrada: ticker, exchange, as_of (tz-aware), horizons, model_version
 1. require_aware(as_of)                         → NaiveDatetimeError si no tiene zona
 2. security_id = SecurityMaster.resolve(ticker, exchange, as_of)
        ticker_history con valid_from ≤ as_of < valid_to   (0 → UnknownSecurity, >1 → Ambiguous)
 3. cal = calendar_for(security.exchange)
    last_closed_session = última sesión con close < as_of
 4. PITContext(as_of) — único objeto que entrega datos a los motores:
      prices      = raw OHLCV con bar_close ≤ as_of, ajustado con CA ex_date ≤ as_of
      fundamentals= as_of_view(facts, as_of)  (última revisión con available_at ≤ as_of)
      macro       = as_of_view(macro, as_of)   (vintage, no serie revisada)
      universe    = universe(index, as_of)     (para percentiles cross-sectionales)
      estimates   = sólo si provider.is_point_in_time
 5. motores (fundamental, técnico, régimen) → FeatureValue(name, value, available_at, source_ref)
 6. FeatureSnapshot.freeze()
      PITGuard: assert max(available_at) ≤ as_of   → LookAheadError (pipeline falla)
      missing_mask, imputed_mask, dq_warnings
      content_hash = sha256(json canónico)
 7. scoring → subscores 0–100 → calibrador → probability, expected_excess, confidence → signal
 8. Prediction (append-only) con versiones, git commit, seed, config_hash, snapshot hash
 9. execution_timestamp = next_session_open(as_of)
10. [Time Machine] si now ≥ label_available_at: calcular outcome (TR, benchmark, excess,
    drawdown, MAE/MFE) y mostrarlo DEBAJO, sin alimentar nunca el paso 5–7.
```

## B. Flujo de backtest (panel histórico)

```
config: universe=[SP500, IBEX35], frequency=monthly(first_session), horizons=[6m,12m],
        model_version (congelado), validation=expanding_walk_forward, embargo=horizonte
 1. dates = primera sesión de cada mes en [start, end] según calendario del mercado
    (end ≤ inicio del holdout salvo ejecución autorizada con HoldoutGuard.unlock)
 2. para cada T0 en dates (paralelizable, idempotente, cacheado por (T0, data_version)):
      a. U = universe(index, T0) − filtros PIT documentados (motivo guardado)
      b. para cada s en U: snapshot(s, as_of=close(T0)) → PITGuard
      c. predicciones congeladas (backtest_observations)
 3. labels: para cada observación
      t_exec = next_session_open(as_of)
      label_end = sesión ≥ t_exec + h meses
      label_available_at = close(label_end) + latencia
      TR acción (incl. dividendos, delisting return, consideración M&A)
      TR benchmark mercado y sector (total return) → excess
 4. validación (si el modelo aprende pesos/calibración):
      PurgedWalkForward(expanding|rolling) → folds
        train: label_available_at ≤ train_cutoff, purgado, embargado
        validation: selección de hiperparámetros (nested)
        test: sólo evaluación
 5. analytics sobre OOS: IC (Spearman) por fecha → media/mediana/IR con errores HAC,
    deciles D1…D10 y spread, calibración (Brier, log loss, curva, ECE), métricas de
    clasificación, resultados por año/sector/régimen/confianza, bootstrap por bloques
 6. backtest_runs guarda: config_hash, versiones, nº de experimentos acumulados (para
    Deflated Sharpe / PBO), fechas, filas, informe
```

**Modo non-overlapping:** una cohorte cada `h` meses (6M → 2/año; 12M → 1/año).
**Modo overlapping:** cohortes mensuales; los errores estándar usan Newey-West con
`lags = h_meses − 1` y bootstrap por bloques de longitud ≥ h.

## C. Separación de responsabilidades

| Pregunta | Componente | Datos permitidos |
|---|---|---|
| ¿Qué se sabía en T? | PIT engine | `available_at ≤ T` |
| ¿Qué habría dicho el modelo? | scoring/modelos | sólo `FeatureSnapshot` |
| ¿Qué pasó después? | labels | precios `> t_exec` — nunca vuelven a features |
| ¿Funciona el modelo? | validation + analytics | labels con `label_available_at ≤ train_cutoff` para entrenar |
