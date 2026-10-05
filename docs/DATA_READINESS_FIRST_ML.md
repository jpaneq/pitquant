# DATA READINESS FOR FIRST ML (generado desde la base)

Generado 2026-10-05T17:10:58Z · experimento preparado `FIRST_EQUITY_ML_12M_V0` (NO ejecutado). Fuente de datos de mercado y FX: **Yahoo Finance** (decisión del propietario; VENDOR, `CANONICAL_PROVIDER_FOR_PITQUANT`). Ningún gate se ha bajado: `required_securities = 100`.

## Matriz de gates

| Gate | Required | Actual | Status | Blocking reason |
|---|---|---|---|---|
| D02_MONTHLY_RESEARCH_READY | 85 READY months positioned 2014-09..2021-09; >= 3 LABEL_SAFE folds; statistical coverage separate | 72/141 READY; required history 60/85; target calendar folds 3, label-safe 0 | BLOCKED | 25 required membership months blocked; 0 LABEL_SAFE folds; need 3. Coverage not evaluated and does not decide D02. |
| US_SECURITY_IDENTITY_READY | 0 weak identity members, 0 unresolved lines | 40 weak identity securities; 0 unresolved anchor lines | PARTIAL | unresolved identity evidence; see D02 graph metrics |
| D05_READY | accepted prices + corporate actions + adjustment method + provenance | Yahoo Finance (CANONICAL_PROVIDER_FOR_PITQUANT, VENDOR) | READY | — |
| BENCHMARK_RETURN_BASIS_READY | first ML US scope: comparable return + currency basis, accepted provenance | US rows comparable 7000/7000; non-US via USD conversion (PROXY) | READY | — |
| RESEARCH_SECURITY_COVERAGE_READY | >= 100 usable securities | 51 usable (strict); 51 if D05 were accepted; 100 with snapshots | BLOCKED | fewer than 100 securities satisfy all PIT eligibility conditions; see the per-security audit |
| US_FUNDAMENTALS_READY | >= 30 securities with >= 36 usable PIT months | 40 securities | READY | — |
| HOLDOUT_SEALED | 0 research rows inside 2022-10-01..2025-09-30 | 0 snapshots inside the holdout | READY | — |
| RESEARCH_DATA_READY | all data gates READY | derived | BLOCKED | at least one data gate is not READY |
| FIRST_ML_BASELINE_READY | all required gates READY | false | BLOCKED | required gates not READY: D02_MONTHLY_RESEARCH_READY, US_SECURITY_IDENTITY_READY, RESEARCH_SECURITY_COVERAGE_READY, RESEARCH_DATA_READY |

`FIRST_ML_BASELINE_READY = false` (calcularlo no entrena nada).

La matriz corresponde al primer ML. Los `flags` del JSON describen el Research Lab histórico y su disponibilidad para recopilar features; no autorizan entrenamiento ni sustituyen estos gates.

## Folds factibles

| fold | train start | train end | test start | test end | train months | purge | embargo |
|---|---|---|---|---|---|---|---|
| 0 | 2014-09 | 2017-09 | 2018-10 | 2019-09 | 37 | 12 | 1 |
| 1 | 2014-09 | 2018-09 | 2019-10 | 2020-09 | 49 | 12 | 1 |
| 2 | 2014-09 | 2019-09 | 2020-10 | 2021-09 | 61 | 12 | 1 |

## D02 mensual

CALENDAR_FOLD = structural dates; LABEL_SAFE_FOLD = complete required membership history and TRAIN labels available at fit, plus twelve valid TEST outcome months; ML_ELIGIBLE_FOLD adds statistical coverage, NOT_YET_EVALUATED. Sample minimum remains UNSPECIFIED_CONTRACT and does not decide label safety. TRAIN cutoff = first TEST decision; TEST cutoff = audit time. See ADR-0055 V2.

