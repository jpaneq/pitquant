# Catálogo de tests anti-leakage

Todos llevan el marcador `pit` y CI los ejecuta en un paso propio que falla si alguno se
omite. Estado a 2026-10-01:

- **108 tests pasan sobre SQLite** (87 marcados `pit`).
- **12 tests de PostgreSQL** se omiten sin `PITQUANT_PG_URL`. Se han ejecutado aquí en
  **modo estricto contra PostgreSQL 16.2 real** y pasan; aun así **no se consideran
  verificados hasta que el job `postgres` de CI los ejecute**. En ese job
  (`PITQUANT_REQUIRE_POSTGRES=1`) la ejecución falla si la URL no es PostgreSQL, si se
  recogen o ejecutan cero tests `postgres`, o si cualquiera queda *skipped*.

## Tests exigidos en §80

| Test pedido | Implementación | Estado |
|---|---|---|
| `test_no_future_financial_data` | `tests/unit/test_point_in_time.py::test_no_future_financial_data` — reproduce el ejemplo del Q3-2020 publicado el 5-nov | ✅ |
| `test_no_future_price_data` | `test_point_in_time.py::test_no_future_price_data` — la barra de una sesión no cerrada nunca es visible | ✅ |
| `test_historical_index_membership` | `test_universe.py::test_historical_index_membership` | ✅ |
| `test_delisted_companies_preserved` | `test_security_master.py::test_delisted_companies_preserved` + `test_universe.py::test_universe_never_built_from_current_constituents` | ✅ |
| `test_next_session_execution` | `test_calendar.py::test_next_session_execution` (festivo, fin de semana, apertura exacta) | ✅ |
| `test_label_availability` | `test_validation_splits.py::test_label_availability` — ejemplo literal de §33 | ✅ |
| `test_purged_training` | `test_validation_splits.py::test_purged_training` | ✅ |
| `test_embargo` | `test_validation_splits.py::test_embargo` | ✅ |
| `test_split_adjustment` | `test_point_in_time.py::test_split_adjustment_is_as_of` + `test_returns.py::test_split_total_return_is_continuous`, `test_reverse_split` | ✅ |
| `test_dividend_total_return` | `test_returns.py::test_dividend_total_return` | ✅ |
| `test_merger_handling` | `test_returns.py::test_merger_handling_cash_consideration` (+ quiebra −100 %) | ✅ (cash); stock consideration → fase 2 |
| `test_reproducible_snapshot` | `test_snapshots_and_immutability.py::test_reproducible_snapshot` | ✅ |
| `test_timezone` | `test_calendar.py::test_timezone_and_dst` (semana de desfase DST EE. UU./UE) | ✅ |
| `test_market_calendar` | `test_calendar.py::test_market_calendar_holidays`, `test_early_closes` | ✅ |
| `test_scaler_train_only` | `test_snapshots_and_immutability.py::test_scaler_train_only` | ✅ |
| `test_imputer_train_only` | `test_snapshots_and_immutability.py::test_imputer_train_only` | ✅ |
| `test_holdout_never_used_for_training` | `test_validation_splits.py::test_holdout_never_used_for_training` (+ unlock sólo con modelo congelado y registrado) | ✅ |
| `test_model_version_immutability` | `test_snapshots_and_immutability.py::test_model_version_immutability` + `test_predictions_and_snapshots_are_append_only` | ✅ |

## D-01 — SEC EDGAR (`tests/unit/test_sec_edgar.py`, fixtures ficticias)

