# D02/D05 y preparación del primer ML — cierre verificable

> Los apartados anteriores al resultado de extensión documentan la iteración previa. El estado vigente está en **D02 EXTENDED ANCHOR RESULT**, al final.

HEAD inicial de la iteración previa: `85cf086`. Rama: `codex/d02-d05-first-ml-readiness`. No se ha entrenado ningún modelo ni tocado BTC, pesos, champion o holdout.

## D02

Antes: 54/141 meses READY, 6 BLOCKED, 81 NO_ANCHOR, racha 54. Después: 60/141 READY, 0 BLOCKED, 81 NO_ANCHOR, racha 60. Cero folds: un fold exige 61 meses; tres exigen 85 (36 train +12 purge +1 embargo +36 test). No se han reducido requisitos. Faltan 25 meses continuos como mínimo.

Se ejecutó `scripts/ingest_spy_anchors.py --extend`; rechazó la ejecución porque falta `PITQUANT_SEC_USER_AGENT` con correo de contacto. No se ha inventado un contacto. Las anclas 2014-09→2017-03 siguen pendientes de descargar. Todos los meses y motivos están en DATA_READINESS_FIRST_ML.md; los 81 meses sin ancla abarcan 2011-01→2017-09.

PPoG queda resuelto exclusivamente para accession 0001193125-17-355427, mediante DOCUMENT_SPECIFIC_TYPO_ALIAS, versión document-typo-alias-v2. El texto original y hash permanecen archivados. Se enlaza con PPG canónico (CUSIP 693506107 documentado por NPORT), sin evento corporativo ni nueva security. El issuer interno se registra sin inventar CIK. Véase ADR-0051 y D02_D05_RECONSTRUCTION.json.

## Mercado

Yahoo es el proveedor canónico aprobado, tier VENDOR. ADR-0050 fija yahoo-market-data-v1: OHLC bruto reconstruido desde el vintage, adjusted close separado para QA, splits y dividendos normalizados y archivo original con SHA. Volumen anterior a splits se deja NULL si no puede reconstruirse. La disponibilidad de mercado al cierre de sesión es distinta de retrieved_at/ingested_at reales; las consultas con ingested_before respetan el vintage. FX sigue disponible a las 00:00 UTC del día siguiente.

Las ingestas AAPL y MSFT conservan la security SEC existente y enlazan el issuer con su submission oficial archivada. Ambas tienen 3.961 barras Yahoo y 59/63 acciones corporativas; ENG.MC tiene 4.029 barras y 30 acciones. QA READY para las tres. EODHD histórico se conserva pero queda excluido de investigación canónica.

**Corrección del diagnóstico de ENG:** no se reproduce la cifra de 22 barras del encargo. La copia SQLite anterior a esta intervención contiene exactamente cuatro precios oficiales BME, entre 2023-12-19 y 2024-07-02. `scripts/ingest_real_market_ca.py` seleccionaba cuatro boletines alrededor de dos fechas ex-dividendo (BULLETIN_DAYS), para validar eventos; no era una descarga de historia completa. No hay evidencia para atribuir 22 barras a un fallo del proveedor.

QA: 103 series incluyendo tres benchmarks; 85 READY y 18 BLOCKED. Todas las series US pasan; fuera de US quedan OHLC imposibles, divisas incompatibles o cobertura de acciones no verificable. Los 14 originales que el normalizador estricto rechaza y cada fecha inválida se conservan y listan en D05_YAHOO_QA.json. No se corrigen OHLC ni divisas por aproximación.

