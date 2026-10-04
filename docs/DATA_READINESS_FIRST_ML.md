# DATA READINESS FOR FIRST ML (generado desde la base)

Generado 2026-10-04T21:01:53Z · experimento preparado `FIRST_EQUITY_ML_12M_V0` (NO ejecutado). Fuente de datos de mercado y FX: **Yahoo Finance** (decisión del propietario; VENDOR, `EXPLORATORY_SOURCE`). Ningún gate se ha bajado: `required_securities = 100`.

## Matriz de gates

| Gate | Required | Actual | Status | Blocking reason |
|---|---|---|---|---|
| D02_MONTHLY_RESEARCH_READY | >= 3 feasible walk-forward folds on consecutive READY months | 54/141 months READY, longest run 54, folds 0 | BLOCKED | longest consecutive usable run = 54 months; one fold needs 61 (train_min 36 + purge 12 + embargo 1 + test 12) |
| US_SECURITY_IDENTITY_READY | 0 weak identity members, 0 unresolved lines | see D02 graph metrics | PARTIAL | weak_identity_members > 0 (PPoG Industries line without CUSIP) |
| D05_READY | accepted prices + corporate actions + adjustment method + provenance | Yahoo chart (VENDOR, EXPLORATORY_SOURCE) | BLOCKED | price source is exploratory (owner chose Yahoo): not accepted as canonical; D05 suite (>=98% active / >=95% delisted coverage) not run |
| BENCHMARK_RETURN_BASIS_READY | comparable return + currency basis, accepted provenance | US rows comparable 6797/6797; non-US via USD conversion (PROXY) | PARTIAL | return basis comparable (TR vs TR, USD) but the benchmark series is a Yahoo ETF proxy (not D05-accepted); Spain: IBEX Total Return MISSING, ^IBEX price-only |
| RESEARCH_SECURITY_COVERAGE_READY | >= 100 usable securities | 0 usable (strict); 45 if D05 were accepted; 97 with snapshots | BLOCKED | fewer than 100 securities and none usable until D02/D05 close |
| US_FUNDAMENTALS_READY | >= 30 securities with >= 36 usable PIT months | 38 securities | READY | — |
| HOLDOUT_SEALED | 0 research rows inside 2022-10-01..2025-09-30 | 0 snapshots inside the holdout | READY | — |
| RESEARCH_DATA_READY | all data gates READY | derived | BLOCKED | at least one data gate is not READY |
| FIRST_ML_BASELINE_READY | all required gates READY | false | BLOCKED | required gates not READY: D02_MONTHLY_RESEARCH_READY, US_SECURITY_IDENTITY_READY, D05_READY, BENCHMARK_RETURN_BASIS_READY, RESEARCH_SECURITY_COVERAGE_READY, RESEARCH_DATA_READY |

`FIRST_ML_BASELINE_READY = false` (calcularlo no entrena nada).

## D02 mensual

| métrica | valor |
|---|---|
| total_months | 141 |
| ready_months | 54 |
| partial_months | 0 |
| blocked_months | 6 |
| no_anchor_months | 81 |
| coverage_pct | 38.300 |
| longest_run | 54 |
| feasible_folds | 0 |
| reason_if_no_folds | longest consecutive usable run = 54 months; one fold needs 61 (train_min 36 + purge 12 + embargo 1 + test 12) |

Walk-forward factible (train_min 36, purge 12, embargo 1, test 12): **0 folds** — longest consecutive usable run = 54 months; one fold needs 61 (train_min 36 + purge 12 + embargo 1 + test 12)

