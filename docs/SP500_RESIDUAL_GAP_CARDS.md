# D-02 — fichas residuales para investigación documental

> Generado desde el archivo local. Las fechas de discovery son pistas, nunca evidencia. Una diferencia entre anclas puede ser una sucesión; no prueba una entrada/salida real.

Ventana 2017-10 → 2022-09: **54/60** cohortes, **2** bloqueos mensuales; **1** requieren identidad. Los bloqueos de identidad se cuentan también como mensuales sólo cuando impiden determinar la composición.

## Prioridad por segmento

| Segmento | Bloqueos mensuales |
|---|---|
| 2017-09-30→2018-03-31 | 2 |

## 1. PPoG Industries, Inc. — acac7cab-36e8-4829-ae50-239b39b19460

- Segmento: 2017-09-30→2018-03-31.
- Clasificación: SECURITY_IDENTITY_ONLY.
- Estado ancla A → B: MEMBER → ABSENT.
- Evento esperado por reconciliar: REMOVAL_OR_SECURITY_CONTINUITY.
- Intervalo candidato: ['2017-10-02', '2018-03-31'] (límite superior excluido para las cohortes ambiguas).
- Evidencia ausente: identity link (same issuer under a new name/CUSIP?) between the unresolved N-30D security and its counterpart; membership unknown until then.
- Por qué bloquea: sin una fecha efectiva o continuidad documentada, las composiciones posibles difieren en los decision_at indicados.
- Decision_at afectados: 2017-10-02, 2017-11-01, 2017-12-01, 2018-01-02, 2018-02-01, 2018-03-01.
- Evidencia de eventos disponible: none.
- Pista QA: one side of this change rests on a name-only identity (N-30D): it may be the same security under another name/CUSIP.

## 2. PPG Industries, Inc. — b483e600-410b-4916-ad7f-cec18bc42ac0

- Segmento: 2017-09-30→2018-03-31.
- Clasificación: PRIMARY_EVENT_MISSING.
- Estado ancla A → B: ABSENT → MEMBER.
- Evento esperado por reconciliar: ADDITION_OR_SECURITY_CONTINUITY.
- Intervalo candidato: ['2017-10-02', '2018-03-31'] (límite superior excluido para las cohortes ambiguas).
- Evidencia ausente: official effective date of the addition/removal (absent/present at anchor A, opposite at anchor B; no primary event pins it).
- Por qué bloquea: sin una fecha efectiva o continuidad documentada, las composiciones posibles difieren en los decision_at indicados.
- Decision_at afectados: 2017-10-02, 2017-11-01, 2017-12-01, 2018-01-02, 2018-02-01, 2018-03-01.
- Evidencia de eventos disponible: none.
