# PITQuant — open-source model adapter registry

Only XGBRanker is authorized for real scientific DEV data in this task, plus the mandatory fixed M4R control. Every other row is a specification only: no imports/installations, new datasets or real-outcome access. Engineering effort/value are judgments, not experimental results. Qlib is not PITQuant core.

## XGBRanker

- **algorithm_family**: LambdaMART.
- **official_repository**: https://github.com/dmlc/xgboost.
- **paper**: https://arxiv.org/abs/1603.02754.
- **license**: Apache-2.0.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/dmlc/xgboost/blob/v3.1.3/LICENSE.
- **repository_last_push**: 2026-10-09T09:44:09Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/C++.
- **input_shape**: N×44.
- **target_type**: monthly relevance grades.
- **group_support**: True.
- **PITQuant_compatibility**: TIER_A_DROP_IN_RANKER.
- **required_dataset_changes**: none.
- **estimated_engineering_effort**: LOW.
- **expected_scientific_value**: Final preregistered challenger only.
- **integration_status**: IMPLEMENTED_RESEARCH_ONLY.
- **recommended_trigger**: Current authorized final experiment.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": false, "supports_categorical": false, "supports_group_ranking": true, "supports_missing_native": true}`.

## LightGBM LambdaRank

- **algorithm_family**: LambdaRank.
- **official_repository**: https://github.com/lightgbm-org/LightGBM.
- **paper**: https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html.
- **license**: MIT.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/lightgbm-org/LightGBM/blob/main/LICENSE.
- **repository_last_push**: 2026-10-09T13:46:26Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/C++.
- **input_shape**: N×F.
- **target_type**: integer relevance.
- **group_support**: True.
- **PITQuant_compatibility**: TIER_A_DROP_IN_RANKER.
- **required_dataset_changes**: none; convert qid to group sizes.
- **estimated_engineering_effort**: LOW.
- **expected_scientific_value**: Potential alternative tree ranker, untested in PITQuant.
- **integration_status**: SPECIFICATION_ONLY.
- **recommended_trigger**: Separate human-reviewed preregistration.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": false, "supports_categorical": true, "supports_group_ranking": true, "supports_missing_native": true}`.

## CatBoost Ranker

- **algorithm_family**: YetiRank/YetiRankPairwise/PairLogit/QuerySoftMax.
- **official_repository**: https://github.com/catboost/catboost.
- **paper**: https://arxiv.org/abs/1706.09516.
- **license**: Apache-2.0.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/catboost/catboost/blob/master/LICENSE.
- **repository_last_push**: 2026-10-09T13:57:01Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/C++.
- **input_shape**: N×F.
- **target_type**: query relevance.
- **group_support**: True.
- **PITQuant_compatibility**: TIER_A_DROP_IN_RANKER.
- **required_dataset_changes**: group IDs; categorical contract only if later introduced.
- **estimated_engineering_effort**: MEDIUM.
- **expected_scientific_value**: Possible native categorical ranking after new information contract.
- **integration_status**: SPECIFICATION_ONLY.
- **recommended_trigger**: Human-reviewed experiment, not automatic.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": false, "supports_categorical": true, "supports_group_ranking": true, "supports_missing_native": true}`.

## DoubleEnsemble

- **algorithm_family**: ensemble/sample reweighting/feature selection.
- **official_repository**: https://github.com/microsoft/qlib.
- **paper**: https://arxiv.org/abs/2010.01265.
- **license**: MIT.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/microsoft/qlib/blob/main/LICENSE.
- **repository_last_push**: 2026-10-08T10:58:43Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/LightGBM.
- **input_shape**: N×F.
- **target_type**: tabular forecasting.
- **group_support**: False.
- **PITQuant_compatibility**: TIER_A_B_TABULAR_DRIFT_CHALLENGER.
- **required_dataset_changes**: new sample reweighting and feature-selection preregistration, no sequence required.
- **estimated_engineering_effort**: MEDIUM.
- **expected_scientific_value**: Tabular temporal drift hypothesis; no claimed performance.
- **integration_status**: SPECIFICATION_ONLY.
- **recommended_trigger**: Human review after temporal instability.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": false, "supports_categorical": false, "supports_group_ranking": false, "supports_missing_native": true}`.