| month | expected_universe | resolved_members | unresolved_members | identity_resolved | membership_evidence | status | blocking_reason |
|---|---|---|---|---|---|---|---|
| 2011-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-10 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-11 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2011-12 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-10 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-11 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2012-12 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-10 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-11 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2013-12 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-10 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-11 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2014-12 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-10 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-11 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2015-12 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-10 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-11 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2016-12 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-01 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-02 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-03 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-04 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-05 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-06 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-07 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-08 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-09 | — | — | 1 | False | — | NO_ANCHOR | no anchor on one side of this date inside the pre-holdout chain |
| 2017-10 | — | — | 1 | False | segment 2017-09-30→2018-03-31 | BLOCKED | 2 securities with an effective-date uncertainty covering this decision_at |
| 2017-11 | — | — | 1 | False | segment 2017-09-30→2018-03-31 | BLOCKED | 2 securities with an effective-date uncertainty covering this decision_at |
| 2017-12 | — | — | 1 | False | segment 2017-09-30→2018-03-31 | BLOCKED | 2 securities with an effective-date uncertainty covering this decision_at |
| 2018-01 | — | — | 1 | False | segment 2017-09-30→2018-03-31 | BLOCKED | 2 securities with an effective-date uncertainty covering this decision_at |
| 2018-02 | — | — | 1 | False | segment 2017-09-30→2018-03-31 | BLOCKED | 2 securities with an effective-date uncertainty covering this decision_at |
| 2018-03 | — | — | 1 | False | segment 2017-09-30→2018-03-31 | BLOCKED | 2 securities with an effective-date uncertainty covering this decision_at |
| 2018-04 | 504 | 504 | — | True | segment 2018-03-31→2018-09-30; forward==backward | READY | — |
| 2018-05 | 504 | 504 | — | True | segment 2018-03-31→2018-09-30; forward==backward | READY | — |
| 2018-06 | 504 | 504 | — | True | segment 2018-03-31→2018-09-30; forward==backward | READY | — |
| 2018-07 | 504 | 504 | — | True | segment 2018-03-31→2018-09-30; forward==backward | READY | — |
| 2018-08 | 504 | 504 | — | True | segment 2018-03-31→2018-09-30; forward==backward | READY | — |
| 2018-09 | 504 | 504 | — | True | segment 2018-03-31→2018-09-30; forward==backward | READY | — |
| 2018-10 | 504 | 504 | — | True | segment 2018-09-30→2019-03-31; forward==backward | READY | — |
| 2018-11 | 504 | 504 | — | True | segment 2018-09-30→2019-03-31; forward==backward | READY | — |
| 2018-12 | 504 | 504 | — | True | segment 2018-09-30→2019-03-31; forward==backward | READY | — |
| 2019-01 | 504 | 504 | — | True | segment 2018-09-30→2019-03-31; forward==backward | READY | — |
| 2019-02 | 504 | 504 | — | True | segment 2018-09-30→2019-03-31; forward==backward | READY | — |
| 2019-03 | 504 | 504 | — | True | segment 2018-09-30→2019-03-31; forward==backward | READY | — |
| 2019-04 | 504 | 504 | — | True | segment 2019-03-31→2019-09-30; forward==backward | READY | — |
| 2019-05 | 504 | 504 | — | True | segment 2019-03-31→2019-09-30; forward==backward | READY | — |
| 2019-06 | 505 | 505 | — | True | segment 2019-03-31→2019-09-30; forward==backward | READY | — |
| 2019-07 | 504 | 504 | — | True | segment 2019-03-31→2019-09-30; forward==backward | READY | — |
| 2019-08 | 504 | 504 | — | True | segment 2019-03-31→2019-09-30; forward==backward | READY | — |
| 2019-09 | 504 | 504 | — | True | segment 2019-03-31→2019-09-30; forward==backward | READY | — |
| 2019-10 | 505 | 505 | — | True | segment 2019-09-30→2019-12-31; forward==backward | READY | — |
| 2019-11 | 505 | 505 | — | True | segment 2019-09-30→2019-12-31; forward==backward | READY | — |
| 2019-12 | 505 | 505 | — | True | segment 2019-09-30→2019-12-31; forward==backward | READY | — |
| 2020-01 | 505 | 505 | — | True | segment 2019-12-31→2020-03-31; forward==backward | READY | — |
| 2020-02 | 505 | 505 | — | True | segment 2019-12-31→2020-03-31; forward==backward | READY | — |
| 2020-03 | 505 | 505 | — | True | segment 2019-12-31→2020-03-31; forward==backward | READY | — |
| 2020-04 | 505 | 505 | — | True | segment 2020-03-31→2020-06-30; forward==backward | READY | — |
| 2020-05 | 505 | 505 | — | True | segment 2020-03-31→2020-06-30; forward==backward | READY | — |
| 2020-06 | 505 | 505 | — | True | segment 2020-03-31→2020-06-30; forward==backward | READY | — |
| 2020-07 | 505 | 505 | — | True | segment 2020-06-30→2020-09-30; forward==backward | READY | — |
| 2020-08 | 505 | 505 | — | True | segment 2020-06-30→2020-09-30; forward==backward | READY | — |
| 2020-09 | 505 | 505 | — | True | segment 2020-06-30→2020-09-30; forward==backward | READY | — |
| 2020-10 | 505 | 505 | — | True | segment 2020-09-30→2020-12-31; forward==backward | READY | — |
| 2020-11 | 505 | 505 | — | True | segment 2020-09-30→2020-12-31; forward==backward | READY | — |
| 2020-12 | 505 | 505 | — | True | segment 2020-09-30→2020-12-31; forward==backward | READY | — |
| 2021-01 | 505 | 505 | — | True | segment 2020-12-31→2021-03-31; forward==backward | READY | — |
| 2021-02 | 505 | 505 | — | True | segment 2020-12-31→2021-03-31; forward==backward | READY | — |
| 2021-03 | 505 | 505 | — | True | segment 2020-12-31→2021-03-31; forward==backward | READY | — |
| 2021-04 | 505 | 505 | — | True | segment 2021-03-31→2021-06-30; forward==backward | READY | — |
| 2021-05 | 505 | 505 | — | True | segment 2021-03-31→2021-06-30; forward==backward | READY | — |
| 2021-06 | 505 | 505 | — | True | segment 2021-03-31→2021-06-30; forward==backward | READY | — |
| 2021-07 | 505 | 505 | — | True | segment 2021-06-30→2021-09-30; forward==backward | READY | — |
| 2021-08 | 505 | 505 | — | True | segment 2021-06-30→2021-09-30; forward==backward | READY | — |
| 2021-09 | 505 | 505 | — | True | segment 2021-06-30→2021-09-30; forward==backward | READY | — |
| 2021-10 | 505 | 505 | — | True | segment 2021-09-30→2021-12-31; forward==backward | READY | — |
| 2021-11 | 505 | 505 | — | True | segment 2021-09-30→2021-12-31; forward==backward | READY | — |
| 2021-12 | 505 | 505 | — | True | segment 2021-09-30→2021-12-31; forward==backward | READY | — |
| 2022-01 | 505 | 505 | — | True | segment 2021-12-31→2022-03-31; forward==backward | READY | — |
| 2022-02 | 505 | 505 | — | True | segment 2021-12-31→2022-03-31; forward==backward | READY | — |
| 2022-03 | 505 | 505 | — | True | segment 2021-12-31→2022-03-31; forward==backward | READY | — |
| 2022-04 | 505 | 505 | — | True | segment 2022-03-31→2022-06-30; forward==backward | READY | — |
| 2022-05 | 504 | 504 | — | True | segment 2022-03-31→2022-06-30; forward==backward | READY | — |
| 2022-06 | 504 | 504 | — | True | segment 2022-03-31→2022-06-30; forward==backward | READY | — |
| 2022-07 | 503 | 503 | — | True | segment 2022-06-30→2022-09-30; forward==backward | READY | — |
| 2022-08 | 503 | 503 | — | True | segment 2022-06-30→2022-09-30; forward==backward | READY | — |
| 2022-09 | 503 | 503 | — | True | segment 2022-06-30→2022-09-30; forward==backward | READY | — |

