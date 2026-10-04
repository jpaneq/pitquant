# RUN 3 — Features continuas PIT, fundamentales y efectividad (informe generado)

Generado desde la base el 2026-10-04T21:01:12Z · segmento **DEV** (decisiones ≤ 2022-09-30) · 13,488 filas · 97 valores · 140 meses. El holdout oct-2022→sep-2025 no se ha leído: sus decisiones no se generan y los objetivos que lo tocan son `UNAVAILABLE`. Todo es **descriptivo**: no se entrena ni se seleccionan pesos.

> Limitaciones que se aplican a TODO lo que sigue: universo = conjunto de investigación ACTUAL (sesgo de supervivencia, no es membresía de índice), benchmarks son proxies (SPY ETF; ^IBEX índice de precio sin dividendos; URTH ETF USD con desajuste de divisa en no-USD), fundamentales sólo EE. UU. y sectores soportados.

## 1. Cobertura de features / 2. Missingness

83 features analizadas (47 técnicas/soporte/riesgo, 36 fundamentales/valoración). Missing nunca se rellena con 0; las razones por feature están en cada snapshot.

| feature | N | missing % | media | std | P10 | P50 | P90 |
|---|---|---|---|---|---|---|---|
| fund_net_equity_issuance | 1537 | 88.605 | -1598615137.931 | 10040305967.341 | -8126000000.000 | -1379000000.000 | 842000000.000 |
| fund_gross_margin | 1982 | 85.305 | 0.461 | 0.235 | 0.135 | 0.488 | 0.787 |
| fund_gross_profitability | 2038 | 84.890 | 0.353 | 0.173 | 0.146 | 0.344 | 0.594 |
| fund_dividends_to_fcf | 2741 | 79.678 | 0.473 | 0.516 | 0.145 | 0.397 | 0.749 |
| val_fcf_yield_own_pct | 2770 | 79.463 | 39.477 | 32.724 | 0.000 | 33.333 | 90.000 |
| val_ev_to_operating_income | 3314 | 75.430 | 63.347 | 577.064 | 11.381 | 17.744 | 58.214 |
| val_fcf_yield | 3482 | 74.184 | 20.966 | 618.374 | 0.011 | 0.045 | 0.083 |
| fund_fcf_yoy | 3528 | 73.843 | 0.125 | 1.502 | -0.237 | 0.086 | 0.573 |
| val_price_to_book_own_pct | 3763 | 72.101 | 70.009 | 31.821 | 13.333 | 82.353 | 100.000 |
| val_pe_own_pct | 3850 | 71.456 | 63.370 | 32.014 | 10.000 | 73.077 | 100.000 |
| fund_fcf_margin | 3893 | 71.137 | 0.158 | 0.214 | 0.019 | 0.149 | 0.367 |
| fund_capex_growth_yoy | 4159 | 69.165 | 0.133 | 0.399 | -0.182 | 0.042 | 0.515 |
| fund_capex_to_assets | 4188 | 68.950 | 0.037 | 0.037 | 0.009 | 0.024 | 0.079 |
| fund_interest_coverage | 4196 | 68.891 | 71.665 | 370.337 | 4.847 | 13.658 | 118.940 |
| val_ev_to_sales | 4202 | 68.846 | 4.674 | 4.201 | 1.097 | 3.667 | 9.265 |
| val_price_to_sales_own_pct | 4251 | 68.483 | 73.858 | 29.373 | 21.667 | 86.486 | 100.000 |
| fund_debt_to_equity | 4322 | 67.957 | 1.611 | 6.062 | 0.080 | 0.604 | 2.839 |
| fund_shareholder_yield | 4558 | 66.207 | 0.063 | 0.086 | 0.017 | 0.054 | 0.108 |
| val_price_to_book | 4675 | 65.340 | 2278.670 | 88945.568 | 2.268 | 5.827 | 25.457 |
| fund_operating_income_yoy | 4717 | 65.028 | 0.263 | 1.251 | -0.235 | 0.088 | 0.672 |
| val_pe | 4856 | 63.998 | 9331.712 | 371641.270 | 13.834 | 22.160 | 74.834 |
| fund_buyback_yield | 4931 | 63.442 | 0.025 | 0.044 | 0.000 | 0.021 | 0.064 |
| fund_roe | 4944 | 63.345 | 1.288 | 21.432 | 0.047 | 0.238 | 0.974 |
| fund_debt_to_assets | 4964 | 63.197 | 0.239 | 0.147 | 0.058 | 0.218 | 0.433 |
| fund_operating_margin | 4971 | 63.145 | 0.204 | 0.193 | 0.034 | 0.170 | 0.416 |
| val_earnings_yield | 5202 | 61.432 | 1.937 | 68.535 | 0.005 | 0.043 | 0.071 |
| fund_net_income_yoy | 5221 | 61.292 | 1.176 | 32.705 | -0.486 | 0.093 | 1.004 |
| val_price_to_sales | 5259 | 61.010 | 2358.171 | 98400.677 | 0.988 | 3.228 | 8.406 |
| fund_cfo_to_net_income | 5355 | 60.298 | 2.457 | 9.635 | 0.993 | 1.470 | 3.080 |
| fund_accruals_to_assets | 5399 | 59.972 | -0.051 | 0.054 | -0.125 | -0.046 | 0.000 |
| fund_roa | 5636 | 58.215 | 0.090 | 0.074 | 0.018 | 0.084 | 0.182 |
| fund_dividend_yield | 5656 | 58.066 | 0.034 | 0.065 | 0.005 | 0.024 | 0.047 |
| fund_revenue_yoy | 5729 | 57.525 | 0.136 | 0.605 | -0.039 | 0.062 | 0.315 |
| fund_net_margin | 5761 | 57.288 | 0.139 | 0.161 | 0.020 | 0.114 | 0.299 |
| fund_cash_to_assets | 6102 | 54.760 | 0.112 | 0.085 | 0.026 | 0.092 | 0.216 |
| fund_current_ratio | 6156 | 54.359 | 1.852 | 1.598 | 0.865 | 1.348 | 3.389 |
| volume_change_63 | 9543 | 29.248 | 0.037 | 0.383 | -0.267 | -0.025 | 0.389 |
| volume_zscore_63 | 9790 | 27.417 | 0.302 | 1.144 | -0.779 | 0.051 | 1.698 |
| volume_change_20 | 9876 | 26.779 | 0.049 | 0.388 | -0.296 | -0.014 | 0.433 |
| volume_zscore_20 | 9989 | 25.942 | 0.403 | 1.164 | -0.832 | 0.138 | 2.135 |
| rc_drawdown_state | 11869 | 12.003 | 0.199 | 0.399 | 0.000 | 0.000 | 1.000 |
| ret_12m | 11869 | 12.003 | 0.191 | 0.373 | -0.121 | 0.157 | 0.495 |
| drawdown_from_52w_high | 11869 | 12.003 | -0.094 | 0.103 | -0.225 | -0.063 | -0.004 |
| momentum_12_1 | 11869 | 12.003 | 0.176 | 0.344 | -0.120 | 0.145 | 0.462 |
| rc_elevated_volatility | 12231 | 9.319 | 0.118 | 0.323 | 0.000 | 0.000 | 1.000 |
| atr14_normalized | 12317 | 8.682 | 1.067 | 0.330 | 0.759 | 0.998 | 1.436 |
| distance_52w_high | 12402 | 8.052 | -0.103 | 0.108 | -0.241 | -0.072 | -0.006 |
| sma200_slope | 12516 | 7.206 | 0.009 | 0.023 | -0.015 | 0.009 | 0.032 |
| risk_alert_h3 | 12613 | 6.487 | 0.177 | 0.381 | 0.000 | 0.000 | 1.000 |
| risk_alert_h6 | 12613 | 6.487 | 0.258 | 0.437 | 0.000 | 0.000 | 1.000 |
| risk_alert_h12 | 12613 | 6.487 | 0.260 | 0.439 | 0.000 | 0.000 | 1.000 |
| risk_alert_h24 | 12613 | 6.487 | 0.260 | 0.439 | 0.000 | 0.000 | 1.000 |
| rc_below_sma200 | 12613 | 6.487 | 0.325 | 0.468 | 0.000 | 0.000 | 1.000 |
| risk_alert_h1 | 12613 | 6.487 | 0.177 | 0.381 | 0.000 | 0.000 | 1.000 |
| distance_sma200 | 12613 | 6.487 | 0.046 | 0.133 | -0.097 | 0.045 | 0.182 |
| sma50_vs_sma200 | 12613 | 6.487 | 0.033 | 0.099 | -0.073 | 0.035 | 0.135 |
| drawdown_from_26w_high | 12670 | 6.065 | -0.080 | 0.087 | -0.186 | -0.054 | -0.003 |
| realized_vol_126 | 12670 | 6.065 | 0.257 | 0.119 | 0.145 | 0.226 | 0.412 |
| rc_momentum_negative | 12670 | 6.065 | 0.307 | 0.461 | 0.000 | 0.000 | 1.000 |
| ret_6m | 12670 | 6.065 | 0.084 | 0.206 | -0.120 | 0.073 | 0.286 |
| distance_26w_high | 12929 | 4.144 | -0.085 | 0.089 | -0.197 | -0.060 | -0.004 |
| realized_vol_63 | 13078 | 3.040 | 0.253 | 0.129 | 0.136 | 0.220 | 0.404 |
| ret_3m | 13078 | 3.040 | 0.040 | 0.131 | -0.103 | 0.037 | 0.179 |
| return_skew_63 | 13078 | 3.040 | -0.064 | 0.953 | -1.002 | -0.056 | 0.857 |
| return_kurtosis_63 | 13078 | 3.040 | 2.424 | 4.170 | -0.158 | 1.103 | 5.992 |
| downside_vol_63 | 13078 | 3.040 | 0.173 | 0.099 | 0.085 | 0.149 | 0.285 |
| sma50_slope | 13197 | 2.157 | 0.008 | 0.043 | -0.038 | 0.010 | 0.054 |
| support_touches | 13253 | 1.742 | 2.340 | 1.832 | 1.000 | 2.000 | 5.000 |
| rc_support_broken | 13253 | 1.742 | 0.079 | 0.270 | 0.000 | 0.000 | 0.000 |
| support_age_bars | 13253 | 1.742 | 76.093 | 100.580 | 8.000 | 32.000 | 217.000 |
| support_distance_atr | 13253 | 1.742 | 2.027 | 1.997 | 0.121 | 1.571 | 4.561 |
| support_distance_pct | 13253 | 1.742 | 0.103 | 9.136 | 0.002 | 0.032 | 0.104 |
| support_broken | 13253 | 1.742 | 0.079 | 0.270 | 0.000 | 0.000 | 0.000 |
| distance_sma50 | 13294 | 1.438 | 0.010 | 0.063 | -0.060 | 0.011 | 0.077 |
| sma20_vs_sma50 | 13294 | 1.438 | 0.006 | 0.041 | -0.039 | 0.008 | 0.049 |
| ema50_distance | 13294 | 1.438 | 0.009 | 0.053 | -0.052 | 0.011 | 0.066 |
| sma20_slope | 13327 | 1.194 | 0.010 | 0.061 | -0.056 | 0.010 | 0.075 |
| ret_1m | 13344 | 1.068 | 0.012 | 0.074 | -0.070 | 0.012 | 0.093 |
| realized_vol_20 | 13344 | 1.068 | 0.244 | 0.147 | 0.118 | 0.209 | 0.400 |
| distance_sma20 | 13478 | 0.074 | 0.004 | 0.039 | -0.041 | 0.005 | 0.046 |
| ema20_distance | 13478 | 0.074 | 0.003 | 0.033 | -0.034 | 0.005 | 0.038 |
| rsi14 | 13486 | 0.015 | 52.295 | 11.615 | 37.178 | 52.441 | 67.113 |
| atr14_pct | 13486 | 0.015 | 0.022 | 0.010 | 0.013 | 0.019 | 0.034 |

