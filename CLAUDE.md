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
- Cada decisión arquitectónica relevante → ADR nuevo en `docs/adr/` (siguiente: 0022).
- Migraciones: `0001` (base), `0002` (identidad), `0003` (CNMV) y `0004` (emisor/security,
  snapshots e identidad, corporate actions normalizadas) fijadas; **todo cambio de esquema =
  revisión nueva**.
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
- **IBEX 35:**
  - 133 intervalos; 5 de las 7 filas sin leyenda probadas como cambio de código por ANCV.
  - Identidad 2011+: 59/68 intervalos MULTI_SOURCE_CONFIRMED (86,8 %); LOG y PUIG quedan
    PROVISIONAL (dos líneas con la misma etiqueta; sólo un documento oficial exacto desempata).
    Detalle en `docs/IBEX_COVERAGE_REPORT.md`.
  - Ninguna fecha 2011+ es backtestable todavía: MTS (ArcelorMittal, ISIN LU) no tiene
    identidad probada y el fallo es cerrado por fecha.
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

## Pendiente (por orden)
1. **Identidad IBEX 2011+:**
   - código BME ↔ ISIN oficial y fechado para MTS (LU), FER (NL desde 2023) y ABG.P (clase B);
   - fechas de cambio de ISIN de REE y GRF en 2016 (hecho relevante o aviso);
   - borde de PHM en 2020.
2. **Con claves:**
   - contract tests y suite D-05 sobre Sharadar y EODHD reales;
   - semánticas `UNVERIFIED` (base del dividendo en Sharadar, dirección de `tickerchange`,
     fecha SP500);
   - cruce de SHARADAR/SP500 con anuncios S&P DJI → `CANONICAL_CANDIDATE`.
3. **Capa oficial BME/CNMV de corporate actions españolas:** derechos, scrip, OPA, fusiones.
4. **CNMV:** ESEF anual y más emisores (CIF de cada miembro IBEX vía consulta ANCV por NIF).
5. **Readiness READY con precios reales.** Sólo después: Feature Engine.

## Limitaciones conocidas

- Identidad ≠ membership (ADR-0017/0020): el build IBEX sigue en espacio de códigos
  (`IDENTITY_UNRESOLVED`). La identidad viene de los segmentos ANCV, y `backtest_universe()`
  falla cerrado por fecha si un solo miembro no está probado. El build es PROVISIONAL
  (ancla transcrita), así que no es elegible para validación final ni para el holdout.
- `register_event_securities` cierra el ticker de otra emisión si se reasigna (aviso DQ).
- Conceptos XBRL sin normalizar todavía.
- Los hechos SEC siguen ligados a la security registrada por CIK (patrón que ADR-0020 eliminó
  para CNMV): migrarlos a `issuer_id` queda pendiente.
- `security_identity_snapshots.issuer_id/security_id` quedan NULL (tabla append-only, ingerida
  antes de resolver): el vínculo vive en `membership_identity_segments` e `identifier_history`.
- Cobertura de corporate actions: COMPLETE si hay una fuente aceptada, sin traza de ingestión
  por security todavía.
- Ferrovial (ES→NL) no está modelada como Security A/B: el ISIN ES deja de aparecer tras 12/2022
  y el NL no está probado.
- Emisores registrados desde SEC usan `exchange="XNYS"` como código de calendario aunque
  coticen en NASDAQ (mismo horario); su ticker queda vacío hasta una fuente fechada.

## Entorno del propietario

Mac Mini M4 (16 GB), servidor 24/7 autoalojado. Preferencia por soluciones locales y sin
dependencia de nube; despliegue con Docker Compose (PostgreSQL + API + Prefect).
