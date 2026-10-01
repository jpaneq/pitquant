# Parser del histórico IBEX 35 de BME — calibración

## Documento calibrado
**«Composición histórica – IBEX 35»** (BME, 3 páginas, filas Nº 1–137):
- Last-Modified: 2026-09-21.
- SHA-256 `5c028420…3695`.
- Archivado el 2026-10-01 en `raw_source_archive`, descargado de dos URLs oficiales que
  sirven bytes idénticos:
  - `bolsasymercados.es/bme-exchange/docs/SB/compoibex.pdf`;
  - `bolsasymercados.es/dam/descargas/indices/composicion-ibex-35-es-en.pdf`.
- Calibración versionada en código: `COMPOIBEX_2026_09`. Sólo se aplica a ese hash; otra
  versión del PDF vuelve a `UNKNOWN`.

### Layout medido
- **Columnas:**
  - cabeceras «Inclusiones / Addtions» y «Exclusiones / Deletions»;
  - cada fila empieza por «Nº» y fecha;
  - «—» o «-» significan «sin cambios»;
  - el inicio de cada columna se toma de la **celda** de cabecera más específica. La tabla
    se desplaza entre páginas y en la página 2 hay un rectángulo de fondo que la abarca entera.
- **Leyenda («Clave color»):**
  - *Revisión extraordinaria*: relleno CMYK `(0.149, 0.13, 0, 0)` en las celdas Nº/fecha.
    43 filas.
  - *Cambio de código*: relleno `0.5` en **celdas individuales** de ticker. Las celdas
    marcadas de altas y de bajas de una fila se emparejan de izquierda a derecha.
    7 cambios: CUB→ANA, UNI→PUL, TAB→ALT (dentro de la revisión ordinaria 25), CTG→GAS,
    SCH→SAN, ACE→ABE y VAL→SYV.
- **Color sin leyenda:** CMYK `(0.048, 0.176, 0.285, 0)` en las filas 62, 76, 80, 91, 106,
  108 y 122 (COL/CAR, EBRO/EVA, CABK/CRI, SCYR/SYV, SGRE/GAM, NTGY/GAS, RED/REE).
  Probablemente son cambios de código, pero **no está en la leyenda y no se infiere**: esas
  filas salen `UNKNOWN` y exigen su aviso BME.
- **Regla:** cualquier color no explicado por la calibración hace la fila `UNKNOWN`. Antes,
  un color desconocido se clasificaba en silencio como ORDINARY; está corregido.

### Anomalías del documento (visibles en tests)
- La fila 108 (02/07/2018, GAS→NTGY) es posterior a la 109 (09/05/2018): el orden no es
  cronológico.
- La fila 1 (02/01/1991) ya tiene bajas: **el documento no contiene la composición
  inicial**.

## Membership build real (2026-10-01)
`scripts/build_ibex_real.py` construye el universo sólo desde documentos oficiales
archivados. El informe está en `docs/IBEX_COVERAGE_REPORT.md`.

**Composición vigente.** `Constituents.pdf` ya no existe: la URL redirige a la página de
cotizaciones del IBEX 35. El aviso 15/2026 remite a un CSV de SIX que requiere licencia
(«Access denied»). Por eso la composición vigente es una **observación fechada** de la
página oficial de cotizaciones y de las 35 fichas (ticker + ISIN), archivada con su SHA-256.

**Reconstrucción.** Se recorre hacia atrás el histórico completo desde 2026-10-01 hasta
1995-01-02 (inicio del calendario XMAD):
- cada paso se valida;
- el tamaño se mantiene en [33, 36]: hubo 33 miembros entre el 2006-07-25 y el 2006-07-31
  (filas 55–58) y 36 en 2012 (alta de DIA sin baja).

**Las 7 filas sin marcador de leyenda** se cargan como rotación `UNRESOLVED_EVENT_TYPE`.
La membresía es idéntica bajo ambas lecturas (cambio de código o rotación); la continuidad
de identidad no se supone. Los avisos de 2007–2022 no están en el índice público de avisos
de BME (sólo 2026).

**Identidad.** Las 138/138 membresías históricas son `IDENTITY_UNRESOLVED`. Los ISIN
vigentes se registran sólo desde 2026-10-01 (ej.: FER pasó de ISIN español a neerlandés).
El build no es elegible para validación final y `backtest_universe()` falla cerrado.

**Tickers.** Derivados del índice y acotados a los periodos de pertenencia. Caso real:
CUB→ANA en 1997, ANA sale y vuelve a entrar en 1999.

## Prioridad de fuentes
1. Aviso BME: autoritativo para el tipo de evento, `announced_at` e ISIN si lo da.
2. Marcador visual calibrado del PDF.
3. Nada más: sin 1 ni 2, la fila no se carga.

## Identidad en reentradas (ADR-0017)
Una reentrada sin ISIN **no** se asume como la misma emisión: recibe identidad nueva
`IDENTITY_UNRESOLVED`. Con el ISIN oficial queda resuelta.

## Tests
- `tests/unit/test_ibex_history.py`: filas ficticias y un PDF generado en el test.
- `tests/realdata/test_bme_compoibex.py`: el PDF real desde el archivo local. Se salta si
  no está, porque el documento no se versiona en git.
