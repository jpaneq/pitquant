# RUN 3 — Features continuas PIT, fundamentales y efectividad (informe generado)

Generado desde la base el 2026-10-04T18:28:22Z · segmento **DEV** (decisiones ≤ 2022-09-30) · 13,348 filas · 96 valores · 140 meses. El holdout oct-2022→sep-2025 no se ha leído: sus decisiones no se generan y los objetivos que lo tocan son `UNAVAILABLE`. Todo es **descriptivo**: no se entrena ni se seleccionan pesos.

> Limitaciones que se aplican a TODO lo que sigue: universo = conjunto de investigación ACTUAL (sesgo de supervivencia, no es membresía de índice), benchmarks son proxies (SPY ETF; ^IBEX índice de precio sin dividendos; URTH ETF USD con desajuste de divisa en no-USD), fundamentales sólo EE. UU. y sectores soportados.

## 1. Cobertura de features / 2. Missingness

83 features analizadas (47 técnicas/soporte/riesgo, 36 fundamentales/valoración). Missing nunca se rellena con 0; las razones por feature están en cada snapshot.

| feature | N | missing % | media | std | P10 | P50 | P90 |
|---|---|---|---|---|---|---|---|
| fund_net_equity_issuance | 1398 | 89.527 | -1586328660.229 | 10517623102.569 | -8961000000.000 | -1187000000.000 | 999000000.000 |
| fund_gross_profitability | 1908 | 85.706 | 0.359 | 0.177 | 0.143 | 0.351 | 0.602 |
| fund_gross_margin | 1939 | 85.473 | 0.458 | 0.237 | 0.134 | 0.484 | 0.795 |
| fund_dividends_to_fcf | 2602 | 80.506 | 0.457 | 0.523 | 0.126 | 0.380 | 0.711 |
| val_fcf_yield_own_pct | 2655 | 80.109 | 39.097 | 32.457 | 0.000 | 32.653 | 90.000 |
| val_ev_to_operating_income | 3175 | 76.214 | 65.109 | 589.501 | 11.282 | 17.473 | 60.390 |
| val_fcf_yield | 3343 | 74.955 | 21.837 | 631.088 | 0.010 | 0.046 | 0.084 |
| fund_fcf_yoy | 3404 | 74.498 | 0.128 | 1.529 | -0.245 | 0.092 | 0.580 |
| val_price_to_book_own_pct | 3648 | 72.670 | 69.566 | 32.058 | 13.333 | 81.667 | 100.000 |
| val_pe_own_pct | 3735 | 72.018 | 63.154 | 32.041 | 10.000 | 72.500 | 100.000 |
| fund_fcf_margin | 3850 | 71.157 | 0.157 | 0.215 | 0.018 | 0.147 | 0.368 |
| fund_capex_growth_yoy | 4029 | 69.816 | 0.139 | 0.403 | -0.173 | 0.046 | 0.515 |
| fund_interest_coverage | 4057 | 69.606 | 73.648 | 376.469 | 4.735 | 13.814 | 128.410 |
| fund_capex_to_assets | 4058 | 69.598 | 0.037 | 0.037 | 0.009 | 0.024 | 0.080 |
| val_ev_to_sales | 4159 | 68.842 | 4.646 | 4.213 | 1.090 | 3.631 | 9.302 |
| fund_debt_to_equity | 4183 | 68.662 | 1.623 | 6.161 | 0.072 | 0.599 | 2.889 |
| val_price_to_sales_own_pct | 4232 | 68.295 | 73.912 | 29.399 | 21.667 | 86.667 | 100.000 |
| fund_shareholder_yield | 4420 | 66.886 | 0.064 | 0.087 | 0.016 | 0.054 | 0.109 |
| val_price_to_book | 4536 | 66.017 | 2348.245 | 90297.491 | 2.241 | 5.769 | 26.089 |
| fund_operating_income_yoy | 4587 | 65.635 | 0.270 | 1.268 | -0.246 | 0.091 | 0.690 |
| val_pe | 4717 | 64.661 | 9605.765 | 377074.919 | 13.810 | 21.966 | 75.283 |
| fund_buyback_yield | 4792 | 64.099 | 0.025 | 0.044 | 0.000 | 0.021 | 0.065 |
| fund_roe | 4814 | 63.935 | 1.315 | 21.719 | 0.046 | 0.235 | 0.986 |
| fund_debt_to_assets | 4825 | 63.852 | 0.236 | 0.148 | 0.052 | 0.216 | 0.431 |
| fund_operating_margin | 4928 | 63.081 | 0.203 | 0.194 | 0.033 | 0.166 | 0.416 |
| val_earnings_yield | 5063 | 62.069 | 1.989 | 69.469 | 0.004 | 0.044 | 0.071 |
| fund_net_income_yoy | 5091 | 61.859 | 1.201 | 33.119 | -0.487 | 0.095 | 1.004 |
| fund_cfo_to_net_income | 5216 | 60.923 | 2.483 | 9.760 | 0.993 | 1.477 | 3.102 |
| val_price_to_sales | 5216 | 60.923 | 2377.558 | 98805.290 | 0.983 | 3.194 | 8.432 |
| fund_accruals_to_assets | 5269 | 60.526 | -0.052 | 0.054 | -0.125 | -0.047 | 0.001 |
| fund_roa | 5506 | 58.750 | 0.090 | 0.075 | 0.017 | 0.084 | 0.182 |
| fund_dividend_yield | 5518 | 58.660 | 0.034 | 0.066 | 0.005 | 0.023 | 0.048 |
| fund_revenue_yoy | 5692 | 57.357 | 0.136 | 0.607 | -0.039 | 0.062 | 0.316 |
| fund_net_margin | 5718 | 57.162 | 0.138 | 0.161 | 0.020 | 0.113 | 0.300 |
| fund_cash_to_assets | 5963 | 55.327 | 0.112 | 0.086 | 0.026 | 0.092 | 0.216 |
| fund_current_ratio | 6017 | 54.922 | 1.868 | 1.613 | 0.864 | 1.356 | 3.410 |
| volume_change_63 | 9428 | 29.368 | 0.038 | 0.385 | -0.268 | -0.025 | 0.390 |
| volume_zscore_63 | 9672 | 27.540 | 0.301 | 1.143 | -0.779 | 0.049 | 1.693 |
| volume_change_20 | 9757 | 26.903 | 0.049 | 0.390 | -0.297 | -0.014 | 0.434 |
| volume_zscore_20 | 9869 | 26.064 | 0.401 | 1.163 | -0.834 | 0.136 | 2.131 |
| rc_drawdown_state | 11741 | 12.039 | 0.200 | 0.400 | 0.000 | 0.000 | 1.000 |
| ret_12m | 11741 | 12.039 | 0.193 | 0.375 | -0.122 | 0.159 | 0.496 |
| drawdown_from_52w_high | 11741 | 12.039 | -0.094 | 0.104 | -0.226 | -0.063 | -0.004 |
| momentum_12_1 | 11741 | 12.039 | 0.177 | 0.346 | -0.122 | 0.146 | 0.464 |
| rc_elevated_volatility | 12103 | 9.327 | 0.118 | 0.323 | 0.000 | 0.000 | 1.000 |
| atr14_normalized | 12189 | 8.683 | 1.067 | 0.330 | 0.759 | 0.998 | 1.436 |
| distance_52w_high | 12273 | 8.054 | -0.104 | 0.108 | -0.243 | -0.072 | -0.006 |
| sma200_slope | 12386 | 7.207 | 0.009 | 0.023 | -0.015 | 0.009 | 0.032 |
| risk_alert_h3 | 12482 | 6.488 | 0.177 | 0.382 | 0.000 | 0.000 | 1.000 |
| risk_alert_h6 | 12482 | 6.488 | 0.258 | 0.438 | 0.000 | 0.000 | 1.000 |
| risk_alert_h12 | 12482 | 6.488 | 0.260 | 0.439 | 0.000 | 0.000 | 1.000 |
| risk_alert_h24 | 12482 | 6.488 | 0.260 | 0.439 | 0.000 | 0.000 | 1.000 |
| rc_below_sma200 | 12482 | 6.488 | 0.324 | 0.468 | 0.000 | 0.000 | 1.000 |
| risk_alert_h1 | 12482 | 6.488 | 0.177 | 0.382 | 0.000 | 0.000 | 1.000 |
| distance_sma200 | 12482 | 6.488 | 0.046 | 0.134 | -0.097 | 0.045 | 0.183 |
| sma50_vs_sma200 | 12482 | 6.488 | 0.033 | 0.099 | -0.074 | 0.035 | 0.136 |
| drawdown_from_26w_high | 12536 | 6.083 | -0.080 | 0.087 | -0.187 | -0.055 | -0.003 |
| realized_vol_126 | 12536 | 6.083 | 0.258 | 0.119 | 0.146 | 0.228 | 0.413 |
| rc_momentum_negative | 12536 | 6.083 | 0.308 | 0.462 | 0.000 | 0.000 | 1.000 |
| ret_6m | 12536 | 6.083 | 0.085 | 0.207 | -0.121 | 0.073 | 0.288 |
| distance_26w_high | 12795 | 4.143 | -0.086 | 0.089 | -0.198 | -0.060 | -0.004 |
| realized_vol_63 | 12941 | 3.049 | 0.253 | 0.129 | 0.137 | 0.221 | 0.405 |
| ret_3m | 12941 | 3.049 | 0.040 | 0.132 | -0.103 | 0.037 | 0.180 |
| return_skew_63 | 12941 | 3.049 | -0.061 | 0.953 | -0.997 | -0.055 | 0.860 |
| return_kurtosis_63 | 12941 | 3.049 | 2.419 | 4.167 | -0.159 | 1.102 | 5.955 |
| downside_vol_63 | 12941 | 3.049 | 0.174 | 0.099 | 0.086 | 0.149 | 0.285 |
| sma50_slope | 13060 | 2.158 | 0.009 | 0.043 | -0.039 | 0.010 | 0.054 |
| support_touches | 13114 | 1.753 | 2.334 | 1.823 | 1.000 | 2.000 | 5.000 |
| rc_support_broken | 13114 | 1.753 | 0.079 | 0.270 | 0.000 | 0.000 | 0.000 |
| support_age_bars | 13114 | 1.753 | 76.016 | 100.530 | 8.000 | 32.000 | 217.000 |
| support_distance_atr | 13114 | 1.753 | 2.030 | 2.000 | 0.121 | 1.575 | 4.562 |
| support_distance_pct | 13114 | 1.753 | 0.104 | 9.185 | 0.002 | 0.032 | 0.104 |
| support_broken | 13114 | 1.753 | 0.079 | 0.270 | 0.000 | 0.000 | 0.000 |
| distance_sma50 | 13156 | 1.438 | 0.010 | 0.063 | -0.061 | 0.012 | 0.078 |
| sma20_vs_sma50 | 13156 | 1.438 | 0.006 | 0.041 | -0.039 | 0.008 | 0.049 |
| ema50_distance | 13156 | 1.438 | 0.009 | 0.054 | -0.052 | 0.011 | 0.066 |
| sma20_slope | 13189 | 1.191 | 0.010 | 0.061 | -0.057 | 0.010 | 0.075 |
| ret_1m | 13205 | 1.071 | 0.013 | 0.075 | -0.071 | 0.012 | 0.093 |
| realized_vol_20 | 13205 | 1.071 | 0.245 | 0.147 | 0.119 | 0.210 | 0.401 |
| distance_sma20 | 13338 | 0.075 | 0.004 | 0.039 | -0.041 | 0.005 | 0.046 |
| ema20_distance | 13338 | 0.075 | 0.003 | 0.033 | -0.035 | 0.005 | 0.039 |
| rsi14 | 13346 | 0.015 | 52.294 | 11.611 | 37.184 | 52.439 | 67.111 |
| atr14_pct | 13346 | 0.015 | 0.022 | 0.011 | 0.013 | 0.019 | 0.034 |

