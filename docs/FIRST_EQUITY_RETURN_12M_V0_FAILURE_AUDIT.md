# Auditoría del fallo del modelo Return 12M

CASE E — MIXED

Recomendación: NO_FURTHER_MODEL_EXPERIMENT_JUSTIFIED

Auditoría sin ajustes nuevos: 315 candidatos, 945 ajustes internos archivados. Iteración DEV permanece en 2. Holdout y OOT: cero. Fuentes originales verificadas por SHA-256 antes y después.

## Selección y ranking interno

| Fold/modelo | Margen MAE | Mejor cero MAE | Mejor no cero MAE | IC mensual mejor no cero | Pareto (MAE/IC agrupado) |
|---|---:|---:|---:|---:|---|
| F1/R2 | 0.000209286 | 0.193504 | 0.193294 | 0.272839 | 1.0/0.0 |
| F1/R3 | 0.000557349 | 0.193504 | 0.189215 | 0.204402 | 0.003/0.75, 0.003/1.0, 0.01/0.5, 0.1/0.25, 1.0/0.0 |
| F1/R4 | 0.000169558 | 0.193504 | 0.189802 | 0.317528 | 0.01/0.5 |
| F2/R2 | 0 | 0.163704 | 0.163728 | 0.225112 | 0.03/1.0, 0.1/0.25, 0.1/1.0, 0.3/0.5, 0.3/0.75, 0.3/1.0, 1.0/0.0, 1.0/0.25, 1.0/0.5, 1.0/0.75, 1.0/1.0 |
| F2/R3 | 0 | 0.163704 | 0.16464 | 0.0670323 | 0.1/0.25, 0.1/0.5, 0.1/0.75, 0.1/1.0, 0.3/0.25, 0.3/0.5, 0.3/0.75, 0.3/1.0, 1.0/0.25, 1.0/0.5, 1.0/0.75, 1.0/1.0 |
| F2/R4 | 0 | 0.163704 | 0.16464 | 0.0670323 | 0.1/0.75, 0.1/1.0, 0.3/0.25, 0.3/0.5, 0.3/0.75, 0.3/1.0, 1.0/0.25, 1.0/0.5, 1.0/0.75, 1.0/1.0 |
| F3/R2 | 0 | 0.166454 | 0.166468 | 0.225112 | 0.03/0.75, 0.03/1.0, 0.1/0.0, 0.1/0.25, 0.1/1.0, 0.3/0.0, 0.3/0.5, 0.3/0.75, 0.3/1.0, 1.0/0.0, 1.0/0.25, 1.0/0.5, 1.0/0.75, 1.0/1.0 |
| F3/R3 | 0 | 0.166454 | 0.167143 | 0.00992548 | 0.003/0.5, 0.003/0.75, 0.01/0.25, 0.03/0.0, 0.1/0.0, 0.1/0.75, 0.1/1.0, 0.3/0.0, 0.3/0.25, 0.3/0.5, 0.3/0.75, 0.3/1.0, 1.0/0.0, 1.0/0.25, 1.0/0.5, 1.0/0.75, 1.0/1.0 |
| F3/R4 | 0 | 0.166454 | 0.167143 | 0.00992548 | 0.001/0.0, 0.003/0.0, 0.003/0.75, 0.003/1.0, 0.01/0.0, 0.01/0.5, 0.01/0.75, 0.01/1.0, 0.03/0.0, 0.03/0.25, 0.03/0.5, 0.03/0.75, 0.03/1.0, 0.1/0.25, 0.1/0.75, 0.1/1.0, 0.3/0.5, 0.3/0.75, 0.3/1.0, 1.0/0.25, 1.0/0.5, 1.0/0.75, 1.0/1.0 |

El margen ordena MAE sin redondeo; el selector original conserva tolerancia 1e-12, alpha mayor, menor complejidad y menor l1_ratio. Un margen cero puede deberse a varios candidatos constantes idénticos. No se cambia el ganador. Complejidad no cero significa media de ajustes internos; no implica que el ajuste exterior no seleccionado exista.

## Colapso de coeficientes

