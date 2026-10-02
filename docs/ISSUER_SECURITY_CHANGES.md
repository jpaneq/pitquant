# Cambios emisor / security detectados en el IBEX (generado)

Generado con `scripts/gen_identity_reports.py` **sólo** desde la base local: segmentos del run `abf041cd-47d5-459b-8e71-82cc5660b632` (`identity-engine-4`), snapshots ANCV y la observación BME `9d2f010701a50c42de9d5d5bcac6fd3aa4b57cb253b1cd7533740c78b159c28d`. Las reglas de clasificación son mecánicas; lo que la evidencia no decide queda `UNRESOLVED`. Identidad: no se calcula ningún retorno ni métrica.

## Casos solicitados

| Caso | Detectado | Tipo | Estado |
|---|---|---|---|
| POP 2013 | sí | ISIN_CHANGE_ANCV_ISSUE_DATE | MULTI_SOURCE_CONFIRMED |
| ITX 2014 | sí | ISIN_CHANGE_ANCV_ISSUE_DATE | EXACT_OFFICIAL_IDENTIFIER |
| BKIA 2013 | sí | REENTRY_UNDER_DIFFERENT_ISIN | UNRESOLVED |
| BKIA 2017 | sí | ISIN_CHANGE_ANCV_ISSUE_DATE | MULTI_SOURCE_CONFIRMED |
| AENA 2025 | sí | ISIN_CHANGE_ANCV_ISSUE_DATE | EXACT_OFFICIAL_IDENTIFIER |
| Ferrovial | sí | ISIN_CHANGE_NEW_SECURITY | EXACT_OFFICIAL_IDENTIFIER |
| MTS 2017 | sí | ISIN_CHANGE_OFFICIAL_TRANSITION | EXACT_OFFICIAL_IDENTIFIER |
| GRF 2016 | sí | ISIN_CHANGE_OFFICIAL_TRANSITION | EXACT_OFFICIAL_IDENTIFIER |
| REE 2016 | sí | ISIN_CHANGE_OFFICIAL_TRANSITION | EXACT_OFFICIAL_IDENTIFIER |
| PHM 2020 | **NO DETECTADO** | — | — |

## Detalle

### ABG.P — 2012-10-26 — REENTRY_UNDER_DIFFERENT_ISIN

- **Estado:** UNRESOLVED
- **Intervalo de membership:** [2008-01-02, 2012-10-26) → [2012-10-26, 2013-07-01)
- **security_id:** antes `c9f8cc7a-baa6-433e-b60d-843314195902` → después `e6eaf5b7-b5ab-443f-80d5-9dd890ca14d5` (**distinta**)
- **ISIN:** antes ES0105200416 → después ES0105200002
- **issuer_id:** antes `b311d3c4-349f-4ddc-ad1b-8938ecc6c58f` (ABENGOA, S.A.) → después `8963cf72-53f0-47e5-8876-b07af424178f` (ABENGOA, S.A.)
- **Evidencia y hashes:**
  - último snapshot del ISIN del primer intervalo: ES0105200416 @ 2026-06-30 [ACTIVE_IN_ANCV] «ABG/AC A 0.02» / «ABENGOA, S.A.» emitido 2001-07-26; miembro `3d8f003bc264…` zip `338cb8d43afe…` (Semestral0626.zip)
  - primer snapshot del ISIN del segundo intervalo: ES0105200002 @ 2012-12-31 [ADMITTED_TO_TRADING] «ABG/AC B 0,01» / «ABENGOA, S.A.» emitido 2011-11-04; miembro `5474374e3b7c…` zip `33e28ea29882…` (ANCVSemestral122012.zip)
  - razón social normalizada idéntica en ANCV: «ABENGOA S A» (igualdad de nombre, NO un identificador oficial)
- **Por qué:** issuer_id distintos: el sistema no tiene un vínculo oficial (CIF) entre ambos ISIN, sólo la igualdad de razón social. El ISIN y el security_id cambian entre intervalos. No se infiere por nombre que sea el mismo emisor ni que sea la misma security: UNRESOLVED hasta tener el CIF (consulta ANCV por NIF) o un hecho relevante de canje/agrupación.

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

