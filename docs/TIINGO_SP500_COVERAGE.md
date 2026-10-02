# Tiingo Free como candidato D-05 (cobertura S&P 500)

> Generado por `scripts/tiingo_evaluate.py` (ADR-0024). Evaluación, **no** fuente canónica.

## Resumen (nivel `supported_tickers.zip`: descubrimiento, NO cobertura de precios)

```
total_unique_securities   = 828   (tickers del universo candidato: 504 activos del ancla + 324 ex-miembros de los eventos)
resolved                 = 775
price_history_available  = 623   (rango del ticker cubre el periodo de pertenencia aproximado)
missing                  = 53
delisted_resolved        = 273
delisted_missing         = 51
ticker_recycled_cases    = 16
partial_period           = 136
coverage_percentage      = 75.2%
```

**Calidad del universo:** los periodos de pertenencia son aproximados (2011-01-03 → fecha del CSV de descubrimiento del último evento de salida); los ex-miembros proceden de eventos de descubrimiento y NO son membresía canónica (D02_RESEARCH_READY = false). Los tickers se cruzan con la lista pública de Tiingo; un ticker presente no garantiza datos de precios y un ticker reciclado puede pertenecer a otra empresa.

## Muestra determinista D-05 (semilla SHA-256 de `PITQUANT_D05_SAMPLE_V1`)

- 20 activas: GEN, UDR, CHTR, DOV, PH, SHW, KKR, EL, MO, IR, ISRG, NDAQ, NXPI, DLTR, CBRE, ERIE, TECH, DECK, J, PNR
- 20 ex-miembros: DO, MRO, KORS, FRC, CEPH, MKTX, DF, PEAK, MXIM, ATGE, R, POOL, CVH, ALTR, CBE, CPRI, SVU, GMCR, NLSN, IPG
- Fijas: AAPL, MSFT, SPY. Categoría «cambios de ticker/reorganizaciones»: vacía hasta resolver renombres con identidad (los renombres no son eventos de membresía).
- Símbolos únicos de la muestra: 43 de 500/mes del plan gratuito; la descarga NO se hace sin clave.

## Filas de la muestra a nivel de lista pública

