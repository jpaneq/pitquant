# Decisiones de datos

Estado a 2026-10-01. Las decisiones condicionan la **validez** de los resultados, no la
arquitectura: el código funciona con cualquier opción gracias a las interfaces de providers.

## Resueltas

| ID | Decisión | Resolución | Implementación |
|---|---|---|---|
| D-01 | Fundamentales PIT EE. UU. | **SEC EDGAR**, procedencia por accession + header ACCEPTANCE-DATETIME; companyfacts sólo descubrimiento/validación; política de disponibilidad conservadora; cobertura 2011+ | ADR-0015, `data/providers/sec_edgar/` |
| D-02 | Constituyentes S&P 500 | **Histórico oficial/licenciado S&P DJI** como canónico; reconstrucción desde anuncios como `PROVISIONAL_RESEARCH_SOURCE`; fuentes comunitarias sólo QA | ADR-0013, `universe/sources/spdji.py` |
| D-03 | Constituyentes IBEX 35 | **PDF oficial BME «Composición histórica – IBEX 35»** como flujo de eventos + **avisos BME** para verificar, actualizar, resolver ambigüedades y aportar `announced_at`; `TICKER_CHANGE` nunca inferido | ADR-0013, `universe/sources/bme.py`, `docs/BME_PARSER.md` |
| D-09 | Holdout final | **oct-2022 → sep-2025**, fijado antes de ver resultados y ahora **sellado**: sólo `evaluate_candidate_on_holdout` (modelo congelado, una vez por versión, registrado); invisible en analytics/API/dashboard | ADR-0014, `validation/holdout.py` |

### Pendiente de acción del propietario para D-01…D-03
- **D-01:** fijar `PITQUANT_SEC_USER_AGENT` con un contacto real y lista de CIKs del universo.
  El conector no se ha ejecutado contra la SEC desde aquí (red bloqueada en este entorno);
  sólo contra fixtures.
- **D-02:** obtener la licencia/fichero histórico de S&P DJI y escribir el adaptador a su
  formato real (hoy se acepta el «formato normalizado» documentado en `spdji.py`).
- **D-03:** descargar el PDF y los avisos de BME y **calibrar** el parser
  (`docs/BME_PARSER.md`). Sin calibración, cada fila no inicial exige su aviso.

## Abiertas

### D-04 — Fundamentales point-in-time del IBEX 35 (no bloquea EDGAR)

**Actualización:** ADR-0018 fija la parte arquitectónica.
- Fuente oficial: CNMV, con `nreg` como accession.
- Documentos archivados: XBRL IPP y ESEF iXBRL.
- Política `DATE_ONLY`: primera apertura XMAD estrictamente posterior al final del día de
  publicación.

Sigue abierto:
- el proveedor comercial para la historia previa (opción b/c);
- la implementación del vertical slice, que necesita aprobar las descargas CNMV.

Es bastante más difícil que EDGAR: no hay un equivalente directo a un header con hora de
aceptación ni a companyfacts, la cobertura estructurada es más reciente y la frecuencia de
reporte es menor.

| Pregunta a resolver | Por qué importa |
|---|---|
| ¿Qué marca temporal oficial usamos? (registro CNMV de la información regulada / hecho relevante / OIR: fecha y, si existe, hora de registro) | Equivale a `accepted_at`; sin hora fiable aplicar la política conservadora de "sólo fecha" (cierre + lag) |
| ¿Qué estructura de datos? (informes financieros anuales en ESEF/iXBRL; formatos de información pública periódica semestral) | Determina cuánto se puede automatizar y desde qué año |
| ¿Qué frecuencia? (anual y semestral obligatorias; información trimestral según emisor) | Afecta a frescura de features y a comparabilidad con EE. UU. |
| ¿Qué taxonomía? (IFRS / ESEF) y su mapeo a conceptos comunes | Comparación sectorial transfronteriza |
| ¿Qué cobertura antes de ESEF? | Probablemente requiere proveedor comercial PIT o aceptar historia corta |

Opciones (a verificar coste, cobertura y condiciones actuales):
(a) construcción propia sobre CNMV + ESEF con la misma arquitectura de accession/archivo;
(b) proveedor comercial con histórico PIT europeo (institucional);
(c) híbrido: (a) como fuente auditable reciente y (b) para historia y contraste.

**Recomendación provisional:** (c). Mientras tanto, el IBEX se analiza sin bloque
fundamental y cualquier resultado lo indica explícitamente (no se rellenan huecos).

### D-05 — Precios, dividendos, corporate actions y delisting returns (EE. UU. y España)

**Actualización:** la especificación de aceptación, la suite de contrato
(`tests/contracts/`) y la matriz de proveedores están en `docs/D05_MARKET_DATA_ACCEPTANCE.md`.
La decisión sigue **ABIERTA**: depende de una decisión económica del propietario y de
verificar los casos de contrato.

Decisiva: un motor fundamental excelente sobre precios contaminados o sin empresas
desaparecidas reintroduce sesgo de supervivencia.

**Requisitos mínimos de cualquier fuente** (se convertirán en tests de aceptación):
1. OHLCV **sin ajustar** y eventos por separado (`ex_date`, `announced_at`, ratio, importe).
2. Empresas **deslistadas** incluidas, con última cotización y motivo; para fusiones,
   contraprestación (efectivo/acciones) y fecha efectiva; para quiebras, valor terminal.
3. Historial de identificadores (ticker, ISIN/CUSIP) con fechas.
4. Dividendos brutos con tipo; en España: **dividendo flexible/scrip** y **ampliaciones
   con derechos** (frecuentes en banca española) tratados explícitamente.
5. Benchmarks **total return** (S&P 500 TR, IBEX 35 con Dividendos) y sectoriales.
6. Archivo de cada descarga en `raw_source_archive`.

Opciones (a verificar coste y cobertura actual): EE. UU. — CRSP (estándar académico,
incluye delisting returns), Sharadar (incluye deslistadas), proveedores minoristas
(verificar cobertura real de deslistadas antes de pagar). España — datos oficiales de BME
o proveedores institucionales; validar específicamente scrip dividends y derechos.

**Plan de validación:** muestra de control con casos conocidos (splits, quiebras,
adquisiciones en efectivo y en acciones, scrip, derechos) que el candidato debe reproducir
antes de aceptarse.

### Otras

| ID | Decisión | Estado |
|---|---|---|
| D-06 | Benchmarks total return y sectoriales | Ligada a D-05 |
| D-07 | Estimaciones de analistas PIT | **Desactivadas** hasta tener fuente PIT verificable |
| D-08 | Divisa | Excess return en divisa local; carteras en EUR |
| D-10 | Despliegue | Docker Compose local (Mac Mini); el código no depende del host |