| Fold/modelo | Máximo gradiente | Umbral L1 | Condición cero |
|---|---:|---:|---|
| F1/R2 | 0.100247 | 0 | False |
| F1/R3 | 0.166126 | 0 | False |
| F1/R4 | 0.166126 | 0.005 | False |
| F2/R2 | 0.0589856 | 0.25 | True |
| F2/R3 | 0.14233 | 0.25 | True |
| F2/R4 | 0.14233 | 0.25 | True |
| F3/R2 | 0.0413639 | 0.25 | True |
| F3/R3 | 0.110138 | 0.25 | True |
| F3/R4 | 0.110138 | 0.25 | True |

Con intercepto sin penalizar, el óptimo cero requiere max |X centradaᵀ y centrado / n| ≤ alpha × l1_ratio. Se reconstruye X con los parámetros archivados; no se estiman estadísticas nuevas. Las columnas numéricas tienen escala archivada; los indicadores de faltantes permanecen sin estandarizar.

## Colas y drift

| Fold | TRAIN/TEST media | TEST desviación | Top 10% / 5% / 1% error cuadrático interno R4 seleccionado |
|---|---|---:|---|
| F1 | 0.101613 / 0.0745855 | 0.267738 | 52.4955% / 36.7019% / 13.0832% |
| F2 | 0.104315 / 0.0136593 | 0.299867 | 52.6867% / 39.0288% / 16.6794% |
| F3 | 0.0970556 / 0.0194104 | 0.240764 | 53.7982% / 41.2896% / 19.3769% |

Drift descriptivo: `{"F1_vs_F2": {"ks_distance": 0.2110644257703081, "standardized_mean_difference": -0.21433512312299313}, "F1_vs_F3": {"ks_distance": 0.12316327682704559, "standardized_mean_difference": -0.2167057701353905}}`. No se publican p-values IID: los retornos de 12 meses se solapan.

## Evidencia y límites

`{"consistent_candidates": {"F2": {"R2": ["0.01/0.5", "0.01/0.75", "0.01/1.0", "0.03/0.25", "0.03/0.5", "0.03/0.75", "0.03/1.0", "0.1/0.0", "0.1/0.25", "0.1/0.5", "0.1/0.75", "0.1/1.0", "0.3/0.0", "0.3/0.25", "1.0/0.0"], "R3": ["0.01/0.75", "0.01/1.0", "0.03/0.25", "0.03/0.5", "0.03/0.75", "0.03/1.0", "0.1/0.25", "0.1/0.5", "1.0/0.0"], "R4": ["0.03/0.5", "0.03/1.0", "0.1/0.25"]}, "F3": {"R2": ["0.003/1.0", "0.01/0.25", "0.01/0.5", "0.01/0.75", "0.01/1.0", "0.03/0.25", "0.03/0.5", "0.1/0.0", "0.1/1.0", "0.3/0.0", "1.0/0.0"], "R3": ["0.001/0.0", "0.001/0.25", "0.001/0.5", "0.001/0.75", "0.001/1.0", "0.003/0.0", "0.003/0.25", "0.003/0.5", "0.003/0.75", "0.003/1.0", "0.01/0.0", "0.01/0.25", "0.01/0.5", "0.01/0.75", "0.01/1.0", "0.03/0.0", "0.03/0.25", "0.03/0.5", "0.03/0.75", "0.03/1.0", "0.1/0.0", "0.1/0.25", "0.3/0.0", "1.0/0.0"], "R4": ["0.001/0.0", "0.001/0.25", "0.001/0.5", "0.001/0.75", "0.001/1.0", "0.003/0.0", "0.003/0.25", "0.003/0.5", "0.003/0.75", "0.003/1.0", "0.01/0.0", "0.01/0.25", "0.01/0.5", "0.01/0.75", "0.01/1.0", "0.03/0.0", "0.03/0.25", "0.03/0.5", "0.1/0.0", "0.3/0.0", "1.0/0.0"]}}, "raw_features_positive_majority_both_folds": ["sma50_vs_sma200", "downside_vol_63", "fund_roa", "fund_fcf_margin", "fund_cfo_to_net_income", "fund_revenue_yoy", "fund_shareholder_yield", "val_pe_own_pct", "rc_support_broken"], "objective_mismatch_criterion": true, "outlier_dominance_criterion": false, "total_breakdown_criterion": false, "regime_dependence": "insufficient independent months/replication for definitive causal attribution", "raw_features_sign_changes": ["ret_1m", "ret_3m", "ret_6m", "ret_12m", "momentum_12_1", "distance_sma20", "distance_sma50", "distance_sma200", "sma50_vs_sma200", "realized_vol_63", "realized_vol_126", "atr14_pct", "volume_zscore_20", "rsi14", "fund_gross_margin", "fund_operating_margin", "fund_net_margin", "fund_roe", "fund_cfo_to_net_income", "fund_accruals_to_assets", "fund_shareholder_yield", "val_fcf_yield", "val_pe_own_pct", "risk_alert_h6", "risk_alert_h12", "rc_below_sma200", "rc_momentum_negative", "rc_support_broken", "rc_drawdown_state", "support_distance_atr"], "reused_inner_period_warning": "F2 and F3 inner OOF share 2017-2018 months; positive available-month IC is not independent replication. Best nonzero R2 has defined IC in only the same six 2017 months in both folds. Best nonzero R3/R4 IC turns negative in the three latest inner periods."}`


