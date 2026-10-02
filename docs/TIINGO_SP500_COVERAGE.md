# Tiingo Free como candidato D-05 (cobertura S&P 500)

> Generado por `scripts/tiingo_evaluate.py` (ADR-0024). Evaluación, **no** fuente canónica.

## Resumen

```
total_unique_securities   = n/a (BLOCKED: no historical S&P 500 universe)
resolved                 = n/a
price_history_available  = n/a
missing                  = n/a
delisted_resolved        = n/a
delisted_missing         = n/a
ticker_recycled_cases    = n/a
coverage_percentage      = n/a
```

**BLOCKED**: la base no contiene ninguna membresía histórica del S&P 500 (D-02: el fichero S&P DJI
lo aporta el propietario; el candidato Sharadar SP500 está `BLOCKED_BY_CREDENTIAL`). No se ha
inventado un universo: sin él no se puede medir la cobertura de *former/delisted constituents*, que es
el test crítico. La herramienta (`coverage_rows`) está lista y testeada con estados
`ACTIVE_COVERED / DELISTED_COVERED / PARTIAL_PERIOD / TICKER_RECYCLED_SUSPECT / MISSING`.

## Filas disponibles (las dos únicas securities US reales; tickers actuales, no históricos)

| security_id | historical_ticker | period | tiingo_ticker | start_date | end_date | is_active | status | reason |
|---|---|---|---|---|---|---|---|---|
| cd8b8a8f | AAPL | 2011-01-03.. | AAPL | 1980-12-12 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| d224cb0b | MSFT | 2011-01-03.. | MSFT | 1986-03-13 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |

## Estadística del fichero público de Tiingo (todo el vendor, NO cobertura del S&P 500)

- Fichero archivado: sha256 `13bf390494c4412d21dc9fa899331d41258b0159e18df0ab91a8e070b6a7bfef` (5037474 bytes descomprimido).
- Tickers distintos: 106557; filas acciones en bolsas US: 16529; con `endDate` anterior a hoy (delistadas/inactivas): 8256.
- Tickers con más de una fila (reciclados/ambiguos): 2272.
- Delistadas por año de `endDate` (2011+): {2011: 75, 2012: 56, 2013: 143, 2014: 151, 2015: 299, 2016: 427, 2017: 612, 2018: 609, 2019: 550, 2020: 540, 2021: 884, 2022: 1001, 2023: 1167, 2024: 604, 2025: 434, 2026: 610}.

Estas cifras no prueban cobertura de antiguos miembros del S&P 500; sólo muestran que Tiingo lista
símbolos inactivos. Cada ticker de un miembro histórico habría que cruzarlo contra su periodo.

## Eventos del proveedor vs evidencia oficial

| fuente | security | evento oficial | estado | diferencias | info |
|---|---|---|---|---|---|
| EODHD demo | AAPL | SPLIT 2020-08-31 | MATCH | — | — |
| EODHD demo | MSFT | SPECIAL_DIVIDEND 2004-11-15 | VENDOR_DISAGREEMENT | cash_amount: official 3.0 vs vendor 3.08; announcement_date: official 2004-07-20 vs vendor 2004-07-21 | kind: official SPECIAL_DIVIDEND vs vendor CASH_DIVIDEND |

El evento oficial manda siempre. La diferencia de Microsoft 2004 queda registrada como `VENDOR_DISAGREEMENT`
(`data_quality_issues`) **sin explicación**: no hay eventos separados que permitan demostrar que 3.08 = 3.00 + 0.08.

## Tiingo real (AAPL, MSFT desde 2011-01-01)

**BLOCKED_BY_CREDENTIAL**: `PITQUANT_TIINGO_API_KEY` no está definida; no se ha hecho ninguna llamada
con token (cupo gratuito intacto). Adaptador, parser, presupuesto de cupo y comparadores testeados con
payloads sintéticos en el formato documentado.

## Criterios D-05

**TIINGO_D05_CANDIDATE = false** (nunca implica CANONICAL)

| criterio | resultado | detalle |
|---|---|---|
| 1 history 2011+ | UNKNOWN | no real Tiingo series ingested (no key) |
| 2 raw OHLCV consistent | UNKNOWN | no real series |
| 3 sessions aligned | UNKNOWN | no real series |
| 4 corporate actions vs ground truth | UNKNOWN | no comparison available |
| 5 identity/ticker mapping reproducible | UNKNOWN | AAPL/MSFT identified (CIK + OFFICIAL CUSIP) but historical ticker->security mapping needs the S&P universe (D-02) |
| 6 former/delisted coverage | UNKNOWN | no historical S&P universe (D-02) |
| 7 raw provenance complete | UNKNOWN | archived raw responses with SHA-256, token not archived |