| fold | calendar TEST rows | mature targets | benchmark ready | price ready | eligible | holdout excluded | TEST label safe | full fold label safe |
|---|---|---|---|---|---|---|---|---|
| 0 | 660 | 660 | 660 | 660 | 599 | 0 | True | False |
| 1 | 660 | 660 | 660 | 660 | 600 | 0 | True | False |
| 2 | 660 | 660 | 660 | 660 | 609 | 0 | True | False |

Every TRAIN/TEST row's target_start, target_end, actual_exit_session, target_mature_at, availability cutoff and exclusion reasons are recorded in `FIRST_ML_FOLD_AUDIT.json`.

Derived requirement: 2014-09..2021-09, 85 continuous READY months. Last admissible decision 2021-09-01T13:30:00+00:00; target end 2022-09-01T13:30:00+00:00; expected earliest maturity 2022-08-31T21:00:00+00:00. No outcomes read for this derivation.

| métrica | valor |
|---|---|
| total_months | 141 |
| ready_months | 72 |
| membership_ready_months | 72 |
| partial_months | 0 |
| blocked_months | 69 |
| no_anchor_months | 0 |
| coverage_pct | 51.100 |
| longest_run | 72 |
| longest_membership_run | 72 |
| feasible_folds | 1 |
| reason_if_no_folds | — |
| required_continuous_months | 85 |
| weak_identity_securities | 40 |
| required_history_start | 2014-09 |
| required_history_end | 2021-09 |
| required_months_ready | 60 |
| required_months_blocked | 25 |
| longest_relevant_run | 60 |
| calendar_folds | 3 |
| label_safe_folds | 0 |
| test_label_safe_folds | 3 |
| coverage_gate_evaluated | False |

Walk-forward factible (train_min 36, purge 12, embargo 1, test 12): 3 folds

