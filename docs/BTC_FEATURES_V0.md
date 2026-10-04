# BTC features V0

Version `btc-core-v0`. Transparent families; no combined opaque score. Every missing value is NULL plus availability/reason. Model imputation is fit on training rows only.

| Family | Definitions |
|---|---|
| Price/momentum | price; log(close / close lag 1/3/7/14/30/90/180/365 calendar days) |
| Trend | distance SMA20/50/200; SMA20/SMA50 and SMA50/SMA200 minus one; EMA20/50 |
| High/drawdown | distances to 30/90/365 day high; 30/90 day drawdown; observed-history drawdown separate from true ATH |
| Volatility | log-return sample SD × sqrt(365) over 7/30/90 days; ATR14 = mean of last 14 true ranges; pandas skew/kurtosis over 30 days |
| Volume | change 1/7 days and 30-day z score |
| Derivatives | current funding, mean3/7 days, z30; OI and change1/7/30; premium/basis/annualized basis; taker ratio and long/short ratio |
| States | four price/OI sign combinations; funding positive/negative extreme at abs(z) >= 2; context only |
| Network | active addresses, transaction count, fees, hash rate, supply, market cap, MVRV where fetched successfully |
| Regime | SMA50 versus SMA200 context; no automatic BUY/SELL |

Windows require consecutive daily bars; sparse earliest/latest probes do not count as continuous history. True ATH remains NULL because full price coverage is not verified. Funding and derivatives freshness is bounded; network daily timestamps represent period end, not period start. Coin Metrics units stay metric-native: market cap is USD; prices are USDT. Transaction transfer volume would be native BTC, not an entity-adjusted exchange flow.

Availability enum: AVAILABLE / UNAVAILABLE / NOT_ENOUGH_HISTORY / SOURCE_RETENTION_LIMIT. Public Community catalog advertisement alone is insufficient: actual HTTP access is checked. Transaction volume, difficulty and realized cap currently return 403.

BTC_CORE_V0 supports price, momentum, trend, volatility, volume and accessible network features. Funding is optional pending sufficient continuous PIT coverage. BTC_DERIVATIVES_V0 is the optional OI/basis/taker/long-short block; it does not truncate core history. Future ablations must compare identical OOS dates and frozen versions; no derivative challenger or scientific ablation is claimed in this V0.

Support/resistance reuses confirmed-pivot pure computation with UTC daily BTC bars. Trade plan is a separate rule contract: long MARKET, stop 2×ATR, TP1 +2×ATR, TP2 +4×ATR, 50% at TP1, with confirmed zones shown as context. RULE_BASED / NOT_YET_BACKTEST_VALIDATED. P(up) is never used. Execution and same-bar ambiguity follow the conservatively tested engine.
