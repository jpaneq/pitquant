# First ML fundamental coverage gap

49 meses deficitarios únicos, impacto {3: 37, 2: 11, 1: 1}. 1158 issuer-months faltantes sin duplicar folds/clases.

Causas: {'NO_SEC_IDENTITY': 84, 'REQUIRED_FEATURE_MISSING': 197, 'XBRL_TAG_UNMAPPED': 537, 'UNSUPPORTED_SECTOR': 340}. Clases de evidencia: {'UNVERIFIED_HISTORICAL_ISSUER_COVERAGE': 84, 'CANDIDATE_PIPELINE_MISSINGNESS_NOT_PROVEN_RECOVERABLE': 390, 'RECOVERABLE_PIPELINE_MISSINGNESS': 344, 'STRUCTURAL_CONTRACT_EXCLUSION': 340}. No se atribuye ausencia real a lo no verificado.

El gate no exige las 18 features: tres core obligatorias; 15 opcionales imputables dentro de TRAIN. La propagación latest-known es correcta; replay del mapper existente recupera cero filas.

sec-tags-4 usa DebtAndCapitalLeaseObligations como deuda financiera total reportada (incluye arrendamientos), último conocido; también suma componentes corrientes/no corrientes del mismo periodo. No asume cero ni exige un filing nuevo cada mes. Versiones originales conservadas.

| Mes | Folds | PRICE issuers | FUND issuers | Requeridos | % actual | Gap issuers |
|---|---|---:|---:|---:|---:|---:|
| 2014-09 | [1, 2, 3] | 47 | 29 | 33 | 61.702127659574465 | 4 |
| 2014-10 | [1, 2, 3] | 47 | 29 | 33 | 61.702127659574465 | 4 |
| 2014-11 | [1, 2, 3] | 47 | 29 | 33 | 61.702127659574465 | 4 |
| 2014-12 | [1, 2, 3] | 47 | 29 | 33 | 61.702127659574465 | 4 |
| 2015-01 | [1, 2, 3] | 47 | 29 | 33 | 61.702127659574465 | 4 |
| 2015-02 | [1, 2, 3] | 47 | 29 | 33 | 61.702127659574465 | 4 |
| 2015-03 | [1, 2, 3] | 47 | 28 | 33 | 59.57446808510638 | 5 |
| 2015-04 | [1, 2, 3] | 47 | 30 | 33 | 63.829787234042556 | 3 |
| 2015-05 | [1, 2, 3] | 47 | 30 | 33 | 63.829787234042556 | 3 |
| 2015-06 | [1, 2, 3] | 47 | 31 | 33 | 65.95744680851064 | 2 |
| 2015-07 | [1, 2, 3] | 47 | 31 | 33 | 65.95744680851064 | 2 |
| 2015-08 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2015-09 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2015-10 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2015-11 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2015-12 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2016-01 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2016-02 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2016-03 | [1, 2, 3] | 47 | 32 | 33 | 68.08510638297872 | 1 |
| 2016-04 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-05 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-06 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-07 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-08 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-09 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-10 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-11 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2016-12 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-01 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-02 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-03 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-04 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-05 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-06 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-07 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-08 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-09 | [1, 2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-10 | [2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-11 | [2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2017-12 | [2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2018-01 | [2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2018-02 | [2, 3] | 48 | 32 | 34 | 66.66666666666667 | 2 |
| 2018-03 | [2, 3] | 48 | 33 | 34 | 68.75 | 1 |
| 2018-04 | [2, 3] | 48 | 33 | 34 | 68.75 | 1 |
| 2018-09 | [2, 3] | 48 | 33 | 34 | 68.75 | 1 |
| 2018-10 | [1, 3] | 48 | 33 | 34 | 68.75 | 1 |
| 2018-11 | [1, 3] | 48 | 33 | 34 | 68.75 | 1 |
| 2018-12 | [1, 3] | 48 | 33 | 34 | 68.75 | 1 |
| 2019-09 | [3] | 0 | 0 | 30 | None | 30 |

## Después de la reparación

[
  {
    "fold": 1,
    "before_issuers": {
      "TRAIN": 32,
      "TEST": 37
    },
    "after_issuers": {
      "TRAIN": 37,
      "TEST": 42
    },
    "before": {
      "TRAIN": 1156,
      "TEST": 416
    },
    "after": {
      "TRAIN": 1318,
      "TEST": 476
    }
  },
  {
    "fold": 2,
    "before_issuers": {
      "TRAIN": 34,
      "TEST": 42
    },
    "after_issuers": {
      "TRAIN": 39,
      "TEST": 44
    },
    "before": {
      "TRAIN": 1518,
      "TEST": 472
    },
    "after": {
      "TRAIN": 1735,
      "TEST": 510
    }
  },
  {
    "fold": 3,
    "before_issuers": {
      "TRAIN": 37,
      "TEST": 42
    },
    "after_issuers": {
      "TRAIN": 42,
      "TEST": 44
    },
    "before": {
      "TRAIN": 1932,
      "TEST": 497
    },
    "after": {
      "TRAIN": 2209,
      "TEST": 521
    }
  }
]

Los déficits exactos residuales, candidatos por issuer con causa primaria única, curva de 85 meses, cobertura por issuer y prioridades están en FIRST_ML_FUNDAMENTAL_COVERAGE_GAP.json. Los datos de performance no se usan.


## Límites

Absence in the local ledger is not proof that no historical filing existed.
Unmapped tags are not automatically semantically equivalent or recoverable.
84 missing periods precede available facts for current DIS/AVGO issuer identities; never attach predecessor facts without dated issuer proof.
Structural unsupported sectors are not genuine PIT absence and are counted separately.
