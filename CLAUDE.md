# PITQuant — contexto para Claude Code

Plataforma propia de análisis bursátil, scoring y backtesting **point-in-time** (S&P 500 e
IBEX 35). Propietario: Jairo Panero. Idioma de trabajo: **español** (código e
identificadores en inglés, documentación en español).

La especificación original completa (102 secciones) está en `docs/SPEC_ORIGINAL.md` y las
condiciones del propietario para D-01…D-03 en `docs/DECISIONES_D01_D03_PROPIETARIO.md`.
Léela antes de cualquier decisión de diseño importante.

## Regla de oro (no negociable)

El objetivo no es el backtest que mejor explique el pasado, sino saber si la información
disponible en cada momento contenía señal predictiva. Prioridades, en este orden:
**ausencia de sesgos > reproducibilidad > auditabilidad > robustez estadística >
interpretabilidad > rendimiento.** Si algo mejora resultados pero compromete la integridad
temporal, se rechaza.

## Reglas de implementación

- Todo dato lleva `available_at` (cuándo pudo saberlo un inversor) e `ingested_at`. Nada
  lee datos sin pasar por `PITContext` / `facts_as_of` / `IndexUniverse`.
- `PITGuard` hace fallar el pipeline si aparece `available_at > as_of`. Nunca silenciarlo.
- Datetimes siempre timezone-aware (UTC interno). Naive → error. Ruff tiene `DTZ` activado.
- Tablas append-only (ver `IMMUTABLE_TABLES` en `db/models.py`): nunca UPDATE/DELETE;
  correcciones = fila nueva. Hay guard ORM + triggers PostgreSQL.
- Membership de índices: sólo desde eventos (`index_events` → `membership_builds`).
  `TICKER_CHANGE` nunca se infiere; si la fuente es ambigua, se falla (no adivinar).
- Fundamentales SEC: procedencia por accession + header `ACCEPTANCE-DATETIME`;
  companyfacts sólo descubrimiento/validación.
- Holdout final **oct-2022 → sep-2025** fijado y sellado. Sólo
  `evaluate_candidate_on_holdout` (modelo congelado, una vez por versión, registrado).
  Nunca exponerlo en API/dashboard/analytics.
- No inventar datos. Fixtures y sintéticos claramente etiquetados (`SYN*`, CIK 0000999999,
  "FIXTURE"). Nunca presentarlos como históricos reales.
- No dar una funcionalidad por terminada porque "ejecuta": correcta, testeada, tipada,
  documentada, reproducible, point-in-time.
- Cada decisión arquitectónica relevante → ADR nuevo en `docs/adr/` (siguiente: 0043).
- Migraciones: `0001`…`0023` fijadas (`0023` rutina diaria) (`0022` posiciones simuladas) (`0021` fusiona la cabeza BTC `btc_v0_20261004_r1` con `0020`) (`0020` predicciones y Strategy Engine) (`0019` motor fijado por simulación, `event_schema_version` y observaciones históricas) (`0018` event store del Simulation Lab y contrafactual, `0017` ancho de event_type de sucesiones, `0016` Simulation Lab, `0015` tipos de sucesión) (`0014` lista SEC 13(f) y sucesión de securities) (`0013` grafo de anclas SEC SPY: `sp500_anchors`, `sp500_anchor_members`, `sp500_anchor_crosschecks`, `sp500_membership_segments`, `security_ticker_alias`) (`0011` perfiles descriptivos `security_profiles`) (`0010` anclas de índice SPY/IVV) (`0009` evidencia de membresía S&P 500) (`0008` evidencia de identificadores con clase OFFICIAL/DERIVED/VENDOR) (`0004` emisor/security y snapshots, `0005` evidencia
  código↔ISIN, `0006` transiciones de ISIN, `0007` traza de corporate actions, `role` de
  security e `issuer_id` en filings SEC); **todo cambio de esquema = revisión nueva**.
