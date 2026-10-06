# FIRST_EQUITY_ML_12M_V0 — interpretación y reproducción

La clasificación **PROMISING_BUT_UNSTABLE** aplica la regla registrada antes del ajuste. Describe señal exploratoria de ranking, no probabilidades validadas ni una estrategia rentable. M4 tiene AUC pooled 0.56951, pero Brier 0.28462 frente a 0.26579 de M0; en F3 su AUC es 0.47579 y el spread top20–bottom20 es −13.482 puntos porcentuales.

## Respuestas Q1–Q10

1. **M2 vs M0:** mejora AUC en F2/F3, pierde en F1; no mejora Brier pooled ni de forma consistente. Evidencia débil para PRICE.
2. **M3 vs M0:** mejora ranking en F1/F2 y pooled, pero falla F3 y empeora Brier en los tres folds. No mejora probabilidades.
3. **M4 vs M2:** AUC pooled superior, diferencia +0.05348, IC95 exploratorio [0.01444, 0.09159]. Sin mejora de Brier: diferencia +0.01706, IC95 [0.00500, 0.02973]. No gana en todas las dimensiones.
4. **M4 vs M3:** diferencia AUC +0.01476 con IC95 [−0.01786, 0.04370]; diferencia Brier +0.00105 con IC95 que contiene cero. Ventaja no concluyente.
5. **ML vs V0:** M3/M4 superan su ranking en F1/F2 y pooled, no en F3. V0 no tiene probabilidad congelada y sus métricas probabilísticas son N/A.
6. **Consistencia:** no. M3/M4 invierten la dirección de AUC, IC y spread en F3; M2 falla F1. La dispersión mensual también es amplia.
7. **Calibración:** mala. Pendientes pooled M2/M3/M4 ≈0.127/0.130/0.167; ECE ≈12.61/16.98/16.28 puntos porcentuales. Ninguna recalibración aplicada.
8. **Probabilidad mayor implica retorno mayor:** no de forma monotónica. El spread mensual medio M4 top20–bottom20 es −0.169 puntos porcentuales; IC95 [−5.273, 4.916] puntos. Las tablas de buckets conservan medias, medianas, N y tasas de outperform.
9. **Coeficientes:** estabilidad parcial. Signo consistente en los tres folds para 11/18 columnas RAW de M2, 14/18 de M3 y 25/44 de M4. Coeficientes no causales; no se eliminaron features.
10. **Segundo experimento:** sí, como investigación controlada sobre calibración e inestabilidad; no como promoción ni apertura de holdout.

## Lectura correcta de las métricas

M0 tiene AUC 0.50 en cada fold y en cada mes. Su AUC pooled 0.42850 se debe a que sus constantes TRAIN difieren entre folds y se alinean mal con las prevalencias TEST; no representa ranking transversal. Las diferencias pooled frente a M0 deben leerse junto a las comparaciones por fold y los IC de cada ML frente a 0.50.

Los spreads principales son medias con igual peso de los meses TEST. La resta de dos medias de buckets agregados por filas puede diferir por ponderación. Los empates se mantienen juntos, de modo que top/bottom representan cuotas aproximadas; M0 constante carece de extremos de ranking. No se inventa spread cero para completar bootstrap.

Los IC95 resamplean 36 meses completos. Conservan dependencia transversal, pero no toda la dependencia serial de targets de 12 meses solapados. Universo configurado, supervivencia, fuente Yahoo retrospectiva, uso previo exploratorio de DEV y comparaciones múltiples limitan la inferencia. Esto es OOS temporal DEV, no un holdout virgen ni validación de producción.

## Reproducir

Código de entrenamiento: commit `1966698`; source readiness: `9f1bf55`. Conservar la rama final para los artefactos y usar un checkout separado del SHA de código para repetir el runner. No hace falta regenerar datos SEC/Yahoo.

1. Crear un entorno Python 3.12 con `pip install -e '.[dev,equity-baseline]'` y las versiones exactas de los paquetes numéricos registradas en el manifiesto.
2. Extraer `FIRST_EQUITY_ML_12M_V0_DATASET.json.gz` a `data/research/FIRST_EQUITY_ML_12M_V0/dataset.json`; verificar el SHA256 del contenido descomprimido contra `data_snapshot_hash`.
3. Copiar el manifiesto entregado a docs del checkout de código. Ejecutar `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/run_first_equity_ml.py run` y `python scripts/report_first_equity_ml.py`.
4. Comparar los hashes de OOF y parámetros. Un contenido distinto bajo la misma identidad produce conflicto explícito; no sobrescribe archivos.

La repetición completa produjo el mismo hash OOF. Los nueve ajustes repetidos y el replay independiente desde coeficientes serializados tuvieron diferencia máxima **0.0**; tolerancia predeclarada 1e-12. Prueba: `FIRST_EQUITY_ML_12M_V0_REPRODUCTION.json`.

Los gráficos usan TEST exclusivamente: ROC y precision–recall, distribución de probabilidades, calibración (X: probabilidad; Y: frecuencia observada), buckets de exceso y comparación de coeficientes F1/F3. Los bins extremos pequeños deben leerse con su N en REPORT.json.

Holdout outcomes accedidos: **0**. OOT outcomes accedidos: **0**. Nueve modelos logísticos convergieron sin warnings; artefactos RESEARCH_DEV_ONLY / RETROSPECTIVE_UNVALIDATED. Sin schema/migración, UI, live signals, champion ni promoción.

## Único siguiente experimento propuesto

**FIRST_EQUITY_ML_12M_V1 — M4 sin calibración vs M4 con calibración temporal TRAIN-only**. Prerregistrar la partición interna purgada y comprobar su viabilidad antes de ajustar; mantener folds externos, target, familias, cobertura y cohortes comunes. No usar TEST para ajustar la calibración y no abrir holdout.