| month | expected_universe | resolved_members | unresolved_members | identity_resolved | membership_evidence | status | blocking_reason |
|---|---|---|---|---|---|---|---|
| 2011-01 | — | — | 1 | False | segment 2010-09-30→2011-03-31 | BLOCKED | 17 securities with an effective-date uncertainty covering this decision_at |
| 2011-02 | — | — | 1 | False | segment 2010-09-30→2011-03-31 | BLOCKED | 19 securities with an effective-date uncertainty covering this decision_at |
| 2011-03 | — | — | 1 | False | segment 2010-09-30→2011-03-31 | BLOCKED | 19 securities with an effective-date uncertainty covering this decision_at |
| 2011-04 | — | — | 1 | False | segment 2011-03-31→2011-09-30 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2011-05 | — | — | 1 | False | segment 2011-03-31→2011-09-30 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2011-06 | — | — | 1 | False | segment 2011-03-31→2011-09-30 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2011-07 | — | — | 1 | False | segment 2011-03-31→2011-09-30 | BLOCKED | 14 securities with an effective-date uncertainty covering this decision_at |
| 2011-08 | — | — | 1 | False | segment 2011-03-31→2011-09-30 | BLOCKED | 14 securities with an effective-date uncertainty covering this decision_at |
| 2011-09 | — | — | 1 | False | segment 2011-03-31→2011-09-30 | BLOCKED | 14 securities with an effective-date uncertainty covering this decision_at |
| 2011-10 | — | — | 1 | False | segment 2011-09-30→2012-03-31 | BLOCKED | 39 securities with an effective-date uncertainty covering this decision_at |
| 2011-11 | — | — | 1 | False | segment 2011-09-30→2012-03-31 | BLOCKED | 39 securities with an effective-date uncertainty covering this decision_at |
| 2011-12 | — | — | 1 | False | segment 2011-09-30→2012-03-31 | BLOCKED | 39 securities with an effective-date uncertainty covering this decision_at |
| 2012-01 | — | — | 1 | False | segment 2011-09-30→2012-03-31 | BLOCKED | 39 securities with an effective-date uncertainty covering this decision_at |
| 2012-02 | — | — | 1 | False | segment 2011-09-30→2012-03-31 | BLOCKED | 39 securities with an effective-date uncertainty covering this decision_at |
| 2012-03 | — | — | 1 | False | segment 2011-09-30→2012-03-31 | BLOCKED | 39 securities with an effective-date uncertainty covering this decision_at |
| 2012-04 | — | — | 1 | False | segment 2012-03-31→2012-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2012-05 | — | — | 1 | False | segment 2012-03-31→2012-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2012-06 | — | — | 1 | False | segment 2012-03-31→2012-09-30 | BLOCKED | 25 securities with an effective-date uncertainty covering this decision_at |
| 2012-07 | — | — | 1 | False | segment 2012-03-31→2012-09-30 | BLOCKED | 25 securities with an effective-date uncertainty covering this decision_at |
| 2012-08 | — | — | 1 | False | segment 2012-03-31→2012-09-30 | BLOCKED | 25 securities with an effective-date uncertainty covering this decision_at |
| 2012-09 | — | — | 1 | False | segment 2012-03-31→2012-09-30 | BLOCKED | 25 securities with an effective-date uncertainty covering this decision_at |
| 2012-10 | — | — | 1 | False | segment 2012-09-30→2013-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2012-11 | — | — | 1 | False | segment 2012-09-30→2013-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2012-12 | — | — | 1 | False | segment 2012-09-30→2013-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2013-01 | — | — | 1 | False | segment 2012-09-30→2013-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2013-02 | — | — | 1 | False | segment 2012-09-30→2013-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2013-03 | — | — | 1 | False | segment 2012-09-30→2013-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2013-04 | — | — | 1 | False | segment 2013-03-31→2013-09-30 | BLOCKED | 3 securities with an effective-date uncertainty covering this decision_at |
| 2013-05 | — | — | 1 | False | segment 2013-03-31→2013-09-30 | BLOCKED | 3 securities with an effective-date uncertainty covering this decision_at |
| 2013-06 | — | — | 1 | False | segment 2013-03-31→2013-09-30 | BLOCKED | 3 securities with an effective-date uncertainty covering this decision_at |
| 2013-07 | — | — | 1 | False | segment 2013-03-31→2013-09-30 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2013-08 | — | — | 1 | False | segment 2013-03-31→2013-09-30 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2013-09 | — | — | 1 | False | segment 2013-03-31→2013-09-30 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2013-10 | — | — | 1 | False | segment 2013-09-30→2014-03-31 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2013-11 | — | — | 1 | False | segment 2013-09-30→2014-03-31 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2013-12 | — | — | 1 | False | segment 2013-09-30→2014-03-31 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2014-01 | — | — | 1 | False | segment 2013-09-30→2014-03-31 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2014-02 | — | — | 1 | False | segment 2013-09-30→2014-03-31 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2014-03 | — | — | 1 | False | segment 2013-09-30→2014-03-31 | BLOCKED | 4 securities with an effective-date uncertainty covering this decision_at |
| 2014-04 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-05 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-06 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-07 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-08 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-09 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-10 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-11 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2014-12 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2015-01 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2015-02 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2015-03 | — | — | 1 | False | segment 2014-03-31→2015-03-31 | BLOCKED | 13 securities with an effective-date uncertainty covering this decision_at |
| 2015-04 | — | — | 1 | False | segment 2015-03-31→2015-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2015-05 | — | — | 1 | False | segment 2015-03-31→2015-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2015-06 | — | — | 1 | False | segment 2015-03-31→2015-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2015-07 | — | — | 1 | False | segment 2015-03-31→2015-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2015-08 | — | — | 1 | False | segment 2015-03-31→2015-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2015-09 | — | — | 1 | False | segment 2015-03-31→2015-09-30 | BLOCKED | 23 securities with an effective-date uncertainty covering this decision_at |
| 2015-10 | — | — | 1 | False | segment 2015-09-30→2016-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2015-11 | — | — | 1 | False | segment 2015-09-30→2016-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2015-12 | — | — | 1 | False | segment 2015-09-30→2016-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2016-01 | — | — | 1 | False | segment 2015-09-30→2016-03-31 | BLOCKED | 11 securities with an effective-date uncertainty covering this decision_at |
| 2016-02 | — | — | 1 | False | segment 2015-09-30→2016-03-31 | BLOCKED | 12 securities with an effective-date uncertainty covering this decision_at |
| 2016-03 | — | — | 1 | False | segment 2015-09-30→2016-03-31 | BLOCKED | 12 securities with an effective-date uncertainty covering this decision_at |
| 2016-04 | — | — | 1 | False | segment 2016-03-31→2016-09-30 | BLOCKED | 1 securities with an effective-date uncertainty covering this decision_at |
| 2016-05 | — | — | 1 | False | segment 2016-03-31→2016-09-30 | BLOCKED | 1 securities with an effective-date uncertainty covering this decision_at |
| 2016-06 | — | — | 1 | False | segment 2016-03-31→2016-09-30 | BLOCKED | 1 securities with an effective-date uncertainty covering this decision_at |
| 2016-07 | — | — | 1 | False | segment 2016-03-31→2016-09-30 | BLOCKED | 1 securities with an effective-date uncertainty covering this decision_at |
| 2016-08 | — | — | 1 | False | segment 2016-03-31→2016-09-30 | BLOCKED | 1 securities with an effective-date uncertainty covering this decision_at |
| 2016-09 | — | — | 1 | False | segment 2016-03-31→2016-09-30 | BLOCKED | 1 securities with an effective-date uncertainty covering this decision_at |
| 2016-10 | 504 | 504 | — | True | segment 2016-09-30→2017-03-31; forward==backward | READY | — |
| 2016-11 | 504 | 504 | — | True | segment 2016-09-30→2017-03-31; forward==backward | READY | — |
| 2016-12 | 504 | 504 | — | True | segment 2016-09-30→2017-03-31; forward==backward | READY | — |
| 2017-01 | 504 | 504 | — | True | segment 2016-09-30→2017-03-31; forward==backward | READY | — |
| 2017-02 | 504 | 504 | — | True | segment 2016-09-30→2017-03-31; forward==backward | READY | — |
| 2017-03 | 504 | 504 | — | True | segment 2016-09-30→2017-03-31; forward==backward | READY | — |
| 2017-04 | 504 | 504 | — | True | segment 2017-03-31→2017-09-30; forward==backward | READY | — |
| 2017-05 | 504 | 504 | — | True | segment 2017-03-31→2017-09-30; forward==backward | READY | — |
| 2017-06 | 504 | 504 | — | True | segment 2017-03-31→2017-09-30; forward==backward | READY | — |
| 2017-07 | 504 | 504 | — | True | segment 2017-03-31→2017-09-30; forward==backward | READY | — |
| 2017-08 | 504 | 504 | — | True | segment 2017-03-31→2017-09-30; forward==backward | READY | — |
| 2017-09 | 504 | 504 | — | True | segment 2017-03-31→2017-09-30; forward==backward | READY | — |
| 2017-10 | 504 | 504 | — | True | segment 2017-09-30→2018-03-31; forward==backward | READY | — |
| 2017-11 | 504 | 504 | — | True | segment 2017-09-30→2018-03-31; forward==backward | READY | — |
| 2017-12 | 504 | 504 | — | True | segment 2017-09-30→2018-03-31; forward==backward | READY | — |
| 2018-01 | 504 | 504 | — | True | segment 2017-09-30→2018-03-31; forward==backward | READY | — |
| 2018-02 | 504 | 504 | — | True | segment 2017-09-30→2018-03-31; forward==backward | READY | — |
| 2018-03 | 504 | 504 | — | True | segment 2017-09-30→2018-03-31; forward==backward | READY | — |
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

