# Enagás de extremo a extremo: identidad española con datos REALES

Generado con `scripts/gen_spanish_identity_demo.py` sobre la base local real (ADR-0018, ADR-0020). Pregunta: **¿por qué sabemos que este filing, este ticker y este membership corresponden al mismo emisor y a la misma security en T = 2018-07-18T09:00:00+02:00?**

## 1. Emisor CNMV → `issuer_id`

- Emisor `ee1e5d70-c2a7-450b-86d4-54ccaba62128` «ENAGAS, S.A.», identificado por **CIF A-28294726** (fuente: CNMV IFI page (NIF field)). Ningún ticker ni security se crea a partir del CIF.
- Informes periódicos CNMV de ese CIF ingeridos: 5 — nreg 2017082262 (2017 S1, publicado 2017-07-18), nreg 2018023181 (2017 S2, publicado 2018-02-21), nreg 2018085463 (2018 S1, publicado 2018-07-17), nreg 2019025071 (2018 S2, publicado 2019-02-27), nreg 2019090846 (2019 S1, publicado 2019-07-30).

## 2. `issuer_id` → ISIN (documento oficial)

- Consulta ANCV por NIF (`https://www.cnmv.es/portal/ancv/isin?nif=A-28294726`, archivada SHA-256 `0dad3f21786eefb701e770d95a6557be4e52a63f3f4cc024db7af76b722fc6b6`, 2026-10-01): «ENAGAS, S.A.» → **ES0130960018** ENG/AC 1.50 (emitido 1972-07-13, CFI ESVUFB).
- Es un vínculo CIF ↔ ISIN de la propia CNMV; no un parecido de nombre.

## 3. ISIN histórico (snapshots ANCV)

- ES0130960018 aparece en **33** snapshots semestrales ANCV (2010-06-30 → 2026-06-30), siempre con etiqueta ['ENG'] y razón social ['ENAGAS, S.A.'].
- Un snapshot prueba que el ISIN estaba activo en su fecha de referencia; NO es una fecha de alta ni de baja.

| Fecha ref. | Alcance (LEAME) | Etiqueta | SHA-256 del miembro |
|---|---|---|---|
| 2010-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `ef6dd64932e41e3f…` |
| 2010-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `ec9f73d7e6bfae37…` |
| 2011-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `dfa46b5c78e446d8…` |
| 2011-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `37112d82afaa92cc…` |
| 2012-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `5130679c55d216a9…` |
| 2012-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `5474374e3b7c11e0…` |
| 2013-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `615bf7d47fcb240d…` |
| 2013-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `5d6f108627757e17…` |
| 2014-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `38a34c9c11553b39…` |
| 2014-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `6095729c970afe36…` |
| 2015-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `333e2d2a0a58d0b4…` |
| 2015-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `852bc60857d8d54a…` |
| 2016-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `97ec1b9b074639ba…` |
| 2016-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `33fd428aa50fea10…` |
| 2017-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `d35e4333eacd10e4…` |
| 2017-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `5487d77f69c1da72…` |
| 2018-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `43ff4c902bb28784…` |
| 2018-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `a4059dbcadc7fd96…` |
| 2019-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `fd5cfb61d3308a9c…` |
| 2019-12-31 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `d8e8fdc8b150b182…` |
| 2020-06-30 | ADMITTED_TO_TRADING | ENG/AC 1,50 | `dc10b288b32ea5cb…` |
| 2020-12-31 | ADMITTED_TO_TRADING | ENG/AC 1.50 | `2c0f7bbee2093682…` |
| 2021-06-30 | ADMITTED_TO_TRADING | ENG/AC 1.50 | `316c2db9dba7d2e2…` |
| 2021-12-31 | ADMITTED_TO_TRADING | ENG/AC 1.50 | `0eb2390ee95b8948…` |
| 2022-06-30 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `9f7e6ab1736a5a9e…` |
| 2022-12-31 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `155ca258be8c4977…` |
| 2023-06-30 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `cc2a036783b62351…` |
| 2023-12-31 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `8df9bb6ed66a70b8…` |
| 2024-06-30 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `0ac7d3276813b5c7…` |
| 2024-12-31 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `10c0e1ab165a5ba5…` |
| 2025-06-30 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `739c96ebe234534e…` |
| 2025-12-31 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `5a809a9e9b2798af…` |
| 2026-06-30 | ACTIVE_IN_ANCV | ENG/AC 1.50 | `3d8f003bc26482ca…` |

## 4. ISIN → `security_id`

- Security `ce79cc0a-00dd-4bcb-a653-9909fe94aa72` (ENG (BME_HISTORICAL_COMPOSITION)), emisor enlazado `ee1e5d70-c2a7-450b-86d4-54ccaba62128` (= el emisor CNMV).
- Validez probada del ISIN en esa security: [2010-06-30, abierto) — la unión de los segmentos MULTI_SOURCE_CONFIRMED, nunca un alta inventada.

