# FIRST_EQUITY_RETURN_12M_V0

**RESEARCH_DEV_ONLY · ADAPTIVE_DEV_EXPLORATORY · dev_adaptive_iteration=2 · RETROSPECTIVE_UNVALIDATED**

Este experimento se diseñó tras observar Direction V0/V1. No es confirmación independiente. Holdout/OOT: cero resultados accedidos. No champion, producción, señales live ni portfolio.

## Diseño congelado

Dataset, cohortes y folds exactamente iguales a Direction V0/V1. Target existente ResearchTarget.excess_total_return (campo congelado excess_return): total return security menos SPY total return, misma moneda USD, horizonte/entrada/madurez intactos. No target nuevo ni winsorización.

R0: media TRAIN. R2/R3/R4: familias 18/18/44 intactas. Grid alpha={.001,.003,.01,.03,.1,.3,1}, l1_ratio={0,.25,.5,.75,1}. l1_ratio=0 usa Ridge alpha=n*alpha por equivalencia de objetivos. Elastic Net cyclic, max_iter=100000, tol=1e-8.

Inner CV causal 1/3/5 bloques de seis meses, TRAIN expansivo mínimo 18 meses, H12+embargo1 y madurez efectiva. Preprocessing de V0 en cada inner TRAIN. Selección sólo MAE OOF; RMSE diagnóstico. Empate 1e-12: alpha mayor, menor número medio de coeficientes activos, l1_ratio menor.

R0 constante: IC/spread mensual NA, no cero. Ranking del pooled puede reflejar cambios entre folds; para selección interesa IC cross-sectional mensual. Spreads son diagnósticos, no estrategia.

## Distribuciones antes de fit

# Distribuciones previas al fit

Retornos en fracción: 0.07 = +7 puntos porcentuales. Dataset y target congelados; no se modifica ningún valor.

| Fold | Role | n | mean | median | std_ddof0 | p01 | p05 | p25 | p75 | p95 | p99 | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | TEST | 476 | 0.074585 | 0.048936 | 0.267738 | -0.538538 | -0.270153 | -0.065826 | 0.185739 | 0.452950 | 0.985629 | -0.762191 | 2.185175 |
| F1 | TRAIN | 1318 | 0.101613 | 0.058003 | 0.280769 | -0.285187 | -0.181648 | -0.050535 | 0.179021 | 0.509134 | 1.583020 | -0.463314 | 2.563373 |
| F2 | TEST | 510 | 0.013659 | -0.035789 | 0.299867 | -0.524232 | -0.362282 | -0.179396 | 0.151544 | 0.548095 | 0.925829 | -0.711158 | 1.965149 |
| F2 | TRAIN | 1735 | 0.104315 | 0.068703 | 0.260665 | -0.302481 | -0.181248 | -0.042513 | 0.197496 | 0.448891 | 1.202270 | -0.496658 | 2.563373 |
| F3 | TEST | 521 | 0.019410 | 0.012455 | 0.240764 | -0.462798 | -0.352684 | -0.135632 | 0.154152 | 0.413193 | 0.689143 | -0.617938 | 1.164645 |
| F3 | TRAIN | 2209 | 0.097056 | 0.066540 | 0.255507 | -0.338062 | -0.202656 | -0.045093 | 0.196871 | 0.439487 | 1.118359 | -0.685522 | 2.563373 |

Extremos/outliers descriptivos completos en el JSON. Se conservan todas las filas. SD ddof=0; cuantiles lineales.


## Resultados por fold antes de pooled

### F1

| Modelo | N | MAE | RMSE | R² | Pearson | POOLED_OBSERVATION_IC | MEAN_MONTHLY_CROSS_SECTIONAL_IC | spread mensual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | 476 | 0.184233 | 0.269098 | -0.010191 | NA | NA | NA | NA |
| R2 | 476 | 0.207071 | 0.285961 | -0.140764 | 0.052254 | 0.038659 | 0.040554 | 0.049749 |
| R3 | 476 | 0.185016 | 0.263426 | 0.031945 | 0.252969 | 0.210676 | 0.202199 | 0.132686 |
| R4 | 476 | 0.207931 | 0.295526 | -0.218356 | 0.160311 | 0.164573 | 0.154972 | 0.167714 |

IC y spread: resumen mensual

