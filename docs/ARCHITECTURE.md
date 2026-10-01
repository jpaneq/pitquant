# PITQuant — Arquitectura técnica

> Plataforma de análisis bursátil, scoring y backtesting **point-in-time** (PIT).
> Regla de oro: *el objetivo no es explicar el pasado, sino determinar si la información
> disponible en cada momento contenía señal predictiva útil sobre resultados posteriores.*

Prioridades ante cualquier conflicto de diseño (en este orden):
1. ausencia de sesgos · 2. reproducibilidad · 3. auditabilidad · 4. robustez estadística ·
5. interpretabilidad · 6. rendimiento.

---

## 1. Vista general

```
                ┌───────────────────────────── Providers (interfaces ABC) ─────────────────────────────┐
                │ PriceProvider · FundamentalProvider · IndexMembershipProvider · CorporateActions...  │
                └───────────────┬──────────────────────────────────────────────────────────────────────┘
                                │ raw records + provenance (provider, original_id, retrieved_at, raw)
                                ▼
 ┌────────────────────── INGESTION (idempotente, append-only, data quality) ──────────────────────┐
 │  normaliza → valida (DQ engine) → asigna security_id → escribe con available_at + ingested_at  │
 └───────────────┬───────────────────────────────────────────────┬────────────────────────────────┘
                 ▼                                               ▼
     PostgreSQL (metadatos, registros,               Parquet + DuckDB (series masivas:
     predicciones inmutables, experimentos)          OHLCV raw, facts bitemporales)
                 │                                               │
                 └──────────────────────┬────────────────────────┘
                                        ▼
                   ┌────────── POINT-IN-TIME ENGINE (único punto de lectura) ──────────┐
                   │  as_of_view(as_of): revisiones con available_at ≤ as_of            │
                   │  universe(index, as_of) · security_master.resolve(ticker, as_of)   │
                   │  PITGuard: falla con LookAheadError si available_at > as_of        │
                   └────────────────────────────────┬──────────────────────────────────┘
                                                    ▼
          FEATURE ENGINE (fundamental · técnico · régimen) → FeatureSnapshot (inmutable, hash)
                                                    ▼
          SCORING baseline (subscores 0–100) → CALIBRATOR (score → P(outperform)) → SIGNAL
                                                    ▼
          predictions (append-only)  ──►  LABELS (excess TR, label_available_at)  ──►  ANALYTICS
                                                    ▲
          VALIDATION: walk-forward · purging · embargo · nested · holdout bloqueado · forward test
```

**Invariante central:** ningún módulo de features, scoring o modelos accede a datos
directamente. Todo pasa por el PIT engine, que recibe un `as_of` timezone-aware y
devuelve únicamente lo conocible en ese instante. El `PITGuard` vuelve a comprobarlo
al congelar cada snapshot (defensa en profundidad).

## 2. Modelo temporal (bitemporal)

Cada dato tiene dos ejes de tiempo:

| Eje | Campos | Pregunta |
|---|---|---|
| Tiempo de validez | `period_start`, `period_end` | ¿A qué periodo económico se refiere? |
| Tiempo de conocimiento | `available_at` (= publicación + latencia), `ingested_at` | ¿Cuándo pudo saberlo un inversor? ¿Cuándo lo supimos nosotros? |

- Las revisiones **nunca sobrescriben**: se añade una fila nueva con `revision_id` y su propio `available_at`.
- `as_of_view(as_of)` elige, por `(security_id, concepto, period_end)`, la revisión con mayor `available_at ≤ as_of`.
- `ingested_at` permite reconstruir "lo que el sistema tenía cargado" en una fecha (forward test) — distinto de lo que el mercado conocía (backtest).
- Cuando la fuente solo da fecha (sin hora), `available_at` se fija de forma **conservadora**: fin de la sesión de esa fecha en la zona del mercado + latencia configurable. Nunca se redondea hacia atrás.

## 3. Momento de señal y de ejecución

- `as_of` = instante de análisis (p. ej. 2020-06-15 16:00 America/New_York).
- Features técnicas usan solo barras **cerradas** antes de `as_of`. Si `as_of` cae dentro de una sesión, la barra de ese día no se usa.
- `signal_timestamp = as_of`. `execution_timestamp` = siguiente apertura de sesión estrictamente posterior (modo `next_open`, por defecto). Alternativas configurables: `next_close`, `next_vwap`, `delay_sessions=N`.
- Horizontes 6M/12M se calculan en **meses de calendario** desde la fecha de ejecución y se ruedan a la siguiente sesión válida del calendario real (XNYS / XMAD). Nunca `+180 días`.

## 4. Universo histórico y supervivencia

- `index_membership` guarda intervalos `[inclusion_date, exclusion_date)` por `security_id`.
- `universe(index, T0)` devuelve los miembros efectivos en T0 y **oculta** cualquier `exclusion_date > T0` y su motivo (saber que una empresa saldrá del índice es información futura).
- Empresas quebradas, adquiridas o deslistadas permanecen en el Security Master con `successor_security_id` / `acquirer_security_id`; sus retornos de deslisting se incorporan al label.
- Los filtros de universo (liquidez, datos mínimos) son parte de la definición PIT y se evalúan con datos de T0; cada exclusión guarda su motivo.

