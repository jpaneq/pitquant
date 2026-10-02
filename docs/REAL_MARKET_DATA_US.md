# Datos de mercado reales: AAPL, MSFT y ENG (iteración 4, ADR-0023)

> Generado por `scripts/gen_real_market_report.py` desde la base local. **No es histórico
> canónico**: son ventanas cortas de QA/prototipo. `FEATURE_RESEARCH_READY = false`.

## 1. Alpha Vantage `TIME_SERIES_DAILY`

**BLOCKED_BY_CREDENTIAL**: `PITQUANT_ALPHAVANTAGE_API_KEY` no está definida en este entorno; no se
ha hecho ninguna llamada real y no se ha inventado ningún dato. Adaptador, parser y validación
están testeados con payloads sintéticos y con fetch inyectado (`tests/unit/test_market_validation.py`);
la prueba real (`tests/real_api/`) se ejecuta sólo con clave. Con clave gratuita,
`outputsize=compact` = últimas 100 observaciones: sirve para probar la cadena, **no** para el
backfill 2011+.

## 2. Series de precios almacenadas (RAW, validación contra calendario)

| security | fuente | primer día | último día | barras | duplicados | fuera de orden | no-sesión | sesiones ausentes | valores imposibles |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | EODHD:eod | 2020-06-01 | 2020-12-31 | 150 | 0 | 0 | 0 | 0 | 0 |
| MSFT | EODHD:eod | 2004-10-01 | 2004-12-31 | 64 | 0 | 0 | 0 | 0 | 0 |
| ENG | BME:boletin-diario:2_38_0 | 2023-12-19 | 2024-07-02 | 4 | 0 | 0 | 0 | n/a (4 sesiones sueltas) | 0 |

Las series de EODHD (token público `demo`, sólo AAPL.US/MSFT.US) son ventanas dirigidas alrededor de los
eventos reales (QA, fuente única, no aceptada). ENG: cuatro sesiones sueltas del boletín oficial de BME
(sin `open`: el boletín no lo publica; nunca se imputa). «Sesiones ausentes» se mide dentro de cada
ventana, no es una laguna del histórico.

## 3. Archivo raw (URL sin claves, SHA-256)

| proveedor | identificador | sha256 | retrieved_at |
|---|---|---|---|
| APPLE_IR:dividend-history | http://web.archive.org/web/20260422063456id_/https://investor.apple.com/dividend-history/ | `4f315669af215437…` | 2026-10-02 09:40:34 |
| BME_BOLETIN_DIARIO | https://www.bolsasymercados.es/descargas/boletines/barcelona/2024/07/01/2_38_0_20240701.pdf | `2a1e47965e191dc6…` | 2026-10-02 09:03:47 |
| BME_BOLETIN_DIARIO | https://www.bolsasymercados.es/descargas/boletines/barcelona/2024/07/01/2_49_0_20240701.pdf | `e7c79857d872d7aa…` | 2026-10-02 09:03:47 |
| BME_BOLETIN_DIARIO | https://www.bolsasymercados.es/descargas/boletines/barcelona/2023/12/19/2_38_0_20231219.pdf | `e0c24006fccbc2fc…` | 2026-10-02 09:40:35 |
| BME_BOLETIN_DIARIO | https://www.bolsasymercados.es/descargas/boletines/barcelona/2023/12/20/2_38_0_20231220.pdf | `a6b4692526d9ccf6…` | 2026-10-02 09:40:37 |
| BME_BOLETIN_DIARIO | https://www.bolsasymercados.es/descargas/boletines/barcelona/2024/07/02/2_38_0_20240702.pdf | `c79c9091e6be587c…` | 2026-10-02 09:40:40 |
| ENAGAS_IR:dividends | https://www.enagas.es/en/investor-relations/share-performance/dividends/ | `b35e8141617fdf03…` | 2026-10-02 09:40:35 |
| ENAGAS_IR:dividends | https://www.enagas.es/en/investor-relations/share-performance/dividends/ | `82a59bc6f3454542…` | 2026-10-02 09:41:44 |
| EODHD:div | https://eodhd.com/api/div/AAPL.US?api_token=REDACTED&fmt=json&from=2020-06-01&to=2020-12-31 | `c52a827f4671f044…` | 2026-10-02 09:40:31 |
| EODHD:div | https://eodhd.com/api/div/MSFT.US?api_token=REDACTED&fmt=json&from=2004-10-01&to=2004-12-31 | `2c217ca0609ed699…` | 2026-10-02 09:40:33 |
| EODHD:eod | https://eodhd.com/api/eod/AAPL.US?api_token=REDACTED&fmt=json&from=2020-06-01&to=2020-12-31 | `5bc537912f6ec050…` | 2026-10-02 09:40:30 |
| EODHD:eod | https://eodhd.com/api/eod/MSFT.US?api_token=REDACTED&fmt=json&from=2004-10-01&to=2004-12-31 | `62124e1aab3f3273…` | 2026-10-02 09:40:32 |
| EODHD:splits | https://eodhd.com/api/splits/AAPL.US?api_token=REDACTED&fmt=json&from=2020-06-01&to=2020-12-31 | `7965c8570969c004…` | 2026-10-02 09:40:31 |
| EODHD:splits | https://eodhd.com/api/splits/MSFT.US?api_token=REDACTED&fmt=json&from=2004-10-01&to=2004-12-31 | `4f53cda18c2baa0c…` | 2026-10-02 09:40:33 |
| MICROSOFT_IR:dividends | https://www.microsoft.com/en-us/Investor/dividends-and-stock-history.aspx | `ec22b6934db311f7…` | 2026-10-02 09:40:35 |
| MICROSOFT_IR:dividends | https://www.microsoft.com/en-us/Investor/dividends-and-stock-history.aspx | `726c99dd8ac534dc…` | 2026-10-02 09:47:16 |

