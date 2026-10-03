# D-02 — paquete documental residual (generado)

> Generado por `scripts/gen_d02_residual_package.py` desde la base y el archivo local. No editar a mano. Las pistas de discovery NO son evidencia.

## Antes / después (ventana 2017-10 → 2022-09)

| métrica | inicio de la iteración (HEAD 8af040b) | ahora |
|---|---|---|
| cohortes mensuales listas | 21/60 | 27/60 |
| racha continua máxima | 9 | 15 |
| bloqueos de membresía | 46 | 21 |
| bloqueos sólo de identidad | 8 | 3 |
| securities con identidad débil | 15 | 2 |

Sucesiones persistidas: 19. `D02_MONTHLY_MEMBERSHIP_READY` = False; `US_SECURITY_IDENTITY_READY` = False.

## Resumen por segmento

| segmento | bloqueos membresía | bloqueos identidad | documento ausente | archivado pero insuficiente |
|---|---|---|---|---|
| 2017-09-30→2018-03-31 | 4 | 2 | 3 | 1 |
| 2018-03-31→2018-09-30 | 2 | 1 | 2 | 0 |
| 2018-09-30→2019-03-31 | 2 | 0 | 2 | 0 |
| 2019-03-31→2019-09-30 | 4 | 0 | 2 | 2 |
| 2020-03-31→2020-06-30 | 4 | 0 | 4 | 0 |
| 2020-09-30→2020-12-31 | 2 | 0 | 2 | 0 |
| 2022-03-31→2022-06-30 | 3 | 0 | 3 | 0 |

## Identidad (aparte de la membresía)

- Identidad débil: 2 securities; bloqueos sólo de identidad: 3.
- Categorías de fichas: {'PRIMARY_EVENT_MISSING': 18, 'SECURITY_IDENTITY_ONLY': 3}.

## Prompt para investigación externa (copiar tal cual)

```
Busca fuentes oficiales para estas fichas. Devuelve por caso URL, accession si aplica, fecha de publicación/acceptance, cita breve que demuestra el evento, fecha efectiva y evidencia de continuidad/clase. Separa lo probado de lo incierto. No uses CSV comunitarios como prueba.
```

## Fichas

### D02-2aa06dfc94d9 — IQVIA Holdings, Inc.
- security_id: `07b912e9-b028-4ff5-b3c2-25a09e7046e1`; segmento 2017-09-30→2018-03-31; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2017-09-30, N-30D, accession 0001193125-17-355427, sha256 `45cc19b41167f647…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312517355427/d418234dn30d.htm]
- Ancla B (2018-03-31, N-30D, accession 0001193125-18-176552, sha256 `4e23b7abd6a732de…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312518176552/d483307dn30d.htm]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2017-10-02', '2018-03-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2017-10-02, 2017-11-01, 2017-12-01, 2018-01-02, 2018-02-01, 2018-03-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-bb9c820d1cfe — PPG Industries, Inc.
- security_id: `b483e600-410b-4916-ad7f-cec18bc42ac0`; segmento 2017-09-30→2018-03-31; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2017-09-30, N-30D, accession 0001193125-17-355427, sha256 `45cc19b41167f647…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312517355427/d418234dn30d.htm]
- Ancla B (2018-03-31, N-30D, accession 0001193125-18-176552, sha256 `4e23b7abd6a732de…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312518176552/d483307dn30d.htm]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2017-10-02', '2018-03-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2017-10-02, 2017-11-01, 2017-12-01, 2018-01-02, 2018-02-01, 2018-03-01.
- Documentación local: **ARCHIVED_BUT_PARSER_OR_RULES_INSUFFICIENT**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-eed1724e5343 — PPoG Industries, Inc.
- security_id: `acac7cab-36e8-4829-ae50-239b39b19460`; segmento 2017-09-30→2018-03-31; categoría SECURITY_IDENTITY_ONLY.
- Ancla A (2017-09-30, N-30D, accession 0001193125-17-355427, sha256 `45cc19b41167f647…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312517355427/d418234dn30d.htm]
- Ancla B (2018-03-31, N-30D, accession 0001193125-18-176552, sha256 `4e23b7abd6a732de…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312518176552/d483307dn30d.htm]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2017-10-02', '2018-03-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2017-10-02, 2017-11-01, 2017-12-01, 2018-01-02, 2018-02-01, 2018-03-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): one side of this change rests on a name-only identity (N-30D): it may be the same security under another name/CUSIP