## 3. IC raw (retorno total futuro)

### Horizonte 6M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.122 | -2.026 | 18.526 | 61.048 | DATA_QUALITY_LIMITED |
| fund_shareholder_yield | 0.121 | 3.114 | 31.571 | 33.832 | WEAK |
| fund_fcf_yoy | 0.112 | 2.037 | 23.925 | 49.042 | WEAK |
| fund_revenue_yoy | 0.104 | 1.856 | 40.373 | 14.790 | WEAK |
| val_pe | 0.101 | 1.845 | 33.455 | 29.386 | WEAK |
| fund_accruals_to_assets | -0.100 | -2.775 | 37.306 | 21.123 | PROMISING |
| realized_vol_126 | 0.095 | 1.816 | 92.023 | 6.083 | WEAK |
| val_fcf_yield_own_pct | 0.094 | 2.014 | 22.664 | 60.254 | DATA_QUALITY_LIMITED |
| fund_debt_to_assets | -0.090 | -2.503 | 34.149 | 27.769 | UNSTABLE |
| fund_debt_to_equity | -0.090 | -2.104 | 29.910 | 37.380 | UNSTABLE |
| val_earnings_yield | -0.086 | -1.558 | 35.948 | 24.207 | WEAK |
| fund_cfo_to_net_income | 0.076 | 1.978 | 37.000 | 21.916 | WEAK |
| val_price_to_book | 0.075 | 1.375 | 32.410 | 32.096 | UNSTABLE |
| realized_vol_63 | 0.072 | 1.419 | 92.992 | 3.049 | UNSTABLE |
| val_ev_to_operating_income | 0.072 | 1.246 | 22.496 | 52.470 | DATA_QUALITY_LIMITED |
| val_ev_to_sales | 0.070 | 1.410 | 29.579 | 37.740 | WEAK |
| downside_vol_63 | 0.068 | 1.338 | 92.992 | 3.049 | UNSTABLE |
| rc_drawdown_state | 0.056 | 1.346 | 90.065 | 12.039 | WEAK |
| realized_vol_20 | 0.054 | 1.175 | 94.269 | 1.071 | UNSTABLE |
| val_price_to_sales | 0.053 | 1.049 | 37.090 | 21.916 | WEAK |
| fund_net_income_yoy | -0.053 | -1.104 | 36.119 | 23.787 | WEAK |
| fund_cash_to_assets | 0.052 | 1.315 | 42.396 | 10.734 | WEAK |
| atr14_pct | 0.052 | 1.000 | 94.615 | 0.015 | UNSTABLE |
| fund_current_ratio | 0.051 | 1.479 | 42.799 | 9.925 | WEAK |
| drawdown_from_52w_high | -0.048 | -1.061 | 90.065 | 12.039 | WEAK |

