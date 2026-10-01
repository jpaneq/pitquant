# ADR-0018 — D-04: CNMV como fuente oficial de fundamentales españoles; precisión temporal DATE_ONLY

**Estado:** aceptada en lo arquitectónico · implementación del proveedor **pendiente** (requiere
descargar documentos CNMV) · **Fecha:** 2026-10-01 · **Amplía:** ADR-0015, ADR-0016

## Contexto
EDGAR da un header con `ACCEPTANCE-DATETIME` por accession. La CNMV no ofrece un equivalente
comprobado. Verificado el 2026-10-01 en fuentes oficiales CNMV:
- La ficha pública de información financiera intermedia (p. ej.
  `cnmv.es/Portal/AlDia/DetalleIFIAlDia?nreg=2017082262`) muestra un número de registro
  (`nreg`), «Inicio periodo», «Fin periodo» y «Publicación inicial» **sólo con fecha**,
  más las fechas de las **modificaciones** posteriores. Descarga en PDF y en XBRL
  (taxonomía IPP).
- La herramienta IPP (`cnmv.es/ipps/`) procesa los XBRL de información pública periódica
  remitidos bajo las Circulares 5/2015, 1/2008 y 1/2005.
- ESEF (Reglamento Delegado UE 2019/815): informe financiero anual en xHTML, con los estados
  NIIF consolidados etiquetados en Inline XBRL, para ejercicios iniciados desde el
  01-01-2020 (remitidos en 2021). La Directiva de Transparencia permitió aplazarlo un año.

**UNVERIFIED** (no comprobado todavía): si algún registro CNMV (OIR, hechos relevantes o el
registro de entrada) expone una **hora** inequívocamente ligada a cada documento; los
formatos exactos de descarga masiva; y las condiciones de reutilización.

## Decisión
1. **`CNMVFundamentalProvider`** sobre fuentes oficiales CNMV, con los mismos principios que
   EDGAR (ADR-0015):
   - el número de registro CNMV (`nreg`) hace de accession;
   - cada documento (PDF, XBRL IPP, ESEF xHTML/iXBRL) se guarda en `raw_source_archive` con
     su SHA-256;
   - las versiones de hechos son append-only;
   - cada modificación de la CNMV es una versión nueva con su propia fecha, y nunca
     reescribe la anterior;
   - companyfacts no tiene equivalente: el hecho se extrae del propio XBRL/iXBRL archivado.
2. **`availability_precision`**: `DATETIME` sólo si una fuente oficial liga una hora exacta
   al documento; en caso contrario `DATE_ONLY`. **No se inventa hora.**
3. **Política `DATE_ONLY`**: `effective_available_at` = primera apertura de sesión XMAD
   **estrictamente posterior al final** (00:00 del día siguiente, hora de Madrid) de la
   fecha de publicación (`MarketCalendar.date_only_available_at`).
   - Interpretar `next_market_open(fecha)` como la apertura de ese mismo día filtraría un
     documento publicado a las 17:45.
   - Tampoco vale el cierre de ese día más un retardo: el documento pudo publicarse a las
     23:59.
   - Esta regla sustituye a la anterior genérica «cierre + 60 min» para cualquier registro
     sin hora (`available_after_publication`).
4. `accepted_at`/hora de registro y `effective_available_at` se guardan **por separado**.
   Con `DATE_ONLY` se guarda la fecha publicada tal cual y nunca se rellena una hora.
5. **Alcance inicial:** un vertical slice de pocas compañías del IBEX y varios tipos de
   informe (anual ESEF, semestral IPP XBRL, una modificación). No se normaliza todo el IBEX
   de golpe.
6. Mientras no haya datos CNMV ingeridos, el IBEX se analiza **sin bloque fundamental** y
   `data-readiness` marca «CNMV fundamentals» como BLOCKED.

## Pendiente
- Aprobación para descargar los documentos CNMV del slice. Tras ella:
  - parser IPP XBRL y parser ESEF iXBRL;
  - tabla de filings CNMV (migración nueva);
  - tests con documentos reales archivados.
- Verificar si existe una hora oficial de registro por documento.
- D-04 (b)/(c): proveedor comercial para la historia previa a IPP/ESEF. Es decisión
  económica del propietario.


## Addendum 2026-10-01 — vertical slice real (Enagás)

1. **El XBRL descargable es la versión vigente.** La ficha de la CNMV lista las fechas de
   modificación, pero sólo ofrece el XBRL actual. Como no se puede probar qué valores
   existían en la publicación inicial, el contenido se usa desde la primera apertura XMAD
   posterior al final de la fecha **más tardía** entre publicación y modificaciones.
   Ejemplo: Enagás 2017S1, publicado el 18-07 y modificado el 27-07, se usa desde el
   28-07 a las 09:00 de Madrid.
2. **Dimensiones relativas.** Los miembros IPP «…PeriodoActual/Anterior»,
   «AcumuladoActual/Anterior» y «PeriodoCorriente» sólo sitúan la columna respecto al propio
   informe. Se elimina el sufijo relativo y se conserva el significado (p. ej.
   `IngresosOrdinariosClientesExternos`). Así, el comparativo de un informe posterior es una
   versión posterior del mismo hecho: en Enagás se detectaron 5 hechos de 2017S1 con otro
   valor en el informe de 2018S1. Los duplicados conflictivos se rechazan.
3. **Hora.** La página de «Otra información relevante» muestra fecha y hora (HH:MM) y enlaza
   a fichas IFI por `nReg`, pero **no declara zona horaria**. Hasta verificarla, la hora no
   se usa: la precisión sigue siendo `DATE_ONLY`.
4. **Identidad.** El emisor se identifica por CIF (nivel emisor). El vínculo CIF ↔ ISIN ↔
   miembro del IBEX está pendiente (hoy son `security_id` distintos).