Preserve MIT copyright/license notices if future reuse; no source copied now

## TRA

- **algorithm_family**: temporal routing and optimal transport.
- **official_repository**: https://github.com/microsoft/qlib.
- **paper**: https://arxiv.org/abs/2106.12950.
- **license**: MIT.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/microsoft/qlib/blob/main/LICENSE.
- **repository_last_push**: 2026-10-08T10:58:43Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/PyTorch.
- **input_shape**: N×T×F.
- **target_type**: sequence forecasting.
- **group_support**: False.
- **PITQuant_compatibility**: TIER_B_SEQUENCE_TEMPORAL_DRIFT.
- **required_dataset_changes**: new causal sequence dataset and routing contract.
- **estimated_engineering_effort**: HIGH.
- **expected_scientific_value**: Study multiple temporal patterns if F3 instability persists.
- **integration_status**: SPECIFICATION_ONLY.
- **recommended_trigger**: Temporal instability and approved sequence design.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": true, "supports_categorical": false, "supports_group_ranking": false, "supports_missing_native": false}`.

## MASTER

- **algorithm_family**: market-guided stock transformer.
- **official_repository**: https://github.com/SJTU-DMTai/MASTER.
- **paper**: https://arxiv.org/abs/2312.15235.
- **license**: MIT.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/SJTU-DMTai/MASTER/blob/master/LICENSE.
- **repository_last_push**: 2025-06-26T15:01:29Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/PyTorch.
- **input_shape**: N×T×F + market context.
- **target_type**: cross-sectional sequence forecasting.
- **group_support**: False.
- **PITQuant_compatibility**: TIER_B_SEQUENCE_CROSS_SECTIONAL_MARKET_MODEL.
- **required_dataset_changes**: sequence PIT guard, market context, new preprocessing.
- **estimated_engineering_effort**: HIGH.
- **expected_scientific_value**: Market/cross-stock/cross-time structure; needs new dataset.
- **integration_status**: SPECIFICATION_ONLY.
- **recommended_trigger**: New sequence and market-context contracts approved.

Capabilities: `{"requires_gpu": false, "requires_market_context": true, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": true, "supports_categorical": false, "supports_group_ranking": false, "supports_missing_native": false}`.

## StockMixer

- **algorithm_family**: indicator/temporal/stock mixing.
- **official_repository**: https://github.com/SJTU-DMTai/StockMixer.
- **paper**: https://github.com/SJTU-DMTai/StockMixer/blob/master/paper%2Bslide%2Bposter/StockMixer.pdf.
- **license**: UNRESOLVED.
- **license_confidence**: NO_CLEAR_LICENSE_FOUND_NOT_PERMISSION_TO_COPY.
- **license_source**: None.
- **repository_last_push**: 2024-03-19T11:48:43Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python 3.7 / PyTorch ~1.10 published.
- **input_shape**: N×T×F.
- **target_type**: sequence forecasting.
- **group_support**: False.
- **PITQuant_compatibility**: TIER_B_SEQUENCE_CROSS_SECTIONAL_MARKET_MODEL.
- **required_dataset_changes**: sequence PIT dataset and modernization; legal review.
- **estimated_engineering_effort**: HIGH.
- **expected_scientific_value**: Simple mixing architecture reference; no prediction claim.
- **integration_status**: REFERENCE_ONLY_LICENSE_UNRESOLVED.
- **recommended_trigger**: Clear license or independently reviewed clean reimplementation.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": false, "requires_sequence": true, "supports_categorical": false, "supports_group_ranking": false, "supports_missing_native": false}`.

## HIST

