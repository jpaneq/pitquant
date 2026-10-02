# ADR-0022 — Evidencia oficial código ↔ ISIN, transiciones de ISIN y trazas de cobertura

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Amplía:** ADR-0020, ADR-0021 ·
**Migraciones:** `0005`, `0006`, `0007`

## Contexto
Tras ADR-0020, 0 de 190 fechas candidatas del IBEX (primer día hábil de cada mes desde 2011) eran
elegibles: `backtest_universe` falla cerrado si UN miembro no tiene identidad probada. Los
bloqueos eran lagunas de evidencia (`docs/IDENTITY_BLOCKERS.md`): ArcelorMittal (código MTS,
ISIN luxemburgués que la ANCV deja de listar desde 12/2018), Ferrovial (ES → NL), Logista y
Puig (dos líneas ordinarias con la misma etiqueta ANCV), Abengoa clase B, y los splits de
Grifols, Red Eléctrica y Pharma Mar.

## Decisión

### 1. Evidencia oficial fechada (`official_code_isin_evidence`, append-only)
Una fila = una declaración oficial «el código BME C correspondía al ISIN I el día D». Sólo prueba
ese día; la continuidad entre dos días es trabajo del motor. Fuentes aceptadas:

| `source_kind` | Qué es | Salvaguardas |
|---|---|---|
| `BME_FICHA_WAYBACK` | Copia (Internet Archive, forma `id_` sin reescribir) de la ficha oficial antigua de Bolsa de Madrid: ISIN, Ticker y fecha de la propia página | La fecha es el sello de la página, no la de captura; se exige que el valor COTICE (último precio ≤ 7 días antes del sello): una página servida de un valor excluido no es una presencia |
| `BME_BOLETIN_JOIN` | Boletín diario de BME (Barcelona): sección de precios (`MC <código> <nombre>`) + sección de dividendos (`MC <nombre> <ISIN>`) de la MISMA sesión | Unión por nombre corto exacto o prefijo único; lo ambiguo se descarta; se rechaza el boletín si un nombre se repite o casan < 90 %. Distingue Grifols A (`GRF`) de B (`GRF.P`) |
| `BME_INSTRUCCION_OPERATIVA` / `OFFICIAL_DOCUMENT` | Documento oficial con la frase exacta | Se registra sólo si TODAS las frases del registro se encuentran en el original archivado |

### 2. Transiciones de ISIN (`official_isin_transitions`, append-only)
Registran un cambio oficial y fechado de ISIN, con `effective_date` = **primera sesión de
negociación del ISIN nuevo** (no la fecha de emisión ANCV, que es administrativa: Pharma Mar emitió
el ISIN nuevo el 13/07/2020 y negoció el 22/07/2020) y la `continuity` según ADR-0020:
- **SAME_SECURITY**: cambio de nominal de la misma entidad (split, contra-split, agrupación).
  Mismo `security_id`, ISIN fechado.
- **NEW_SECURITY**: fusión o redomiciliación (cambia la entidad jurídica). Security nueva con
  `successor_security_id`, mismo `issuer_id` (continuidad económica del emisor, no identidad
  jurídica), código anterior cerrado en la fecha efectiva.

Una transición sólo entra si cada frase del registro está en cada documento (capa de texto o OCR
con Apple Vision para PDF escaneados) y, cuando hay cambio de nominal, si los nominales de la
ANCV coinciden (`Valor_Nominal`).

### 3. Motor de identidad v4
- Cada declaración oficial exacta es un **punto de presencia** (ancla) para su código e ISIN, aunque
  no haya snapshot ANCV en esa fecha. Un tramo con evidencia exacta se marca
  `EXACT_OFFICIAL_IDENTIFIER`.
- **Desempate de etiquetas** (LOG, PUIG, ABG): sólo evidencia oficial EXACTA que enmarque la fecha
  (mismo ISIN antes y después) o adyacente a ≤ 200 días sin otro ISIN en medio. Una transcripción
  de página renderizada nunca desempata. Clase A nunca se elige por parecido de nombre.
- **Snapshots ANCV sólo-ES** (desde 12/2018): la AUSENCIA de un ISIN extranjero no es evidencia y no
  interrumpe un tramo.
- **Transición oficial**: la frontera es su fecha de negociación; exige que la última evidencia del
  ISIN antiguo sea anterior. Si contradice la evidencia, la ventana queda sin resolver. Sin
  proyección hacia atrás: el ISIN nuevo no se asigna antes de su fecha efectiva.
- Los códigos de un intervalo salen de los eventos inmutables del build, no de `ticker_history`,
  que una ejecución puede editar al cerrar el ticker de un predecesor: el resultado de un run no
  depende de runs anteriores. Una ejecución reutilizada debe coincidir con sus segmentos
  almacenados (`_assert_run_matches`); si la lógica cambia, hay que subir `ENGINE_VERSION`.

### 4. Cobertura de corporate actions con traza (`corporate_action_ingestions`)
`COMPLETE` sólo si existe una ingestión COMPLETADA de una fuente aceptada que cubre todo el
periodo de esa security. Estados: `PROVIDER_UNAVAILABLE`, `NOT_ATTEMPTED`, `ATTEMPTED_FAILED`,
`PARTIAL_PERIOD`, `VERIFIED_COVERAGE`. «No tengo eventos» no es «no hubo eventos»: el número de
eventos es lo que declara el proveedor.

### 5. Fundamentales SEC ligados al emisor
Cada CIK tiene un `issuer` real (`issuer_identifiers`); la pseudo-security queda marcada
`role=ISSUER_ANCHOR` y filings y hechos llevan `issuer_id`. Los fundamentales se aplican a
cualquier security del emisor sin duplicarse.

## Consecuencias y límites
- Las copias de Internet Archive son un archivo de terceros de páginas oficiales; se registran con
  su sello de captura y SHA-256. La unión de boletines se apoya en el nombre corto que BME publica en
  ambas secciones del mismo boletín.
- POP 2013, ITX 2014, BKIA 2017 y AENA 2025 siguen fechados por la emisión ANCV (frontera con
  incertidumbre de días), pendiente de documentos oficiales de inicio de contratación.
- BKIA 2013 y ABG.P (clase A → clase B): la identidad de cada tramo está resuelta, pero el vínculo de
  EMISOR entre las dos securities sigue sin documento (CIF): `UNRESOLVED`.
- Ferrovial: continuidad económica del emisor (mismo `issuer_id`) por la IO de BME y el hecho de
  que la sucesora hereda precio de referencia; la identidad jurídica del emisor no está modelada.
- Pre-2011 permanece `ARCHIVAL_UNRESOLVED` y no bloquea V1.
