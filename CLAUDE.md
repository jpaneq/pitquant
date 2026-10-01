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
- Cada decisión arquitectónica relevante → ADR nuevo en `docs/adr/` (siguiente: 0018).
- Migraciones: `0001` (base) y `0002` (identidad) fijadas; **todo cambio de esquema = revisión nueva**.

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

## Estado a 2026-10-01

Hecho (ver `docs/ROADMAP.md`, `docs/ANTI_LEAKAGE_TESTS.md`):
- Fase 0: arquitectura, 16 ADRs, esquema de 35 tablas, flujos PIT y backtest.
- Fase 1: Security Master (tickers reutilizados/cambios), calendarios XNYS/XMAD, motor
  PIT bitemporal, ajuste de precios as-of, total return, walk-forward purgado con embargo y
  label availability, snapshots con hash, ingestión idempotente, API, Docker, CI.
- D-01: `SECEdgarFundamentalProvider` (header, XBRL archivado, versiones inmutables,
  política de disponibilidad `conservative_session`, cobertura 2011+).
- D-02/D-03: universos por eventos; S&P DJI licenciado (canónico) y reconstrucción por
  anuncios (provisional); parser BME del histórico IBEX 35 con resolución por avisos.
- `raw_source_archive` (SHA-256), holdout sellado, CI con job `postgres` estricto,
  `audit/reconstruction.py` (criterio de terminación demostrado con fixtures).
- Tests: 108 en SQLite + 12 PostgreSQL (pasados localmente contra PG 16.2 en modo
  estricto; **no verificados hasta que el job `postgres` de CI esté en verde**).

**Nada se ha ejecutado aún contra SEC, S&P DJI ni BME reales**: el entorno anterior no
tenía red hacia esos dominios. Todo lo D-01…D-03 está probado sólo con fixtures.

## Pendiente (por orden)

1. **Subir a GitHub y conseguir CI en verde**, en especial el job `postgres`.
2. **D-01 real:** fijar `PITQUANT_SEC_USER_AGENT` (con e-mail de contacto) y ejecutar
   `ingest_sec_company` sobre algunos CIK reales; revisar `data_quality_issues`
   (sobre todo `acceptance_mismatch` y `companyfacts_xbrl_mismatch`). Escribir el job que
   recorra el universo.
3. **D-03 real:** descargar el PDF oficial «Composición histórica – IBEX 35» y los avisos
   BME; calibrar `BMELayoutCalibration` siguiendo `docs/BME_PARSER.md`; cargar y validar
   (35 miembros por fecha, cada TICKER_CHANGE cruzado con su aviso). Escribir el parser de
   avisos (hoy `BMEAviso` se construye a mano).
4. **D-02 real:** obtener el histórico licenciado de S&P DJI y escribir el adaptador a su
   formato real (hoy se acepta el formato normalizado documentado en `spdji.py`). Hasta
   entonces, cualquier resultado sobre S&P 500 es `PROVISIONAL_RESEARCH_SOURCE`.
5. Demostrar el **criterio de terminación con datos reales** (los 7 puntos de
   `audit/reconstruction.py`) para varias fechas T. No avanzar a scoring antes.
6. **D-05** (precios, dividendos, corporate actions, delisting returns EE. UU. y España) y
   **D-04** (fundamentales PIT del IBEX): decidir proveedor según requisitos de
   `docs/PENDING_DECISIONS.md`; tests de aceptación con casos conocidos.
7. Fase 2 completa: stock-for-stock M&A, spin-offs, derechos y scrip, FX, almacén
   Parquet/DuckDB, benchmarks total return.
8. Después: Feature Engine (normalización de conceptos XBRL, técnico, régimen) → baseline
   scoring + calibración (fase 5) → backtest de panel (fase 7) → analytics/dashboard
   (sin holdout) → challengers ML → forward paper test.

## Limitaciones conocidas

- Identidad ≠ membership (ADR-0017): S&P provisional e IBEX sin ISIN producen intervalos
  `IDENTITY_UNRESOLVED`; `backtest_universe()` falla cerrado y esos builds no son elegibles
  para validación final/holdout. El IBEX necesita ISIN oficiales por miembro y fecha.
- `register_event_securities` cierra el ticker de otra emisión si se reasigna (aviso DQ).
- Conceptos XBRL sin normalizar todavía.

## Entorno del propietario

Mac Mini M4 (16 GB), servidor 24/7 autoalojado. Preferencia por soluciones locales y sin
dependencia de nube; despliegue con Docker Compose (PostgreSQL + API + Prefect).
