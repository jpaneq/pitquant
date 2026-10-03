# S&P 500 — grafo de anclas históricas SEC (generado)

> Generado por `scripts/build_sp500_anchor_graph.py` desde la base. No editar a mano. Las anclas son composiciones de SPY presentadas a la SEC (`SEC_FILED_INDEX_REPLICATION_ANCHOR`), **no** listas oficiales de S&P DJI; `as_of_date` y `source_available_at` son relojes distintos y los anclajes nunca alimentan features.

Holdout 2022-10-01 → 2025-09-30 sellado: ningún ancla posterior a 2022-09-30 se carga.

## Anclas verificadas

| as_of | formulario | accession | tier | publicado (SEC) | miembros | con CUSIP | solo ISIN | sin resolver | excluidos (stubs/no-equity) |
|---|---|---|---|---|---|---|---|---|---|
| 2017-09-30 | N-30D | 0001193125-17-355427 | SEC_SCHEDULE_ANCHOR | 2017-11-29 14:06 | 504 | 0 | 0 | 0 | 0 |
| 2018-03-31 | N-30D | 0001193125-18-176552 | SEC_SCHEDULE_ANCHOR | 2018-05-29 14:10 | 504 | 0 | 0 | 0 | 0 |
| 2018-09-30 | N-30D | 0001193125-18-334730 | SEC_SCHEDULE_ANCHOR | 2018-11-27 10:29 | 505 | 0 | 0 | 0 | 0 |
| 2019-03-31 | N-30D | 0001193125-19-156288 | SEC_SCHEDULE_ANCHOR | 2019-05-24 10:03 | 504 | 0 | 0 | 0 | 0 |
| 2019-09-30 | N-30D | 0001193125-19-302203 | SEC_SCHEDULE_ANCHOR | 2019-11-27 11:35 | 505 | — | — | 0 | 0 |
| 2019-09-30 | NPORT-P | 0001752724-19-166260 | SEC_NPORT_IDENTIFIED_ANCHOR | 2019-11-18 15:09 | 505 | 477 | 28 | 0 | 0 |
| 2019-12-31 | NPORT-P | 0001752724-20-042737 | SEC_NPORT_IDENTIFIED_ANCHOR | 2020-02-28 14:55 | 505 | 474 | 31 | 0 | 0 |
| 2020-03-31 | N-30D | 0001193125-20-156851 | SEC_SCHEDULE_ANCHOR | 2020-06-01 11:22 | 505 | — | — | 0 | 0 |
| 2020-03-31 | NPORT-P | 0001752724-20-111515 | SEC_NPORT_IDENTIFIED_ANCHOR | 2020-05-29 17:35 | 505 | 474 | 31 | 0 | 0 |
| 2020-06-30 | NPORT-P | 0001752724-20-177260 | SEC_NPORT_IDENTIFIED_ANCHOR | 2020-08-27 16:57 | 505 | 476 | 29 | 0 | 0 |
| 2020-09-30 | N-30D | 0001193125-20-305082 | SEC_SCHEDULE_ANCHOR | 2020-11-30 09:20 | 505 | — | — | 0 | 0 |
| 2020-09-30 | NPORT-P | 0001752724-20-236128 | SEC_NPORT_IDENTIFIED_ANCHOR | 2020-11-18 20:32 | 505 | 476 | 29 | 0 | 0 |
| 2020-12-31 | NPORT-P | 0001752724-21-043869 | SEC_NPORT_IDENTIFIED_ANCHOR | 2021-02-26 16:35 | 505 | 477 | 28 | 0 | 0 |
| 2021-03-31 | N-30D | 0001193125-21-176380 | SEC_SCHEDULE_ANCHOR | 2021-05-28 09:49 | 505 | — | — | 0 | 0 |
| 2021-03-31 | NPORT-P | 0001752724-21-119080 | SEC_NPORT_IDENTIFIED_ANCHOR | 2021-05-28 15:06 | 505 | 477 | 28 | 0 | 1 |
| 2021-06-30 | NPORT-P | 0001752724-21-189808 | SEC_NPORT_IDENTIFIED_ANCHOR | 2021-08-27 14:17 | 505 | 477 | 28 | 0 | 1 |
| 2021-09-30 | N-30D | 0001193125-21-342303 | SEC_SCHEDULE_ANCHOR | 2021-11-29 16:32 | 505 | — | — | 0 | 0 |
| 2021-09-30 | NPORT-P | 0001752724-21-258706 | SEC_NPORT_IDENTIFIED_ANCHOR | 2021-11-24 18:35 | 505 | 478 | 27 | 0 | 1 |
| 2021-12-31 | NPORT-P | 0001752724-22-048845 | SEC_NPORT_IDENTIFIED_ANCHOR | 2022-02-25 17:20 | 505 | 478 | 27 | 0 | 1 |
| 2022-03-31 | N-30D | 0001193125-22-161896 | SEC_SCHEDULE_ANCHOR | 2022-05-27 10:48 | 505 | — | — | 0 | 1 |
| 2022-03-31 | NPORT-P | 0001752724-22-127611 | SEC_NPORT_IDENTIFIED_ANCHOR | 2022-05-27 13:54 | 505 | 481 | 24 | 0 | 1 |
| 2022-06-30 | NPORT-P | 0001752724-22-196968 | SEC_NPORT_IDENTIFIED_ANCHOR | 2022-08-26 13:22 | 503 | 479 | 24 | 0 | 2 |
| 2022-09-30 | N-30D | 0001193125-22-293237 | SEC_SCHEDULE_ANCHOR | 2022-11-28 13:58 | 505 | — | — | 0 | 0 |
| 2022-09-30 | NPORT-P | 0001752724-22-271183 | SEC_NPORT_IDENTIFIED_ANCHOR | 2022-11-28 15:50 | 503 | 479 | 24 | 0 | 2 |