Objective trade-off exists, but archived inner periods overlap and recent R3/R4 ranking deteriorates. Raw PRICE/RISK signs change, F3 Direction fails, and F3 regime lacks BEAR counterfactual. No evidence isolates one loss/objective intervention likely to repair forward stability. Do not consume last structural iteration merely by changing algorithm.

## Señal temporal, familias y sectores

| Familia | Media de IC individuales F1 / F2 / F3 | Features con signo estable |
|---|---|---|
| PRICE | -0.0660619 / 0.164558 / -0.0261706 | 4 |
| FUNDAMENTALS | 0.0378261 / 0.0649992 / 0.0351858 | 9 |
| RISK | 0.0935342 / -0.0497131 / -0.0293823 | 0 |

Estas medias no indican que una familia con IC negativo carezca de señal: el signo económico difiere entre features. No se reorientan ni seleccionan features.

| Fold | Dispersión mensual media std / IQR / P90−P10 | Edad TRAIN días | IC R4 global / dentro sector |
|---|---|---:|---|
| F1 | 0.24749 / 0.261999 / 0.5122 | 933.934 | 0.154972 / 0.0701294 |
| F2 | 0.283526 / 0.329789 / 0.647315 | 1125.06 | NA / NA |
| F3 | 0.234215 / 0.278879 / 0.526566 | 1297.99 | NA / NA |

F1 R4 reduce su IC al comparar dentro de sector, compatible con componente sectorial. F2/F3 permanecen NA por predicción constante. Menor dispersión F3 no demuestra ausencia intrínseca de señal.

F3 contiene únicamente BULL; no permite contrastar BULL/BEAR dentro de ese fold. F1 y F2 sí contienen ambos, pero sector, tiempo y régimen están confundidos. No se justifica atribuir el fallo exclusivamente al régimen.

## Direction y Return

Sobre las mismas 476 filas F1: Pearson 0.580815, Spearman 0.771549. Coincidencia media del quintil superior 0.458333, inferior 0.645833. F2/F3 Return constante: comparación de ranking indefinida.

M4R AUC congelado: F1 0.613252, F2 0.600629, F3 0.491293. Su componente fundamental tiene mayor contribución logit absoluta F1; esto no prueba atribución causal ni equivale a rendimiento de un modelo por familia.

## Squared-loss, MAE y colas

La función ElasticNet minimiza MSE/(2) + alpha*l1_ratio*norma L1 + alpha*(1-l1_ratio)*norma L2²/2. La selección compara MAE fuera de muestra. El JSON permite comparar el candidato con RMSE mínimo y el seleccionado por MAE, sin cambiarlo. Errores TRAIN son in-sample y no justifican selección.