### Horizonte 12M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_fcf_yoy | 0.185 | 2.940 | 23.586 | 49.042 | WEAK |
| fund_dividends_to_fcf | -0.167 | -2.279 | 18.354 | 61.048 | DATA_QUALITY_LIMITED |
| val_pe | 0.159 | 2.150 | 33.234 | 29.386 | PROMISING |
| fund_revenue_yoy | 0.154 | 2.532 | 40.102 | 14.790 | PROMISING |
| realized_vol_126 | 0.153 | 2.075 | 92.553 | 6.083 | PROMISING |
| val_earnings_yield | -0.146 | -1.964 | 35.750 | 24.207 | WEAK |
| val_ev_to_operating_income | 0.137 | 1.869 | 22.181 | 52.470 | DATA_QUALITY_LIMITED |
| fund_debt_to_assets | -0.132 | -3.253 | 33.828 | 27.769 | PROMISING |
| fund_shareholder_yield | 0.132 | 2.493 | 31.346 | 33.832 | WEAK |
| realized_vol_63 | 0.131 | 1.904 | 93.563 | 3.049 | WEAK |
| fund_debt_to_equity | -0.124 | -2.216 | 29.669 | 37.380 | WEAK |
| val_price_to_book | 0.124 | 1.742 | 32.383 | 32.096 | UNSTABLE |
| fund_accruals_to_assets | -0.120 | -2.204 | 36.984 | 21.123 | PROMISING |
| downside_vol_63 | 0.116 | 1.717 | 93.563 | 3.049 | WEAK |
| atr14_pct | 0.110 | 1.517 | 95.266 | 0.015 | WEAK |
| val_fcf_yield_own_pct | 0.109 | 1.868 | 22.510 | 60.254 | DATA_QUALITY_LIMITED |
| realized_vol_20 | 0.106 | 1.654 | 94.906 | 1.071 | WEAK |
| val_ev_to_sales | 0.099 | 1.439 | 29.228 | 37.740 | WEAK |
| fund_cfo_to_net_income | 0.088 | 1.694 | 36.758 | 21.916 | WEAK |
| val_price_to_sales | 0.081 | 1.291 | 36.906 | 21.916 | UNSTABLE |
| rc_drawdown_state | 0.074 | 1.395 | 90.504 | 12.039 | WEAK |
| val_fcf_yield | -0.073 | -0.854 | 23.477 | 49.955 | WEAK |
| fund_cash_to_assets | 0.072 | 1.416 | 42.195 | 10.734 | WEAK |
| drawdown_from_52w_high | -0.072 | -1.172 | 90.504 | 12.039 | WEAK |
| fund_net_income_yoy | -0.066 | -1.226 | 35.891 | 23.787 | WEAK |

## 4. IC excess return vs benchmark

### Horizonte 6M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.122 | -2.026 | 18.526 | 61.048 | DATA_QUALITY_LIMITED |
| fund_shareholder_yield | 0.121 | 3.114 | 31.571 | 33.832 | WEAK |
| fund_fcf_yoy | 0.112 | 2.037 | 23.925 | 49.042 | WEAK |
| realized_vol_126 | 0.109 | 2.159 | 90.715 | 6.083 | PROMISING |
| fund_revenue_yoy | 0.104 | 1.856 | 40.373 | 14.790 | WEAK |
| val_pe | 0.101 | 1.845 | 33.455 | 29.386 | WEAK |
| fund_accruals_to_assets | -0.100 | -2.775 | 37.306 | 21.123 | PROMISING |
| val_fcf_yield_own_pct | 0.094 | 2.014 | 22.664 | 60.254 | DATA_QUALITY_LIMITED |
| fund_debt_to_assets | -0.090 | -2.503 | 34.149 | 27.769 | UNSTABLE |
| fund_debt_to_equity | -0.090 | -2.104 | 29.910 | 37.380 | UNSTABLE |
| realized_vol_63 | 0.087 | 1.783 | 91.015 | 3.049 | WEAK |
| downside_vol_63 | 0.086 | 1.816 | 91.015 | 3.049 | UNSTABLE |
| val_earnings_yield | -0.086 | -1.558 | 35.948 | 24.207 | WEAK |
| atr14_pct | 0.084 | 1.739 | 91.859 | 0.015 | WEAK |
| fund_cfo_to_net_income | 0.076 | 1.978 | 37.000 | 21.916 | WEAK |
| val_price_to_book | 0.075 | 1.375 | 32.410 | 32.096 | UNSTABLE |
| rc_drawdown_state | 0.072 | 1.869 | 89.984 | 12.039 | WEAK |
| val_ev_to_operating_income | 0.072 | 1.246 | 22.496 | 52.470 | DATA_QUALITY_LIMITED |
| val_ev_to_sales | 0.070 | 1.410 | 29.579 | 37.740 | WEAK |
| realized_vol_20 | 0.070 | 1.571 | 91.813 | 1.071 | WEAK |
| drawdown_from_52w_high | -0.064 | -1.551 | 89.984 | 12.039 | WEAK |
| drawdown_from_26w_high | -0.057 | -1.507 | 90.715 | 6.083 | WEAK |
| val_price_to_sales | 0.053 | 1.049 | 37.090 | 21.916 | WEAK |
| fund_net_income_yoy | -0.053 | -1.104 | 36.119 | 23.787 | WEAK |
| fund_cash_to_assets | 0.052 | 1.315 | 42.396 | 10.734 | WEAK |

### Horizonte 12M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_fcf_yoy | 0.185 | 2.940 | 23.586 | 49.042 | WEAK |
| realized_vol_126 | 0.170 | 2.459 | 91.171 | 6.083 | PROMISING |
| fund_dividends_to_fcf | -0.167 | -2.279 | 18.354 | 61.048 | DATA_QUALITY_LIMITED |
| val_pe | 0.159 | 2.150 | 33.234 | 29.386 | PROMISING |
| fund_revenue_yoy | 0.154 | 2.532 | 40.102 | 14.790 | PROMISING |
| atr14_pct | 0.152 | 2.280 | 92.359 | 0.015 | PROMISING |
| realized_vol_63 | 0.150 | 2.302 | 91.476 | 3.049 | PROMISING |
| val_earnings_yield | -0.146 | -1.964 | 35.750 | 24.207 | WEAK |
| val_ev_to_operating_income | 0.137 | 1.869 | 22.181 | 52.470 | DATA_QUALITY_LIMITED |
| downside_vol_63 | 0.137 | 2.200 | 91.476 | 3.049 | PROMISING |
| fund_debt_to_assets | -0.132 | -3.253 | 33.828 | 27.769 | PROMISING |
| fund_shareholder_yield | 0.132 | 2.493 | 31.346 | 33.832 | WEAK |
| realized_vol_20 | 0.127 | 2.059 | 92.315 | 1.071 | PROMISING |
| fund_debt_to_equity | -0.124 | -2.216 | 29.669 | 37.380 | WEAK |
| val_price_to_book | 0.124 | 1.742 | 32.383 | 32.096 | UNSTABLE |
| fund_accruals_to_assets | -0.120 | -2.204 | 36.984 | 21.123 | PROMISING |
| val_fcf_yield_own_pct | 0.109 | 1.868 | 22.510 | 60.254 | DATA_QUALITY_LIMITED |
| val_ev_to_sales | 0.099 | 1.439 | 29.228 | 37.740 | WEAK |
| drawdown_from_52w_high | -0.093 | -1.565 | 90.419 | 12.039 | WEAK |
| rc_drawdown_state | 0.092 | 1.797 | 90.419 | 12.039 | WEAK |
| fund_cfo_to_net_income | 0.088 | 1.694 | 36.758 | 21.916 | WEAK |
| val_price_to_sales | 0.081 | 1.291 | 36.906 | 21.916 | UNSTABLE |
| drawdown_from_26w_high | -0.079 | -1.286 | 91.171 | 6.083 | WEAK |
| distance_52w_high | -0.078 | -1.368 | 94.932 | 8.054 | WEAK |
| val_fcf_yield | -0.073 | -0.854 | 23.477 | 49.955 | WEAK |

