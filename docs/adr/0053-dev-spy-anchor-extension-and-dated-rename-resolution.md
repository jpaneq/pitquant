# ADR-0053 — Extensión DEV de anclas SPY y resolución de nombres fechada

Estado: implementada, 2026-10-05. Ningún gate, universo de entrenamiento o modelo cambia.

La extensión intenta los N-30D semestrales de 2010-09 a 2017-03; septiembre de 2010 acota enero de 2011. El accession real de septiembre de 2013 se declara y se verifica contra EDGAR para distinguirlo del filing de 2014 incorrectamente fechado como 2013. No se reemplaza la fecha de ningún documento.

El resolver pasa a `anchor-graph-6`: los segmentos de versiones anteriores se conservan append-only; las nuevas evaluaciones se persisten con una versión distinta, sin reutilizar resultados de otro algoritmo.

Si CUSIP e ISIN oficiales apuntan a securities diferentes, se rechaza la ingesta antes de declarar un ancla VERIFIED; informar del conflicto y elegir uno no basta.

La ingesta core conserva su rechazo atómico ante discrepancias. `--extend` comprueba cada objetivo independientemente: un objetivo ausente o con fecha contradictoria se publica en `extension_errors`; sólo se incorporan los demás documentos verificados. La ejecución devuelve código 1 cuando hay errores, aunque haya conservado avances válidos. Repetirla no crea anclas duplicadas. Cada documento se conserva con originales, retrieval, hash, accession y versión; una descarga rechazada puede quedar archivada sin convertirse en ancla.

`spy-n30d-period-v1` lee la fecha junto a «Schedule of Investments». Las nuevas anclas de extensión exigen esa fecha; API, encabezado y schedule deben concordar. El parser histórico se mantiene compatible con fixtures anteriores sin ese encabezado, pero rechaza una fecha visible contradictoria. El filing `0001193125-14-428689` tiene API y encabezado 2013-09-30 frente a schedule 2014-09-30: se conserva la discrepancia y se excluye. El archivo de procedencia registra nombres originales y resueltos, identificadores observados y bases de resolución. Las listas 13(f) son evidencia trimestral de identidad; no de membresía ni de fecha de evento.

Añadir anclas antiguas hizo visible un predecessor Bemis que antes no estaba en el índice de nombres. Una pata ADD que S&P describe con el nombre antiguo no puede quedar asignada a ese predecessor cuando una declaración de cambio de nombre ya publicada identifica al sucesor presente sólo en B. El resolver prioriza esa declaración fechada y consistente con B; una declaración futura no participa. No se introduce una sucesión, fecha de fusión o identidad por esa prioridad de resolución. No se aplica el cambio de nombre retroactivamente a la membresía anterior al evento.

Los folds del primer ML rechazan fechas del holdout/OOT incluso si el llamador las pasa. Una cohorte con identidad débil no entra en el plan: se comparan sus IDs legales con los IDs de linaje utilizados por la reconciliación. El contrato sigue exigiendo 85 meses para tres folds; `required_securities=100` permanece intacto.

Resultado: 13 anclas nuevas, 30 nodos por fecha, 37 filas de anclas. Los 60 meses originales siguen listos; los 81 meses anteriores ahora tienen anclas pero permanecen bloqueados por fechas/identidades pendientes. Las cuatro identidades de research se documentan con fuentes oficiales, sin convertir un hecho de CUSIP en una autorización de toda la serie histórica. Véanse los informes D02_EXTENDED_AUDIT, FIRST_ML_SECURITY_IDENTITY y DATA_READINESS_FIRST_ML.