- Identidad (ADR-0022): sólo evidencia oficial EXACTA desempata o ancla un código; subir
  `ENGINE_VERSION` si cambia la lógica del motor (un run reutilizado debe coincidir con lo
  almacenado). Nunca relajar el fallo cerrado de `backtest_universe`.
- Emisor ≠ security (ADR-0020): fundamentales → `issuer_id`; precios y membership →
  `security_id`. Nunca reutilizar `security_id` por comodidad.
- Market data: sólo registros normalizados (`pitquant.market.normalized`); serie base = OHLCV
  RAW; ajustado del proveedor sólo QA; claves sólo por entorno y nunca archivadas (`redact`).
- Periodo canónico V1: 2011-01-01 → presente; lo anterior es `ARCHIVAL / NON_CANONICAL_FOR_V1`.
- No investigar precios, planes ni licencias de proveedores (gestión externa).

## Comandos

```bash
pip install -e ".[dev,postgres]"
make lint && make type && make test     # ruff, mypy --strict, pytest (SQLite)
make pit                                 # suite anti-leakage
PITQUANT_PG_URL=postgresql+psycopg://... make pg   # PostgreSQL real, modo estricto
python scripts/gen_data_model_doc.py     # regenerar docs/DATA_MODEL.md tras cambiar modelos
python scripts/demo_time_machine.py      # demo PIT sobre datos sintéticos
```

Antes de cada commit: lint + mypy + tests en verde. Commits en español o inglés,
descriptivos.

## Estado a 2026-10-01 (tras la iteración «identidad + adapters»)

Verificado ejecutando `make ci` (ruff, mypy strict, suite `pit`, suite completa) y
`make pg-local` (PostgreSQL 16.2 embebido: suite estricta y alembic upgrade/check/downgrade).

Hecho:
- **Fases 0–1, D-01…D-03, ADR-0017…0019** (ver `docs/ROADMAP.md`).
- **ADR-0020: emisor ≠ security.**
  - Snapshots ANCV: `CNMVSecurityIdentityProvider`, 33 distribuciones 06/2010–06/2026 y tres
    formatos.
  - `IdentityResolutionEngine`, con segmentos de identidad por intervalo.
  - `backtest_universe` devuelve la security probada.
  - Consulta ANCV por NIF (vínculo CIF ↔ ISIN).
- **ADR-0021: capa de market data normalizada.**
  - Adapters `SharadarMarketDataProvider`, `SharadarSP500MembershipProvider` (candidato,
    no canónico), `EODHDMarketDataProvider` y `AlphaVantageLifecycleQAProvider` (sólo QA).
  - Modelo de corporate actions; motor de total return; Data Coverage Engine; elegibilidad
    `SUPPORTED_SECURITY ≠ INDEX_MEMBERSHIP`.
- **`pitquant data-readiness` v3**, con componentes separados (identidad US/ES, adapter ≠ dato
  real, total return).

**Datos reales** (sólo en local, sin versionar):
- **Dónde:** `data/pitquant.db`, `data/archive/` y `data/sources/ancv/` (zips ANCV).
- **Bases previas conservadas:** `pitquant_dev_v0…v3.db`; la v3 tiene una propiedad duplicada
  de ISIN por un bug ya corregido.
- **SEC (MSFT, AAPL):** 127 filings y 51.538 hechos (ADR-0019).
- **IBEX 35 (ADR-0022):**
  - Identidad 2011+: **68/68 intervalos resueltos (17 EXACT + 51 MULTI_SOURCE)** y **190/190 fechas
    candidatas** pasan `backtest_universe` (antes 0/190). Calibración: 35/35 contra la composición
    BME vigente. `docs/IDENTITY_BLOCKERS.md`, `docs/ISSUER_SECURITY_CHANGES.md`,
    `docs/OFFICIAL_IDENTITY_EVIDENCE.md`.
  - Evidencia: fichas oficiales archivadas (Internet Archive) 2012–2022, boletines diarios de BME
    2022–2026 y 5 transiciones de ISIN verificadas contra el original (MTS 2017, GRF 2016, REE
    2016, PHM 2020, FER 2023 = security nueva). Ferrovial modelada como Security A/B.
  - El build sigue PROVISIONAL (ancla transcrita): no elegible para validación final.
  - `pitquant cohort-readiness`: cohortes de identidad 190/190; cohortes completas 0 (sin
    precios, fundamentales del universo ni corporate actions).