## 5. IC vs max drawdown (negativo = más caída si el feature sube)

### Horizonte 6M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| atr14_pct | -0.474 | -14.830 | 94.615 | 0.015 | PROMISING |
| realized_vol_126 | -0.457 | -13.567 | 92.023 | 6.083 | PROMISING |
| realized_vol_63 | -0.455 | -14.297 | 92.992 | 3.049 | PROMISING |
| downside_vol_63 | -0.426 | -12.156 | 92.992 | 3.049 | PROMISING |
| realized_vol_20 | -0.414 | -12.577 | 94.269 | 1.071 | PROMISING |
| val_fcf_yield | 0.259 | 5.993 | 23.649 | 49.955 | WEAK |
| drawdown_from_26w_high | 0.224 | 5.159 | 92.023 | 6.083 | PROMISING |
| rc_drawdown_state | -0.224 | -6.527 | 90.065 | 12.039 | PROMISING |
| drawdown_from_52w_high | 0.222 | 5.248 | 90.065 | 12.039 | PROMISING |
| distance_26w_high | 0.215 | 4.997 | 94.015 | 4.143 | PROMISING |
| distance_52w_high | 0.213 | 4.969 | 94.355 | 8.054 | PROMISING |
| val_earnings_yield | 0.199 | 4.932 | 35.948 | 24.207 | PROMISING |
| fund_roe | 0.181 | 4.404 | 34.157 | 27.934 | PROMISING |
| fund_dividend_yield | 0.173 | 3.234 | 39.187 | 17.395 | PROMISING |
| fund_revenue_yoy | -0.167 | -4.884 | 40.373 | 14.790 | PROMISING |
| support_distance_pct | -0.152 | -4.748 | 92.941 | 1.753 | PROMISING |
| fund_dividends_to_fcf | 0.150 | 3.040 | 18.526 | 61.048 | DATA_QUALITY_LIMITED |
| val_price_to_sales_own_pct | 0.145 | 2.541 | 36.236 | 36.647 | WEAK |
| val_ev_to_operating_income | -0.143 | -2.614 | 22.496 | 52.470 | DATA_QUALITY_LIMITED |
| val_price_to_sales | -0.143 | -3.430 | 37.090 | 21.916 | PROMISING |
| fund_cash_to_assets | -0.142 | -4.209 | 42.396 | 10.734 | PROMISING |
| fund_operating_margin | 0.139 | 4.628 | 34.985 | 26.228 | PROMISING |
| val_price_to_book | -0.129 | -3.373 | 32.410 | 32.096 | WEAK |
| fund_fcf_margin | 0.124 | 3.544 | 27.209 | 42.365 | WEAK |
| val_ev_to_sales | -0.122 | -2.716 | 29.579 | 37.740 | WEAK |

### Horizonte 12M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| atr14_pct | -0.441 | -9.076 | 95.266 | 0.015 | PROMISING |
| realized_vol_126 | -0.433 | -8.181 | 92.553 | 6.083 | PROMISING |
| realized_vol_63 | -0.428 | -8.561 | 93.563 | 3.049 | PROMISING |
| downside_vol_63 | -0.408 | -8.130 | 93.563 | 3.049 | PROMISING |
| realized_vol_20 | -0.386 | -7.805 | 94.906 | 1.071 | PROMISING |
| val_fcf_yield | 0.261 | 4.459 | 23.477 | 49.955 | WEAK |
| drawdown_from_26w_high | 0.224 | 3.902 | 92.553 | 6.083 | PROMISING |
| rc_drawdown_state | -0.217 | -4.905 | 90.504 | 12.039 | PROMISING |
| distance_26w_high | 0.217 | 3.819 | 94.659 | 4.143 | PROMISING |
| drawdown_from_52w_high | 0.216 | 4.194 | 90.504 | 12.039 | PROMISING |
| distance_52w_high | 0.208 | 3.931 | 95.051 | 8.054 | PROMISING |
| fund_roe | 0.178 | 2.722 | 33.898 | 27.934 | PROMISING |
| val_earnings_yield | 0.177 | 3.582 | 35.750 | 24.207 | PROMISING |
| val_price_to_sales_own_pct | 0.166 | 2.732 | 35.981 | 36.647 | WEAK |
| fund_cash_to_assets | -0.164 | -3.322 | 42.195 | 10.734 | PROMISING |
| fund_operating_margin | 0.156 | 3.850 | 34.789 | 26.228 | PROMISING |
| val_ev_to_operating_income | -0.155 | -2.075 | 22.181 | 52.470 | DATA_QUALITY_LIMITED |
| fund_revenue_yoy | -0.155 | -3.424 | 40.102 | 14.790 | PROMISING |
| fund_dividend_yield | 0.147 | 2.186 | 38.961 | 17.395 | PROMISING |
| val_price_to_sales | -0.146 | -2.385 | 36.906 | 21.916 | PROMISING |
| val_price_to_book_own_pct | 0.145 | 2.752 | 31.317 | 45.389 | WEAK |
| fund_fcf_margin | 0.144 | 2.612 | 26.969 | 42.365 | WEAK |
| support_distance_pct | -0.133 | -2.874 | 93.500 | 1.753 | PROMISING |
| val_price_to_book | -0.131 | -2.231 | 32.383 | 32.096 | WEAK |
| fund_net_margin | 0.128 | 3.997 | 40.305 | 14.401 | PROMISING |

## 6-8. Deciles, D10−D1 y monotonicidad (excess, DEV)

| feature | H | D10−D1 | monot. deciles | Q5−Q1 | monot. quintiles |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | 6M | -0.020 | -0.080 | -0.040 | -0.838 |
| fund_dividends_to_fcf | 12M | -0.083 | -0.417 | -0.075 | -0.879 |
| fund_shareholder_yield | 6M | 0.077 | 0.644 | 0.044 | 0.738 |
| fund_shareholder_yield | 12M | 0.168 | 0.556 | 0.089 | 0.634 |
| fund_fcf_yoy | 6M | 0.005 | 0.423 | 0.020 | 0.575 |
| fund_fcf_yoy | 12M | 0.041 | 0.501 | 0.052 | 0.646 |
| realized_vol_126 | 6M | 0.131 | 0.811 | 0.088 | 0.887 |
| realized_vol_126 | 12M | 0.339 | 0.802 | 0.224 | 0.885 |
| fund_revenue_yoy | 6M | 0.057 | 0.796 | 0.079 | 0.876 |
| fund_revenue_yoy | 12M | 0.167 | 0.775 | 0.201 | 0.829 |
| val_pe | 6M | 0.082 | 0.750 | 0.061 | 0.800 |
| val_pe | 12M | 0.176 | 0.832 | 0.143 | 0.901 |
| fund_accruals_to_assets | 6M | -0.070 | -0.719 | -0.063 | -0.762 |
| fund_accruals_to_assets | 12M | -0.111 | -0.651 | -0.134 | -0.720 |
| val_fcf_yield_own_pct | 6M | 0.097 | 0.935 | 0.080 | 0.928 |
| val_fcf_yield_own_pct | 12M | 0.276 | 0.861 | 0.210 | 0.905 |
| fund_debt_to_assets | 6M | -0.042 | -0.333 | -0.014 | -0.399 |
| fund_debt_to_assets | 12M | -0.097 | -0.244 | -0.006 | -0.214 |
| fund_debt_to_equity | 6M | -0.028 | -0.336 | -0.022 | -0.327 |
| fund_debt_to_equity | 12M | -0.022 | -0.214 | -0.025 | -0.184 |
| realized_vol_63 | 6M | 0.120 | 0.765 | 0.074 | 0.886 |
| realized_vol_63 | 12M | 0.312 | 0.791 | 0.205 | 0.881 |
| downside_vol_63 | 6M | 0.108 | 0.796 | 0.071 | 0.892 |
| downside_vol_63 | 12M | 0.290 | 0.790 | 0.189 | 0.891 |
| val_earnings_yield | 6M | -0.093 | -0.822 | -0.093 | -0.823 |
| val_earnings_yield | 12M | -0.323 | -0.824 | -0.260 | -0.853 |
| atr14_pct | 6M | 0.099 | 0.836 | 0.068 | 0.913 |
| atr14_pct | 12M | 0.284 | 0.842 | 0.196 | 0.922 |
| fund_cfo_to_net_income | 6M | 0.042 | 0.685 | 0.030 | 0.775 |
| fund_cfo_to_net_income | 12M | 0.065 | 0.586 | 0.048 | 0.796 |