## 3. IC raw (retorno total futuro)

### Horizonte 6M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.139 | -2.258 | 19.526 | 59.809 | DATA_QUALITY_LIMITED |
| fund_shareholder_yield | 0.122 | 3.187 | 32.564 | 33.167 | WEAK |
| fund_fcf_yoy | 0.113 | 2.023 | 24.806 | 48.270 | WEAK |
| fund_accruals_to_assets | -0.106 | -2.994 | 38.231 | 20.836 | PROMISING |
| fund_revenue_yoy | 0.105 | 1.858 | 40.604 | 15.997 | WEAK |
| realized_vol_126 | 0.097 | 1.818 | 93.008 | 6.065 | WEAK |
| fund_debt_to_equity | -0.093 | -2.107 | 30.910 | 36.628 | UNSTABLE |
| fund_debt_to_assets | -0.092 | -2.448 | 35.142 | 27.214 | PROMISING |
| val_fcf_yield_own_pct | 0.092 | 1.856 | 23.655 | 59.384 | DATA_QUALITY_LIMITED |
| val_pe | 0.091 | 1.699 | 34.448 | 28.798 | WEAK |
| fund_cfo_to_net_income | 0.081 | 2.190 | 37.993 | 21.481 | PROMISING |
| val_earnings_yield | -0.079 | -1.445 | 36.940 | 23.724 | WEAK |
| realized_vol_63 | 0.074 | 1.428 | 93.977 | 3.040 | UNSTABLE |
| val_ev_to_sales | 0.070 | 1.446 | 29.857 | 38.387 | WEAK |
| downside_vol_63 | 0.069 | 1.351 | 93.977 | 3.040 | UNSTABLE |
| val_price_to_book | 0.068 | 1.278 | 33.403 | 31.452 | UNSTABLE |
| fund_current_ratio | 0.058 | 1.614 | 43.791 | 9.736 | WEAK |
| rc_drawdown_state | 0.056 | 1.351 | 91.048 | 12.003 | WEAK |
| realized_vol_20 | 0.055 | 1.174 | 95.261 | 1.068 | UNSTABLE |
| atr14_pct | 0.053 | 1.011 | 95.607 | 0.015 | UNSTABLE |
| val_price_to_sales | 0.053 | 1.071 | 37.366 | 22.889 | UNSTABLE |
| val_ev_to_operating_income | 0.051 | 0.896 | 23.496 | 51.408 | DATA_QUALITY_LIMITED |
| drawdown_from_52w_high | -0.048 | -1.079 | 91.048 | 12.003 | WEAK |
| fund_cash_to_assets | 0.048 | 1.238 | 43.388 | 10.528 | WEAK |
| fund_net_income_yoy | -0.044 | -0.950 | 37.045 | 23.446 | WEAK |