| Modelo | Diagnóstico | N meses | mean | median | positive_fraction | min | max | SD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R0 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R2 | mean_monthly_cross_sectional_ic | 12 | 0.040554 | -0.019732 | 0.500000 | -0.475873 | 0.426266 | 0.256811 |
| R2 | monthly_spread | 12 | 0.049749 | 0.007634 | 0.500000 | -0.294446 | 0.393116 | 0.203036 |
| R3 | mean_monthly_cross_sectional_ic | 12 | 0.202199 | 0.219667 | 0.916667 | -0.170150 | 0.390244 | 0.158640 |
| R3 | monthly_spread | 12 | 0.132686 | 0.097020 | 0.750000 | -0.152778 | 0.593178 | 0.201395 |
| R4 | mean_monthly_cross_sectional_ic | 12 | 0.154972 | 0.218798 | 0.750000 | -0.341285 | 0.373734 | 0.200753 |
| R4 | monthly_spread | 12 | 0.167714 | 0.196673 | 0.833333 | -0.245967 | 0.479643 | 0.196337 |

### F2

| Modelo | N | MAE | RMSE | R² | Pearson | POOLED_OBSERVATION_IC | MEAN_MONTHLY_CROSS_SECTIONAL_IC | spread mensual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | 510 | 0.245939 | 0.313271 | -0.091398 | NA | NA | NA | NA |
| R2 | 510 | 0.245939 | 0.313271 | -0.091398 | NA | NA | NA | NA |
| R3 | 510 | 0.245939 | 0.313271 | -0.091398 | NA | NA | NA | NA |
| R4 | 510 | 0.245939 | 0.313271 | -0.091398 | NA | NA | NA | NA |

IC y spread: resumen mensual

| Modelo | Diagnóstico | N meses | mean | median | positive_fraction | min | max | SD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R0 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R2 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R2 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R3 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R3 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R4 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R4 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |

### F3

| Modelo | N | MAE | RMSE | R² | Pearson | POOLED_OBSERVATION_IC | MEAN_MONTHLY_CROSS_SECTIONAL_IC | spread mensual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | 521 | 0.196363 | 0.252974 | -0.104004 | NA | NA | NA | NA |
| R2 | 521 | 0.196363 | 0.252974 | -0.104004 | NA | NA | NA | NA |
| R3 | 521 | 0.196363 | 0.252974 | -0.104004 | NA | NA | NA | NA |
| R4 | 521 | 0.196363 | 0.252974 | -0.104004 | NA | NA | NA | NA |

IC y spread: resumen mensual

| Modelo | Diagnóstico | N meses | mean | median | positive_fraction | min | max | SD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R0 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R2 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R2 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R3 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R3 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R4 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R4 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |

### POOLED_DEV_OOF

| Modelo | N | MAE | RMSE | R² | Pearson | POOLED_OBSERVATION_IC | MEAN_MONTHLY_CROSS_SECTIONAL_IC | spread mensual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | 1507 | 0.209309 | 0.279659 | -0.059085 | 0.006033 | -0.043308 | NA | NA |
| R2 | 1507 | 0.216522 | 0.284896 | -0.099120 | 0.070693 | 0.039142 | 0.040554 | 0.049749 |
| R3 | 1507 | 0.209556 | 0.277949 | -0.046166 | 0.149843 | 0.076230 | 0.202199 | 0.132686 |
| R4 | 1507 | 0.216794 | 0.287963 | -0.122911 | 0.104434 | 0.046513 | 0.154972 | 0.167714 |

IC y spread: resumen mensual

| Modelo | Diagnóstico | N meses | mean | median | positive_fraction | min | max | SD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R0 | mean_monthly_cross_sectional_ic | 0 | NA | NA | NA | NA | NA | NA |
| R0 | monthly_spread | 0 | NA | NA | NA | NA | NA | NA |
| R2 | mean_monthly_cross_sectional_ic | 12 | 0.040554 | -0.019732 | 0.500000 | -0.475873 | 0.426266 | 0.256811 |
| R2 | monthly_spread | 12 | 0.049749 | 0.007634 | 0.500000 | -0.294446 | 0.393116 | 0.203036 |
| R3 | mean_monthly_cross_sectional_ic | 12 | 0.202199 | 0.219667 | 0.916667 | -0.170150 | 0.390244 | 0.158640 |
| R3 | monthly_spread | 12 | 0.132686 | 0.097020 | 0.750000 | -0.152778 | 0.593178 | 0.201395 |
| R4 | mean_monthly_cross_sectional_ic | 12 | 0.154972 | 0.218798 | 0.750000 | -0.341285 | 0.373734 | 0.200753 |
| R4 | monthly_spread | 12 | 0.167714 | 0.196673 | 0.833333 | -0.245967 | 0.479643 | 0.196337 |

