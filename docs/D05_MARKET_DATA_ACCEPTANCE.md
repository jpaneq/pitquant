# D-05 — Especificación de aceptación y matriz de proveedores (market data y corporate actions)

> **Actualización 2026-10-01:** los proveedores están fijados por el propietario y se
> gestionan externamente: Sharadar SEP (EE. UU.), EODHD y la capa oficial BME/CNMV (España)
> y Alpha Vantage sólo para QA (ADR-0021). La matriz de costes y la consulta a BME de abajo
> son **históricas** y ya no se mantienen. Lo vigente son los casos de contrato y la suite,
> que se ejecutarán sobre datos reales cuando existan las claves.

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

## Arquitectura
`USMarketDataProvider` y `ESMarketDataProvider` son roles distintos (`providers/base.py`). Cada
uno se acepta por separado con los casos de su mercado. No se asume que un único proveedor
sirva para los dos.

## Casos de contrato (20; 11 VERIFIED: 9 con la fecha exacta + 2 sobre una fecha ancla declarada)
La evidencia (URL, SHA-256 y extracto de cada documento archivado) está en
`docs/d05_contract_evidence.json` (`scripts/verify_contract_cases.py`).

| Caso | Estado | Fuente oficial |
|---|---|---|
| AAPL split 7×1 (2014-06-09) | VERIFIED | Apple 8-K ex.99.1 (2014-04-23) |
| AAPL split 4×1 (2020-08-31) | VERIFIED | Apple 8-K ex.99.1 (2020-07-30) |
| AAPL dividendo ordinario 0,82 $ (fecha ancla = registro 2020-08-10; ex dentro de tolerancia) | VERIFIED (ancla) | Apple 8-K ex.99.1 (2020-07-30) |
| C contra-split 1×10 (2011-05-09) | VERIFIED | Citigroup 8-K ex.99.1 |
| ABT→ABBV spin-off 1:1 (fecha ancla = distribución 2013-01-01) | VERIFIED (ancla) | Abbott 8-K ex.99.1 |
| MSFT dividendo especial 3,00 $ (ex 2004-11-15) | VERIFIED | Microsoft 8-K (2004-11-15) |
| HNZ adquisición en efectivo 72,50 $ (última sesión 2013-06-07) | VERIFIED | Heinz 8-K ex.99.1 |
| XTO adquisición en acciones 0,7098 (2010-06-25) | VERIFIED | XTO 8-K |
| PEP cambio NYSE→Nasdaq (2017-12-20) | VERIFIED | PepsiCo 8-K (2017-12-08) |
| FB→META (2022-06-09) | VERIFIED | Meta IR |
| BKIA fusión en CABK 0,6845 (última sesión 2021-03-26) | VERIFIED | Anuncio de canje de CaixaBank |
| LEH quiebra (fecha de exclusión) | UNVERIFIED | El 8-K confirma el Chapter 11, no la fecha de exclusión |
| ITX split 5×1 (fecha ex) | UNVERIFIED | El hecho relevante CNMV confirma el ratio, no la fecha ex |
| POP resolución, SAN derechos y ampliación, GAS→NTGY, IBE scrip, ACS liberada, ABE OPA con exclusión | UNVERIFIED | Pendiente de documentos CNMV/BME fechados |

## Matriz comparativa (2026-10-01)
Leyenda: ✔ confirmado en la documentación oficial del proveedor · ✖ no ofrece ·
`UNVERIFIED` no comprobado.