### Horizonte 12M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.192 | -2.735 | 19.354 | 59.809 | DATA_QUALITY_LIMITED |
| fund_fcf_yoy | 0.181 | 2.769 | 24.461 | 48.270 | WEAK |
| realized_vol_126 | 0.157 | 2.095 | 93.545 | 6.065 | PROMISING |
| fund_revenue_yoy | 0.153 | 2.499 | 40.297 | 15.997 | PROMISING |
| val_pe | 0.148 | 2.030 | 34.227 | 28.798 | PROMISING |
| val_earnings_yield | -0.138 | -1.879 | 36.742 | 23.724 | WEAK |
| fund_debt_to_assets | -0.137 | -3.252 | 34.820 | 27.214 | PROMISING |
| realized_vol_63 | 0.133 | 1.917 | 94.556 | 3.040 | WEAK |
| fund_shareholder_yield | 0.133 | 2.613 | 32.339 | 33.167 | WEAK |
| fund_accruals_to_assets | -0.130 | -2.529 | 37.906 | 20.836 | PROMISING |
| fund_debt_to_equity | -0.129 | -2.255 | 30.669 | 36.628 | WEAK |
| downside_vol_63 | 0.119 | 1.738 | 94.556 | 3.040 | WEAK |
| atr14_pct | 0.113 | 1.540 | 96.266 | 0.015 | WEAK |
| val_price_to_book | 0.112 | 1.606 | 33.375 | 31.452 | UNSTABLE |
| realized_vol_20 | 0.109 | 1.670 | 95.906 | 1.068 | WEAK |
| val_fcf_yield_own_pct | 0.104 | 1.734 | 23.500 | 59.384 | DATA_QUALITY_LIMITED |
| val_ev_to_operating_income | 0.101 | 1.390 | 23.181 | 51.408 | DATA_QUALITY_LIMITED |
| fund_cfo_to_net_income | 0.099 | 1.968 | 37.750 | 21.481 | WEAK |
| val_ev_to_sales | 0.097 | 1.433 | 29.472 | 38.387 | UNSTABLE |
| val_price_to_sales | 0.079 | 1.289 | 37.148 | 22.889 | UNSTABLE |
| rc_drawdown_state | 0.075 | 1.413 | 91.496 | 12.003 | WEAK |
| drawdown_from_52w_high | -0.073 | -1.183 | 91.496 | 12.003 | WEAK |
| fund_current_ratio | 0.067 | 1.347 | 43.594 | 9.736 | WEAK |
| fund_cash_to_assets | 0.065 | 1.314 | 43.188 | 10.528 | WEAK |
| drawdown_from_26w_high | -0.061 | -0.965 | 93.545 | 6.065 | WEAK |

## 4. IC excess return vs benchmark

### Horizonte 6M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.139 | -2.258 | 19.526 | 59.809 | DATA_QUALITY_LIMITED |
| fund_shareholder_yield | 0.122 | 3.187 | 32.564 | 33.167 | WEAK |
| fund_fcf_yoy | 0.113 | 2.023 | 24.806 | 48.270 | WEAK |
| realized_vol_126 | 0.113 | 2.186 | 91.700 | 6.065 | PROMISING |
| fund_accruals_to_assets | -0.106 | -2.994 | 38.231 | 20.836 | PROMISING |
| fund_revenue_yoy | 0.105 | 1.858 | 40.604 | 15.997 | WEAK |
| fund_debt_to_equity | -0.093 | -2.107 | 30.910 | 36.628 | UNSTABLE |
| fund_debt_to_assets | -0.092 | -2.448 | 35.142 | 27.214 | PROMISING |
| val_fcf_yield_own_pct | 0.092 | 1.856 | 23.655 | 59.384 | DATA_QUALITY_LIMITED |
| val_pe | 0.091 | 1.699 | 34.448 | 28.798 | WEAK |
| realized_vol_63 | 0.090 | 1.815 | 92.000 | 3.040 | WEAK |
| downside_vol_63 | 0.090 | 1.851 | 92.000 | 3.040 | UNSTABLE |
| atr14_pct | 0.087 | 1.758 | 92.852 | 0.015 | WEAK |
| fund_cfo_to_net_income | 0.081 | 2.190 | 37.993 | 21.481 | PROMISING |
| val_earnings_yield | -0.079 | -1.445 | 36.940 | 23.724 | WEAK |
| rc_drawdown_state | 0.073 | 1.883 | 90.968 | 12.003 | WEAK |
| realized_vol_20 | 0.072 | 1.591 | 92.806 | 1.068 | WEAK |
| val_ev_to_sales | 0.070 | 1.446 | 29.857 | 38.387 | WEAK |
| val_price_to_book | 0.068 | 1.278 | 33.403 | 31.452 | UNSTABLE |
| drawdown_from_52w_high | -0.065 | -1.588 | 90.968 | 12.003 | WEAK |
| drawdown_from_26w_high | -0.059 | -1.556 | 91.700 | 6.065 | WEAK |
| fund_current_ratio | 0.058 | 1.614 | 43.791 | 9.736 | WEAK |
| val_price_to_sales | 0.053 | 1.071 | 37.366 | 22.889 | UNSTABLE |
| distance_52w_high | -0.051 | -1.313 | 95.234 | 8.052 | WEAK |
| val_ev_to_operating_income | 0.051 | 0.896 | 23.496 | 51.408 | DATA_QUALITY_LIMITED |

### Horizonte 12M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.192 | -2.735 | 19.354 | 59.809 | DATA_QUALITY_LIMITED |
| fund_fcf_yoy | 0.181 | 2.769 | 24.461 | 48.270 | WEAK |
| realized_vol_126 | 0.176 | 2.514 | 92.163 | 6.065 | PROMISING |
| atr14_pct | 0.157 | 2.328 | 93.359 | 0.015 | PROMISING |
| realized_vol_63 | 0.154 | 2.348 | 92.468 | 3.040 | PROMISING |
| fund_revenue_yoy | 0.153 | 2.499 | 40.297 | 15.997 | PROMISING |
| val_pe | 0.148 | 2.030 | 34.227 | 28.798 | PROMISING |
| downside_vol_63 | 0.141 | 2.250 | 92.468 | 3.040 | PROMISING |
| val_earnings_yield | -0.138 | -1.879 | 36.742 | 23.724 | WEAK |
| fund_debt_to_assets | -0.137 | -3.252 | 34.820 | 27.214 | PROMISING |
| fund_shareholder_yield | 0.133 | 2.613 | 32.339 | 33.167 | WEAK |
| realized_vol_20 | 0.131 | 2.109 | 93.315 | 1.068 | PROMISING |
| fund_accruals_to_assets | -0.130 | -2.529 | 37.906 | 20.836 | PROMISING |
| fund_debt_to_equity | -0.129 | -2.255 | 30.669 | 36.628 | WEAK |
| val_price_to_book | 0.112 | 1.606 | 33.375 | 31.452 | UNSTABLE |
| val_fcf_yield_own_pct | 0.104 | 1.734 | 23.500 | 59.384 | DATA_QUALITY_LIMITED |
| val_ev_to_operating_income | 0.101 | 1.390 | 23.181 | 51.408 | DATA_QUALITY_LIMITED |
| fund_cfo_to_net_income | 0.099 | 1.968 | 37.750 | 21.481 | WEAK |
| val_ev_to_sales | 0.097 | 1.433 | 29.472 | 38.387 | UNSTABLE |
| rc_drawdown_state | 0.093 | 1.824 | 91.410 | 12.003 | WEAK |
| drawdown_from_52w_high | -0.093 | -1.574 | 91.410 | 12.003 | WEAK |
| drawdown_from_26w_high | -0.081 | -1.315 | 92.163 | 6.065 | WEAK |
| val_price_to_sales | 0.079 | 1.289 | 37.148 | 22.889 | UNSTABLE |
| distance_52w_high | -0.078 | -1.383 | 95.932 | 8.052 | WEAK |
| distance_26w_high | -0.071 | -1.196 | 94.049 | 4.144 | WEAK |

## 5. IC vs max drawdown (negativo = más caída si el feature sube)