### D02-345bd022371f — Quintiles IMS Holdings, Inc.
- security_id: `9a15337e-8be3-478a-b111-9097461e0997`; segmento 2017-09-30→2018-03-31; categoría SECURITY_IDENTITY_ONLY.
- Ancla A (2017-09-30, N-30D, accession 0001193125-17-355427, sha256 `45cc19b41167f647…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312517355427/d418234dn30d.htm]
- Ancla B (2018-03-31, N-30D, accession 0001193125-18-176552, sha256 `4e23b7abd6a732de…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312518176552/d483307dn30d.htm]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2017-10-02', '2018-03-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2017-10-02, 2017-11-01, 2017-12-01, 2018-01-02, 2018-02-01, 2018-03-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): one side of this change rests on a name-only identity (N-30D): it may be the same security under another name/CUSIP

### D02-fcb97424cefc — Jefferies Financial Group, Inc.
- security_id: `ab14ed13-8c2d-4f10-8ef2-27529b2bdf2e`; segmento 2018-03-31→2018-09-30; categoría SECURITY_IDENTITY_ONLY.
- Ancla A (2018-03-31, N-30D, accession 0001193125-18-176552, sha256 `4e23b7abd6a732de…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312518176552/d483307dn30d.htm]
- Ancla B (2018-09-30, N-30D, accession 0001193125-18-334730, sha256 `614d4c43526ae361…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312518334730/d613130dn30d.htm]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2018-04-02', '2018-09-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2018-04-02, 2018-05-01, 2018-06-01, 2018-07-02, 2018-08-01, 2018-09-04.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): one side of this change rests on a name-only identity (N-30D): it may be the same security under another name/CUSIP

### D02-63f69061cbe0 — Leucadia National Corp.
- security_id: `545885d8-f14c-4e9c-9859-d43739979d1e`; segmento 2018-03-31→2018-09-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2018-03-31, N-30D, accession 0001193125-18-176552, sha256 `4e23b7abd6a732de…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312518176552/d483307dn30d.htm]
- Ancla B (2018-09-30, N-30D, accession 0001193125-18-334730, sha256 `614d4c43526ae361…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312518334730/d613130dn30d.htm]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2018-04-02', '2018-09-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2018-04-02, 2018-05-01, 2018-06-01, 2018-07-02, 2018-08-01, 2018-09-04.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-ef2a5fbf66aa — Capri Holdings, Ltd.
- security_id: `feb9e370-2c97-4048-8c69-76845dd0fdd2`; segmento 2018-09-30→2019-03-31; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2018-09-30, N-30D, accession 0001193125-18-334730, sha256 `614d4c43526ae361…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312518334730/d613130dn30d.htm]
- Ancla B (2019-03-31, N-30D, accession 0001193125-19-156288, sha256 `53ad4bd145d740dc…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312519156288/d690538dn30d.htm]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2018-10-01', '2019-03-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2018-10-01, 2018-11-01, 2018-12-03, 2019-01-02, 2019-02-01, 2019-03-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-097fe8bea4ae — Michael Kors Holdings, Ltd.
- security_id: `e2ba7cc7-007d-433a-a6d4-c081dac1ce11`; segmento 2018-09-30→2019-03-31; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2018-09-30, N-30D, accession 0001193125-18-334730, sha256 `614d4c43526ae361…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312518334730/d613130dn30d.htm]
- Ancla B (2019-03-31, N-30D, accession 0001193125-19-156288, sha256 `53ad4bd145d740dc…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312519156288/d690538dn30d.htm]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2018-10-01', '2019-03-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2018-10-01, 2018-11-01, 2018-12-03, 2019-01-02, 2019-02-01, 2019-03-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-9d6ce9aa8611 — GLOBE LIFE INC COMMON STOCK USD1.0
- security_id: `b71cba2b-5058-42f6-bafb-11259cf127a6`; segmento 2019-03-31→2019-09-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2019-03-31, N-30D, accession 0001193125-19-156288, sha256 `53ad4bd145d740dc…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312519156288/d690538dn30d.htm]
- Ancla B (2019-09-30, NPORT-P, accession 0001752724-19-166260, sha256 `a516a35e07b5bf4a…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272419166260/primary_doc.xml]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2019-04-01', '2019-09-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2019-04-01, 2019-05-01, 2019-06-03, 2019-07-01, 2019-08-01, 2019-09-03.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg ADD GL 2019-08-08 (unconfirmed, date not trusted)