## Cobertura de securities frente al requisito de 100

| métrica | valor |
|---|---|
| required | 100 |
| configured_tickers | 100 |
| with_prices | 100 |
| with_snapshots | 100 |
| identity_ready | 51 |
| configured_labels_unmatched | ['CABK', 'NTGY', 'ROG', 'SAN'] |
| usable_strict | 51 |
| usable_preview | 51 |
| us_configured_with_snapshots | 55 |
| non_us_configured_with_snapshots | 45 |
| global_eligible_under_current_contract | 51 |
| distinct_issuer_ids_with_eligible_rows | 51 |
| scope | US_ONLY: XNYS membership + SPY comparable benchmark; non-US excluded by current eligibility contract |
| iid_effective_sample_size | — |
| ess_reason | Overlapping 12M targets and shared market regimes; counts do not establish statistical independence. |

| mes DEV | securities elegibles PRICE 12M |
|---|---|
| 2011-01 | 0 |
| 2011-02 | 0 |
| 2011-03 | 0 |
| 2011-04 | 0 |
| 2011-05 | 0 |
| 2011-06 | 0 |
| 2011-07 | 0 |
| 2011-08 | 0 |
| 2011-09 | 0 |
| 2011-10 | 0 |
| 2011-11 | 0 |
| 2011-12 | 0 |
| 2012-01 | 0 |
| 2012-02 | 0 |
| 2012-03 | 0 |
| 2012-04 | 0 |
| 2012-05 | 0 |
| 2012-06 | 0 |
| 2012-07 | 0 |
| 2012-08 | 0 |
| 2012-09 | 0 |
| 2012-10 | 0 |
| 2012-11 | 0 |
| 2012-12 | 0 |
| 2013-01 | 0 |
| 2013-02 | 0 |
| 2013-03 | 0 |
| 2013-04 | 0 |
| 2013-05 | 0 |
| 2013-06 | 0 |
| 2013-07 | 0 |
| 2013-08 | 0 |
| 2013-09 | 0 |
| 2013-10 | 0 |
| 2013-11 | 0 |
| 2013-12 | 0 |
| 2014-01 | 0 |
| 2014-02 | 0 |
| 2014-03 | 0 |
| 2014-04 | 0 |
| 2014-05 | 0 |
| 2014-06 | 0 |
| 2014-07 | 0 |
| 2014-08 | 0 |
| 2014-09 | 0 |
| 2014-10 | 0 |
| 2014-11 | 0 |
| 2014-12 | 0 |
| 2015-01 | 0 |
| 2015-02 | 0 |
| 2015-03 | 0 |
| 2015-04 | 0 |
| 2015-05 | 0 |
| 2015-06 | 0 |
| 2015-07 | 0 |
| 2015-08 | 0 |
| 2015-09 | 0 |
| 2015-10 | 0 |
| 2015-11 | 0 |
| 2015-12 | 0 |
| 2016-01 | 0 |
| 2016-02 | 0 |
| 2016-03 | 0 |
| 2016-04 | 0 |
| 2016-05 | 0 |
| 2016-06 | 0 |
| 2016-07 | 0 |
| 2016-08 | 0 |
| 2016-09 | 0 |
| 2016-10 | 49 |
| 2016-11 | 49 |
| 2016-12 | 49 |
| 2017-01 | 49 |
| 2017-02 | 49 |
| 2017-03 | 49 |
| 2017-04 | 49 |
| 2017-05 | 49 |
| 2017-06 | 49 |
| 2017-07 | 49 |
| 2017-08 | 49 |
| 2017-09 | 49 |
| 2017-10 | 49 |
| 2017-11 | 49 |
| 2017-12 | 49 |
| 2018-01 | 49 |
| 2018-02 | 49 |
| 2018-03 | 49 |
| 2018-04 | 49 |
| 2018-05 | 49 |
| 2018-06 | 49 |
| 2018-07 | 49 |
| 2018-08 | 49 |
| 2018-09 | 49 |
| 2018-10 | 49 |
| 2018-11 | 50 |
| 2018-12 | 50 |
| 2019-01 | 50 |
| 2019-02 | 50 |
| 2019-03 | 50 |
| 2019-04 | 50 |
| 2019-05 | 50 |
| 2019-06 | 50 |
| 2019-07 | 50 |
| 2019-08 | 50 |
| 2019-09 | 50 |
| 2019-10 | 50 |
| 2019-11 | 50 |
| 2019-12 | 50 |
| 2020-01 | 50 |
| 2020-02 | 50 |
| 2020-03 | 50 |
| 2020-04 | 50 |
| 2020-05 | 50 |
| 2020-06 | 50 |
| 2020-07 | 50 |
| 2020-08 | 50 |
| 2020-09 | 50 |
| 2020-10 | 50 |
| 2020-11 | 50 |
| 2020-12 | 50 |
| 2021-01 | 51 |
| 2021-02 | 51 |
| 2021-03 | 51 |
| 2021-04 | 51 |
| 2021-05 | 51 |
| 2021-06 | 51 |
| 2021-07 | 51 |
| 2021-08 | 51 |
| 2021-09 | 51 |
| 2021-10 | 0 |
| 2021-11 | 0 |
| 2021-12 | 0 |
| 2022-01 | 0 |
| 2022-02 | 0 |
| 2022-03 | 0 |
| 2022-04 | 0 |
| 2022-05 | 0 |
| 2022-06 | 0 |
| 2022-07 | 0 |
| 2022-08 | 0 |
| 2022-09 | 0 |