### Horizonte 6M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| atr14_pct | -0.479 | -15.007 | 95.607 | 0.015 | PROMISING |
| realized_vol_126 | -0.461 | -13.748 | 93.008 | 6.065 | PROMISING |
| realized_vol_63 | -0.460 | -14.537 | 93.977 | 3.040 | PROMISING |
| downside_vol_63 | -0.429 | -12.339 | 93.977 | 3.040 | PROMISING |
| realized_vol_20 | -0.419 | -12.733 | 95.261 | 1.068 | PROMISING |
| val_fcf_yield | 0.236 | 5.620 | 24.642 | 48.944 | WEAK |
| rc_drawdown_state | -0.224 | -6.606 | 91.048 | 12.003 | PROMISING |
| drawdown_from_26w_high | 0.224 | 5.140 | 93.008 | 6.065 | PROMISING |
| drawdown_from_52w_high | 0.221 | 5.244 | 91.048 | 12.003 | PROMISING |
| distance_26w_high | 0.215 | 4.970 | 95.000 | 4.144 | PROMISING |
| distance_52w_high | 0.212 | 4.946 | 95.347 | 8.052 | PROMISING |
| val_earnings_yield | 0.193 | 4.805 | 36.940 | 23.724 | PROMISING |
| fund_dividends_to_fcf | 0.185 | 3.774 | 19.526 | 59.809 | DATA_QUALITY_LIMITED |
| fund_roe | 0.183 | 4.442 | 35.082 | 27.507 | PROMISING |
| fund_dividend_yield | 0.183 | 3.426 | 40.172 | 17.067 | PROMISING |
| fund_revenue_yoy | -0.169 | -4.954 | 40.604 | 15.997 | PROMISING |
| support_distance_pct | -0.156 | -4.856 | 93.926 | 1.742 | PROMISING |
| val_price_to_sales_own_pct | 0.143 | 2.463 | 36.355 | 37.669 | WEAK |
| fund_operating_margin | 0.141 | 4.729 | 35.261 | 27.111 | PROMISING |
| val_price_to_sales | -0.138 | -3.375 | 37.366 | 22.889 | PROMISING |
| fund_cash_to_assets | -0.133 | -3.986 | 43.388 | 10.528 | PROMISING |
| fund_capex_growth_yoy | -0.131 | -3.501 | 29.381 | 39.018 | WEAK |
| fund_fcf_margin | 0.126 | 3.606 | 27.485 | 42.918 | WEAK |
| fund_net_margin | 0.123 | 4.829 | 40.843 | 15.528 | PROMISING |
| val_ev_to_operating_income | -0.123 | -2.182 | 23.496 | 51.408 | DATA_QUALITY_LIMITED |

### Horizonte 12M (top 25 por |IC|; IC y t sobre offsets no solapados)

| feature | IC | t | N medio/mes | missing % | etiqueta |
|---|---|---|---|---|---|
| atr14_pct | -0.447 | -9.178 | 96.266 | 0.015 | PROMISING |
| realized_vol_126 | -0.439 | -8.239 | 93.545 | 6.065 | PROMISING |
| realized_vol_63 | -0.434 | -8.654 | 94.556 | 3.040 | PROMISING |
| downside_vol_63 | -0.412 | -8.166 | 94.556 | 3.040 | PROMISING |
| realized_vol_20 | -0.391 | -7.876 | 95.906 | 1.068 | PROMISING |
| val_fcf_yield | 0.237 | 4.315 | 24.469 | 48.944 | WEAK |
| drawdown_from_26w_high | 0.223 | 3.880 | 93.545 | 6.065 | PROMISING |
| rc_drawdown_state | -0.218 | -4.952 | 91.496 | 12.003 | PROMISING |
| distance_26w_high | 0.216 | 3.790 | 95.650 | 4.144 | PROMISING |
| drawdown_from_52w_high | 0.214 | 4.155 | 91.496 | 12.003 | PROMISING |
| distance_52w_high | 0.206 | 3.889 | 96.051 | 8.052 | PROMISING |
| fund_roe | 0.180 | 2.660 | 34.820 | 27.507 | PROMISING |
| val_earnings_yield | 0.170 | 3.446 | 36.742 | 23.724 | PROMISING |
| fund_dividends_to_fcf | 0.164 | 2.025 | 19.354 | 59.809 | DATA_QUALITY_LIMITED |
| val_price_to_sales_own_pct | 0.164 | 2.673 | 36.048 | 37.669 | WEAK |
| fund_dividend_yield | 0.158 | 2.377 | 39.945 | 17.067 | PROMISING |
| fund_revenue_yoy | -0.157 | -3.442 | 40.297 | 15.997 | PROMISING |
| fund_operating_margin | 0.157 | 3.875 | 35.031 | 27.111 | PROMISING |
| fund_cash_to_assets | -0.152 | -3.145 | 43.188 | 10.528 | PROMISING |
| val_price_to_book_own_pct | 0.146 | 2.779 | 32.308 | 44.824 | WEAK |
| fund_fcf_margin | 0.145 | 2.636 | 27.211 | 42.918 | WEAK |
| val_price_to_sales | -0.143 | -2.393 | 37.148 | 22.889 | UNSTABLE |
| support_distance_pct | -0.136 | -2.930 | 94.492 | 1.742 | PROMISING |
| fund_net_margin | 0.131 | 4.186 | 40.547 | 15.528 | PROMISING |
| val_ev_to_operating_income | -0.129 | -1.705 | 23.181 | 51.408 | DATA_QUALITY_LIMITED |

## 6-8. Deciles, D10−D1 y monotonicidad (excess, DEV)

| feature | H | D10−D1 | monot. deciles | Q5−Q1 | monot. quintiles |
|---|---|---|---|---|---|
| fund_dividends_to_fcf | 6M | -0.034 | -0.734 | -0.047 | -0.891 |
| fund_dividends_to_fcf | 12M | -0.083 | -0.814 | -0.092 | -0.933 |
| fund_shareholder_yield | 6M | 0.077 | 0.662 | 0.046 | 0.748 |
| fund_shareholder_yield | 12M | 0.169 | 0.580 | 0.091 | 0.644 |
| fund_fcf_yoy | 6M | -0.003 | 0.406 | 0.020 | 0.679 |
| fund_fcf_yoy | 12M | 0.031 | 0.500 | 0.060 | 0.726 |
| realized_vol_126 | 6M | 0.134 | 0.812 | 0.090 | 0.892 |
| realized_vol_126 | 12M | 0.343 | 0.807 | 0.226 | 0.888 |
| fund_accruals_to_assets | 6M | -0.072 | -0.753 | -0.066 | -0.805 |
| fund_accruals_to_assets | 12M | -0.117 | -0.689 | -0.146 | -0.768 |
| fund_revenue_yoy | 6M | 0.057 | 0.799 | 0.079 | 0.873 |
| fund_revenue_yoy | 12M | 0.168 | 0.774 | 0.199 | 0.824 |
| fund_debt_to_equity | 6M | -0.027 | -0.357 | -0.024 | -0.440 |
| fund_debt_to_equity | 12M | -0.021 | -0.257 | -0.040 | -0.286 |
| fund_debt_to_assets | 6M | -0.042 | -0.418 | -0.015 | -0.433 |
| fund_debt_to_assets | 12M | -0.055 | -0.369 | -0.016 | -0.355 |
| val_fcf_yield_own_pct | 6M | 0.098 | 0.891 | 0.075 | 0.941 |
| val_fcf_yield_own_pct | 12M | 0.271 | 0.861 | 0.202 | 0.919 |
| val_pe | 6M | 0.082 | 0.706 | 0.059 | 0.783 |
| val_pe | 12M | 0.175 | 0.789 | 0.140 | 0.877 |
| realized_vol_63 | 6M | 0.121 | 0.773 | 0.075 | 0.893 |
| realized_vol_63 | 12M | 0.314 | 0.798 | 0.207 | 0.889 |
| downside_vol_63 | 6M | 0.110 | 0.802 | 0.072 | 0.897 |
| downside_vol_63 | 12M | 0.293 | 0.795 | 0.192 | 0.899 |
| atr14_pct | 6M | 0.101 | 0.841 | 0.067 | 0.921 |
| atr14_pct | 12M | 0.286 | 0.845 | 0.196 | 0.928 |
| fund_cfo_to_net_income | 6M | 0.049 | 0.684 | 0.032 | 0.808 |
| fund_cfo_to_net_income | 12M | 0.087 | 0.668 | 0.059 | 0.861 |
| val_earnings_yield | 6M | -0.095 | -0.806 | -0.091 | -0.817 |
| val_earnings_yield | 12M | -0.324 | -0.808 | -0.257 | -0.840 |

