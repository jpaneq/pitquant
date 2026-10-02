# ADR-0024 — Tiingo como candidato D-05 e identidad US sin ISIN obligatorio

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Amplía:** ADR-0021, ADR-0023 · **Migración:** `0008`

## Contexto
Primera fuente histórica real US a evaluar para D-05 (Tiingo Free: ~500 símbolos únicos/mes,
1.000 peticiones/día, 50/hora). Además, la identidad US exigía un ISIN fechado que ninguna fuente
oficial accesible aporta para AAPL/MSFT.

## Decisión
1. **`TiingoEODMarketDataProvider`** (`/tiingo/daily/<ticker>/prices`, `startDate`/`endDate`).
   El token va en la cabecera `Authorization` (nunca en la URL, así que no se archiva) y sólo de
   `PITQUANT_TIINGO_API_KEY` (`BLOCKED_BY_CREDENTIAL` si falta). La serie base es OHLCV RAW;
   `adj*` sólo QA (`vendor_adj_close`, `adjustment_report`).
2. `divCash` (fecha = ex-date según el proveedor) y `splitFactor` → corporate actions **tier VENDOR**,
   conocidas desde el cierre del ex-date; nunca promovidas a OFFICIAL.
3. **El evento oficial siempre manda** (`market/ca_compare.py`): `MATCH`, `MISSING_IN_VENDOR` o
   `VENDOR_DISAGREEMENT` (campo a campo, registrado en `data_quality_issues`). La diferencia no se
   explica salvo que los datos la demuestren (Microsoft 2004: 3,00 oficial vs 3,08 vendor, sin eventos
   separados → sin explicación).
4. **`TiingoBudget`**: se detiene ANTES de superar 50/hora, 1.000/día o 500 símbolos únicos/mes; reloj
   inyectado (los tests no duermen); estado local en `data/tiingo_budget.json`.
5. **Cobertura por descubrimiento** con el fichero público `supported_tickers.zip` (sin token ni cupo):
   `ACTIVE_COVERED / DELISTED_COVERED / PARTIAL_PERIOD / TICKER_RECYCLED_SUSPECT / MISSING`. Sin
   universo histórico S&P 500 (D-02) la tabla queda BLOCKED; no se inventa un universo.
6. **`TIINGO_D05_CANDIDATE`** = verdadero sólo si los 7 criterios están en PASS; UNKNOWN cuenta como no
   superado. Nunca implica CANONICAL.
7. **Identificadores con clase de evidencia** (`security_identifier_evidence`, append-only):
   `OFFICIAL | DERIVED | VENDOR | UNRESOLVED`. **ISIN ya no es obligatorio**: una security queda
   identificada si un identificador OFFICIAL no-ISIN (CUSIP de un Schedule 13G de la SEC) encadena
   observación a observación (≤ 400 días) sobre el periodo; más allá, `PARTIAL`. DERIVED (p. ej. un ISIN
   calculado desde el CUSIP) y VENDOR nunca cuentan. Si hay ISIN probado, el camino anterior no cambia.
8. CUSIP AAPL `037833100` y MSFT `594918104`: un Schedule 13G por año y emisor (2011–2024, 14 + 14
   filings), archivado (URL, SHA-256) y registrado sólo si el texto nombra emisor, «Common Stock» y el
   CUSIP. 2025+ usa el formato XML estructurado de la SEC y aún no se parsea.

## Límites
- La evidencia prueba el vínculo en la fecha de cada filing; la continuidad entre dos filings es la regla
  de los 400 días, no una prueba.
- Sin clave de Tiingo y sin universo S&P, 6 de 7 criterios están UNKNOWN: `TIINGO_D05_CANDIDATE=false`.