## Cross-check NPORT-P vs N-30D (misma fecha)

| fecha | NPORT equities | schedule equities | matched | nport_only | schedule_only | identity_unresolved |
|---|---|---|---|---|---|---|
| 2019-09-30 | 505 | 505 | 505 | 0 | 0 | 0 |
| 2020-03-31 | 505 | 505 | 505 | 0 | 0 | 0 |
| 2020-09-30 | 505 | 505 | 505 | 0 | 0 | 0 |
| 2021-03-31 | 505 | 505 | 505 | 0 | 0 | 0 |
| 2021-09-30 | 505 | 505 | 505 | 0 | 0 | 0 |
| 2022-03-31 | 505 | 505 | 505 | 0 | 0 | 0 |
| 2022-09-30 | 503 | 505 | 503 | 0 | 2 | 0 |

La discrepancia de 2022-09-30 (`schedule_only` = EQT y PG&E) NO es un error: el N-30D es la cartera tras las operaciones de cierre del día y SPY ya había comprado las altas que entraban en el índice el 2022-10-03 (S&P: EQT por Duke Realty, PG&E por Citrix), mientras que el NPORT-P refleja el índice a esa fecha. Para un ancla Tier B se retiran de su conjunto las altas CONFIRMADAS con efecto en la sesión siguiente.

## Métricas principales

| métrica | estricto | indulgente (QA) |
|---|---|---|
| verified_anchors | 17 | 17 |
| segments | 16 | 16 |
| validated_segments | 1 | 4 |
| forward_validated_segments | 4 | 4 |
| backward_validated_segments | 4 | 4 |
| local_unresolved_segments | 15 | 12 |
| monthly_cohorts | 60 | 60 |
| monthly_cohorts_reconstructible | 3 | 15 |
| longest_continuous_period | 3 | 9 |
| post_limit_events_used | 0 | 0 |
| security_identity_resolution | {'anchor_members': 8577, 'weak_identity_members': 76, 'unresolved_lines': 0} | |

El modo ESTRICTO es el de la puerta: una pata sin confirmar del CSV de discovery sin ticker resoluble bloquea su segmento si excede los cambios visibles en las anclas, o si el mismo ticker se añade y se retira dentro del segmento. El porcentaje de eventos del CSV confirmados es sólo QA.

## Ventana mínima (60): 2017-10-01 → 2022-09-30

- monthly_cohorts 60 · membership_ready **3** · bloqueadas 57 · racha continua 3 · identity (miembros de ancla sin resolver) 0
- cohortes sin ancla a uno de los lados: 0 (no se han buscado anclas anteriores a 2017-09: la ventana mínima aún no está completa)

## Ventana preferida (96): 2014-10-01 → 2022-09-30

- monthly_cohorts 96 · membership_ready **3** · bloqueadas 93 · racha continua 3 · identity (miembros de ancla sin resolver) 0
- cohortes sin ancla a uno de los lados: 36 (no se han buscado anclas anteriores a 2017-09: la ventana mínima aún no está completa)

## Segmentos

