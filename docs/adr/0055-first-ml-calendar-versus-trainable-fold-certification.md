# ADR-0055 — Certify first-ML target availability separately from calendar folds

Status: accepted for the readiness audit requested on 2026-10-05; no training authorized.

## Context

The frozen FIRST_EQUITY_ML_12M_V0 calendar can produce a fold whose TEST decisions are
before the holdout but whose H12 outcomes touch it. With the current 72-month run,
TRAIN is 2016-10..2019-10 and TEST is 2020-11..2021-10. October 2021's nominal
H12 endpoint reaches the sealed period beginning 2022-10-01. The calendar's
inclusive boundaries, 37 first-fold TRAIN months and 12 excluded months are retained.

There is no explicit per-fold row minimum in this experiment. The legacy global
DEV minimum in model_contracts is a different contract and cannot substitute for one.

## Decision

Keep the calendar constructor and all feature, target and model definitions intact.
Use first_ml_eligibility for membership, identity, price provenance, benchmark basis
and feature-family checks. Extend its HOLDOUT/OOT guards to the nominal H12 endpoint
and any later actual exit, so an allegedly OK target cannot bypass sealed boundaries.

The read-only fold auditor additionally checks actual entry/exit, security and
benchmark outcomes, label_available_at, the nominal H12 window, and timezone-aware
availability cutoffs. TRAIN labels must be available by the first actual TEST
decision; TEST labels must be available by audit time. Both month-level purge/embargo
and the corresponding actual decision-plus-H12-plus-embargo boundary are enforced.
No price rows in sealed periods are read to reconstruct missing targets.

Report every TRAIN/TEST row with its nominal target window, actual exit, maturity,
cutoff and family-specific exclusion reasons. Count calendar rows, mature labels,
benchmark-ready, price-ready and eligible rows separately; these marginal counts
are not interchangeable. Report PRICE and FUNDAMENTALS eligible counts on the same
calendar. A complete twelve-month TEST window requires eligible rows in all twelve
months, independently of the future statistical minimum.

Until the per-fold row minimum is explicitly defined, its status is
UNSPECIFIED_CONTRACT and no fold is certified trainable. D02 for First ML requires
85 continuous usable membership months, three calendar folds and three certified
trainable folds. Other identity and dataset gates remain independently required.
The legacy Research Lab collection flags are not this experiment's certification.

## Consequences

Closing the thirteen missing membership months alone cannot certify three trainable
folds. Even without the unspecified minimum, the resulting last calendar fold has
TEST 2021-10..2022-09, whose entire nominal H12 outcome window touches holdout.
That is an independent outcome-window limitation, not permission to move the
holdout, shorten TEST, change the target or expand this task's historical scope.

Under Armour's index-effective date remains unconfirmed. OCC and SEC corporate
evidence is accepted for class/distribution/listing facts only. This ADR does not
relax membership evidence or promote the candidate 2016-04-08 date to an index event.
Required securities remains 100; coverage design and M0–M4 training stay deferred.
