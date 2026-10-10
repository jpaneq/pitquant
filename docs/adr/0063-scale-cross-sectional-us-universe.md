# ADR-0063 — Scale cross-sectional US universe before further model complexity

Estado: aceptado para expansión de datos; ningún nuevo experimento autorizado por este ADR.

## Contexto

El experimento anterior utilizó aproximadamente 38–44 emisores por TEST month. La auditoría congelada concluyó CASE E — MIXED: inestabilidad temporal, señal fundamental bruta modesta pero positiva, componente sectorial y sensibilidad al período. Se acepta NO_FURTHER_MODEL_EXPERIMENT_JUSTIFIED sobre el dataset anterior. Sus resultados no se recalculan ni se usan para seleccionar nuevas securities.

## Decisión

Crear US_LARGE_CAP_RESEARCH_UNIVERSE_V1 y US_LARGE_CAP_RESEARCH_DATASET_V1 desde 97743c4 para septiembre de 2014 a septiembre de 2021. Ampliar información transversal antes de aumentar complejidad del modelo. No cambiar targets, features, mappings, gates, champion ni datasets científicos congelados. dev_adaptive_iteration permanece en 2, modelos nuevos=0, holdout outcomes=0, OOT outcomes=0.

La selección histórica procede del grafo D02: anclas SEC/State Street y eventos primarios fechados, corroborados por productores históricos independientes según ADR-0056. OFFICIAL_DIRECT y CORROBORATED_HISTORICAL son aceptables; UNVERIFIED/CONFLICTED excluyen sólo el security-period. Dos copias o historias con el mismo upstream no cuentan dos veces. Yahoo nunca prueba membresía.

Separar GLOBAL_IDENTITY_COMPLETENESS de RESEARCH_IDENTITY_VALIDITY. Resolver por nombres legales exactos, clases, identificadores oficiales, CIK y perfil primario; las colisiones y reorganizaciones sin enlace fechado quedan excluidas. Un ticker no sustituye a una identidad. Una sucesora no recibe precios del predecesor automáticamente: el lookback empieza en su intervalo legal. Las cuatro fichas PARTIAL anteriores siguen bloqueadas. Nuevos enlaces de investigación sólo se escriben en una copia de la base de datos; no cambian el security master de producción.

Conservar Yahoo como proveedor canónico de mercado con D05: RAW, acciones, dividendos, divisa y sesiones. Sólo se auditan precios históricos hasta 2021-09-30. Los splits posteriores archivados pueden deshacer el ajuste del proveedor para recuperar unidades RAW, sin usar precios posteriores ni calcular rentabilidades futuras. Mantener SPY canónico y USD/USD; no inventar FX.

Reutilizar ingestión SEC nativa y sec-tags-4: header con aceptación real, accession, XBRL, available_at y originales hashificados. Companyfacts es descubrimiento/validación. La auditoría fundamental usa exactamente los tres core fields existentes. Missing no es cero. Las familias financieras SIC no soportadas mantienen su exclusión. La metadata sectorial actual es descriptiva, CURRENT_PROFILE_NOT_PIT, nunca predictor nuevo.

Cobertura por mes en las cuatro etapas y por sector, con min/P10/mediana/P90/max. Clases se deduplican por issuer. Identidades desconocidas se cuentan como security-periods pendientes, sin emisores ficticios. Comparar tamaños con la PRIMARY_COMMON_COHORT anterior explicando que el candidato nuevo mide disponibilidad sin el antiguo contrato de labels; no es una comparación de resultados.

## Presupuestos y reproducibilidad

Archivo content-addressed, fuentes/URL/publisher/retrieved_at/SHA, originales, parsed events, evidence tiers y resolver version. Copia aislada de SQLite, tres descargadores RAW, un escritor nativo, limiter SEC global ≤6,67/s, Yahoo ≤1/s, timeout 20s, tres intentos con backoff, 220 documentos nuevos por emisor y corte después de cinco fallos del proveedor. Reutilizar fuentes ya archivadas; ningún test requiere red. Cada revisión local se preserva por SHA; recolecciones nuevas nunca sobrescriben los originales. El contacto SEC sólo vive en el entorno.

El registro histórico SEC de nombres/CIK permite descubrir emisores ausentes del mapa actual; sólo un nombre legal exacto y un perfil primario con historia solapada validan el issuer. El vínculo con la security y el vendor se verifica por separado. Un ticker retirado que Yahoo reutiliza para otro emisor queda excluido. Las primeras fechas de filings observadas son límites conservadores de soporte, no fechas legales de IPO.

Un 404 real y archivado de companyfacts permite la recuperación nativa desde header y XBRL propios de cada filing. Un fallo de autorización, presupuesto o caché nunca equivale a ese 404. No se alteran mappings ni fórmulas. La descarga mantiene una reserva de 5 GiB en disco: al alcanzarla se clasifica el resto como bloqueo de capacidad y se conservan los originales.

Si el presupuesto impide obtener un header, los hechos de companyfacts que el ingestor nativo rechazaría por esa ausencia se excluyen de la entrada y se cuentan de forma agregada. Los originales quedan archivados y cada filing ausente conserva su aviso. Los hechos con filing existente o header cacheado 200 pasan todavía por la validación nativa; no se omite ninguna validación ni se cambia la fecha de disponibilidad. Esto evita generar miles de avisos SQL duplicados durante un cierre por capacidad.

No perseguir perfección: detener al procesar el roster, clasificar todos los casos y cuantificar bloqueos. Registrar ausencia de Yahoo y desconocimiento de lifecycle; no inferir delisting, adquisición o bankruptcy desde una retirada del índice o un 404. La cobertura conseguida puede conservar sesgo de disponibilidad hacia supervivientes; se presenta explícitamente.

## Consecuencias

≥200 emisores por mes es sólo milestone de ingeniería. No existe nuevo gate estadístico. El candidato no reemplaza V0/V1 y no declara TRAINING_READY. El siguiente contrato científico deberá fijarse antes de congelar un experimento estructural único. La recomendación de esta expansión prioriza las pérdidas históricas cuantificadas, sin nuevos fits ni inspección de outcomes.

Los artefactos previos se verifican byte a byte contra el HEAD inicial. No se tocan BTC, Filing Intelligence, Trade Planning, Simulation Engine, holdout ni OOT. La auditoría offline publica cinco hashes (membership, identity, price-universe, fundamental-universe, coverage) y el SHA del candidato comprimido sin targets.
