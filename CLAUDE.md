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
- Cada decisión arquitectónica relevante → ADR nuevo en `docs/adr/` (siguiente: 0029).
- Migraciones: `0001`…`0010` fijadas (`0010` anclas de índice SPY/IVV) (`0009` evidencia de membresía S&P 500) (`0008` evidencia de identificadores con clase OFFICIAL/DERIVED/VENDOR) (`0004` emisor/security y snapshots, `0005` evidencia
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
