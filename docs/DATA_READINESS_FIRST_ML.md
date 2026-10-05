# DATA READINESS FOR FIRST ML (generado desde la base)

Generado 2026-10-05T20:55:01Z · experimento preparado `FIRST_EQUITY_ML_12M_V0` (NO ejecutado). Fuente de datos de mercado y FX: **Yahoo Finance** (decisión del propietario; VENDOR, `CANONICAL_PROVIDER_FOR_PITQUANT`). Contrato US: `FIRST_ML_COVERAGE_V1`. El `required_securities = 100` global se conserva solo como diagnóstico legacy y no decide First US ML.

## Matriz de gates

| Gate | Required | Actual | Status | Blocking reason |
|---|---|---|---|---|
| D02_MEMBERSHIP_VALIDITY | Every included security-period OFFICIAL_DIRECT or CORROBORATED_HISTORICAL; nonempty supported months | 85/85 temporally valid months | READY | — |
| D02_MONTHLY_RESEARCH_READY | 85 READY months positioned 2014-09..2021-09; >= 3 LABEL_SAFE folds; statistical coverage separate | 97/141 READY; required history 85/85; target calendar folds 3, label-safe 3 | READY | — |
| US_SECURITY_IDENTITY_READY | 0 weak identity members, 0 unresolved lines | 40 weak identity securities; 0 unresolved anchor lines | PARTIAL | unresolved identity evidence; see D02 graph metrics |
| D05_READY | accepted prices + corporate actions + adjustment method + provenance | Yahoo Finance (CANONICAL_PROVIDER_FOR_PITQUANT, VENDOR) | READY | — |
| BENCHMARK_RETURN_BASIS_READY | first ML US scope: comparable return + currency basis, accepted provenance | US rows comparable 7000/7000; non-US via USD conversion (PROXY) | READY | — |
| FIRST_ML_IDENTITY_VALIDITY_READY | Every included row has verified issuer/security/membership identity | True | READY | — |
| RESEARCH_SECURITY_COVERAGE_READY | FIRST_ML_COVERAGE_V1 | {'passing_folds': 0, 'required_folds': 3} | BLOCKED | See FIRST_ML_COVERAGE_AUDIT.json: exact family/month deficits or class degeneracy |
| US_FUNDAMENTALS_READY | >= 30 securities with >= 36 usable PIT months | 40 securities | READY | — |
| HOLDOUT_SEALED | 0 research rows inside 2022-10-01..2025-09-30 | 0 snapshots inside the holdout | READY | — |
| RESEARCH_DATA_READY | all data gates READY | derived | BLOCKED | at least one data gate is not READY |
| FIRST_ML_BASELINE_READY | all required gates READY | false | BLOCKED | required gates not READY: RESEARCH_SECURITY_COVERAGE_READY, RESEARCH_DATA_READY |

`FIRST_ML_BASELINE_READY = false` (calcularlo no entrena nada).

La matriz corresponde al primer ML. Los `flags` del JSON describen el Research Lab histórico y su disponibilidad para recopilar features; no autorizan entrenamiento ni sustituyen estos gates.

## D02: validez y completitud (ADR-0056)

Todas las filas incluidas requieren OFFICIAL_DIRECT o CORROBORATED_HISTORICAL. UNVERIFIED/CONFLICTED se excluyen por security y fecha. La reconstrucción estricta se conserva. La completitud no decide suficiencia estadística. Yahoo sigue siendo proveedor de mercado, nunca autoridad de membership.

Ledger versionado `d02-membership-evidence-v1`, hash `823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52`; provenance y exclusiones en D02_MEMBERSHIP_ELIGIBILITY.json.

| Month | Configured | Resolved | Eligible securities | Eligible issuers | UNVERIFIED | CONFLICTED | Verified nonmember | Included rows | Lost rows | Coverage % |
|---|---|---|---|---|---|---|---|---|---|---|
| 2014-09 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2014-10 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2014-11 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2014-12 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-01 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-02 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-03 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-04 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-05 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-06 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-07 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-08 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-09 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-10 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-11 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2015-12 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2016-01 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2016-02 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2016-03 | 55 | 49 | 47 | 47 | 6 | 0 | 2 | 47 | 8 | 85.450 |
| 2016-04 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-05 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-06 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-07 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-08 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-09 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-10 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-11 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2016-12 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-01 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-02 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-03 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-04 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-05 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-06 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-07 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-08 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-09 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-10 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-11 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2017-12 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-01 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-02 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-03 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-04 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-05 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-06 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-07 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-08 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-09 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-10 | 55 | 50 | 48 | 48 | 5 | 0 | 2 | 48 | 7 | 87.270 |
| 2018-11 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2018-12 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-01 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-02 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-03 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-04 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-05 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-06 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-07 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-08 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-09 | 55 | 49 | 48 | 48 | 6 | 0 | 1 | 48 | 7 | 87.270 |
| 2019-10 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2019-11 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2019-12 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-01 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-02 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-03 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-04 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-05 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-06 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-07 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-08 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-09 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-10 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-11 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2020-12 | 55 | 50 | 49 | 49 | 5 | 0 | 1 | 49 | 6 | 89.090 |
| 2021-01 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-02 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-03 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-04 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-05 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-06 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-07 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-08 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |
| 2021-09 | 55 | 50 | 50 | 50 | 5 | 0 | 0 | 50 | 5 | 90.910 |

