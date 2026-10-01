# Condiciones del propietario para D-01…D-03 (2026-10-01)

Confirmo D-01, D-02 y D-03 con las siguientes condiciones y modificaciones obligatorias.

D-01 — FUNDAMENTALES EE. UU.

APROBADO: utilizar SEC EDGAR como fuente primaria.

Implementar un SECEdgarFundamentalProvider.

No utilizar companyfacts como única fuente canónica point-in-time.

Arquitectura requerida:

1. Utilizar EDGAR Submissions para:
    * CIK;
    * accession number;
    * form;
    * filing date;
    * filing metadata.
2. Recuperar y conservar el filing/XBRL original asociado a cada accession.
3. Recuperar del header EDGAR:
    * ACCEPTANCE-DATETIME.
4. Cada hecho financiero debe quedar asociado como mínimo a:
    * security_id;
    * cik;
    * accession_number;
    * form;
    * period_start;
    * period_end;
    * filed_date;
    * accepted_at;
    * taxonomy;
    * concept;
    * unit;
    * value;
    * source_document;
    * amendment;
    * ingested_at.
5. Una reexpresión posterior NO puede modificar retrospectivamente un snapshot antiguo.

Ejemplo:

Un filing de 2025 puede presentar cifras comparativas corregidas de 2023.

Esas cifras corregidas:

NO pueden aparecer en un snapshot de 2024.

El motor debe seleccionar la versión del dato que estaba disponible realmente en as_of.

6. Conservar las diferentes versiones del mismo hecho.

Nunca hacer UPDATE destructivo del dato anterior.

Usar versionado append-only.

7. companyfacts puede utilizarse para:
    * descubrimiento;
    * descarga eficiente;
    * validación;
    * cache.

Pero la procedencia temporal debe resolverse mediante accession/filing.

8. Implementar:

available_at

diferenciado de:

period_end.

9. Añadir tests:

* test_later_restatement_does_not_rewrite_history
* test_companyfacts_later_fact_not_visible_early
* test_fact_bound_to_accession
* test_amended_filing_visibility
* test_acceptance_datetime_controls_availability
* test_same_period_multiple_filings

10. Para evitar ambigüedad intradía, hacer configurable una política conservadora de disponibilidad.

Inicialmente:

un filing aceptado después del cierre no estará disponible para una señal calculada al cierre de esa misma sesión.

Será utilizable desde la siguiente ejecución elegible.

11. Primera cobertura fundamental recomendada:

2011/2012 → actualidad.

No dedicar todavía recursos importantes a normalizar fundamentales pre-XBRL.

Diseñar el sistema para permitir backfill anterior posteriormente.

⸻

D-02 — HISTÓRICO DE CONSTITUYENTES S&P 500

APROBADO CON CONDICIÓN.

Crear interfaz:

SP500MembershipProvider

No acoplar el dominio a un proveedor.

Fuente canónica de producción

Utilizar histórico oficial/licenciado de S&P Dow Jones Indices cuando esté disponible.

Debe proporcionar, directa o indirectamente:

* constituyente;
* identificador;
* fecha efectiva;
* entrada;
* salida;
* cambios de identificador;
* corporate actions relevantes.

Proveedor provisional

Puede implementarse además:

SPDJIAnnouncementReconstructionProvider

que reconstruya membership mediante:

* snapshot conocido;
* anuncios oficiales S&P;
* additions;
* deletions;
* fechas efectivas.

Pero marcarlo:

PROVISIONAL_RESEARCH_SOURCE.

No considerar los resultados obtenidos con una cobertura no verificada como backtest definitivo.

No utilizar Wikipedia, Kaggle o repositorios comunitarios como fuente canónica.

Se pueden utilizar únicamente como:

* cross-check;
* detección de discrepancias;
* QA.

Validaciones obligatorias

Para cada fecha:

* ninguna duplicidad accidental;
* aproximadamente 500 compañías, admitiendo múltiples share classes;
* toda entrada debe tener causa/evento;
* toda salida debe tener causa/evento;
* conservar empresas desaparecidas;
* no inferir membership a partir de compañías actuales.

Añadir:

membership_source

source_event_id

effective_from

