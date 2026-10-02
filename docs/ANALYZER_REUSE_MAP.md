# Analyzer — mapa de reutilización

Inspección breve del repositorio (HEAD de partida `f68c92b`) para integrar el Analyzer **encima** de lo que ya existía.

| component | existing_module_or_class | existing_status | reused_as_is | needs_extension | new_work_required | notes |
|---|---|---|---|---|---|---|
| API | `pitquant.api.app.create_app` (FastAPI) | operativo | ✔ | routers añadidos | `api/analyzer.py`, SPA estático | mismo `session_factory` |
| Persistencia / migraciones | SQLAlchemy + Alembic (0001–0010) | operativo | ✔ | — | migración 0011 `security_profiles` | append-only con trigger PG |
| Security Master / identidad | `SecurityMaster`, `Issuer`, `IdentifierHistory`, `SecurityIdentifierEvidence` | operativo | ✔ | — | `SecurityProfile` (nombre/ticker actual/SIC) | ticker actual ≠ identidad fechada |
| PIT | `PITContext.raw_bars`, `market_actions`, `PITGuard`, `available_at` | operativo | ✔ | `market_actions` colapsa eventos equivalentes por tier | `market/ca_resolve.py` | un evento económico = una acción |
| Calendarios | `MarketCalendar` | operativo | ✔ | — | — | sesiones completadas, `last_closed_session` |
| Market data | adapters EODHD/Tiingo/AV/Sharadar, `store_batch`, `Price` | operativo | ✔ | — | `scripts/ingest_analyzer_demo_data.py` (demo público EODHD) | sin clave de Tiingo: `BLOCKED_BY_CREDENTIAL` |
| Corporate actions | `CorporateAction`, `CorporateActionEvent`, tiers | operativo | ✔ | resolución por tier | — | oficial > vendor |
| Total Return | `market.total_return`, `features.v0.series.build_series` | validado en datos reales | ✔ (misma serie) | — | — | momentum/riesgo usan el mismo índice TR |
| Técnicos | `features.v0.technical` (SMA/RSI/ATR/vol/mom) | motor V0 | ✔ (momentum, vol, beta, relativos) | — | `analyzer/indicators.py` (MACD, ADX, Bollinger, EMA/RSI/ATR por serie), `technical_v1.py` | misma fórmula para research y producto |
| Fundamentales SEC | `features.v0.fundamentals` (TTM, YTD, resolución de tags) + hechos normalizados | operativo | ✔ | parámetro `tags` | `analyzer/fundamental_v1.py` (CAGR, balance, capital allocation, series históricas) | sin nueva ingestión SEC |
| Valoración | `features.v0.engine._valuation` | V0 | parcial | — | `analyzer/valuation_v1.py` (EV, historia propia 5Y) | |
| Feature Engine / snapshots | `features.v0.engine`, `feature_snapshots` | operativo | ✔ | `shares_growth_yoy` alineado a splits → `v0.2` | — | |
| Labels | `backtest/targets.py` | operativo | ✔ | — | — | no se usa en el Analyzer |
| Elegibilidad | `analyzer/eligibility.py` (`SUPPORTED_SECURITY`) | estricta | ✔ | — | `AnalyzerService.eligibility` (FULL/PARTIAL/TECHNICAL_ONLY/FUNDAMENTAL_ONLY/INSUFFICIENT) | `ANALYZER_ELIGIBLE ≠ BACKTEST_ELIGIBLE` |
| Cobertura / readiness | `coverage.py`, `research_readiness.py`, `/dev/status` | operativo | ✔ | — | pantalla Research Lab | |
| Modelo / registro | `ModelRow` (`role`), `ModelVersion` | existe | ✔ | — | `prediction` siempre `NOT_YET_VALIDATED` sin Champion | sin promoción automática |
| Holdout | `settings.validation.final_holdout` | sellado | ✔ | `as_of` en holdout → 403 | — | |
| Frontend | — | **no existía** | — | — | `frontend/` (React 19, TS strict, Vite, Tailwind 4, TanStack Query, Lightweight Charts) | |
| Soporte/resistencia, plan de trade, análisis | — | no existían | — | — | `sr_v1.py`, `trade_plan_v0.py`, `analysis_v0.py` | reglas deterministas |
