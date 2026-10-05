# ADR-0055 — Calendar, label-safe and ML-eligible folds (V2)

Status: amended and applied under the user's 2026-10-05 label-safe critical-path request.
The initial V1 decision is preserved in Git at a47228d. No training authorized.

## Why V1 is amended

V1 distinguished dates from certified trainability but made an unspecified statistical
row minimum prevent label certification. The user explicitly separates these decisions:
D02 concerns correct historical universes and usable temporal labels; statistical sample
sufficiency belongs to RESEARCH_SECURITY_COVERAGE_READY. V2 removes that coupling,
without approving or inventing a replacement sample-size threshold.

## Three levels

CALENDAR_FOLD: expanding TRAIN/PURGE/EMBARGO/TEST dates satisfy the unchanged frozen
FIRST_EQUITY_ML_12M_V0 contract. TRAIN minimum 36, H12 purge, embargo 1, TEST 12,
step 12, three folds. The inclusive constructor still gives 37 calendar TRAIN months
in the first fold. A proposed calendar is structural, not proof that its data exists.

LABEL_SAFE_FOLD: calendar valid, complete usable membership/identity history over its
required interval, at least the contracted 36 TRAIN decision months with available
labels at fit, and all twelve TEST months with valid mature H12 outcomes. No row uses
holdout/OOT outcomes. TRAIN rows also satisfy the existing actual-instant availability
and purge/embargo checks. Invalid individual rows are excluded and counted; a missing
individual security does not erase a month with other valid rows. A zero-outcome month
cannot meet temporal completeness. Existence of outcome rows is not a statistical
sample-size claim. Missing core model features can reduce ML candidate counts without
changing temporal label validity.

ML_ELIGIBLE_FOLD: label-safe plus the future approved coverage/sample-size contract.
`coverage_evaluated=false`, `ml_eligible=null`, status
NOT_YET_EVALUATED_BLOCKED_BY_COVERAGE. UNSPECIFIED_CONTRACT remains visible for the
statistical minimum, but neither it nor required_securities decides label safety.

## Derive the latest three folds

`latest_label_safe_history` walks backwards over first XNYS monthly opens. The
nominal decision_at + H12 date must be strictly before holdout start. Both US
security and SPY use their last closed XNYS session at that target instant;
label availability uses the existing one-hour close lag. This is a calendar-only
calculation and reads no prices, labels or performance in sealed periods.
The nominal boundary is retained even when the preceding close is before holdout.

For the frozen holdout start 2022-10-01, the latest admissible decision is
2021-09-01 13:30Z; nominal endpoint 2022-09-01 13:30Z, prior security/benchmark
close 2022-08-31, earliest label availability 2022-08-31 21:00Z. October 2021
is rejected by the nominal boundary. These are program outputs, not configured dates.
Actual existing label maturity remains separately audited per row.

The frozen constructor requires 36+12+1+12+2×12=85 decision months, positioned
2014-09..2021-09. Its three latest TEST windows are 2018-10..2019-09,
2019-10..2020-09 and 2020-10..2021-09, with a common TRAIN start of 2014-09.
The operational D02 requirement is that positioned interval, not 85 months ending
anywhere. Required prices/outcomes may extend to September 2022; that does not
require membership at a subsequent decision merely to compute an existing label.

## Certification and audit

Every actual row retains nominal target_start/end, actual exit, target maturity,
availability cutoff and family-specific exclusions. TRAIN availability cutoff is
the first TEST decision; TEST cutoff is audit time. Missing, prematurely available
or future labels fail closed. Nominal/actual windows touching sealed periods are
rejected before inspecting outcome values. Readiness queries select only label-safe
DEV target dates; sealed/out-of-time outcome rows are not loaded.

The intended three calendars are reported separately from the old available-READY-run
calendar. Each fold reports complete twelve-month TEST coverage, TRAIN temporal
months, missing historical months, securities, issuers, eligible rows and exclusions.
A calendar can be structurally valid while label safety fails on missing history.
Unknown issuer IDs are counted explicitly, never treated as securities-as-issuers.

D02_MONTHLY_RESEARCH_READY for First ML requires historical membership/identity
correctness for the complete derived interval and three LABEL_SAFE_FOLDS. Coverage
remains a separate mandatory First ML gate. Thus D02 can eventually be READY while
coverage and FIRST_ML_BASELINE_READY stay BLOCKED. Legacy Research Lab collection
flags are explicitly distinguished from the first-ML readiness gates.

## Unchanged constraints

required_securities=100. No coverage threshold, calendar constructor, horizon,
feature/model definitions, holdout/OOT boundaries or market scope is changed.
No model is trained. No BTC, scheduler, simulation, champion/master or non-US work.
Under Armour still needs official evidence directly establishing index inclusion
and its effective date; equivalent official history/notices/files are acceptable.
Corporate distribution, listing or a secondary candidate date do not close membership.
