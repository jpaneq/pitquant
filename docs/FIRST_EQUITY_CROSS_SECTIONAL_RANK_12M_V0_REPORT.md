# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0 — preflight closure

**ABORTED_PREFLIGHT_FROZEN_CONTRACT_CONFLICT. No real model has been fitted.**

Initial HEAD: `8b7f258180dbb12e68ab0645783ea62b55598541`. The frozen dataset, original preregistration, sec-tags-5, 44 features, full cohort and folds remain unchanged.

XGBoost 3.1.3 and its OpenMP runtime are installed. All material parameters are recorded before a real fit in IMPLEMENTATION_COMPLETION and its synthetic booster configuration. Synthetic qid, grades 0..9, linear NDCG gain, fitting, prediction, serialization/reload and exact determinism pass. The optional research adapter owns no PIT, folds, cohort, targets, preprocessing, metrics or holdout.

## Exact blocker

The original scientific freeze checked row eligibility and nullable-feature provenance, but did not check whether every feature had at least one observed value in **each inner TRAIN**. The frozen model preprocessing rule says “all-missing TRAIN feature fails”. `val_pe_own_pct` violates that rule in five of the nine inner blocks:

| Fold | Inner index | TRAIN period | TRAIN rows | Missing feature | Missing reasons |
|---|---|---|---|---|---|
| F1 | 0 | 2014-09–2016-02 | 2877 | val_pe_own_pct | {'INSUFFICIENT_HISTORY': 2581, 'METRIC_NOT_MEANINGFUL': 296} |
| F2 | 0 | 2014-09–2016-02 | 2877 | val_pe_own_pct | {'INSUFFICIENT_HISTORY': 2581, 'METRIC_NOT_MEANINGFUL': 296} |
| F2 | 1 | 2014-09–2016-08 | 3893 | val_pe_own_pct | {'INSUFFICIENT_HISTORY': 3443, 'METRIC_NOT_MEANINGFUL': 450} |
| F3 | 0 | 2014-09–2016-02 | 2877 | val_pe_own_pct | {'INSUFFICIENT_HISTORY': 2581, 'METRIC_NOT_MEANINGFUL': 296} |
| F3 | 1 | 2014-09–2016-08 | 3893 | val_pe_own_pct | {'INSUFFICIENT_HISTORY': 3443, 'METRIC_NOT_MEANINGFUL': 450} |

These counts are feature availability, not model-performance results. The full outer TRAIN sets have observations in this column; that does not make the early inner blocks trainable. The runner audits **every** inner block before creating any real estimator.

No fallback is used. No column is dropped or zero-filled, no valuation history is rebuilt, no window or grid is changed, and no extra algorithm is tried. A frozen rule cannot be bypassed by a claim that the library technically accepts NaN.

## Reconstructed inputs and preserved boundaries

All 16,717 scientific issuer-month rows were reconstructed with the native frozen engines and sec-tags-5. Their missing-feature lists match the frozen audit. Complete query counts are preserved. Targets use native comparable total-return excess vs canonical Yahoo SPY from the read-only frozen database; only pre-holdout target observations are extracted from retained sources. Later split metadata reverses vendor adjustments, not future outcome selection. Maximum target end is 2022-09-01, before the sealed boundary.

46,594 archived original objects and the frozen input hashes were verified. The target-containing reconstruction is retained locally under data/research/equity-ranking-v0, with content hashes; no target or feature writes occur in the frozen or product database. Holdout/OOT outcomes accessed: **0/0**.

## What is and is not a result

Selected candidates F1/F2/F3, L2R/control metrics, paired differences, quintiles, spreads, NDCG, monthly IC, sector diagnostics and bootstrap are **NOT AVAILABLE**. No classification is assigned: lack of an executable frozen contract is not evidence that the ranking signal is absent. F3 recovery cannot be assessed.

No real outer predictions, no real ranker/control fits and no ranking metrics were produced. DEV labels were constructed under the authorized execution scope solely for reconstruction/guards, not fed to other adapters. Current adaptive iteration remains **2**. Final structural DEV experiment is **NOT_COMPLETED**, not completed iteration 3.

## Registry and architecture

See PITQUANT_OPEN_SOURCE_MODEL_REGISTRY.md/.json. XGBRankerAdapter is implemented and synthetically validated but real execution is blocked. LightGBM, CatBoost, DoubleEnsemble, TRA and MASTER are specifications only. StockMixer, HIST and DoubleAdapt have unresolved repository licenses. RSR is AGPL-3.0 reference only. No Qlib core import, no upstream source vendoring and no real-data model shopping.

## Recommendation

**HUMAN_REVIEW_FROZEN_PREPROCESSING_CONTRACT_BEFORE_ANY_FIT.** The performance-based future-path decision tree cannot be applied without a valid experiment classification.

For review only, the smallest prospective amendment would permit fully-NaN columns in inner TRAIN for the native-missing tree ranker while retaining every row and all 44 columns, targets, folds and eight candidates. This changes the frozen preprocessing rule and needs explicit human approval and a new experiment preregistration. It is not implemented or executed here. Alternatively, constructing pre-2014 valuation warm-up changes feature values and requires both a new dataset and experiment version.

Dataset hash: `e90b817ab038735d1c5aa0f096384cb80337b75589dabf0731e49b39a9b7af39`. Reconstructed input hash: `b7949613f290c9ca6a9899845e7c377bbdb0acdc63c6249b7ef7595eab572ada`. Report hash: `bc14a0fb38fe952ccf2ce8d99e29de1fb2c9f031e14d2c306dbb64da5dd3681b`.