| security | meses elegibles PRICE 12M |
|---|---|
| AAPL | 60 |
| ABBV | 60 |
| ABT | 60 |
| ACN | 60 |
| ADBE | 60 |
| AMGN | 60 |
| AMZN | 60 |
| AVGO | 60 |
| BA | 60 |
| BAC | 60 |
| CAT | 60 |
| COST | 60 |
| CRM | 60 |
| CSCO | 60 |
| CVX | 60 |
| DIS | 60 |
| HD | 60 |
| HON | 60 |
| IBM | 60 |
| INTU | 60 |
| JNJ | 60 |
| JPM | 60 |
| KO | 60 |
| LIN | 35 |
| LLY | 60 |
| LMT | 60 |
| LOW | 60 |
| MA | 60 |
| MCD | 60 |
| META | 60 |
| MRK | 60 |
| MSFT | 60 |
| NEE | 60 |
| NFLX | 60 |
| NVDA | 60 |
| ORCL | 60 |
| PEP | 60 |
| PFE | 60 |
| PG | 60 |
| QCOM | 60 |
| SPGI | 60 |
| TMO | 60 |
| TSLA | 9 |
| TXN | 60 |
| UNH | 60 |
| UNP | 60 |
| UPS | 60 |
| V | 60 |
| VZ | 60 |
| WFC | 60 |
| WMT | 60 |

