# ADR-0059 — Primer baseline ML de acciones, exclusivamente DEV

Estado: aceptado por encargo del propietario, 2026-10-06. Fuente: `9f1bf55`; fase independiente `codex/first-equity-ml-baseline-12m`. Sin cambios de contratos de datos, mappings, folds, features, umbrales ni producto.

## Congelación antes del primer ajuste

`run_first_equity_ml.py prepare` exige código comprometido, gates certificados y hashes de las claves de los cohortes comunes. Recupera targets por clave exacta exclusivamente DEV, con exit anterior a 2022-10-01. Valida identidad, timestamps, feature_hash, madurez TRAIN y separación respecto a TEST. Archiva dataset y manifiesto con escritura exclusiva y conflicto explícito si los bytes cambian. `run` exige exactamente el SHA del manifiesto. Los archivos locales bajo data/research son append-only; manifiesto, OOF y parámetros se entregan también en docs. No migración ni registro de champion.

El manifiesto fija las familias explícitas de 18/18/44 columnas RAW de first_ml_contract; no se añaden columnas rank adicionales ni se seleccionan features. Su descripción general menciona ranks, pero las tuplas concretas de candidatos son la definición de entrada de esta ejecución. Todas las columnas permanecen, incluso constantes. El snapshot original y el hash de sus ranks quedan vinculados.

M0: prevalencia TRAIN del cohorte común. M1: `position-review-v0`, reutilizando `positions.backtest.context_at` y AnalyzerService históricos a la apertura mensual; posición hipotética recién abierta, horizonte 12 meses, sin stop/target. Se conserva score y traza de reglas, sin ajustar pesos. La nota previa sobre mapear score por rango no establece una probabilidad calibrada y queda expresamente descartada por el encargo actual: ninguna probabilidad inventada, Brier/log loss/calibración N/A para M1. Su ranking sí admite AUC/AP/IC. No se interpreta ADD/HOLD/SELL como clasificación de outperform.

M2/M3/M4: sklearn 1.7.2 LogisticRegression L2, C=1, lbfgs, class_weight=None, max_iter=5000, tol=1e-4, intercepto, seed=20261006. Ninguna búsqueda, calibración aplicada, selección, rebalanceo ni modificación de umbral (0.50 diagnóstico).

Preprocesado por fold: mediana TRAIN; clipping percentiles TRAIN 1/99 sobre datos imputados; estandarización TRAIN; concatenación de un indicador de faltante por candidato. Se fija ahora la parametrización no especificada de winsorización del baseline general. Una columna totalmente faltante provoca fallo explícito, nunca eliminación ni cero inventado. Parámetros y coeficientes archivados; repetición independiente del ajuste exige probabilidades iguales con tolerancia absoluta 1e-12.

## Diagnósticos predeclarados

Calibración de diez bins uniformes; intercepto/pendiente mediante optimización diagnóstica que nunca modifica predicciones. Correlaciones de TRAIN y estabilidad de coeficientes, sin selección. Ranking dentro de cada mes por rango medio: empates conservados juntos, nunca desempate por identidad o outcome. Buckets de cinco/diez si N>=3×buckets y existen extremos; cuotas aproximadas con empates, no cartera exacta del 20%. M0 constante mensualmente tiene spread N/A.

1.000 bootstrap de meses TEST completos, seed fijo y remuestreos pareados. Conserva dependencia transversal pero no toda dependencia serial por targets de 12 meses solapados. IC exploratorios; tres folds DEV y múltiples comparaciones no constituyen validación independiente. No umbral de monotonía nuevo: tablas.

Interpretación global predeclarada: STRONG_PROMISING_SIGNAL si algún ML mejora AUC y Brier en los tres folds y los IC95 pareados favorecen ambos; PROMISING_BUT_UNSTABLE si algún ML mejora AUC en al menos dos folds y su IC95 de delta AUC es positivo; WEAK_SIGNAL si algún ML tiene AUC pooled>0.50 y mejora AUC en al menos dos folds; en otro caso NO_MEANINGFUL_SIGNAL. Conserva todos los números y las limitaciones.

## Separación y política de errores

Holdout/OOT: cero lecturas de outcomes; ninguna promoción, señal live ni sustitución de V0. Solo DIRECTION; RETURN/RISK futuros permanecen sin entrenar. Un fallo de implementación/PIT después del inicio requiere invalidación explícita y una revisión nueva: nunca sobrescritura ni parche silencioso del experimento.
