# Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Arquitectura, ADRs, esquema de datos, flujos, catálogo de tests | ✅ |
| 1 | Infraestructura + Security Master + universo histórico | ✅ |
| 1b | D-01…D-03: archivo de fuentes, SEC por accession, universos por eventos, holdout sellado, CI PostgreSQL estricto | ✅ en código y tests con fixtures · ⏳ pendiente: ejecución real contra SEC/S&P/BME y job `postgres` de CI en verde |
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

**Siguiente paso:** cargas reales (requieren red y licencias): fijar el User-Agent SEC y
ejecutar el conector sobre el universo; calibrar el parser BME con el PDF oficial y sus
avisos; adaptar el fichero licenciado S&P DJI. Después, D-05 (precios y corporate actions)
y D-04 (fundamentales IBEX). El Feature/Scoring Engine no empieza hasta que el criterio de
terminación se demuestre con datos reales, no sólo con fixtures.