### D02-59c8bf3e7721 — Harris Corp.
- security_id: `e5e10193-f543-447d-afeb-69011b4d629b`; segmento 2019-03-31→2019-09-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2019-03-31, N-30D, accession 0001193125-19-156288, sha256 `53ad4bd145d740dc…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312519156288/d690538dn30d.htm]
- Ancla B (2019-09-30, NPORT-P, accession 0001752724-19-166260, sha256 `a516a35e07b5bf4a…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272419166260/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2019-04-01', '2019-09-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2019-04-01, 2019-05-01, 2019-06-03, 2019-07-01, 2019-08-01, 2019-09-03.
- Documentación local: **ARCHIVED_BUT_PARSER_OR_RULES_INSUFFICIENT**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg REMOVE HRS 2019-06-01 (unconfirmed, date not trusted)

### D02-14c1011e8b48 — L3 HARRIS TECHNOLOGIES INC
- security_id: `5ae0498c-f341-4e79-9bf2-7e65f137c2c3`; segmento 2019-03-31→2019-09-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2019-03-31, N-30D, accession 0001193125-19-156288, sha256 `53ad4bd145d740dc…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000119312519156288/d690538dn30d.htm]
- Ancla B (2019-09-30, NPORT-P, accession 0001752724-19-166260, sha256 `a516a35e07b5bf4a…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272419166260/primary_doc.xml]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2019-04-01', '2019-09-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2019-04-01, 2019-05-01, 2019-06-03, 2019-07-01, 2019-08-01, 2019-09-03.
- Documentación local: **ARCHIVED_BUT_PARSER_OR_RULES_INSUFFICIENT**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg ADD LHX 2019-06-01 (unconfirmed, date not trusted)

### D02-8cd84d39fc0f — Torchmark Corp.
- security_id: `c47f88fd-276c-43dc-a696-f9c7e48c2d23`; segmento 2019-03-31→2019-09-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2019-03-31, N-30D, accession 0001193125-19-156288, sha256 `53ad4bd145d740dc…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000119312519156288/d690538dn30d.htm]
- Ancla B (2019-09-30, NPORT-P, accession 0001752724-19-166260, sha256 `a516a35e07b5bf4a…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272419166260/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2019-04-01', '2019-09-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2019-04-01, 2019-05-01, 2019-06-03, 2019-07-01, 2019-08-01, 2019-09-03.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-c3d865620135 — Allergan PLC
- security_id: `86f51cd9-087b-460c-aeed-7a3fc50b0de1`; segmento 2020-03-31→2020-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2020-03-31, NPORT-P, accession 0001752724-20-111515, sha256 `360bc89eb44ff895…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272420111515/primary_doc.xml]
- Ancla B (2020-06-30, NPORT-P, accession 0001752724-20-177260, sha256 `34e52311ef607c87…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272420177260/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2020-04-01', '2020-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2020-04-01, 2020-05-01, 2020-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-452eb02699a1 — Capri Holdings Ltd
- security_id: `feb9e370-2c97-4048-8c69-76845dd0fdd2`; segmento 2020-03-31→2020-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2020-03-31, NPORT-P, accession 0001752724-20-111515, sha256 `360bc89eb44ff895…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272420111515/primary_doc.xml]
- Ancla B (2020-06-30, NPORT-P, accession 0001752724-20-177260, sha256 `34e52311ef607c87…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272420177260/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2020-04-01', '2020-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2020-04-01, 2020-05-01, 2020-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg REMOVE CPRI 2020-05-12 (unconfirmed, date not trusted)

### D02-e28696ebb261 — DexCom Inc
- security_id: `0aac833a-a933-4d3f-bcca-72983f1360aa`; segmento 2020-03-31→2020-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2020-03-31, NPORT-P, accession 0001752724-20-111515, sha256 `360bc89eb44ff895…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272420111515/primary_doc.xml]
- Ancla B (2020-06-30, NPORT-P, accession 0001752724-20-177260, sha256 `34e52311ef607c87…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272420177260/primary_doc.xml]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2020-04-01', '2020-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2020-04-01, 2020-05-01, 2020-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg ADD DXCM 2020-05-12 (unconfirmed, date not trusted)

