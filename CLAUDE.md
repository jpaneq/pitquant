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

## Estado a 2026-10-01 (tras la iteración «real data readiness»)

Verificado ejecutando:
- `make ci`: ruff, mypy strict, suite `pit` sin skips y suite completa.
- `make pg-local`: PostgreSQL 16.2 embebido vía `pgserver`, sin Docker, con la suite
  estricta y alembic upgrade/check/downgrade.

Hecho:
- Fases 0–1 y D-01…D-03 (ver `docs/ROADMAP.md`).
- ADR-0017: identidad ≠ membership, `backtest_universe` falla cerrado y puerta del holdout
  por linaje.
- ADR-0018: CNMV y política `DATE_ONLY`.
- `audit.explain` y `pitquant explain`.
- `pitquant data-readiness`.
- Suite de contrato D-05.
- Jobs SEC (`sec-stress-scan`, `sec-ingest`).

**No hay datos reales ingeridos.** Bloqueos externos:
- `PITQUANT_SEC_USER_AGENT` sin definir;
- aprobación para descargar los documentos BME y CNMV;
- decisión y licencia D-05;
- fichero licenciado S&P DJI.

El job `docker` y GitHub Actions no están verificados: no hay Docker ni remoto.

## Pendiente (por orden)

1. Subir a GitHub y ver la CI en verde, incluido el build Docker en 3.12.
2. **D-01 real:**
   - definir el User-Agent;
   - `pitquant sec-stress-scan` y `pitquant sec-ingest` sobre pocos CIK;
   - revisar `data_quality_issues` y `pitquant explain`;
   - después, el job sobre el universo.
3. **D-03 real:**
   - archivar el PDF BME y los avisos, y calibrar `BMELayoutCalibration`;
   - aportar ISIN oficiales (`identities`), sin los cuales el IBEX es `IDENTITY_UNRESOLVED`;
   - parser de avisos.
4. **D-04:** vertical slice CNMV (ADR-0018).
5. **D-02:** adaptador del fichero licenciado S&P DJI.
6. **D-05:**
   - verificar los casos `UNVERIFIED`;
   - ejecutar la suite contra los candidatos;
   - ADR de aceptación y `data_readiness.accepted_*`.
7. `pitquant data-readiness` READY con datos reales. Sólo después: Feature Engine y fases
   siguientes.

## Limitaciones conocidas

- Identidad ≠ membership (ADR-0017): S&P provisional e IBEX sin ISIN producen intervalos
  `IDENTITY_UNRESOLVED`; `backtest_universe()` falla cerrado y esos builds no son elegibles
  para validación final/holdout. El IBEX necesita ISIN oficiales por miembro y fecha.
- `register_event_securities` cierra el ticker de otra emisión si se reasigna (aviso DQ).
- Conceptos XBRL sin normalizar todavía.

## Entorno del propietario

Mac Mini M4 (16 GB), servidor 24/7 autoalojado. Preferencia por soluciones locales y sin
dependencia de nube; despliegue con Docker Compose (PostgreSQL + API + Prefect).
