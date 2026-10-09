# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1 — invalidated first execution

**No valid final ranking result. One real inner fit; zero outer predictions; no control fit.**

## Feature correction

All 44 frozen features were audited in 9 inner plus 3 outer TRAIN blocks (528 cells). Only `val_pe_own_pct` failed. The 43 retained features pass every block (516 cells). No arbitrary percentage coverage threshold was introduced.

Frozen PE is prior raw close × split-aligned cover shares / positive visible TTM earnings. Zero/negative/unresolved earnings and stale/unresolved shares do not create PE. Own history requires 24 finite native PE observations from earlier decisions; the current point is added afterwards. It uses the last 60 valid decision observations, not elapsed calendar months. Facts are cut strictly before decision_at; prices close before decision. Histories are per security with issuer-resolved facts, just as the frozen dataset specifies.

History begins at frozen COMBINED decisions in 2014-09. First theoretical and observed scientific availability is 2016-09. Full native replay matched every value and provenance in all 16,717 scientific rows. No construction bug was found.

| Block | Rows | Issuers | PE valid / missing | PE coverage | Percentile valid | Issuers ≥24 prior PE |
|---|---:|---:|---:|---:|---:|---:|
| F1/INNER_0_TRAIN | 2877 | 174 | 2581 / 296 | 89.71% | 0 | 0 |
| F2/INNER_0_TRAIN | 2877 | 174 | 2581 / 296 | 89.71% | 0 | 0 |
| F2/INNER_1_TRAIN | 3893 | 184 | 3443 / 450 | 88.44% | 0 | 0 |
| F3/INNER_0_TRAIN | 2877 | 174 | 2581 / 296 | 89.71% | 0 | 0 |
| F3/INNER_1_TRAIN | 3893 | 184 | 3443 / 450 | 88.44% | 0 | 0 |

The 18-month windows have at most 17 prior valid points; 24-month windows at most 23. Percentile coverage is 0%, although PE itself has 88–90% coverage. This is warm-up, not a complete absence of source PE.

REMOVE: `val_pe_own_pct`. ADD: nothing. XGB received 43 RAW columns. M4R was intended to receive the same 43 RAW plus 43 missing indicators (86); it was not fitted.

Dataset unchanged: `e90b817ab038735d1c5aa0f096384cb80337b75589dabf0731e49b39a9b7af39`.

Old feature hash: `f4bdb8a502b4c0dda424ad1f63b47d853fc9bfb4e7f0274ad79d12022cf5bc49`.

New feature hash: `4803e4d52b320a4f24771e92df1586a57af5d4fcccabd6f2cfbe721e4d1855e7`.

Attempted manifest: `d6a7a51eb448a346647a79396256ce4362324330630931efc9b9031c61220996`.

Corrected metadata manifest (not executed): `0d44e5d9d66ba227cd0a512199c745c0a592ac86ffb7ba13b2dc34506f50794d`.

Derived input: `5c5b6fcf3464e80ffe5d525c094d249b454de81ea5ce67b12a5585503b45b922`.

## Execution failure and bug history

All revised trainability/PIT/cohort/hash checks passed. The first real fit was F1/candidate 0: max_depth=2, learning_rate=0.03, reg_lambda=1; all other parameters were unchanged. All six inner validation-month ICs were undefined. The frozen selection contract requires at least one defined month. The runner raised `ValueError: no defined inner IC` and wrote an INVALIDATED record.

This is an observed inner-execution failure, not evidence for a final negative ranking classification. No candidate was selected; F2/F3, outer TEST and M4R were not executed. Inner predictions were evaluated but their scores/model were not persisted before failure. The report does not fabricate them or assert an unverified causal explanation such as a Hessian threshold. No real fit was repeated.

A second implementation error was discovered in inherited manifest descriptions: they still said 44 RAW/88 transformed while the execution used the 43-column projection. The attempted manifest remains immutable. A separate metadata revision 2 corrects 43/86 and adds explicit feature-hash/count bindings, without changing parameters or outcomes. Its full 43-feature preflight passes, but it has not been executed. This technical fix is not permission for an additional adaptive search.

## Scientific state

V0 is preserved as aborted before fit. V0R1 is INVALIDATED after one real inner fit. Adaptive iteration = 3. Final structural experiment = INVALIDATED_NOT_COMPLETED. F1/F2/F3/combined metrics, paired comparison, quintiles, sector diagnostics, bootstrap and classification are null. No replay of an invalidated execution.

Holdout outcomes = 0; OOT outcomes = 0; other challengers = 0. Conditions for holdout consideration are not met.

One next step: `HUMAN_REVIEW_INVALIDATED_INNER_IC_EXECUTION_BEFORE_ANY_NEW_FIT`. A performance-based recommendation cannot be assigned without valid outer results.
