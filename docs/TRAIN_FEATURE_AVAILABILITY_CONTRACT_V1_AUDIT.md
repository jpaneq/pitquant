# TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1

Frozen outcome-free eligibility: every retained feature must have at least one finite observed value in every required inner and outer TRAIN. No other percentage threshold. Same RAW list for XGB and M4R; no row removals.

Audit SHA256: `56466920db9a7a77479d081afa7d3a60f5792767933814dbd70c5d1e145440b8`.

44 features × 12 blocks = 528 cells. Full per-block counts/reasons are in the adjacent JSON.

| Feature | Minimum finite N across blocks | Minimum coverage | Violating blocks | Decision |
|---|---:|---:|---|---|
| ret_1m | 2877 | 100.00% | none | RETAIN |
| ret_3m | 2877 | 100.00% | none | RETAIN |
| ret_6m | 2877 | 100.00% | none | RETAIN |
| ret_12m | 2877 | 100.00% | none | RETAIN |
| momentum_12_1 | 2877 | 100.00% | none | RETAIN |
| distance_sma20 | 2877 | 100.00% | none | RETAIN |
| distance_sma50 | 2877 | 100.00% | none | RETAIN |
| distance_sma200 | 2877 | 100.00% | none | RETAIN |
| sma50_vs_sma200 | 2877 | 100.00% | none | RETAIN |
| distance_52w_high | 2877 | 100.00% | none | RETAIN |
| drawdown_from_52w_high | 2877 | 100.00% | none | RETAIN |
| realized_vol_20 | 2877 | 100.00% | none | RETAIN |
| realized_vol_63 | 2877 | 100.00% | none | RETAIN |
| realized_vol_126 | 2877 | 100.00% | none | RETAIN |
| atr14_pct | 2877 | 100.00% | none | RETAIN |
| downside_vol_63 | 2877 | 100.00% | none | RETAIN |
| volume_zscore_20 | 2266 | 78.76% | none | RETAIN |
| rsi14 | 2877 | 100.00% | none | RETAIN |
| fund_gross_margin | 1471 | 50.91% | none | RETAIN |
| fund_operating_margin | 2422 | 84.18% | none | RETAIN |
| fund_net_margin | 2877 | 100.00% | none | RETAIN |
| fund_roa | 2874 | 99.90% | none | RETAIN |
| fund_roe | 2632 | 90.36% | none | RETAIN |
| fund_fcf_margin | 2103 | 72.56% | none | RETAIN |
| fund_cfo_to_net_income | 2598 | 86.95% | none | RETAIN |
| fund_accruals_to_assets | 2725 | 93.33% | none | RETAIN |
| fund_revenue_yoy | 2877 | 100.00% | none | RETAIN |
| fund_net_income_yoy | 2759 | 93.32% | none | RETAIN |
| fund_debt_to_assets | 2877 | 100.00% | none | RETAIN |
| fund_current_ratio | 2877 | 99.94% | none | RETAIN |
| fund_shareholder_yield | 2217 | 76.65% | none | RETAIN |
| val_pe | 2581 | 87.41% | none | RETAIN |
| val_price_to_sales | 2704 | 93.51% | none | RETAIN |
| val_price_to_book | 2475 | 83.56% | none | RETAIN |
| val_fcf_yield | 1966 | 67.29% | none | RETAIN |
| val_pe_own_pct | 0 | 0.00% | F1/INNER_0_TRAIN, F2/INNER_0_TRAIN, F2/INNER_1_TRAIN, F3/INNER_0_TRAIN, F3/INNER_1_TRAIN | REMOVE |
| risk_alert_h6 | 2877 | 100.00% | none | RETAIN |
| risk_alert_h12 | 2877 | 100.00% | none | RETAIN |
| rc_below_sma200 | 2877 | 100.00% | none | RETAIN |
| rc_momentum_negative | 2877 | 100.00% | none | RETAIN |
| rc_support_broken | 2788 | 96.91% | none | RETAIN |
| rc_elevated_volatility | 2877 | 100.00% | none | RETAIN |
| rc_drawdown_state | 2877 | 100.00% | none | RETAIN |
| support_distance_atr | 2788 | 96.91% | none | RETAIN |

Only `val_pe_own_pct` is structurally unavailable in required early TRAIN windows. The frozen engine is unchanged. First valid scientific percentile: 2016-09. The projected 43-feature contract passes 516 block-feature cells.

The first V0R1 real fit was subsequently invalidated by undefined inner IC; this availability audit is not evidence of model performance. See the immutable V0R1 report.
