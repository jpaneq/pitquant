# ADR-0061 — Retorno continuo 12M: Elastic Net causal sobre el dataset congelado

Desde 6953df7. Experimentos Direction V0/V1 inmutables. Nuevo ID
FIRST_EQUITY_RETURN_12M_V0, dev_adaptive_iteration=2. Sin promoción.
M4R se referencia como CURRENT_BEST_DIRECTION_RESEARCH_BASELINE, no champion.

Target existente ResearchTarget.excess_total_return, guardado como excess_return
por el archivo V0: security total return menos SPY ETF_PROXY total return en USD.
Misma entrada/H12/madurez/benchmark/FX; no reingesta ni redefinición. Benchmark es
proxy ETF, no índice oficial. Datos originales/folds/cohortes/familias intactos.
Distribuciones TRAIN/TEST se publican antes de fit; no se capan ni escalan labels.

R0 media TRAIN. R2 PRICE18, R3 FUNDAMENTALS18, R4 COMBINED44.
Grid cerrado alpha={.001,.003,.01,.03,.1,.3,1}, l1_ratio={0,.25,.5,.75,1}.
Elastic Net minimiza ||y-Xb||²/(2n)+alpha*l1_ratio*||b||1
+alpha*(1-l1_ratio)*||b||²/2. Para l1_ratio=0 se usa Ridge(svd) con
alpha_Ridge=n*alpha; evita coordinate descent sin L1 y resuelve el mismo objetivo.
Intercepto sin penalizar; preprocessing V0 en TRAIN correspondiente. Elastic Net:
cyclic, max_iter=100000, tol=1e-8; cero efectivo abs(coef)<=1e-12.

Inner CV reutiliza el diseño causal V1: min18 meses, bloques6 completos, paso6,
H12+embargo1 y madurez efectiva. F1/F2/F3 tienen 1/3/5 validaciones.
MAE OOF por filas selecciona hiperparámetros; RMSE sólo diagnóstico.
Empate abs<=1e-12: alpha mayor, menor media nozero de fits internos, l1_ratio menor.
Nada se decide por TEST IC/spread. Grid y regla descriptiva de clasificación se
congelan con SHA/semillas/hash antes del entrenamiento real.

Métricas de error y Pearson/IC de observaciones separadas del IC cross-sectional
mensual. Quintiles mensuales con rango promedio de empates. Spreads promedian
meses por igual; tablas de quintiles ponderan filas. R0 constante no tiene ranking:
IC/spread NA, nunca cero ficticio. Modelos que colapsen a constante también NA.

1000 muestras pareadas de meses para errores e IC/spread; ranking compara sólo
intersecciones de meses con ambas métricas definidas y declara sus N. R0 sólo
permite deltas MAE/RMSE. ADAPTIVE_DEV_EXPLORATORY_INTERVAL; no independencia
entre targets H12 solapados ni confirmación independiente tras observar V0/V1.

Parámetros de todos los fits internos y seleccionados en JSON comprimido de
forma determinista/inmutable; OOF con target/predicción/rango/provenance/hash.
Refit independiente y repetición completa tolerancia1e-12; ninguna probabilidad
inventada, portfolio, operativa, modificación de datos o apertura holdout/OOT.
Ante bug real data/PIT/preprocessing/fold: STOP e invalidar, no reparar en silencio.

Presupuesto DEV: después evaluar como máximo un siguiente experimento estructural
predeclarado. No iniciar automáticamente V3 ni seguir adaptando indefinidamente.
