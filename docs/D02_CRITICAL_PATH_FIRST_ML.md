# D02 — label-safe critical path V2

**BLOCKED.** 25 required months remain unresolved; first blocker **2016-09**. Global READY remains 72/141 (72-month run), but only 60/85 of the correctly positioned history is READY. No model trained.

## Reproducible temporal derivation

| Parameter | Derived value |
|---|---|
| last_admissible_decision_month | 2021-09 |
| last_decision_at | 2021-09-01T13:30:00+00:00 |
| target_start | 2021-09-01T13:30:00+00:00 |
| target_end | 2022-09-01T13:30:00+00:00 |
| security_exit_session | 2022-08-31 |
| benchmark_exit_session | 2022-08-31 |
| earliest_target_mature_at | 2022-08-31T21:00:00+00:00 |
| next_month_rejected | 2021-10 |
| minimum_ready_history_start | 2014-09 |
| last_required_dev_month | 2021-09 |
| minimum_contiguous_ready_months | 85 |
| horizon_months | 12 |
| holdout_start | 2022-10-01 |
| security_calendar | XNYS |
| benchmark_calendar | XNYS |
| semantics | Nominal decision_at + H12 date < holdout start; security and SPY exit at their last closed session at that instant. No outcome data read. |

The latest monthly XNYS open whose nominal H12 endpoint precedes holdout is derived by walking market months backwards. Both the security and SPY use the previous closed XNYS session at the target instant; maturity uses the existing one-hour lag. Nominal horizon, not merely the earlier exit close, is the frozen sealing rule. No prices or outcomes in holdout/OOT are inspected.

The frozen inclusive calendar requires 36+12+1+12+2×12=85 continuous decision months, positioned **2014-09..2021-09**. The first fold retains 37 calendar TRAIN months, as in the existing contract. The missing extension is **2014-09..2016-09: 25 months**. The 2016-10..2021-09 portion contributes 60 usable months; the extra READY months through 2022-09 do not make H12 TEST labels admissible. Membership is required at decisions; outcome prices extend to 2022-09 without requiring later decision cohorts.

## Three latest target calendar folds

| Fold | TRAIN | Purge/excluded decisions | Embargo | TEST |
|---|---|---|---|---|
| 1 | 2014-09..2017-09 | 2017-10..2018-09 | 2018-09..2018-09 | 2018-10..2019-09 |
| 2 | 2014-09..2018-09 | 2018-10..2019-09 | 2019-09..2019-09 | 2019-10..2020-09 |
| 3 | 2014-09..2019-09 | 2019-10..2020-09 | 2020-09..2020-09 | 2020-10..2021-09 |

These are three structurally valid **target** calendars, not three ready historical datasets. The prior READY-run generator still yields one calendar (TEST 2020-11..2021-10), which is not label-safe; shifting only that single run does not fill the missing TRAIN history.

## Calendar vs labels vs coverage

CALENDAR_FOLD validates dates. LABEL_SAFE_FOLD certifies a complete required membership/identity history, at least the contracted 36 TRAIN decision months with labels available at fit, and all twelve TEST months with valid H12 outcomes. Individual absent rows are reported; no per-security or per-issuer sample-size threshold is used. ML_ELIGIBLE_FOLD adds the future statistical coverage contract and stays NOT_YET_EVALUATED_BLOCKED_BY_COVERAGE. `required_securities=100` is unchanged and cannot decide label safety. ADR-0055 V2 supersedes its earlier conflation with trainability.

| Fold | Calendar valid | TEST label safe | Full fold label safe | TRAIN eligible | TEST eligible | Securities | Issuers | Blocking reasons |
|---|---|---|---|---|---|---|---|---|
| 1 | True | True | False | 588 | 599 | 50 | 50 | REQUIRED_MEMBERSHIP_HISTORY_NOT_READY, TRAIN_LABEL_MONTHS_INCOMPLETE_AT_FIT |
| 2 | True | True | False | 1127 | 600 | 50 | 50 | REQUIRED_MEMBERSHIP_HISTORY_NOT_READY, TRAIN_LABEL_MONTHS_INCOMPLETE_AT_FIT |
| 3 | True | True | False | 1725 | 609 | 51 | 51 | REQUIRED_MEMBERSHIP_HISTORY_NOT_READY, TRAIN_LABEL_MONTHS_INCOMPLETE_AT_FIT |

TEST outcomes already span all twelve months in each intended fold. Full-fold certification is blocked by the missing earlier membership history and insufficient verified TRAIN months. Source values remain immutable; no labels/features were built. Every decision window, availability cutoff, actual exit, maturity and exclusion is in `FIRST_ML_FOLD_AUDIT.json`.

## Required monthly path (newest first)

