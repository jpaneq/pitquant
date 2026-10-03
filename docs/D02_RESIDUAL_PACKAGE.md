# D-02 — paquete documental residual (generado)

> Generado por `scripts/gen_d02_residual_package.py` desde la base y el archivo local. No editar a mano. Las pistas de discovery NO son evidencia.

## Antes / después (ventana 2017-10 → 2022-09)

| métrica | inicio de la iteración (HEAD f84f38d) | ahora |
|---|---|---|
| cohortes mensuales listas | 27/60 | 54/60 |
| racha continua máxima | 15 | 54 |
| bloqueos de membresía | 21 | 2 |
| bloqueos sólo de identidad | 3 | 1 |
| securities con identidad débil | 2 | 2 |

Sucesiones persistidas: 27. `D02_MONTHLY_MEMBERSHIP_READY` = False; `US_SECURITY_IDENTITY_READY` = False.

## Resumen por segmento

| segmento | bloqueos membresía | bloqueos identidad | documento ausente | archivado pero insuficiente |
|---|---|---|---|---|
| 2017-09-30→2018-03-31 | 2 | 1 | 1 | 1 |

## Identidad (aparte de la membresía)

- Identidad débil: 2 securities; bloqueos sólo de identidad: 1.
- Categorías de fichas: {'PRIMARY_EVENT_MISSING': 1, 'SECURITY_IDENTITY_ONLY': 1}.

## Prompt para investigación externa (copiar tal cual)

```
Busca fuentes oficiales para estas fichas. Devuelve por caso URL, accession si aplica, fecha de publicación/acceptance, cita breve que demuestra el evento, fecha efectiva y evidencia de continuidad/clase. Separa lo probado de lo incierto. No uses CSV comunitarios como prueba.
```

## Fichas

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

