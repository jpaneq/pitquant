# Parser del histórico IBEX 35 de BME — procedimiento de calibración

El documento oficial **«Composición histórica – IBEX 35»** distingue visualmente (formato
o color de fila) entre revisiones ordinarias, revisiones extraordinarias y **cambios de
código/ticker**. El parser (`pitquant.universe.sources.bme`) lee ese marcador con una
`BMELayoutCalibration`. **Hoy no está calibrado**: no se ha tenido acceso al PDF real desde
este entorno (bme.es no es alcanzable), así que no se ha inventado ningún mapeo.

## Comportamiento sin calibrar (actual, seguro)
- Todas las filas salen con estilo `UNKNOWN`.
- La fila inicial (sin bajas, índice vacío) se acepta como `INITIAL_SNAPSHOT`.
- Cualquier otra fila exige un **aviso BME** de la misma fecha efectiva; sin él, la carga
  falla con `UnresolvedSourceEventError` listando las filas. **No se adivina nunca.**

## Calibración (una vez por versión del documento)
1. Descargar el PDF oficial y archivarlo (queda su SHA-256).
2. Abrirlo con `pdfplumber` e inspeccionar las filas conocidas de cada tipo, por ejemplo
   un cambio de código documentado en un aviso: anotar `non_stroking_color` de los
   caracteres y de los rectángulos de fondo.
3. Crear `BMELayoutCalibration(style_by_color={color: RowStyle.TICKER_CHANGE, ...},
   calibrated_for_sha256=<sha del PDF>)` y versionarla en el repositorio.
4. Ejecutar la extracción completa y cruzar **todas** las filas `TICKER_CHANGE` y
   `EXTRAORDINARY` con su aviso. Discrepancias → corregir calibración, no los datos.
5. Si BME publica una versión nueva del PDF (otro hash), la calibración deja de aplicarse
   automáticamente (vuelve a `UNKNOWN`) hasta recalibrar.

## Prioridad de fuentes
1. Aviso BME (autoritativo: tipo de evento, `announced_at`, ISIN si lo da).
2. Marcador visual calibrado del PDF histórico.
3. Nada más: sin 1 ni 2, la fila no se carga.

## Identidad en reentradas
Si un código vuelve a entrar tras haber salido y la fuente no aporta ISIN, se asume la
misma emisión y se registra un aviso de calidad `identity_assumed_reentry` para revisión
con los datos de D-05. Con ISIN en el aviso, la identidad queda determinada.

## Tests
Los tests (`tests/unit/test_ibex_history.py`) usan filas **ficticias**: los códigos
GAS/NTGY y REE/RED aparecen porque el requisito los nombra, pero las fechas son
ilustrativas y no están verificadas contra BME. La mecánica de extracción se prueba con un
PDF generado en el propio test, no con el documento de BME.
