# ADR-0020 — Emisor ≠ security, snapshots de identidad ANCV y motor de resolución de identidad

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Amplía:** ADR-0002, ADR-0017, ADR-0018 ·
**Migración:** `0004`

## Contexto
1. **El modelo no separaba de verdad emisor y security.** `issuers` y `securities.issuer_id`
   existían, pero los fundamentales CNMV colgaban de una pseudo-security creada a partir del CIF.
   Eso reutiliza `security_id` por comodidad. Una sociedad puede seguir siendo el mismo emisor
   y cambiar la acción negociada: redomiciliación (Ferrovial ES→NL), fusión, canje, nueva
   emisión o cambio de ISIN por cambio de nominal.
2. **Identidad IBEX sin resolver.** El histórico BME prueba la membership en el espacio de
   CÓDIGOS (ADR-0017). Los 138 intervalos eran `IDENTITY_UNRESOLVED`.
3. **Fuente oficial gratuita disponible.** La Agencia Nacional de Codificación de Valores (ANCV,
   CNMV) publica cada junio y diciembre, desde 06/2010, los ISIN activos.

## Decisión

### 1. Emisor y security separados
- **Fundamentales → `issuer_id`.** Se añaden `fundamental_facts.issuer_id` y
  `cnmv_filings.issuer_id`; `security_id` pasa a ser nullable, con
  `CHECK security_id IS NOT NULL OR issuer_id IS NOT NULL`.
- **CNMV.** Resuelve el emisor por CIF (tabla nueva `issuer_identifiers`: CIF, CIK, LEI) y no
  crea securities.
- **SEC.** Sin cambios: sus hechos siguen ligados a la security registrada por CIK.
- **Precios y membership → `security_id`.**
- **`facts_as_of(security_id)`.** Incluye los hechos del emisor de esa security;
  `facts_as_of(None, issuer_id=…)` consulta un emisor directamente.
- **Vínculo emisor ↔ security.** Sólo por evidencia oficial: la consulta ANCV por NIF
  (`/portal/ancv/isin?nif=`) da los ISIN activos de un CIF. Nunca por parecido de nombre.
- **Filas anteriores a 0004.** Son append-only y no se reescriben; la base local se reconstruye
  conservando la anterior (`data/pitquant_dev_v2.db`).

### 2. Snapshots de identidad (`security_identity_snapshots`, append-only)
Cada línea de renta variable de cada distribución ANCV guarda:
- ISIN, razón social del emisor, nombre del valor (etiqueta ANCV), CFI, divisa, nominal;
- «Fecha de emisión» del TXT de ancho fijo;
- fecha de referencia y alcance según el LEAME;
- miembro del zip, SHA-256 del miembro, `archive_id` y versión del parser.

El zip completo pasa por `raw_source_archive` con URL, nombre de fichero, fecha de referencia,
hashes de todos los miembros y la frase del LEAME que define el alcance.

**Lo que prueba un snapshot:** que el ISIN estaba activo (o admitido) en la fecha de
referencia. **No** prueba alta ni baja: nunca se convierte en fecha de inicio o fin.

**Formatos, que cambian** (no se asume uno; un formato desconocido falla cerrado):

| Periodo | Renta variable | TXT | Alcance del TXT según el LEAME |
|---|---|---|---|
| 06/2010–12/2021 | `LVRVaamm.XML` sin CFI | 180 bytes | admitidos a cotización |
| 06/2022–06/2026 (salvo 12/2022) | `LVRVaamm.XML` con `<Cfi>` | 186 bytes | ISIN activos en la base ANCV |
| 12/2022 | `ILVRV` delimitado por `??` (8 campos) | 186 bytes | ISIN activos en la base ANCV |

- **Fecha de referencia.** Se lee del contenido (raíz `CODIGOS_ISIN_{1|2}_{aaaa}` y sellos de
  los miembros) y todas las señales deben coincidir. Nunca se toma del nombre del zip:
  `ANCVSEMESTRAL25.zip` es 12/2025, y 12/2022 mezcla `LV1222` (mmaa) con `LV2212` (aamm).
- **Desde 12/2018 sólo hay ISIN `ES`.** La ausencia de un ISIN extranjero no prueba nada
  (ArcelorMittal en LU, Ferrovial en NL desde 2023).

### 3. `IdentityResolutionEngine` (`security_master/identity.py`)
Combina:
- los intervalos de membership (BME) y el código de cada fecha;
- los snapshots ANCV (ISIN, razón social, etiqueta, fecha de emisión);
- los cambios de ISIN;
- las observaciones oficiales código ↔ ISIN, como la composición vigente BME (transcripción,
  no exacta).