- **CNMV (Enagás 2017S1–2019S1):** 5 informes, ligados al EMISOR (CIF). La cadena de extremo a
  extremo está en `docs/REAL_DATA_SPANISH_IDENTITY_DEMO.md`.
- **Market data:** sin datos reales (`BLOCKED_BY_CREDENTIAL`). Las claves irían en
  `PITQUANT_SHARADAR_API_KEY`, `PITQUANT_EODHD_API_KEY` y `PITQUANT_ALPHAVANTAGE_API_KEY`.
- **GitHub:** `jpaneq/pitquant` (PRIVADO).
- **User-Agent SEC:** no se persiste; hay que exportar `PITQUANT_SEC_USER_AGENT`.

Informes generados desde la base (nunca a mano): `docs/ISSUER_SECURITY_CHANGES.md`,
`docs/IDENTITY_BLOCKERS.md` (qué security bloquea qué fecha y qué evidencia falta) y
`docs/ADAPTER_FIELD_EVIDENCE.md`. `FEATURE_ENGINE_READY` es derivado de `data-readiness` y hoy
es `false`: no empezar Feature Engine hasta READY con datos reales.

## Iteración 4 (2026-10-02): datos reales → corporate actions → total return (ADR-0023)
- Informe generado: `docs/REAL_MARKET_DATA_US.md` (`scripts/gen_real_market_report.py`); ingesta:
  `scripts/ingest_real_market_ca.py` (idempotente; Alpha Vantage sólo con clave).
- Real: AAPL split 4:1 (Apple IR, vía Wayback: la web da 403), dividendos Enagás 2016-06-30+ (web IR),
  MSFT especial 2004 (IR), 4 sesiones ENG del boletín BME, ventanas EODHD `demo` (QA) de AAPL/MSFT.
- Total Return validado en 6 ventanas reales contra cálculo independiente. Sin ex-date publicado
  (Apple, Enagás ≤2015) la ventana se rechaza, no se calcula.
- `FEATURE_RESEARCH_READY=false`: falta histórico de precios 2011+ aceptado (D-05).

## Micro-iteración Tiingo (2026-10-02, ADR-0024)
- `TiingoEODMarketDataProvider` (token sólo en cabecera, presupuesto de cupo), comparador
  vendor-vs-oficial (`VENDOR_DISAGREEMENT`), cobertura por `supported_tickers.zip`, criterios D-05.
- CUSIP oficial de AAPL y MSFT (Schedule 13G 2011–2024); ISIN ya no es obligatorio.
- `docs/TIINGO_SP500_COVERAGE.md` (generado por `scripts/tiingo_evaluate.py`): sin clave y sin universo
  S&P histórico → `TIINGO_D05_CANDIDATE=false`, `FEATURE_RESEARCH_READY=false`.

## D-02 candidato (2026-10-02, ADR-0025)
- Evidencia de membresía S&P 500 desde comunicados de S&P (tier 1 press.spglobal.com, tier 2 PRNewswire
  vía Wayback); CSV comunitario sólo descubre. `pitquant sp500-evidence`; informe generado
  `docs/SP500_MEMBERSHIP_EVIDENCE.md` (`scripts/ingest_sp500_evidence.py`, `scripts/gen_sp500_evidence_report.py`).
- `CURRENT_ANCHOR_BLOCKED` (S&P DJI 403): `SP500_MEMBERSHIP_CANONICAL_READY=false`.

## Iteración 6 (2026-10-02, ADR-0026/27/28)
- Ancla S&P 500 SPY+IVV `MULTI_SOURCE_CONFIRMED` (2026-10-01); D-02 desde comunicados de S&P: 171/558 eventos
  confirmados, `D02_RESEARCH_READY=false` (387 eventos sin confirmar rompen la cadena; 1 cohorte demostrada).
