# ADR-0029 — Analyzer (producto) y Research Lab en paralelo

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Migración:** `0011` · **Amplía:** ADR-0023/0027

## Decisión
1. **Dos carriles.** *Product*: el Analyzer actual (`/analyzer/{ticker}`), usable a diario sin esperar D-02 ni histórico S&P. *Research Lab*: PIT, backtests, modelos y auditoría. Se separan `ANALYZER_ELIGIBLE` (FULL / PARTIAL / TECHNICAL_ONLY / FUNDAMENTAL_ONLY / INSUFFICIENT, desde la disponibilidad real de datos) y `BACKTEST_ELIGIBLE`; la pertenencia a un índice no es entrada del Analyzer.
2. **Una sola implementación por métrica.** Los motores (`technical_v1`, `fundamental_v1`, `valuation_v1`, `sr_v1`, `analysis_v0`, `trade_plan_v0`) reciben `decision_at` y reutilizan `features.v0` (series, TTM, fórmulas). El Analyzer pasa `utc_now()`; el research pasa un instante histórico. Prohibido `now()` dentro de un motor. El backend es la autoridad: el frontend sólo renderiza.
3. **Una acción corporativa por evento económico** (`market/ca_resolve.py`, aplicado en `PITContext.market_actions`): oficial > vendor > fixture; splits con ratio contradictorio y dividendos de importe distinto permanecen visibles para QA (`VENDOR_DISAGREEMENT`) pero no se suman al cálculo.
4. **`shares_growth_yoy` alineado a splits** → `FEATURE_VERSION v0.2` (los snapshots `v0.1` son inmutables).
5. **Datos del Analyzer.** Sin clave de Tiingo, las barras proceden de la ingesta persistida (token público `demo` de EODHD: AAPL, MSFT y VTI), con insignia `STALE`/`EOD` honesta y el aviso `DATA SOURCE NOT CONFIGURED` + variable necesaria. No se inventa tiempo real. SPY es el benchmark preferido; mientras no haya sus precios se usa **VTI como proxy alternativo explícito** (`ETF_PROXY`). KO: sólo fundamentales SEC (`FUNDAMENTAL_ONLY`).
6. **Perfil descriptivo** (`security_profiles`, append-only): nombre, ticker *actual*, bolsa y SIC desde las `submissions` de la SEC archivadas; sector = división SIC, industria = descripción SIC. No es identidad fechada.
7. **Análisis, no predicción.** `AnalysisEngine V0` (reglas deterministas; sin pares, la valoración se compara con la **propia historia 5Y**); `TradePlanEngine V0` etiquetado `RULE_BASED_NOT_BACKTEST_VALIDATED`; `Prediction` siempre `NOT_YET_VALIDATED` sin Champion. Sin BUY/HOLD/SELL ni score global.
8. **Superficie API** (`api/analyzer.py`): `/search`, `/analyzer/{sec}/{summary,quote,chart,technicals,fundamentals,fundamental-history,valuation,analysis,trade-plan,position-size,prediction,filings,data-quality,report}`; paneles independientes (caché TTL de 60 s por (security, minuto)); `as_of` opcional (fechas del holdout → 403).
9. **Frontend** (`frontend/`): React 19, TypeScript estricto, Vite, Tailwind 4, TanStack Query/Table, Lightweight Charts 5 (atribución en `NOTICE` y barra lateral). Componentes al estilo shadcn/ui escritos a mano (no se usó su CLI).
10. **Holdout** intacto: ningún panel ni dato de ejemplo lo toca.

## Límites
Sin intradía ni cotización en vivo; sin pares/sectores actuales; sin EBITDA; bancos/aseguradoras/REIT sin perfil fundamental; el Research Lab es andamiaje (el detalle PIT vive en `/dev/`).
