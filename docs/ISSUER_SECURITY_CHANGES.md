# Cambios emisor / security detectados en el IBEX (generado)

Generado con `scripts/gen_identity_reports.py` **sólo** desde la base local: segmentos del run `7854a476-c1cd-4475-97e5-f3234643abe0` (`identity-engine-2`), snapshots ANCV y la observación BME `9d2f010701a50c42de9d5d5bcac6fd3aa4b57cb253b1cd7533740c78b159c28d`. Las reglas de clasificación son mecánicas; lo que la evidencia no decide queda `UNRESOLVED`. Identidad: no se calcula ningún retorno ni métrica.

## Casos solicitados

| Caso | Detectado | Tipo | Estado |
|---|---|---|---|
| POP 2013 | sí | ISIN_CHANGE_SAME_SECURITY | MULTI_SOURCE_CONFIRMED |
| ITX 2014 | sí | ISIN_CHANGE_SAME_SECURITY | MULTI_SOURCE_CONFIRMED |
| BKIA 2013 | sí | REENTRY_UNDER_DIFFERENT_ISIN | UNRESOLVED |
| BKIA 2017 | sí | ISIN_CHANGE_SAME_SECURITY | MULTI_SOURCE_CONFIRMED |
| AENA 2025 | sí | ISIN_CHANGE_SAME_SECURITY | MULTI_SOURCE_CONFIRMED |
| Ferrovial | sí | ISIN_CHANGE_UNRESOLVED | UNRESOLVED |

## Detalle

### BKIA — 2013-01-02 — REENTRY_UNDER_DIFFERENT_ISIN

- **Estado:** UNRESOLVED
- **Intervalo de membership:** [2011-10-03, 2013-01-02) → [2013-12-23, 2021-03-29)
- **security_id:** antes `eef77e52-cc1f-4866-bd3a-5c12805ae58e` → después `17b007f4-3d39-4d74-958e-3cb3dbca731d` (**distinta**)
- **ISIN:** antes ES0113307039 → después ES0113307021
- **issuer_id:** antes `678cf2c1-d614-403d-a2c7-63feb1e140b2` (BANKIA, S.A.) → después `3ed3fa8a-64ef-467a-a880-d1008539f32b` (BANKIA, S.A.)
- **Evidencia y hashes:**
  - último snapshot del ISIN del primer intervalo: ES0113307039 @ 2012-12-31 [ADMITTED_TO_TRADING] «BKIA/AC 2,00» / «BANKIA, S.A.» emitido 2011-05-31; miembro `5474374e3b7c…` zip `33e28ea29882…` (ANCVSemestral122012.zip)
  - primer snapshot del ISIN del segundo intervalo: ES0113307021 @ 2013-06-30 [ADMITTED_TO_TRADING] «BKIA/AC 1,00» / «BANKIA, S.A.» emitido 2013-04-19; miembro `615bf7d47fcb…` zip `741a17874417…` (ANCVSemestral062013.zip)
  - razón social normalizada idéntica en ANCV: «BANKIA S A» (igualdad de nombre, NO un identificador oficial)
- **Por qué:** issuer_id distintos: el sistema no tiene un vínculo oficial (CIF) entre ambos ISIN, sólo la igualdad de razón social. El ISIN y el security_id cambian entre intervalos. No se infiere por nombre que sea el mismo emisor ni que sea la misma security: UNRESOLVED hasta tener el CIF (consulta ANCV por NIF) o un hecho relevante de canje/agrupación.

### POP — 2013-05-24 — ISIN_CHANGE_SAME_SECURITY

