# Technical Engine V1 (`technical-v1.0`, `sr-v1.0`)

**Implementado:** `src/pitquant/analyzer/{indicators,technical_v1,sr_v1,market}.py`. **Tests:** `tests/unit/test_analyzer_engines.py`, `tests/integration/test_analyzer_api.py`.

## Una sola implementación, `decision_at` obligatorio
`load_market(session, security_id, decision_at)` devuelve **sólo barras completadas conocidas en `decision_at`** (`PITContext.raw_bars`) y las corporate actions de mayor tier conocidas entonces. Las series se construyen con `features.v0.series.build_series` (el mismo constructor del Feature Engine). Ningún motor lee `now()`; la vista actual pasa `utc_now()` como parámetro. Una sesión en curso nunca entra (test `test_only_completed_bars_known_at_decision_at_are_used`).

## Series
- **`split_adjusted_ohlcv`**: OHLC ÷ factor acumulado de splits posteriores; volumen × factor. Sin ajuste por dividendos. Para velas, SMA/EMA/RSI/ATR/ADX/MACD/Bollinger y soportes.
- **Índice de Total Return interno**: precio RAW + splits + dividendos en efectivo con el motor de TR existente. Para momentum, volatilidad, drawdown, beta y fuerza relativa. El adjusted close del proveedor no se usa.

## Fórmulas
| métrica | definición |
|---|---|
| SMA n | media móvil simple, requiere n barras |
| EMA n | `ewm(span=n, adjust=False)`, NaN hasta n barras |
| RSI 14 | Wilder (semilla = media de las 14 primeras variaciones); 100 si no hay pérdidas |
| MACD | EMA12 − EMA26; señal = EMA9(MACD); hist = MACD − señal |
| ATR 14 | Wilder sobre True Range = max(H−L, \|H−C₋₁\|, \|L−C₋₁\|); `atr14_pct = ATR/close` |
| ADX 14 | Wilder (+DM/−DM/TR → DI → DX → ADX). Fuerza, no dirección |
| Bollinger 20,2 | SMA20 ± 2·std20 (desviación poblacional) |
| `close_vs_smaN` | close/SMA − 1; `sma50_vs_sma200`; pendientes `MA(t)/MA(t−n) − 1` (SMA200 n=20, EMA20 n=10) |
| retornos | producto de factores TR diarios de los últimos 21/63/126/252 días − 1; `mom_12_1` = TR[t−21]/TR[t−252] − 1 |
| `distance_52w_high` | último close ajustado / máximo de los últimos 252 closes ajustados − 1 (sin highs intradía) |
| volatilidad | std (ddof 1) de log-retornos TR × √252 (20/63/252); `downside_vol_63` = √(media(min(r,0)²))·√252 |
| max drawdown 252 | mínimo de TR/máximo acumulado − 1 sobre el índice TR |
| beta 252 | cov/var de log-retornos con el benchmark, ≥ 126 sesiones comunes |
| fuerza relativa | TR del valor − TR del benchmark (21/63/126/252 sesiones comunes) |
| volumen | media 20, ratio 20, z-score 20 (volumen ajustado a splits), `dollar_volume` = close RAW × volumen RAW |
| sobreextensión | (close − SMA20)/ATR, (close − SMA50)/ATR, close/SMA200 − 1 |

## Clasificación de tendencia (`trend-rules-v0.1`)
Cinco evidencias ±1: close>SMA20, close>SMA50, close>SMA200, SMA50>SMA200, SMA200 al alza. Score ≥4 `STRONG_UPTREND`, 2–3 `UPTREND`, −1..1 `NEUTRAL`, −3..−2 `DOWNTREND`, ≤−4 `STRONG_DOWNTREND`; con < 4 evidencias disponibles, `INSUFFICIENT_HISTORY`. Devuelve estado, score y evidencias. **No es una predicción.**

## Soportes y resistencias V1 (zonas)
- Pivote: `high[i] > max(high[i−5:i])` y `high[i] ≥ max(high[i+1:i+6])` (low simétrico). **Sólo existe tras 5 barras posteriores**: sin look-ahead (test).
- Cluster: mismo tipo, mientras `|nivel − centro| ≤ 0,75·ATR14`; zona = [mín, máx], ensanchada a ±0,1 ATR como mínimo.
- Fuerza = 100·(0,4·min(toques,5)/5 + 0,3·recencia + 0,3·min(rechazo_ATR/3,1)), recencia = media de 0,5^(edad/126), rechazo = movimiento medio en 5 barras. Pesos fijos, no optimizados.
- Salida: ≤ 3 soportes (centro bajo el cierre) y ≤ 3 resistencias; sólo zonas con ≥ 2 toques o rechazo ≥ 1 ATR; con `lower, upper, midpoint, touches, first/last_touch, strength, distance_pct, distance_atr, reasons`.
- `broken_resistances`: resistencia superada con un **cierre completado** > `upper + 0,25·ATR14` en las últimas 30 sesiones.

## Límites
Sin intradía (no se sintetiza desde diario); ADX/MACD/Bollinger/RSI son contexto, no señales; el benchmark preferido es SPY y, mientras no haya precios de SPY, VTI **etiquetado como proxy alternativo (ETF_PROXY)**.
