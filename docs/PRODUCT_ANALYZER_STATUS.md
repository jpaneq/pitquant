# Analyzer — estado del producto (2026-10-02)

Arranque: `make frontend-ci && make analyzer` → **http://127.0.0.1:8000** (API + UI). Desarrollo: `uvicorn pitquant.api.main:app --port 8000` y `make frontend-dev` → http://127.0.0.1:5173. Base real local: `PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db`.

Datos reales usados (ningún valor está en el código): AAPL/MSFT/VTI barras EOD 1995→2026-10-01 vía el token público `demo` de EODHD (tier VENDOR/QA); fundamentales SEC EDGAR de AAPL, MSFT y KO; perfiles de las `submissions` de la SEC; corporate actions oficiales (Apple IR, Microsoft IR) por encima del vendor.

| Feature | Status | Source | Engine | UI | Tested with real data | Blocker |
|---|---|---|---|---|---|---|
| Búsqueda global (ticker, nombre, CUSIP, ISIN, fuzzy) | ✔ | Security Master + perfiles | `analyzer/search.py` | `GlobalSearch` | AAPL, apple, `037833100`, KO; `APPL` sugiere AAPL **sin** navegar | — |
| Cabecera / cotización | ✔ EOD | barras persistidas | `AnalyzerService.quote` | `SecurityHeader` | AAPL, MSFT | sin `PITQUANT_TIINGO_API_KEY` no hay referencia en vivo: insignia `STALE`/`EOD` + banner |
| Gráfico (velas, volumen, SMA/EMA, Bollinger, S/R, plan, RSI, MACD; 1M…MAX) | ✔ | EODHD demo | `technical_v1.chart_payload` | `MarketChart` (Lightweight Charts 5) | AAPL, MSFT | intradía no ingerido (1D/5D ausentes por diseño) |
| Técnicos (SMA/EMA/RSI/MACD/ATR/ADX/Bollinger, tendencia, momentum, 52w, riesgo, volumen) | ✔ | RAW + splits + TR interno | `technical_v1` | `TechnicalsCard`, `RiskCard`, `TechnicalDetail` | AAPL, MSFT | — |
| Fuerza relativa y beta | ✔ proxy | VTI (SPY no servido por el demo) | `technical_v1` | `TechnicalDetail` | AAPL, MSFT vs VTI `ETF_PROXY` | precios de SPY (Tiingo/EODHD con clave) |
| Soportes/resistencias V1 | ✔ | OHLC ajustado | `sr_v1` | gráfico + tabla | AAPL, MSFT | — |
| Fundamentales (TTM, márgenes, calidad, crecimiento, inversión, balance, capital allocation) | ✔ | SEC EDGAR | `fundamental_v1` | `FundamentalsCard` (+detalle) | AAPL (50/50 métricas), KO (45/50) | bancos/aseguradoras/REIT: «SPECIALIZED PROFILE NOT YET SUPPORTED» |
| Historia fundamental (trimestral/anual) | ✔ | SEC | `history_series` | `FundamentalHistory` | AAPL | — |
| Valoración (P/E, P/S, P/B, FCF yield, EV, historia propia 5Y) | ✔ | SEC + precio | `valuation_v1` | `ValuationCard` | AAPL (percentiles sobre 60 puntos), MSFT | comparación con pares: no disponible (sin universo actual) |
| Análisis V0 (8 etiquetas, positivos/riesgos) | ✔ | derivado | `analysis_v0` | `AnalysisSummary` | AAPL, MSFT, KO | etiquetas con reglas absolutas V0 (documentado) |
| Trade Plan V0 (pullback/breakout, stop = zona − 0,5 ATR, 1,5R/2R/3R, tamaño de posición) | ✔ `RULE_BASED_NOT_BACKTEST_VALIDATED` | estructura | `trade_plan_v0` | `TradePlanSection` + overlay | AAPL, MSFT (6 setups) | no validado con backtest |
| Predicción | **NOT_YET_VALIDATED** | — | `AnalyzerService.prediction` | `PredictionPanel` | contrato; ningún valor mostrado | requiere un Champion calibrado (Research Lab) |
| Filings (10-K/10-Q/8-K) | ✔ | SEC (`sec_filings`) | `AnalyzerService.filings` | `FilingsPanel` | AAPL | — |
| Data quality + proveedores | ✔ | todos | `AnalyzerService.data_quality` | `DataQualityDrawer`, `/status` | AAPL | — |
| Informe JSON + Markdown | ✔ | todos | `report`/`report_markdown` | `ReportButton` | AAPL (sin secretos) | PDF no implementado |
| Watchlist | ✔ V0 | API | — | `WatchlistPage` (TanStack Table, localStorage) | AAPL, MSFT, KO | persistencia sólo en el navegador |
| Research Lab (overview) | ✔ andamio | `/dev/status` | `research_readiness` | `ResearchPage` | holdout SEALED, gates | Backtests/Modelos/Universos/Auditoría: andamio sin datos |
| MSFT | ✔ FULL | | | | ✔ | |
| KO | `FUNDAMENTAL_ONLY` | SEC | | gráfico sustituido por aviso | ✔ | **sin precios**: el token demo de EODHD no sirve KO; con clave: `PITQUANT_EODHD_API_KEY` o `PITQUANT_TIINGO_API_KEY` + `python scripts/ingest_analyzer_demo_data.py` |

## Credenciales y comandos exactos
| variable | efecto |
|---|---|
| `PITQUANT_TIINGO_API_KEY` | cotización/EOD de Tiingo (`scripts/tiingo_evaluate.py`); quita el banner `DATA SOURCE NOT CONFIGURED` |
| `PITQUANT_EODHD_API_KEY` | `python scripts/ingest_analyzer_demo_data.py` usa la clave (cualquier ticker) en vez del token demo |
| `PITQUANT_SEC_USER_AGENT` | `python scripts/ingest_security_profiles.py` y `pitquant sec-ingest <CIK> --register-missing` para nuevos emisores |

## Latencias locales (SQLite, un proceso)
Primera petición de un valor: `summary` ≈ 0,9–1,2 s (calcula todos los motores); resto de paneles ≈ 10–25 ms (caché TTL 60 s por (security, minuto)); `chart` ≈ 24 ms. Sin N+1 detectado (los motores cargan hechos y barras una vez).

## Capturas (reales)
`docs/screenshots/analyzer_aapl_top.jpg`, `analyzer_aapl_fundamentals.jpg`, `analyzer_aapl_technical_tradeplan.jpg`, `analyzer_msft_top.jpg`, `analyzer_msft_tradeplan_macd.jpg`, `analyzer_msft_mobile.jpg`, `analyzer_ko_fundamental_only.jpg`.

## Tests
Frontend (vitest): `format`, `GlobalSearch` (APPL sugiere AAPL, sin navegación silenciosa), `PredictionPanel`, `Metric`, `ErrorBoundary`. Backend: `tests/unit/test_analyzer_engines.py` (indicadores, split, completed-bars, pivotes sin look-ahead, S/R, TTM/YTD, CAGR NOT_MEANINGFUL, capex, acciones vs splits, PE/PB nulos, FCF yield negativo, historia propia sin futuro, plan, tamaño de posición, colapso de CA, búsqueda), `tests/integration/test_analyzer_api.py` (contrato, aislamiento de paneles, holdout 403, secretos), `tests/realdata/test_analyzer_golden_path.py` (AAPL/MSFT/KO reales; split 2020 continuo en el gráfico). E2E de navegador: ejecutado a mano en el panel del navegador (búsqueda, ruta, gráfico con toggles, tarjetas, plan, KO), no en CI.