| security_id | ticker_at_T | issuer_id | market | first_date | last_date | identity_status | price_status | fundamental_status | reason_not_usable |
|---|---|---|---|---|---|---|---|---|---|
| d224cb0b | MSFT | 64c69676 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| cd8b8a8f | AAPL | e28c1501 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 4d1aedb4 | CTG | 45358a3c | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| c078ea25 | IBE | ceb549c8 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 35c77f24 | REP | b050f4a2 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 95b1b253 | TEF | 0c10afe8 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| aa330b59 | ACS | 21cb4f9e | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 04499b95 | SCH | 97df9b36 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 9eb07b86 | BBVA | 79fccbec | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 10fc3d3d | ITX | 9b86e623 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| ce79cc0a | ENG | ee1e5d70 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 52322e74 | CRI | b915f41b | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 61f8190e | AMS | 265c8a37 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 23206ded | ELE |  | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 2c882a14 | FER | 26daf587 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 1fecea5c | KO | aa2f4d8a | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| c24e70f1 | VTI |  | XNYS | None | None | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | NONE | BENCHMARK_SERIES (not a research security) |
| 27615e6f | JNJ | ad4de1d1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| b8dddadd | JPM | 361c0e7e | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | UNSUPPORTED_SECTOR | — |
| 67cab159 | XOM | d225df5a | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 140de420 | PG | 658db81b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 3e44c4d0 | AMZN | 2936853c | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 6e75fc3b | GOOGL | e1d78079 | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 6e6e9ba4 | NVDA | 61c3be3f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| b13f6397 | META | 22876d90 | XNYS | 2012-05-18 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| dccdb7a3 | V | b66cccb6 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 7eba0f34 | UNH | 81bd0de3 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | UNSUPPORTED_SECTOR | — |
| 85875435 | LLY | 29348354 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 60e8375b | AVGO | 808dd69f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | — |
| a39a3cf8 | TSLA | 43b4af2b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 7f98b411 | MA | 1b8f5b0b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 56b48939 | COST | 9eb7b399 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| f32474b2 | HD | d58f8c52 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 1dc79d7e | WMT | 3e4073c5 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| b8194184 | ABBV | dc457a14 | XNYS | 2013-01-02 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 8f5dd8bc | MRK | b60da8da | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 71598032 | CVX | e305a204 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| eb3c38c1 | BAC | d0a61d20 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | UNSUPPORTED_SECTOR | — |
| 66217c41 | ORCL | b444fd32 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 18bcc934 | CRM | 19e51e57 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 631cae7f | NFLX | 0dcb90eb | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 52e8fe35 | ADBE | 82d133a7 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 9abd13cb | CSCO | 307a428c | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| a358721b | PEP | e2c4212f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 6eb3dc49 | TMO | 93c70d73 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| e8c5c52f | ACN | 5155d771 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 50b87e9d | MCD | 5f8f8e10 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| eaf31854 | ABT | ea9d8dd9 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| f0efb37f | LIN | 51d6d72d | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | — |
| 1efeccbc | DIS | 46c5da7d | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | — |
| 485fa49d | WFC | e7f3242f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | UNSUPPORTED_SECTOR | — |
| 257b7380 | CAT | bbacfef6 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 4b7851e2 | IBM | e07fdae0 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 9a8fc57b | GE | 3abd4af0 | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 555f0c85 | QCOM | ea8c8ed1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 0d560a31 | TXN | f8fc0393 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 64352eea | AMGN | d8da7795 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 1ea23764 | INTU | 130bb611 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| c2642c7d | VZ | 7103e001 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| f597e07d | PFE | 4294108a | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 2d773a5d | BA | 74a5c72d | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 9983b4aa | HON | c7f542ea | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 93b9ac92 | UNP | ca510d2e | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| fbca5260 | LOW | 4bebe7e1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| aed9f0f2 | SPGI | 9d3bc125 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 5ca6f391 | NEE | 04afd841 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| ee89281c | RTX | 53b6d813 | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| b36ce627 | LMT | afd7ffb3 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 16d3f78c | UPS | 69a34f0b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| beffff95 | ASML |  | XAMS | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 28c786a4 | NESN |  | XSWX | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| c48e7d66 | NOVN |  | XSWX | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 48a569ee | SAP |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 5bc7a3d3 | SIE |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 238704f0 | ALV |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| afb82f95 | AIR |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 42cd8596 | MC |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 6544caf0 | OR |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| cae3f007 | SU |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 5186a8c6 | TTE |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| d6164473 | AZN |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 4b803cf8 | SHEL |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 1d23d05c | HSBA |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 359f0e99 | ULVR |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| b0ffe77c | BP |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| fecf17d4 | GSK |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 928c725f | NOVO-B |  | XCSE | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 7c4b1b9d | ENEL |  | XMIL | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 17fedeb6 | ISP |  | XMIL | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| d3376494 | BHP |  | XASX | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 06c32c6f | CBA |  | XASX | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 82414aa2 | CSL |  | XASX | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 2e35be8c | RY |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 6227956b | TD |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 576169af | SHOP |  | XTSE | 2015-05-21 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| fe9d3e5c | ENB |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 5cec853a | 7203 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 7e6c5b98 | 6758 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| e3230ff5 | 9984 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 4ba66cf7 | 8306 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 3137e1cf | 7974 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; OOT; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| cb5de976 | SPY |  | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | NONE | BENCHMARK_SERIES (not a research security) |
| 0c0022b8 | URTH |  | XNYS | 2012-01-12 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | NONE | BENCHMARK_SERIES (not a research security) |
| 3ba7c569 | ^IBEX |  | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NONE | BENCHMARK_SERIES (not a research security) |