## 9. Robustez no solapada

Para el horizonte H sólo se usan los meses congruentes módulo H (H offsets sin solape) y se reporta la media de los t por offset. Un IC con t<2 en este esquema no se considera evidencia.

## 10-12. Estabilidad por periodo, región y régimen (IC medio excess 6M)

| feature | 2011-16 | 2017-22 | BULL | BEAR | US | EU | ES | ASIA | NA |
|---|---|---|---|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.166 | -0.073 | -0.115 | -0.003 | -0.122 | — | — | — | — |
| fund_shareholder_yield | 0.143 | 0.097 | 0.098 | 0.149 | 0.121 | — | — | — | — |
| fund_fcf_yoy | 0.067 | 0.155 | 0.116 | 0.114 | 0.112 | — | — | — | — |
| realized_vol_126 | 0.122 | 0.095 | 0.125 | 0.021 | 0.125 | 0.127 | -0.045 | 0.041 | — |
| fund_revenue_yoy | 0.084 | 0.127 | 0.124 | 0.039 | 0.105 | — | — | — | — |
| val_pe | 0.076 | 0.129 | 0.131 | 0.082 | 0.101 | — | — | — | — |
| fund_accruals_to_assets | -0.063 | -0.136 | -0.094 | -0.140 | -0.100 | — | — | — | — |
| val_fcf_yield_own_pct | 0.059 | 0.119 | 0.099 | 0.055 | 0.094 | — | — | — | — |
| fund_debt_to_assets | -0.069 | -0.115 | -0.106 | 0.009 | -0.091 | — | — | — | — |
| fund_debt_to_equity | -0.071 | -0.110 | -0.100 | 0.029 | -0.090 | — | — | — | — |
| realized_vol_63 | 0.094 | 0.080 | 0.116 | 0.004 | 0.104 | 0.119 | -0.064 | 0.031 | — |
| downside_vol_63 | 0.088 | 0.085 | 0.116 | -0.006 | 0.101 | 0.099 | -0.081 | 0.040 | — |
| val_earnings_yield | -0.080 | -0.092 | -0.119 | -0.041 | -0.086 | — | — | — | — |
| atr14_pct | 0.100 | 0.065 | 0.116 | 0.013 | 0.099 | 0.115 | -0.038 | 0.020 | — |
| fund_cfo_to_net_income | 0.063 | 0.090 | 0.079 | 0.163 | 0.076 | — | — | — | — |
| val_price_to_book | 0.044 | 0.109 | 0.095 | -0.007 | 0.075 | — | — | — | — |
| rc_drawdown_state | 0.077 | 0.067 | 0.076 | 0.029 | 0.057 | 0.087 | 0.007 | 0.069 | — |
| val_ev_to_operating_income | 0.028 | 0.120 | 0.081 | 0.109 | 0.072 | — | — | — | — |
| val_ev_to_sales | 0.038 | 0.106 | 0.076 | 0.014 | 0.070 | — | — | — | — |
| realized_vol_20 | 0.073 | 0.066 | 0.101 | 0.005 | 0.080 | 0.100 | -0.045 | 0.014 | — |
| drawdown_from_52w_high | -0.070 | -0.057 | -0.072 | -0.031 | -0.058 | -0.054 | 0.011 | -0.046 | — |
| drawdown_from_26w_high | -0.064 | -0.048 | -0.068 | -0.006 | -0.066 | -0.051 | 0.072 | -0.026 | — |
| val_price_to_sales | 0.009 | 0.103 | 0.071 | 0.002 | 0.053 | — | — | — | — |
| fund_net_income_yoy | -0.095 | -0.008 | -0.045 | -0.062 | -0.053 | — | — | — | — |
| fund_cash_to_assets | 0.027 | 0.080 | 0.061 | 0.030 | 0.052 | — | — | — | — |

## 13. Redundancia (|Spearman| ≥ 0.85, sólo DEV)

| feature A | feature B | ρ |
|---|---|---|
| support_broken | rc_support_broken | 1.000 |
| risk_alert_h1 | risk_alert_h3 | 1.000 |
| risk_alert_h12 | risk_alert_h24 | 1.000 |
| val_pe | val_earnings_yield | -1.000 |
| risk_alert_h6 | risk_alert_h12 | 0.994 |
| risk_alert_h6 | risk_alert_h24 | 0.994 |
| distance_26w_high | drawdown_from_26w_high | 0.989 |
| val_price_to_sales | val_ev_to_sales | 0.987 |
| distance_52w_high | drawdown_from_52w_high | 0.984 |
| distance_sma50 | ema50_distance | 0.975 |
| distance_sma20 | ema20_distance | 0.975 |
| sma20_slope | sma20_vs_sma50 | 0.955 |
| ema20_distance | rsi14 | 0.946 |
| ret_12m | momentum_12_1 | 0.945 |
| drawdown_from_52w_high | drawdown_from_26w_high | 0.938 |
| realized_vol_63 | downside_vol_63 | 0.938 |
| distance_26w_high | drawdown_from_52w_high | 0.936 |
| fund_operating_margin | fund_net_margin | 0.923 |
| distance_52w_high | distance_26w_high | 0.922 |
| ema50_distance | rsi14 | 0.918 |
| support_distance_pct | support_distance_atr | 0.915 |
| ret_3m | sma50_slope | 0.912 |
| ret_6m | distance_sma200 | 0.910 |
| realized_vol_63 | realized_vol_126 | 0.908 |
| distance_52w_high | drawdown_from_26w_high | 0.907 |
| distance_sma20 | rsi14 | 0.905 |
| realized_vol_20 | atr14_pct | 0.904 |
| fund_buyback_yield | fund_net_equity_issuance | -0.901 |
| rc_momentum_negative | risk_alert_h6 | 0.899 |
| rc_momentum_negative | risk_alert_h12 | 0.899 |
| rc_momentum_negative | risk_alert_h24 | 0.899 |
| distance_sma50 | rsi14 | 0.893 |
| realized_vol_63 | atr14_pct | 0.885 |
| atr14_pct | downside_vol_63 | 0.867 |
| ret_12m | sma200_slope | 0.867 |
| ema20_distance | ema50_distance | 0.862 |
| ret_6m | sma50_vs_sma200 | 0.860 |
| rc_below_sma200 | risk_alert_h12 | 0.856 |
| rc_below_sma200 | risk_alert_h24 | 0.856 |
| volume_zscore_20 | volume_zscore_63 | 0.856 |
| ret_1m | distance_sma50 | 0.855 |
| fund_gross_margin | fund_fcf_margin | 0.854 |
| distance_sma200 | sma50_vs_sma200 | 0.853 |
| rc_below_sma200 | risk_alert_h6 | 0.851 |

