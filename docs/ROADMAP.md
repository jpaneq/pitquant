# Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Arquitectura, ADRs, esquema de datos, flujos, catálogo de tests | ✅ |
| 1 | Infraestructura + Security Master + universo histórico | ✅ |
| 1b | D-01…D-03: archivo de fuentes, SEC por accession, universos por eventos, holdout sellado, CI PostgreSQL estricto | ✅ en código y tests con fixtures · ⏳ pendiente: ejecución real contra SEC/S&P/BME y job `postgres` de CI en verde |
| 1c | Verificación real de la toolchain, PostgreSQL local estricto, identidad ≠ membership (ADR-0017), `audit.explain`, `pitquant data-readiness`, contrato D-05, política DATE_ONLY (ADR-0018), jobs SEC | ✅ en código y tests · ✅ SEC real (MSFT y AAPL) · 🟡 BME: PDF real calibrado, sin build (falta composición inicial o actual y 7 avisos) · ⏳ CNMV (documentos por identificar y aprobar) · ⏳ D-05 (decisión económica) |
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

**Siguiente paso:** cargas reales, que requieren red y licencias:
1. Fijar `PITQUANT_SEC_USER_AGENT`; después `pitquant sec-stress-scan` y `pitquant sec-ingest`
   sobre unos pocos CIK, y revisar `pitquant explain`.
2. Calibrar el parser BME con el PDF oficial y sus avisos, y aportar los ISIN oficiales.
3. Vertical slice CNMV (ADR-0018).
4. Ejecutar la suite D-05 contra los candidatos y verificar sus casos.

El Feature/Scoring Engine no empieza hasta que `pitquant data-readiness` salga READY con
datos reales.

## Módulos acordados para fases posteriores (NO implementar todavía)

### Decision Support Engine
Incluirá:
- tesis de inversión e invalidadores de la tesis;
- riesgos;
- expectativas descontadas por el precio y variables a vigilar;
- comprar / mantener / reducir / evitar;
- escenarios bear / base / bull;
- confianza condicionada a sector y régimen;
- Historical Analogues.

### BTC Engine
Módulo separado de equities, con backtesting point-in-time:
- técnico, on-chain y network fundamentals;
- derivados, macro y liquidez;
- modelos por horizonte;
- fan charts probabilísticos.

### AI Audit / Model Review Export
Exportará todo lo necesario para que una IA externa audite:
- predicciones, errores y calibración;
- features, contribuciones y drift;
- historical analogues y procedencia;
- Champion vs Challenger y outcomes realizados.

Salida en Markdown/PDF legible más JSON/CSV procesable. Nunca expone secretos ni el
holdout sellado.

### También pendientes
- BUY/HOLD/SELL y pesos definitivos.
- Optimización.
- ML predictivo.
- Champion/Challenger productivo.
- Price targets.