## Cobertura de securities (96 vs 100)

| métrica | valor |
|---|---|
| required | 100 |
| configured_tickers | 100 |
| with_prices | 100 |
| with_snapshots | 97 |
| configured_without_prices | ['AAPL', 'CABK', 'MSFT', 'NTGY', 'ROG', 'SAN'] |
| usable_strict | 0 |
| usable_preview | 45 |

| security_id | ticker_at_T | issuer_id | market | first_date | last_date | identity_status | price_status | fundamental_status | reason_not_usable |
|---|---|---|---|---|---|---|---|---|---|
| d224cb0b | — |  | XNYS | 1995-01-03 | 2026-10-01 | NO_ISSUER_LINK | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | OTHER: no snapshots built |
| cd8b8a8f | — |  | XNYS | 1995-01-03 | 2026-10-01 | NO_ISSUER_LINK | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | OTHER: no snapshots built |
| 4d1aedb4 | CTG | 45358a3c | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| c078ea25 | IBE | ceb549c8 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 35c77f24 | REP | b050f4a2 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 95b1b253 | TEF | 0c10afe8 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| aa330b59 | ACS | 21cb4f9e | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 04499b95 | SCH | 97df9b36 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 9eb07b86 | BBVA | 79fccbec | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 10fc3d3d | ITX | 9b86e623 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| ce79cc0a | ENG | ee1e5d70 | XMAD | 2023-12-19 | 2024-07-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | PRICES: fewer than 30 bars |
| 52322e74 | CRI | b915f41b | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 61f8190e | AMS | 265c8a37 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 23206ded | ELE |  | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 2c882a14 | FER | 26daf587 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 1fecea5c | KO | aa2f4d8a | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| c24e70f1 | VTI |  | XNYS | 2001-05-31 | 2026-10-01 | NO_ISSUER_LINK | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | BENCHMARK_SERIES (not a research security) |
| 27615e6f | JNJ | ad4de1d1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| b8dddadd | JPM | 361c0e7e | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 67cab159 | XOM | d225df5a | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | INSUFFICIENT_HISTORY | — |
| 140de420 | PG | 658db81b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 3e44c4d0 | AMZN | 2936853c | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 6e75fc3b | GOOGL | e1d78079 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 6e6e9ba4 | NVDA | 61c3be3f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| b13f6397 | META | 22876d90 | XNYS | 2012-05-18 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| dccdb7a3 | V | b66cccb6 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 7eba0f34 | UNH | 81bd0de3 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 85875435 | LLY | 29348354 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 60e8375b | AVGO | 808dd69f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | INSUFFICIENT_HISTORY | — |
| a39a3cf8 | TSLA | 43b4af2b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 7f98b411 | MA | 1b8f5b0b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 56b48939 | COST | 9eb7b399 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| f32474b2 | HD | d58f8c52 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 1dc79d7e | WMT | 3e4073c5 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| b8194184 | ABBV | dc457a14 | XNYS | 2013-01-02 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 8f5dd8bc | MRK | b60da8da | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 71598032 | CVX | e305a204 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| eb3c38c1 | BAC | d0a61d20 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 66217c41 | ORCL | b444fd32 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 18bcc934 | CRM | 19e51e57 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 631cae7f | NFLX | 0dcb90eb | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 52e8fe35 | ADBE | 82d133a7 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 9abd13cb | CSCO | 307a428c | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| a358721b | PEP | e2c4212f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 6eb3dc49 | TMO | 93c70d73 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| e8c5c52f | ACN | 5155d771 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 50b87e9d | MCD | 5f8f8e10 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| eaf31854 | ABT | ea9d8dd9 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| f0efb37f | LIN | 51d6d72d | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | INSUFFICIENT_HISTORY | — |
| 1efeccbc | DIS | 46c5da7d | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | INSUFFICIENT_HISTORY | — |
| 485fa49d | WFC | e7f3242f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 257b7380 | CAT | bbacfef6 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 4b7851e2 | IBM | e07fdae0 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 9a8fc57b | GE | 3abd4af0 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 555f0c85 | QCOM | ea8c8ed1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 0d560a31 | TXN | f8fc0393 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 64352eea | AMGN | d8da7795 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 1ea23764 | INTU | 130bb611 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| c2642c7d | VZ | 7103e001 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| f597e07d | PFE | 4294108a | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 2d773a5d | BA | 74a5c72d | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 9983b4aa | HON | c7f542ea | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 93b9ac92 | UNP | ca510d2e | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| fbca5260 | LOW | 4bebe7e1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| aed9f0f2 | SPGI | 9d3bc125 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 5ca6f391 | NEE | 04afd841 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| ee89281c | RTX | 53b6d813 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| b36ce627 | LMT | afd7ffb3 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| 16d3f78c | UPS | 69a34f0b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | EXPLORATORY_SOURCE (Yahoo, VENDOR) | OK | — |
| beffff95 | ASML |  | XAMS | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 28c786a4 | NESN |  | XSWX | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| c48e7d66 | NOVN |  | XSWX | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 48a569ee | SAP |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 5bc7a3d3 | SIE |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 238704f0 | ALV |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| afb82f95 | AIR |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 42cd8596 | MC |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 6544caf0 | OR |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| cae3f007 | SU |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 5186a8c6 | TTE |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| d6164473 | AZN |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 4b803cf8 | SHEL |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 1d23d05c | HSBA |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 359f0e99 | ULVR |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| b0ffe77c | BP |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| fecf17d4 | GSK |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 928c725f | NOVO-B |  | XCSE | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 7c4b1b9d | ENEL |  | XMIL | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 17fedeb6 | ISP |  | XMIL | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| d3376494 | BHP |  | XASX | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 06c32c6f | CBA |  | XASX | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 82414aa2 | CSL |  | XASX | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 2e35be8c | RY |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 6227956b | TD |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 576169af | SHOP |  | XTSE | 2015-05-21 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| fe9d3e5c | ENB |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 5cec853a | 7203 |  | XTKS | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 7e6c5b98 | 6758 |  | XTKS | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| e3230ff5 | 9984 |  | XTKS | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 4ba66cf7 | 8306 |  | XTKS | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| 3137e1cf | 7974 |  | XTKS | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NOT_REGISTERED | — |
| cb5de976 | SPY |  | XNYS | 2011-01-03 | 2026-10-02 | NO_ISSUER_LINK | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | BENCHMARK_SERIES (not a research security) |
| 0c0022b8 | URTH |  | XNYS | 2012-01-12 | 2026-10-02 | NO_ISSUER_LINK | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | BENCHMARK_SERIES (not a research security) |
| 3ba7c569 | ^IBEX |  | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | EXPLORATORY_SOURCE (Yahoo, VENDOR) | NONE | BENCHMARK_SERIES (not a research security) |

