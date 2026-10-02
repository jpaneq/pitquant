# SP500_CURRENT_ANCHOR

> Generado por `scripts/ingest_sp500_anchor.py` (ADR-0026). Procede de dos ETF, **no** de S&P DJI: nunca se etiqueta `OFFICIAL_SPDJI`.

## Estado: **MULTI_SOURCE_CONFIRMED**  (as_of 2026-10-01, nivel de clave `TICKER_NAME`)

| fuente | fichero | as_of | equities | excluidas | sha256 |
|---|---|---|---|---|---|
| SPY | holdings-daily-us-en-spy.xlsx | 2026-10-01 | 504 | 2 | `650faea1cec18f3ee3cfad10b0abcd443819711023854c25354b8c25f037e1a1` |
| IVV | latest-holdings.csv | 2026-09-30 | 503 | 5 | `ab722f6637e678015a3052085c371eb4f29bd65f1c15c3b17b090d1edb099fe8` |

- Equities reconciladas security a security: **503**; miembros del ancla: **504**.
- Los recuentos de SPY e IVV NO se exigen iguales: las líneas no-equity se eliminan por regla, no por cantidad.

## Líneas excluidas (por regla)

- SPY: `US DOLLAR` — no ticker (cash/other line)
- SPY: `2602335D TPG INC` — numeric placeholder ticker (CUSIP 436CVR021, weight 3.0E-6): not a listed equity
- IVV: `XTSLA BLK CSH FND TREASURY SL AGENCY` — asset class Money Market
- IVV: `USD USD CASH` — asset class Cash
- IVV: `SGAFT CASH COLLATERAL USD SGAFT` — asset class Cash Collateral and Margins
- IVV: `HOLX HOLOGIC INC` — equity line with no market (unlisted remnant of a delisted holding)
- IVV: `ESZ6 S&P500 EMINI DEC 26` — asset class Futures

## Reconciliación

- SPY as of 2026-10-01 (504 equities), IVV as of 2026-09-30 (503 equities); counts are not required to match
- IVV advanced 2026-09-30 -> 2026-10-01 with 1 confirmed event(s): 2026-10-01 +VYLR --
- IVV file has no CUSIP/ISIN: tickers are matched and every pair name-checked (BRK.B/BRK-B/BRK B normalised only because names agree)
- 2 pair(s) with different issuer names corroborated by ticker + weight (±20 %): GE ('GENERAL ELECTRIC' / 'GE AEROSPACE'); WAB ('WABTEC CORP' / 'WESTINGHOUSE AIR BRAKE TECHNOLOGIE')

- Eventos S&P confirmados aplicados entre ambas fechas: ['2026-10-01 +VYLR --']

## Diferencias

- ninguna

## Discrepancia con la descripción del propietario

El CSV público de iShares (`latest-holdings.csv`) NO trae CUSIP/ISIN/SEDOL (columnas: Ticker, Name, Sector, Asset Class, Market Value, Weight, Notional Value, Quantity, Price, Location, Exchange, Currency, FX Rate, Market Currency, Accrual Date). Por eso la reconciliación IVV↔SPY es por ticker normalizado + nombre (soporte), con CUSIP sólo en el lado SPY. Las variantes `.ajax` del mismo producto devuelven la página HTML, no un CSV con identificadores.

