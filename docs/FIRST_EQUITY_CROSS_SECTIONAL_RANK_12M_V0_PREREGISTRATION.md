# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0 — prerregistro

Estado: **PREREGISTERED_NOT_RUN / NOT_RUN**. Esta tarea congela los datos y el diseño. No contiene un ejecutor de entrenamiento, ni calcula etiquetas, retornos, predicciones o métricas reales. Partimos exactamente de `9929b0d`. La iteración actual sigue siendo 2; un futuro ajuste autorizado sería la **iteración adaptativa 3 y el último experimento estructural DEV**. Después habrá revisión humana, sin V4/V5 automáticos.

## Pregunta y congelación

¿Puede PITQuant ordenar el universo contemporáneamente disponible por su rendimiento relativo a doce meses? La salida investigada es un orden; no es una probabilidad calibrada, retorno absoluto ni recomendación de operar.

Se acepta el cierre de datos: ninguna reparación, expansión o nuevo mapping. El dataset `US_LARGE_CAP_RESEARCH_DATASET_V1_FROZEN` conserva membresía, identidades, precios, acciones corporativas, fundamentales, `sec-tags-5`, benchmark, elegibilidad de features, constructibilidad de etiquetas y cohorte científica. Una corrección posterior exige **otro dataset y otro experimento**.

La cohorte contiene **16.717 observaciones científicas únicas de emisor-mes**, 85 meses y tamaños mensuales 147 / 162 / 187 / 246,6 / 252 (mínimo/P10/mediana/P90/máximo). El mínimo del gate no implica reducir el tamaño de la muestra: se usan todas las observaciones elegibles.

`EXPANDED_US_RESEARCH_COVERAGE_V1`: al menos 100 emisores únicos por mes, cobertura de membresía verificada ≥50%, ≥5 sectores, mayor sector ≤60% y tres mayores ≤90%. **85/85 meses pasan**. Denominador: emisores únicos con membresía válida, incluidas familias financieras no soportadas; identidades no resueltas se documentan aparte. Son requisitos de calidad y amplitud definidos sin resultados de modelos, no garantías de potencia estadística.

## Qué queda retenido y cómo se verifica

El manifiesto del dataset contiene cada capa y su SHA-256; referencia el candidato target-free original, precios históricos originales más la serie adicional, originales archivados por contenido y una copia independiente APFS de la base de investigación. La copia tiene permisos de solo lectura y debe abrirse `mode=ro; immutable=1`; nunca se debe ejecutar contra la base mutable candidata. No se copia ni escribe la base de producto. Las acciones conocidas estrictamente antes de T0 afectan las features; la futura etiqueta madura conservará la semántica existente de retorno total realizado, incluidos los dividendos y acciones del horizonte que correspondan, sin incorporarlos a las features de T0.

La base retenida y los originales se verifican como bytes opacos, sin consultar tablas de outcomes ni interpretar valores futuros. Los archivos de origen pueden contener registros posteriores a DEV; su existencia en un archivo **no autoriza su uso**. La futura ejecución debe aplicar los guards PIT y de holdout al leerlos. Este paquete es una congelación reproducible de entradas y elegibilidad, no una matriz de entrenamiento ya etiquetada. Requiere los originales locales retenidos; el manifiesto Git por sí solo no sustituye esos archivos.

`write_once` acepta únicamente replay idéntico. Los verificadores detectan cambios en contratos/capas y opcionalmente comprueban los bytes locales retenidos. Las huellas de los 45 artefactos anteriores y de sus motores se preservan. No se modifican BTC, Filing Intelligence, Trade Planning, Simulation, champion ni master.

## Muestra y folds exteriores exactos

Purge H12, embargo 1 y madurez de target y `label_available_at` estrictamente anteriores al fit permanecen como en V1. La convención inclusiva original cuenta 37/49/61 meses TRAIN. No se rediseña esa geometría.

