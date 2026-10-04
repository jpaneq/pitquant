# BTC data readiness — observed 2026-10-04

Actual API/catalog calls and local archived rows, not promised supplier history. Times below are UTC period-end boundaries. Earliest usable HISTORICAL_OOS date: **NULL**. All five BTC_*D_HISTORY_READY gates and DERIVATIVES_HISTORY_READY are **false**. BTC_CORE_BASELINE_V0: BLOCKED_BY_DATA, trained=false, champion=NULL.

| Source | Metric | Frequency | Earliest archived | Latest archived | Distinct timestamps | First knowledge time | Completeness / PIT / license / status |
|---|---|---|---|---|---:|---|---|
| BINANCE_DERIVATIVES | basis | 1h | 2026-09-13 12:00:00.000000 | 2026-10-04 08:00:00.000000 | 501 | 2026-10-04 08:49:40.774944 | Limited latest window; incremental archive; historical PIT unproved; provider terms; AVAILABLE archived |
| BINANCE_DERIVATIVES | long_short_ratio | 1h | 2026-09-13 13:00:00.000000 | 2026-10-04 09:00:00.000000 | 501 | 2026-10-04 08:49:41.581714 | Limited latest window; incremental archive; historical PIT unproved; provider terms; AVAILABLE archived |
| BINANCE_DERIVATIVES | open_interest | 1h | 2026-09-13 13:00:00.000000 | 2026-10-04 09:00:00.000000 | 501 | 2026-10-04 08:49:40.324099 | Limited latest window; incremental archive; historical PIT unproved; provider terms; AVAILABLE archived |
| BINANCE_DERIVATIVES | taker_buy_sell_ratio | 1h | 2026-09-13 12:00:00.000000 | 2026-10-04 08:00:00.000000 | 501 | 2026-10-04 08:49:41.174146 | Limited latest window; incremental archive; historical PIT unproved; provider terms; AVAILABLE archived |
| BINANCE_FUNDING | funding_rate | funding schedule | 2019-09-10 08:00:00.000000 | 2026-10-04 08:00:00.001000 | 1500 | 2026-10-04 08:49:37.387258 | Sparse earliest/latest probes; middle not backfilled; historical PIT unproved; provider terms; AVAILABLE archived |
| BINANCE_SPOT | spot | 1D UTC | 2017-08-18 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 1999 | 2026-10-04 08:49:36.860863 | Sparse earliest/latest probes; middle not backfilled; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | MVRV | 1D UTC | 2010-07-19 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 5922 | 2026-10-04 08:55:36.416711 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | active_addresses | 1D UTC | 2009-01-04 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 6483 | 2026-10-04 08:55:26.417994 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | fees | 1D UTC | 2009-01-04 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 6483 | 2026-10-04 08:55:29.751085 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | hash_rate | 1D UTC | 2009-01-10 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 6477 | 2026-10-04 08:55:31.320053 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | market_cap | 1D UTC | 2010-07-19 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 5922 | 2026-10-04 08:55:34.841315 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | supply | 1D UTC | 2009-01-04 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 6483 | 2026-10-04 08:55:33.221582 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |
| COIN_METRICS | transaction_count | 1D UTC | 2009-01-04 00:00:00.000000 | 2026-10-04 00:00:00.000000 | 6483 | 2026-10-04 08:55:27.883646 | Observed values only; revisions/publication lag not historically established; historical PIT unproved; provider terms; AVAILABLE archived |

Current collection responses (incremental network responses are small windows, not full coverage):

