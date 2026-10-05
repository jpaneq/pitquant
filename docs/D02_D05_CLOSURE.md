# D02/D05 y preparación del primer ML — estado vigente

Iteración crítica desde HEAD `f4c01f1`, rama `codex/d02-d05-first-ml-readiness`, PR #1. No se ha entrenado. La referencia vigente es DATA_READINESS_FIRST_ML.json y D02_CRITICAL_PATH_RESULT.json.

D02: 60 → **72/141 meses utilizables READY**; racha 60 → **72/85**, membresía 72, folds 0 → **1/3**. Se cerraron 57 de las 93 fichas iniciales de la ventana 2015-09..2017-09. Quedan 36 fichas dentro de esa ventana y 131 fuera; estas últimas quedan inventariadas fuera del objetivo de cierre.

Se ha trabajado desde el mes más reciente hacia atrás. Las pruebas compartidas recuperaron 2017-04..09 y 2016-10..2017-03. La revisión posterior de identidad detectó nueve instrumentos débiles en esos meses: se resolvieron por formatos legales exactos de las listas SEC, no por similitud. La racha no se declara utilizable hasta comprobar tanto membresía como identidad.

El siguiente segmento 2016-03→09 conserva **Under Armour Class C** como bloqueo primario: el 10-K verifica el reparto y la cotización inicial, pero falta un documento oficial de S&P que fije el alta en el índice. Las búsquedas y el documento insuficiente se conservan con hashes. No se infiere que no exista un documento; no se convierte una fecha de descubrimiento en evento primario. Las otras fichas de los trece meses pendientes quedan empaquetadas con accession/hash de anclas, decisión afectada y condición de cierre.

Detalle de cada mes, transiciones, fuentes oficiales, extracción de tablas, clases y precisión temporal: D02_CRITICAL_PATH_FIRST_ML.md/.json, D02_CRITICAL_PATH_RESULT.json, D02_CRITICAL_IDENTITY_RESOLUTIONS.json, D02_CRITICAL_DOCUMENT_BREAKS.json, D02_CRITICAL_WEAK_IDENTITY.json, D02_CRITICAL_SOURCE_ATTEMPTS.json y ADR-0054. Se mantienen los originales y las versiones previas append-only. Una ficha Broadcom Ltd cambió de contradicción a alta sin prueba y sigue pendiente: no se cuenta como resuelta. La hora legal UTC de L-3/Alcoa no está verificada; los valores almacenados son límites para reconstrucción mensual y se documenta esa precisión, sin sobreescribir notas inmutables.

## Mercado

Yahoo es el proveedor canónico aprobado, tier VENDOR. ADR-0050 fija yahoo-market-data-v1: OHLC bruto reconstruido desde el vintage, adjusted close separado para QA, splits y dividendos normalizados y archivo original con SHA. Volumen anterior a splits se deja NULL si no puede reconstruirse. La disponibilidad de mercado al cierre de sesión es distinta de retrieved_at/ingested_at reales; las consultas con ingested_before respetan el vintage. FX sigue disponible a las 00:00 UTC del día siguiente.

Las ingestas AAPL y MSFT conservan la security SEC existente y enlazan el issuer con su submission oficial archivada. Ambas tienen 3.961 barras Yahoo y 59/63 acciones corporativas; ENG.MC tiene 4.029 barras y 30 acciones. QA READY para las tres. EODHD histórico se conserva pero queda excluido de investigación canónica.

**Corrección del diagnóstico de ENG:** no se reproduce la cifra de 22 barras del encargo. La copia SQLite anterior a esta intervención contiene exactamente cuatro precios oficiales BME, entre 2023-12-19 y 2024-07-02. `scripts/ingest_real_market_ca.py` seleccionaba cuatro boletines alrededor de dos fechas ex-dividendo (BULLETIN_DAYS), para validar eventos; no era una descarga de historia completa. No hay evidencia para atribuir 22 barras a un fallo del proveedor.

QA: 103 series incluyendo tres benchmarks; 85 READY y 18 BLOCKED. Todas las series US pasan; fuera de US quedan OHLC imposibles, divisas incompatibles o cobertura de acciones no verificable. Los 14 originales que el normalizador estricto rechaza y cada fecha inválida se conservan y listan en D05_YAHOO_QA.json. No se corrigen OHLC ni divisas por aproximación.

SPY y URTH son ETF_PROXY/PROXY_ACCEPTABLE, no índices oficiales. ^IBEX sigue PRICE_RETURN_ONLY y no proporciona retorno total. Se buscó una serie Yahoo IBEX 35 TR sin identificar un símbolo verificable. BME identifica el índice con dividendos como ES0SI0000047 ([ficha oficial](https://www.bolsasymercados.es/es/bme-exchange/indices/ficha.ibex-35-con-dividendos-es0si0000047.html)). INDST.MC no sustituye al IBEX 35 TR: corresponde al small cap. URTH+FX se mantiene como diagnóstico para España; el primer ML usa alcance US explícito.


## Cuatro identidades de research y cobertura

XOM, RTX, GOOGL y GE siguen **PARTIAL** como vínculos de la serie de research al instrumento histórico. Las fuentes y acciones mínimas están en FIRST_ML_SECURITY_IDENTITY.json. Esto es distinto de cerrar las identidades de miembros del universo mensual; no se mapearon precios a otro issuer o clase.

`required_securities=100` permanece sin cambios. Está aprobada la nota metodológica para **diseñar después** un reemplazo estadístico del gate global de 100; no se aplica 100→51 ni se crea un umbral que fuerce READY. El primer experimento sigue US-only.

## Matriz vigente

| Gate | Estado |
|---|---|
| D02_MONTHLY_RESEARCH_READY | BLOCKED |
| US_SECURITY_IDENTITY_READY | PARTIAL |
| D05_READY | READY |
| BENCHMARK_RETURN_BASIS_READY | READY |
| RESEARCH_SECURITY_COVERAGE_READY | BLOCKED |
| US_FUNDAMENTALS_READY | READY |
| HOLDOUT_SEALED | READY |
| RESEARCH_DATA_READY | BLOCKED |
| FIRST_ML_BASELINE_READY | BLOCKED |

La factibilidad de calendario no garantiza etiquetas maduras: el holdout 2022-10-01..2025-09-30 y el OOT >=2025-10 permanecen excluidos. No se han regenerado features/objetivos ni entrenado M0–M4. Tampoco se toca BTC/scheduler/paper, Simulation Engine, Trade Plan, Filing Intelligence, V0/P0 o champion/master.

## Validación

Validación local: ruff y formato limpios; mypy strict sin errores en 213 módulos; SQLite **974 passed, 3 skipped**, PIT **389 passed sin skips**, PostgreSQL estricto **20 passed**. El CI del SHA publicado se enlaza en la PR y el cierre del chat. No hay cambio de esquema ni migración nueva; head 0027. Docker se comprueba en su job de GitHub Actions porque no está instalado localmente. Frontend/E2E no se han modificado; sus jobs de CI siguen siendo obligatorios.

**Único siguiente paso:** obtener y archivar el aviso oficial de S&P para el alta de Under Armour Class C de abril de 2016, y repetir el segmento antes de avanzar hacia septiembre de 2015. Se conserva el objetivo de 85 meses y tres folds; todavía no procede entrenar.
