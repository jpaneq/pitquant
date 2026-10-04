# D02/D05 y preparación del primer ML — cierre verificable

HEAD inicial: `85cf086`. Rama: `codex/d02-d05-first-ml-readiness`. No se ha entrenado ningún modelo ni tocado BTC, pesos, champion o holdout.

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