## Quintiles por fold y pooled

Rankings calculados dentro de cada mes; empates promedio, sin desempate por identidad o resultado. N y medias de tabla ponderan filas; spread principal promedia meses por igual.

| Fold | Modelo | Q | N | exceso medio | exceso mediano | outperform rate |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | R0 | 1 | 0 | NA | NA | NA |
| F1 | R0 | 2 | 0 | NA | NA | NA |
| F1 | R0 | 3 | 0 | NA | NA | NA |
| F1 | R0 | 4 | 0 | NA | NA | NA |
| F1 | R0 | 5 | 0 | NA | NA | NA |
| F1 | R2 | 1 | 96 | 0.034156 | 0.036096 | 0.562500 |
| F1 | R2 | 2 | 95 | 0.052193 | 0.030314 | 0.578947 |
| F1 | R2 | 3 | 94 | 0.039749 | 0.045502 | 0.659574 |
| F1 | R2 | 4 | 95 | 0.162886 | 0.162629 | 0.705263 |
| F1 | R2 | 5 | 96 | 0.083905 | 0.019153 | 0.531250 |
| F1 | R3 | 1 | 96 | 0.036919 | 0.049430 | 0.572917 |
| F1 | R3 | 2 | 95 | -0.024863 | -0.027149 | 0.431579 |
| F1 | R3 | 3 | 94 | 0.026271 | 0.049424 | 0.638298 |
| F1 | R3 | 4 | 95 | 0.163884 | 0.094438 | 0.810526 |
| F1 | R3 | 5 | 96 | 0.169605 | 0.088096 | 0.583333 |
| F1 | R4 | 1 | 96 | 0.016416 | 0.005102 | 0.500000 |
| F1 | R4 | 2 | 95 | 0.014288 | 0.024511 | 0.610526 |
| F1 | R4 | 3 | 94 | 0.053215 | 0.045024 | 0.659574 |
| F1 | R4 | 4 | 95 | 0.104113 | 0.074643 | 0.652632 |
| F1 | R4 | 5 | 96 | 0.184130 | 0.078684 | 0.614583 |
| F2 | R0 | 1 | 0 | NA | NA | NA |
| F2 | R0 | 2 | 0 | NA | NA | NA |
| F2 | R0 | 3 | 0 | NA | NA | NA |
| F2 | R0 | 4 | 0 | NA | NA | NA |
| F2 | R0 | 5 | 0 | NA | NA | NA |
| F2 | R2 | 1 | 0 | NA | NA | NA |
| F2 | R2 | 2 | 0 | NA | NA | NA |
| F2 | R2 | 3 | 0 | NA | NA | NA |
| F2 | R2 | 4 | 0 | NA | NA | NA |
| F2 | R2 | 5 | 0 | NA | NA | NA |
| F2 | R3 | 1 | 0 | NA | NA | NA |
| F2 | R3 | 2 | 0 | NA | NA | NA |
| F2 | R3 | 3 | 0 | NA | NA | NA |
| F2 | R3 | 4 | 0 | NA | NA | NA |
| F2 | R3 | 5 | 0 | NA | NA | NA |
| F2 | R4 | 1 | 0 | NA | NA | NA |
| F2 | R4 | 2 | 0 | NA | NA | NA |
| F2 | R4 | 3 | 0 | NA | NA | NA |
| F2 | R4 | 4 | 0 | NA | NA | NA |
| F2 | R4 | 5 | 0 | NA | NA | NA |
| F3 | R0 | 1 | 0 | NA | NA | NA |
| F3 | R0 | 2 | 0 | NA | NA | NA |
| F3 | R0 | 3 | 0 | NA | NA | NA |
| F3 | R0 | 4 | 0 | NA | NA | NA |
| F3 | R0 | 5 | 0 | NA | NA | NA |
| F3 | R2 | 1 | 0 | NA | NA | NA |
| F3 | R2 | 2 | 0 | NA | NA | NA |
| F3 | R2 | 3 | 0 | NA | NA | NA |
| F3 | R2 | 4 | 0 | NA | NA | NA |
| F3 | R2 | 5 | 0 | NA | NA | NA |
| F3 | R3 | 1 | 0 | NA | NA | NA |
| F3 | R3 | 2 | 0 | NA | NA | NA |
| F3 | R3 | 3 | 0 | NA | NA | NA |
| F3 | R3 | 4 | 0 | NA | NA | NA |
| F3 | R3 | 5 | 0 | NA | NA | NA |
| F3 | R4 | 1 | 0 | NA | NA | NA |
| F3 | R4 | 2 | 0 | NA | NA | NA |
| F3 | R4 | 3 | 0 | NA | NA | NA |
| F3 | R4 | 4 | 0 | NA | NA | NA |
| F3 | R4 | 5 | 0 | NA | NA | NA |
| POOLED | R0 | 1 | 0 | NA | NA | NA |
| POOLED | R0 | 2 | 0 | NA | NA | NA |
| POOLED | R0 | 3 | 0 | NA | NA | NA |
| POOLED | R0 | 4 | 0 | NA | NA | NA |
| POOLED | R0 | 5 | 0 | NA | NA | NA |
| POOLED | R2 | 1 | 96 | 0.034156 | 0.036096 | 0.562500 |
| POOLED | R2 | 2 | 95 | 0.052193 | 0.030314 | 0.578947 |
| POOLED | R2 | 3 | 94 | 0.039749 | 0.045502 | 0.659574 |
| POOLED | R2 | 4 | 95 | 0.162886 | 0.162629 | 0.705263 |
| POOLED | R2 | 5 | 96 | 0.083905 | 0.019153 | 0.531250 |
| POOLED | R3 | 1 | 96 | 0.036919 | 0.049430 | 0.572917 |
| POOLED | R3 | 2 | 95 | -0.024863 | -0.027149 | 0.431579 |
| POOLED | R3 | 3 | 94 | 0.026271 | 0.049424 | 0.638298 |
| POOLED | R3 | 4 | 95 | 0.163884 | 0.094438 | 0.810526 |
| POOLED | R3 | 5 | 96 | 0.169605 | 0.088096 | 0.583333 |
| POOLED | R4 | 1 | 96 | 0.016416 | 0.005102 | 0.500000 |
| POOLED | R4 | 2 | 95 | 0.014288 | 0.024511 | 0.610526 |
| POOLED | R4 | 3 | 94 | 0.053215 | 0.045024 | 0.659574 |
| POOLED | R4 | 4 | 95 | 0.104113 | 0.074643 | 0.652632 |
| POOLED | R4 | 5 | 96 | 0.184130 | 0.078684 | 0.614583 |