## Fundamentales: securities con ≥36 meses PIT utilizables

40 de los que tienen snapshots (requeridos 30).

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
| MSFT | 131 | 2011-08-01 | 2022-09-01 | 140 |
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
| AAPL | 110 | 2013-08-01 | 2022-09-01 | 140 |
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
| ENG | 0 | — | — | 140 |
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
| raw snapshots | 15208 |
| − HOLDOUT | 1200 |
| − OOT | 1300 |
| − UNIVERSE_NOT_CANONICAL | 9408 |
| − NOT_INDEX_MEMBER_AT_T | 76 |
| − SECURITY_IDENTITY_NOT_READY | 240 |
| = eligible | 2984 |
| securities con filas elegibles | 51 |

### strict_FUNDAMENTALS

| etapa | filas |
|---|---|
| raw snapshots | 15208 |
| − HOLDOUT | 1200 |
| − OOT | 1300 |
| − UNIVERSE_NOT_CANONICAL | 9408 |
| − NOT_INDEX_MEMBER_AT_T | 76 |
| − SECURITY_IDENTITY_NOT_READY | 240 |
| − FUNDAMENTALS_NOT_READY | 575 |
| − UNSUPPORTED_SECTOR | 240 |
| = eligible | 2169 |
| securities con filas elegibles | 43 |

