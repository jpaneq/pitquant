# Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Arquitectura, ADRs, esquema de datos, flujos, catálogo de tests | ✅ |
| 1 | Infraestructura + Security Master + universo histórico | ✅ |
| 1b | D-01…D-03: archivo de fuentes, SEC por accession, universos por eventos, holdout sellado, CI PostgreSQL estricto | ✅ en código y tests con fixtures · ⏳ pendiente: ejecución real contra SEC/S&P/BME y job `postgres` de CI en verde |
| 1d | ADR-0019 (zona horaria EDGAR), GitHub privado con CI verde (incl. PostgreSQL y Docker 3.12), universo IBEX real desde documentos BME, recuperación SEC desde instancia, slice CNMV real (Enagás), bake-off D-05 (11/20 casos verificados), readiness v2 | ✅ · ⏳ identidades IBEX históricas (ISIN fechados), D-05 (decisión económica), S&P DJI (licencia) |
| 1e | Emisor ≠ security y snapshots ANCV (ADR-0020, migración 0004), `IdentityResolutionEngine`, identidad IBEX 2011+ (61/68 intervalos), 5 de 7 filas BME resueltas, Enagás de extremo a extremo; capa de market data normalizada, adapters Sharadar (SEP, ACTIONS, TICKERS, SP500), EODHD y Alpha Vantage (sólo QA), modelo de corporate actions, motor de total return, Data Coverage Engine y elegibilidad del analizador (ADR-0021); readiness v3 | ✅ en código y tests · ✅ ANCV real (33 snapshots) · ⏳ claves de API (BLOCKED_BY_CREDENTIAL) · ⏳ 7 intervalos IBEX sin probar (MTS y FER con ISIN extranjero, ABG.P, ventanas REE/GRF, borde PHM) |
| 1f | ADR-0022: evidencia oficial código↔ISIN (fichas BME archivadas, boletines diarios), 5 transiciones de ISIN verificadas contra el original (MTS, GRF, REE, PHM, FER como security nueva), motor v4, `cohort-readiness`, traza de corporate actions, fundamentales SEC por emisor | ✅ identidad IBEX 2011+: 68/68 intervalos, 190/190 fechas · ⏳ precios, corporate actions y fundamentales de los miembros para la primera cohorte completa |
| 1g | ADR-0023: primeros datos reales (EODHD demo AAPL/MSFT, boletín BME para ENG), corporate actions oficiales (Apple IR, Enagás IR, Microsoft IR), Total Return validado en 6 ventanas reales, `reconstruct-security`, cohort-readiness por capas | ✅ split/dividendo reales neutralizados vs cálculo independiente · ⏳ Alpha Vantage real (sin clave), histórico 2011+ (D-05) |
| 1h | ADR-0024: Tiingo EOD como candidato D-05 (adapter, cupo, comparador vendor-oficial, cobertura por fichero público), CUSIP oficial AAPL/MSFT (13G), identidad sin ISIN obligatorio, migración 0008 | ✅ código y evidencia CUSIP · ⏳ clave Tiingo y universo S&P histórico (D-02) para medir former/delisted |
| 1i | ADR-0025: evidencia de membresía S&P 500 (D-02 candidato): comunicados S&P tier 1/2, semántica after-close/before-open con calendario NYSE, replay reversible, migración 0009 | ✅ 90/549 eventos confirmados · ⏳ ancla actual y huecos listados en `docs/SP500_MEMBERSHIP_EVIDENCE.md` |
| 1j | ADR-0026/27/28: ancla SPY/IVV, reconstrucción D-02, Feature Engine V0 (51 features), Label Engine, Developer UI, readiness separados, migración 0010 | ✅ código, tests y snapshots reales AAPL/MSFT · ⏳ D-02 canónico (171/558 eventos), clave Tiingo, cohortes US |
| 1k | ADR-0029: Analyzer (producto) en paralelo al Research Lab: frontend profesional, Technical/Fundamental/Valuation/S-R/Analysis/TradePlan engines, búsqueda, informe, watchlist, migración 0011 | ✅ AAPL/MSFT FULL, KO FUNDAMENTAL_ONLY con datos reales · ⏳ clave Tiingo/EODHD (precios KO, SPY, referencia en vivo) |
| 1c | Verificación real de la toolchain, PostgreSQL local estricto, identidad ≠ membership (ADR-0017), `audit.explain`, `pitquant data-readiness`, contrato D-05, política DATE_ONLY (ADR-0018), jobs SEC | ✅ en código y tests · ✅ SEC real (MSFT y AAPL) · 🟡 BME: PDF real calibrado, sin build (falta composición inicial o actual y 7 avisos) · ⏳ CNMV (documentos por identificar y aprobar) · ⏳ D-05 (decisión económica) |
| 2 | Market data + corporate actions + calendarios | 🟡 calendarios, precios raw, ajuste as-of, ingestión idempotente; capa normalizada, adapters y total return con spin-offs y adquisiciones en efectivo y en acciones (ADR-0021). Falta: datos reales (claves), capa oficial BME/CNMV de corporate actions españolas, FX, almacén Parquet/DuckDB para histórico masivo, benchmarks TR |
| 3 | Fundamentales PIT | 🟡 modelo bitemporal, `facts_as_of`, reexpresiones, latencia conservadora. Falta: conector real (D-01/D-04), normalización de conceptos XBRL, macro vintages |
| 4 | Feature store | 🟡 `FeatureSnapshot` inmutable con hash, preprocesado sin fugas. Falta: motores fundamental/técnico/régimen y caché |
| 5 | Baseline scoring + calibración | ⬜ |
| 6 | Time Machine completo + regression test diario | 🟡 reconstrucción PIT en `/analysis` y `scripts/demo_time_machine.py` |
| 7 | Backtest histórico (panel completo, labels, outcomes) | 🟡 `label_window`, `total_return`, tablas `backtest_*` |
| 8 | Walk-forward + purging + embargo + holdout | ✅ splitter, guards y holdout bloqueado |
| 9 | Analytics + dashboard | ⬜ |
| 10 | Challengers ML | ⬜ (sólo tras el baseline) |
| 11 | Forward paper test | 🟡 tabla `live_predictions` |

