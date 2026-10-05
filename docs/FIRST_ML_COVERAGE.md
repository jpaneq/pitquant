# First ML US coverage — FIRST_ML_COVERAGE_V1

Generado desde filas DEV; sin entrenamiento ni rendimiento. Cohorte común TRAIN y TEST para M0–M4; native por familia solo diagnóstico. El 100 global no decide este experimento.

PRICE: >=40 issuers y >=80% de membresía válida configurada. FUNDAMENTALS/COMBINED: >=30 issuers y >=70% de PRICE. TRAIN >=90% meses; TEST 12/12. Ambos targets deben existir en TRAIN y TEST.

Resultado: READY. Effective sample size: NOT_FORMALLY_ESTIMATED.

## Fold 1

| Family | Partition | Rows | Issuers | Min monthly issuers | Passing months | Required | Pass |
|---|---|---|---|---|---|---|---|
| PRICE | TRAIN | 1757 | 48 | 47 | 37 | 34 | True |
| PRICE | TEST | 576 | 48 | 48 | 12 | 12 | True |
| FUNDAMENTALS | TRAIN | 1318 | 37 | 33 | 37 | 34 | True |
| FUNDAMENTALS | TEST | 476 | 42 | 38 | 12 | 12 | True |
| COMBINED | TRAIN | 1318 | 37 | 33 | 37 | 34 | True |
| COMBINED | TEST | 476 | 42 | 38 | 12 | 12 | True |

COMMON TRAIN: 1318 rows, 37 issuers; labels {'positive': 840, 'negative': 478, 'missing_or_invalid': 0, 'base_rate': 0.637329286798179, 'non_degenerate': True}; frozen keys SHA256 a06b0d079a3b627c12a8a8567692fb992f86af1f83ccc66e7953cd4232857ae5.

COMMON TEST: 476 rows, 42 issuers; labels {'positive': 289, 'negative': 187, 'missing_or_invalid': 0, 'base_rate': 0.6071428571428571, 'non_degenerate': True}; frozen keys SHA256 d21fcf4e320ac0175cee5faef878a7733cbf62124fa38db3a7ab0d4c5db6de0c.

## Fold 2

| Family | Partition | Rows | Issuers | Min monthly issuers | Passing months | Required | Pass |
|---|---|---|---|---|---|---|---|
| PRICE | TRAIN | 2285 | 48 | 0 | 48 | 45 | True |
| PRICE | TEST | 588 | 49 | 49 | 12 | 12 | True |
| FUNDAMENTALS | TRAIN | 1735 | 39 | 0 | 48 | 45 | True |
| FUNDAMENTALS | TEST | 510 | 44 | 40 | 12 | 12 | True |
| COMBINED | TRAIN | 1735 | 39 | 0 | 48 | 45 | True |
| COMBINED | TEST | 510 | 44 | 40 | 12 | 12 | True |

COMMON TRAIN: 1735 rows, 39 issuers; labels {'positive': 1141, 'negative': 594, 'missing_or_invalid': 0, 'base_rate': 0.6576368876080692, 'non_degenerate': True}; frozen keys SHA256 9086e59cb77fbaa200829f7f7bb35e7a4e9187d53cf2bc8fc6963aa26486bacd.

COMMON TEST: 510 rows, 44 issuers; labels {'positive': 227, 'negative': 283, 'missing_or_invalid': 0, 'base_rate': 0.44509803921568625, 'non_degenerate': True}; frozen keys SHA256 97fecdea8185e1eaac83a58caf3a79941935d3ead140970fa6a30f19cbd22d02.

## Fold 3

| Family | Partition | Rows | Issuers | Min monthly issuers | Passing months | Required | Pass |
|---|---|---|---|---|---|---|---|
| PRICE | TRAIN | 2861 | 48 | 0 | 60 | 55 | True |
| PRICE | TEST | 597 | 50 | 49 | 12 | 12 | True |
| FUNDAMENTALS | TRAIN | 2209 | 42 | 0 | 60 | 55 | True |
| FUNDAMENTALS | TEST | 521 | 44 | 42 | 12 | 12 | True |
| COMBINED | TRAIN | 2209 | 42 | 0 | 60 | 55 | True |
| COMBINED | TEST | 521 | 44 | 42 | 12 | 12 | True |

COMMON TRAIN: 2209 rows, 42 issuers; labels {'positive': 1435, 'negative': 774, 'missing_or_invalid': 0, 'base_rate': 0.6496152105024898, 'non_degenerate': True}; frozen keys SHA256 44c59e37f82aaa87c9ea5f54b3744803d20045684f03f73b550101da5ab6b722.

COMMON TEST: 521 rows, 44 issuers; labels {'positive': 275, 'negative': 246, 'missing_or_invalid': 0, 'base_rate': 0.527831094049904, 'non_degenerate': True}; frozen keys SHA256 502aaf2cd71832809c6b168efc8566dcb6bce5029bd2d17d7580b50bebf71067.


## Limitaciones

Configured universe selection/survivorship bias persists.
Sector categories are descriptive current metadata, not historical predictors.
Panel rows are dependent; no formally estimated effective N.
Retrospective membership reference is not an investor feature.

Exclusiones: 581; distribución completa y concentración en FIRST_ML_COVERAGE_AUDIT.json. No se compararon retornos futuros de filas excluidas.
