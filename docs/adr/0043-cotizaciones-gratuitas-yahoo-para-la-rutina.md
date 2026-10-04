# ADR-0043 — Cotizaciones gratuitas (Yahoo chart) para la rutina diaria

Estado: aceptada (2026-10-05). Sin migración. Complementa ADR-0021/0042.

## Contexto
La rutina necesita precios diarios de muchos valores (IBEX, EE. UU.), sin clave ni intradía. El token público de EODHD sólo sirve AAPL/MSFT/VTI.

## Decisión
1. `YahooChartMarketDataProvider` (`market/providers/yahoo.py`): endpoint público NO oficial de Yahoo Finance, sin clave. **Sin SLA ni licencia de redistribución: uso personal/educativo para la rutina de simulación.** Nivel VENDOR; nunca fuente canónica de investigación (regla de oro intacta). Puede cambiar o limitarse en cualquier momento y cada fallo se informa.
2. **Serie base RAW:** Yahoo entrega OHLC ya ajustado por splits; se restaura multiplicando por los splits POSTERIORES a cada barra (AAPL 2020-08-28: 124,81 → 499,23) y se marca `imputed_fields`. Los dividendos (también ajustados) se restauran al pago real. El volumen anterior a un split se retiene (None): su ajuste no está verificado.
3. **Sólo sesiones completadas:** una barra cuya sesión no ha cerrado se descarta (nunca se persiste un precio intradía como barra final).
4. **Orden de fuentes** (`routine-run --refresh`): EODHD si hay `PITQUANT_EODHD_API_KEY`; si no, Yahoo. Un valor que ya tiene barras de OTRA fuente las conserva (no se mezclan fuentes). Ingesta incremental (últimas sesiones) e idempotente. El ticker se resuelve a su valor VIGENTE (un ticker reutilizado por otro valor no se confunde).
5. Cobertura: sufijo `.MC` (Madrid) y EE. UU.; otras bolsas fallan con aviso hasta mapear su calendario.
