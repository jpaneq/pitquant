# ADR-0042 — Rutina diaria de compras simuladas, evaluación semanal e informe en texto

Estado: aceptada (2026-10-05). Migración `0023` (`daily_picks`, `daily_evaluations`, append-only). Complementa ADR-0041.

## Decisión
1. **Un valor por mercado y día** (IBEX, SP500, MSCI_WORLD) más BTC: rotación determinista por fecha entre los tickers configurados que tengan datos (≥250 barras). Las listas son orientativas, no composiciones oficiales (`data/daily_universe.json` o `PITQUANT_DAILY_UNIVERSE`). Un ticker sin resolver o sin precios se registra como `NO_DATA` con el motivo; nada se inventa. Idempotente por (día, mercado).
2. **Entrada** por horizonte (1, 3, 6, 12 meses): la misma regla del ADR-0041 sobre una posición nueva a precio de hoy; compra simulada sólo si la recomendación es AMPLIAR. **Objetivo** = entrada·(1+max(2 %, 0,5·σ·√(h/12))); **stop** = entrada − max(2·ATR14, 0,35·σ·√(h/12)·entrada). Sin volatilidad/ATR no se abre. Todos los parámetros son `UNVALIDATED_STRATEGY_PARAMETER` y se imprimen en el informe (`daily-routine-v0`).
3. **Evaluación semanal** (semana ISO) y final: primer contacto de objetivo o stop con las velas diarias POSTERIORES a la entrada (nada anterior); ambos el mismo día = `AMBIGUOUS_STOP` (cuenta como stop); hueco bajo el stop se llena a la apertura; fin de horizonte = `EXPIRED` al último cierre. Al cerrar se registra un evento CLOSE con fuente `ROUTINE_RULE`.
4. **Informe en texto plano** (`routine-run`, `GET /routine/report`, página «Rutina diaria»): parámetros, datos no accesibles, actividad, selectividad, abiertas, cerradas, resumen mercado×horizonte (sin tasas con N<10) y puntos a revisar orientativos. Sirve para reajustar parámetros; el backtest queda para más adelante.
5. Fixtures/E2E: la frescura se marca `SYNTHETIC_TEST_DATA`. Programación diaria: plantilla launchd, no instalada.

## Adenda (2026-10-05)
6. **No comprar también es una decisión valorada.** Cada «no compra» guarda los niveles hipotéticos (entrada, objetivo, stop) y se evalúa como si se hubiera comprado (`daily_virtual_evaluations`, migración `0024`, sin abrir nunca una posición): acertó si el objetivo NO se habría cumplido; fue oportunidad perdida si sí. El informe (sección 8) cuenta compras y no compras por igual.
7. **Horario de cada bolsa:** el planificador (`routine-run`, sin `--ignore-hours`) sólo analiza los mercados cuya sesión está abierta en ese momento (IBEX en XMAD, SP500/MSCI en XNYS; BTC siempre). Un mercado cerrado no deja fila y se analiza en la siguiente ejecución dentro de sesión. El botón manual (`force=true`) ignora el horario.
8. **Cobertura de valores = fuente de datos, no algoritmo.** `routine-run --refresh` registra e ingiere TODO el universo configurado con una clave de proveedor (`PITQUANT_EODHD_API_KEY`; sufijo `.MC` IBEX, `.US` EE. UU., o `SIMBOLO.BOLSA`). Sin clave no se ingiere nada y los valores quedan `NO_PRICE_DATA`. El proveedor sólo mapea hoy calendarios de Madrid (`.MC`) y EE. UU. (`.US`).
9. **Precio al analizar:** con barras diarias el precio es el último cierre disponible (etiquetado `STALE`/`EOD`); un precio de sesión en vivo exige una fuente con cotización intradía.
