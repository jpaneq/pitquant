# ADR-0042 — Rutina diaria de compras simuladas, evaluación semanal e informe en texto

Estado: aceptada (2026-10-05). Migración `0023` (`daily_picks`, `daily_evaluations`, append-only). Complementa ADR-0041.

## Decisión
1. **Un valor por mercado y día** (IBEX, SP500, MSCI_WORLD) más BTC: rotación determinista por fecha entre los tickers configurados que tengan datos (≥250 barras). Las listas son orientativas, no composiciones oficiales (`data/daily_universe.json` o `PITQUANT_DAILY_UNIVERSE`). Un ticker sin resolver o sin precios se registra como `NO_DATA` con el motivo; nada se inventa. Idempotente por (día, mercado).
2. **Entrada** por horizonte (1, 3, 6, 12 meses): la misma regla del ADR-0041 sobre una posición nueva a precio de hoy; compra simulada sólo si la recomendación es AMPLIAR. **Objetivo** = entrada·(1+max(2 %, 0,5·σ·√(h/12))); **stop** = entrada − max(2·ATR14, 0,35·σ·√(h/12)·entrada). Sin volatilidad/ATR no se abre. Todos los parámetros son `UNVALIDATED_STRATEGY_PARAMETER` y se imprimen en el informe (`daily-routine-v0`).
3. **Evaluación semanal** (semana ISO) y final: primer contacto de objetivo o stop con las velas diarias POSTERIORES a la entrada (nada anterior); ambos el mismo día = `AMBIGUOUS_STOP` (cuenta como stop); hueco bajo el stop se llena a la apertura; fin de horizonte = `EXPIRED` al último cierre. Al cerrar se registra un evento CLOSE con fuente `ROUTINE_RULE`.
4. **Informe en texto plano** (`routine-run`, `GET /routine/report`, página «Rutina diaria»): parámetros, datos no accesibles, actividad, selectividad, abiertas, cerradas, resumen mercado×horizonte (sin tasas con N<10) y puntos a revisar orientativos. Sirve para reajustar parámetros; el backtest queda para más adelante.
5. Fixtures/E2E: la frescura se marca `SYNTHETIC_TEST_DATA`. Programación diaria: plantilla launchd, no instalada.
