# ADR-0035 — Cierre local de D-02: parser v4, declaraciones de cambio de nombre y conjuntos de clases

Estado: aceptada (2026-10-03). Motor `anchor-graph-3`, parser `sp500-evidence-4`, `sp500-renames-1`.

## Contexto
Con sólo el archivo local había 46 bloqueos de membresía (21/60 cohortes, racha 9). Auditados uno a uno, la mayoría eran fallos de
extracción o de identidad, no ausencia de evidencia.

## Decisiones
1. **Parser v4** (las filas v3 se conservan, append-only, y no se mezclan: el grafo sólo lee la versión vigente).
   - Corrección de un falso evento primario: una retirada «replacing X, which will be removed» sin ticker tomaba el ticker añadido anterior
     (OGN). Ahora el ticker de retirada debe estar pegado a «which will be removed»; si no, el ticker sale de un nombre exacto único de un comunicado
     oficial anterior o de ese mismo comunicado; si no, no hay pata.
   - Varios tickers de clases (`FOXAV; FOXBV`, `UA/UAA`) = patas enumeradas; «respectively» empareja por empresa; «to be renamed X» se conserva en el nombre;
     «A will be added. A will replace B.» (Tesla/AIV). Piernas con fechas distintas nunca se funden.
2. **Declaraciones de cambio de nombre de S&P** (formas cerradas, `sources/sp500_renames.py`): son evidencia PRIMARIA de que la plaza del índice continúa,
   no de la fecha de transición del CUSIP. Sólo enlazan (`security_succession`, `membership_continuity`, `effective_at` NULL) si, además, el nombre viejo y el
   nuevo resuelven cada uno a UNA security de ancla, el comunicado dice que permanece en el S&P 500 y las listas 13(f) muestran el mismo CUSIP o
   DELETED/ADDED coincidentes en un trimestre. Una declaración sola o un cambio 13(f) solo nunca enlazan. Un alias de nombre (Gardner Denver → Ingersoll Rand Inc,
   Bemis → Amcor) sólo ayuda a resolver la pata del evento, como última ruta.
3. **Regla de conjunto de clases:** patas de una misma cláusula (mismo tipo, fecha y estado) con el mismo nombre y el mismo conjunto de candidatos se asignan a la vez sólo si
   nº de patas = nº de securities; el emparejamiento ticker↔clase queda sin decidir. Otro recuento = ficha.
4. **Resolver:** la ruta por nombre del comunicado precede a la del ticker actual (reutilización de tickers: FOXA) y la ruta válida para el segmento gana.
5. **Puente 13(f):** tabla fija de abreviaturas que imprime la propia lista (PETE, FINL, RUBR, NATL, EXPL, RES, CENTY, COMMUNICATNS, INTERACT IN→INTERACTIVE INC, sufijo DEL),
   «Cos.»→«Companies», «Series X» como clase, línea `WHEN ISSUED` no es la acción ordinaria, y una única entrada ordinaria sin clase sirve a una etiqueta «Series A».
   La clase nunca se toca; dos candidatos = sin resolver.
6. **Idempotencia:** el run de eventos se reutiliza si el contenido es idéntico; `link_same_security` no duplica un par ya enlazado.

## Lo que NO se hace
Sin similitud de texto (PPoG sigue siendo una ficha: el typo está en el N-30D original, accession 0001193125-17-355427); IQVIA, Harris/L3Harris, Torchmark/Globe Life,
Kors/Capri, Leucadia/Jefferies, DexCom/Domino's/Allergan/Capri, Mylan/Viatris y Discovery/WBD quedan como fichas (documento ausente del archivo local).
Ningún ancla ni declaración posterior a 2022-09-30 se lee. El CSV de discovery no prueba nada.

## Residuo conocido
Bemis→Amcor: la declaración de S&P prueba la continuidad de la plaza pero no la fecha de cierre de la fusión; antes del cierre el miembro real era Bemis, no Amcor.
Las cohortes mensuales afectadas (julio–septiembre de 2019) quedan bloqueadas por otros casos del segmento; si se desbloquearan, esta salvedad debe revisarse.