| Month | Required by fold | Status | Cards | Events | Identities | Ambiguities | Conflicts | Minimum resolution |
|---|---|---|---|---|---|---|---|---|
| 2021-09 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-08 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-07 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-06 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-05 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-04 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-03 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-02 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2021-01 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-12 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-11 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-10 | F3:TEST | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-09 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-08 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-07 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-06 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-05 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-04 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-03 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-02 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2020-01 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-12 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-11 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-10 | F2:TEST, F3:PURGE/EMBARGO_CONTINUITY | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-09 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-08 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-07 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-06 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-05 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-04 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-03 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-02 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2019-01 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-12 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-11 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-10 | F1:TEST, F2:PURGE/EMBARGO_CONTINUITY, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-09 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-08 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-07 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-06 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-05 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-04 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-03 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-02 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2018-01 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-12 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-11 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-10 | F1:PURGE/EMBARGO_CONTINUITY, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-09 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-08 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-07 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-06 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-05 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-04 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-03 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-02 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2017-01 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2016-12 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2016-11 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2016-10 | F1:TRAIN, F2:TRAIN, F3:TRAIN | READY | 0 | 0 | 0 | 0 | 0 | NONE |
| 2016-09 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 1 | 1 | 0 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 2016-08 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 1 | 1 | 0 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 2016-07 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 1 | 1 | 0 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 2016-06 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 1 | 1 | 0 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 2016-05 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 1 | 1 | 0 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 2016-04 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 1 | 1 | 0 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 2016-03 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 12 | 10 | 1 | 0 | 1 | Audit the linked primary release and both anchor rows; resolve contradictory event legs, transient positions or legal predecessor/successor with official evidence.; Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2016-02 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 12 | 10 | 1 | 0 | 1 | Audit the linked primary release and both anchor rows; resolve contradictory event legs, transient positions or legal predecessor/successor with official evidence.; Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2016-01 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 11 | 10 | 1 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-12 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 11 | 10 | 1 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-11 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 11 | 10 | 1 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-10 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 11 | 10 | 1 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-09 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 23 | 17 | 6 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-08 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 23 | 17 | 6 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-07 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 23 | 17 | 6 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-06 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 23 | 17 | 6 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-05 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 23 | 17 | 6 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-04 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 23 | 17 | 6 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-03 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-02 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2015-01 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2014-12 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2014-11 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2014-10 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 2014-09 | F1:TRAIN, F2:TRAIN, F3:TRAIN | BLOCKED | 13 | 11 | 2 | 0 | 0 | Dated official S&P index notice/history/file proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself.; Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |

Distinct in-path cards: **49**, categories {'PRIMARY_EVENT_MISSING': 39, 'SECURITY_IDENTITY_ONLY': 9, 'PRIMARY_DELTA_UNEXPLAINED': 1}. Full gap IDs, official anchor references and resolution requirements remain in the result JSON and `D02_EXTENDED_AUDIT.json`; 118 cards are outside this path and are not clean-up targets.

## Under Armour and chronological stop

**OFFICIAL_INDEX_DATE_UNVERIFIED.** Distribution 2016-04-07 and regular-way listing 2016-04-08 are proved; index inclusion is not. Class A and C, their CUSIPs and recycled ticker histories remain separate. Official S&P announcements, archived pages, constituent notices/history and index files are acceptable formats. Searches, historical archive URLs, temporal range and failure status are in `D02_CRITICAL_SOURCE_ATTEMPTS.json`; SEC/OCC alternative evidence and hashes are in the evidence matrix. The minimum missing proof is an official dated index record directly establishing Class C inclusion and its effective date. No secondary date is promoted. Stop before resolving earlier months until this newest required blocker closes.

## Claude trace and unchanged scope

`CLAUDE_HEAD_TRACE.md/.json` audits both intervening commits and all eighteen paths: no D02/fold/target/holdout/readiness contract changed. Existing interface additions are retained. L-3/Alcoa remain TIME_PRECISION_NOT_MATERIAL_FOR_MONTHLY_MEMBERSHIP with unknown legal timezone; XOM/RTX/GOOGL/GE and Broadcom are inventoried only when they block this path. No BTC, global markets, features, models, champion/master or coverage-threshold changes.

## Gates

| Gate | Status | Actual |
|---|---|---|
| D02_MONTHLY_RESEARCH_READY | BLOCKED | 72/141 READY; required history 60/85; target calendar folds 3, label-safe 0 |
| US_SECURITY_IDENTITY_READY | PARTIAL | 40 weak identity securities; 0 unresolved anchor lines |
| D05_READY | READY | Yahoo Finance (CANONICAL_PROVIDER_FOR_PITQUANT, VENDOR) |
| BENCHMARK_RETURN_BASIS_READY | READY | US rows comparable 7000/7000; non-US via USD conversion (PROXY) |
| RESEARCH_SECURITY_COVERAGE_READY | BLOCKED | 51 usable (strict); 51 if D05 were accepted; 100 with snapshots |
| US_FUNDAMENTALS_READY | READY | 40 securities |
| HOLDOUT_SEALED | READY | 0 snapshots inside the holdout |
| RESEARCH_DATA_READY | BLOCKED | derived |
| FIRST_ML_BASELINE_READY | BLOCKED | false |

Reproduce offline with the explicit project DB: `scripts/gen_data_readiness_first_ml.py`, then `scripts/gen_d02_label_safe_report.py` (legacy `gen_d02_critical_report.py` delegates here). Original pre-V2 reports and source provenance are retained in the baseline file; original 93 cards are not rewritten.