SPY y URTH son ETF_PROXY/PROXY_ACCEPTABLE, no índices oficiales. ^IBEX sigue PRICE_RETURN_ONLY y no proporciona retorno total. Se buscó una serie Yahoo IBEX 35 TR sin identificar un símbolo verificable. BME identifica el índice con dividendos como ES0SI0000047 ([ficha oficial](https://www.bolsasymercados.es/es/bme-exchange/indices/ficha.ibex-35-con-dividendos-es0si0000047.html)). INDST.MC no sustituye al IBEX 35 TR: corresponde al small cap. URTH+FX se mantiene como diagnóstico para España; el primer ML usa alcance US explícito.

## Datos y elegibilidad

Versiones append-only: research-features-v1-yahoo-v1 y research-targets-v2-yahoo-v2. La primera reconstrucción de objetivos yahoo-v1 se conserva: yahoo-v2 corrige únicamente la etiqueta de procedencia FX EXPLORATORY→CANONICAL, sin reescribir filas anteriores. Se reconstruyeron 15.208 snapshots y 76.040 objetivos por versión de targets (cinco variantes, no 76.040 observaciones independientes).

100 securities configuradas, 100 con precios y snapshots. 51 con puente de identidad válido para el universo US y filas elegibles; faltan 49 para required_securities=100: 45 valores no US fuera del universo de este primer experimento y cuatro US sin puente inequívoco (XOM, GOOGL, GE, RTX). Algunas etiquetas configuradas (CABK, NTGY, ROG, SAN) no coinciden con las etiquetas archivadas: no equivalen a cuatro securities adicionales sin precios. El informe publica security_id, fechas Yahoo, QA, identidad, motivos acumulados y filas elegibles para cada security.

Precio 12M: 2.396 filas elegibles. Fundamentales 12M: 1.785. Precio 6M: 2.702. Son elegibilidades individuales; no autorizan entrenamiento porque faltan gates globales. 40 securities tienen al menos 36 meses fundamentales PIT (antes 38). CVX ya tenía 130 meses en HEAD inicial: no ha requerido un mapping especial nuevo. JPM/BAC/WFC/UNH siguen excluidos de la familia fundamental por sector, conservando posibilidad de familia precio. XOM sigue sin puente oficial a su nueva identidad/CIK y con cero meses fundamentales; no se infiere continuidad. RTX, clases Alphabet/GE siguen pendientes de evidencia inequívoca. C.R. Bard se cierra con la lista oficial SEC 13F 2017Q3 (CUSIP 067383109), regla exacta de iniciales versionada y clase común verificada; identidad global de miembros D02 READY. Véase ADR-0052. Esto no resuelve los cuatro puentes de research US pendientes.

Holdout 2022-10-01→2025-09-30: cero snapshots nuevos; ventanas que lo tocan permanecen UNAVAILABLE. 1.300 filas OOT desde 2025-10 se mantienen separadas y excluidas de elegibilidad. No se han usado resultados para elegir modelos, pesos ni umbrales.

## Resultado

FIRST_ML_BASELINE_READY=false. Bloqueos exactos: D02 sin tres folds y 51/100 securities elegibles. Identidad global de miembros D02, D05 US, benchmark comparable US, fundamentales y holdout pasan. La matriz completa y los embudos son DATA_READINESS_FIRST_ML.json/.md. El estado histórico D02 de 60 meses puede pasar su gate antiguo; el gate del primer ML exige tres folds y permanece BLOCKED.

Validación: ruff, mypy strict, SQLite (933 passed, 3 skipped por proveedores opcionales), PIT (353 passed sin skips) y PostgreSQL estricto (20 passed); Alembic sin nuevas operaciones, head 0027. No hay migración nueva. Docker se verifica en el job de CI. Los resultados finales de CI corresponden al SHA final publicado, no a la ejecución inicial.

Único siguiente paso recomendado: proporcionar el contacto SEC y ejecutar la extensión oficial de anclas SPY para obtener al menos 85 meses consecutivos verificables, manteniendo los gates restantes visibles.

Reproducción: `PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db .venv/bin/python scripts/rebuild_canonical_research.py` (o `--targets-only`), seguido de `scripts/validate_yahoo_d05.py` y `scripts/gen_data_readiness_first_ml.py`. Cada fase confirma su transacción; no entrena modelos.

## D02 EXTENDED ANCHOR RESULT

HEAD inicial de esta iteración: `c936a13`. Rama: `codex/d02-d05-first-ml-readiness`; PR draft [#1](https://github.com/jpaneq/pitquant/pull/1). Se mantiene separada de master.

### SEC y anclas

El contacto proporcionado por el propietario se ha validado mediante respuestas SEC 200. Se pasa sólo en `PITQUANT_SEC_USER_AGENT` runtime; no se guarda en código, configuración ni logs. Se ejecutó `scripts/ingest_spy_anchors.py --extend`: core sin duplicados y 13 anclas N-30D nuevas, de 2010-09 a 2017-03. Se archivaron también las 14 listas 13(f) trimestrales correspondientes, con originales y hashes. La repetición de la extensión crea cero anclas: es idempotente.

Anclas verificadas en DB: **24→37**; nodos únicos por fecha, con NPORT preferido: **17→30**. La ancla 2010-09 acota enero de 2011; ninguna posterior a 2022-09 se incorpora. Los 13 accessions, fechas de presentación/aceptación, fuentes, retrievals, hashes, nombres originales/resueltos de 6.512 posiciones, CUSIP/ISIN observados y métodos/versiones se publican en D02_EXTENDED_ANCHOR_PROVENANCE.json.

El filing `0001193125-14-428689`, presentado 2014-12-01, declara 2013-09-30 en la API y el encabezado, pero 2014-09-30 en el schedule. Sus originales se archivaron; **no se corrige la fecha ni se declara ancla VERIFIED**. La ejecución de extensión devuelve 1 por este objetivo pendiente, conservando las 13 incorporaciones válidas. No es un error de contacto o de red.

### Reconstrucción y pendientes exactos

Antes: **60/141 READY**, 81 NO_ANCHOR, racha 60. Después: **60/141 READY**, **81 BLOCKED**, **0 NO_ANCHOR**, racha **60**, cero folds. Los 81 meses 2011-01→2017-09 ahora están acotados por anclas; faltan los cambios oficiales e identidades que permiten fechar su composición. Tres folds requieren **85 meses continuos** (36 train +12 purge +1 embargo +36 test); un fold requiere 61. Ningún umbral cambia.

La incorporación de anclas antiguas reveló un cruce del nombre Bemis con la pata ADD de Amcor en 2019. Se corrige mediante la declaración fechada de S&P y la presencia del sucesor en B; una declaración futura no se usa. Los **60 meses originales vuelven a estar íntegros**. `anchor-graph-6` conserva los segmentos de versiones previas y escribe nuevos resultados append-only; no redefine la fecha legal de una fusión.

Quedan **227 fichas que bloquean membresía**: **141 PRIMARY_EVENT_MISSING**, **65 SECURITY_IDENTITY_ONLY**, **12 MONTHLY_DATE_AMBIGUITY**, **9 PRIMARY_DELTA_UNEXPLAINED**. No se afirma que todos los documentos estén ausentes: los casos de fecha insuficiente o contradicción incluyen evidencia primaria archivada. Hay **56 securities históricas con identidad débil**, frente a cero en la cadena corta previa; se hacen visibles al ampliar la cadena. No se oculta el retroceso del gate global de identidad: US_SECURITY_IDENTITY_READY está PARTIAL.

D02_EXTENDED_AUDIT.json vincula cada uno de los 81 meses a sus gap_ids, anclas A/B, accession/hash, instrumento, intervalo, disponibilidad de evidencia, documento requerido y condición de cierre. Todas las cohortes bloqueadas tienen fichas. SP500_LOCAL_GAPS.md/.json y SP500_RESIDUAL_GAP_CARDS.md/.json cubren ahora **DEV 2011-01→2022-09**, no sólo la ventana antigua de 60 meses.

Las cohortes con identidad débil no entran en folds. El planificador tampoco acepta holdout/OOT aunque un llamador se los pase. No hay rangos de folds reales que publicar mientras el contador sea cero.

### Cuatro identidades de research

FIRST_ML_SECURITY_IDENTITY.json conserva fuentes regulatorias/exchange con retrieval, archive_id y hash. Ninguna se promociona automáticamente a una serie entera:

- **XOM PARTIAL**: el 8-K confirma sustitución 1:1 del antiguo issuer CIK 34088 por ExxonMobil Holdings CIK 2115436 el 2026-07-01. El perfil actual no certifica el instrumento antiguo. La evidencia posterior al DEV es sólo auditoría de identidad, nunca ancla, feature o dato de selección.
- **RTX PARTIAL**: UTC/UTX continúa bajo nuevo nombre el 2020-04-03; RTN es otra security, con canje 2.3348. No se aplica esa ratio a UTX. Falta formalizar el vínculo fechado de instrumentos y reconciliar Carrier/Otis con la base de retorno.
- **GOOGL PARTIAL**: SEC verifica Alphabet Class A CUSIP 02079K305; Nasdaq confirma reemplazo por clases el 2015-10-05. GOOG Class C 02079K107 permanece distinto. Falta la asignación temporal completa de la serie de research al instrumento, incluidas las etapas Google/Alphabet.
- **GE PARTIAL**: el exhibit del emisor verifica reverse split 1:8 y CUSIP 369604301 desde 2021-08-02. Falta formalizar la transición desde el antiguo identificador con su evidencia y unidades, separada de la QA de retornos. No se traslada retrospectivamente el negocio actual a periodos anteriores a los spin-offs.

### Cobertura y decisión metodológica

Se mantienen **51 securities US elegibles**, antes y después; 55 US configuradas, 45 non-US, 100 globales con snapshots. Bajo el contrato US actual, el número global elegible también es 51. Hay 51 issuer IDs distintos, 2.396 filas PRICE 12M en 48 cohortes con etiquetas maduras (49–51 valores por cohorte, entre 9 y 48 meses por security) y 1.785 filas FUNDAMENTALS. Estos conteos **no son tamaño efectivo independiente**.

El umbral 100 procede del gate global de snapshots de RUN 3; fue conservado para un gate de elegibilidad distinto en ADR-0049. No hay cálculo estadístico documentado que derive 100. PROPUESTA-first-ml-security-coverage.md propone cobertura histórica mensual y precisión por fold, con dependencia por issuer/bloques temporales y parámetros preregistrados; **no se aplica** y no se inventa un nuevo mínimo para que pasen los 51. El primer ML actual es US-only y se recomienda mantener ese alcance; no se renombra el experimento.

### Matriz final

| Gate | Estado |
|---|---|
| D02_MONTHLY_RESEARCH_READY | BLOCKED |
| US_SECURITY_IDENTITY_READY | PARTIAL |
| D05_READY (US) | READY |
| BENCHMARK_RETURN_BASIS_READY (US) | READY |
| RESEARCH_SECURITY_COVERAGE_READY | BLOCKED: 51/100 |
| US_FUNDAMENTALS_READY | READY: 40 securities con >=36 meses; mínimo 30 |
| HOLDOUT_SEALED | READY |
| RESEARCH_DATA_READY | BLOCKED |
| FIRST_ML_BASELINE_READY | **false** |

Validación local final: ruff y formato limpios; mypy strict, 213 módulos; **948 passed, 3 skipped** en SQLite, **363 PIT passed sin skips**, **20 PostgreSQL passed**, upgrade/check/downgrade Alembic limpio, head **0027**, ninguna migración nueva. Docker no está instalado localmente; su build se valida en el job específico de GitHub Actions del commit publicado. No se toca frontend/E2E; sus jobs de CI siguen siendo obligatorios. La PR y el cierre de chat enlazan el run final, no un verde de otro SHA.

No se han entrenado M0–M4, ajustado gates, modificado champion, V0, P0, BTC/scheduler/paper, Simulation Engine, Trade Plan o Filing Intelligence. Holdout/OOT siguen excluidos.

**Único siguiente paso:** investigar y cerrar con documentos oficiales las fichas de **2015-03→2017-09**, priorizando las que bloquean la apertura de septiembre de 2015: ese tramo contiene los 25 meses inmediatamente anteriores a la racha actual necesarios para alcanzar 85. La discrepancia de 2014 no debe desviar esa prioridad ni resolverse forzando fechas.

Reproducción: contacto SEC runtime → `scripts/ingest_spy_anchors.py --extend` (partial documentado, exit 1), `scripts/ingest_13f_lists.py --anchor-quarters` (sólo trimestres de anclas verificadas anteriores al holdout), `scripts/build_sp500_anchor_graph.py`, `scripts/gen_d02_extended_audit.py`, `scripts/audit_first_ml_security_identity.py`, `scripts/gen_data_readiness_first_ml.py`. Los reportes no entrenan ni reescriben snapshots/objetivos.
