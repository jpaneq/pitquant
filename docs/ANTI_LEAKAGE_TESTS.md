# Catálogo de tests anti-leakage

Todos llevan el marcador `pit` y CI los ejecuta en un paso propio que **no puede omitirse**
(`pytest -m pit`). Estado a 2026-10-01: **69 tests pasan, 1 omitido localmente**
(`test_postgres`, requiere PostgreSQL; corre en CI).

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

## Tests adicionales

| Riesgo | Test |
|---|---|
| Reutilización de tickers | `test_ticker_reuse_resolves_to_different_securities_by_date`, API `test_ticker_reuse_via_api` |
| Saber de antemano que una empresa saldrá del índice | `test_universe_member_does_not_expose_future_exit`, `test_view_hides_future_delisting` |
| Universo desde constituyentes actuales | `test_non_point_in_time_membership_provider_rejected` |
| Reexpresiones contables | `test_restatement_only_visible_after_publication` |
| Corporate action anunciada después de `as_of` | `test_adjustment_ignores_events_not_yet_announced` |
| Fecha sin hora de publicación | `test_date_only_publication_is_conservative` |
| `+180 días` en lugar de calendario | `test_horizon_uses_calendar_months_and_rolls_to_session` |
| Datetimes naive | `test_naive_datetime_rejected`, `test_naive_observation_times_rejected`, API `test_naive_datetime_rejected_by_api` |
| Hiperparámetros elegidos con labels futuros | `test_validation_labels_known_at_decision_time` |
| Normalización cross-sectional con otras fechas | `test_cross_sectional_transforms_never_mix_dates` |
| Retornos perdidos al deslistar | `test_bankruptcy_delisting_return_is_minus_100pct`, `test_missing_history_without_terminal_event_fails_loudly` |
| Mutación por SQL directo | `tests/integration/test_postgres.py` (triggers) |

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
