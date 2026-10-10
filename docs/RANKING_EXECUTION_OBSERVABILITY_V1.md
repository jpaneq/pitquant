# Ranking execution observability V1

Status: technical repair tested on synthetic fixtures only. V0R2 is **PROPOSED_NOT_APPROVED**. Initial HEAD: `1ddd3c1cd08014650823b8ca63deaf1b1b89c177`. Adaptive iteration remains 3. Real fits, new DEV predictions, holdout and OOT outcomes accessed: **0**.

## Confirmed defect and interpretation

The frozen V0R1 runner computed inner metrics and attempted selection before persisting the inner model or its validation scores. Its first inner fit produced six undefined ICs, then the global exception discarded the objects needed to distinguish constant predictions from other causes. The forensic conclusion remains INSUFFICIENT_EVIDENCE. This repair does not reconstruct that fit, establish constant historical scores, or demonstrate scientific progress.

All existing V0/V0R1 documents, manifests, execution locks, failure audit and frozen implementation are preserved byte-for-byte. The companion JSON records their hashes and frozen contract hashes. The old executor is not rewritten: a new observed lifecycle and a blocked draft entry point preserve its historical reproducibility.

## Persistence lifecycle

`ranking_observability.fit_synthetic_inner` first archives input arrays, declared feature names, row counts and context. It validates shapes, ordering, issuer/security-month uniqueness, exact monthly qid, targets/relevance, TRAIN availability and TRAIN/validation separation. Then:

1. Fit returns. The **first durable operation** saves the native model, parameters/context and implementation hash in `model`.
2. `training` saves backend/library metadata and actual optional ensemble inspection, referring to the committed model.
3. Predict validation once; `validation` stores raw scores, features, targets, relevance, qid, decision_month, issuer_id/security_id, and both target and prediction row-key bindings.
4. `descriptive` stores monthly numerical diagnostics without calculating ranking metrics. Technical anomalies abort here.
5. Only after these phases verify does Spearman run. `diagnostics` records observed ICs or explicit null reasons; `candidate` records the proposed status and selection summary.

Each phase has an immutable directory and COMMIT.json containing exact file inventory, SHA-256 and self hash. Writing uses same-filesystem staging, exclusive files, fsync, verification, atomic rename and publication verification. No overwrite or silent resume is permitted. The archive root belongs to one attempt/fold/candidate/inner-block; a future approved controller must allocate distinct roots. Individual phases are atomic, not a single transaction spanning an entire fit. A partial attempt is never described as a completed experiment.

Persistence or serialization failure aborts before evaluation. Incomplete staging remains forensic evidence, not a valid committed phase. Exception metadata is saved where storage permits. Complete disk failure may prevent that marker. A killed process between fit return and its first disk write cannot be guaranteed to leave a model; test H injects immediately after the first verified model commit. Exceptions during prediction, native diagnostics or metrics retain already committed phases.

## Diagnostics and proposed decisions

Every monthly record retains N, finite/nonfinite counts, distinct finite scores/targets, population SD, min/max, modal identical-score percentage, distinct relevance grades, and IC/null reason. Nonfinite statistics are explicitly finite-only; raw nonfinite values remain in NPZ. Fold, candidate and inner-block are in the enclosing context. Native XGB inspection counts actual boosted rounds, trees, split/stump trees, splits, leaves, gain, feature importance (weight/gain/total_gain/cover/total_cover) and tree dump. Per-query raw predictions are archived rather than reconstructed.

Undefined reasons: CONSTANT_SCORES, CONSTANT_TARGET, INSUFFICIENT_ROWS, NONFINITE_SCORES, NONFINITE_TARGET, GROUP_ALIGNMENT_ERROR, OTHER. Unknown failures remain OTHER; an exception also records its phase/type/message. Input faults may abort before any scores exist, with the input evidence retained. Native ensemble details are linked from monthly diagnostics rather than duplicated for each query. Missing backend details say NOT_PROVIDED.

Finite constant scores with variable targets and validated groups are NON_RANKING_CANDIDATE when all required inner months are constant. That status cannot win and does not mean technical corruption. Corrupt qid, invalid labels, row loss, misalignment, nonfinite scores, serialization errors or other technical failures abort immediately. Constant targets are a degenerate evaluation query and treated as TECHNICAL_INVALID in this proposal; this does not claim the source data were corrupt.

For a candidate with at least one defined month and other months undefined only due to constant scores, the draft inherits the frozen partial-month selection composite: sum of defined ICs divided by **all required months**. Monthly IC remains null; the composite is explicitly not an observed IC. No months disappear, no coverage threshold is introduced. All required blocks must be complete before candidate-level selection. Tie-breaking remains composite, NDCG20 and original grid order (1e-12). All candidates nonranking abort with NO_VALID_RANKING_CANDIDATE. No scientific outer metrics or acceptance criteria are relaxed.

## Backend and execution boundaries

The lifecycle depends on a fit/predict/serialize/metadata protocol and explicit scored-row keys. Optional backend diagnostics are separate. XGB uses composition around the frozen adapter; no parameters change. LightGBM and CatBoost are neither installed nor trained. TRAINING_ARTIFACT and VALIDATION_DIAGNOSTIC cannot be promoted automatically to OUTER_TEST_RESULT or SCIENTIFIC_CONCLUSION; the current publisher rejects those kinds.

The callable fit wrapper accepts only SYNTHETIC_FIXTURE scope and synthetic issuer/security identifiers. `scripts/run_observed_equity_ranker.py` unconditionally blocks before reading research inputs. This is a tested infrastructure draft, not an approved real-data executor. Human approval, a new immutable manifest/attempt identity and versioned real controller wiring are mandatory before future execution. The historical runner is never rerun in this repair.

## Verification

Tests A–J cover valid IC, constant scores, variable scores/constant targets, nonfinite scores, qid corruption, mixed/all nonranking candidates, exceptions after model commit and during Spearman, and archive write failure. Additional tests cover all reason codes, row loss, alignment, real execution blocking, integrity tampering, immutable history and the full denominator. A deterministic native XGB fit uses exclusively fabricated rows with the unchanged frozen first-candidate parameters to inspect actual serialization/booster diagnostics. These fits and scores are not DEV results.

Validation commands: Ruff check/format, mypy strict, full unit/integration suite, PIT suite and strict PostgreSQL/Alembic controls, plus repository CI. Exact run totals and final HEAD are delivered with the PR, avoiding a self-referential committed CI claim.

Native synthetic example (XGBoost 3.1.3, 120 fabricated TRAIN rows, 20 validation rows, unchanged candidate 0): 200 boosted rounds/trees, 200 trees without splits, zero split trees, zero splits, 200 leaves, gain total 0 and empty feature importance maps. This verifies inspection and archival for an actual constant synthetic booster. It provides no evidence about the missing historical booster.