## R4 frente a M4R: métricas comunes de ranking

M4R: CURRENT_BEST_DIRECTION_RESEARCH_BASELINE, sin validación ni promoción. Mismas TEST rows y mismo retorno realizado. No se compara MAE con LogLoss.

| Fold | Modelo | IC observaciones | IC mensual | spread mensual |
| --- | --- | --- | --- | --- |
| F1 | R4 | 0.164573 | 0.154972 | 0.167714 |
| F1 | M4R | 0.259534 | 0.291194 | 0.229008 |
| F2 | R4 | NA | NA | NA |
| F2 | M4R | 0.240852 | 0.206700 | 0.100277 |
| F3 | R4 | NA | NA | NA |
| F3 | M4R | -0.007321 | -0.067335 | -0.037166 |
| POOLED | R4 | 0.046513 | 0.154972 | 0.167714 |
| POOLED | M4R | 0.175070 | 0.143519 | 0.097373 |

Quintiles M4R de referencia

| Fold | Q | N | exceso medio | exceso mediano | outperform rate |
| --- | --- | --- | --- | --- | --- |
| F1 | 1 | 96 | -0.024911 | -0.007718 | 0.479167 |
| F1 | 2 | 95 | 0.063473 | 0.055523 | 0.610526 |
| F1 | 3 | 94 | -0.017239 | -0.008186 | 0.457447 |
| F1 | 4 | 95 | 0.146225 | 0.106469 | 0.673684 |
| F1 | 5 | 96 | 0.204097 | 0.139379 | 0.812500 |
| F2 | 1 | 103 | 0.011706 | -0.067259 | 0.436893 |
| F2 | 2 | 101 | -0.069357 | -0.097384 | 0.326733 |
| F2 | 3 | 102 | -0.014184 | -0.066364 | 0.382353 |
| F2 | 4 | 101 | 0.027980 | -0.012427 | 0.465347 |
| F2 | 5 | 103 | 0.110547 | 0.085543 | 0.611650 |
| F3 | 1 | 107 | 0.038902 | 0.018367 | 0.551402 |
| F3 | 2 | 103 | 0.018895 | 0.042184 | 0.592233 |
| F3 | 3 | 101 | 0.031488 | 0.001965 | 0.514851 |
| F3 | 4 | 103 | 0.004044 | -0.005260 | 0.485437 |
| F3 | 5 | 107 | 0.003807 | -0.004473 | 0.495327 |
| POOLED | 1 | 306 | 0.009728 | -0.007779 | 0.490196 |
| POOLED | 2 | 299 | 0.003248 | 0.002249 | 0.508361 |
| POOLED | 3 | 297 | 0.000381 | -0.018538 | 0.451178 |
| POOLED | 4 | 299 | 0.057304 | 0.020797 | 0.538462 |
| POOLED | 5 | 306 | 0.102572 | 0.068345 | 0.633987 |