## Fundamentales: securities con ≥36 meses PIT utilizables

38 de los que tienen snapshots (requeridos 30).

| ticker | meses utilizables | primero | último | snapshots |
|---|---|---|---|---|
| PG | 133 | 2011-09-01 | 2022-09-01 | 140 |
| MCD | 133 | 2011-03-01 | 2022-09-01 | 140 |
| MA | 133 | 2011-03-01 | 2022-09-01 | 140 |
| WMT | 132 | 2011-04-01 | 2022-09-01 | 140 |
| INTU | 132 | 2011-10-03 | 2022-09-01 | 140 |
| UNP | 132 | 2011-03-01 | 2022-09-01 | 140 |
| CSCO | 132 | 2011-10-03 | 2022-09-01 | 140 |
| SPGI | 132 | 2011-03-01 | 2022-09-01 | 140 |
| LMT | 132 | 2011-03-01 | 2022-09-01 | 140 |
| VZ | 132 | 2011-03-01 | 2022-09-01 | 140 |
| RTX | 132 | 2011-03-01 | 2022-09-01 | 140 |
| HD | 132 | 2011-04-01 | 2022-09-01 | 140 |
| COST | 131 | 2011-11-01 | 2022-09-01 | 140 |
| AMGN | 130 | 2011-03-01 | 2022-09-01 | 140 |
| CVX | 130 | 2011-03-01 | 2022-09-01 | 140 |
| MRK | 130 | 2011-03-01 | 2022-09-01 | 140 |
| V | 130 | 2011-12-01 | 2022-09-01 | 140 |
| PFE | 130 | 2011-03-01 | 2022-09-01 | 140 |
| LLY | 129 | 2011-03-01 | 2022-09-01 | 140 |
| PEP | 129 | 2011-03-01 | 2022-09-01 | 140 |
| TXN | 127 | 2012-03-01 | 2022-09-01 | 140 |
| UPS | 127 | 2011-03-01 | 2022-09-01 | 140 |
| AMZN | 127 | 2012-03-01 | 2022-09-01 | 140 |
| HON | 127 | 2012-03-01 | 2022-09-01 | 140 |
| TSLA | 127 | 2012-03-01 | 2022-09-01 | 140 |
| ABT | 103 | 2014-03-03 | 2022-09-01 | 140 |
| NVDA | 102 | 2014-04-01 | 2022-09-01 | 140 |
| CRM | 100 | 2013-10-01 | 2022-09-01 | 140 |
| NEE | 94 | 2011-03-01 | 2020-04-01 | 140 |
| ADBE | 90 | 2015-04-01 | 2022-09-01 | 140 |
| LOW | 90 | 2015-04-01 | 2022-09-01 | 140 |
| QCOM | 86 | 2015-08-03 | 2022-09-01 | 140 |
| GOOGL | 73 | 2016-03-01 | 2022-09-01 | 140 |
| IBM | 55 | 2018-03-01 | 2022-09-01 | 140 |
| NFLX | 53 | 2018-05-01 | 2022-09-01 | 140 |
| AVGO | 45 | 2019-01-02 | 2022-09-01 | 140 |
| JNJ | 40 | 2019-03-01 | 2022-09-01 | 140 |
| KO | 37 | 2019-03-01 | 2022-09-01 | 140 |
| LIN | 35 | 2019-04-01 | 2022-09-01 | 140 |
| DIS | 34 | 2019-12-02 | 2022-09-01 | 140 |
| TMO | 34 | 2019-12-02 | 2022-09-01 | 140 |
| ABBV | 31 | 2020-03-02 | 2022-09-01 | 116 |
| BA | 26 | 2020-08-03 | 2022-09-01 | 140 |
| ORCL | 3 | 2022-07-01 | 2022-09-01 | 140 |
| SCH | 0 | — | — | 140 |
| ITX | 0 | — | — | 140 |
| ELE | 0 | — | — | 140 |
| FER | 0 | — | — | 140 |
| REP | 0 | — | — | 140 |
| CTG | 0 | — | — | 140 |
| CRI | 0 | — | — | 140 |
| AMS | 0 | — | — | 140 |
| TEF | 0 | — | — | 140 |
| BBVA | 0 | — | — | 140 |
| ACS | 0 | — | — | 140 |
| IBE | 0 | — | — | 140 |
| CBA | 0 | — | — | 140 |
| CSL | 0 | — | — | 140 |
| BHP | 0 | — | — | 140 |
| CAT | 0 | — | — | 140 |
| WFC | 0 | — | — | 140 |
| XOM | 0 | — | — | 140 |
| UNH | 0 | — | — | 140 |
| GE | 0 | — | — | 140 |
| JPM | 0 | — | — | 140 |
| ACN | 0 | — | — | 140 |
| BAC | 0 | — | — | 140 |
| META | 0 | — | — | 124 |
| ISP | 0 | — | — | 140 |
| ENEL | 0 | — | — | 140 |
| HSBA | 0 | — | — | 140 |
| ULVR | 0 | — | — | 140 |
| SHEL | 0 | — | — | 140 |
| BP | 0 | — | — | 140 |
| AZN | 0 | — | — | 140 |
| GSK | 0 | — | — | 140 |
| ALV | 0 | — | — | 140 |
| SAP | 0 | — | — | 140 |
| SIE | 0 | — | — | 140 |
| NESN | 0 | — | — | 140 |
| NOVN | 0 | — | — | 140 |
| RY | 0 | — | — | 140 |
| TD | 0 | — | — | 140 |
| ENB | 0 | — | — | 140 |
| SHOP | 0 | — | — | 88 |
| 7974 | 0 | — | — | 140 |
| 8306 | 0 | — | — | 140 |
| 7203 | 0 | — | — | 140 |
| 6758 | 0 | — | — | 140 |
| 9984 | 0 | — | — | 140 |
| MC | 0 | — | — | 140 |
| TTE | 0 | — | — | 140 |
| OR | 0 | — | — | 140 |
| AIR | 0 | — | — | 140 |
| SU | 0 | — | — | 140 |
| NOVO-B | 0 | — | — | 140 |
| ASML | 0 | — | — | 140 |