## 5. Ticker histórico (BME)

- `ENG` [2003-01-10, abierto) — acotado a la membership (el histórico BME sólo prueba el código mientras es miembro)

## 6. Membership IBEX y su identidad

- Intervalo [2003-01-10, abierto) código ENG (build `8f4716ed`, PROVISIONAL_RESEARCH_SOURCE)
- Segmentos de identidad (run `52ff0be6`):
  - [2003-01-10, 2010-06-30) **PROVISIONAL** — (ARCHIVAL_NON_CANONICAL_FOR_V1); evidencia: leading edge: no snapshot before the interval; candidate:ES0130960018
  - [2010-06-30, 2011-01-01) **MULTI_SOURCE_CONFIRMED** ES0130960018 (ARCHIVAL_NON_CANONICAL_FOR_V1); evidencia: 2025-12-31:anchor:ES0130960018; 2026-06-30:anchor:ES0130960018; 2026-10-01: BME current composition (transcription) gives ES0130960018
  - [2011-01-01, abierto) **MULTI_SOURCE_CONFIRMED** ES0130960018 (V1_CANONICAL); evidencia: 2025-12-31:anchor:ES0130960018; 2026-06-30:anchor:ES0130960018; 2026-10-01: BME current composition (transcription) gives ES0130960018

## 7. En T = 2018-07-18T09:00:00+02:00

- `universe('IBEX35', 2018-07-18)`: 35 miembros; Enagás presente (código ENG).
- Segmento de identidad en T: **MULTI_SOURCE_CONFIRMED** → ES0130960018 → security `ce79cc0a-00dd-4bcb-a653-9909fe94aa72`.
- `facts_as_of(security, T)`: 2403 hechos visibles, del EMISOR (issuer_id) por ser fundamentales CNMV; I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 = 682573000.0 (nreg del filing que lo aporta en el explain).
- `backtest_universe('IBEX35', 2018-07-18)`: FALLA CERRADO: IBEX35@2018-07-18: 1 member(s) without a proven identity (e.g. 88a25898-1850-4dbd-99cc-4fc84114ca49(UNRESOLVED)); resolve identity before backtesting

### `explain` en T
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for ce79cc0a-00dd-4bcb-a653-9909fe94aa72 (ticker then: ENG) as of 2018-07-18T07:00:00+00:00
  identity    ISIN on that day: ES0130960018 (proven 2010-06-30..open)
  identity    issuer ENAGAS, S.A. (CIF A-28294726 [CNMV IFI page (NIF field)])
KNOWN: 682573000.0 EUR (ipp_ge@2016-06-01:I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] ..2017-06-30, 2018 S1)
  filing      IFI_IPP 2018 S1 (published 2018-07-17, DATE_ONLY) CNMV nreg 2018085463 filed 2018-07-17
  document    https://www.cnmv.es/Portal/AlDia/DetalleIFIAlDia?nreg=2018085463
  accepted_at - (header)
  available   2018-07-18T07:00:00+00:00 (DATE_ONLY: next XMAD open after end of publication date)
  parser      cnmv-ipp-3  header sha256 eee463890aa0480936d91f84d52949dd7732accad4046fb00f42ff829e6be015
  xbrl sha256 734fcffab760dc70db541b1c21850e0e0bdb63b1f97a6925ba2417f6af5326f3
NOT KNOWN: 688034000.0 from CNMV nreg 2017082262 — superseded_by:6ea831dc-5f94-4284-add0-30bf85e73f35: a later version (CNMV nreg 2018085463, available 2018-07-18T07:00:00+00:00) was also known at as_of
```

## Por qué es la misma entidad

1. **Filing → emisor:** el informe CNMV lleva el CIF A-28294726 en su ficha oficial.
2. **Emisor → ISIN:** la ANCV (CNMV) devuelve para ese NIF el ISIN ES0130960018.
3. **ISIN → security:** el motor de identidad ancla ES0130960018 al intervalo IBEX porque, DENTRO del intervalo, la única acción ordinaria con etiqueta ANCV `ENG` es ese ISIN, y está presente en todos los snapshots (MULTI_SOURCE_CONFIRMED: BME + ANCV).
4. **Security → ticker/membership:** el código ENG es el que el histórico oficial BME da a ese miembro en esas fechas.

Lo que NO se afirma: fechas de alta/baja del ISIN (los snapshots no las prueban), ni identidad anterior al primer snapshot (2010-06-30, ARCHIVAL). Si `backtest_universe` falla en T, es porque OTRO miembro del índice no tiene identidad probada (fallo cerrado por fecha), no por Enagás.