## 5. Precios y corporate actions

- Se almacena **solo** `raw` OHLCV + eventos de corporate actions (con `ex_date` y `announced_at`).
- El precio ajustado se calcula **as-of**: en un snapshot T se aplican solo los eventos con `ex_date ≤ T`. Los splits posteriores a T jamás tocan la serie que ve el modelo en T (en la práctica no cambian ratios, pero sí niveles absolutos y comparaciones de umbral).
- `raw_price`: valoración (precio × acciones en circulación del mismo momento), fills de ejecución.
- `adjusted_price` (as-of): indicadores técnicos, retornos.
- Total return: reinversión de dividendos en el ex-date; se compara siempre contra un benchmark **total return** (S&P 500 TR, IBEX 35 con Dividendos).

## 6. Labels y disponibilidad de labels

Para una observación con ejecución en `t_exec` y horizonte `h`:
- `label_end` = sesión de cierre `h` meses después.
- `label_available_at` = cierre de `label_end` + latencia de datos.
- Target principal: `excess_TR = TR_stock − TR_benchmark` (log o simple, configurable).
- **Regla:** una observación solo entra en un training set con corte `train_cutoff` si `label_available_at ≤ train_cutoff`. Se comprueba en el splitter y otra vez al entrenar.

## 7. Validación

1. **Panel completo** del universo PIT en snapshots mensuales (primera sesión del mes).
2. **Walk-forward** (expanding por defecto, rolling configurable) con particiones train/validation/test.
3. **Purging**: se elimina del train toda observación cuyo intervalo `[t_exec, label_end]` se solape con el de cualquier observación de validación/test.
4. **Embargo**: hueco adicional tras cada bloque de test (por defecto = horizonte).
5. **Nested**: hiperparámetros solo con validation interna; test nunca se mira para elegir.
6. **Holdout final** bloqueado: acceso solo con modelo congelado; cada acceso queda registrado y es irrevocable.
7. **Forward paper test**: `live_predictions` inmutables desde hoy.
8. Modo **non-overlapping** (una cohorte por horizonte) para la evaluación más limpia; modo overlapping con errores estándar HAC / block bootstrap.

## 8. Score ≠ probabilidad

El baseline produce subscores 0–100 interpretables (Quality, Valuation, Growth…).
La probabilidad `P(outperform | features)` la produce un **calibrador** (isotónico o Platt)
ajustado exclusivamente sobre predicciones out-of-sample de folds anteriores. La señal
BUY/HOLD/SELL sale de umbrales sobre la probabilidad calibrada y la confianza; HOLD es
la salida por defecto cuando la evidencia es insuficiente o hay avisos de calidad de datos.

## 9. Reproducibilidad y versionado

Cada predicción guarda: `model_version`, `code_version` (git commit), `data_version`,
`feature_version`, `scoring_version`, `config_hash`, `seed`, `created_at`, y el
`snapshot_id` cuyo contenido tiene un hash SHA-256 canónico. Predicciones y snapshots
son **append-only**: guard en el ORM + trigger en PostgreSQL.

## 10. Estructura del código

```
src/pitquant/
  core/            tipos, errores, utilidades de tiempo, hashing
  config/          settings (YAML + env), configuración por defecto
  db/              modelos SQLAlchemy de todas las tablas, guards de inmutabilidad
  security_master/ registro de valores, historial de tickers e identificadores
  universe/        index_membership y universe(index, as_of)
  data/
    providers/     interfaces abstractas + proveedor SINTÉTICO etiquetado
    point_in_time/ PITGuard, as_of_view bitemporal
    corporate_actions/ ajuste as-of y total return
    calendars/     calendarios reales XNYS/XMAD, ejecución, horizontes
    validation/    data quality engine
  features/        FeatureSnapshot (inmutable, hash, missing mask)
  backtest/        labels y label_available_at
  validation/      walk-forward, purging, embargo, holdout guard
  api/             FastAPI
  jobs/            pipelines (orquestación Prefect, ADR-0006)
```

Fases posteriores añadirán `fundamentals/`, `technical/`, `market_regime/`, `scoring/`,
`models/`, `signals/`, `analytics/`, `experiments/` siguiendo la misma regla: sólo leen
del PIT engine.

## 11. Documentos relacionados

- `docs/adr/` — decisiones arquitectónicas (ADR-0001 … ADR-0012)
- `docs/DATA_MODEL.md` — esquema completo de datos
- `docs/PIT_AND_BACKTEST_FLOWS.md` — flujo point-in-time y flujo de backtest paso a paso
- `docs/ANTI_LEAKAGE_TESTS.md` — catálogo de tests y su estado
- `docs/PENDING_DECISIONS.md` — decisiones que requieren al propietario
- `docs/ROADMAP.md` — fases y estado