## 14. Fundamentales continuos: qué componente aporta

Compuesto = media de rangos percentiles orientados a priori (`ORIENT`, fijados antes de ver ningún IC). IC frente a excess 6/12/24M y drawdown 6/12M.

| componente | IC exc 6M | IC exc 12M | IC exc 24M | IC mdd 6M | IC mdd 12M | t 6M | t 12M | t 24M |
|---|---|---|---|---|---|---|---|---|
| comp_profitability | 0.002 | 0.000 | — | 0.110 | 0.115 | 0.039 | -0.027 | — |
| comp_cash_flow | 0.086 | 0.094 | — | 0.028 | 0.037 | 2.840 | 1.902 | — |
| comp_growth | 0.038 | 0.072 | — | -0.108 | -0.079 | 0.743 | 1.239 | — |
| comp_leverage | 0.055 | 0.078 | — | -0.098 | -0.099 | 1.518 | 1.627 | — |
| comp_capital_allocation | 0.042 | 0.018 | — | 0.122 | 0.104 | 0.954 | 0.312 | — |
| comp_valuation | -0.057 | -0.110 | — | 0.137 | 0.122 | -1.095 | -1.614 | — |

## 15. Cobertura SEC de fundamentales (tabla)

Valores XNYS con precios: 52 → {'READY': 32, 'PARTIAL': 15, 'NOT_REGISTERED': 4, 'INSUFFICIENT_HISTORY': 1}. No-XNYS: sin fundamentales SEC (`NOT_REGISTERED`, esperado).

| ticker | estado | SIC | cobertura | 1º filing | métricas ausentes |
|---|---|---|---|---|---|
| TXN | READY | 3674 | 0.920 | 2011-02-28 | fund_dividend_yield, fund_interest_coverage, fund_net_equity_issuance, fund_shareholder_yield |
| PG | READY | 2840 | 0.820 | 2011-01-31 | fund_debt_to_equity, fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_roe |
| UPS | READY | 4210 | 0.800 | 2011-02-28 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| CRM | READY | 7372 | 0.940 | 2011-03-24 | fund_dividend_yield, fund_net_equity_issuance, fund_shareholder_yield |
| WMT | READY | 5331 | 0.860 | 2011-03-31 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| INTU | READY | 7372 | 0.880 | 2011-03-01 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| DIS | READY | 7990 | 0.820 | 2019-05-09 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| CAT | PARTIAL | 3531 | 0.720 | 2011-02-23 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance, fund_net_income_yoy |
| JNJ | READY | 2834 | 0.900 | 2011-02-25 | fund_dividend_yield, fund_dividends_to_fcf, fund_net_equity_issuance, fund_shareholder_yield |
| BA | READY | 3721 | 0.800 | 2011-02-09 | fund_dividend_yield, fund_interest_coverage, fund_shareholder_yield |
| AMZN | READY | 5961 | 0.820 | 2011-01-28 | fund_dividend_yield, fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| WFC | NOT_REGISTERED | — | — | — |  |
| IBM | READY | 3570 | 0.820 | 2011-02-22 | fund_dividend_yield, fund_interest_coverage, fund_net_equity_issuance, fund_operating_income_yoy, fund_operating_margin, fund_shareholder_yield |
| MCD | READY | 5812 | 0.820 | 2011-02-25 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| ADBE | READY | 7372 | 0.900 | 2011-01-27 | fund_dividend_yield, fund_dividends_to_fcf, fund_net_equity_issuance, fund_shareholder_yield |
| QCOM | PARTIAL | 3663 | 0.740 | 2011-01-27 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| COST | READY | 5331 | 0.940 | 2011-03-17 | fund_dividend_yield, fund_net_equity_issuance, fund_shareholder_yield |
| NEE | PARTIAL | 4911 | 0.600 | 2011-02-28 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| AVGO | READY | 3674 | 0.940 | 2018-06-15 | fund_dividend_yield, fund_interest_coverage, fund_shareholder_yield |
| NFLX | READY | 7841 | 0.860 | 2011-02-18 | fund_dividend_yield, fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| AMGN | READY | 2836 | 0.860 | 2011-02-28 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| ORCL | READY | 7372 | 0.880 | 2011-03-29 | fund_dividend_yield, fund_shareholder_yield |
| XOM | INSUFFICIENT_HISTORY | 2911 | 0.140 | 2026-08-03 | fund_accruals_to_assets, fund_buyback_yield, fund_capex_growth_yoy, fund_capex_to_assets, fund_cfo_to_net_income, fund_dividend_yield |
| NVDA | PARTIAL | 3674 | 0.780 | 2011-03-17 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| GOOGL | READY | 7370 | 0.800 | 2015-10-30 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| TMO | READY | 3829 | 0.880 | 2011-02-25 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| CVX | PARTIAL | 2911 | 0.600 | 2011-02-24 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| UNH | NOT_REGISTERED | — | — | — |  |
| MA | READY | 7389 | 0.800 | 2011-02-24 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| LLY | PARTIAL | 2834 | 0.580 | 2011-02-22 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| MRK | PARTIAL | 2834 | 0.720 | 2011-02-28 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance, fund_operating_income_yoy |
| UNP | READY | 4011 | 0.880 | 2011-02-07 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| HON | READY | 3724 | 0.820 | 2011-02-11 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance, fund_shareholder_yield |
| GE | PARTIAL | 3600 | 0.740 | 2011-02-28 | fund_dividend_yield, fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_operating_income_yoy |
| CSCO | READY | 3576 | 0.960 | 2011-02-23 | fund_dividend_yield, fund_shareholder_yield |
| PEP | PARTIAL | 2080 | 0.780 | 2011-02-22 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| TSLA | READY | 3711 | 0.860 | 2011-08-15 | fund_buyback_yield, fund_dividend_yield, fund_dividends_to_fcf, fund_net_equity_issuance, fund_shareholder_yield |
| SPGI | PARTIAL | 7320 | 0.700 | 2011-02-23 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| META | READY | 7370 | 0.820 | 2012-08-01 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| LMT | READY | 3760 | 0.920 | 2011-02-25 | fund_dividend_yield, fund_net_equity_issuance, fund_shareholder_yield |
| ABBV | READY | 2834 | 0.820 | 2013-05-09 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| JPM | NOT_REGISTERED | — | — | — |  |
| VZ | PARTIAL | 4813 | 0.600 | 2011-02-28 | fund_buyback_yield, fund_capex_growth_yoy, fund_capex_to_assets, fund_debt_to_equity, fund_dividend_yield, fund_dividends_to_fcf |
| V | PARTIAL | 7389 | 0.620 | 2011-02-03 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| ACN | PARTIAL | 7389 | 0.700 | 2011-03-28 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| ABT | READY | 2834 | 0.860 | 2011-02-18 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| BAC | NOT_REGISTERED | — | — | — |  |
| RTX | READY | 3724 | 0.900 | 2011-02-10 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| LIN | READY | 2810 | 0.900 | 2017-10-31 | fund_dividend_yield, fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| HD | PARTIAL | 5211 | 0.800 | 2011-03-25 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividend_yield, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| PFE | PARTIAL | 2834 | 0.720 | 2011-02-28 | fund_dividend_yield, fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance |
| LOW | READY | 5211 | 0.900 | 2011-03-29 | fund_dividend_yield, fund_net_equity_issuance, fund_shareholder_yield |

