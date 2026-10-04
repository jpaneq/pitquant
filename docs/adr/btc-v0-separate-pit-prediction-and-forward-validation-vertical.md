# BTC Engine as separate PIT prediction and forward-validation vertical

Status: accepted on feature/btc-engine-v0, 2026-10-04. Source f212b3d.

Separate UTC 24/7 data/feature/prediction contracts preserve equity semantics while reusing event sourcing, observations, outcome storage, hypotheses, pinning and replay. Binance public BTCUSDT and discovered Coin Metrics Community metrics provide the first archives. Observation/retrieval time controls knowledge; downloaded historical dates are not historical PIT proof. Four append-only BTC tables preserve provenance and versioned predictions.

The historical holdout 2025-10-01–2026-09-30 was pinned before real training. Historical gates are blocked. A new research protocol/holdout requires a separately versioned challenger rather than editing the pinned configuration. Forward activation is separate from that holdout. No signal/probability/quantile or champion is manufactured to make a UI look complete.

Unique migration IDs btc_v0_20261004 and btc_v0_20261004_r1. MUST_REBASE_MIGRATIONS_BEFORE_MERGE. No merge authorized. A reverting source value is a new vintage, while identical latest values are idempotent. Daily decision uniqueness prevents two competing frozen snapshots for the same cohort/version.

Consequences: the interface can freeze/reveal and paper-test rule plans now. Scientific training must wait for demonstrated PIT history. Public API access does not imply redistribution rights; archive locally and consult provider terms. Realized cap/transaction volume/difficulty inaccessible responses remain explicit. Automatic collection depends on local app uptime. The initial source backfill is sparse for price/funding and cannot prove ATH or OOS readiness.
