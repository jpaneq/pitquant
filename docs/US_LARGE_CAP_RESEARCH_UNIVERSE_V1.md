# US Large Cap Research Universe V1

Expansión de datos desde `97743c4`; ningún modelo, target ni resultado futuro nuevo.

Período: 2014-09 → 2021-09 (85 meses). 42,977 security-periods candidatos; 696 securities históricas; 469 emisores con vínculo primario validado. Los CIK candidatos no resueltos no cuentan como emisores verificados.

## Procedencia y selección

La selección nace de las anclas históricas SEC/State Street y los eventos fechados del grafo D02. Se aplica ADR-0056 con el mismo clasificador: réplica de anclas más historia Clenow/Wikipedia de productor independiente. Dos copias de una fuente no añaden independencia. Yahoo es exclusivamente proveedor de mercado.

Los períodos UNVERIFIED/CONFLICTED se excluyen localmente. El informe conserva sus filas, hashes, motivos y casos ambiguos. El identificador de un instrumento no se sustituye por un ticker actual. Nombre legal exacto y ticker de clase en submissions SEC, identificador oficial del instrumento, historial del emisor anterior al período y ausencia de colisión se verifican antes de enlazar el issuer. El registro SEC histórico cik-lookup-data.txt aporta emisores desaparecidos del mapa actual; sólo descubre CIK candidatos. Filings y nombre legal primario deben confirmar historia compatible con el período del instrumento. Una compañía con ticker actual vacío puede usar una pata histórica exacta, pero Yahoo no se acepta para ese ticker terminal sin concordancia de nombre con la identidad primaria. Los enlaces de investigación no certifican completitud global de identidad.

Las sucesiones de securities diferentes no habilitan continuidad de precios: la ventana de 253 sesiones se corta en el inicio legal de la sucesora. Los aliases fechados y las transiciones parciales se conservan como tales. GE/GOOGL/RTX/XOM mantienen los bloqueos de la auditoría anterior.

## Mercado y fundamentales

D05 conserva OHLC RAW, divisa, sesiones, acciones corporativas y reconstrucción determinista. Para deshacer el ajuste retrospectivo de Yahoo se archiva la respuesta completa hasta 2026-10-07; los precios posteriores a 2021-09-30 se descartan antes de normalizar. Sólo los splits posteriores pueden intervenir para recuperar las unidades RAW originales. No se construyen targets ni outcomes. El candidato comprimido contiene únicamente las barras históricas normalizadas.

SEC se procesa con el ingestor existente: accession, header ACCEPTANCE-DATETIME, XBRL primario, available_at, originales y hashes. Companyfacts sigue siendo descubrimiento/validación. Un 404 real cacheado permite usar la recuperación nativa de filings no citados desde su propio XBRL y header; un cache miss, 403, 429 o fallo primario no se convierte en esa excepción. Se mantiene sec-tags-4 sin mappings nuevos. La auditoría calcula exactamente los tres campos fundamentales existentes de First ML; no certifica disponibilidad de todo el feature set ni de labels.

Los sectores SIC no soportados continúan excluidos de fundamentales. SIC y sector actuales son CURRENT_PROFILE_NOT_PIT, metadatos descriptivos, sin features sectoriales nuevas. Todos los cortes de hechos y barras son estrictamente anteriores a la apertura mensual.

## Supervivencia

Referencia descriptiva fechada 2026-08-18, 503 tickers; no se declara composición oficial actual. Resultados sobre securities históricas: `{"CURRENT_REFERENCE_MEMBER": 331, "CURRENT_STATUS_UNRESOLVED": 162, "EXPLICIT_ACQUIRED_OR_SUCCESSOR": 0, "EXPLICIT_BANKRUPT": 0, "EXPLICIT_DELISTED": 0, "PRIMARY_MERGER_PREDECESSOR": 5, "PRIMARY_REPLACEMENT_PREDECESSOR": 14, "REMOVED_FROM_CURRENT_REFERENCE": 189, "REMOVED_OR_REPLACED_HISTORICAL_SECURITY": 14}`.

Explicit lifecycle counts are lower bounds. Removal, a replacement, or a Yahoo 404 does not by itself prove delisting/acquisition/bankruptcy. Unknown cases remain unknown.

La inclusión en el roster no depende de sobrevivir. Sin embargo, la cobertura usable sigue condicionada por resolver identidad histórica y obtener Yahoo: este sesgo residual se cuantifica y no se oculta como un universo sin survivorship bias.

## Reproducción y presupuesto

Usar un checkout aislado desde el HEAD de referencia y el entorno de desarrollo. Crear la copia con `python scripts/scale_us_research_universe.py initialize`. El script rechaza una copia existente y nunca escribe en data/pitquant.db. Configurar PITQUANT_SEC_USER_AGENT sólo en el entorno con un contacto válido; no se almacena en código, artefactos ni logs.

Ejecutar, por orden: `discover`, `historical-discovery`, `identity`, `prices`, `fundamentals` y `python scripts/audit_us_research_scale.py`. fundamentals usa tres descargadores RAW y un único escritor SQL. SEC comparte un límite global de 6,67 solicitudes/s; Yahoo es secuencial, máximo 1/s. Timeout 20s, hasta tres intentos con backoff; 220 documentos nuevos por issuer y cinco fallos de proveedor antes de cerrar su ficha. Se conserva además una reserva operativa de 5 GiB: si se alcanza, las descargas restantes se clasifican como bloqueadas por capacidad, sin borrar originales. Los límites son de ingeniería, no gates científicos.

La copia candidate.db, el archivo content-addressed y data/research/us-universe-scale-v1/cache/requests.jsonl permiten repetir sin red. Las respuestas fallidas también quedan cacheadas; una nueva colección requiere otra revisión explícita, sin borrar originales. Las versiones inmutables se guardan por SHA-256. Reproducir hashes requiere las mismas fuentes archivadas y la copia registrada; una revisión remota distinta es otro candidato.

Todos los casos quedan clasificados y el impacto residual se mide. No se exige evidencia perfecta ni se sustituyen silenciosamente empresas desaparecidas por supervivientes.

## Artefactos

- [Universo y fichas](US_LARGE_CAP_RESEARCH_UNIVERSE_V1.json)
- [Cobertura mensual](US_LARGE_CAP_RESEARCH_COVERAGE_V1.md)
- [Candidato sin targets](US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz)
- [ADR-0063](adr/0063-scale-cross-sectional-us-universe.md)

Dataset candidate SHA-256: `3288c606b108f4ddf77a747f39339ebd9bbb085361b33f90c3c79bb30f8db330`. No reemplaza V0/V1; training_ready=false. Los 45 artefactos científicos protegidos coinciden byte a byte con el HEAD inicial.

dev_adaptive_iteration=2; holdout outcomes=0; OOT outcomes=0; new_fits=0.
