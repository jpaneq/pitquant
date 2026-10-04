# BTC experimental predictor and live operation tracking

Follow-up explicitly requested by the user after the initial BTC V0 delivery: create an actual experimental predictor, show it beside current quotes, test old prices and record the forecast when launching a paper operation.

The original historical PIT gates remain false. This new price-only retrospective experiment is explicitly **RETROSPECTIVE_NOT_HISTORICAL_PIT** and **EXPERIMENTAL_NOT_VALIDATED**; no champion, no automatic prediction trade, no recalibration based on the observed score.

## Model and data

Version btc-elastic-logistic-experimental-v1, feature version btc-price-experimental-v1. Shared baseline pipelines: training-only SimpleImputer/StandardScaler, ElasticNet alpha .01/l1ratio .5, LogisticRegression seed0/maxiter2000. Separate models for 7/30/90/180/365D. Frozen research windows train1095/validation180/embargo7. Holdout starts2025-10-01: training/validation labels were computed only from prices strictly before that date. Final training labels end2025-09-30.

Price-only features: log returns1/3/7/14/30/90/180/365, SMA20/50/200 distances, realized volatility7/30/90, ATR14/price, volumez30. Feature vectors are tested against future-candle changes. No network/derivative historical revision assumptions enter this experimental fit. Quantiles stay NULL. The exp-transformed log forecast is a point forecast, not a calibrated distributional mean. P(up) is uncalibrated model output, not proven confidence.

Official Binance backfill fills the previously large middle gap, retaining original hashes/retrieval times. Observed frame:3335 daily boundaries from2017-08-18 through2026-10-04; one missing boundary2018-02-09 remains after an individual official API probe. Missing OHLC are not filled. A complete one-year input window is required; calendar gaps remain excluded from training eligibility. Download time does not establish historical PIT availability.

Model coefficients, imputer/scaler parameters, feature names, protocol hash, data hash, OOS predictions and their hashes are appended to BTCResearchRecord. A model protocol is persisted before fitting, and each OOS prediction batch is committed before its outcomes are recorded. The latest protocol additionally records the implementation hash. Inputs to historical metrics are never the reserved holdout.

## Retrospective observations

These are temporal validation results on today's archived price vintage. They are not validated PIT results, not holdout results and not an investable portfolio. Compare against the trivial always-UP baseline; long horizons overlap strongly.

| Horizon | Raw N | Nonoverlap cohorts reported | Direction hits | Always UP | Mean absolute return error |
|---|---:|---:|---:|---:|---:|
| 7D | 1080 | 156 | 51.57% | 51.85% | 5.36 percentage points |
| 30D | 900 | 30 | 47.89% | 57.67% | 15.82 percentage points |
| 90D | 720 | 8 | 50.69% | 53.33% | 39.51 percentage points |
| 180D | 360 | 2 | 72.78% | 97.78% | 79.70 percentage points |
| 365D | 180 | 1 | 100.00% | 100.00% | 46.87 percentage points |

There is **no demonstrated consistent directional advantage** over always-UP. The365D100% score matches always-UP in just one nonoverlap cohort. Do not interpret raw sample counts or large forward probabilities as established precision. Model parameters were not changed to improve these scores.

## Forward and operations

POST /btc/experimental/forecast freezes one versioned forecast per UTC day. Its input/reference price is the last completed daily close; generated_at records when it was actually made. Manual daytime generation is marked MANUAL_FORWARD_1D with the real knowledge cutoff, never represented as knowledge available at midnight. This is a separate feature version; the canonical strict daily snapshot path is unchanged. Current live BTCUSDT quote is display-only and updates every5seconds.

The UI shows five cards with uncalibrated P(up), point return/price target, base price, generation time, target date and model version. Historical tests show saved retrospective predictions beside actual returns/errors and the always-UP comparison.

Launching a paper operation selects notional and horizon, pins the selected prediction ID/hash/payload/model and the original ATR plan into the immutable Simulation source_provenance. A reload can recover the operation from BTC Simulations. Actual fills use the existing conservative daily engine, from the next UTC session for intraday creation; live quote alone does not prove TP/stop order.

Operations track separately: (1) plan state/TP1/TP2, (2) forecast expected vs actual at its full horizon, error and single-case directional hit. A trade can close before forecast maturity; forecast outcome remains pending. Mature outcomes are appended only when the exact target daily price is available, even if the trade closed earlier. Missing target stays pending. Revisions do not edit the original forecast or first recorded outcome. The daily forward archiver generates experimental forecasts once models exist and updates these assessments; it never opens an automatic trade.

## Reproduction

The independent .btc-venv installs the existing project dev dependencies plus scikit-learn; the shared equity virtualenv was not modified. Run:

```sh
PITQUANT_DATABASE_URL=sqlite:///data/btc.db .btc-venv/bin/python scripts/btc_experiment.py
```

Web inference uses serialized JSON model parameters and NumPy; no ML training occurs on a quote refresh or when launching an operation. Real model records and raw evidence are in the independent local BTC DB/archive and must be backed up together. Core readiness remains BLOCKED_BY_DATA for proven historical PIT research.