- Feature Engine V0 (51 features RAW, PIT), Label Engine 6M/12M, `explain-feature`, Developer UI `/dev/`,
  `cohort-readiness --universe SP500`, flags de readiness separados (`research_readiness.py`).
- Tiingo sigue `BLOCKED_BY_CREDENTIAL`: sin clave no hay precios US, cohortes completas ni baseline.
- Holdout NO tocado: los features rechazan fechas 2022-10-01 → 2025-09-30.

## Analyzer (2026-10-02, ADR-0029)
- Producto: `make frontend-ci && make analyzer` → http://127.0.0.1:8000 (React 19 + TS estricto + Vite + Tailwind 4 +
  TanStack + Lightweight Charts). Backend: `src/pitquant/analyzer/` (`technical_v1`, `fundamental_v1`, `valuation_v1`,
  `sr_v1`, `analysis_v0`, `trade_plan_v0`, `service`, `search`) y `api/analyzer.py`. **Una sola implementación**: los
  motores reciben `decision_at` y reutilizan `features.v0`; el frontend no calcula finanzas.
- Estado y bloqueos exactos: `docs/PRODUCT_ANALYZER_STATUS.md`. Mapa de reutilización: `docs/ANALYZER_REUSE_MAP.md`.
- Datos: AAPL/MSFT/VTI vía token público `demo` de EODHD (`scripts/ingest_analyzer_demo_data.py`); KO sólo SEC
  (FUNDAMENTAL_ONLY). Sin `PITQUANT_TIINGO_API_KEY` → banner `DATA SOURCE NOT CONFIGURED`. Predicción siempre
  `NOT_YET_VALIDATED`; trade plan `RULE_BASED_NOT_BACKTEST_VALIDATED`.
- `PITContext.market_actions` colapsa eventos equivalentes por tier (`market/ca_resolve.py`); `FEATURE_VERSION=v0.2`.

## Pendiente (por orden)
1. **Cohortes completas:** al menos un flujo real de precios y de corporate actions, y
   fundamentales de los miembros (CNMV: más emisores); después, la primera cohorte
   `FIRST_CANONICAL_COHORT`.
2. **Identidad:** fechas oficiales de inicio de contratación para POP 2013, ITX 2014, BKIA 2017 y
   AENA 2025 (hoy fecha de emisión ANCV); vínculo de emisor BKIA 2013.
3. **Con claves:**
   - contract tests y suite D-05 sobre Sharadar y EODHD reales;
   - semánticas `UNVERIFIED` (base del dividendo en Sharadar, dirección de `tickerchange`,
     fecha SP500);
   - cruce de SHARADAR/SP500 con anuncios S&P DJI → `CANONICAL_CANDIDATE`.
4. **Capa oficial BME/CNMV de corporate actions españolas:** derechos, scrip, OPA, fusiones.
5. **CNMV:** ESEF anual y más emisores (CIF de cada miembro IBEX vía consulta ANCV por NIF).
6. **Readiness READY con precios reales.** Sólo después: Feature Engine.

## Limitaciones conocidas

- Identidad ≠ membership (ADR-0017/0020): el build IBEX sigue en espacio de códigos
  (`IDENTITY_UNRESOLVED`). La identidad viene de los segmentos ANCV, y `backtest_universe()`
  falla cerrado por fecha si un solo miembro no está probado. El build es PROVISIONAL
  (ancla transcrita), así que no es elegible para validación final ni para el holdout.
- `register_event_securities` cierra el ticker de otra emisión si se reasigna (aviso DQ).
- Conceptos XBRL sin normalizar todavía.
- Los hechos SEC llevan `issuer_id` (ADR-0022); la security registrada por CIK es un ancla
  (`role=ISSUER_ANCHOR`). Las filas ingeridas antes de 0007 sólo tienen `security_id`.