| Proveedor | US | España | Deslistadas | OHLCV raw | Corporate actions | Identidad histórica | Licencia | Coste | Contract tests | Limitaciones |
|---|---|---|---|---|---|---|---|---|---|---|
| **Sharadar SEP** | ✔ | ✖ | ✔ «active and delisted» | ✔ «Close Price – Unadjusted» y ajustado | ✔ splits, dividendos, spin-offs, adquisiciones, motivos de baja, cambios de ticker | UNVERIFIED | «Personal Use License»; texto UNVERIFIED | Precios 99 $/año; paquete 299 $/año (5 años) o 69 $/mes (historia completa) | No ejecutado (requiere suscripción) | Historia desde dic-1997; delisting return explícito UNVERIFIED |
| **Norgate** | ✔ | ✖ | ✔ según la página de paquetes («delisted securities»); cifra de 25.222 y «complete since 1992»: extracto de búsqueda, UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED (calculadora dinámica) | No ejecutado | Acceso programático en macOS UNVERIFIED |
| **EODHD** | ✔ | ✔ (MC) | ✔, pero antes de 2018 sólo EOD | ✔ EOD | Sólo splits y dividendos; derechos, scrip, fusiones y OPAs UNVERIFIED | UNVERIFIED | Personal frente a comercial interno | Personal 19,99–99,99 €/mes (leído); comercial interno 3.990 €/año: extracto de búsqueda, UNVERIFIED | No ejecutado | Deslistadas españolas UNVERIFIED |
| **CRSP** (WRDS) | ✔ (referencia) | ✖ | extracto de búsqueda (>36.000 valores activos/inactivos), UNVERIFIED | UNVERIFIED | extracto de búsqueda (ficheros de delisting con código, precio y return), UNVERIFIED | UNVERIFIED | Institucional; personal UNVERIFIED | UNVERIFIED | No ejecutado | Acceso vía institución |
| **BME Market Data** | ✖ | ✔ fuente oficial | Maestro de Valores (1100): altas y bajas; profundidad UNVERIFIED | ✔ Precios y Volúmenes (2100) | ✔ Hechos Relevantes Back Office (1200): ampliaciones, dividendos, fusiones, escisiones | UNVERIFIED | Sólo usuario final, **sin redifusión** | Catálogo jul-2025: maestro renta variable ~1.050–3.500 €; precios ~93–933 €; hechos relevantes ~183–5.001 € (significado de las columnas UNVERIFIED) | No ejecutado | Formato e histórico pendientes de consulta |

Fuentes:
- [Sharadar prices](https://sharadar.com/prices)
- [Sharadar suscripción](https://sharadar.com/subscribe)
- [Norgate](https://norgatedata.com/stockmarketpackages.php)
- [EODHD pricing](https://eodhd.com/pricing)
- [EODHD comercial](https://eodhd.com/commercial-pricing)
- [CRSP](https://www.crsp.org/research/crsp-us-stock-databases/)
- [BME fin de día](https://www.bolsasymercados.es/en/bme-exchange/prices-and-markets/market-data-services/end-of-day-and-historical-services.html)
- [BME tarifas jul-2025](https://www.bolsasymercados.es/dam/descargas/servicios-de-datos/tarifas-julio-2025-informacion-fin-de-dia-es.pdf)

## Consulta preparada para BME Market Data (no enviada)
> Para uso interno y personal de backtesting (sin redifusión), solicitamos información sobre:
> 1. Profundidad histórica de: Maestro de Valores (1100) con altas, bajas y modificaciones;
>    Precios y Volúmenes (2100); Hechos Relevantes Back Office (1200).
> 2. Inclusión de valores excluidos y su motivo (OPA, fusión, resolución).
> 3. Tratamiento de derechos, ampliaciones liberadas / scrip, splits y contra-splits.
> 4. Formato de entrega y posibilidad de un histórico completo de una vez.
> 5. Condiciones de almacenamiento local indefinido y tarifa para un usuario final persona
>    física.

## Lectura provisional (no es la decisión)

**EE. UU.** Sharadar SEP cumple sobre el papel los requisitos de datos a coste bajo para uso
personal. Debe pasar los 11 casos verificados, y hay que leer su licencia personal.

**España**
- BME Market Data es la única fuente oficial que documenta corporate actions españolas.
  Tarifa de usuario final y profundidad por confirmar.
- EODHD no documenta derechos, scrip ni OPAs.

**Decisión: ABIERTA.**