La selección usa exclusivamente evidencia histórica e identidad; no retornos ni scores. Sectores/issuers afectados y pérdidas por evidencia separadas de ausencias verificadas: D02_MEMBERSHIP_COMPLETENESS.json. El subconjunto configurado conserva su limitación de supervivencia.

## Folds factibles

| fold | train start | train end | test start | test end | train months | purge | embargo |
|---|---|---|---|---|---|---|---|
| 0 | 2014-09 | 2017-09 | 2018-10 | 2019-09 | 37 | 12 | 1 |
| 1 | 2014-09 | 2018-09 | 2019-10 | 2020-09 | 49 | 12 | 1 |
| 2 | 2014-09 | 2019-09 | 2020-10 | 2021-09 | 61 | 12 | 1 |

## D02 mensual

CALENDAR_FOLD = structural dates; LABEL_SAFE_FOLD = valid included membership history with explicit security-period exclusions and TRAIN labels available at fit, plus twelve valid TEST outcome months; ML_ELIGIBLE_FOLD adds FIRST_ML_COVERAGE_V1 structural issuer/month coverage, common cohorts and non-degenerate labels. See FIRST_ML_COVERAGE.md. Label safety is unchanged. TRAIN cutoff = first TEST decision; TEST cutoff = audit time. See ADR-0055 V2 and ADR-0056.

| fold | calendar TEST rows | mature targets | benchmark ready | price ready | eligible | holdout excluded | TEST label safe | full fold label safe |
|---|---|---|---|---|---|---|---|---|
| 0 | 660 | 660 | 660 | 660 | 576 | 0 | True | True |
| 1 | 660 | 660 | 660 | 660 | 588 | 0 | True | True |
| 2 | 660 | 660 | 660 | 660 | 597 | 0 | True | True |

Every TRAIN/TEST row's target_start, target_end, actual_exit_session, target_mature_at, availability cutoff and exclusion reasons are recorded in `FIRST_ML_FOLD_AUDIT.json`.

Derived requirement: 2014-09..2021-09, 85 continuous READY months. Last admissible decision 2021-09-01T13:30:00+00:00; target end 2022-09-01T13:30:00+00:00; expected earliest maturity 2022-08-31T21:00:00+00:00. No outcomes read for this derivation.

| métrica | valor |
|---|---|
| total_months | 141 |
| ready_months | 97 |
| membership_ready_months | 72 |
| partial_months | 0 |
| blocked_months | 44 |
| no_anchor_months | 0 |
| coverage_pct | 68.800 |
| longest_run | 97 |
| longest_membership_run | 72 |
| feasible_folds | 4 |
| reason_if_no_folds | — |
| required_continuous_months | 85 |
| weak_identity_securities | 40 |
| required_history_start | 2014-09 |
| required_history_end | 2021-09 |
| required_months_ready | 85 |
| required_months_blocked | 0 |
| longest_relevant_run | 85 |
| validity_scope | Included US research observations in required history; explicitly excluded periods are not unresolved months |
| strict_ready_months_unchanged | 72 |
| strict_membership_cards_not_closed_by_exclusion | True |
| calendar_folds | 3 |
| label_safe_folds | 3 |
| test_label_safe_folds | 3 |
| coverage_gate_evaluated | True |

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
| 2014-09 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2014-10 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2014-11 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2014-12 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-01 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-02 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-03 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-04 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-05 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-06 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-07 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-08 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-09 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-10 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-11 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2015-12 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-01 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-02 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-03 | — | 47 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-04 | — | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-05 | — | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-06 | — | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-07 | — | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-08 | — | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-09 | — | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-10 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-11 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2016-12 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-01 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-02 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-03 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-04 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-05 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-06 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-07 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-08 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-09 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-10 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-11 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2017-12 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-01 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-02 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-03 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-04 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-05 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-06 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-07 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-08 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-09 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-10 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-11 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2018-12 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-01 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-02 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-03 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-04 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-05 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-06 | 505 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-07 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-08 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-09 | 504 | 48 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-10 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-11 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2019-12 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-01 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-02 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-03 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-04 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-05 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-06 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-07 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-08 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-09 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-10 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-11 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2020-12 | 505 | 49 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-01 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-02 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-03 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-04 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-05 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-06 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-07 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-08 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
| 2021-09 | 505 | 50 | — | True | d02-membership-evidence-v1; explicit security-period exclusions; 823731663559c2d902b0bd877035015cf0b826324e476c38b53d031ff7b1ab52 | READY | — |
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