- `security_identity_snapshots.issuer_id/security_id` quedan NULL (tabla append-only, ingerida
  antes de resolver): el vínculo vive en `membership_identity_segments` e `identifier_history`.
- Cobertura de corporate actions: COMPLETE sólo con traza de ingestión completada
  (`corporate_action_ingestions`); hoy no hay ninguna.
- Fechas de cambio de ISIN de POP 2013, ITX 2014, BKIA 2017 y AENA 2025 = emisión ANCV
  (administrativa), no inicio oficial de contratación.
- Emisores registrados desde SEC usan `exchange="XNYS"` como código de calendario aunque
  coticen en NASDAQ (mismo horario); su ticker queda vacío hasta una fuente fechada.

## Entorno del propietario

Mac Mini M4 (16 GB), servidor 24/7 autoalojado. Preferencia por soluciones locales y sin
dependencia de nube; despliegue con Docker Compose (PostgreSQL + API + Prefect).

## Research Lab (ADR-0030)
`RESEARCH_LAB_IMPLEMENTED=true` pero `RESEARCH_DATA_READY=false` hasta D-02/D-05. El holdout sigue
sellado: los folds y el Dataset Builder lo excluyen (también si la ventana de la etiqueta lo toca).
Etiquetas humanas del Analyzer nunca son feature ni target. `pitquant research-dry-run`,
`explain-analysis`, `explain-trade-plan`. E2E de navegador: `cd frontend && npx playwright test`.

## D-02 por ventanas (ADR-0031)
- `pitquant sp500-window-readiness --start 2017-10-01 --end 2022-09-30` (y `2014-10-01`): bloqueos dentro de la
  ventana vs. de CADENA (ancla única de 2026-10: los eventos de 2022-10→2026 también bloquean). Fichas de gap
  generadas: `docs/SP500_GAP_CARDS.md/.json`; informes: `scripts/gen_us_window_reports.py`.
- Evidencia oficial > CSV; `CONFLICT` inmaterial se resuelve con la fecha oficial. Reprocesar sin red:
  `python scripts/ingest_sp500_evidence.py --offline` (parser `sp500-evidence-3`).
- D-05 sin clave: `pitquant tiingo-backfill-plan`, `pitquant us-window-dryrun` (demanda CANDIDATA, no cobertura).
- `scripts/register_us_baseline_v0.py` registra `US_BASELINE_V0` BLOCKED. Con train_min 60m, 60 cohortes = 0 folds.

## D-02 por GRAFO DE ANCLAS (ADR-0032) — sustituye la ancla única
- Anclas históricas = composiciones de SPY presentadas a la SEC (NPORT-P Tier A, N-30D Tier B); **no** `OFFICIAL_SPDJI`. Ingesta:
  `PITQUANT_SEC_USER_AGENT=... python scripts/ingest_spy_anchors.py` (verifica cada accession contra EDGAR; falla cerrado). Informes:
  `python scripts/build_sp500_anchor_graph.py` → `docs/SP500_ANCHOR_GRAPH.md`, `docs/SP500_LOCAL_GAPS.md/.json`.
- `pitquant sp500-window-readiness --start 2017-10-01 --end 2022-09-30` usa el grafo (`--legacy` = ancla única; `--lenient` = QA).
- Un gap sólo bloquea SU segmento entre dos anclas. Nunca se carga un ancla posterior a 2022-09-30 (holdout). Las anclas son dato de
  referencia: `features`, `analyzer`, `backtest`, `api` no pueden importarlas.

## Estándar mensual vs diario, 13F y sucesiones (ADR-0033)
- `D02_MONTHLY_RESEARCH_READY` es la puerta del Research Lab (decision_at mensuales); `D02_DAILY_CANONICAL_READY` el criterio estricto.
  `pitquant sp500-window-readiness --standard monthly|daily`. El CSV de discovery nunca bloquea por sí solo ni invalida evidencia primaria.
