# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1

Status: PREREGISTERED_NOT_RUN; frozen before the first real fit.

Supersedes V0, aborted before fitting for TRAIN feature availability. The original artifacts are immutable. This revision uses TRAIN availability only.

Dataset unchanged: `e90b817ab038735d1c5aa0f096384cb80337b75589dabf0731e49b39a9b7af39`.

Manifest: `d6a7a51eb448a346647a79396256ce4362324330630931efc9b9031c61220996`.

Feature contract: `4803e4d52b320a4f24771e92df1586a57af5d4fcccabd6f2cfbe721e4d1855e7`.

Removed: `['val_pe_own_pct']`. Added: nothing. RAW count: 43.

Eligibility requires at least one finite value in every required inner and outer TRAIN. No other coverage threshold. Partial missingness retains original processing.

XGB and M4R use identical RAW features and issuer-month rows. M4R has one TRAIN-derived missingness indicator per retained feature.

Dataset, targets, cohorts, 1/3/5 inner geometry, outer folds, purge and embargo are unchanged. XGBoost 3.1.3 parameters, eight candidates, selection, metrics, sector N>=10, bootstrap 1000/PCG64/20261009, classification and holdout rules are copied exactly from V0 and its implementation completion; see the full manifest.

Current adaptive iteration is 2; first real fit increments it to 3. No other challenger, holdout or OOT is authorized.