## Cobertura US por fold y familia

Contrato FIRST_ML_COVERAGE_V1: PRICE >=40 emisores y >=80% de membresía válida; FUNDAMENTALS/COMBINED >=30 y >=70% de PRICE. TRAIN >=90% meses; TEST 12/12. Cohorte común TRAIN y TEST para M0–M4. Ver [FIRST_ML_COVERAGE.md](FIRST_ML_COVERAGE.md) y FIRST_ML_COVERAGE_AUDIT.json: déficits exactos, labels DEV, concentración, dependencia y hashes.

## Diagnóstico legacy global de securities (100; no gate de First US ML)

| métrica | valor |
|---|---|
| required | 100 |
| configured_tickers | 100 |
| with_prices | 100 |
| with_snapshots | 100 |
| identity_ready | 51 |
| configured_labels_unmatched | ['CABK', 'NTGY', 'ROG', 'SAN'] |
| usable_strict | 50 |
| usable_preview | 50 |
| us_configured_with_snapshots | 55 |
| non_us_configured_with_snapshots | 45 |
| global_eligible_under_current_contract | 50 |
| distinct_issuer_ids_with_eligible_rows | 50 |
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
| 2014-09 | 47 |
| 2014-10 | 47 |
| 2014-11 | 47 |
| 2014-12 | 47 |
| 2015-01 | 47 |
| 2015-02 | 47 |
| 2015-03 | 47 |
| 2015-04 | 47 |
| 2015-05 | 47 |
| 2015-06 | 47 |
| 2015-07 | 47 |
| 2015-08 | 47 |
| 2015-09 | 47 |
| 2015-10 | 47 |
| 2015-11 | 47 |
| 2015-12 | 47 |
| 2016-01 | 47 |
| 2016-02 | 47 |
| 2016-03 | 47 |
| 2016-04 | 48 |
| 2016-05 | 48 |
| 2016-06 | 48 |
| 2016-07 | 48 |
| 2016-08 | 48 |
| 2016-09 | 48 |
| 2016-10 | 48 |
| 2016-11 | 48 |
| 2016-12 | 48 |
| 2017-01 | 48 |
| 2017-02 | 48 |
| 2017-03 | 48 |
| 2017-04 | 48 |
| 2017-05 | 48 |
| 2017-06 | 48 |
| 2017-07 | 48 |
| 2017-08 | 48 |
| 2017-09 | 48 |
| 2017-10 | 48 |
| 2017-11 | 48 |
| 2017-12 | 48 |
| 2018-01 | 48 |
| 2018-02 | 48 |
| 2018-03 | 48 |
| 2018-04 | 48 |
| 2018-05 | 48 |
| 2018-06 | 48 |
| 2018-07 | 48 |
| 2018-08 | 48 |
| 2018-09 | 48 |
| 2018-10 | 48 |
| 2018-11 | 48 |
| 2018-12 | 48 |
| 2019-01 | 48 |
| 2019-02 | 48 |
| 2019-03 | 48 |
| 2019-04 | 48 |
| 2019-05 | 48 |
| 2019-06 | 48 |
| 2019-07 | 48 |
| 2019-08 | 48 |
| 2019-09 | 48 |
| 2019-10 | 49 |
| 2019-11 | 49 |
| 2019-12 | 49 |
| 2020-01 | 49 |
| 2020-02 | 49 |
| 2020-03 | 49 |
| 2020-04 | 49 |
| 2020-05 | 49 |
| 2020-06 | 49 |
| 2020-07 | 49 |
| 2020-08 | 49 |
| 2020-09 | 49 |
| 2020-10 | 49 |
| 2020-11 | 49 |
| 2020-12 | 49 |
| 2021-01 | 50 |
| 2021-02 | 50 |
| 2021-03 | 50 |
| 2021-04 | 50 |
| 2021-05 | 50 |
| 2021-06 | 50 |
| 2021-07 | 50 |
| 2021-08 | 50 |
| 2021-09 | 50 |
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
| AAPL | 85 |
| ABBV | 85 |
| ABT | 85 |
| ACN | 85 |
| ADBE | 85 |
| AMGN | 85 |
| AMZN | 85 |
| AVGO | 66 |
| BA | 85 |
| BAC | 85 |
| CAT | 85 |
| COST | 85 |
| CRM | 85 |
| CSCO | 85 |
| CVX | 85 |
| DIS | 85 |
| HD | 85 |
| HON | 85 |
| IBM | 85 |
| INTU | 85 |
| JNJ | 85 |
| JPM | 85 |
| KO | 85 |
| LIN | 24 |
| LLY | 85 |
| LMT | 85 |
| LOW | 85 |
| MA | 85 |
| MCD | 85 |
| MRK | 85 |
| MSFT | 85 |
| NEE | 85 |
| NFLX | 85 |
| NVDA | 85 |
| ORCL | 85 |
| PEP | 85 |
| PFE | 85 |
| PG | 85 |
| QCOM | 85 |
| SPGI | 85 |
| TMO | 85 |
| TSLA | 9 |
| TXN | 85 |
| UNH | 85 |
| UNP | 85 |
| UPS | 85 |
| V | 85 |
| VZ | 85 |
| WFC | 85 |
| WMT | 85 |