- Lista SEC 13(f): `python scripts/ingest_13f_lists.py` (PDF archivados); puente + seis sucesiones verificadas: `python scripts/apply_identity_bridge.py`;
  informes: `python scripts/build_sp500_anchor_graph.py` → `docs/SP500_ANCHOR_GRAPH.md`, `docs/US_IDENTITY_BRIDGE.md`, `docs/SP500_LOCAL_GAPS.md`.
- Un security_id nuevo (reorganización, nuevo CUSIP) NO es salida + entrada del índice: `security_succession` con `membership_continuity`.

## Simulation Lab V0 (ADR-0034)
Paper trading, SIN dinero real ni broker ni cambios de modelo. `/simulations` (UI y API), botón «Simulate trade» en el Analyzer. T0 inmutable;
outcomes/observaciones/post-mortems en tablas aparte. `AUTO_PAPER` desactivado. El Research Lab sólo lee `/research/simulation-evidence`.
D-02: `python scripts/apply_identity_events.py` (8-K verificados contra 13F). Estado (ADR-0035): 27/60 cohortes mensuales, racha 15, 21 blockers de membresía; paquete: `docs/D02_RESIDUAL_PACKAGE.md` (`scripts/gen_d02_residual_package.py`).

## Simulation Lab V1 (ADR-0036)
Event store append-only (`simulation_events`), `pitquant simulation-update` (idempotente) y `simulation-replay [--verify]`, política de salidas explícita (`TRACK_TARGETS_ONLY` por defecto), fills con `fill_method`, ambigüedad con escenarios, contrafactual del plan PITQuant, Insights, post-mortem de hechos. Docs: `docs/SIMULATION_LAB.md`. E2E: `frontend/e2e/simulation.spec.ts` (SYNSIM con barras futuras guionizadas en `tests/e2e/serve.py`).

## Simulation Lab: motores fijados (ADR-0037)
Cada simulación queda ligada a su `simulation_engine_version` (registry en `simulation/registry.py`; v1 congelado con test de digest). Sin migración silenciosa; versión no registrada ⇒ `ENGINE_VERSION_UNAVAILABLE`. Observaciones históricas PIT (`PERIODIC`) y `bars_to_entry`.

## Señales y rutina diaria de acciones (ADR-0038/0039/0040)
Contrato de predicción V1 (`prediction_snapshots`, NULL mientras `NOT_YET_VALIDATED`), Strategy Engine versionado (TRADE_PLAN_ONLY operativa; PREDICTION_ONLY/HYBRID deshabilitadas) y runs HISTORICAL (bloqueado por data gates)/FORWARD_PAPER/SYNTHETIC.
Analyzer: `GET /analyzer/{security}/signals` (repetición retrospectiva en memoria, holdout omitido, capas R y F) y `python -m pitquant.cli strategy-daily-test [--refresh]` (docs/EQUITY_SIGNALS_AND_DAILY_TESTS.md). No hay modelo entrenado: sklearn no está instalado y `US_FUNDAMENTALS_READY=false`.

Bitcoin (fusionado desde `feature/btc-engine-v0`): vertical independiente `src/pitquant/btc/` y `/bitcoin` (cotización en vivo Binance, vela diaria del modelo, seguimiento `evaluate_due`, simulaciones BTC). Las estadísticas de evidencia de acciones filtran `asset_type == EQUITY` y no sintéticas. Docs: `docs/BTC_LIVE_AND_FOLLOWUP.md`. Tras la fusión la base real está en la revisión `0021` (copia previa: `data/pitquant.pre0020.bak.db`).

Posiciones simuladas y revisión ampliar/mantener/vender por horizonte en meses (ADR-0041): `src/pitquant/positions/`, `api/positions.py`, panel «Mis compras simuladas» en acciones y BTC. Reglas, no predicción; pesos sin validar.

Rutina diaria de compras simuladas (ADR-0042): `python -m pitquant.cli routine-run [--refresh] [--print-report]`, `src/pitquant/positions/routine*.py`, página `/rutina`; informe de texto en `data/reports/`. IBEX y MSCI World sin precios hoy ⇒ `NO_DATA` (no se inventa).