## 9. Robustez no solapada

Para el horizonte H sólo se usan los meses congruentes módulo H (H offsets sin solape) y se reporta la media de los t por offset. Un IC con t<2 en este esquema no se considera evidencia.

## 10-12. Estabilidad por periodo, región y régimen (IC medio excess 6M)

| feature | 2011-16 | 2017-22 | BULL | BEAR | US | EU | ES | ASIA | NA |
|---|---|---|---|---|---|---|---|---|---|
| fund_dividends_to_fcf | -0.186 | -0.087 | -0.131 | -0.040 | -0.139 | — | — | — | — |
| fund_shareholder_yield | 0.144 | 0.098 | 0.099 | 0.158 | 0.122 | — | — | — | — |
| fund_fcf_yoy | 0.066 | 0.159 | 0.117 | 0.110 | 0.113 | — | — | — | — |
| realized_vol_126 | 0.127 | 0.097 | 0.128 | 0.022 | 0.129 | 0.127 | -0.045 | 0.041 | — |
| fund_accruals_to_assets | -0.074 | -0.137 | -0.103 | -0.141 | -0.106 | — | — | — | — |
| fund_revenue_yoy | 0.084 | 0.127 | 0.124 | 0.036 | 0.105 | — | — | — | — |
| fund_debt_to_equity | -0.072 | -0.116 | -0.102 | 0.018 | -0.093 | — | — | — | — |
| fund_debt_to_assets | -0.070 | -0.117 | -0.108 | -0.002 | -0.092 | — | — | — | — |
| val_fcf_yield_own_pct | 0.042 | 0.128 | 0.094 | 0.079 | 0.092 | — | — | — | — |
| val_pe | 0.063 | 0.122 | 0.121 | 0.066 | 0.091 | — | — | — | — |
| realized_vol_63 | 0.097 | 0.083 | 0.120 | 0.005 | 0.109 | 0.119 | -0.064 | 0.031 | — |
| downside_vol_63 | 0.091 | 0.088 | 0.119 | -0.005 | 0.105 | 0.099 | -0.081 | 0.040 | — |
| atr14_pct | 0.103 | 0.068 | 0.119 | 0.014 | 0.104 | 0.115 | -0.038 | 0.020 | — |
| fund_cfo_to_net_income | 0.073 | 0.090 | 0.087 | 0.156 | 0.081 | — | — | — | — |
| val_earnings_yield | -0.070 | -0.088 | -0.111 | -0.028 | -0.079 | — | — | — | — |
| rc_drawdown_state | 0.079 | 0.066 | 0.076 | 0.029 | 0.056 | 0.087 | 0.007 | 0.069 | — |
| realized_vol_20 | 0.075 | 0.069 | 0.104 | 0.006 | 0.084 | 0.100 | -0.045 | 0.014 | — |
| val_ev_to_sales | 0.038 | 0.105 | 0.076 | 0.011 | 0.070 | — | — | — | — |
| val_price_to_book | 0.036 | 0.104 | 0.087 | -0.013 | 0.068 | — | — | — | — |
| drawdown_from_52w_high | -0.070 | -0.059 | -0.072 | -0.033 | -0.058 | -0.054 | 0.011 | -0.046 | — |
| drawdown_from_26w_high | -0.065 | -0.051 | -0.069 | -0.006 | -0.067 | -0.051 | 0.072 | -0.026 | — |
| fund_current_ratio | 0.069 | 0.046 | 0.062 | 0.056 | 0.058 | — | — | — | — |
| val_price_to_sales | 0.009 | 0.102 | 0.071 | -0.001 | 0.053 | — | — | — | — |
| distance_52w_high | -0.066 | -0.036 | -0.061 | -0.022 | -0.050 | -0.063 | 0.066 | -0.024 | — |
| val_ev_to_operating_income | -0.004 | 0.111 | 0.056 | 0.102 | 0.051 | — | — | — | — |

## 13. Redundancia (|Spearman| ≥ 0.85, sólo DEV)

| feature A | feature B | ρ |
|---|---|---|
| support_broken | rc_support_broken | 1.000 |
| risk_alert_h1 | risk_alert_h3 | 1.000 |
| risk_alert_h12 | risk_alert_h24 | 1.000 |
| val_pe | val_earnings_yield | -1.000 |
| risk_alert_h6 | risk_alert_h12 | 0.994 |
| risk_alert_h6 | risk_alert_h24 | 0.994 |
| distance_26w_high | drawdown_from_26w_high | 0.990 |
| val_price_to_sales | val_ev_to_sales | 0.988 |
| distance_52w_high | drawdown_from_52w_high | 0.984 |
| distance_sma50 | ema50_distance | 0.975 |
| distance_sma20 | ema20_distance | 0.975 |
| sma20_slope | sma20_vs_sma50 | 0.955 |
| ema20_distance | rsi14 | 0.946 |
| ret_12m | momentum_12_1 | 0.944 |
| drawdown_from_52w_high | drawdown_from_26w_high | 0.938 |
| realized_vol_63 | downside_vol_63 | 0.938 |
| distance_26w_high | drawdown_from_52w_high | 0.936 |
| fund_operating_margin | fund_net_margin | 0.923 |
| distance_52w_high | distance_26w_high | 0.921 |
| ema50_distance | rsi14 | 0.918 |
| support_distance_pct | support_distance_atr | 0.915 |
| ret_3m | sma50_slope | 0.912 |
| ret_6m | distance_sma200 | 0.910 |
| realized_vol_63 | realized_vol_126 | 0.909 |
| distance_52w_high | drawdown_from_26w_high | 0.907 |
| distance_sma20 | rsi14 | 0.905 |
| realized_vol_20 | atr14_pct | 0.904 |
| fund_buyback_yield | fund_net_equity_issuance | -0.901 |
| rc_momentum_negative | risk_alert_h6 | 0.899 |
| rc_momentum_negative | risk_alert_h12 | 0.899 |
| rc_momentum_negative | risk_alert_h24 | 0.899 |
| distance_sma50 | rsi14 | 0.893 |
| realized_vol_63 | atr14_pct | 0.886 |
| atr14_pct | downside_vol_63 | 0.867 |
| ret_12m | sma200_slope | 0.867 |
| ema20_distance | ema50_distance | 0.862 |
| ret_6m | sma50_vs_sma200 | 0.859 |
| volume_zscore_20 | volume_zscore_63 | 0.856 |
| rc_below_sma200 | risk_alert_h12 | 0.855 |
| rc_below_sma200 | risk_alert_h24 | 0.855 |
| ret_1m | distance_sma50 | 0.855 |
| fund_gross_margin | fund_fcf_margin | 0.854 |
| distance_sma200 | sma50_vs_sma200 | 0.852 |