**Siguiente paso** (sólo técnico):
1. Cerrar la identidad IBEX 2011+ con evidencia oficial: código BME ↔ ISIN extranjero para MTS
   y FER (NL desde 2023), clase B de Abengoa (ABG.P), fechas de cambio de ISIN de REE y GRF
   en 2016 y borde de PHM en 2020. Hoy, en fallo cerrado por fecha, MTS bloquea todas las
   fechas.
2. Con las claves de API: suite D-05 y contract tests sobre datos reales (Sharadar, EODHD),
   resolver las semánticas sin verificar y cruzar SHARADAR/SP500 con anuncios S&P DJI.
3. Capa oficial BME/CNMV de corporate actions españolas complejas.

Informes generados desde la base (no editar a mano): `docs/ISSUER_SECURITY_CHANGES.md`,
`docs/IDENTITY_BLOCKERS.md` (entrada de trabajo de la siguiente iteración) y
`docs/ADAPTER_FIELD_EVIDENCE.md` (frase oficial que justifica cada campo de los adapters).

Prioridad de la siguiente iteración:
1. (hecho en ADR-0022) Resolver los blockers de identidad que impiden formar cohortes: 190/190.
2. Introducir al menos un flujo real de market data.
3. Validar corporate actions reales.
4. Conseguir la primera cohorte histórica elegible.
5. Sólo entonces, Feature Engine (`FEATURE_ENGINE_READY = false` hasta entonces).

Criterio para iniciar el Feature Engine:
- identidad IBEX 2011+ prácticamente resuelta;
- emisor y security separados (hecho);
- provider S&P validable (adapter hecho; falta clave);
- adapters de market data listos (hecho);
- total return validado (con fixtures; falta con datos reales);
- que sólo falten claves e ingestión.

No se declara DATA READY sin precios reales suficientes.

## Requisitos de producto ya acordados (no implementar todavía)

### Stock Analyzer: universos de backtest ≠ valores analizables
- S&P 500 e IBEX 35 son los **universos de backtest iniciales**, no una restricción sobre
  qué acciones puede analizar PITQuant.
