# ADR-0056 — D02 membership evidence tiers and fail-soft exclusions

Estado: APLICADO. Decisión expresa del propietario en esta iteración, continuación de `01eb216`. Sustituye la exigencia de completitud global de D02 para el primer ML; mantiene la derivación temporal de ADR-0055 y el universo diario/backtest estricto.

## Decisión

VALIDITY y COMPLETENESS son diferentes. D02 pregunta si todas las observaciones incluidas tienen membership histórica soportada. El futuro coverage contract determinará si son suficientes. Una security-period no resuelta se excluye; no bloquea automáticamente el mes. Un mes sin ninguna fila soportada sigue BLOCKED. No se modifica `required_securities=100`, ni se ejecuta entrenamiento.

- OFFICIAL_DIRECT: documento del proveedor del índice que prueba directamente security/evento/fecha. Aceptado con identidad soportada.
- CORROBORATED_HISTORICAL: al menos dos productores independientes, mismo instrumento/clase, evento y fecha; identidad/corporate event primarios cuando corresponde; sin contradicción material. Aceptado para research.
- UNVERIFIED: evidencia insuficiente. Periodo excluido.
- CONFLICTED: versiones materialmente incompatibles. Periodo excluido, sin elegir arbitrariamente.

La identidad del productor/upstream se declara y se audita con documentación archivada. Dos dominios, mirrors o hashes repetidos no son dos corroboraciones. Upstream desconocido no añade independencia. Yahoo Finance es CANONICAL_MARKET_PRICE_PROVIDER para OHLCV, acciones corporativas, FX y benchmarks; no es membership authority.

## Periodos estables y eventos

Para eventos ADD/REMOVE, las fuentes Tier 2 deben coincidir en la fecha efectiva del evento. No se deduce esa fecha del inicio de cotización.

Para estados mensuales estables se certifica `MEMBER_AT_SESSION_OPEN` en la fecha de decisión, no una fecha ADD inventada: replay concordante de las composiciones SEC de SPY que acotan el periodo y una historia independiente de membership que coincide. Las incertidumbres de fecha, identidades débiles y conflictos se excluyen localmente incluso si dos sets coinciden accidentalmente. Un ticker histórico puede comprobarse con una pata oficial exacta del mismo instrumento anterior a la decisión. CLASS_SET prueba el conjunto de clases, nunca el emparejamiento ticker/clase. El ticker es únicamente una comprobación adicional después del puente exacto de nombre/clase e identidad instrumental; nunca resuelve la identidad. No se equiparan securities legales de una sucesión para introducir la serie del sucesor antes de su periodo.

Una ausencia concordante se registra separadamente como NON_MEMBER, no como falta de evidencia. Por ello las pérdidas por evidencia no incluyen automáticamente todas las filas anteriores a la incorporación de una compañía.

## Under Armour

Se acepta Class C, security `ea33aaa6-2990-475f-b03d-3852d591c274`, ADD efectivo 2016-04-08, como CORROBORATED_HISTORICAL. Fuentes de membership: original 1996–2019 distribuido con Trading Evolved por Clenow, conservado por FJA; cambios Wikipedia extraídos y conservados en 2021 por Analyzing Alpha. La documentación de ambos orígenes y los bytes originales están archivados. El original Clenow y el historial Wikipedia coinciden en ADD 2016-04-08. El ticker UA del fichero reconstruido es una etiqueta normalizada de Class C, no prueba de que cotizase como UA en abril: SEC conserva UA.C hasta diciembre. Las actualizaciones FJA posteriores a 2019 usan Wikipedia y no se cuentan como otro productor independiente de Wikipedia.

SEC 10-K y OCC 38727 soportan instrumento/clase, distribución y cronología de tickers, no una declaración oficial S&P. Class A y Class C siguen separadas; issuer común no autoriza una fusión. UA / UA.C / UAA conservan sus periodos fechados. La fecha aceptada no se etiqueta OFFICIAL_DIRECT. No se sigue buscando S&P para este bloqueo. Una promoción posterior exige evidencia nueva y una nueva revisión; una contradicción exige excluir/revisar, no modificar el pasado silenciosamente. El ADD no mantiene membership después de una retirada verificada.

## Estado y persistencia

`d02-membership-evidence-v1` produce un ledger por security/decision_session con eligibility, tier, motivo, versión, enlaces instrumentales y provenance. Se archiva como JSON content-addressed en `raw_source_archive`, que ya es append-only por ORM y triggers PostgreSQL. No hay cambio de esquema. El ledger incluye el hash del código resolver. Correcciones generan otra fila/hash; repetición idéntica reutiliza la misma revisión. La lectura revalida el hash y la versión.

Las evidencias son referencia retrospectiva, nunca features ni información que se pretenda disponible en T. Se conserva el reloj real de retrieval/SEC acceptance; no se retrodata. No se borran securities, precios, fundamentales, snapshots, targets ni fuentes. La reconstrucción estricta no cambia ni publica eventos canónicos nuevos.

La función única `first_ml_eligibility` exige el ledger fijado en las fechas cubiertas por la política y excluye una fila ausente/desconocida/conflictiva. Fuera del intervalo requerido continúa el régimen estricto anterior. Folds: TRAIN labels maduros al fit, purge/embargo intactos, doce meses TEST íntegros, sin outcomes de holdout/OOT. ML_ELIGIBLE permanece NOT_YET_EVALUATED.

## Investigación acotada y limitaciones

Las 49 fichas se reevaluaron contra el inventario primario existente y las dos historias archivadas. UA satisface el nuevo contrato; 47 fichas quedan UNVERIFIED y Chubb queda CONFLICTED por retirada oficial incompatible con el ancla posterior. Ninguno de esos 48 eventos/vínculos se considera resuelto por ticker o parecido de nombre. Se excluyen sus periodos inciertos, conservando fichas y anclas. No se prolonga la búsqueda de documentos perfectos ni se inventan transiciones de identidad.

Completitud y sesgo: por mes se publican configuradas, resueltas, incluidas, UNVERIFIED, CONFLICTED, ausencias verificadas, issuers, sectores descriptivos, filas perdidas y porcentajes. La selección es outcome-blind. El universo configurado sigue siendo el mismo subconjunto US de 55 securities: cerrar validez temporal no elimina su limitación de supervivencia ni certifica ESS o suficiencia estadística. Las features/ranks almacenadas no se recalculan; ningún modelo las consume en esta iteración. El contrato de coverage deberá revisar esa limitación antes de autorizar entrenamiento.

## Reproducción

Con el archivo local verificado: `PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db .venv/bin/python scripts/gen_data_readiness_first_ml.py`, seguido de `.venv/bin/python scripts/gen_d02_critical_report.py`. Ambos nombres anteriores del generador de camino crítico delegan en el informe vigente. La ingesta acotada inicial es `scripts/ingest_d02_tier_sources.py`; no se ejecuta red al reconstruir el ledger desde su manifest. El resultado guarda el hash del resolver y el original de su código en el archivo append-only.
