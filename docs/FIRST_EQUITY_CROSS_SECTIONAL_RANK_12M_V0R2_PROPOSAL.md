# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R2 — proposal

**PROPOSED_NOT_APPROVED. Do not execute.** This document is not an approved preregistration or a scientific result. It is a methodological proposal following the already observed V0R1 failure. It is neither independent nor completely blind. `dev_adaptive_iteration = 3` remains unchanged during this repair; any future real attempt must declare its new adaptive identity before execution.

## Immutable scientific baseline

Inherit the V0R1 contracts and hashes listed in RANKING_EXECUTION_OBSERVABILITY_V1.json: dataset, target/relevance transformation, cohorts, features, outer folds, complete inner geometry, grid, library contract, metrics, bootstrap, classification and sealed holdout policy. No data, features, targets, folds or XGB hyperparameters change. V0R1's 43 raw features / 86 control inputs remain the baseline. Its attempted manifest digest is `d6a7a51eb448a346647a79396256ce4362324330630931efc9b9031c61220996`; this is a reference, not a new V0R2 manifest.

The original eight-candidate grid stays max_depth 2/3 × learning_rate .03/.05 × reg_lambda 1/10 in original order. n_estimators=200, min_child_weight=10, pair_method=mean, pairs_per_sample=8 and all normalization/fixed settings remain exactly frozen. No alternative hyperparameter was tested here.

## Changes requiring approval

- Persist and verify model, metadata, ensemble, scores/labels/row keys and numerical diagnostics before evaluating inner IC.
- Preserve all undefined monthly ICs as null with explicit reasons.
- An entire candidate with constant finite scores in every required inner month, variable targets and valid data is NON_RANKING_CANDIDATE, ineligible to win. Continue other candidates only absent any technical fault.
- Any technical invalidity aborts the attempt immediately. Degenerate constant-target queries are included; do not silently drop them.
- If all eight candidates are nonranking, abort NO_VALID_RANKING_CANDIDATE without a selected model or external predictions.
- If at least one required monthly IC is defined and the remainder are undefined exclusively due to constant scores, retain the original composite: sum(defined IC)/all required months, with every block/month and defined/undefined count visible. Do not present this composite as mean observed IC or rewrite null IC as zero. No new coverage threshold is proposed. Tie-breaking is unchanged.

This changes V0R1's global all-undefined-candidate abort into a candidate-local nonranking outcome followed by an explicit all-candidates abort. Observability is a technical repair; candidate continuation is a methodological revision. Neither is applied retroactively. Original failure classification and missing historical evidence remain unchanged.

## Activation conditions and limits

Human approval must explicitly cover the full-denominator composite and degenerate-target abort policy. Then freeze a new immutable V0R2 manifest and execution identity, preserving all scientific contract hashes above and the adaptive history. Before any real fit, a versioned controller must validate the approved full inner geometry, allocate archive roots by attempt/fold/candidate/block, accumulate every required block before selecting, and use the observed lifecycle. The draft real entry point is intentionally blocked and offers no bypass flag.

No new fits on research data, DEV predictions, outer results, holdout access or OOT access are authorized by this proposal. Holdout/OOT stay sealed. Synthetic validation cannot establish that XGB will learn, identify the original failure's cause, or demonstrate scientific progress.

Recommendation after green validation: **READY_FOR_HUMAN_APPROVAL_OF_V0R2**. Approval is a separate action; execution is not part of this repair.