## 14. Fundamentales continuos: qué componente aporta

Compuesto = media de rangos percentiles orientados a priori (`ORIENT`, fijados antes de ver ningún IC). IC frente a excess 6/12/24M y drawdown 6/12M.

| componente | IC exc 6M | IC exc 12M | IC exc 24M | IC mdd 6M | IC mdd 12M | t 6M | t 12M | t 24M |
|---|---|---|---|---|---|---|---|---|
| comp_profitability | 0.002 | -0.001 | — | 0.107 | 0.111 | 0.042 | -0.065 | — |
| comp_cash_flow | 0.092 | 0.105 | — | 0.016 | 0.025 | 3.269 | 2.274 | — |
| comp_growth | 0.043 | 0.074 | — | -0.114 | -0.089 | 0.839 | 1.263 | — |
| comp_leverage | 0.057 | 0.082 | — | -0.108 | -0.109 | 1.532 | 1.655 | — |
| comp_capital_allocation | 0.041 | 0.017 | — | 0.120 | 0.104 | 0.926 | 0.299 | — |
| comp_valuation | -0.046 | -0.093 | — | 0.124 | 0.111 | -0.894 | -1.404 | — |

## 15. Cobertura SEC de fundamentales (tabla)

Valores XNYS con precios: 53 → {'READY': 33, 'PARTIAL': 15, 'UNSUPPORTED_SECTOR': 4, 'INSUFFICIENT_HISTORY': 1}. No-XNYS: sin fundamentales SEC (`NOT_REGISTERED`, esperado).

| ticker | estado | SIC | cobertura | 1º filing | métricas ausentes |
|---|---|---|---|---|---|
| TXN | READY | 3674 | 0.960 | 2011-02-28 | fund_interest_coverage, fund_net_equity_issuance |
| PG | READY | 2840 | 0.860 | 2011-01-31 | fund_debt_to_equity, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_roe |
| UPS | READY | 4210 | 0.820 | 2011-02-28 | fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| CRM | READY | 7372 | 0.980 | 2011-03-24 | fund_net_equity_issuance |
| WMT | READY | 5331 | 0.900 | 2011-03-31 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| INTU | READY | 7372 | 0.920 | 2011-03-01 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| DIS | READY | 7990 | 0.860 | 2019-05-09 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| KO | READY | 2080 | 0.960 | 2011-02-28 |  |
| CAT | PARTIAL | 3531 | 0.760 | 2011-02-23 | fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance, fund_net_income_yoy, fund_roe |
| JNJ | READY | 2834 | 0.940 | 2011-02-25 | fund_dividends_to_fcf, fund_net_equity_issuance |
| BA | READY | 3721 | 0.840 | 2011-02-09 | fund_interest_coverage |
| AMZN | READY | 5961 | 0.860 | 2011-01-28 | fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| WFC | UNSUPPORTED_SECTOR | 6021 | — | 2011-02-25 |  |
| IBM | READY | 3570 | 0.860 | 2011-02-22 | fund_interest_coverage, fund_net_equity_issuance, fund_operating_income_yoy, fund_operating_margin |
| MCD | READY | 5812 | 0.860 | 2011-02-25 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| ADBE | READY | 7372 | 0.900 | 2011-01-27 | fund_dividend_yield, fund_dividends_to_fcf, fund_net_equity_issuance, fund_shareholder_yield |
| QCOM | PARTIAL | 3663 | 0.780 | 2011-01-27 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_gross_margin |
| COST | READY | 5331 | 0.980 | 2011-03-17 | fund_net_equity_issuance |
| NEE | PARTIAL | 4911 | 0.640 | 2011-02-28 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_gross_margin |
| AVGO | READY | 3674 | 0.980 | 2018-06-15 | fund_interest_coverage |
| NFLX | READY | 7841 | 0.900 | 2011-02-18 | fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability |
| AMGN | READY | 2836 | 0.900 | 2011-02-28 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| ORCL | READY | 7372 | 0.920 | 2011-03-29 |  |
| XOM | INSUFFICIENT_HISTORY | 2911 | 0.160 | 2026-08-03 | fund_accruals_to_assets, fund_buyback_yield, fund_capex_growth_yoy, fund_capex_to_assets, fund_cfo_to_net_income, fund_dividends_to_fcf |
| NVDA | PARTIAL | 3674 | 0.820 | 2011-03-17 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_net_equity_issuance |
| GOOGL | READY | 7370 | 0.820 | 2015-10-30 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| TMO | READY | 3829 | 0.920 | 2011-02-25 | fund_gross_margin, fund_gross_profitability |
| CVX | PARTIAL | 2911 | 0.640 | 2011-02-24 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_gross_margin |
| UNH | UNSUPPORTED_SECTOR | 6324 | — | 2011-02-11 |  |
| MA | READY | 7389 | 0.820 | 2011-02-24 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| LLY | PARTIAL | 2834 | 0.620 | 2011-02-22 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_gross_margin |
| MRK | PARTIAL | 2834 | 0.760 | 2011-02-28 | fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance, fund_operating_income_yoy, fund_operating_margin |
| UNP | READY | 4011 | 0.920 | 2011-02-07 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| HON | READY | 3724 | 0.860 | 2011-02-11 | fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance |
| GE | PARTIAL | 3600 | 0.780 | 2011-02-28 | fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_operating_income_yoy, fund_operating_margin |
| CSCO | READY | 3576 | 1.000 | 2011-02-23 |  |
| PEP | PARTIAL | 2080 | 0.820 | 2011-02-22 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_net_equity_issuance |
| TSLA | READY | 3711 | 0.880 | 2011-08-15 | fund_buyback_yield, fund_dividends_to_fcf, fund_net_equity_issuance, fund_shareholder_yield |
| SPGI | PARTIAL | 7320 | 0.740 | 2011-02-23 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_gross_margin |
| META | READY | 7370 | 0.840 | 2012-08-01 | fund_gross_margin, fund_gross_profitability, fund_shareholder_yield |
| LMT | READY | 3760 | 0.960 | 2011-02-25 | fund_net_equity_issuance |
| ABBV | READY | 2834 | 0.860 | 2013-05-09 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| JPM | UNSUPPORTED_SECTOR | 6021 | — | 2011-03-01 |  |
| VZ | PARTIAL | 4813 | 0.620 | 2011-02-28 | fund_buyback_yield, fund_capex_growth_yoy, fund_capex_to_assets, fund_debt_to_equity, fund_dividends_to_fcf, fund_fcf_margin |
| V | PARTIAL | 7389 | 0.640 | 2011-02-03 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy, fund_gross_margin |
| ACN | PARTIAL | 7389 | 0.720 | 2011-03-28 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance, fund_shareholder_yield |
| ABT | READY | 2834 | 0.900 | 2011-02-18 | fund_gross_margin, fund_gross_profitability, fund_net_equity_issuance |
| BAC | UNSUPPORTED_SECTOR | 6021 | — | 2011-02-28 |  |
| RTX | READY | 3724 | 0.940 | 2011-02-10 | fund_gross_margin, fund_gross_profitability |
| LIN | READY | 2810 | 0.940 | 2017-10-31 | fund_gross_margin, fund_gross_profitability |
| HD | PARTIAL | 5211 | 0.840 | 2011-03-25 | fund_capex_growth_yoy, fund_capex_to_assets, fund_dividends_to_fcf, fund_fcf_margin, fund_fcf_yoy |
| PFE | PARTIAL | 2834 | 0.760 | 2011-02-28 | fund_dividends_to_fcf, fund_gross_margin, fund_gross_profitability, fund_interest_coverage, fund_net_equity_issuance, fund_operating_income_yoy |
| LOW | READY | 5211 | 0.940 | 2011-03-29 | fund_net_equity_issuance |