### POP — 2013-05-24 — ISIN_CHANGE_ANCV_ISSUE_DATE

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
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre la última evidencia del antiguo y la primera del nuevo, el antiguo desaparece y la razón social no cambia (cambio de nominal = misma security). La fecha es la de EMISIÓN ANCV (administrativa), no una fecha oficial de inicio de contratación: frontera con incertidumbre de días.

### ITX — 2014-07-15 — ISIN_CHANGE_ANCV_ISSUE_DATE

- **Estado:** EXACT_OFFICIAL_IDENTIFIER
- **Intervalo de membership:** [2001-07-02, abierto)
- **security_id:** antes `10fc3d3d-6a55-4a3a-989c-ddb469994b35` → después `10fc3d3d-6a55-4a3a-989c-ddb469994b35` (misma)
- **ISIN:** antes ES0148396015 → después ES0148396007
- **issuer_id:** antes `9b86e623-7b88-411d-975b-dd389d1954f2` (INDUSTRIA DE DISEÑO TEXTIL, S.A.) → después `9b86e623-7b88-411d-975b-dd389d1954f2` (INDUSTRIA DE DISEÑO TEXTIL, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0148396015 @ 2014-06-30 [ADMITTED_TO_TRADING] «ITX/AC 0,15» / «INDUSTRIA DE DISEÑO TEXTIL, S.A.» emitido 2000-07-20; miembro `38a34c9c1155…` zip `6b825e3e1cd3…` (ANCVSemestral062014.zip)
  - primer snapshot con el ISIN nuevo: ES0148396007 @ 2014-12-31 [ADMITTED_TO_TRADING] «ITX/AC 0,03» / «INDUSTRIA DE DISEÑO TEXTIL, S.A.» emitido 2014-07-15; miembro `6095729c970a…` zip `4fc589e75847…` (ANCVSemestral122014.zip)
  - segmento: ISIN change ES0148396015->ES0148396007 (same issuer) at ANCV issue date 2014-07-15
  - segmento: 2014-12-31:anchor:ES0148396007
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre la última evidencia del antiguo y la primera del nuevo, el antiguo desaparece y la razón social no cambia (cambio de nominal = misma security). La fecha es la de EMISIÓN ANCV (administrativa), no una fecha oficial de inicio de contratación: frontera con incertidumbre de días.

### GRF — 2016-01-04 — ISIN_CHANGE_OFFICIAL_TRANSITION

- **Estado:** EXACT_OFFICIAL_IDENTIFIER
- **Intervalo de membership:** [2008-01-02, abierto)
- **security_id:** antes `db3b0ce6-b241-409b-bfbd-e3a7406acc79` → después `db3b0ce6-b241-409b-bfbd-e3a7406acc79` (misma)
- **ISIN:** antes ES0171996012 → después ES0171996087
- **issuer_id:** antes `94016825-1176-470d-95b9-bf899d76a21a` (GRIFOLS, S.A.) → después `94016825-1176-470d-95b9-bf899d76a21a` (GRIFOLS, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0171996012 @ 2015-12-31 [ADMITTED_TO_TRADING] «GRF/AC A 0,50» / «GRIFOLS, S.A.» emitido 1987-06-22; miembro `852bc60857d8…` zip `7ab8a2a357b2…` (ANCVSemestral122015.zip)
  - primer snapshot con el ISIN nuevo: ES0171996087 @ 2016-06-30 [ADMITTED_TO_TRADING] «GRF/AC A 0,25» / «GRIFOLS, S.A.»; miembro `97ec1b9b0746…` zip `f6be93ce585a…` (ANCVSEMESTRAL062016.zip)
  - segmento: 2015-10-01: BME_FICHA_WAYBACK (10981a638f62)
  - segmento: 2016-03-22:official-exact:ES0171996087
  - documento oficial (CNMV hecho relevante 233601, 30/12/2015 (scanned: OCR)): https://www.cnmv.es/webservices/verdocumento/ver?e=Cks%2fkcHyRhulBjaj9Xn%2flafqoTZheLsWaW8eg8EG1exQSRh0dt1K2vXNhAR3mLSV [direct] `0c33c14cd314…` extracción OCR_APPLE_VISION; cita: «eted, foreseen that next 4 January 2016 will be the commencement of trading of the Company's ne»
  - documento oficial (BME-hosted notice of warrant adjustment (BNP Paribas) for the Grifols split): https://www.bolsasymercados.es/dam/descargas/indices/notices/adjustment-corporate-actions-warrants/ajuste-warrants-bnpp-grifols-split.pdf [direct] `e3875c953d1d…` extracción TEXT_LAYER; cita: «C Bloomberg: GRF SM ISIN: ES0171996012 Términos: Fecha ExD»
- **Por qué:** Cambio de ISIN de la MISMA entidad (SPLIT, política ADR-0020: cambio de nominal = misma security). La fecha es la de INICIO DE CONTRATACIÓN declarada en los documentos oficiales archivados, no la fecha de emisión ANCV; el security_id se mantiene.

### REE — 2016-07-11 — ISIN_CHANGE_OFFICIAL_TRANSITION

- **Estado:** EXACT_OFFICIAL_IDENTIFIER
- **Intervalo de membership:** [2005-07-01, abierto)
- **security_id:** antes `31f9e226-d336-4d4f-b796-1e498c2dd427` → después `31f9e226-d336-4d4f-b796-1e498c2dd427` (misma)
- **ISIN:** antes ES0173093115 → después ES0173093024
- **issuer_id:** antes `41a27580-74fc-478e-9209-0a0b7614920b` (RED ELECTRICA CORPORACION, S.A.) → después `41a27580-74fc-478e-9209-0a0b7614920b` (RED ELECTRICA CORPORACION, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0173093115 @ 2016-06-30 [ADMITTED_TO_TRADING] «REE/AC 2,00» / «RED ELECTRICA CORPORACION, S.A.» emitido 1999-05-19; miembro `97ec1b9b0746…` zip `f6be93ce585a…` (ANCVSEMESTRAL062016.zip)
  - primer snapshot con el ISIN nuevo: ES0173093024 @ 2016-12-31 [ADMITTED_TO_TRADING] «REE/AC 0,50» / «RED ELECTRICA CORPORACION, S.A.»; miembro `33fd428aa50f…` zip `3d4f8bae6435…` (ANCVSEMESTRAL122016.zip)
  - segmento: 2016-04-03: BME_FICHA_WAYBACK (bbf5a8a96fd1)
  - segmento: 2016-07-14:official-exact:ES0173093024
  - documento oficial (CNMV hecho relevante 240218, 28/06/2016): https://www.cnmv.es/webservices/verdocumento/ver?e=VBD0lrCcuITtbW6CZo8M5qfqoTZheLsWaW8eg8EG1exQSRh0dt1K2vXNhAR3mLSV [direct] `5b5c330df7c8…` extracción TEXT_LAYER; cita: «it is reported that next 11 of July 2016 the trading of the new shares of Red Eléctrica Co»
- **Por qué:** Cambio de ISIN de la MISMA entidad (SPLIT, política ADR-0020: cambio de nominal = misma security). La fecha es la de INICIO DE CONTRATACIÓN declarada en los documentos oficiales archivados, no la fecha de emisión ANCV; el security_id se mantiene.

### MTS — 2017-05-22 — ISIN_CHANGE_OFFICIAL_TRANSITION

- **Estado:** EXACT_OFFICIAL_IDENTIFIER
- **Intervalo de membership:** [2009-05-05, abierto)
- **security_id:** antes `88a25898-1850-4dbd-99cc-4fc84114ca49` → después `88a25898-1850-4dbd-99cc-4fc84114ca49` (misma)
- **ISIN:** antes LU0323134006 → después LU1598757687
- **issuer_id:** antes `ac4a0b65-36b3-458c-9e38-2e9ef4130725` (ARCELORMITTAL, S.A.) → después `ac4a0b65-36b3-458c-9e38-2e9ef4130725` (ARCELORMITTAL, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: LU0323134006 @ 2016-12-31 [ADMITTED_TO_TRADING] «ARCELORMITTAL/AC SVN» / «ARCELORMITTAL, S.A.»; miembro `33fd428aa50f…` zip `3d4f8bae6435…` (ANCVSEMESTRAL122016.zip)
  - primer snapshot con el ISIN nuevo: LU1598757687 @ 2017-06-30 [ADMITTED_TO_TRADING] «ARCELORMITTAL/AC» / «ARCELORMITTAL, S.A.» emitido 2017-05-18; miembro `d35e4333eacd…` zip `8f59f0501c90…` (ANCVSEMESTRAL062017.zip)
  - segmento: 2017-01-11: BME_FICHA_WAYBACK (4cb6972da825)
  - segmento: 2017-05-21:official-exact:LU1598757687
  - documento oficial (issuer notice via CNMV (registro 251971, 12/05/2017)): https://www.cnmv.es/webservices/verdocumento/ver?e=Oyxe7f5sj%2fMkwpClNVWVIrojc5caDaczWitwUsYwRmRQSRh0dt1K2vXNhAR3mLSV [direct] `0f45baf2e9fb…` extracción TEXT_LAYER; cita: «Reverse Stock Split will become effective on 22 May 2017. ENDS About Arcelor»
  - documento oficial (issuer notice via CNMV (registro 252333, 22/05/2017)): https://www.cnmv.es/webservices/verdocumento/ver?e=zynpuaJLVU0rFQ40M7Els7ojc5caDaczWitwUsYwRmRQSRh0dt1K2vXNhAR3mLSV [direct] `ad7174efe16b…` extracción TEXT_LAYER; cita: «2017, ArcelorMittal has completed the consolidation of each three existing shares in ArcelorMittal wi»
- **Por qué:** Cambio de ISIN de la MISMA entidad (REVERSE_SPLIT, política ADR-0020: cambio de nominal = misma security). La fecha es la de INICIO DE CONTRATACIÓN declarada en los documentos oficiales archivados, no la fecha de emisión ANCV; el security_id se mantiene.

### BKIA — 2017-06-03 — ISIN_CHANGE_ANCV_ISSUE_DATE

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
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre la última evidencia del antiguo y la primera del nuevo, el antiguo desaparece y la razón social no cambia (cambio de nominal = misma security). La fecha es la de EMISIÓN ANCV (administrativa), no una fecha oficial de inicio de contratación: frontera con incertidumbre de días.

### FER — 2023-06-16 — ISIN_CHANGE_NEW_SECURITY

- **Estado:** EXACT_OFFICIAL_IDENTIFIER
- **Intervalo de membership:** [1999-07-01, abierto)
- **security_id:** antes `c3a72758-1b3e-419e-a9db-98cb3d702d20` → después `2c882a14-a9a9-4183-a2c9-4939a8f33c46` (**distinta**)
- **ISIN:** antes ES0118900010 → después NL0015001FS8
- **issuer_id:** antes `26daf587-1b8e-45f1-980b-cea1160f73f3` (FERROVIAL, S.A.) → después `26daf587-1b8e-45f1-980b-cea1160f73f3` (FERROVIAL, S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0118900010 @ 2022-12-31 [ACTIVE_IN_ANCV] «FER/AC 0.20» / «FERROVIAL, S.A.» emitido 2004-09-01; miembro `155ca258be8c…` zip `b48e6e256be6…` (ANCVSEMESTRAL1222.zip)
  - primer snapshot con el ISIN nuevo: sin snapshot
  - segmento: 2023-06-01: BME_BOLETIN_JOIN (86c4e9dd4e51)
  - segmento: 2023-06-16:official-exact:NL0015001FS8
  - documento oficial (BME-hosted notice of warrant underlying change (Societe Generale)): https://www.bolsasymercados.es/dam/descargas/indices/notices/adjustment-corporate-actions-warrants/ferrovial-jun2023.pdf [direct] `aaf660faabb2…` extracción TEXT_LAYER; cita: «o de 2023, sobre la absorción de Ferrovial, S.A. por su filial Ferrovial International SE, se realizará el ca»
  - documento oficial (BME Instruccion Operativa 26/2023 (Internet Archive copy)): https://www.bolsasymercados.es/bme-exchange/docs/regula/SBolsas/esp/instrucc/2023/2023-26-IO-incorporacion-FER.pdf [wayback 20230717023409] `5e9a3c62d683…` extracción TEXT_LAYER; cita: «Instrucción Operativa Nº 26/2023 Inicio de Contratac»
- **Por qué:** Fusión por absorción / redomiciliación: cambia la entidad jurídica emisora del valor, así que es una security NUEVA enlazada a su predecesora (ADR-0020, `successor_security_id`); el ISIN antiguo cotiza hasta la víspera de la fecha efectiva y el nuevo desde ella. Continuidad ECONÓMICA del emisor (mismo issuer_id), no identidad jurídica.

### AENA — 2025-06-12 — ISIN_CHANGE_ANCV_ISSUE_DATE

- **Estado:** EXACT_OFFICIAL_IDENTIFIER
- **Intervalo de membership:** [2015-06-22, abierto)
- **security_id:** antes `48975c23-4e54-4751-9aba-a10f0a3bb5f6` → después `48975c23-4e54-4751-9aba-a10f0a3bb5f6` (misma)
- **ISIN:** antes ES0105046009 → después ES0105046017
- **issuer_id:** antes `4c167f16-9d5f-458f-89d1-9f9ed008b149` (AENA, S.M.E., S.A.) → después `4c167f16-9d5f-458f-89d1-9f9ed008b149` (AENA, S.M.E., S.A.)
- **Evidencia y hashes:**
  - último snapshot con el ISIN antiguo: ES0105046009 @ 2024-12-31 [ACTIVE_IN_ANCV] «AENA/AC 10.00» / «AENA, S.M.E., S.A.» emitido 2014-10-15; miembro `10c0e1ab165a…` zip `0407d3fffd18…` (ANCVSEMESTRAL1224.zip)
  - primer snapshot con el ISIN nuevo: ES0105046017 @ 2025-06-30 [ACTIVE_IN_ANCV] «AENA/AC 1.00» / «AENA, S.M.E., S.A.» emitido 2025-06-12; miembro `739c96ebe234…` zip `4fb8ba691b5e…` (ANCVSEMESTRAL0625.zip)
  - segmento: 2025-06-02: BME_BOLETIN_JOIN (9b3f64b6a20f)
  - segmento: 2025-06-30:anchor:ES0105046017
- **Por qué:** La ANCV fecha la emisión del ISIN nuevo entre la última evidencia del antiguo y la primera del nuevo, el antiguo desaparece y la razón social no cambia (cambio de nominal = misma security). La fecha es la de EMISIÓN ANCV (administrativa), no una fecha oficial de inicio de contratación: frontera con incertidumbre de días.

## Transiciones oficiales de ISIN registradas

| Efecto | ISIN antiguo → nuevo | Tipo | Continuidad | Uso en el universo IBEX | Documentos |
|---|---|---|---|---|---|
| 2016-01-04 | ES0171996012 → ES0171996087 | SPLIT | SAME_SECURITY | GRF [2008-01-02, abierto) | CNMV hecho relevante 233601, 30/12/2015 (scanned: OCR) `0c33c14cd314…`; BME-hosted notice of warrant adjustment (BNP Paribas) for the Grifols split `e3875c953d1d…` |
| 2016-07-11 | ES0173093115 → ES0173093024 | SPLIT | SAME_SECURITY | REE [2005-07-01, abierto) | CNMV hecho relevante 240218, 28/06/2016 `5b5c330df7c8…` |
| 2017-05-22 | LU0323134006 → LU1598757687 | REVERSE_SPLIT | SAME_SECURITY | MTS [2009-05-05, abierto) | issuer notice via CNMV (registro 251971, 12/05/2017) `0f45baf2e9fb…`; issuer notice via CNMV (registro 252333, 22/05/2017) `ad7174efe16b…` |
| 2020-07-22 | ES0169501030 → ES0169501022 | REVERSE_SPLIT | SAME_SECURITY | fuera de los intervalos IBEX (el valor entra o sale después/antes de la transición) | CNMV OIR 3518, 22/07/2020 `58899defd312…`; CNMV OIR 3401, 14/07/2020 `10332de80665…` |
| 2023-06-16 | ES0118900010 → NL0015001FS8 | CROSS_BORDER_MERGER | NEW_SECURITY | FER [1999-07-01, abierto) | BME-hosted notice of warrant underlying change (Societe Generale) `aaf660faabb2…`; BME Instruccion Operativa 26/2023 (Internet Archive copy) `5e9a3c62d683…` |

