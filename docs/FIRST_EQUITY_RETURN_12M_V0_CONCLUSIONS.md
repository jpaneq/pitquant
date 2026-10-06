# Conclusiones — FIRST_EQUITY_RETURN_12M_V0

**RETURN_SIGNAL_UNSTABLE**, según la regla descriptiva congelada antes del fit.
RESEARCH_DEV_ONLY, ADAPTIVE_DEV, RETROSPECTIVE_UNVALIDATED; iteración adaptativa 2.
No promoción. M4R conserva únicamente el papel de CURRENT_BEST_DIRECTION_RESEARCH_BASELINE.

## Resultado principal

No se demuestra una mejora reproducible de magnitud frente a R0 TRAIN mean.
MAE pooled R0 0.209309, R2 0.216522, R3 0.209556, R4 0.216794.
RMSE pooled R0 0.279659, R2 0.284896, R3 0.277949, R4 0.287963.
El pequeño descenso puntual de RMSE R3 no tiene un intervalo exploratorio
enteramente favorable. R2/R4 empeoran MAE; R4 también empeora RMSE frente a R0.

F2/F3: los tres candidatos seleccionan alpha=1, l1_ratio=0.25; todos los
coeficientes quedan a cero. Predicen exactamente la misma media TRAIN que R0.
No es un bug ni ausencia de precios: es el resultado de la selección causal
por MAE dentro del grid predeclarado. No se amplió el grid ni se capó el target.

El ranking económico sólo está definido en 12 de 36 meses (F1). Por eso las
medias "pooled" de IC mensual y spread de los modelos de retorno describen
esos 12 meses, no tres folds de señal. En F2/F3 son NA, nunca cero ficticio.
Las métricas MAE/RMSE y el IC de observaciones pooled incluyen las 1507 filas.
R0 pooled IC sólo refleja cambios de sus constantes entre folds; no ordena securities.

## Q1–Q10

1. **¿Magnitud mejor que R0?** No de forma reproducible. Ningún candidato mejora
   MAE pooled. R3 mejora RMSE puntualmente, con IC95 delta [−0.006216,+0.002187].
2. **¿PRICE contiene señal continua?** Muy débil y limitada a F1: IC mensual
   0.040554, meses positivos 50%, spread +4.975 pp. MAE/RMSE F1 peores que R0;
   F2/F3 colapsan al baseline constante.
3. **¿FUNDAMENTALS contiene señal?** Exploratoria en F1: IC mensual 0.202199,
   11/12 meses positivos; spread +13.269 pp, positivo 9/12 meses. F1 RMSE mejora,
   MAE no. No se reproduce en F2/F3.
4. **¿R4 mejora R2?** En ranking disponible F1 sí: delta IC mensual IC95
   [+0.029594,+0.206349], spread [+0.054380,+0.175790]. No mejora los errores:
   delta MAE/RMSE pooled no concluyente; F2/F3 ambos equivalen a R0.
5. **¿R4 mejora R3?** No. Peores MAE/RMSE pooled y menor IC mensual en F1:
   delta IC95 [−0.081184,−0.011214]. Mayor spread puntual, intervalo cruzando cero.
6. **¿IC positivo y estable?** Positivo sólo en F1 y con magnitudes distintas.
   No hay ranking en F2/F3; no constituye estabilidad en tres folds.
7. **¿Spread positivo en F1/F2/F3?** F1 sí para R2/R3/R4. F2/F3 NA por
   predicciones constantes. No existe evidencia de tres spreads positivos.
8. **¿Quintiles más monotónicos que M4R?** No se demuestra. Comparando F1
   para ambos, R4 y M4R tienen 3 de 4 diferencias adyacentes positivas;
   ninguno satisface Q1<Q2<Q3<Q4<Q5. No comparar quintiles pooled de
   R4 (sólo F1) con M4R (36 meses) como si compartieran el mismo periodo.
9. **¿F3 sigue problemático?** Sí: ausencia de ranking y R² −0.104004 en todos
   los regresores, igual que R0. Ahora F2 también carece de ranking: el problema
   no queda resuelto cambiando la etiqueta binaria por retorno continuo.
10. **¿Información incremental sobre Direction?** No demostrada. En los mismos
    meses de F1, R4 IC mensual 0.154972 frente a M4R 0.291194; spread
    +16.771 frente a +22.901 pp. R4 no ordena en F2/F3; M4R sí, aunque F3 falla.
    No se compara MAE con LogLoss ni se infiere que M4R prediga magnitud.

## Comparación temporal justa con M4R

OOF global usa exactamente las mismas 1507 TEST rows. Para IC/spread, la
intersección de meses con ranking definido contiene sólo los 12 meses de F1
(2018-10→2019-09), 476 filas. La restricción es por disponibilidad del ranking,
no por rendimiento observado. DIRECTION_COMPARISON_AUDIT.json contiene medias
pareadas y sus meses; COMMON_RANKING_COMPARISON.json contiene quintiles del
mismo periodo para ambos. Los quintiles pooled sin restricción describen
poblaciones temporales distintas, con sus N, y no son comparación pareada.

## Integridad y límites

Dataset/folds/target/benchmark/FX/familias/cohortes intactos; no target nuevo ni
winsorización. Todos los datos congelados son total return USD frente a SPY
ETF_PROXY; SPY no es índice oficial. Extremos +256.34 pp conservados.

Dos ejecuciones completas coinciden byte a byte. Refit independiente y replay
desde parámetros: diferencias máximas cero. Cero avisos de convergencia; ningún
bug data/PIT/preprocessing/folds. V0/V1 conservan todos sus hashes.
Holdout outcomes accessed=0; OOT outcomes accessed=0. No portfolio ni live.

1000 réplicas ADAPTIVE_DEV_EXPLORATORY_INTERVAL: dependencia dentro del mes
preservada, no toda la dependencia serial H12. Deltas IC/spread contra R0 NA.
Deltas entre regresores de ranking se refieren únicamente a 12 meses de F1.
No confirmación independiente tras observar V0/V1.

## Un único siguiente paso recomendado

**Auditoría predeclarada del desajuste entre pérdida cuadrática y selección por
MAE, sin nuevos fits ni apertura holdout/OOT.** Evaluar desde ella si merece
como máximo un último experimento estructural. No iniciar V3 automáticamente
ni seguir ampliando modelos sobre el mismo DEV para buscar un resultado positivo.