| Fold | TRAIN | TEST | Meses TRAIN/TEST | Filas TRAIN/TEST | Emisores TRAIN min/P10/med/P90/max | TEST min/P10/med/P90/max |
|---|---|---|---|---|---|---|
| F1 | 2014-09 → 2017-09 | 2018-10 → 2019-09 | 37/12 | 6191/2470 | 147/153.6/168.0/178.0/180 | 189/190.1/211.5/220.7/222 |
| F2 | 2014-09 → 2018-09 | 2019-10 → 2020-09 | 49/12 | 8427/2842 | 147/154.8/174.0/188.4/191 | 220/228.3/240.0/244.0/246 |
| F3 | 2014-09 → 2019-09 | 2020-10 → 2021-09 | 61/12 | 10897/2978 | 147/155.0/177.0/209.0/222 | 244/244.0/249.0/251.0/252 |

Los recuentos y sectores de **cada mes**, sus claves de emisor/security y sus hashes constan en `contracts.cohorts`. Las filas son exactamente las elegibles, sin duplicados de emisor-mes. La amplitud sectorial global es 6–8 sectores (mediana 7); la concentración sigue alta, por eso se exige diagnóstico sectorial.

## Biblioteca y arquitectura

Auditoría: LightGBM no instalado; XGBoost no instalado; scikit-learn 1.7.2 instalado. El proyecto ya declara XGBoost como dependencia opcional `ml` (`>=2.0`). Por esa preferencia por dependencias existentes, se propone **XGBoost 3.1.3 / XGBRanker / LambdaMART / `rank:ndcg`**. No se instaló ninguna biblioteca. La versión exacta y su implementación necesitan aprobación humana en la tarea de ejecución. Deben registrarse plataforma, paquete/binario y OpenMP y verificarse repetibilidad antes de ejecutar; no se promete equivalencia numérica entre plataformas distintas.

