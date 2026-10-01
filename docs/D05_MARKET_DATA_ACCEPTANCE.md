# D-05 — Especificación de aceptación y matriz de proveedores (market data y corporate actions)

**Estado:** ABIERTA. Ningún proveedor está aceptado.
`data_readiness.accepted_market_data_sources` sigue vacío, así que US/ES market data y
corporate actions no pueden salir READY.

## Regla de aceptación
Un proveedor sólo se acepta si, envuelto en un adaptador `ContractCandidate`
(`pitquant/data/providers/contract.py`), cumple dos condiciones:
1. Pasa **todos** los casos de `contract_cases.py`.
2. **Todas** las expectativas de esos casos están `VERIFIED` contra un documento oficial.

Ejecución:

```bash
PITQUANT_D05_CANDIDATE=mi_modulo:factory pytest tests/contracts -rA
```

La aceptación se registra en un ADR nuevo y sólo entonces se añade el proveedor a
`config/default.yaml → data_readiness`.

## Requisitos (cada uno tiene una comprobación en la suite)

| Área | Requisito | Comprobación |
|---|---|---|
| Market data | OHLCV **sin ajustar**, zona horaria/mercado, histórico suficiente, correcciones versionadas | salto de precio en splits (`_check_split`); el versionado se revisa en el adaptador |
| Securities | Activas **y deslistadas**; historia de tickers; identificador persistente | `not found` ⇒ FAIL; `_check_ticker_change` sobre la misma clave |
| Corporate actions | Dividendos ordinarios y extraordinarios, splits, contra-splits, ampliaciones, derechos, spin-offs, fusiones en efectivo y en acciones, cambios de ticker, exclusiones, quiebras | un `_check_*` por categoría |
| Returns | Rentabilidad de precio, ajustada, total return y **delisting return** | valor terminal obligatorio en quiebras; contraprestación en adquisiciones |
| Licencia | Almacenamiento local, caché, uso histórico, backtesting, redistribución interna, límites de API, coste | revisión documental (abajo); no automatizable |

## Casos de contrato (14)

**VERIFIED** contra fuente oficial:
- FB→META, 2022-06-09 (nota de prensa de Meta IR).

**UNVERIFIED** (valores a confirmar en el documento oficial antes de contar para la
aceptación):
- AAPL 7×1 de 2014: el FAQ de Apple IR confirma el ratio pero no si el 9-jun es la fecha ex.
- AAPL 4×1 de 2020 (fecha ex).
- C 1×10 de 2011.
- Spin-off ABT→ABBV.
- Dividendo especial de MSFT de 2004.
- HNZ en efectivo.
- XTO en acciones.
- Quiebra de LEH.
- Resolución de Banco Popular.
- Derechos de SAN en 2017.
- Split de ITX en 2014.
- GAS→NTGY.
- Scrip de IBE.

Los meta-tests demuestran que la suite **rechaza** tres tipos de proveedor defectuoso:
- uno sin compañías muertas (sesgo de supervivencia);
- uno con precios ya ajustados;
- uno sin valor terminal ni continuidad de ticker.

## Matriz de proveedores (2026-10-01)

Leyenda: ✔ confirmado en documentación oficial del proveedor · ✖ no ofrece ·
`UNVERIFIED` no comprobado.

| Proveedor | Mercado | Deslistadas | Corporate actions | Delisting return / valor terminal | Licencia: almacenamiento local, backtesting, redistribución interna | Coste |
|---|---|---|---|---|---|---|
| **CRSP** (US Stock Databases) | US (NYSE, NYSE American, Arca, NASDAQ, Cboe BZX) | ✔ >36.000 valores activos e inactivos | ✔ corporate actions en ficheros diarios y mensuales | ✔ ficheros de delisting: fecha, código de motivo, precio, importe y return con y sin dividendos | UNVERIFIED (licencia académica/institucional) | UNVERIFIED |
| **Sharadar** (Nasdaq Data Link SEP/SF1) | US | ✔ «active and delisted», >25.000 valores en precios, historia desde 1998 | ✔ cambios de ticker, splits, dividendos en efectivo, spin-offs, fechas de alta y baja, motivo de baja, contraparte de adquisición | UNVERIFIED (hay motivo y contraparte; no consta un delisting return explícito) | UNVERIFIED | UNVERIFIED |
| **Norgate Data** | US (también AU/CA) | ✔ 25.222 deslistadas 1950–sep-2022; cobertura «essentially complete» desde finales de 1992 | Constituyentes históricos de índices (Platinum/Diamond); detalle de corporate actions UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| **EODHD** | US y **Madrid (MC)** | ✔ deslistadas; datos según año de baja: antes de 2018 sólo EOD; desde 2018 también fundamentales, dividendos y splits | Sólo splits y dividendos en endpoints; derechos, scrip y fusiones UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| BME Market Data / LSEG / Bloomberg / FactSet | ES (y global) | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |

Fuentes:
- [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases/)
- [CRSP Data Descriptions Guide](https://www.crsp.org/wp-content/uploads/guides/CRSP_US_Stock_&_Indexes_Database_Data_Descriptions_Guide.pdf)
- [Sharadar prices](https://sharadar.com/prices)
- [Nasdaq Data Link SEP](https://data.nasdaq.com/databases/SEP)
- [Norgate packages](https://norgatedata.com/stockmarketpackages.php)
- [Norgate FAQ](https://norgatedata.com/data-package-faq.php)
- [EODHD delisted data](https://eodhd.com/financial-apis/delisted-stock-companies-data-2)
- [EODHD exchanges](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours)

## Lectura provisional (no es la decisión)

**EE. UU.**
- CRSP es el estándar para delisting returns.
- Sharadar es la alternativa minorista mejor documentada en deslistadas y corporate actions.
- Ambos deben pasar la suite.

**España**
- Ningún candidato documenta todavía derechos, scrip y resolución bancaria.
- Es el punto débil: probablemente exija una fuente oficial BME o institucional. Es una
  decisión económica del propietario.

**Licencias**
- Todas las condiciones de licencia están `UNVERIFIED`. Hay que leer los contratos antes
  de pagar.
