# ADR-0040 — Señales retrospectivas en el gráfico y rutina diaria de pruebas (acciones)

Estado: aceptada (2026-10-04). Sin migración. Complementa ADR-0029, 0034 y 0039.

## Contexto
El Analyzer de acciones sólo dibujaba el plan de HOY. Se pidió ver en el gráfico las entradas y salidas del algoritmo a lo largo del tiempo y una rutina que pruebe varias acciones cada día. No existe un modelo de retorno validado: no se inventa ninguna predicción.

## Decisiones
1. **Repetición retrospectiva** (`analyzer/replay.py`, `GET /analyzer/{security}/signals`). En fechas T muestreadas se reconstruye el Trade Plan V0 con SÓLO las barras conocidas en el cierre de T, se elige el perfil BASE con la misma regla que una simulación real (`_pitquant_plan`) y se juega sobre las barras posteriores con el motor registrado y congelado. **No escribe nada** (no son simulaciones: no llegan a Insights ni evidencia). Etiquetas: `RETROSPECTIVE_NOT_PIT` (precios descargados a posteriori), `RULE_BASED_NOT_BACKTEST_VALIDATED`, `COSTS_NOT_MODELED`, `ONE_TRADE_AT_A_TIME`; sin tasa de aciertos con <10 operaciones cerradas. Política: una operación a la vez; salidas 50 % en TP1 / 50 % en TP2 (PARTIAL_FRACTIONS).
2. **Holdout:** una decisión dentro de 2022-10-01→2025-09-30, o cuya ventana de operación lo alcance, se omite y se cuenta; nunca se dibuja.
3. **Base de precios:** los niveles del plan están en unidades de la fecha de decisión; los marcadores se convierten a la base del gráfico (ajustada por splits) con `split_factor`. Corrección asociada: `restated_bars` usa `anchor_date` (ex-date o primer día ajustado) en lugar de sólo `ex_date`; Apple IR no publica ex-date y sus splits no se reexpresaban en las simulaciones.
4. **Capas visualmente separadas:** R (retrospectivo, flechas) y F (pruebas paper reales: simulaciones no sintéticas, círculos).
5. **Rutina diaria** (`strategy/daily.py`, `pitquant strategy-daily-test`): un run `FORWARD_PAPER` de `TRADE_PLAN_DAILY_V0` sobre un universo congelado (por defecto todo valor con ≥250 barras, sin el benchmark). Cada llamada = un tick al reloj del servidor (idempotente por día, sin `--as-of`), abre simulaciones AUTO_PAPER por autoridad y añade un `StrategyRunResult`. `--refresh` actualiza barras con `scripts/ingest_analyzer_demo_data.py`. Cambiar el universo detiene el run y abre otro. La programación (launchd) no se instala automáticamente: plantilla en `deploy/launchd/`.
6. Alcance real de datos: el token público `demo` de EODHD sólo sirve AAPL/MSFT/VTI; más valores requieren `PITQUANT_EODHD_API_KEY` o `PITQUANT_TIINGO_API_KEY`. Precio: EOD, con insignia STALE si faltan sesiones.