| Test exigido | Qué demuestra |
|---|---|
| `test_later_restatement_does_not_rewrite_history` | FY2023 = 100 en un snapshot de 2024 aunque el 10-K de 2025 lo reexprese a 95; ambas versiones conservadas; editar una versión falla |
| `test_companyfacts_later_fact_not_visible_early` | companyfacts descargado hoy no adelanta un hecho antes de `accepted_at + lag` |
| `test_fact_bound_to_accession` | cada hecho lleva cik, accession, form, filed_date, accepted_at, taxonomía, unidad, documento; header archivado con `published_at`; accession huérfano rechazado |
| `test_amended_filing_visibility` | el 10-Q/A sólo sustituye al 10-Q desde su aceptación |
| `test_acceptance_datetime_controls_availability` | aceptado 16:15 ET → no visible al cierre ni esa noche; visible en la siguiente apertura; pre-market visible esa mañana; sábado → lunes |
| `test_same_period_multiple_filings` | varias versiones del mismo hecho; se elige la disponible en cada `as_of` |
| extra | validación contra la instancia XBRL del filing, cobertura 2011+, idempotencia (con revalidación desde el archivo), DST del header, User-Agent y reintentos |

## D-02 — S&P 500 (`tests/unit/test_sp500_history.py`)

Construcción canónica desde fichero licenciado, causa obligatoria en altas/bajas,
reconstrucción provisional etiquetada como tal, anuncios inconsistentes → error, sin
duplicados, tamaño validado, fuentes `CROSSCHECK_ONLY` rechazadas, detección de
discrepancias.

## D-03 — IBEX 35 (`tests/unit/test_ibex_history.py`, fechas ilustrativas)

| Test exigido | Qué demuestra |
|---|---|
| `test_ibex_ticker_change_preserves_security_id` | mismo `security_id`, dos filas en `ticker_history` |
| `test_gas_to_ntgy_not_membership_turnover` | marcador ilegible → resuelto por aviso BME, un único intervalo continuo |
| `test_ree_to_red_not_membership_turnover` | marcador visual de cambio de código → `TICKER_CHANGE`, sin altas/bajas |
| `test_ibex_extraordinary_review` | evento padre `EXTRAORDINARY_REVIEW` con sus altas/bajas hijas |
| `test_announcement_date_not_effective_date` | anunciado 4-jun, efectivo 22-jun: el universo cambia sólo el 22; `announced_changes` lo expone antes |
| `test_ibex_membership_reconstruction_from_events` | 35 miembros tras cada evento, salidas con fecha efectiva exclusiva |
| extra | fila ambigua sin aviso → `UnresolvedSourceEventError`; marcador que contradice al aviso → error; tamaño fuera de rango → build fallido; extracción PDF con calibración (y sin calibración → `UNKNOWN`); archivo detecta manipulación |

## Criterio de terminación (`tests/integration/test_reconstruction.py`)

Para T = 28-jun-2024 16:00 ET: universo, ticker en T, fundamentales publicados en T con su
accession y `available_at`, evento de entrada de cada miembro; repetir da el mismo hash;
tras ingerir una reexpresión posterior **y** una corrección del proveedor del índice, la
reconstrucción con el mismo `DataVersion` es idéntica.

## Holdout sellado (`tests/unit/test_holdout_sealed.py`)

Modelo no congelado → rechazado; una evaluación por versión; acceso y lectura registrados;
analytics de desarrollo no pueden tocar el rango; ninguna ruta de la API lo expone.

## Inmutabilidad en PostgreSQL (`tests/integration/test_postgres.py`)

`test_prediction_update_rejected`, `test_prediction_delete_rejected`,
`test_snapshot_update_rejected`, `test_snapshot_delete_rejected` (también en versión ORM),
más hechos, eventos de índice, versión de modelo congelada, triggers presentes en todas
las tablas inmutables, migración = modelos, timestamps UTC.

## Tests adicionales

