# XGBRanker V0R1 — diagnostic audit

**F — INSUFFICIENT_EVIDENCE. No new fits. No exact causal attribution is possible from the retained artifacts.**

## Retained evidence

The failed run contains started.json, first-real-fit.json and invalidated.json only. Archived inputs bind each issuer/month to its validation target and 43 feature values. No inner model, prediction vector, native tree dump, runtime qid or monthly metric array was persisted. Synthetic smoke models are not evidence of this real fit.

All input and frozen code hashes match the attempted execution lock. This audit did not open the frozen database, raw market sources, holdout/OOT or any other model.

## Six validation months

Target is archived H12 excess total return, in return fractions; SD is population ddof=0. Relevance-grade counts are descriptive application of the frozen transformation to those archived labels, not a recovered runtime grade array.

| Month | Decision UTC | Issuers | Distinct targets | Target SD | Distinct grades | Score distinct / SD / min / max / identical % | Monthly cause |
|---|---|---:|---:|---:|---:|---|---|
| 2017-03 | 2017-03-01T14:30:00+00:00 | 178 | 178 | 0.274611611 | 10 | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |
| 2017-04 | 2017-04-03T13:30:00+00:00 | 178 | 178 | 0.245404788 | 10 | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |
| 2017-05 | 2017-05-01T13:30:00+00:00 | 180 | 180 | 0.248467647 | 10 | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |
| 2017-06 | 2017-06-01T13:30:00+00:00 | 178 | 178 | 0.269103409 | 10 | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |
| 2017-07 | 2017-07-03T13:30:00+00:00 | 176 | 176 | 0.262442855 | 10 | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |
| 2017-08 | 2017-08-01T13:30:00+00:00 | 177 | 177 | 0.250361506 | 10 | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |

None of the six archived target groups is constant, nonfinite or too small. OTHER denotes unavailable causal evidence, not proof of an additional numerical cause. Constant scores are compatible with the frozen IC function/control flow, but their actual distinct count, spread, extrema and modal identical percentage cannot be measured. We do not assign CONSTANT_PREDICTIONS without the prediction vector.

## Trees and alignment

Configured trees: 200. Actual constructed trees, splits, leaves, feature importance and score distribution: unavailable. Even a confirmed constant validation vector would not by itself prove every tree is a stump. Learned model versus failed evaluation cannot be distinguished here.

The archived validation has 1067 rows, qids 0–5 in month order, complete expected groups and no issuer-month or security-month duplicates. The frozen source constructs X/grades/qid in the same row order and masks rows and scores with the same monthly selector. No static alignment bug was found; actual score/target correspondence cannot be certified without runtime predictions.

## Static parameter review

First candidate: depth=2, lambda=1, learning_rate=0.03. min_child_weight=10 thresholds child Hessian sums, not ten rows; small child Hessians can block every split. [XGBoost 3.1.3 split evaluator](https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/hist/evaluate_splits.h).

Mean pair sampling uses eight pairs; the enabled normalization scales pair gradients and Hessians. Its interaction with the child threshold is a possible mechanism, not evidence of this fit's cause. [LambdaRank source](https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/objective/lambdarank_obj.cc).

Depth caps growth; L2 changes leaf weight/gain; positive learning_rate shrinks updates. None alone demonstrates that this model had no splits. No alternative value was tried. [Tree parameter source](https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/param.h).

## Selection contract

An undefined month contributes zero only to selection if another month is defined; the published IC remains null. A wholly undefined candidate raises before append, invalidating the entire run. Candidates 1–7 and all later folds/control were unreachable after this exception; no performance claim about them can be made.

The preregistration states a minimum of one defined month but does not explicitly spell out whole-experiment abort versus candidate rejection. The pre-fit frozen executor unequivocally implements global abort. Discarding a candidate and continuing would change the operative policy and requires a new methodological preregistration. This audit does not change that policy or demonstrate a numerical Spearman bug.

## Classification and next step

Exactly one classification: **F — INSUFFICIENT_EVIDENCE**. A proven secondary observability defect is that inner scores/model/monthly diagnostics were lost on exception. The previous 44/88 metadata-description error is separate; there is no evidence tying it to undefined IC.

Exactly one recommendation: **FIX_IMPLEMENTATION_BUG**, limited to prospective failure-path artifact retention. Save model/config and row-key-bound scores, targets, grades and qid, with per-month diagnostic reasons, before throwing. This repair cannot recover historical outputs and has NOT been implemented in this task.

Instrumenting persistence without changing numerical behavior is a technical repair. Changing candidate-invalidity policy is methodological; changing hyperparameters is a new scientific experiment. Any future exact reexecution needs human authorization and a distinct attempt identifier; it cannot be called a verified replay of outputs that were not saved. No reexecution or new experiment is authorized here.

New fits = 0; holdout outcomes = 0; OOT outcomes = 0. Iteration remains 3. Final experiment remains INVALIDATED_NOT_COMPLETED. No scientific progress claimed.