El ancla es el ISIN; la etiqueta ANCV sólo sirve para encontrar candidatos. No es el ticker:
Redeia figura como `REDEIA/AC` y su código BME es RED.

| Estado | Regla (verificable con tests) | ¿Backtest canónico? |
|---|---|---|
| `EXACT_OFFICIAL_IDENTIFIER` | Un documento oficial archivado declara código ↔ ISIN en una fecha del segmento | sí |
| `MULTI_SOURCE_CONFIRMED` | Ver los criterios bajo la tabla | sí |
| `PROVISIONAL` | Sólo snapshots que rodean el intervalo, una sola fuente, ventana entre snapshots sin explicar o etiqueta ambigua | no |
| `UNRESOLVED` | Sin evidencia | no |

Criterios de `MULTI_SOURCE_CONFIRMED`:
- **Anclaje.** Al menos un snapshot ESTRICTAMENTE dentro del intervalo con una única línea de
  acción ordinaria (`AC`, CFI `E*`) cuya etiqueta coincide con el código BME de esa fecha.
- **Continuidad.** Los demás snapshots del tramo contienen el mismo ISIN, con cualquier
  etiqueta.
- **Bordes.** Heredan el estado si el ISIN aparece fuera del intervalo, o si es un alta nueva
  (etiqueta libre en el snapshot anterior y emitido antes del inicio).
- **Cambio de ISIN.** Es la misma security sólo si el ANCV fecha la emisión del nuevo ISIN entre
  los dos snapshots, el antiguo desaparece y la razón social no cambia (cambio de nominal). Si
  no, la ventana entre snapshots queda `PROVISIONAL`.
- **Tramo posterior al último snapshot ANCV.** Exige que la composición vigente BME dé el mismo
  ISIN.

Un ticker solo nunca basta. La etiqueta GAM reutilizada en 2023 por otra sociedad no puede
contaminar el intervalo de Gamesa 2013–2017, porque sólo anclan los snapshots interiores; hay
un test de regresión.

**Persistencia.** `identity_resolution_runs` y `membership_identity_segments` son append-only.
Cada segmento probado asigna el ISIN a una security mediante `identifier_history`, con
validez = unión de los segmentos probados:
- si el ISIN ya tenía dueño (reentrada), es ese dueño: un ISIN nunca recibe dos `security_id`;
- si no, la security del intervalo.

**`backtest_universe(..., canonical_start=)`.**
- Acepta un miembro de código sólo si su segmento en la fecha es EXACT o MULTI_SOURCE.
- Devuelve la security probada.
- Falla cerrado ante cualquier otro caso.

### 4. Filas BME sin marcador de leyenda
Se clasifican sólo con continuidad de ISIN: la etiqueta antigua antes y la nueva después
(ANCV reetiqueta con su propio calendario; ventana de 4 años), con el ISIN presente en TODOS
los snapshots intermedios. Resultado:

| Situación | Clasificación |
|---|---|
| Mismo ISIN antes y después | `TICKER_CHANGE` |
| ISIN distintos y el antiguo sigue activo | `INDEX_TURNOVER` |
| Cualquier otra | `UNRESOLVED` |

Nunca se infiere por nombre parecido.

### 5. Periodo canónico V1
- `canonical_period.start = 2011-01-01` (configuración).
- Lo anterior se conserva como `ARCHIVAL / NON_CANONICAL_FOR_V1` y sus carencias no bloquean V1.
- `data-readiness` distingue `IBEX_IDENTITY_2011_PLUS` de `IBEX_IDENTITY_PRE_2011`.
- No cambia el holdout.

## Consecuencias
- **La identidad IBEX 2011+ pasa a medirse** (`docs/IBEX_COVERAGE_REPORT.md`).
- **Elegibilidad del build.** Sigue sin ser elegible para validación final mientras la fuente de
  membership sea PROVISIONAL (ancla transcrita).
- **Pendiente sin fuente oficial gratuita localizada:**
  - ISIN extranjeros (MTS en LU, FER en NL desde 2023);
  - clases de acciones con código BME propio (ABG.P frente a la etiqueta ANCV `ABG/AC B`);
  - ventanas de cambio de ISIN sin fecha de emisión (REE 2016, GRF 2016).
- **`TICKER_CHANGE` probado no implica rebautizo.** GAM→SGRE (fusión con Siemens Wind Power) y
  CRI→CABK (reorganización Criteria/CaixaBank) son cambios de código sobre la misma acción.
  El evento societario subyacente se modela aparte como corporate action (ADR-0021), con
  fuente oficial.