- El Stock Analyzer podrá analizar **cualquier** valor que tenga:
  - identidad inequívoca;
  - precios suficientes y corporate actions;
  - fundamentales;
  - un sector y benchmark adecuados;
  - la cobertura mínima exigida.
- `SUPPORTED_SECURITY` (cobertura suficiente) e `INDEX_MEMBERSHIP` (pertenencia a un
  universo) son conceptos separados.
- Búsqueda por ticker, nombre o identificadores (ISIN, CIK, CIF…), resolviendo siempre a
  `security_id`.
- Con cobertura insuficiente se devuelve `INSUFFICIENT_DATA` o `ANALYSIS_NOT_RELIABLE`.
  Nunca una señal artificial.

### Data Coverage Panel
Cobertura por valor de:
- histórico de precios, fundamentales y corporate actions;
- benchmark y sector;
- estimaciones de analistas, cuando existan fuentes PIT.

### Time Machine
Debe poder analizar también valores fuera del S&P y del IBEX cuando haya cobertura PIT
suficiente.

## Módulos acordados para fases posteriores (NO implementar todavía)

### Decision Support Engine
- Tesis, invalidadores y riesgos.
- Qué descuenta el precio y qué vigilar.
- Comprar / mantener / reducir / evitar.
- Escenarios bear / base / bull.
- Historical analogues.
- Confianza según sector y régimen.

### BTC Engine
Módulo separado que reutiliza la infraestructura común:
- spot 24/7 y técnico;
- on-chain y network fundamentals;
- derivados: funding, open interest, liquidaciones;
- macro;
- modelos por horizonte, probabilidades y fan charts;
- Time Machine PIT.

### AI Audit / Model Review Export
Exportación para auditoría externa por IA, de una predicción individual, de un lote, o de
Champion vs Challenger.

Contenido:
- versiones, snapshot, features y contribuciones;
- probabilidades y calibración;
- expected/excess return y escenarios;
- historical analogues y riesgos;
- cobertura de datos, procedencia y avisos;
- outcome realizado, drift y cambio respecto a la predicción anterior.

Formatos: Markdown, PDF, JSON y CSV. Nunca expone secretos ni el holdout sellado.

### También pendientes
- BUY/HOLD/SELL y pesos definitivos.
- Optimización.
- ML predictivo.
- Champion/Challenger productivo.
- Price targets y expected returns.

## Iteración 7 (2026-10-02): Research Lab listo, sin resultados (ADR-0030)
Hecho: modelo de datos 0012, walk-forward con guardas de holdout, Dataset Builder, missingness,
baselines predefinidos, métricas, contrato de predicción, backtest de Trade Plan, registro de
experimentos, `/research/*`, UI Research Lab, provenance del Analyzer y E2E de navegador.
Pendiente (datos): D-02 con ≥60 cohortes mensuales probadas fuera del holdout y D-05 con precios
reales; después, el primer experimento baseline.

## Iteración 8 (2026-10-03): D-02 por ventanas y demanda D-05 (ADR-0031)
Diagnóstico exacto de las ventanas 2017-10→2022-09 (60) y 2014-10→2022-09 (96), parser v3 sobre el archivo existente,
fichas de gap para investigación externa, plan de backfill de demanda sin llamadas, `US_BASELINE_V0` BLOCKED.
Siguiente: segunda ancla verificada ~2022-09/10, evidencia de los comunicados que faltan (`NO_DOCUMENT`) y tabla fechada
de alias de ticker de miembros; después Tiingo (D-05).

## Iteración 9 (2026-10-03): D-02 por grafo de anclas SEC (ADR-0032)
24 presentaciones SPY verificadas contra EDGAR (13 NPORT-P + 11 N-30D, 2017-09-30 → 2022-09-30) = 17 fechas de ancla, identidad por
CUSIP/ISIN/LEI, 16 segmentos con gaps LOCALES. Pendiente: evidencia oficial de las fechas de cada cambio (docs/SP500_LOCAL_GAPS.md) y
vínculos de identidad por cambio de CUSIP; extensión a 2014-2017 sólo cuando 2017-10→2022-09 llegue a 60/60.
