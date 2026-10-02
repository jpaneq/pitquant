# PITQuant

Plataforma de análisis bursátil, scoring y backtesting **point-in-time**: cada cálculo usa
exclusivamente la información que un inversor podía conocer en el instante analizado.

> ⚠️ **Estado (2026-10-01):**
> - **Datos reales:** SEC (MSFT, AAPL), CNMV (Enagás) e IBEX 35 (documentos BME), todos
>   con `explain`. La identidad histórica del IBEX sigue sin resolver.
> - **Sin datos aún:** S&P DJI y market data (D-05 abierta).
> - **Señales:** no se generan BUY/HOLD/SELL. La API responde explícitamente que no hay
>   señal en lugar de inventarla.
> - **Datos versionados en el repositorio:** sólo sintéticos (`SYN*`) y fixtures. Los datos
>   reales viven en `data/`, que no se versiona.

## Qué hay

- **Security Master** con `security_id` permanente, historial de tickers (incl. reutilización y cambios) e ISIN.
- **Universo histórico** `universe(index, fecha)` sin sesgo de supervivencia y sin exponer salidas futuras.
- **Motor PIT** bitemporal (`available_at` / `ingested_at`, revisiones), `PITGuard` que hace fallar el pipeline ante cualquier dato futuro, y `PITContext` como única puerta de acceso a datos.
- **Calendarios reales** NYSE (XNYS) y BME (XMAD): festivos, cierres anticipados, DST; ejecución `next_session_open`; horizontes en meses de calendario.
- **Precios raw + ajuste as-of**, total return con dividendos, splits, fusiones en efectivo y quiebras.
- **Validación temporal**: walk-forward expanding/rolling, label availability, purging, embargo, holdout final bloqueado con registro de accesos.
- **Snapshots inmutables** con hash SHA-256 canónico; predicciones append-only (guard ORM + triggers PostgreSQL).
- **Ingestión idempotente** con lineage (`raw_records`) y motor de calidad de datos.
- **Archivo de fuentes crudas** direccionado por SHA-256 (`raw_source_archive`).
- **SEC EDGAR por accession**: header ACCEPTANCE-DATETIME, versiones de hechos inmutables, validación contra la instancia XBRL, política de disponibilidad conservadora.
- **Universos por eventos** (S&P DJI licenciado / reconstrucción provisional; BME + avisos), con `TICKER_CHANGE` explícito y builds reproducibles.
- **Emisor ≠ security** e **identidad por evidencia** (ADR-0020): snapshots semestrales ANCV de la CNMV desde 2010, `IdentityResolutionEngine` (EXACT / MULTI_SOURCE / PROVISIONAL / UNRESOLVED) y `backtest_universe` que falla cerrado por fecha.
- **Market data normalizada** (ADR-0021): adapters Sharadar (SEP, ACTIONS, TICKERS, SP500), EODHD y Alpha Vantage (sólo QA), modelo de corporate actions, motor de total return y Data Coverage Engine. Sin clave: `SOURCE_NOT_CONFIGURED`.
- **Holdout sellado**: sólo `evaluate_candidate_on_holdout`, registrado y una vez por modelo.
- **Reconstrucción auditable** en una fecha T con `DataVersion` fijado (`audit/reconstruction.py`).
- **API FastAPI**, Docker, CI (lint, mypy strict, tests PIT, migraciones, build).

## Uso rápido

```bash
pip install -e ".[dev]"
make ci                # lint + mypy + suite pit + suite completa + PostgreSQL embebido
make pg-local          # suite PostgreSQL estricta sin Docker (pip install -e ".[localpg]")
pitquant data-readiness   # ¿datos reales listos? (exit 1 si no READY)
make pit               # sólo la suite anti-leakage
python scripts/demo_time_machine.py      # reconstrucción PIT sobre datos sintéticos
make demo              # API en http://127.0.0.1:8000/docs con datos sintéticos
docker compose up -d   # PostgreSQL + API (migraciones Alembic al arrancar)
```

## Documentación

| Documento | Contenido |
|---|---|
| `docs/ARCHITECTURE.md` | Arquitectura técnica y modelo temporal |
| `docs/adr/` | 21 decisiones arquitectónicas |
| `docs/BME_PARSER.md` | Calibración del parser del histórico IBEX 35 |
| `docs/DATA_MODEL.md` | Esquema completo (42 tablas, generado desde el ORM) |
| `docs/IBEX_COVERAGE_REPORT.md` | Universo IBEX real e identidad 2011+ |
| `docs/IDENTITY_BLOCKERS.md`, `docs/ISSUER_SECURITY_CHANGES.md`, `docs/ADAPTER_FIELD_EVIDENCE.md` | Informes generados: bloqueos de identidad por security, cambios emisor/security y evidencia documental de los adapters |
| `docs/REAL_DATA_SPANISH_IDENTITY_DEMO.md` | Enagás de extremo a extremo (emisor → ISIN → security → ticker → membership → fundamentales) |
| `docs/PIT_AND_BACKTEST_FLOWS.md` | Flujo point-in-time y flujo de backtest |
| `docs/ANTI_LEAKAGE_TESTS.md` | Catálogo de tests y su estado |
| `docs/PENDING_DECISIONS.md` | Decisiones de datos: resueltas (D-01…D-03, proveedores, periodo V1, D-09) y abiertas |
| `docs/ROADMAP.md` | Fases y estado |

## Regla de oro

El objetivo no es construir el backtest que mejor explique el pasado, sino determinar si
la información disponible en cada momento contenía señal predictiva útil sobre resultados
posteriores. Prioridades: ausencia de sesgos > reproducibilidad > auditabilidad >
robustez estadística > interpretabilidad > rendimiento.