| desde | hasta | estado | forward | backward | patas confirmadas | gaps por tipo |
|---|---|---|---|---|---|---|
| 2017-09-30 | 2018-03-31 | LOCAL_GAPS | False | False | 12 | {'SECURITY_IDENTITY_GAP': 11, 'MISSING_ADDITION_EVENT': 7} |
| 2018-03-31 | 2018-09-30 | LOCAL_GAPS | False | False | 18 | {'MISSING_REMOVAL_EVENT': 2, 'SECURITY_IDENTITY_GAP': 1, 'MISSING_ADDITION_EVENT': 1} |
| 2018-09-30 | 2019-03-31 | LOCAL_GAPS | False | False | 22 | {'SECURITY_IDENTITY_GAP': 5, 'DATE_CONFLICT': 2, 'MISSING_ADDITION_EVENT': 4, 'UNEXPLAINED': 1, 'MISSING_REMOVAL_EVENT': 4} |
| 2019-03-31 | 2019-09-30 | LOCAL_GAPS | False | False | 16 | {'SECURITY_IDENTITY_GAP': 5, 'DATE_CONFLICT': 2, 'MISSING_ADDITION_EVENT': 6, 'MISSING_REMOVAL_EVENT': 4} |
| 2019-09-30 | 2019-12-31 | LOCAL_GAPS | True | True | 14 | {'SECURITY_IDENTITY_GAP': 5} |
| 2019-12-31 | 2020-03-31 | LOCAL_GAPS | False | False | 4 | {'MISSING_ADDITION_EVENT': 1, 'SECURITY_IDENTITY_GAP': 1} |
| 2020-03-31 | 2020-06-30 | LOCAL_GAPS | False | False | 12 | {'MISSING_ADDITION_EVENT': 2, 'SECURITY_IDENTITY_GAP': 2, 'MISSING_REMOVAL_EVENT': 2} |
| 2020-06-30 | 2020-09-30 | VALIDATED | True | True | 6 | {} |
| 2020-09-30 | 2020-12-31 | LOCAL_GAPS | False | False | 4 | {'DATE_CONFLICT': 1, 'MISSING_ADDITION_EVENT': 1, 'MISSING_REMOVAL_EVENT': 2} |
| 2020-12-31 | 2021-03-31 | LOCAL_GAPS | False | False | 14 | {'MISSING_REMOVAL_EVENT': 1, 'MISSING_ADDITION_EVENT': 1} |
| 2021-03-31 | 2021-06-30 | LOCAL_GAPS | False | False | 5 | {'SECURITY_IDENTITY_GAP': 2, 'DATE_CONFLICT': 1, 'MISSING_REMOVAL_EVENT': 1} |
| 2021-06-30 | 2021-09-30 | LOCAL_GAPS | True | True | 10 | {'SECURITY_IDENTITY_GAP': 1} |
| 2021-09-30 | 2021-12-31 | LOCAL_GAPS | True | True | 8 | {'SECURITY_IDENTITY_GAP': 1} |
| 2021-12-31 | 2022-03-31 | LOCAL_GAPS | False | False | 4 | {'DATE_CONFLICT': 2, 'SECURITY_IDENTITY_GAP': 2} |
| 2022-03-31 | 2022-06-30 | LOCAL_GAPS | False | False | 4 | {'MISSING_REMOVAL_EVENT': 5, 'MISSING_ADDITION_EVENT': 3, 'SECURITY_IDENTITY_GAP': 1} |
| 2022-06-30 | 2022-09-30 | LOCAL_GAPS | False | False | 4 | {'MISSING_ADDITION_EVENT': 1, 'MISSING_REMOVAL_EVENT': 1} |

Aliases de ticker / transiciones de identidad persistidos: 8 (límites `PARTIAL`: no se infiere ninguna fecha). Segmentos persistidos: 16.

## Gaps locales (resumen)

| tipo | n |
|---|---|
| SECURITY_IDENTITY_GAP | 37 |
| MISSING_ADDITION_EVENT | 27 |
| MISSING_REMOVAL_EVENT | 22 |
| DATE_CONFLICT | 8 |
| UNEXPLAINED | 1 |

Detalle completo para investigación externa: `docs/SP500_LOCAL_GAPS.md` y `docs/sp500_local_gaps.json`.

## Walk-forward (train_min = 60 meses, sin cambios)

Con las cohortes reconstruibles actuales: 3 cohortes, 0 folds OOS. `BASELINE_TRAINING_READY` exige ≥96 cohortes consecutivas y ≥2 folds.