- `spot`: AVAILABLE, N=999; actual API access confirmed; raw SHA `be8e898f9117ca63ec9d82691b3146091e914ca38d14e5c404acb12e8bd79dcd`.
- `funding`: AVAILABLE, N=500; actual API access confirmed; raw SHA `3b4aa25e3dc0fdcf7a32463cc771058c06e0adece9f99cb95d5a722f509126a6`.
- `open_interest`: AVAILABLE, N=500; actual API access confirmed; raw SHA `08022dd57776066f7e205594b51e04d3378bc9a8a2c679e77bfe70bedb1d4e8f`.
- `basis`: AVAILABLE, N=500; actual API access confirmed; raw SHA `71c679fe9d9200c01b2197cc23f623c2ffd3da8c32ceaa66df29f10cb2195579`.
- `taker_buy_sell_ratio`: AVAILABLE, N=500; actual API access confirmed; raw SHA `acb1ad3c90d442e4f69ded0dad9c660fffb5ee153cf8185e662032c5982a83ab`.
- `long_short_ratio`: AVAILABLE, N=500; actual API access confirmed; raw SHA `8a7e7c66e2472e2201cf4ff37f22332b0563f7757c1ad5ced2196684b1f1adbe`.
- `catalog`: AVAILABLE, N=1235; actual API access confirmed; raw SHA `a1121f67742093ae20e2c39cd13460e0a0fbf0f8d8a35a0e396fdb96633658b8`.
- `active_addresses`: AVAILABLE, N=3; actual API access confirmed; raw SHA `e168defdba1b0ab6bf24c4ef59d4586da0ada813635efbeeccd36442d3ffb9f6`.
- `transaction_count`: AVAILABLE, N=3; actual API access confirmed; raw SHA `fb8d2f78e9c695059ab9d4b3ac98629f505f0df4c63e1535056d5ae6aa14ec3c`.
- `transaction_volume`: UNAVAILABLE, N=0; HTTP Error 403: Forbidden; raw SHA `no successful payload`.
- `fees`: AVAILABLE, N=3; actual API access confirmed; raw SHA `de5d67623a6359513277df1a74e9fb3f9e02887f5ef09dd7caa1195073a6f308`.
- `hash_rate`: AVAILABLE, N=3; actual API access confirmed; raw SHA `401380e98c0c366436e6badbd18bc65983e7609fd99ebb06666e0aae35e8c8e5`.
- `difficulty`: UNAVAILABLE, N=0; HTTP Error 403: Forbidden; raw SHA `no successful payload`.
- `supply`: AVAILABLE, N=3; actual API access confirmed; raw SHA `d0933b059a1ec602c7b1538714cdb36218f166b75ab6d5bbf9aee78ff78b7ec0`.
- `market_cap`: AVAILABLE, N=3; actual API access confirmed; raw SHA `61046ab8b591d1c54efe6ff5eb341f1b6c019419adacd2cae7bed62a9c304b10`.
- `realized_cap`: UNAVAILABLE, N=0; HTTP Error 403: Forbidden; raw SHA `no successful payload`.
- `MVRV`: AVAILABLE, N=3; actual API access confirmed; raw SHA `fb1b863e5b6d009d0b32c39ea6fc9fc09f50489999ae306325e454588f22fc05`.

Price probes cover 2017-08-18→2020-05-13 and 2024-01-10→2026-10-04, with a large middle gap. Funding earliest probe actually returned 2019-09-10→2020-08-08; latest returned 2026-04-21 onward. No assertion of complete funding backfill. Coin Metrics metrics reported by API use period-start; storage shifts to next-day period-end. Hash-rate begins later than other genesis series because early values are null.

Exact training blocker: NO_SUFFICIENT_HISTORICAL_PIT_SNAPSHOTS_BEFORE_FROZEN_HOLDOUT. There are zero audited usable historical frozen snapshots. Even complete present-day OHLC backfill would not establish original availability/revision vintages. Optional derivatives remain limited; no imputation before archiving. Scikit-learn is an optional ML dependency; the local shared dev environment has no ML extra installed. No baseline OOS results exist.

Sources and access terms: [Binance market-data-only](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only), [Binance futures market data and retention](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data), [Coin Metrics API](https://docs.coinmetrics.io/api), [Coin Metrics Community](https://community-api.coinmetrics.io/v4/catalog-all/asset-metrics). Public/no-key access is not a redistribution license. Dataset licenses are not verified for redistribution; local research archive only. Binance documents 30-day retention for OI and several statistics; the observed 500-hour request is shorter than the maximum retention.

Raw payloads/hashes are in local RawSourceArchive + data/archive; value revisions and availability times are append-only. Back up both local data/btc.db and originals; Git contains code/docs/fixtures/screenshots, not a substitute for the real evidence archive.

## Follow-up experimental price baseline

The middle price gap was subsequently backfilled from official archived calls. Current observed frame has3335daily boundaries,2017-08-18→2026-10-04, with one missing boundary2018-02-09 preserved. An independent BTC virtualenv now has scikit-learn. Five **retrospective price-only** experimental models were fit without training/evaluating the2025-10-01 onward holdout. This does not change historical PIT gates. See [BTC_EXPERIMENTAL_PREDICTOR.md](BTC_EXPERIMENTAL_PREDICTOR.md) for exact results and limitations; the initial inventory above is the initial-delivery snapshot.