La página de Apple responde 403 a clientes automáticos: se archiva la copia de Internet Archive
(forma `id_`, sello 20260422063456) de la URL oficial. La página de Enagás cambia de bytes entre
capturas: cada captura es una fila nueva y el motor deduplica por `(provider, evento)` quedándose con
la versión más reciente.

## 4. Corporate actions oficiales normalizadas

| security | tipo | anuncio | ex | record | pago | efectiva | ratio | importe | fuente |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | SPLIT | 2020-07-30 | — | 2020-08-24 | — | 2020-08-31 | 4.0 | —  | APPLE_IR:dividend-history `4f315669af` |
| AAPL | CASH_DIVIDEND | 2020-07-30 | 2020-08-07 | 2020-08-10 | 2020-08-13 | — | — | 0.82 USD | APPLE_IR+EODHD_EXDATE `c52a827f46` |
| AAPL | CASH_DIVIDEND | 2020-10-29 | 2020-11-06 | 2020-11-09 | 2020-11-12 | — | — | 0.205 USD | APPLE_IR+EODHD_EXDATE `c52a827f46` |
| ENG | CASH_DIVIDEND | — | 2016-06-30 | — | 2016-07-05 | — | — | 0.792 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2016-12-20 | — | 2016-12-22 | — | — | 0.556 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2017-07-03 | — | 2017-07-05 | — | — | 0.834 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2017-12-19 | — | 2017-12-21 | — | — | 0.584 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2018-07-03 | — | 2018-07-05 | — | — | 0.876 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2018-12-17 | — | 2018-12-19 | — | — | 0.612 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2019-07-01 | — | 2019-07-03 | — | — | 0.918 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2019-12-19 | — | 2019-12-23 | — | — | 0.64 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2020-07-07 | — | 2020-07-09 | — | — | 0.96 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2020-12-21 | — | 2020-12-23 | — | — | 0.672 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2021-07-06 | — | 2021-07-08 | — | — | 1.008 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2021-12-17 | — | 2021-12-21 | — | — | 0.68 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2022-07-05 | — | 2022-07-07 | — | — | 1.02 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2022-12-19 | — | 2022-12-21 | — | — | 0.688 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2023-07-04 | — | 2023-07-06 | — | — | 1.032 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2023-12-20 | — | 2023-12-22 | — | — | 0.696 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2024-07-02 | — | 2024-07-04 | — | — | 1.044 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2024-12-10 | — | 2024-12-12 | — | — | 0.4 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2025-07-01 | — | 2025-07-03 | — | — | 0.6 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2025-12-19 | — | 2025-12-23 | — | — | 0.4 EUR | ENAGAS_IR:dividends `b35e814161` |
| ENG | CASH_DIVIDEND | — | 2026-06-30 | — | 2026-07-02 | — | — | 0.6 EUR | ENAGAS_IR:dividends `b35e814161` |
| MSFT | SPECIAL_DIVIDEND | 2004-07-20 | 2004-11-15 | 2004-11-17 | 2004-12-02 | — | — | 3.0 USD | MICROSOFT_IR:dividends `ec22b6934d` |

