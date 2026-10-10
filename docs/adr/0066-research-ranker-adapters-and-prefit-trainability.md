# ADR-0066: Narrow research ranker adapters and pre-fit trainability

Status: accepted implementation; frozen real experiment blocked before fitting.

Starting at 8b7f258, install/pin XGBoost 3.1.3 as an optional research dependency (and a development dependency so mandatory synthetic PIT tests never skip). The macOS binary also needs OpenMP; its runtime version and native hashes are recorded. Do not vendor model sources or import Qlib into core.

CrossSectionalRankerAdapter owns only fit, score prediction, native serialization/reload, metadata and capabilities. PITQuant keeps ownership of PIT data, security master, cohorts, labels, preprocessing, temporal folds, metrics and sealed periods. XGBRankerAdapter is executable; every other model remains a dependency-free specification or reference. The registry records upstream license evidence, requirements, tiers and future human-reviewed triggers. No future adapter accesses real outcomes.

Implementation defaults and synthetic deterministic smoke are frozen before real fitting. Existing dataset/preregistration and protected model artifacts remain unchanged. Reconstructed inputs preserve all 16,717 scientific rows and the maximum target end precedes holdout.

A missing condition in the earlier row-wise freeze is now checked: every inner TRAIN must obey the frozen model's all-missing-column policy. val_pe_own_pct is absent throughout five of nine inner blocks. The native-missing tree could technically ignore such a column, but the frozen rule explicitly forbids it. No real fitting may begin; all inner blocks are audited first. No feature removal, zero imputation, warm-up rebuilding or fold alteration is permitted in this version.

Reports are immutable preflight-abort records, not negative performance findings. No classification, valid real replay or holdout consideration is possible; iteration remains 2, final experiment not completed, sealed outcome access 0. A future preprocessing amendment needs explicit human review and a new experiment preregistration; changing feature history additionally requires a new dataset version. No automatic model search.