### preview_if_D05_accepted_PRICE

| etapa | filas |
|---|---|
| raw snapshots | 15208 |
| − HOLDOUT | 1200 |
| − OOT | 1300 |
| − UNIVERSE_NOT_CANONICAL | 9408 |
| − NOT_INDEX_MEMBER_AT_T | 76 |
| − SECURITY_IDENTITY_NOT_READY | 240 |
| = eligible | 2984 |
| securities con filas elegibles | 51 |

### preview_if_D05_accepted_FUNDAMENTALS

| etapa | filas |
|---|---|
| raw snapshots | 15208 |
| − HOLDOUT | 1200 |
| − OOT | 1300 |
| − UNIVERSE_NOT_CANONICAL | 9408 |
| − NOT_INDEX_MEMBER_AT_T | 76 |
| − SECURITY_IDENTITY_NOT_READY | 240 |
| − FUNDAMENTALS_NOT_READY | 575 |
| − UNSUPPORTED_SECTOR | 240 |
| = eligible | 2169 |
| securities con filas elegibles | 43 |

## Benchmarks por mercado (12M)

| market | region | security_ccy | benchmark | bench_ccy | return_type | currency_basis | quality | comparables/filas | bloqueo |
|---|---|---|---|---|---|---|---|---|---|
| XNYS | US | USD | SPY_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 7000/7000 | — |

## Blockers restantes y mínima acción correcta

| gate | estado | actual | bloqueo técnico |
|---|---|---|---|
| D02_MONTHLY_RESEARCH_READY | BLOCKED | 72/141 READY; required history 60/85; target calendar folds 3, label-safe 0 | 25 required membership months blocked; 0 LABEL_SAFE folds; need 3. Coverage not evaluated and does not decide D02. |
| US_SECURITY_IDENTITY_READY | PARTIAL | 40 weak identity securities; 0 unresolved anchor lines | unresolved identity evidence; see D02 graph metrics |
| RESEARCH_SECURITY_COVERAGE_READY | BLOCKED | 51 usable (strict); 51 if D05 were accepted; 100 with snapshots | fewer than 100 securities satisfy all PIT eligibility conditions; see the per-security audit |
| RESEARCH_DATA_READY | BLOCKED | derived | at least one data gate is not READY |
| FIRST_ML_BASELINE_READY | BLOCKED | false | required gates not READY: D02_MONTHLY_RESEARCH_READY, US_SECURITY_IDENTITY_READY, RESEARCH_SECURITY_COVERAGE_READY, RESEARCH_DATA_READY |

PPoG→PPG está aprobado y aplicado como alias documental. La extensión SEC se ha ejecutado con contacto runtime; discrepancias documentales permanecen bloqueadas.