`—` = la fuente no publica ese campo; **no se infiere**. Apple IR no publica ex-date: sus dividendos
(59 desde 1995) quedan como `data_quality_issues.ca_unresolved_ex_date` y cualquier ventana de retorno que los
pueda contener se **rechaza** (`InsufficientValuationError`). El split de Apple se ancla en su «primera fecha
negociada ajustada» (`effective_date`). Enagás: la web publica ex-date sólo desde 2016-06-30; las 27 filas
anteriores (2003–2015, incluidas las de 2011–2015) no traen ex-date y quedan sin resolver.

## 5. Validación de Total Return con datos reales

Motor = `PITContext.total_return` (precios RAW + acciones conocidas en `as_of`). Cálculo independiente =
forma cerrada del test (no usa adjusted close del proveedor).

| caso | start | end | P0 | P1 | acción | raw price return | TR motor | TR independiente | Δ |
|---|---|---|---|---|---|---|---|---|---|
| AAPL 4:1 split | 2020-08-28 | 2020-08-31 | 499.23 | 129.04 | split x4 | -74.1522% | +3.391222% | +3.391222% | 0.0e+00 |
| AAPL 4:1 split (ventana 08-25→09-04) | 2020-08-25 | 2020-09-04 | 499.3 | 120.96 | split x4 | -75.7741% | -3.096335% | -3.096335% | 3.3e-16 |
| AAPL dividendo + split (ventana 08-03→08-31) | 2020-08-03 | 2020-08-31 | 435.75 | 129.04 | 0.82 USD (ex 08-07, EODHD) + split x4 | -70.3867% | +18.671785% | +18.671785% | 4.4e-16 |
| MSFT dividendo especial | 2004-11-12 | 2004-11-15 | 29.97 | 27.39 | 3.00 USD | -8.6086% | +1.401401% | +1.401401% | 7.1e-17 |
| ENG dividendo a cuenta FY2023 | 2023-12-19 | 2023-12-20 | 16.67 | 15.67 | 0.696 EUR | -5.9988% | -1.823635% | -1.823635% | 1.4e-17 |
| ENG dividendo complementario FY2023 | 2024-07-01 | 2024-07-02 | 14.1 | 12.79 | 1.044 EUR | -9.2908% | -1.886525% | -1.886525% | 3.8e-17 |

El retorno de precio del split de Apple sería −74 %: el motor lo neutraliza con el ratio oficial.
Invariancia ante split (100 € × 1 → 50 € × 2) y fórmula de dividendo simple en `tests/unit/test_real_market_ca.py`.

## 6. Discrepancias entre fuentes (QA, nunca autocorregidas)

- **MSFT dividendo especial 2004-11-15**: Microsoft IR = 3.00 USD (anuncio 2004-07-20); EODHD = 3.08
  (`unadjustedValue` = `value`, `period=Quarterly`, declaración 2004-07-21). Diferencia de 0.08 USD y de un día;
  posible suma del dividendo regular de 0.08 pagado el mismo día (NO probado). Se usa el oficial; el vendor es QA.
- **Apple ex-date**: Apple IR no lo publica; EODHD da 2020-08-07 (dividendo 0.82) y 2020-11-06 (0.205), con
  declaración/record/pago/importe idénticos a Apple IR. Se usa SÓLO esa coincidencia completa (tier VENDOR,
  `details.field_sources`); el resto de dividendos de Apple sigue sin ex-date.
- **EODHD volumen**: publicado ajustado por splits; el adaptador lo des-ajusta y lo marca `imputed`.
- **Apple IR vs EODHD** (split 2020-08-31): coinciden en fecha y ratio 4:1.
- **Alpha Vantage vs EODHD**: no medible (sin clave de Alpha Vantage). El comparador
  `compare_bars` está implementado y testeado (exactas/pequeñas/grandes/ausentes en A/B).
- **ENG en EODHD demo**: 403 (el token `demo` sólo sirve algunos tickers US) → `SOURCE_COVERAGE_INSUFFICIENT`;
  las cuatro sesiones ENG vienen del boletín oficial de BME.