| security_id | historical_ticker | period | tiingo_ticker | start_date | end_date | is_active | status | reason |
|---|---|---|---|---|---|---|---|---|
| CBRE | CBRE | 2011-01-03.. | CBRE | 2004-06-10 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| CHTR | CHTR | 2011-01-03.. | CHTR | 2010-01-05 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| DECK | DECK | 2011-01-03.. | DECK | 1993-10-15 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| DLTR | DLTR | 2011-01-03.. | DLTR | 1995-03-09 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| DOV | DOV | 2011-01-03.. | DOV | 1985-07-01 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| EL | EL | 2011-01-03.. | EL | 1995-11-17 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| ERIE | ERIE | 2011-01-03.. | ERIE | 1995-10-02 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| GEN | GEN | 2011-01-03.. | GEN | 1990-03-26 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| IR | IR | 2011-01-03.. | IR | 2017-05-12 | 2026-10-01 | True | PARTIAL_PERIOD | range overlaps but does not cover the period |
| ISRG | ISRG | 2011-01-03.. | ISRG | 2000-06-16 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| J | J | 2011-01-03.. | J | 1990-01-12 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| KKR | KKR | 2011-01-03.. | KKR | 2010-07-15 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| MO | MO | 2011-01-03.. | MO | 1970-01-02 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| NDAQ | NDAQ | 2011-01-03.. | NDAQ | 2002-07-01 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| NXPI | NXPI | 2011-01-03.. | NXPI | 2010-08-06 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| PH | PH | 2011-01-03.. | PH | 1985-07-01 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| PNR | PNR | 2011-01-03.. | PNR | 1973-05-03 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| SHW | SHW | 2011-01-03.. | SHW | 1985-07-01 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| TECH | TECH | 2011-01-03.. | TECH | 1992-12-09 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| UDR | UDR | 2011-01-03.. | UDR | 1990-03-07 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| ALTR | ALTR | 2011-01-03..2015-12-29 | ALTR | 1988-04-04 | 2017-10-31 | False | DELISTED_COVERED | range covers the whole period |
| ATGE | ATGE | 2011-01-03..2012-10-01 | None | None | None | None | MISSING | ticker absent from Tiingo supported list |
| CBE | CBE | 2011-01-03..2012-12-03 | None | None | None | None | MISSING | ticker absent from Tiingo supported list |
| CEPH | CEPH | 2011-01-03..2011-10-14 | None | None | None | None | MISSING | ticker absent from Tiingo supported list |
| CPRI | CPRI | 2011-01-03..2020-05-12 | CPRI | 2011-12-15 | 2026-10-01 | True | PARTIAL_PERIOD | range overlaps but does not cover the period |
| CVH | CVH | 2011-01-03..2013-05-09 | CVH | 2006-12-28 | 2013-10-17 | False | DELISTED_COVERED | range covers the whole period |
| DF | DF | 2011-01-03..2013-05-24 | None | None | None | None | MISSING | ticker absent from Tiingo supported list |
| DO | DO | 2011-01-03..2016-10-03 | DO | 1995-10-11 | 2022-02-03 | False | DELISTED_COVERED | range covers the whole period |
| FRC | FRC | 2011-01-03..2023-05-07 | None | None | None | None | MISSING | ticker absent from Tiingo supported list |
| GMCR | GMCR | 2011-01-03..2016-03-07 | GMCR | 2001-01-12 | 2016-03-04 | False | DELISTED_COVERED | range covers the whole period |
| IPG | IPG | 2011-01-03..2025-12-02 | IPG | 1987-11-05 | 2025-11-26 | False | DELISTED_COVERED | range covers the whole period |
| KORS | KORS | 2011-01-03..2018-09-19 | None | None | None | None | MISSING | ticker absent from Tiingo supported list |
| MKTX | MKTX | 2011-01-03..2025-09-23 | MKTX | 2004-11-05 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| MRO | MRO | 2011-01-03..2024-11-26 | MRO | 1970-01-02 | 2024-11-22 | False | DELISTED_COVERED | range covers the whole period |
| MXIM | MXIM | 2011-01-03..2021-08-30 | MXIM | 1990-03-26 | 2021-09-01 | False | DELISTED_COVERED | range covers the whole period |
| NLSN | NLSN | 2011-01-03..2022-10-12 | NLSN | 2011-01-27 | 2022-10-11 | False | PARTIAL_PERIOD | range overlaps but does not cover the period |
| PEAK | PEAK | 2011-01-03..2024-03-04 | PEAK | 2023-02-10 | 2023-02-13 | False | PARTIAL_PERIOD | range overlaps but does not cover the period |
| POOL | POOL | 2011-01-03..2026-06-20 | POOL | 1995-10-13 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| R | R | 2011-01-03..2017-06-19 | R | 1980-01-02 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| SVU | SVU | 2011-01-03..2012-05-01 | SVU | 1985-07-01 | 2018-12-14 | False | DELISTED_COVERED | range covers the whole period |
| cd8b8a8f | AAPL | 2011-01-03.. | AAPL | 1980-12-12 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |
| d224cb0b | MSFT | 2011-01-03.. | MSFT | 1986-03-13 | 2026-10-01 | True | ACTIVE_COVERED | range covers the whole period |

## Estadística del fichero público de Tiingo (todo el vendor, NO cobertura del S&P 500)

- Fichero archivado: sha256 `1cc44f655da6d5d0290a53c323e569f0907a7f5f61f0fe6f8e12fb86326d7b98` (5037441 bytes descomprimido).
- Tickers distintos: 106557; filas acciones en bolsas US: 16528; con `endDate` anterior a hoy (delistadas/inactivas): 8255.
- Tickers con más de una fila (reciclados/ambiguos): 2271.
- Delistadas por año de `endDate` (2011+): {2011: 75, 2012: 56, 2013: 143, 2014: 151, 2015: 299, 2016: 427, 2017: 612, 2018: 609, 2019: 550, 2020: 540, 2021: 884, 2022: 1001, 2023: 1167, 2024: 604, 2025: 433, 2026: 610}.

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
| 5 identity/ticker mapping reproducible | PASS | mapping run over the historical universe |
| 6 former/delisted coverage | FAIL | 0/0 former constituents covered (0%) |
| 7 raw provenance complete | UNKNOWN | archived raw responses with SHA-256, token not archived |

## Veredicto de la muestra (umbrales fijos: ≥ 98 % activas, ≥ 95 % ex-miembros, 100 % ground truth sin contradicción)

- `TIINGO_D05_CANDIDATE = false`
- active coverage None < 0.98
- former/delisted coverage None < 0.95
- ground-truth contradictions unexplained: None
- ticker mapping reproducibility not demonstrated
- provenance not demonstrated complete