## Embudo de filas (12M)

### strict_PRICE

| etapa | filas |
|---|---|
| raw snapshots | 14749 |
| − OOT | 1261 |
| − UNIVERSE_NOT_CANONICAL | 10626 |
| − NOT_INDEX_MEMBER_AT_T | 40 |
| − SECURITY_IDENTITY_NOT_READY | 432 |
| − PRICE_DATA_NOT_READY | 2390 |
| = eligible | 0 |
| securities con filas elegibles | 0 |

### strict_FUNDAMENTALS

| etapa | filas |
|---|---|
| raw snapshots | 14749 |
| − OOT | 1261 |
| − UNIVERSE_NOT_CANONICAL | 10626 |
| − NOT_INDEX_MEMBER_AT_T | 40 |
| − SECURITY_IDENTITY_NOT_READY | 432 |
| − PRICE_DATA_NOT_READY | 2390 |
| = eligible | 0 |
| securities con filas elegibles | 0 |

### preview_if_D05_accepted_PRICE

| etapa | filas |
|---|---|
| raw snapshots | 14749 |
| − OOT | 1261 |
| − UNIVERSE_NOT_CANONICAL | 10626 |
| − NOT_INDEX_MEMBER_AT_T | 40 |
| − SECURITY_IDENTITY_NOT_READY | 432 |
| − TARGET_IMMATURE | 540 |
| = eligible | 1850 |
| securities con filas elegibles | 45 |

