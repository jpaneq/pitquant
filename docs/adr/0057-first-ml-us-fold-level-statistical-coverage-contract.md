# ADR-0057 — First ML US fold-level statistical coverage contract

Estado: aceptado por decisión explícita del propietario, 2026-10-05.
Contrato: FIRST_ML_COVERAGE_V1. Experimento: FIRST_EQUITY_ML_12M_V0, target outperform_12m.

## Decisión previa a entrenamiento

El mínimo global RUN 3 de 100 securities se conserva como diagnóstico legacy,
pero no decide First US ML: exigir 100 a 55 securities US configuradas es
estructuralmente imposible. No se sustituye por el tamaño observado. Los umbrales
siguientes fueron fijados por el propietario antes de entrenar y permanecen
constantes aunque cambie el tamaño del universo.

La unidad principal es issuer_id distinto; las clases de una emisión no añaden
emisores independientes. Se reportan también securities, filas, issuer-months,
meses, concentración, missingness y distribución de exclusiones. Las filas panel
no son muestras independientes. EFFECTIVE_SAMPLE_SIZE = NOT_FORMALLY_ESTIMATED;
no se inventa un effective-N para aprobar el gate.

PRICE exige >=40 emisores y >=80% de los emisores del cohort US configurado con
membresía reconstruida válida en ese mes. El denominador se calcula desde el ledger
D02, antes de filtrar disponibilidad de features o targets; no es todo el S&P 500.
FUNDAMENTALS y COMBINED exigen >=30 emisores y >=70% de PRICE elegible. El 30 deriva
del estándar fundamental existente (>=36 meses PIT); esa puerta global fundamental
permanece y los folds mantienen >=36 meses TRAIN. COMBINED hereda las restricciones
PRICE/FUNDAMENTALS de la única función first_ml_eligibility. RISK permite los
faltantes imputables del contrato original; no se introduce un filtro complete-case.

TRAIN necesita ceil(90% de meses) que superen ambas condiciones. TEST exige 12/12
meses, cada uno por encima de los dos umbrales. Un mes vacío se cuenta como fallo;
no se elimina del denominador. La condición TRAIN admite meses tempranos escasos;
TEST necesita una población estable para la comparación. No se modifican los
folds, H12, madurez, purge ni embargo de ADR-0055.

## Comparación y congelación

PRIMARY_COMMON_COHORT es la intersección por (security_id, decision_at) de las tres
familias, tanto en TRAIN como TEST. Los cinco modelos M0–M4 deberán consumir las
mismas keys, con hash por partición, ledger de origen y versión de contrato.
FAMILY_NATIVE_COHORT se guarda por separado para diagnóstico secundario. No puede
alimentar el leaderboard principal. El informe completo se archiva append-only;
una corrección genera un nuevo hash, no reemplaza el original.

Las cohortes se seleccionan sin outcomes. Después de congelar keys, se permiten
exclusivamente conteos DEV del target binario para detectar TRAIN/TEST sin ambas
clases. La degeneración bloquea. No se usan AUC, Brier, retornos, IC, Sharpe,
drawdown ni scores. Las dimensiones 18/18/44 son candidatos fijados; los ratios
filas/features son informativos y no seleccionan features. No hay preprocessing
ajustado ni modelo entrenado.

FIRST_ML_IDENTITY_VALIDITY_READY comprueba que todas las filas incluidas tienen
security_id, issuer_id concordante y evidencia de membresía aceptada. Los casos
excluidos no bloquean esa validez. US_SECURITY_IDENTITY_READY permanece como
completitud global, puede ser PARTIAL y no autoriza añadir casos no verificados.
First ML exige validez D02 e identidad de filas incluidas, D05 US, benchmark,
fundamentales, cobertura de las tres familias en los tres folds LABEL_SAFE y
holdout sellado. Ningún gate global de completitud sustituye estas comprobaciones.

## Límites y fallos

Los umbrales no eliminan sesgo de supervivencia del universo configurado, sesgo
por exclusiones, dependencia panel ni limitaciones de categorías sectoriales
actuales. La auditoría muestra concentración por issuer/sector, meses escasos,
clases duplicadas deduplicadas y distribución de exclusiones por año/mes/security/
issuer/sector/razón/tier; nunca compara sus retornos futuros. No se presume que
aprobar cobertura pruebe potencia estadística o validez predictiva.

Si falla un mes se publican los emisores/porcentaje reales y requeridos y el
mínimo adicional con denominador fijo. En TRAIN se indica cuántos meses necesitan
reparación para alcanzar 90%. Recuperar datos PIT verificados puede repararlo;
relajar umbrales o alterar evidencia D02 para aprobar está prohibido.
Holdout 2022-10–2025-09 y OOT >=2025-10 quedan excluidos. Esta tarea termina en
readiness y no ejecuta M0–M4.
