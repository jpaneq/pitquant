# US — dry-runs de fundamentales, dataset y walk-forward (generado)

> CANDIDATE_MEMBERSHIP_NOT_PROVEN. Ningún modelo entrenado, ninguna etiqueta consumida, holdout 2022-10-01 → 2025-09-30 intacto.

## Cobertura fundamental (SEC ya ingerido)

3 de 682 valores candidatos tienen hechos SEC (288 de 48116 meses-valor posibles). Sin security resuelta no hay vínculo CIK→security: el siguiente cuello de botella tras los precios.

| ticker | security_id | membership_months | fundamental_months_possible | first_fundamental_snapshot | last_fundamental_snapshot | missing_reason |
|---|---|---|---|---|---|---|
| AAPL | cd8b8a8f-e550-49ee-86af-4370b15d03ec | 96 | 96 | 2011-01-20 | 2026-07-31 |  |
| KO | 1fecea5c-9f09-40ff-a8a4-e1e51bef0561 | 96 | 96 | 2011-02-28 | 2026-07-29 |  |
| MSFT | d224cb0b-ddae-45ed-8412-9092f17db14b | 96 | 96 | 2011-01-28 | 2026-07-30 |  |
| A | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AAL | — | 90 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AAP | — | 86 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ABBV | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ABC | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ABMD | — | 52 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ABT | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ACN | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADBE | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADI | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADM | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADP | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADS | — | 69 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADSK | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| ADT | — | 20 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AEE | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AEP | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AES | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AET | — | 50 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AFL | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AGN | — | 6 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AIG | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AIV | — | 75 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AIZ | — | 96 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |
| AJG | — | 76 | 0 | — | — | NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested |

(Se listan los resueltos y 25 de 679 sin security; el resto idéntico: `NO_SECURITY`.)

## Dataset dry-run por cohorte (membresía candidata)

| cohorte | members | identity_ready | fundamentals_ready | prices_ready | corporate_actions_ready | eligible |
|---|---|---|---|---|---|---|
| 2014-10-01 | 497 | 3 | 3 | 0 | 0 | 0 |
| 2015-04-01 | 497 | 3 | 3 | 0 | 0 | 0 |
| 2015-10-01 | 500 | 3 | 3 | 0 | 0 | 0 |
| 2016-04-01 | 500 | 3 | 3 | 0 | 0 | 0 |
| 2016-10-03 | 502 | 3 | 3 | 0 | 0 | 0 |
| 2017-04-03 | 502 | 3 | 3 | 0 | 0 | 0 |
| 2017-10-02 | 503 | 3 | 3 | 0 | 0 | 0 |
| 2018-04-02 | 503 | 3 | 3 | 0 | 0 | 0 |
| 2018-10-01 | 501 | 3 | 3 | 0 | 0 | 0 |
| 2019-04-01 | 502 | 3 | 3 | 0 | 0 | 0 |
| 2019-10-01 | 500 | 3 | 3 | 0 | 0 | 0 |
| 2020-04-01 | 502 | 3 | 3 | 0 | 0 | 0 |
| 2020-10-01 | 504 | 3 | 3 | 0 | 0 | 0 |
| 2021-04-01 | 502 | 3 | 3 | 0 | 0 | 0 |
| 2021-10-01 | 502 | 3 | 3 | 0 | 0 | 0 |
| 2022-04-01 | 501 | 3 | 3 | 0 | 0 | 0 |

(Una de cada 6 cohortes; 96 en total.) Dataset Builder real sobre los valores resueltos: `{"BENCHMARK_UNAVAILABLE": 270, "NO_PRICE_HISTORY": 96, "FEATURES_TOO_SPARSE": 96, "LABEL_WINDOW_TOUCHES_HOLDOUT": 18}` — las filas no elegibles se conservan.

## Walk-forward (PLAN) — ventana mínima 2017-10-01 → 2022-09-30

Horizonte 6M · train_min 60m · validación 12m · purge 1 · embargo 1 · `holdout_overlap = false`

```
no fold can be formed (not enough usable decision dates before the sealed holdout)
```

Horizonte 12M · train_min 60m · validación 12m · purge 1 · embargo 1 · `holdout_overlap = false`

```
no fold can be formed (not enough usable decision dates before the sealed holdout)
```

## Walk-forward (PLAN) — ventana preferida 2014-10-01 → 2022-09-30

Horizonte 6M · train_min 60m · validación 12m · purge 1 · embargo 1 · `holdout_overlap = false`

```
fold train_start train_end   val_start   val_end      n_train  n_val
   0 2014-10-01  2019-02-01  2019-10-01  2020-09-01        53     12
   1 2014-10-01  2020-02-03  2020-10-01  2021-09-01        65     12
   2 2014-10-01  2021-03-01  2021-10-01  2022-03-01        78      6
```

Horizonte 12M · train_min 60m · validación 12m · purge 1 · embargo 1 · `holdout_overlap = false`

```
fold train_start train_end   val_start   val_end      n_train  n_val
   0 2014-10-01  2018-08-01  2019-10-01  2020-09-01        47     12
   1 2014-10-01  2019-08-01  2020-10-01  2021-09-01        59     12
```
