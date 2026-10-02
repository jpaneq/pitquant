# Trade Plan Engine V0 (`trade-plan-v0.1`)

**Etiqueta permanente en API y UI: `RULE_BASED · NOT YET BACKTEST VALIDATED`** (`validation_status = RULE_BASED_NOT_BACKTEST_VALIDATED`). No es una recomendación ni una previsión.

## Entradas
Último cierre ajustado a splits, ATR14, estado de tendencia, zonas de soporte/resistencia V1, SMA/EMA, resistencias superadas. **Los fundamentales no intervienen en la geometría.**

## Contexto
Sólo se ofrecen setups **largos** y no con tendencia `DOWNTREND`/`STRONG_DOWNTREND` ni sin contexto (`NO_VALID_SETUP` con motivo).

## Setups
- **PULLBACK**: soporte más fuerte a ≤ 4 ATR bajo el precio; zona de entrada = [soporte.lower, soporte.upper + 0,25·ATR]; *confluencia* si SMA/EMA caen a ≤ 0,75·ATR del punto medio.
- **BREAKOUT_RETEST**: resistencia superada con **cierre completado** > `upper + 0,25·ATR14` (nunca vela incompleta ni intradía) dentro de las últimas 30 sesiones y precio a ≤ 2 ATR de la zona; zona de entrada = la zona superada.
- Sin estructura válida → `NO_VALID_SETUP`.

## Invalidación, stop y objetivos
- Invalidación = `zone.lower`. **Stop = `zone.lower − 0,5·ATR14`** (idéntico para todos los perfiles; nunca un % fijo). Se muestran distancia absoluta, % y en ATR.
- `R = entrada − stop`. Objetivos: **objetivo estructural** (siguiente resistencia por encima) y **1,5R / 2R / 3R**, etiquetados `SCENARIO TARGET` (no previsiones).

## Perfiles (sólo cambia la entrada)
Aggressive: límite en `zone.upper` · Base: reclaim = cierre completado > `zone.upper + 0,25·ATR` · Conservative: reclaim + cierre > EMA20.

## Tamaño de posición (`GET /analyzer/{sec}/position-size`)
`risk_amount = capital·risk%`; `shares = floor(risk_amount / |entrada − stop|)`; sin apalancamiento (se recorta a capital/entrada) y entradas inválidas rechazadas. Cálculo en backend.

## Límites
No validado con backtest; no considera comisiones, gaps, liquidez ni correlaciones; no hay SL/TP automáticos ni conexión con brokers.