## Coeficientes, sparsity y estabilidad

| Modelo | Fold | alpha | l1_ratio | nonzero | L1 | L2 |
| --- | --- | --- | --- | --- | --- | --- |
| R2 | F1 | 1.000000 | 0.000000 | 19 | 0.205299 | 0.055569 |
| R2 | F2 | 1.000000 | 0.250000 | 0 | 0.000000 | 0.000000 |
| R2 | F3 | 1.000000 | 0.250000 | 0 | 0.000000 | 0.000000 |
| R3 | F1 | 1.000000 | 0.000000 | 31 | 0.301925 | 0.095842 |
| R3 | F2 | 1.000000 | 0.250000 | 0 | 0.000000 | 0.000000 |
| R3 | F3 | 1.000000 | 0.250000 | 0 | 0.000000 | 0.000000 |
| R4 | F1 | 0.010000 | 0.500000 | 26 | 0.537267 | 0.177817 |
| R4 | F2 | 1.000000 | 0.250000 | 0 | 0.000000 | 0.000000 |
| R4 | F3 | 1.000000 | 0.250000 | 0 | 0.000000 | 0.000000 |

Vectores completos, signos y frecuencia nozero por feature en COEFFICIENTS.json; parámetros/preprocessing de todos los candidatos en MODELS.json.gz. No interpretar causalmente; cero estable no demuestra señal. No se eliminan features.

## Bootstrap ADAPTIVE_DEV_EXPLORATORY_INTERVAL

1000 muestras pareadas de meses completos. Dependencia dentro del mes preservada; no toda la dependencia serial H12. Deltas MAE/RMSE negativos favorecen el primer modelo; IC/spread positivos lo favorecen. R0 no tiene ranking mensual: sus comparaciones IC/spread quedan NA.

| Comparación | Métrica | N réplicas disponibles | IC95 inferior | IC95 superior |
| --- | --- | --- | --- | --- |
| R2-R0 | mae | 1000 | 0.002802 | 0.012180 |
| R2-R0 | monthly_rank_ic | 0 | NA | NA |
| R2-R0 | rmse | 1000 | -0.000869 | 0.012372 |
| R2-R0 | spread | 0 | NA | NA |
| R3-R0 | mae | 1000 | -0.001763 | 0.002184 |
| R3-R0 | monthly_rank_ic | 0 | NA | NA |
| R3-R0 | rmse | 1000 | -0.006216 | 0.002187 |
| R3-R0 | spread | 0 | NA | NA |
| R4-R0 | mae | 1000 | 0.003212 | 0.012452 |
| R4-R0 | monthly_rank_ic | 0 | NA | NA |
| R4-R0 | rmse | 1000 | 0.001580 | 0.015592 |
| R4-R0 | spread | 0 | NA | NA |
| R4-R2 | mae | 1000 | -0.002403 | 0.002931 |
| R4-R2 | monthly_rank_ic | 1000 | 0.029594 | 0.206349 |
| R4-R2 | rmse | 1000 | -0.000852 | 0.007212 |
| R4-R2 | spread | 1000 | 0.054380 | 0.175790 |
| R4-R3 | mae | 1000 | 0.003640 | 0.011193 |
| R4-R3 | monthly_rank_ic | 1000 | -0.081184 | -0.011214 |
| R4-R3 | rmse | 1000 | 0.005001 | 0.015402 |
| R4-R3 | spread | 1000 | -0.023978 | 0.090247 |

## F3 y clasificación

RETURN_SIGNAL_UNSTABLE

La etiqueta aplica la regla descriptiva congelada antes de fit; consultar conclusiones Q1–Q10. No es gate operativo.

## Presupuesto DEV

No continuar indefinidamente reutilizando DEV. Considerar como máximo un siguiente experimento estructural predeclarado; no iniciar V3 automáticamente.