Fuentes oficiales: [release 3.1.3](https://github.com/dmlc/xgboost/releases/tag/v3.1.3), [learning to rank](https://xgboost.readthedocs.io/en/release_3.1.0/tutorials/learning_to_rank.html), [parámetros](https://xgboost.readthedocs.io/en/release_3.1.0/parameter.html). `rank:ndcg` emplea LambdaMART y recibe consultas mediante `qid` ordenado. Aquí cada consulta es **decision_month**; nunca se divide un mes aleatoriamente.

La etiqueta económica sigue siendo `future_excess_total_return_12m`: retorno total de la acción menos SPY, ambos USD sobre base comparable, entrada al último cierre conocido en T0 y salida al último cierre ≤T0+12 meses. Solo se usa para el orden dentro del mismo mes. No se calcula ahora.

Percentil: `(rango ascendente medio − 1)/(N − 1)`. Los valores exactamente iguales comparten rango; N<2 falla. Para el ranker se congelan grados enteros **`min(9, floor(10×percentil))`**, 0 peor–9 mejor, ganancia NDCG lineal (`ndcg_exp_gain=false`). Los empates pueden dejar grados vacíos; nunca se rompen usando ticker o retorno de otros meses. La magnitud de las ganancias no entra en el objetivo.

## Información y controles

L2R_M4 usa exactamente **44 features RAW**: PRICE (18), FUNDAMENTALS (18), RISK (8). No añade ranks como predictors, selección, macro, sectores, interacciones ni nuevas señales.

**PRICE:** `ret_1m`, `ret_3m`, `ret_6m`, `ret_12m`, `momentum_12_1`, `distance_sma20`, `distance_sma50`, `distance_sma200`, `sma50_vs_sma200`, `distance_52w_high`, `drawdown_from_52w_high`, `realized_vol_20`, `realized_vol_63`, `realized_vol_126`, `atr14_pct`, `downside_vol_63`, `volume_zscore_20`, `rsi14`.

**FUNDAMENTALS:** `fund_gross_margin`, `fund_operating_margin`, `fund_net_margin`, `fund_roa`, `fund_roe`, `fund_fcf_margin`, `fund_cfo_to_net_income`, `fund_accruals_to_assets`, `fund_revenue_yoy`, `fund_net_income_yoy`, `fund_debt_to_assets`, `fund_current_ratio`, `fund_shareholder_yield`, `val_pe`, `val_price_to_sales`, `val_price_to_book`, `val_fcf_yield`, `val_pe_own_pct`.

**RISK:** `risk_alert_h6`, `risk_alert_h12`, `rc_below_sma200`, `rc_momentum_negative`, `rc_support_broken`, `rc_elevated_volatility`, `rc_drawdown_state`, `support_distance_atr`.

**EXPANDED_M4R_CONTROL** reutiliza V1 Logistic L2 sin calibración (M4R, no M4RC): `outperform_12m`, C=0,01 fijo, lbfgs, max_iter=5000, tol=1e-4, intercept=true, class_weight=null, random_state=20261006. Mismas filas y 44 features. Mediana TRAIN, clipping TRAIN 1/99%, media/desviación TRAIN y 44 indicadores de ausencias: 88 columnas transformadas. Desviación nula → escala 1; columna TRAIN completamente ausente → fallo. No reajuste de C.

**EQUAL_INFORMATION_BASELINE** tiene puntuación constante 0, sin ajuste ni ranking aleatorio. IC es indefinido y se muestra null con su recuento. Para bins de ranking, los empates que cruzan un corte se reparten fraccionalmente: top y bottom tienen exactamente 20% del peso. Un score constante produce pesos iguales y spread exactamente cero. NDCG usa DCG promedio de empates. No se fuerza un orden artificial de tickers.

Comparar L2R con el M4R expandido es estrictamente pareado. Comparar M4R expandido con el antiguo es contextual, porque cambia la cohorte. No se reentrenan los modelos antiguos ni R2/R3/R4 ElasticNet.

## Grid y validación interna

Ocho combinaciones, sin ampliación posterior:

| Índice | max_depth | learning_rate | reg_lambda |
|---|---|---|---|
| 0 | 2 | 0.03 | 1.0 |
| 1 | 2 | 0.03 | 10.0 |
| 2 | 2 | 0.05 | 1.0 |
| 3 | 2 | 0.05 | 10.0 |
| 4 | 3 | 0.03 | 1.0 |
| 5 | 3 | 0.03 | 10.0 |
| 6 | 3 | 0.05 | 1.0 |
| 7 | 3 | 0.05 | 10.0 |

Parámetros fijos completos: `{"colsample_bytree": 1.0, "device": "cpu", "grow_policy": "depthwise", "lambdarank_normalization": true, "lambdarank_num_pair_per_sample": 8, "lambdarank_pair_method": "mean", "lambdarank_score_normalization": true, "lambdarank_unbiased": false, "max_bin": 256, "min_child_weight": 10, "n_estimators": 200, "n_jobs": 1, "ndcg_exp_gain": false, "random_state": 20261009, "reg_alpha": 0.0, "subsample": 1.0, "tree_method": "hist"}`.

200 árboles fijos, sin early stopping, CPU histogram y un hilo. RAW features sin estandarizar, imputar ni clipping; NaN mediante rama nativa de ausencia; infinitos o columna completamente ausente en TRAIN detienen la ejecución.

Inner CV conserva V1: TRAIN expansivo desde 2014-09, mínimo 18 meses, validación de seis meses, paso seis meses y diferencia mínima 13 meses entre la última decisión TRAIN y el inicio de validación. Exige además madurez estricta anterior al fit. Bloques completos:

- F1: TRAIN 2014-09–2016-02, VALIDATION 2017-03–2017-08.
- F2: TRAIN 2014-09–2016-02, VALIDATION 2017-03–2017-08; TRAIN 2014-09–2016-08, VALIDATION 2017-09–2018-02; TRAIN 2014-09–2017-02, VALIDATION 2018-03–2018-08.
- F3: TRAIN 2014-09–2016-02, VALIDATION 2017-03–2017-08; TRAIN 2014-09–2016-08, VALIDATION 2017-09–2018-02; TRAIN 2014-09–2017-02, VALIDATION 2018-03–2018-08; TRAIN 2014-09–2017-08, VALIDATION 2018-09–2019-02; TRAIN 2014-09–2018-02, VALIDATION 2019-03–2019-08.

Selección exclusiva en TRAIN: mayor media mensual Spearman IC en validaciones internas, igual peso por mes. Un IC indefinido aporta cero solo a la selección, registrando su recuento, y debe existir al menos un mes definido. Empate ≤1e-12: mayor NDCG@20%; después primer índice del grid. No selección por spread, outer TEST ni holdout.

## Evaluación futura, todavía sin resultados

Primaria: **media mensual Spearman IC cross-sectional**, por F1/F2/F3 y conjunto de 36 meses. Siempre mediana, desviación muestral ddof=1 y porcentaje de meses IC>0. IC indefinidos se muestran null, excluidos de la media y contados; el porcentaje positivo usa todos los meses. Para clasificar se requieren los 36 IC definidos en modelos entrenables.

Diagnósticos globales: spread top20−bottom20 mensual (media, mediana y porcentaje positivo), Q1–Q5 (retorno exceso medio/mediano, outperform, N y N fraccional efectivo), monotonicidad descriptiva, NDCG@ceil(10%N)/@ceil(20%N) con ganancias lineales. IDCG nulo → null. Todo es diagnóstico de ranking, no backtest ni estrategia de cartera.

Diagnósticos sectoriales obligatorios: grupos sector-mes con N≥10; Spearman dentro de sector, promedio de igual peso por sector-mes y versión secundaria ponderada por N; Spearman mensual de predicción frente a retorno menos la media del sector-mes; spread top/bottom dentro del sector, igual peso por sector dentro del mes y después igual peso por mes. Sectores pequeños se excluyen solo de estos diagnósticos. La clasificación SIC congelada es **CURRENT_PROFILE_NOT_PIT**, descriptiva y nunca predictor; no se afirma una taxonomía sectorial histórica perfecta. Se publican recuentos de grupos excluidos/indefinidos. Para bootstrap, IC sectorial mensual se obtiene promediando los sectores elegibles del mes.

Cada TEST mes reportará emisores, sectores, concentración mayor/top3. Entropía no se añade porque no está implementada. F3 conserva explícitamente IC mensual, meses positivos, spread global, IC dentro de sector y spread sector-neutral; una media global favorable no oculta su deterioro.

## Bootstrap

1.000 muestras pareadas, seed 20261009, NumPy Generator PCG64. Unidad: un mes TEST completo, todas sus filas, sectores y modelos juntos. Estratificado: 12 sorteos con reemplazo por fold; 36 meses por muestra conjunta. Intervalos percentiles 2,5/97,5 con interpolación lineal, también por fold. Diferencias L2R−control en IC mensual, spread global, IC sectorial mensual y spread sector-neutral. Usar misma intersección de meses definidos en ambos modelos; menos de seis meses pareados en cualquier fold → NOT_ESTIMABLE y recuentos explícitos.

Interpretación **ADAPTIVE_DEV_EXPLORATORY**. No row-IID ni cientos de emisores independientes. Los targets H12 solapados crean dependencia temporal; este bootstrap de bloques mensuales individuales no proporciona inferencia confirmatoria independiente ni corrige múltiples comparaciones.

## Clasificación futura: primera regla aplicable, exactamente una etiqueta

Umbrales materiales prospectivos: IC −0,02 y spread de retorno decimal −0,02. Ningún resultado se ha asignado.

- **NO_MEANINGFUL_RANKING_SIGNAL**: PIT/data bug, post-fit tuning, any missing required evaluation, OR pooled global mean IC <= 0 OR pooled global top-bottom mean <= 0.
- **TEMPORALLY_UNSTABLE_SIGNAL**: otherwise any fold mean IC <= 0 OR any fold mean top-bottom < -0.02 (explicit F3 included).
- **SECTOR_DRIVEN_SIGNAL**: otherwise pooled equal-sector mean IC <= 0 OR pooled sector-neutral mean spread <= 0.
- **ROBUST_CROSS_SECTIONAL_SIGNAL**: otherwise all folds mean IC >= .02, all fold top-bottom mean > 0, pooled mean IC >= .03, each fold positive-IC-month fraction >= .5, all folds equal-sector mean IC > 0 and sector-neutral mean spread > 0; pooled paired L2R-control differences in IC and spread >= 0, at least one strictly >0, pooled paired sector IC/spread >=0.
- **PROMISING_CROSS_SECTIONAL_SIGNAL**: all remaining complete, positive global/economic, all-fold-positive-IC, within-sector-positive cases; control inconsistency and F3 weakness must be disclosed.

Estas reglas abarcan señal global, estabilidad temporal, F3, orden económico, selección dentro de sectores y consistencia frente al control. No exigen quintiles perfectamente monótonos. Un fallo PIT invalida interpretar como señal; se detiene y documenta aunque el contrato de clasificación lo agrupe bajo NO_MEANINGFUL_RANKING_SIGNAL.

## Revisión humana y periodos sellados

Considerar holdout requiere: IC medio >0 en todos los folds y conjunto, F3 no materialmente negativo, spread conjunto >0 y spreads positivos por fold o ningún fold con spread <−0,02, IC sectorial y spread sector-neutral conjuntos >0, y ambos no negativos en F3, evaluación completa, ausencia de bug PIT y ausencia de tuning tras el fit. Son condiciones necesarias, no permiso automático ni garantía de robustez.

Holdout 2022-10-01–2025-09-30 y OOT desde 2025-10-01: **acceso a outcomes cero**. La futura ejecución nunca los abrirá; solo una decisión humana y tarea separada autorizada puede contemplarlo.

Artefactos futuros: RESEARCH_DEV_ONLY / ADAPTIVE_DEV_ITERATION_3 / RETROSPECTIVE_UNVALIDATED. Sin champion ni producción. No se lanzan otras variantes automáticamente después del resultado.

## Integridad y limitación de ejecución

Dataset SHA-256: `e90b817ab038735d1c5aa0f096384cb80337b75589dabf0731e49b39a9b7af39`. Manifest SHA-256: `50666e2a4b48253067c26d77baa61b474f799be5eeeb2e41d44db8139507cd79`. Los hashes de capas y contratos constan íntegros en los manifiestos.

Los tests detectan mutaciones, preservan la muestra y geometría, rechazan estados/counters de ejecución y outputs anidados, y comprueban que el congelador no importa estimadores ni constructores de outcomes. No existe API de fit/predict en esta tarea. Los estudios históricos conservan sus huellas.

**Bloqueo de ejecución exacto:** XGBoost 3.1.3 no instalado y falta el ejecutor autorizado. Prerregistro completo; no se declara listo para entrenar hasta la aprobación humana de implementación/instalación en la siguiente tarea.

## Validación del cierre

15 tests nuevos de prerregistro. Suite local completa: 1.218 passed, 3 skipped preexistentes, 21 tests PostgreSQL en su ejecución separada. PIT sin PostgreSQL: 541 passed, sin skips. PostgreSQL estricto: 21 passed, cero skips; `make pg-local` y Alembic upgrade/check/downgrade correctos, sin nuevas operaciones de migración. Ruff y formato correctos (450 archivos); mypy estricto correcto (228 módulos). Docker, frontend y E2E se verifican además en los seis jobs de CI del commit entregado; el enlace y estado final se incluyen en la entrega.