### D02-d7d49ba2be65 — Domino's Pizza Inc
- security_id: `6e7ad054-62b6-48f4-9afa-bbd7ff071510`; segmento 2020-03-31→2020-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2020-03-31, NPORT-P, accession 0001752724-20-111515, sha256 `360bc89eb44ff895…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272420111515/primary_doc.xml]
- Ancla B (2020-06-30, NPORT-P, accession 0001752724-20-177260, sha256 `34e52311ef607c87…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272420177260/primary_doc.xml]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2020-04-01', '2020-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2020-04-01, 2020-05-01, 2020-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg ADD DPZ 2020-05-12 (unconfirmed, date not trusted)

### D02-2b09b1ae6378 — Mylan NV
- security_id: `e49460c7-854b-463b-8bf8-de77dda56c9c`; segmento 2020-09-30→2020-12-31; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2020-09-30, NPORT-P, accession 0001752724-20-236128, sha256 `0448bf94f5bf52e1…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272420236128/primary_doc.xml]
- Ancla B (2020-12-31, NPORT-P, accession 0001752724-21-043869, sha256 `5cde609dff35da40…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272421043869/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2020-10-01', '2020-12-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2020-10-01, 2020-11-02, 2020-12-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-3ac166b43295 — Viatris Inc
- security_id: `88f15fae-b855-4c59-bcfd-460e0e788845`; segmento 2020-09-30→2020-12-31; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2020-09-30, NPORT-P, accession 0001752724-20-236128, sha256 `0448bf94f5bf52e1…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272420236128/primary_doc.xml]
- Ancla B (2020-12-31, NPORT-P, accession 0001752724-21-043869, sha256 `5cde609dff35da40…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272421043869/primary_doc.xml]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2020-10-01', '2020-12-31'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2020-10-01, 2020-11-02, 2020-12-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg ADD VTRS 2020-11-17 (unconfirmed, date not trusted)

### D02-afed3d9623dc — Discovery Inc
- security_id: `0c9152f4-4bb9-4970-84ad-1dbeef1049eb`; segmento 2022-03-31→2022-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2022-03-31, NPORT-P, accession 0001752724-22-127611, sha256 `b0d180201db9db9c…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272422127611/primary_doc.xml]
- Ancla B (2022-06-30, NPORT-P, accession 0001752724-22-196968, sha256 `5c2affa10d9818d0…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272422196968/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2022-04-01', '2022-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2022-04-01, 2022-05-02, 2022-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-c6a2874c36ea — Discovery Inc
- security_id: `26e0b041-be73-41b2-aeb5-814ca37bd4e6`; segmento 2022-03-31→2022-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2022-03-31, NPORT-P, accession 0001752724-22-127611, sha256 `b0d180201db9db9c…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272422127611/primary_doc.xml]
- Ancla B (2022-06-30, NPORT-P, accession 0001752724-22-196968, sha256 `5c2affa10d9818d0…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272422196968/primary_doc.xml]
- Evento por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY; intervalo candidato ['2022-04-01', '2022-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2022-04-01, 2022-05-02, 2022-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.

### D02-599fdfdcb4d2 — Warner Bros Discovery Inc
- security_id: `be661ebb-3515-4c84-8bd4-82a2feae8bbe`; segmento 2022-03-31→2022-06-30; categoría PRIMARY_EVENT_MISSING.
- Ancla A (2022-03-31, NPORT-P, accession 0001752724-22-127611, sha256 `b0d180201db9db9c…`): ABSENT. [https://www.sec.gov/Archives/edgar/data/884394/000175272422127611/primary_doc.xml]
- Ancla B (2022-06-30, NPORT-P, accession 0001752724-22-196968, sha256 `5c2affa10d9818d0…`): MEMBER. [https://www.sec.gov/Archives/edgar/data/884394/000175272422196968/primary_doc.xml]
- Evento por reconciliar: ADDITION_OR_SECURITY_CONTINUITY; intervalo candidato ['2022-04-01', '2022-06-30'].
- Motivo: membership: the possible compositions differ at the listed decision_at. decision_at afectados: 2022-04-01, 2022-05-02, 2022-06-01.
- Documentación local: **DOCUMENT_ABSENT_FROM_LOCAL_ARCHIVE**; eventos primarios hallados: none.
- Evidencia que falta: an official document stating the event (S&P DJI release or the issuer's SEC 8-K) with its effective date and, if a rename/succession, that the same security/class continues.
- Condición de cierre: a primary source that fixes the event date (or proves the same-security continuity) so that anchor A and anchor B reconcile for EVERY listed decision_at; a CSV or community list never closes it.
- Pista (NO probatoria): discovery CSV leg ADD WBD 2022-04-11 (unconfirmed, date not trusted)