Los bins por rango absoluto retienen todos los targets, incluidas colas; los límites usan floor y top 1/5/10% ceil. Las colas influyen materialmente pero no satisfacen el umbral predeclarado de dominancia >50% del error cuadrático en el top1% de F2 y F3. No se justifica Huber solo por observar extremos.


## IC raw por feature (medias mensuales)

| Feature | F1 | F2 | F3 | Mismo signo |
|---|---:|---:|---:|---|
| ret_1m | -0.0887349 | 0.0711774 | -0.0976223 | False |
| ret_3m | -0.124943 | 0.133393 | -0.0695317 | False |
| ret_6m | -0.141651 | 0.137587 | 0.00872506 | False |
| ret_12m | -0.18003 | 0.115889 | 0.0335783 | False |
| momentum_12_1 | -0.152309 | 0.0978415 | 0.0491776 | False |
| distance_sma20 | -0.0694164 | 0.0605597 | -0.110939 | False |
| distance_sma50 | -0.116045 | 0.111738 | -0.119996 | False |
| distance_sma200 | -0.166726 | 0.146531 | -0.041774 | False |
| sma50_vs_sma200 | -0.134474 | 0.150693 | 0.0173089 | False |
| distance_52w_high | -0.19477 | -0.033701 | -0.0668416 | True |
| drawdown_from_52w_high | -0.216811 | -0.0537151 | -0.0656003 | True |
| realized_vol_20 | 0.0613909 | 0.378648 | 0.0104009 | True |
| realized_vol_63 | 0.111763 | 0.405616 | -0.0138152 | False |
| realized_vol_126 | 0.121924 | 0.474732 | -0.016027 | False |
| atr14_pct | 0.115231 | 0.433412 | -0.0100265 | False |
| downside_vol_63 | 0.147957 | 0.337836 | 0.0621775 | True |
| volume_zscore_20 | -0.0422131 | -0.0875915 | 0.0808776 | False |
| rsi14 | -0.119256 | 0.0813984 | -0.121143 | False |
| fund_gross_margin | 0.0934478 | 0.188351 | -0.0895781 | False |
| fund_operating_margin | 0.0453638 | -0.0681009 | 0.0266765 | False |
| fund_net_margin | 0.0772177 | -0.0128336 | -0.0244297 | False |
| fund_roa | 0.153809 | 0.116993 | 0.0170189 | True |
| fund_roe | 0.0788162 | -0.0606266 | 0.00283522 | False |
| fund_fcf_margin | 0.00367395 | 0.0656702 | 0.129747 | True |
| fund_cfo_to_net_income | -0.073736 | 0.113658 | 0.162377 | False |
| fund_accruals_to_assets | 0.0129915 | -0.269714 | -0.236292 | False |
| fund_revenue_yoy | 0.22542 | 0.229181 | 0.108198 | True |
| fund_net_income_yoy | -0.0660408 | -0.210374 | -0.188924 | True |
| fund_debt_to_assets | -0.0655262 | -0.00985813 | -0.0220831 | True |
| fund_current_ratio | 0.0165078 | 0.281373 | 0.0201052 | True |
| fund_shareholder_yield | -0.0503172 | 0.0574222 | 0.170711 | False |
| val_pe | 0.146734 | 0.35727 | 0.0579871 | True |
| val_price_to_sales | 0.121463 | 0.307711 | 0.00291588 | True |
| val_price_to_book | 0.229303 | 0.17216 | 0.0121788 | True |
| val_fcf_yield | -0.20703 | -0.219464 | 0.28093 | False |
| val_pe_own_pct | -0.0612275 | 0.131169 | 0.202971 | False |
| risk_alert_h6 | 0.173779 | -0.120313 | -0.0286011 | False |
| risk_alert_h12 | 0.173779 | -0.120313 | -0.0286011 | False |
| rc_below_sma200 | 0.135619 | -0.122273 | -0.0626773 | False |
| rc_momentum_negative | 0.159672 | -0.0993939 | -0.0625492 | False |
| rc_support_broken | -0.0746862 | 0.0232123 | 0.0149491 | False |
| rc_elevated_volatility | 0.0765904 | -0.0450963 | NA | False |
| rc_drawdown_state | 0.163411 | 0.0359964 | -0.00355198 | False |
| support_distance_atr | -0.0598902 | 0.0504764 | -0.0346447 | False |