- **algorithm_family**: concept/graph shared information.
- **official_repository**: https://github.com/Wentao-Xu/HIST.
- **paper**: https://arxiv.org/abs/2110.13716.
- **license**: UNRESOLVED.
- **license_confidence**: NO_CLEAR_LICENSE_FOUND_NOT_PERMISSION_TO_COPY.
- **license_source**: None.
- **repository_last_push**: 2023-01-13T03:42:05Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/PyTorch/Qlib.
- **input_shape**: N×T×F + relation graph.
- **target_type**: stock trend.
- **group_support**: False.
- **PITQuant_compatibility**: TIER_C_RELATIONAL_DATA_REQUIRED.
- **required_dataset_changes**: PIT historical company-concept/relation graph missing.
- **estimated_engineering_effort**: VERY_HIGH.
- **expected_scientific_value**: Hypothesis for new relational information, not current drop-in.
- **integration_status**: REFERENCE_ONLY_LICENSE_UNRESOLVED.
- **recommended_trigger**: PIT graph contract and license clarification.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": true, "requires_sequence": true, "supports_categorical": false, "supports_group_ranking": false, "supports_missing_native": false}`.

## RSR

- **algorithm_family**: temporal relational stock ranking.
- **official_repository**: https://github.com/fulifeng/Temporal_Relational_Stock_Ranking.
- **paper**: https://arxiv.org/abs/1809.09441.
- **license**: AGPL-3.0.
- **license_confidence**: VERIFIED_UPSTREAM_LICENSE_API.
- **license_source**: https://github.com/fulifeng/Temporal_Relational_Stock_Ranking/blob/master/LICENSE.
- **repository_last_push**: 2021-03-04T16:41:52Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python 3.6 / TensorFlow 1.x published.
- **input_shape**: sequential EOD + industry/Wiki relations.
- **target_type**: stock ranking.
- **group_support**: True.
- **PITQuant_compatibility**: TIER_C_RELATIONAL_DATA_REQUIRED.
- **required_dataset_changes**: PIT graph, sequence data and complete modernization.
- **estimated_engineering_effort**: VERY_HIGH.
- **expected_scientific_value**: Conceptual relational ranking reference.
- **integration_status**: REFERENCE_ONLY_AGPL_RELATIONAL_MODEL.
- **recommended_trigger**: Explicit legal decision accepting AGPL obligations.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": false, "requires_relation_graph": true, "requires_sequence": true, "supports_categorical": false, "supports_group_ranking": true, "supports_missing_native": false}`.

Do not copy/integrate AGPL code absent explicit future legal decision

## DoubleAdapt

- **algorithm_family**: incremental/meta-learning drift adaptation.
- **official_repository**: https://github.com/SJTU-DMTai/DoubleAdapt.
- **paper**: https://arxiv.org/abs/2306.09862.
- **license**: UNRESOLVED.
- **license_confidence**: NO_CLEAR_LICENSE_FOUND_NOT_PERMISSION_TO_COPY.
- **license_source**: None.
- **repository_last_push**: 2024-12-25T09:06:01Z.
- **maintenance_status**: NOT_ARCHIVED; last push recorded, no promise of support.
- **language_framework**: Python/PyTorch/higher.
- **input_shape**: temporal batches + mature updates.
- **target_type**: forecasting, not drop-in monthly ranking.
- **group_support**: False.
- **PITQuant_compatibility**: LOW_PRIORITY_FOR_H12_CURRENT_DESIGN.
- **required_dataset_changes**: causal update/label maturity contract; H12 labels mature slowly.
- **estimated_engineering_effort**: HIGH.
- **expected_scientific_value**: Low priority with 12-month maturity; step/horizon mismatch.
- **integration_status**: REFERENCE_ONLY_LICENSE_UNRESOLVED.
- **recommended_trigger**: Only after approved realistic update/maturity design.

Capabilities: `{"requires_gpu": false, "requires_market_context": false, "requires_online_updates": true, "requires_relation_graph": false, "requires_sequence": true, "supports_categorical": false, "supports_group_ranking": false, "supports_missing_native": false}`.

Online update step must be considered relative to forecast horizon; recent H12 labels unavailable for twelve months. No online update implementation.

The adapter receives validated X/y/group and returns scores and provenance. It owns no PIT, cohort, target, preprocessing, evaluation or holdout rules. Native sequence models still need their own future input interface and versioned dataset; the tabular interface does not magically make them compatible. GPU is not an inherent mathematical requirement, but practical resource requirements must be audited in any future implementation. License absence is unresolved, not an open-source permission.