## 16. Features candidatas (PROMISING, a validar fuera de muestra)

| feature | H | IC | t | N medio |
|---|---|---|---|---|
| realized_vol_126 | 6 | 0.109 | 2.159 | 90.715 |
| fund_accruals_to_assets | 6 | -0.100 | -2.775 | 37.306 |
| realized_vol_20 | 12 | 0.127 | 2.059 | 92.315 |
| realized_vol_63 | 12 | 0.150 | 2.302 | 91.476 |
| realized_vol_126 | 12 | 0.170 | 2.459 | 91.171 |
| atr14_pct | 12 | 0.152 | 2.280 | 92.359 |
| downside_vol_63 | 12 | 0.137 | 2.200 | 91.476 |
| fund_accruals_to_assets | 12 | -0.120 | -2.204 | 36.984 |
| fund_revenue_yoy | 12 | 0.154 | 2.532 | 40.102 |
| fund_debt_to_assets | 12 | -0.132 | -3.253 | 33.828 |
| val_pe | 12 | 0.159 | 2.150 | 33.234 |

## 17. Features débiles

atr14_normalized, atr14_pct, distance_26w_high, distance_52w_high, drawdown_from_26w_high, drawdown_from_52w_high, fund_buyback_yield, fund_capex_growth_yoy, fund_cash_to_assets, fund_cfo_to_net_income, fund_current_ratio, fund_debt_to_equity, fund_dividend_yield, fund_fcf_margin, fund_fcf_yoy, fund_net_income_yoy, fund_revenue_yoy, fund_roe, fund_shareholder_yield, rc_drawdown_state, rc_elevated_volatility, realized_vol_20, realized_vol_63, return_kurtosis_63, rsi14, support_age_bars, support_distance_pct, support_touches, val_earnings_yield, val_ev_to_sales, val_fcf_yield, val_pe, val_price_to_sales, volume_change_63

## 18. Features problemáticas (UNSTABLE / DATA_QUALITY_LIMITED)

| feature | H | etiqueta | missing % | N medio |
|---|---|---|---|---|
| ret_1m | 6 | UNSTABLE | 1.071 | 91.813 |
| ret_3m | 6 | UNSTABLE | 3.049 | 91.015 |
| ret_6m | 6 | UNSTABLE | 6.083 | 90.715 |
| ret_12m | 6 | UNSTABLE | 12.039 | 89.984 |
| momentum_12_1 | 6 | UNSTABLE | 12.039 | 89.984 |
| distance_sma20 | 6 | UNSTABLE | 0.075 | 91.859 |
| distance_sma50 | 6 | UNSTABLE | 1.438 | 92.278 |
| distance_sma200 | 6 | UNSTABLE | 6.488 | 93.778 |
| sma20_slope | 6 | UNSTABLE | 1.191 | 91.687 |
| sma50_slope | 6 | UNSTABLE | 2.158 | 92.485 |
| sma200_slope | 6 | UNSTABLE | 7.207 | 94.008 |
| ema20_distance | 6 | UNSTABLE | 0.075 | 91.859 |
| ema50_distance | 6 | UNSTABLE | 1.438 | 92.278 |
| sma20_vs_sma50 | 6 | UNSTABLE | 1.438 | 92.278 |
| sma50_vs_sma200 | 6 | UNSTABLE | 6.488 | 93.778 |
| distance_26w_high | 6 | UNSTABLE | 4.143 | 92.500 |
| return_skew_63 | 6 | UNSTABLE | 3.049 | 91.015 |
| return_kurtosis_63 | 6 | UNSTABLE | 3.049 | 91.015 |
| downside_vol_63 | 6 | UNSTABLE | 3.049 | 91.015 |
| volume_change_20 | 6 | UNSTABLE | 26.903 | 67.612 |
| volume_change_63 | 6 | UNSTABLE | 29.368 | 67.915 |
| volume_zscore_20 | 6 | UNSTABLE | 26.064 | 67.741 |
| volume_zscore_63 | 6 | UNSTABLE | 27.540 | 67.662 |
| rsi14 | 6 | UNSTABLE | 0.015 | 91.859 |
| support_touches | 6 | UNSTABLE | 1.753 | 90.422 |
| support_broken | 6 | UNSTABLE | 1.753 | 90.422 |
| support_distance_atr | 6 | UNSTABLE | 1.753 | 90.422 |
| rc_below_sma200 | 6 | UNSTABLE | 6.488 | 93.778 |
| rc_momentum_negative | 6 | UNSTABLE | 6.083 | 90.715 |
| rc_support_broken | 6 | UNSTABLE | 1.753 | 90.422 |
| rc_elevated_volatility | 6 | UNSTABLE | 9.327 | 92.903 |
| risk_alert_h1 | 6 | UNSTABLE | 6.488 | 93.778 |
| risk_alert_h3 | 6 | UNSTABLE | 6.488 | 93.778 |
| risk_alert_h6 | 6 | UNSTABLE | 6.488 | 93.778 |
| risk_alert_h12 | 6 | UNSTABLE | 6.488 | 93.778 |
| risk_alert_h24 | 6 | UNSTABLE | 6.488 | 93.778 |
| fund_gross_profitability | 6 | DATA_QUALITY_LIMITED | 71.437 | 13.478 |
| fund_operating_margin | 6 | UNSTABLE | 26.228 | 34.985 |
| fund_net_margin | 6 | UNSTABLE | 14.401 | 40.567 |
| fund_gross_margin | 6 | DATA_QUALITY_LIMITED | 70.973 | 13.709 |
| fund_roa | 6 | UNSTABLE | 17.575 | 38.985 |
| fund_roe | 6 | UNSTABLE | 27.934 | 34.157 |
| fund_operating_income_yoy | 6 | UNSTABLE | 31.332 | 32.515 |
| fund_debt_to_assets | 6 | UNSTABLE | 27.769 | 34.149 |
| fund_debt_to_equity | 6 | UNSTABLE | 37.380 | 29.910 |
| fund_interest_coverage | 6 | UNSTABLE | 39.266 | 28.754 |
| fund_net_equity_issuance | 6 | DATA_QUALITY_LIMITED | 79.072 | 9.880 |
| fund_dividends_to_fcf | 6 | DATA_QUALITY_LIMITED | 61.048 | 18.526 |
| fund_capex_to_assets | 6 | UNSTABLE | 39.251 | 28.672 |
| val_price_to_book | 6 | UNSTABLE | 32.096 | 32.410 |
| val_ev_to_operating_income | 6 | DATA_QUALITY_LIMITED | 52.470 | 22.496 |
| val_pe_own_pct | 6 | UNSTABLE | 44.087 | 31.918 |
| val_price_to_sales_own_pct | 6 | UNSTABLE | 36.647 | 36.236 |
| val_price_to_book_own_pct | 6 | UNSTABLE | 45.389 | 31.409 |
| val_fcf_yield_own_pct | 6 | DATA_QUALITY_LIMITED | 60.254 | 22.664 |
| ret_1m | 12 | UNSTABLE | 1.071 | 92.315 |
| ret_3m | 12 | UNSTABLE | 3.049 | 91.476 |
| ret_6m | 12 | UNSTABLE | 6.083 | 91.171 |
| ret_12m | 12 | UNSTABLE | 12.039 | 90.419 |
| momentum_12_1 | 12 | UNSTABLE | 12.039 | 90.419 |
| distance_sma20 | 12 | UNSTABLE | 0.075 | 92.359 |
| distance_sma50 | 12 | UNSTABLE | 1.438 | 92.810 |
| distance_sma200 | 12 | UNSTABLE | 6.488 | 94.429 |
| sma20_slope | 12 | UNSTABLE | 1.191 | 92.181 |
| sma50_slope | 12 | UNSTABLE | 2.158 | 93.032 |
| sma200_slope | 12 | UNSTABLE | 7.207 | 94.678 |
| ema20_distance | 12 | UNSTABLE | 0.075 | 92.359 |
| ema50_distance | 12 | UNSTABLE | 1.438 | 92.810 |
| sma20_vs_sma50 | 12 | UNSTABLE | 1.438 | 92.810 |
| sma50_vs_sma200 | 12 | UNSTABLE | 6.488 | 94.429 |
| atr14_normalized | 12 | UNSTABLE | 8.683 | 95.147 |
| return_skew_63 | 12 | UNSTABLE | 3.049 | 91.476 |
| volume_change_20 | 12 | UNSTABLE | 26.903 | 67.622 |
| volume_zscore_20 | 12 | UNSTABLE | 26.064 | 67.750 |
| volume_zscore_63 | 12 | UNSTABLE | 27.540 | 67.698 |
| support_broken | 12 | UNSTABLE | 1.753 | 90.844 |
| support_distance_atr | 12 | UNSTABLE | 1.753 | 90.844 |
| rc_below_sma200 | 12 | UNSTABLE | 6.488 | 94.429 |
| rc_momentum_negative | 12 | UNSTABLE | 6.083 | 91.171 |
| rc_support_broken | 12 | UNSTABLE | 1.753 | 90.844 |
| risk_alert_h1 | 12 | UNSTABLE | 6.488 | 94.429 |
| risk_alert_h3 | 12 | UNSTABLE | 6.488 | 94.429 |
| risk_alert_h6 | 12 | UNSTABLE | 6.488 | 94.429 |
| risk_alert_h12 | 12 | UNSTABLE | 6.488 | 94.429 |
| risk_alert_h24 | 12 | UNSTABLE | 6.488 | 94.429 |
| fund_gross_profitability | 12 | DATA_QUALITY_LIMITED | 71.437 | 13.352 |
| fund_operating_margin | 12 | UNSTABLE | 26.228 | 34.789 |
| fund_net_margin | 12 | UNSTABLE | 14.401 | 40.305 |
| fund_gross_margin | 12 | DATA_QUALITY_LIMITED | 70.973 | 13.594 |
| fund_roa | 12 | UNSTABLE | 17.575 | 38.648 |
| fund_fcf_margin | 12 | UNSTABLE | 42.365 | 26.969 |
| fund_operating_income_yoy | 12 | UNSTABLE | 31.332 | 32.297 |
| fund_interest_coverage | 12 | UNSTABLE | 39.266 | 28.547 |
| fund_dividend_yield | 12 | UNSTABLE | 17.395 | 38.961 |
| fund_buyback_yield | 12 | UNSTABLE | 28.263 | 33.844 |
| fund_net_equity_issuance | 12 | DATA_QUALITY_LIMITED | 79.072 | 9.756 |
| fund_dividends_to_fcf | 12 | DATA_QUALITY_LIMITED | 61.048 | 18.354 |
| fund_capex_to_assets | 12 | UNSTABLE | 39.251 | 28.406 |
| val_price_to_sales | 12 | UNSTABLE | 21.916 | 36.906 |
| val_price_to_book | 12 | UNSTABLE | 32.096 | 32.383 |
| val_ev_to_operating_income | 12 | DATA_QUALITY_LIMITED | 52.470 | 22.181 |
| val_pe_own_pct | 12 | UNSTABLE | 44.087 | 31.673 |
| val_price_to_sales_own_pct | 12 | UNSTABLE | 36.647 | 35.981 |
| val_price_to_book_own_pct | 12 | UNSTABLE | 45.389 | 31.317 |
| val_fcf_yield_own_pct | 12 | DATA_QUALITY_LIMITED | 60.254 | 22.510 |