### preview_if_D05_accepted_FUNDAMENTALS

| etapa | filas |
|---|---|
| raw snapshots | 14749 |
| − OOT | 1261 |
| − UNIVERSE_NOT_CANONICAL | 10626 |
| − NOT_INDEX_MEMBER_AT_T | 40 |
| − SECURITY_IDENTITY_NOT_READY | 432 |
| − TARGET_IMMATURE | 540 |
| − FUNDAMENTALS_NOT_READY | 468 |
| = eligible | 1382 |
| securities con filas elegibles | 38 |

## Benchmarks por mercado (12M)

| market | region | security_ccy | benchmark | bench_ccy | return_type | currency_basis | quality | comparables/filas | bloqueo |
|---|---|---|---|---|---|---|---|---|---|
| XAMS | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 117/153 | — |
| XASX | ASIA | AUD | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 351/459 | — |
| XCSE | EU | DKK | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 117/153 | — |
| XETR | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 351/459 | — |
| XLON | EU | GBP | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 702/918 | — |
| XMAD | ES | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 1404/1836 | — |
| XMIL | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 234/306 | — |
| XNYS | US | USD | SPY_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 6797/8069 | — |
| XPAR | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 585/765 | — |
| XSWX | EU | CHF | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 234/306 | — |
| XTKS | ASIA | JPY | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 585/765 | — |
| XTSE | NA | CAD | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 428/560 | — |