| security_id | ticker_at_T | issuer_id | market | first_date | last_date | identity_status | price_status | fundamental_status | reason_not_usable |
|---|---|---|---|---|---|---|---|---|---|
| d224cb0b | MSFT | 64c69676 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| cd8b8a8f | AAPL | e28c1501 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 4d1aedb4 | CTG | 45358a3c | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| c078ea25 | IBE | ceb549c8 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 35c77f24 | REP | b050f4a2 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 95b1b253 | TEF | 0c10afe8 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| aa330b59 | ACS | 21cb4f9e | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 04499b95 | SCH | 97df9b36 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 9eb07b86 | BBVA | 79fccbec | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 10fc3d3d | ITX | 9b86e623 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| ce79cc0a | ENG | ee1e5d70 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 52322e74 | CRI | b915f41b | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 61f8190e | AMS | 265c8a37 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 23206ded | ELE |  | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 2c882a14 | FER | 26daf587 | XMAD | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 1fecea5c | KO | aa2f4d8a | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| c24e70f1 | VTI |  | XNYS | None | None | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | NONE | BENCHMARK_SERIES (not a research security) |
| 27615e6f | JNJ | ad4de1d1 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| b8dddadd | JPM | 361c0e7e | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | UNSUPPORTED_SECTOR | — |
| 67cab159 | XOM | d225df5a | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | INSUFFICIENT_HISTORY | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 140de420 | PG | 658db81b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 3e44c4d0 | AMZN | 2936853c | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 6e75fc3b | GOOGL | e1d78079 | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 6e6e9ba4 | NVDA | 61c3be3f | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| b13f6397 | META | 22876d90 | XNYS | 2012-05-18 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; NOT_INDEX_MEMBER_AT_T; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
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
| 9a8fc57b | GE | 3abd4af0 | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
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
| ee89281c | RTX | 53b6d813 | XNYS | 2011-01-03 | 2026-10-02 | UNRESOLVED_SECURITY_LINK | YAHOO_CANONICAL (per-series QA required) | OK | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| b36ce627 | LMT | afd7ffb3 | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| 16d3f78c | UPS | 69a34f0b | XNYS | 2011-01-03 | 2026-10-02 | RESOLVED | YAHOO_CANONICAL (per-series QA required) | OK | — |
| beffff95 | ASML |  | XAMS | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 28c786a4 | NESN |  | XSWX | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| c48e7d66 | NOVN |  | XSWX | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 48a569ee | SAP |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 5bc7a3d3 | SIE |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 238704f0 | ALV |  | XETR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| afb82f95 | AIR |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 42cd8596 | MC |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 6544caf0 | OR |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| cae3f007 | SU |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 5186a8c6 | TTE |  | XPAR | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| d6164473 | AZN |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 4b803cf8 | SHEL |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 1d23d05c | HSBA |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 359f0e99 | ULVR |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| b0ffe77c | BP |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| fecf17d4 | GSK |  | XLON | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 928c725f | NOVO-B |  | XCSE | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 7c4b1b9d | ENEL |  | XMIL | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 17fedeb6 | ISP |  | XMIL | 2011-01-03 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| d3376494 | BHP |  | XASX | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 06c32c6f | CBA |  | XASX | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 82414aa2 | CSL |  | XASX | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 2e35be8c | RY |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 6227956b | TD |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 576169af | SHOP |  | XTSE | 2015-05-21 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| fe9d3e5c | ENB |  | XTSE | 2011-01-04 | 2026-10-02 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 5cec853a | 7203 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 7e6c5b98 | 6758 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| e3230ff5 | 9984 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 4ba66cf7 | 8306 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
| 3137e1cf | 7974 |  | XTKS | 2011-01-04 | 2026-10-05 | NOT_ASSESSED_NON_US | YAHOO_CANONICAL (per-series QA required) | NOT_REGISTERED | BENCHMARK_NOT_READY; HOLDOUT; INSUFFICIENT_HISTORY; MEMBERSHIP_UNVERIFIED; PRICE_DATA_NOT_READY; SECURITY_IDENTITY_NOT_READY; TARGET_IMMATURE; UNIVERSE_NOT_CANONICAL |
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
| META | 0 | — | — | 124 |
| SHOP | 0 | — | — | 88 |

