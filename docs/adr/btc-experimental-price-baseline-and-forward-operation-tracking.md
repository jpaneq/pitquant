# Experimental BTC price baseline and immutable forward-operation tracking

Accepted2026-10-04 on feature/btc-engine-v0 after explicit user steering to create a predictor and try it on old/current prices.

Use separate btc-price-experimental-v1/RETROSPECTIVE records to test a price-only baseline with downloaded official candles. Do not silently call this historical PIT, alter core gates or unseal the predeclared2025-10-01 holdout. Shared baseline pipelines and Simulation Lab are reused. Forward forecasts contain actual generated_at and knowledge cutoff, model parameters/hash and daily reference close. Manual daytime forecasts are distinguished from canonical close-time knowledge.

The prediction is pinned to a paper operation at creation. Plan targets and model forecasts are evaluated independently; early trade closure cannot manufacture a matured horizon outcome. Quote display is ephemeral, refreshes every5seconds, and never changes frozen forecasts, fills or labels. No broker/trading credentials or automatic real orders.

Initial retrospective models do not demonstrate an edge over always-UP. Remain experimental. Future changes require versioned challengers and new documented research configuration rather than tuning the frozen baseline after individual results.
