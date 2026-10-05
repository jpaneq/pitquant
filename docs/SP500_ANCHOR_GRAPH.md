# S&P 500 — grafo de anclas SEC y estándares mensual/diario (generado)

> Generado por `scripts/build_sp500_anchor_graph.py`. No editar a mano. Anclas = composiciones de SPY presentadas a la SEC (`SEC_FILED_INDEX_REPLICATION_ANCHOR`), no `OFFICIAL_SPDJI`.

Holdout 2022-10-01 → 2025-09-30 sellado; ningún ancla posterior a 2022-09-30.

## Estándares

- **D02_MONTHLY_RESEARCH_READY** (puerta del Research Lab): una incertidumbre sobre el día de un evento sólo bloquea las cohortes (decision_at mensuales) que puede cambiar. Las patas del CSV de discovery sin confirmar son `DISCOVERY_UNCORROBORATED` (aviso) y NUNCA invalidan evidencia primaria; una fecha del CSV que discrepa de la oficial es `DISCOVERY_CONFLICT` y no ensancha la fecha primaria.
- **D02_DAILY_CANONICAL_READY**: criterio estricto anterior (cualquier cambio sin resolver o pata de CSV sin confirmar bloquea todo el segmento).

| métrica | mensual (Research) | diario canónico |
|---|---|---|
| verified_anchors | 30 | 30 |
| segments | 29 | 29 |
| validated_segments | 6 | 6 |
| forward_validated_segments | 11 | 11 |
| backward_validated_segments | 11 | 11 |
| monthly_cohorts | 145 | 145 |
| monthly_cohorts_reconstructible | 60 | 18 |
| longest_continuous_period | 60 | 9 |
| post_limit_events_used | 0 | 0 |
| cohortes diarias canónicas / racha | 18 / 9 | |

## Ventana mínima (60): 2017-10-01 → 2022-09-30

- monthly_cohorts 60 · membership_ready **60** · racha continua 60 · cohortes sin ancla 0 (anclas extendidas; eventos e identidad se verifican por separado)

## Ventana preferida (96): 2014-10-01 → 2022-09-30

- monthly_cohorts 96 · membership_ready **60** · racha continua 60 · cohortes sin ancla 0 (anclas extendidas; eventos e identidad se verifican por separado)

## Cohortes (ventana mínima)