- **Estado:** MULTI_SOURCE_CONFIRMED
- **Intervalo de membership:** [1995-01-02, 2017-06-07)
- **security_id:** antes `e7dab8de-8418-40e9-b32a-e6406d655549` → después `e7dab8de-8418-40e9-b32a-e6406d655549` (misma)
- **ISIN:** antes ES0113790531 → después ES0113790226
- **issuer_id:** antes `f30e53f5-1c60-41e8-b211-9ba2a1ab302a` (BANCO POPULAR ESPAÑOL, S.A.) → después `f30e53f5-1c60-41e8-b211-9ba2a1ab302a` (BANCO POPULAR ESPAÑOL, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0113790531 @ 2012-12-31 [ADMITTED_TO_TRADING] «POP/AC 0,10» / «BANCO POPULAR ESPAÑOL, S.A.» emitido 2005-06-16; miembro `5474374e3b7c…` zip `33e28ea29882…` (ANCVSemestral122012.zip)
  - primer snapshot con el ISIN nuevo: ES0113790226 @ 2013-06-30 [ADMITTED_TO_TRADING] «POP/AC 0,50» / «BANCO POPULAR ESPAÑOL, S.A.» emitido 2013-05-24; miembro `615bf7d47fcb…` zip `741a17874417…` (ANCVSemestral062013.zip)
  - segmento: ISIN change ES0113790531->ES0113790226 (same issuer) at ANCV issue date 2013-05-24
  - segmento: 2013-06-30:anchor:ES0113790226
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre los dos snapshots, el ISIN antiguo desaparece y la razón social no cambia (política ADR-0020: cambio de nominal = mismo emisor y misma security, ISIN fechado; el security_id se mantiene).

### ITX — 2014-07-15 — ISIN_CHANGE_SAME_SECURITY

- **Estado:** MULTI_SOURCE_CONFIRMED
- **Intervalo de membership:** [2001-07-02, abierto)
- **security_id:** antes `10fc3d3d-6a55-4a3a-989c-ddb469994b35` → después `10fc3d3d-6a55-4a3a-989c-ddb469994b35` (misma)
- **ISIN:** antes ES0148396015 → después ES0148396007
- **issuer_id:** antes `9b86e623-7b88-411d-975b-dd389d1954f2` (INDUSTRIA DE DISEÑO TEXTIL, S.A.) → después `9b86e623-7b88-411d-975b-dd389d1954f2` (INDUSTRIA DE DISEÑO TEXTIL, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0148396015 @ 2014-06-30 [ADMITTED_TO_TRADING] «ITX/AC 0,15» / «INDUSTRIA DE DISEÑO TEXTIL, S.A.» emitido 2000-07-20; miembro `38a34c9c1155…` zip `6b825e3e1cd3…` (ANCVSemestral062014.zip)
  - primer snapshot con el ISIN nuevo: ES0148396007 @ 2014-12-31 [ADMITTED_TO_TRADING] «ITX/AC 0,03» / «INDUSTRIA DE DISEÑO TEXTIL, S.A.» emitido 2014-07-15; miembro `6095729c970a…` zip `4fc589e75847…` (ANCVSemestral122014.zip)
  - segmento: ISIN change ES0148396015->ES0148396007 (same issuer) at ANCV issue date 2014-07-15
  - segmento: 2014-12-31:anchor:ES0148396007
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre los dos snapshots, el ISIN antiguo desaparece y la razón social no cambia (política ADR-0020: cambio de nominal = mismo emisor y misma security, ISIN fechado; el security_id se mantiene).

### GRF — 2016-06-30 — ISIN_CHANGE_WINDOW_UNEXPLAINED

- **Estado:** UNRESOLVED
- **Intervalo de membership:** [2008-01-02, abierto)
- **security_id:** antes `db3b0ce6-b241-409b-bfbd-e3a7406acc79` → después `db3b0ce6-b241-409b-bfbd-e3a7406acc79` (misma)
- **ISIN:** antes ES0171996012 → después ES0171996087
- **issuer_id:** antes `94016825-1176-470d-95b9-bf899d76a21a` (GRIFOLS, S.A.) → después `94016825-1176-470d-95b9-bf899d76a21a` (GRIFOLS, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0171996012 @ 2015-12-31 [ADMITTED_TO_TRADING] «GRF/AC A 0,50» / «GRIFOLS, S.A.» emitido 1987-06-22; miembro `852bc60857d8…` zip `7ab8a2a357b2…` (ANCVSemestral122015.zip)
  - primer snapshot con el ISIN nuevo: ES0171996087 @ 2016-06-30 [ADMITTED_TO_TRADING] «GRF/AC A 0,25» / «GRIFOLS, S.A.»; miembro `97ec1b9b0746…` zip `f6be93ce585a…` (ANCVSEMESTRAL062016.zip)
  - segmento: 2015-12-31:anchor:ES0171996012
  - segmento: 2016-06-30:anchor:ES0171996087
  - ventana [2016-01-01, 2016-06-30): PROVISIONAL candidatos ['ES0171996012', 'ES0171996087'] — unexplained window between snapshots
- **Por qué:** Entre el último snapshot del ISIN antiguo y el primero del nuevo no hay fecha oficial del cambio: no se puede decidir si es continuidad o sustitución de security. Queda UNRESOLVED; la ventana sigue PROVISIONAL en el motor.

### REE — 2016-12-31 — ISIN_CHANGE_WINDOW_UNEXPLAINED

- **Estado:** UNRESOLVED
- **Intervalo de membership:** [2005-07-01, abierto)
- **security_id:** antes `31f9e226-d336-4d4f-b796-1e498c2dd427` → después `31f9e226-d336-4d4f-b796-1e498c2dd427` (misma)
- **ISIN:** antes ES0173093115 → después ES0173093024
- **issuer_id:** antes `41a27580-74fc-478e-9209-0a0b7614920b` (RED ELECTRICA CORPORACION, S.A.) → después `41a27580-74fc-478e-9209-0a0b7614920b` (RED ELECTRICA CORPORACION, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0173093115 @ 2016-06-30 [ADMITTED_TO_TRADING] «REE/AC 2,00» / «RED ELECTRICA CORPORACION, S.A.» emitido 1999-05-19; miembro `97ec1b9b0746…` zip `f6be93ce585a…` (ANCVSEMESTRAL062016.zip)
  - primer snapshot con el ISIN nuevo: ES0173093024 @ 2016-12-31 [ADMITTED_TO_TRADING] «REE/AC 0,50» / «RED ELECTRICA CORPORACION, S.A.»; miembro `33fd428aa50f…` zip `3d4f8bae6435…` (ANCVSEMESTRAL122016.zip)
  - segmento: 2016-06-30:anchor:ES0173093115
  - segmento: 2016-12-31:anchor:ES0173093024
  - ventana [2016-07-01, 2016-12-31): PROVISIONAL candidatos ['ES0173093115', 'ES0173093024'] — unexplained window between snapshots
- **Por qué:** Entre el último snapshot del ISIN antiguo y el primero del nuevo no hay fecha oficial del cambio: no se puede decidir si es continuidad o sustitución de security. Queda UNRESOLVED; la ventana sigue PROVISIONAL en el motor.

### BKIA — 2017-06-03 — ISIN_CHANGE_SAME_SECURITY

- **Estado:** MULTI_SOURCE_CONFIRMED
- **Intervalo de membership:** [2013-12-23, 2021-03-29)
- **security_id:** antes `17b007f4-3d39-4d74-958e-3cb3dbca731d` → después `17b007f4-3d39-4d74-958e-3cb3dbca731d` (misma)
- **ISIN:** antes ES0113307021 → después ES0113307062
- **issuer_id:** antes `3ed3fa8a-64ef-467a-a880-d1008539f32b` (BANKIA, S.A.) → después `3ed3fa8a-64ef-467a-a880-d1008539f32b` (BANKIA, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0113307021 @ 2016-12-31 [ADMITTED_TO_TRADING] «BKIA/AC 0,80» / «BANKIA, S.A.» emitido 2013-04-19; miembro `33fd428aa50f…` zip `3d4f8bae6435…` (ANCVSEMESTRAL122016.zip)
  - primer snapshot con el ISIN nuevo: ES0113307062 @ 2017-06-30 [ADMITTED_TO_TRADING] «BKIA/AC 1,00» / «BANKIA, S.A.» emitido 2017-06-03; miembro `d35e4333eacd…` zip `8f59f0501c90…` (ANCVSEMESTRAL062017.zip)
  - segmento: ISIN change ES0113307021->ES0113307062 (same issuer) at ANCV issue date 2017-06-03
  - segmento: 2017-06-30:anchor:ES0113307062
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre los dos snapshots, el ISIN antiguo desaparece y la razón social no cambia (política ADR-0020: cambio de nominal = mismo emisor y misma security, ISIN fechado; el security_id se mantiene).

### FER — 2023-01-01 — ISIN_CHANGE_UNRESOLVED

- **Estado:** UNRESOLVED
- **Intervalo de membership:** [1999-07-01, abierto)
- **security_id:** antes `c3a72758-1b3e-419e-a9db-98cb3d702d20` → después `c3a72758-1b3e-419e-a9db-98cb3d702d20` (misma)
- **ISIN:** antes ES0118900010 → después NL0015001FS8
- **issuer_id:** antes `26daf587-1b8e-45f1-980b-cea1160f73f3` (FERROVIAL, S.A.) → después `—` (—)
- **Evidencia y hashes:**
  - último snapshot con el ISIN probado: ES0118900010 @ 2022-12-31 [ACTIVE_IN_ANCV] «FER/AC 0.20» / «FERROVIAL, S.A.» emitido 2004-09-01; miembro `155ca258be8c…` zip `b48e6e256be6…` (ANCVSEMESTRAL1222.zip)
  - composición vigente BME (2026-10-01, transcripción `9d2f010701a5…`): FER → NL0015001FS8
  - segmento [2023-01-01, 2026-07-01): UNRESOLVED — 2023-06-30:none:-; 2023-12-31:none:-; 2024-06-30:none:-; 2024-12-31:none:-; 2025-06-30:none:-; 2025-12-31:none:-; 2026-06-30:none:-
  - segmento [2026-07-01, abierto): PROVISIONAL — trailing edge after an unresolved run
- **Por qué:** El ISIN probado (ES0118900010) deja de aparecer en ANCV y la composición vigente BME (transcripción, no documento exacto) da NL0015001FS8 para el código FER. Sin documento oficial fechado del ISIN nuevo no se concluye si es redomiciliación (mismo emisor, nueva security), cambio de nominal u otra cosa: UNRESOLVED. Nota: desde 12/2018 ANCV sólo lista ISIN ES, así que la ausencia de un ISIN extranjero no prueba nada.

### AENA — 2025-06-12 — ISIN_CHANGE_SAME_SECURITY

- **Estado:** MULTI_SOURCE_CONFIRMED
- **Intervalo de membership:** [2015-06-22, abierto)
- **security_id:** antes `48975c23-4e54-4751-9aba-a10f0a3bb5f6` → después `48975c23-4e54-4751-9aba-a10f0a3bb5f6` (misma)
- **ISIN:** antes ES0105046009 → después ES0105046017
- **issuer_id:** antes `4c167f16-9d5f-458f-89d1-9f9ed008b149` (AENA, S.M.E., S.A.) → después `4c167f16-9d5f-458f-89d1-9f9ed008b149` (AENA, S.M.E., S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0105046009 @ 2024-12-31 [ACTIVE_IN_ANCV] «AENA/AC 10.00» / «AENA, S.M.E., S.A.» emitido 2014-10-15; miembro `10c0e1ab165a…` zip `0407d3fffd18…` (ANCVSEMESTRAL1224.zip)
  - primer snapshot con el ISIN nuevo: ES0105046017 @ 2025-06-30 [ACTIVE_IN_ANCV] «AENA/AC 1.00» / «AENA, S.M.E., S.A.» emitido 2025-06-12; miembro `739c96ebe234…` zip `4fb8ba691b5e…` (ANCVSEMESTRAL0625.zip)
  - segmento: ISIN change ES0105046009->ES0105046017 (same issuer) at ANCV issue date 2025-06-12
  - segmento: 2025-06-30:anchor:ES0105046017
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre los dos snapshots, el ISIN antiguo desaparece y la razón social no cambia (política ADR-0020: cambio de nominal = mismo emisor y misma security, ISIN fechado; el security_id se mantiene).

