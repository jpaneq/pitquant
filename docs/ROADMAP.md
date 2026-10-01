# Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Arquitectura, ADRs, esquema de datos, flujos, catálogo de tests | ✅ |
| 1 | Infraestructura + Security Master + universo histórico | ✅ |
| 2 | Market data + corporate actions + calendarios | 🟡 calendarios, precios raw, ajuste as-of, total return, DQ e ingestión idempotente hechos. Falta: stock-for-stock M&A, spin-offs, derechos, FX, almacén Parquet/DuckDB para histórico masivo, benchmarks TR |
| 3 | Fundamentales PIT | 🟡 modelo bitemporal, `facts_as_of`, reexpresiones, latencia conservadora. Falta: conector real (D-01/D-04), normalización de conceptos XBRL, macro vintages |
| 4 | Feature store | 🟡 `FeatureSnapshot` inmutable con hash, preprocesado sin fugas. Falta: motores fundamental/técnico/régimen y caché |
| 5 | Baseline scoring + calibración | ⬜ |
| 6 | Time Machine completo + regression test diario | 🟡 reconstrucción PIT en `/analysis` y `scripts/demo_time_machine.py` |
| 7 | Backtest histórico (panel completo, labels, outcomes) | 🟡 `label_window`, `total_return`, tablas `backtest_*` |
| 8 | Walk-forward + purging + embargo + holdout | ✅ splitter, guards y holdout bloqueado |
| 9 | Analytics + dashboard | ⬜ |
| 10 | Challengers ML | ⬜ (sólo tras el baseline) |
| 11 | Forward paper test | 🟡 tabla `live_predictions` |

**Siguiente paso recomendado:** cerrar D-01…D-03 (fuentes de datos) y construir el
conector SEC EDGAR + la carga del histórico de constituyentes IBEX 35; sin eso, cualquier
resultado de backtest sería sobre datos sintéticos.
