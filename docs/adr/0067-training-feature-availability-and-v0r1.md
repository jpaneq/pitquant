# ADR-0067 — TRAIN feature availability and V0R1

Status: Accepted before any expanded-dataset fit.

V0 aborted at preflight. Its original manifest, completion, execution lock and aborted reports are preserved byte for byte. V0R1 records V0's normalized history status as `ABORTED_PREFLIGHT_FEATURE_AVAILABILITY` without rewriting its historical files.

`TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1` requires at least one finite observed value for every retained raw feature in every required inner and outer TRAIN block. The same common feature list is supplied to every estimator. The rule introduces no percentage threshold and never drops rows. Partial missingness keeps the existing model-specific preprocessing: native NaN for XGB; TRAIN-only imputation, clipping, standardization and one missingness indicator per retained feature for M4R.

The outcome-free audit covers the 44 original features in 12 blocks (528 cells). The only failing feature is `val_pe_own_pct`. Native feature-history replay reproduces all 16,717 feature rows and their provenance exactly. Early training history has fewer than 24 valid prior PE decision observations; the frozen percentile implementation correctly returns missing. No feature engine, fact, price, target, history initialization, fold or cohort is repaired or warmed up.

The history belongs to one price security, using issuer-resolved facts. Only finite native valuation points from earlier COMBINED-eligible decisions enter it, after the current percentile is read. The frozen implementation counts the last 60 valid decision observations, not 60 elapsed calendar months. This distinction is explicit; no history semantics are changed by this revision.

The raw experiment contract therefore projects 44 to 43 columns by removing `val_pe_own_pct`; no replacement is added. The original dataset and its hashes are untouched. Derived inputs retain every issuer-month row, target and non-feature provenance. A new immutable manifest, feature hash, input hash and source execution lock are frozen before fitting. All other original contracts and the XGBoost implementation completion are inherited exactly.

Eligibility revision keeps adaptive iteration 2. The first real fit records iteration 3; successful final execution completes the structural DEV experiment. Replay repeats the exact frozen run, not a new search. No other challenger or holdout/OOT outcome is authorized. Any preflight, integrity or reproducibility failure invalidates execution rather than silently changing rules.

## Execution disposition

V0R1 passed feature availability and then failed the unchanged defined-inner-IC selection guard in its first F1 candidate. One real inner fit consumed adaptive iteration 3; no outer prediction or mandatory control fit occurred. The execution remains INVALIDATED, not completed. No replay or further candidate fits were attempted.

An inherited manifest description/count mismatch (44/88 instead of the actual 43 RAW/intended 86 transformed) was also recorded. The attempted manifest is untouched. A separate immutable metadata revision 2 corrects the descriptions and introduces explicit common RAW count/hash and control transformed-count bindings. A reusable binding validator and synthetic regression reject this mismatch; the correction passed preflight only and is not a new executed experiment. Any future fit needs explicit human review of the invalidated execution.
