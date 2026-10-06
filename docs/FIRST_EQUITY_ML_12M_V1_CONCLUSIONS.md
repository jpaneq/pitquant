# Conclusiones V1 — ADAPTIVE_DEV_ITERATION_1

Clasificación predeclarada: **REGULARIZATION_IMPROVED_STABILITY**.
C=0.01 fue seleccionado dentro de TRAIN en las seis combinaciones familia/fold.
No se amplió el grid; estar en su límite inferior no autoriza buscar otros C bajo V1.
Sin promoción: RESEARCH_DEV_ONLY, ADAPTIVE_DEV, RETROSPECTIVE_UNVALIDATED.

## Q1–Q10

1. **¿C=1 sobreajustaba M3?** Evidencia compatible, no demostración independiente:
   C=0.01 seleccionado en F1/F2/F3; LogLoss pooled 0.820486→0.751406 y Brier
   0.283565→0.271546. LogLoss mejora en los tres folds, pero AUC pooled cae
   0.554752→0.551316. Más regularización evita extremidad sin resolver toda la señal.
2. **¿C=1 sobreajustaba M4?** Evidencia compatible más clara en probabilidades:
   LogLoss 0.819641→0.722847; Brier 0.284617→0.260011; AUC 0.569508→0.574813.
   La comparación sigue siendo DEV adaptativa, con intervalos exploratorios.
3. **¿Mejora F3?** Parcialmente. M3 AUC 0.466718→0.474080, LL
   0.816455→0.769394; M4 AUC 0.475787→0.491293, LL 0.857538→0.755906.
   Sus spreads siguen negativos: −2.944 y −3.717 puntos porcentuales.
   No evita el fallo de ranking de F3 ni demuestra capacidad OOS estable.
4. **¿Mejora estabilidad entre folds?** Sí, descriptivamente: se reduce la
   dispersión de AUC (M3 0.068291→0.061318; M4 0.061660→0.054760)
   y C es estable. La SD de LogLoss aumenta (M3 0.057985→0.060721;
   M4 0.034423→0.040041): su nivel mejora, su dispersión no. El JSON contiene SD,
   signos, dispersión y normas completas. Sigue habiendo reversión económica en F3.
5. **¿Platt mejora LogLoss?** En F3 sí; en F1/F2 empeora. Pooled M3R→M3RC:
   0.751406→0.751478; M4R→M4RC: 0.722847→0.744966. No hay mejora general.
6. **¿Platt mejora Brier?** En F3 sí. Pooled empeora: M3 0.271546→0.276129;
   M4 0.260011→0.273672. No adoptar por supuesto beneficio de calibración.
7. **¿Corrige slope/intercept?** Comprime la extremidad y modifica estos
   diagnósticos, pero no corrige de forma uniforme los tres folds ni el pooled.
   Consultar la tabla completa; pendiente cercana a uno por sí sola no basta
   cuando LL/Brier empeoran. El cambio de prevalencia TRAIN→TEST limita transferencia.
8. **¿Sobrevive ranking?** En F1/F2 hay AUC >0.5 y spreads positivos; F3 falla.
   Spreads pooled M3R +10.992 pp, M4R +9.737 pp. No son rentabilidad de estrategia.
   Platt preserva exactamente AUC/AP/IC/quintiles por fold y por mes;
   cambios de AUC pooled son consecuencia de calibradores distintos entre folds.
9. **¿M4 aporta información incremental?** LL/Brier pooled favorecen M4R;
   AUC +0.023497, pero IC95 exploratorio [−0.002317,+0.047577] incluye cero.
   Spread M4R−M3R −1.255 pp, intervalo [−4.226,+1.415] pp. La complejidad
   adicional no ha demostrado una superioridad robusta de ranking económico.
10. **¿Justifica V2?** Sí como investigación limitada, no como autorización de
    producción. La regularización mejora probabilidades; quedan inestabilidad
    temporal y fallo de transferencia de Platt. Holdout sigue sellado y virgen.

## Un único siguiente experimento recomendado

**V2: diagnóstico temporal causal de transferencia de calibración**: mantener
C=0.01 y las familias/datos/folds congelados, predeclarar antes de fit una única
ventana de las seis cohortes mensuales OOF causales maduras más recientes para Platt y compararla con V1, verificando primero
si hay historia H12 suficiente. Sin nuevos predictores, sin ampliar grid y sin
abrir holdout/OOT. Sería ADAPTIVE_DEV_ITERATION_2, otra investigación exploratoria.
La hipótesis es transferencia entre prevalencias, no reparar el ranking mediante calibración.

## Integridad, reproducción y límites

Dos ejecuciones completas de V1 coinciden byte a byte en resultados, parámetros,
predicciones y bootstrap. Refit independiente por ajuste: tolerancia 1e-12.
V0 conserva todos los hashes; dataset y contratos externos exactos.
Holdout outcomes accessed = 0. OOT outcomes accessed = 0.
No hubo bugs de datos/PIT/folds/preprocessing/calibration leakage ni avisos de
convergencia. Se corrigió únicamente la presentación de SD del IC no disponible
para M0 constante en el generador del informe después de entrenar; el código de
entrenamiento y los artefactos científicos congelados permanecieron idénticos.

222 observaciones OOF internas en F1 son pocas. Selección y calibración comparten
OOF interna. Los intervalos ADAPTIVE_DEV_EXPLORATORY no preservan dependencia
serial de objetivos H12 y no son confirmación independiente. Los resultados se
refieren a la cohorte común certificada, no a todo el S&P 500 ni a operativa real.