| decision_at | estado | segmento | forward = backward | ambigüedad mensual | conflictos primarios |
|---|---|---|---|---|---|
| 2017-10-02 | MEMBERSHIP_READY | 2017-09-30→2018-03-31 | True | 0 | 0 |
| 2017-11-01 | MEMBERSHIP_READY | 2017-09-30→2018-03-31 | True | 0 | 0 |
| 2017-12-01 | MEMBERSHIP_READY | 2017-09-30→2018-03-31 | True | 0 | 0 |
| 2018-01-02 | MEMBERSHIP_READY | 2017-09-30→2018-03-31 | True | 0 | 0 |
| 2018-02-01 | MEMBERSHIP_READY | 2017-09-30→2018-03-31 | True | 0 | 0 |
| 2018-03-01 | MEMBERSHIP_READY | 2017-09-30→2018-03-31 | True | 0 | 0 |
| 2018-04-02 | MEMBERSHIP_READY | 2018-03-31→2018-09-30 | True | 0 | 0 |
| 2018-05-01 | MEMBERSHIP_READY | 2018-03-31→2018-09-30 | True | 0 | 0 |
| 2018-06-01 | MEMBERSHIP_READY | 2018-03-31→2018-09-30 | True | 0 | 0 |
| 2018-07-02 | MEMBERSHIP_READY | 2018-03-31→2018-09-30 | True | 0 | 0 |
| 2018-08-01 | MEMBERSHIP_READY | 2018-03-31→2018-09-30 | True | 0 | 0 |
| 2018-09-04 | MEMBERSHIP_READY | 2018-03-31→2018-09-30 | True | 0 | 0 |
| 2018-10-01 | MEMBERSHIP_READY | 2018-09-30→2019-03-31 | True | 0 | 0 |
| 2018-11-01 | MEMBERSHIP_READY | 2018-09-30→2019-03-31 | True | 0 | 0 |
| 2018-12-03 | MEMBERSHIP_READY | 2018-09-30→2019-03-31 | True | 0 | 0 |
| 2019-01-02 | MEMBERSHIP_READY | 2018-09-30→2019-03-31 | True | 0 | 0 |
| 2019-02-01 | MEMBERSHIP_READY | 2018-09-30→2019-03-31 | True | 0 | 0 |
| 2019-03-01 | MEMBERSHIP_READY | 2018-09-30→2019-03-31 | True | 0 | 0 |
| 2019-04-01 | MEMBERSHIP_READY | 2019-03-31→2019-09-30 | True | 0 | 0 |
| 2019-05-01 | MEMBERSHIP_READY | 2019-03-31→2019-09-30 | True | 0 | 0 |
| 2019-06-03 | MEMBERSHIP_READY | 2019-03-31→2019-09-30 | True | 0 | 0 |
| 2019-07-01 | MEMBERSHIP_READY | 2019-03-31→2019-09-30 | True | 0 | 0 |
| 2019-08-01 | MEMBERSHIP_READY | 2019-03-31→2019-09-30 | True | 0 | 0 |
| 2019-09-03 | MEMBERSHIP_READY | 2019-03-31→2019-09-30 | True | 0 | 0 |
| 2019-10-01 | MEMBERSHIP_READY | 2019-09-30→2019-12-31 | True | 0 | 0 |
| 2019-11-01 | MEMBERSHIP_READY | 2019-09-30→2019-12-31 | True | 0 | 0 |
| 2019-12-02 | MEMBERSHIP_READY | 2019-09-30→2019-12-31 | True | 0 | 0 |
| 2020-01-02 | MEMBERSHIP_READY | 2019-12-31→2020-03-31 | True | 0 | 0 |
| 2020-02-03 | MEMBERSHIP_READY | 2019-12-31→2020-03-31 | True | 0 | 0 |
| 2020-03-02 | MEMBERSHIP_READY | 2019-12-31→2020-03-31 | True | 0 | 0 |
| 2020-04-01 | MEMBERSHIP_READY | 2020-03-31→2020-06-30 | True | 0 | 0 |
| 2020-05-01 | MEMBERSHIP_READY | 2020-03-31→2020-06-30 | True | 0 | 0 |
| 2020-06-01 | MEMBERSHIP_READY | 2020-03-31→2020-06-30 | True | 0 | 0 |
| 2020-07-01 | MEMBERSHIP_READY | 2020-06-30→2020-09-30 | True | 0 | 0 |
| 2020-08-03 | MEMBERSHIP_READY | 2020-06-30→2020-09-30 | True | 0 | 0 |
| 2020-09-01 | MEMBERSHIP_READY | 2020-06-30→2020-09-30 | True | 0 | 0 |
| 2020-10-01 | MEMBERSHIP_READY | 2020-09-30→2020-12-31 | True | 0 | 0 |
| 2020-11-02 | MEMBERSHIP_READY | 2020-09-30→2020-12-31 | True | 0 | 0 |
| 2020-12-01 | MEMBERSHIP_READY | 2020-09-30→2020-12-31 | True | 0 | 0 |
| 2021-01-04 | MEMBERSHIP_READY | 2020-12-31→2021-03-31 | True | 0 | 0 |
| 2021-02-01 | MEMBERSHIP_READY | 2020-12-31→2021-03-31 | True | 0 | 0 |
| 2021-03-01 | MEMBERSHIP_READY | 2020-12-31→2021-03-31 | True | 0 | 0 |
| 2021-04-01 | MEMBERSHIP_READY | 2021-03-31→2021-06-30 | True | 0 | 0 |
| 2021-05-03 | MEMBERSHIP_READY | 2021-03-31→2021-06-30 | True | 0 | 0 |
| 2021-06-01 | MEMBERSHIP_READY | 2021-03-31→2021-06-30 | True | 0 | 0 |
| 2021-07-01 | MEMBERSHIP_READY | 2021-06-30→2021-09-30 | True | 0 | 0 |
| 2021-08-02 | MEMBERSHIP_READY | 2021-06-30→2021-09-30 | True | 0 | 0 |
| 2021-09-01 | MEMBERSHIP_READY | 2021-06-30→2021-09-30 | True | 0 | 0 |
| 2021-10-01 | MEMBERSHIP_READY | 2021-09-30→2021-12-31 | True | 0 | 0 |
| 2021-11-01 | MEMBERSHIP_READY | 2021-09-30→2021-12-31 | True | 0 | 0 |
| 2021-12-01 | MEMBERSHIP_READY | 2021-09-30→2021-12-31 | True | 0 | 0 |
| 2022-01-03 | MEMBERSHIP_READY | 2021-12-31→2022-03-31 | True | 0 | 0 |
| 2022-02-01 | MEMBERSHIP_READY | 2021-12-31→2022-03-31 | True | 0 | 0 |
| 2022-03-01 | MEMBERSHIP_READY | 2021-12-31→2022-03-31 | True | 0 | 0 |
| 2022-04-01 | MEMBERSHIP_READY | 2022-03-31→2022-06-30 | True | 0 | 0 |
| 2022-05-02 | MEMBERSHIP_READY | 2022-03-31→2022-06-30 | True | 0 | 0 |
| 2022-06-01 | MEMBERSHIP_READY | 2022-03-31→2022-06-30 | True | 0 | 0 |
| 2022-07-01 | MEMBERSHIP_READY | 2022-06-30→2022-09-30 | True | 0 | 0 |
| 2022-08-01 | MEMBERSHIP_READY | 2022-06-30→2022-09-30 | True | 0 | 0 |
| 2022-09-01 | MEMBERSHIP_READY | 2022-06-30→2022-09-30 | True | 0 | 0 |

## Reclasificación de gaps

Antes (ficha global, ADR-0032): **95** gaps. Tras la reclasificación y las resoluciones de identidad:

| categoría | n | bloquea membresía | bloquea identidad |
|---|---|---|---|
| PRIMARY_DELTA_UNEXPLAINED | 9 | 9 | 0 |
| PRIMARY_EVENT_MISSING | 141 | 141 | 0 |
| MONTHLY_DATE_AMBIGUITY | 12 | 12 | 0 |
| SECURITY_IDENTITY_ONLY | 65 | 65 | 65 |
| TICKER_OR_NAME_CHANGE | 32 | 0 | 0 |
| SUCCESSOR_SECURITY | 10 | 0 | 0 |
| DISCOVERY_UNCORROBORATED | 22 | 0 | 0 |
| DISCOVERY_CONFLICT | 56 | 0 | 0 |
| TRANSIENT_EVENT_POSSIBLE | 0 | 0 | 0 |
| RESOLVED | 8 | 0 | 0 |

Blockers de membresía reales: **227** · de identidad: **65** + 56 securities sin evidencia oficial de CUSIP/ISIN.