## 16. Features candidatas (PROMISING, a validar fuera de muestra)

| feature | H | IC | t | N medio |
|---|---|---|---|---|
| realized_vol_126 | 6 | 0.113 | 2.186 | 91.700 |
| fund_cfo_to_net_income | 6 | 0.081 | 2.190 | 37.993 |
| fund_accruals_to_assets | 6 | -0.106 | -2.994 | 38.231 |
| fund_debt_to_assets | 6 | -0.092 | -2.448 | 35.142 |
| realized_vol_20 | 12 | 0.131 | 2.109 | 93.315 |
| realized_vol_63 | 12 | 0.154 | 2.348 | 92.468 |
| realized_vol_126 | 12 | 0.176 | 2.514 | 92.163 |
| atr14_pct | 12 | 0.157 | 2.328 | 93.359 |
| downside_vol_63 | 12 | 0.141 | 2.250 | 92.468 |
| fund_accruals_to_assets | 12 | -0.130 | -2.529 | 37.906 |
| fund_revenue_yoy | 12 | 0.153 | 2.499 | 40.297 |
| fund_debt_to_assets | 12 | -0.137 | -3.252 | 34.820 |
| val_pe | 12 | 0.148 | 2.030 | 34.227 |

## 17. Features débiles

atr14_normalized, atr14_pct, distance_26w_high, distance_52w_high, drawdown_from_26w_high, drawdown_from_52w_high, fund_buyback_yield, fund_capex_growth_yoy, fund_cash_to_assets, fund_cfo_to_net_income, fund_current_ratio, fund_debt_to_equity, fund_dividend_yield, fund_fcf_margin, fund_fcf_yoy, fund_net_income_yoy, fund_revenue_yoy, fund_roe, fund_shareholder_yield, rc_drawdown_state, rc_elevated_volatility, realized_vol_20, realized_vol_63, return_kurtosis_63, rsi14, support_age_bars, support_distance_pct, support_touches, val_earnings_yield, val_ev_to_sales, val_fcf_yield, val_pe, val_pe_own_pct, volume_change_63

## 18. Features problemáticas (UNSTABLE / DATA_QUALITY_LIMITED)

| feature | H | etiqueta | missing % | N medio |
|---|---|---|---|---|
| ret_1m | 6 | UNSTABLE | 1.068 | 92.806 |
| ret_3m | 6 | UNSTABLE | 3.040 | 92.000 |
| ret_6m | 6 | UNSTABLE | 6.065 | 91.700 |
| ret_12m | 6 | UNSTABLE | 12.003 | 90.968 |
| momentum_12_1 | 6 | UNSTABLE | 12.003 | 90.968 |
| distance_sma20 | 6 | UNSTABLE | 0.074 | 92.852 |
| distance_sma50 | 6 | UNSTABLE | 1.438 | 93.271 |
| distance_sma200 | 6 | UNSTABLE | 6.487 | 94.770 |
| sma20_slope | 6 | UNSTABLE | 1.194 | 92.672 |
| sma50_slope | 6 | UNSTABLE | 2.157 | 93.477 |
| sma200_slope | 6 | UNSTABLE | 7.206 | 95.000 |
| ema20_distance | 6 | UNSTABLE | 0.074 | 92.852 |
| ema50_distance | 6 | UNSTABLE | 1.438 | 93.271 |
| sma20_vs_sma50 | 6 | UNSTABLE | 1.438 | 93.271 |
| sma50_vs_sma200 | 6 | UNSTABLE | 6.487 | 94.770 |
| distance_26w_high | 6 | UNSTABLE | 4.144 | 93.485 |
| return_skew_63 | 6 | UNSTABLE | 3.040 | 92.000 |
| return_kurtosis_63 | 6 | UNSTABLE | 3.040 | 92.000 |
| downside_vol_63 | 6 | UNSTABLE | 3.040 | 92.000 |
| volume_change_20 | 6 | UNSTABLE | 26.779 | 68.455 |
| volume_change_63 | 6 | UNSTABLE | 29.248 | 68.754 |
| volume_zscore_20 | 6 | UNSTABLE | 25.942 | 68.585 |
| volume_zscore_63 | 6 | UNSTABLE | 27.417 | 68.504 |
| rsi14 | 6 | UNSTABLE | 0.015 | 92.852 |
| support_touches | 6 | UNSTABLE | 1.742 | 91.407 |
| support_broken | 6 | UNSTABLE | 1.742 | 91.407 |
| support_distance_atr | 6 | UNSTABLE | 1.742 | 91.407 |
| rc_below_sma200 | 6 | UNSTABLE | 6.487 | 94.770 |
| rc_momentum_negative | 6 | UNSTABLE | 6.065 | 91.700 |
| rc_support_broken | 6 | UNSTABLE | 1.742 | 91.407 |
| rc_elevated_volatility | 6 | UNSTABLE | 9.319 | 93.887 |
| risk_alert_h1 | 6 | UNSTABLE | 6.487 | 94.770 |
| risk_alert_h3 | 6 | UNSTABLE | 6.487 | 94.770 |
| risk_alert_h6 | 6 | UNSTABLE | 6.487 | 94.770 |
| risk_alert_h12 | 6 | UNSTABLE | 6.487 | 94.770 |
| risk_alert_h24 | 6 | UNSTABLE | 6.487 | 94.770 |
| fund_gross_profitability | 6 | DATA_QUALITY_LIMITED | 70.117 | 14.403 |
| fund_operating_margin | 6 | UNSTABLE | 27.111 | 35.261 |
| fund_net_margin | 6 | UNSTABLE | 15.528 | 40.843 |
| fund_gross_margin | 6 | DATA_QUALITY_LIMITED | 70.938 | 13.985 |
| fund_roa | 6 | UNSTABLE | 17.361 | 39.910 |
| fund_roe | 6 | UNSTABLE | 27.507 | 35.082 |
| fund_operating_income_yoy | 6 | UNSTABLE | 30.836 | 33.440 |
| fund_debt_to_equity | 6 | UNSTABLE | 36.628 | 30.910 |
| fund_interest_coverage | 6 | UNSTABLE | 38.475 | 29.746 |
| fund_net_equity_issuance | 6 | DATA_QUALITY_LIMITED | 77.463 | 10.880 |
| fund_dividends_to_fcf | 6 | DATA_QUALITY_LIMITED | 59.809 | 19.526 |
| fund_capex_to_assets | 6 | UNSTABLE | 38.592 | 29.597 |
| val_price_to_sales | 6 | UNSTABLE | 22.889 | 37.366 |
| val_price_to_book | 6 | UNSTABLE | 31.452 | 33.403 |
| val_ev_to_operating_income | 6 | DATA_QUALITY_LIMITED | 51.408 | 23.496 |
| val_pe_own_pct | 6 | UNSTABLE | 43.548 | 32.909 |
| val_price_to_sales_own_pct | 6 | UNSTABLE | 37.669 | 36.355 |
| val_price_to_book_own_pct | 6 | UNSTABLE | 44.824 | 32.400 |
| val_fcf_yield_own_pct | 6 | DATA_QUALITY_LIMITED | 59.384 | 23.655 |
| ret_1m | 12 | UNSTABLE | 1.068 | 93.315 |
| ret_3m | 12 | UNSTABLE | 3.040 | 92.468 |
| ret_6m | 12 | UNSTABLE | 6.065 | 92.163 |
| ret_12m | 12 | UNSTABLE | 12.003 | 91.410 |
| momentum_12_1 | 12 | UNSTABLE | 12.003 | 91.410 |
| distance_sma20 | 12 | UNSTABLE | 0.074 | 93.359 |
| distance_sma50 | 12 | UNSTABLE | 1.438 | 93.810 |
| distance_sma200 | 12 | UNSTABLE | 6.487 | 95.429 |
| sma20_slope | 12 | UNSTABLE | 1.194 | 93.173 |
| sma50_slope | 12 | UNSTABLE | 2.157 | 94.032 |
| sma200_slope | 12 | UNSTABLE | 7.206 | 95.678 |
| ema20_distance | 12 | UNSTABLE | 0.074 | 93.359 |
| ema50_distance | 12 | UNSTABLE | 1.438 | 93.810 |
| sma20_vs_sma50 | 12 | UNSTABLE | 1.438 | 93.810 |
| sma50_vs_sma200 | 12 | UNSTABLE | 6.487 | 95.429 |
| atr14_normalized | 12 | UNSTABLE | 8.682 | 96.147 |
| return_skew_63 | 12 | UNSTABLE | 3.040 | 92.468 |
| volume_change_20 | 12 | UNSTABLE | 26.779 | 68.465 |
| volume_zscore_20 | 12 | UNSTABLE | 25.942 | 68.594 |
| volume_zscore_63 | 12 | UNSTABLE | 27.417 | 68.540 |
| support_broken | 12 | UNSTABLE | 1.742 | 91.836 |
| support_distance_atr | 12 | UNSTABLE | 1.742 | 91.836 |
| rc_below_sma200 | 12 | UNSTABLE | 6.487 | 95.429 |
| rc_momentum_negative | 12 | UNSTABLE | 6.065 | 92.163 |
| rc_support_broken | 12 | UNSTABLE | 1.742 | 91.836 |
| risk_alert_h1 | 12 | UNSTABLE | 6.487 | 95.429 |
| risk_alert_h3 | 12 | UNSTABLE | 6.487 | 95.429 |
| risk_alert_h6 | 12 | UNSTABLE | 6.487 | 95.429 |
| risk_alert_h12 | 12 | UNSTABLE | 6.487 | 95.429 |
| risk_alert_h24 | 12 | UNSTABLE | 6.487 | 95.429 |
| fund_gross_profitability | 12 | DATA_QUALITY_LIMITED | 70.117 | 14.273 |
| fund_operating_margin | 12 | UNSTABLE | 27.111 | 35.031 |
| fund_net_margin | 12 | UNSTABLE | 15.528 | 40.547 |
| fund_gross_margin | 12 | DATA_QUALITY_LIMITED | 70.938 | 13.836 |
| fund_roa | 12 | UNSTABLE | 17.361 | 39.570 |
| fund_fcf_margin | 12 | UNSTABLE | 42.918 | 27.211 |
| fund_operating_income_yoy | 12 | UNSTABLE | 30.836 | 33.219 |
| fund_interest_coverage | 12 | UNSTABLE | 38.475 | 29.539 |
| fund_dividend_yield | 12 | UNSTABLE | 17.067 | 39.945 |
| fund_buyback_yield | 12 | UNSTABLE | 27.698 | 34.836 |
| fund_net_equity_issuance | 12 | DATA_QUALITY_LIMITED | 77.463 | 10.756 |
| fund_dividends_to_fcf | 12 | DATA_QUALITY_LIMITED | 59.809 | 19.354 |
| fund_capex_to_assets | 12 | UNSTABLE | 38.592 | 29.328 |
| val_price_to_sales | 12 | UNSTABLE | 22.889 | 37.148 |
| val_price_to_book | 12 | UNSTABLE | 31.452 | 33.375 |
| val_ev_to_sales | 12 | UNSTABLE | 38.387 | 29.472 |
| val_ev_to_operating_income | 12 | DATA_QUALITY_LIMITED | 51.408 | 23.181 |
| val_price_to_sales_own_pct | 12 | UNSTABLE | 37.669 | 36.048 |
| val_price_to_book_own_pct | 12 | UNSTABLE | 44.824 | 32.308 |
| val_fcf_yield_own_pct | 12 | DATA_QUALITY_LIMITED | 59.384 | 23.500 |