effective_to

source_confidence

raw_source_hash.

Guardar una copia/versionado de la fuente utilizada en cada ingestión para garantizar reproducibilidad aunque el proveedor corrija datos posteriormente.

⸻

D-03 — HISTÓRICO IBEX 35

APROBADO.

Cambiar ligeramente la estrategia propuesta.

Fuente primaria

Utilizar el documento oficial de BME:

Composición histórica – IBEX 35.

Contiene eventos desde 1991.

Parsearlo como event stream.

Cada registro debe producir:

* fecha efectiva;
* additions;
* deletions;
* event type;
* source;
* source version/hash.

Fuente secundaria

Utilizar los Avisos de Índices y los comunicados del Comité Asesor Técnico de BME para:

* verificar eventos;
* actualizar incrementalmente;
* resolver casos ambiguos;
* conservar announcement date frente a effective date.

Guardar separadamente:

announced_at

y:

effective_at.

No son equivalentes.

REQUISITO CRÍTICO: CAMBIO DE TICKER

El documento de BME distingue visualmente:

* revisión extraordinaria;
* cambio de código/ticker.

NO interpretar automáticamente cada pareja:

deletion X
+
addition Y

como dos securities distintas.

Ejemplos históricos como:

GAS → NTGY

o:

REE → RED

deben resolverse como cambio de símbolo cuando corresponda.

El mismo emisor/security debe conservar:

security_id

y crear dos registros en:

ticker_history.

Añadir:

event_type = TICKER_CHANGE

diferente de:

INDEX_ADD

INDEX_DELETE

EXTRAORDINARY_REVIEW.

El parser debe conservar esta información aunque provenga de formato/color del PDF.

Si la extracción automática no permite determinar con fiabilidad el significado visual, resolver el evento mediante el aviso BME correspondiente; NO adivinar.

Añadir tests específicos:

* test_ibex_ticker_change_preserves_security_id
* test_gas_to_ntgy_not_membership_turnover
* test_ree_to_red_not_membership_turnover
* test_ibex_extraordinary_review
* test_announcement_date_not_effective_date
* test_ibex_membership_reconstruction_from_events

⸻

CAMBIO ADICIONAL — POSTGRESQL IMMUTABILITY TEST

Actualmente existe un test skipped porque requiere PostgreSQL real.

Esto es aceptable localmente, pero NO considerar esta parte verificada hasta que CI la haya ejecutado.

Crear un job CI específico con PostgreSQL real.

Debe:

1. ejecutar tests de triggers;
2. no permitir SQLite como sustituto;
3. fallar si cualquiera de esos tests queda skipped;
4. fallar si se ejecutan cero tests de la categoría PostgreSQL.

El objetivo es impedir un falso CI verde producido porque los tests se omitieron.

Añadir, si no existe:

test_prediction_update_rejected

test_prediction_delete_rejected

test_snapshot_update_rejected

test_snapshot_delete_rejected.

⸻

RAW SOURCE ARCHIVE

Añadir desde esta fase una capa:

raw_source_archive

para las fuentes externas importantes.

Guardar:

* provider;
* source URL/identifier;
* retrieved_at;
* publication/acceptance timestamp;
* SHA-256;
* mime type;
* raw payload/file reference;
* parser version.

Nunca depender exclusivamente de que una URL externa continúe existiendo o conserve exactamente el mismo contenido.

Esto permitirá reconstruir por qué el sistema creó un determinado universo o fundamental histórico.

⸻

CRITERIO DE TERMINACIÓN DE ESTA FASE

No avanzar a scoring únicamente porque el conector “descargue datos”.

D-01 a D-03 se consideran terminados cuando podemos demostrar:

Para una fecha histórica T:

1. qué compañías pertenecían realmente al universo;
2. qué ticker tenía cada security en T;
3. qué fundamentales estaban realmente publicados en T;
4. de qué filing/evento procede cada dato;
5. cuándo pasó a estar disponible;
6. que una modificación posterior no cambia el snapshot de T;
7. que repetir la reconstrucción produce exactamente el mismo resultado.

Después de cumplir esto, avanzar a market data/fundamentals completos y posteriormente al Feature/Scoring Engine.