## RISK_ALERT: señal de riesgo, no de venta

| alerta | H | tasa alerta | IC vs mdd | t | OR dd≥10% | OR dd≥15% | OR dd≥20% | P(dd15|alerta) | P(dd15|sin) |
|---|---|---|---|---|---|---|---|---|---|
| risk_alert_h6 | 6M | 0.258 | -0.080 | -1.940 | 1.43 [1.31, 1.57] | 1.75 [1.61, 1.91] | 1.81 [1.65, 1.99] | 0.483 | 0.348 |
| risk_alert_h12 | 6M | 0.260 | -0.078 | -1.895 | 1.41 [1.29, 1.55] | 1.73 [1.59, 1.88] | 1.79 [1.63, 1.97] | 0.481 | 0.348 |
| risk_alert_h6 | 12M | 0.258 | -0.079 | -1.365 | 1.23 [1.08, 1.41] | 1.47 [1.34, 1.60] | 1.33 [1.22, 1.45] | 0.663 | 0.573 |
| risk_alert_h12 | 12M | 0.260 | -0.078 | -1.353 | 1.20 [1.05, 1.37] | 1.45 [1.33, 1.59] | 1.32 [1.21, 1.44] | 0.661 | 0.573 |
| risk_alert_h6 | 24M | 0.258 | — | — | 1.69 [1.16, 2.46] | 1.77 [1.55, 2.01] | 1.41 [1.28, 1.55] | 0.873 | 0.796 |
| risk_alert_h12 | 24M | 0.260 | — | — | 1.60 [1.11, 2.31] | 1.73 [1.52, 1.97] | 1.40 [1.27, 1.54] | 0.871 | 0.796 |

## Baselines ingenuos

| H | n | base_rate_outperform | accuracy_always_outperform | auc_momentum_12_1 | auc_low_vol_63 | auc_ret_6m | auc_risk_alert_inverse |
|---|---|---|---|---|---|---|---|
| 6M | 12403 | 0.560 | 0.560 | 0.492 | 0.480 | 0.490 | 0.491 |
| 12M | 11824 | 0.575 | 0.575 | 0.503 | 0.469 | 0.502 | 0.497 |

## 19. Gates antes de ML

| gate | estado | detalle |
|---|---|---|
| DEV_ROWS | READY | 12292 dev rows with a 12M target (need >= 5000) |
| SECURITIES | BLOCKED | 96 securities with snapshots (need >= 100) |
| BENCHMARKS | READY | benchmarks with excess returns: {'SPY': True, '^IBEX': True, 'URTH': True} |
| CANONICAL_UNIVERSE | BLOCKED | the universe is the CURRENT research set (survivorship, UNIVERSE_NOT_PIT_MEMBERSHIP); D02_MONTHLY_RESEARCH_READY=false |
| FUNDAMENTAL_COVERAGE | READY | 47 securities with >= 36 months of OK fundamentals (need >= 30) |
| FILING_INTELLIGENCE_NOT_REQUIRED | READY | contract only; not an input to V0 models |

## 20. Recomendación para el primer baseline ML

**No entrenar todavía.** Gates bloqueados: SECURITIES, CANONICAL_UNIVERSE. Primer experimento recomendado: comparar `EQUITY_6M_LOGISTIC_V0` y `EQUITY_12M_ELASTIC_NET_V0` (contratos en `research/model_contracts.py`) contra los baselines de arriba con folds expansivos purgados sobre DEV; descartar si no los superan fuera de muestra.