## Relación entre errores e IC de candidatos

| Fold/modelo | MAE vs IC agrupado | MAE vs IC mensual | RMSE vs IC mensual | Pareto mensual |
|---|---:|---:|---:|---|
| F1/R2 | -0.917959 | -0.931268 | -0.667876 | 1.0/0.0 |
| F1/R3 | -0.157572 | -0.0359465 | 0.137601 | 0.003/0.75, 0.003/1.0, 0.01/0.25, 0.01/0.5, 0.1/0.25, 1.0/0.0 |
| F1/R4 | -0.729088 | -0.716901 | -0.743485 | 0.01/0.5 |
| F2/R2 | -0.166145 | -0.782938 | -0.771952 | 0.1/1.0 |
| F2/R3 | 0.729207 | 0.174743 | 0.0693844 | 0.1/0.25, 0.1/0.5, 0.3/0.5 |
| F2/R4 | 0.0880964 | -0.719483 | -0.743752 | 0.3/0.25, 0.3/0.5 |
| F3/R2 | 0.896026 | -0.307492 | -0.308472 | 0.1/1.0 |
| F3/R3 | 0.933079 | 0.832221 | 0.827927 | 0.003/0.5, 0.003/0.75, 0.03/0.5, 0.03/0.75, 0.1/0.25, 0.3/0.5, 1.0/0.0 |
| F3/R4 | 0.963111 | 0.719595 | 0.724331 | 0.003/1.0, 0.01/0.5, 0.01/0.75, 0.01/1.0, 0.03/0.25, 0.03/0.5, 0.3/0.5, 1.0/0.0 |

Atención: candidatos constantes dentro de cada periodo interno pueden tener IC agrupado por cambiar el intercepto entre periodos. Por eso el Pareto agrupado solicitado y el Pareto mensual se publican por separado. Los meses con IC indefinido no se convierten en cero; la cobertura debe acompañar cada media.

- DEV adaptively inspected; overlapping H12 labels prevent IID significance claims.
- TRAIN replay is in-sample, never OOF; no unselected candidate outer TEST predictions generated.
- Archived USD/TOTAL_RETURN/SPY and target/binary/hash contracts checked. Original corporate-action and vendor price legs are not present in this frozen dataset: absence of upstream vendor/CA bugs cannot be certified. No internal mismatch detected.
- Within-sector uses existing coarse sector_group, not a fitted neutralized model.
- Pareto/ranking candidates are diagnostics, not a retrospectively selected challenger.
- Raw family means describe feature IC distributions, not composite prediction scores.

## Tablas completas y reproducibilidad

El JSON contiene los 315 candidatos y las 945 tablas internas con MAE, MSE, RMSE, Pearson, Spearman, normas, complejidad, métricas TRAIN in-sample y validación, descomposición de colas, Pareto, márgenes, KKT, IC raw mensual y TRAIN por antigüedad, familias, regímenes, sectores, extremos y coincidencia de quintiles Direction/Return.

No se construyen predicciones TEST de candidatos no seleccionados. El IC dentro de sector es mensual, con N ≥ 5 y cobertura explícita. Las medias de familias describen los IC individuales; no son scores nuevos. La edad TRAIN se mide en días respecto a la primera decisión TEST; edad interna respecto a inner fit_at.

Las tablas raw TRAIN permiten comprobar variación por año/mes sin volver a entrenar ni ponderar. El análisis por régimen conserva BULL/BEAR/UNKNOWN del snapshot y no demuestra causalidad frente a tiempo/sector.

Ejecutar `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_equity_return.py`. Escritura exclusiva: si existe un resultado diferente se rechaza. Un siguiente ajuste requerirá aprobación humana y será la última iteración estructural 3 sobre estos folds; el holdout permanece sellado.