## Blockers restantes y mínima acción correcta

| gate | qué falla | evidencia que falta | mínima acción |
|---|---|---|---|
| D02_MONTHLY_RESEARCH_READY | cadena de 54 meses consecutivos (60 requeridos por el gate existente; el contrato de folds necesita 61 + 12 por fold: longest consecutive usable run = 54 months; one fold needs 61 (train_min 36 + purge 12 + embargo 1 + test 12)); 0 anclas antes de 2017-09 | identidad de la línea «PPoG Industries, Inc.» (N-30D 2017-09-30, sin CUSIP) con PPG Industries; anclas N-30D 2014-09→2017-03 (`--extend`) | decisión del propietario sobre la identidad PPoG→PPG (evidencia candidata: valor/acciones de la línea = 108,66 = cierre de PPG el 2017-09-29, Yahoo, VENDOR: NO se aplica como evidencia oficial) y después `scripts/ingest_spy_anchors.py --extend` |
| US_SECURITY_IDENTITY_READY | 2 miembros con identidad débil (sin CUSIP/ISIN oficial); el puente investigación→ancla es DERIVADO (nombre exacto único) para 44 de 52 | CUSIP oficial por emisor (Schedule 13G, como AAPL/MSFT en ADR-0024) | extender `ingest_cusip_evidence.py` a los emisores de investigación |
| D05_READY | fuente de precios = Yahoo (exploratoria, elegida por el propietario) | suite D05 (cobertura ≥98 % activos / ≥95 % excluidos), corporate actions oficiales, método de ajuste y proveniencia aceptados | aceptación explícita de una fuente o suite D05 sobre Yahoo; no se eleva automáticamente |
| BENCHMARK_RETURN_BASIS_READY | base TR/USD comparable pero la serie es un ETF proxy de Yahoo; IBEX 35 Total Return (ES0SI0000047) sin serie histórica auditable | serie oficial IBEX TR; D05 | idem D05; España queda con URTH+FX sólo diagnóstico |
| RESEARCH_SECURITY_COVERAGE_READY | 100 requeridos; ver tabla de cobertura | MSFT/AAPL (serie EODHD demo, QA, sin ticker/issuer: guarda de no mezclar fuentes), ENG (22 sesiones) | AAPL/MSFT con precios Yahoo en una security de precio vinculada al ancla; ENG no recuperable; 100 NO se baja (propuesta separada) |