## Embudo de filas (12M)

### strict_PRICE

| etapa | filas |
|---|---|
| raw snapshots | 13908 |
| − HOLDOUT | 1200 |
| − UNIVERSE_NOT_CANONICAL | 8033 |
| − NOT_INDEX_MEMBER_AT_T | 241 |
| − MEMBERSHIP_UNVERIFIED | 340 |
| = eligible | 4094 |
| securities con filas elegibles | 50 |

### strict_FUNDAMENTALS

| etapa | filas |
|---|---|
| raw snapshots | 13908 |
| − HOLDOUT | 1200 |
| − UNIVERSE_NOT_CANONICAL | 8033 |
| − NOT_INDEX_MEMBER_AT_T | 241 |
| − MEMBERSHIP_UNVERIFIED | 340 |
| − FUNDAMENTALS_NOT_READY | 818 |
| − UNSUPPORTED_SECTOR | 340 |
| = eligible | 2936 |
| securities con filas elegibles | 43 |

### preview_if_D05_accepted_PRICE

| etapa | filas |
|---|---|
| raw snapshots | 13908 |
| − HOLDOUT | 1200 |
| − UNIVERSE_NOT_CANONICAL | 8033 |
| − NOT_INDEX_MEMBER_AT_T | 241 |
| − MEMBERSHIP_UNVERIFIED | 340 |
| = eligible | 4094 |
| securities con filas elegibles | 50 |

### preview_if_D05_accepted_FUNDAMENTALS

| etapa | filas |
|---|---|
| raw snapshots | 13908 |
| − HOLDOUT | 1200 |
| − UNIVERSE_NOT_CANONICAL | 8033 |
| − NOT_INDEX_MEMBER_AT_T | 241 |
| − MEMBERSHIP_UNVERIFIED | 340 |
| − FUNDAMENTALS_NOT_READY | 818 |
| − UNSUPPORTED_SECTOR | 340 |
| = eligible | 2936 |
| securities con filas elegibles | 43 |

## Benchmarks por mercado (12M)

| market | region | security_ccy | benchmark | bench_ccy | return_type | currency_basis | quality | comparables/filas | bloqueo |
|---|---|---|---|---|---|---|---|---|---|
| XNYS | US | USD | SPY_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 7000/7000 | — |

## Blockers restantes y mínima acción correcta

| gate | estado | actual | bloqueo técnico |
|---|---|---|---|
| US_SECURITY_IDENTITY_READY | PARTIAL | 40 weak identity securities; 0 unresolved anchor lines | unresolved identity evidence; see D02 graph metrics |
| RESEARCH_SECURITY_COVERAGE_READY | BLOCKED | {'passing_folds': 0, 'required_folds': 3} | See FIRST_ML_COVERAGE_AUDIT.json: exact family/month deficits or class degeneracy |
| RESEARCH_DATA_READY | BLOCKED | derived | at least one data gate is not READY |
| FIRST_ML_BASELINE_READY | BLOCKED | false | required gates not READY: RESEARCH_SECURITY_COVERAGE_READY, RESEARCH_DATA_READY |

PPoG→PPG está aprobado y aplicado como alias documental. La extensión SEC se ha ejecutado con contacto runtime; discrepancias documentales permanecen bloqueadas.