## RISK_ALERT: señal de riesgo, no de venta

| alerta | H | tasa alerta | IC vs mdd | t | OR dd≥10% | OR dd≥15% | OR dd≥20% | P(dd15|alerta) | P(dd15|sin) |
|---|---|---|---|---|---|---|---|---|---|
| risk_alert_h6 | 6M | 0.258 | -0.080 | -1.924 | 1.42 [1.29, 1.56] | 1.75 [1.60, 1.90] | 1.80 [1.64, 1.98] | 0.479 | 0.345 |
| risk_alert_h12 | 6M | 0.260 | -0.078 | -1.878 | 1.40 [1.28, 1.53] | 1.73 [1.59, 1.88] | 1.78 [1.62, 1.96] | 0.477 | 0.345 |
| risk_alert_h6 | 12M | 0.258 | -0.078 | -1.331 | 1.20 [1.05, 1.37] | 1.45 [1.33, 1.59] | 1.32 [1.21, 1.44] | 0.656 | 0.568 |
| risk_alert_h12 | 12M | 0.260 | -0.077 | -1.318 | 1.17 [1.03, 1.33] | 1.44 [1.32, 1.57] | 1.31 [1.20, 1.43] | 0.655 | 0.568 |
| risk_alert_h6 | 24M | 0.258 | — | — | 1.69 [1.17, 2.46] | 1.71 [1.51, 1.94] | 1.40 [1.27, 1.53] | 0.866 | 0.790 |
| risk_alert_h12 | 24M | 0.260 | — | — | 1.60 [1.11, 2.31] | 1.68 [1.49, 1.90] | 1.39 [1.26, 1.52] | 0.864 | 0.790 |

## Baselines ingenuos

| H | n | base_rate_outperform | accuracy_always_outperform | auc_momentum_12_1 | auc_low_vol_63 | auc_ret_6m | auc_risk_alert_inverse |
|---|---|---|---|---|---|---|---|
| 6M | 12537 | 0.558 | 0.558 | 0.493 | 0.479 | 0.490 | 0.491 |
| 12M | 11952 | 0.573 | 0.573 | 0.504 | 0.466 | 0.503 | 0.497 |

## 19. Gates antes de ML

| gate | estado | detalle |
|---|---|---|
| DEV_ROWS | READY | 24842 dev rows with a 12M target (need >= 5000) |
| SECURITIES | BLOCKED | 97 securities with snapshots (need >= 100) |
| BENCHMARKS | READY | benchmarks with excess returns: {'SPY': True, '^IBEX': True, 'URTH': True} |
| CANONICAL_UNIVERSE | BLOCKED | the universe is the CURRENT research set (survivorship, UNIVERSE_NOT_PIT_MEMBERSHIP); D02_MONTHLY_RESEARCH_READY=false |
| FUNDAMENTAL_COVERAGE | READY | 48 securities with >= 36 months of OK fundamentals (need >= 30) |
| FILING_INTELLIGENCE_NOT_REQUIRED | READY | contract only; not an input to V0 models |

## 20. Recomendación para el primer baseline ML

**No entrenar todavía.** Gates bloqueados: SECURITIES, CANONICAL_UNIVERSE. Primer experimento recomendado: comparar `EQUITY_6M_LOGISTIC_V0` y `EQUITY_12M_ELASTIC_NET_V0` (contratos en `research/model_contracts.py`) contra los baselines de arriba con folds expansivos purgados sobre DEV; descartar si no los superan fuera de muestra.