| Riesgo | Test |
|---|---|
| Reutilización de tickers | `test_ticker_reuse_resolves_to_different_securities_by_date`, API `test_ticker_reuse_via_api` |
| Saber de antemano que una empresa saldrá del índice | `test_universe_member_does_not_expose_future_exit`, `test_view_hides_future_delisting` |
| Universo desde constituyentes actuales | `test_non_point_in_time_membership_provider_rejected` |
| Reexpresiones contables | `test_restatement_only_visible_after_publication` |
| Corporate action anunciada después de `as_of` | `test_adjustment_ignores_events_not_yet_announced` |
| Fecha sin hora de publicación (DATE_ONLY, ADR-0018) | `test_date_only_publication_is_conservative`, `test_xmad_date_only_policy` |
| `+180 días` en lugar de calendario | `test_horizon_uses_calendar_months_and_rolls_to_session` |
| Datetimes naive | `test_naive_datetime_rejected`, `test_naive_observation_times_rejected`, API `test_naive_datetime_rejected_by_api` |
| Hiperparámetros elegidos con labels futuros | `test_validation_labels_known_at_decision_time` |
| Normalización cross-sectional con otras fechas | `test_cross_sectional_transforms_never_mix_dates` |
| Retornos perdidos al deslistar | `test_bankruptcy_delisting_return_is_minus_100pct`, `test_missing_history_without_terminal_event_fails_loudly` |
| Mutación por SQL directo | `tests/integration/test_postgres.py` (triggers) |

## Añadidos en la iteración «real data readiness»

| Riesgo | Test |
|---|---|
| Disponibilidad SEC en bordes del calendario XNYS (pre-market, retardo que cae justo en el cierre, viernes, cierres anticipados, festivos, DST) | `test_conservative_session_edges` |
| `filingDate` usado como disponibilidad | `test_availability_never_derives_from_filed_date` |
| Deriva de companyfacts aplicada en silencio | `test_companyfacts_drift_is_reported_never_applied` |
| Segunda ingestión sin revalidar | `test_second_ingestion_revalidates_from_archived_instance` |
| Archivo crudo manipulado | `test_corrupted_archive_object_fails_revalidation` |
| Mismo ticker = misma emisión | `test_reentry_without_isin_is_a_new_unresolved_identity`, `test_every_event_and_interval_without_isin_is_unresolved` |
| Ticker moderno proyectado hacia atrás (S&P provisional) | `test_reconstruction_provider_is_provisional` |
| Backtest con identidad sin resolver | `test_membership_without_isin_is_identity_unresolved` (`backtest_universe` falla cerrado) |
| Linaje provisional que toca el holdout | `test_holdout_refuses_non_eligible_universe_lineage` |
| No poder explicar por qué se conocía o no un valor | `tests/integration/test_explain.py` |
| READY con fixtures o sin datos | `tests/unit/test_readiness.py` |
| Proveedor D-05 con sesgo de supervivencia o precios ajustados | `tests/contracts/test_d05_contract.py` |
| Suite PostgreSQL filtrada sin los tests críticos | `tests/conftest.py` (`_CRITICAL_PG_TESTS`) |

## Propiedades (Hypothesis, §81)

| Propiedad | Test |
|---|---|
| `as_of_view` nunca devuelve `available_at > as_of` y siempre la última revisión conocida | `test_as_of_view_never_returns_future_and_returns_latest` |
| `max(feature.available_at) ≤ snapshot.as_of` o el snapshot falla | `test_snapshot_max_available_at_le_as_of_or_fails` |
| `next_session_open(ts) > ts` y es una apertura real; `last_closed_session` cerró antes de `ts` | `test_next_session_open_strictly_after_and_is_a_real_open` |
| Todo fold respeta label availability, purging y disjunción para cualquier horizonte/embargo/latencia | `test_every_fold_respects_label_availability_and_purging` |

## Pendientes (fases posteriores)

- Stock consideration en fusiones y spin-offs con reparto de base de coste (fase 2).
- Vintages macro reales y test de revisiones macro (fase 3, con `MacroProvider`).
- Test de que `analyst_estimates` queda desactivado sin proveedor PIT (fase 3).
- Reproducibilidad end-to-end de predicción (fase 5–6: regenerar predicción y comparar).
- Daily pipeline regression test (§78) sobre un conjunto fijo de valores/fechas (fase 6).
