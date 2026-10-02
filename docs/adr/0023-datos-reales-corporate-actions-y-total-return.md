# ADR-0023 — Datos de mercado reales, corporate actions oficiales y Total Return validado

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Amplía:** ADR-0021, ADR-0022 · **Migraciones:** ninguna

## Contexto
Primera iteración con precios y corporate actions REALES. Restricciones del entorno: sin claves de
Alpha Vantage/EODHD; Alpha Vantage gratuito sólo da `outputsize=compact` (últimas 100 sesiones), por
lo que no sirve para el backfill 2011+. BME no ofrece gratis un OHLCV histórico completo desde 2011
(productos End-of-Day con licencia): no se construye un scraper masivo.

## Decisión
1. **Alpha Vantage `TIME_SERIES_DAILY`** (nunca `_ADJUSTED`): adaptador, parser y validación listos y
   testeados con payloads sintéticos; la llamada real exige `PITQUANT_ALPHAVANTAGE_API_KEY`
   (`BLOCKED_BY_CREDENTIAL` si falta). Se rechazan `Error Message`/`Note`/`Information` (HTTP 200).
   Papel: QA/prototipo, no fuente canónica.
2. **Validación de series** (`market/validation.py`): duplicados, orden, días fuera de calendario,
   sesiones ausentes, valores imposibles; fechas anteriores al calendario (1995) se informan, no fallan.
   `compare_bars` mide exactas/pequeñas/grandes/ausentes A/B sin corregir nunca una fuente con otra.
3. **Corporate actions oficiales** (`market/official_ca.py`): Apple IR, Enagás IR y Microsoft IR. Sólo se
   mapea lo que cada página publica. Apple no publica ex-date: su split se ancla en la «primera fecha
   negociada ajustada» (`effective_date`; `SPLIT` exige `ex_date` **o** `effective_date`) y sus
   dividendos quedan como `data_quality_issues.ca_unresolved_ex_date`. `PITContext.total_return`
   **rechaza** (`InsufficientValuationError`) cualquier ventana que pueda contener uno: nunca se
   calcula en silencio sin ellos.
4. **Ex-date desde fuente estructurada**: sólo si declaración, record, pago e importe del proveedor
   coinciden exactamente con la fila oficial; el evento es tier `VENDOR` (campo más débil) y
   `details.field_sources` registra el origen de cada fecha. Sin coincidencia completa → sin resolver.
5. **Versiones de una misma página** (la de Enagás cambia de bytes entre capturas): cada captura es una
   fila (append-only); `PITContext.market_actions` deduplica por `(provider, evento, tipo)` quedándose
   con la más reciente conocida (no se cuenta dos veces un dividendo).
6. **Precios ES**: el boletín diario oficial de BME (sección 2_38_0) es evidencia de sesiones sueltas
   (sin `open`, nunca imputado), no feed histórico. EODHD `demo` sólo cubre algunos tickers US.
7. **Cobertura**: ninguna de estas páginas es una fuente «aceptada» (D-05 abierto). Sin fuente aceptada la
   cobertura de CA nunca es `VERIFIED_COVERAGE`; se muestran las trazas reales
   (`ATTEMPTED_FAILED`/`PARTIAL_PERIOD`, "never verified"). Enagás: dividendos en efectivo desde
   2016-06-30 → `PARTIAL_PERIOD`. El componente de readiness no pasa a READY por tener un adaptador.
8. **`FEATURE_RESEARCH_READY`** (derivado): `FEATURE_ENGINE_READY` y Total Return real validado en cohortes
   completas. Hoy `false`.
9. **`pitquant reconstruct-security <security_id|ticker|CIK:..> <fecha>`**: conjunto de información en T
   (barras cerradas, hechos disponibles, CAs conocidas, dividendos sin ex-date, procedencia). Sin features.
10. **cohort-readiness** muestra por separado `identity/price/corporate_actions/fundamentals/total_return`
    y `eligible`.
11. Campo `confidence` del brief: se expresa con `source_tier` + `details.field_sources`; no hay columna
    nueva (sin migración).

## Límites
- AAPL/MSFT siguen registrados por CIK sin ISIN/CUSIP fechado: identidad PROVISIONAL (sin ticker fechado,
  `reconstruct-security` los resuelve por `CIK:`).
- 5 ventanas reales cortas validan el motor; no sustituyen histórico de cohortes.
- Enagás 2011–2015: la web da pago/importe pero **no ex-date** (27 filas): sin resolver.
