# ADR-0058 — Fundamental mapping and causal recovery for First US ML

Estado: aceptado dentro del encargo del propietario, 2026-10-05.
Mapping: sec-tags-4. Snapshots activos: first-ml-features-sec4-v4.

## Auditoría

Los 34/41/43 meses TRAIN a reparar se solapan: 49 meses únicos deficitarios,
37 afectan tres folds, 11 dos folds y uno un fold. La decisión de elegibilidad
ya permite nulos en los 15 candidatos opcionales del M3 y exige únicamente
fund_net_margin, fund_revenue_yoy y fund_debt_to_assets, además de sector
soportado. No se relaja ese contrato ni FIRST_ML_COVERAGE_V1.

La lógica visible/latest-known propaga la última revisión conocida por concepto,
periodo y unidad hasta una nueva revisión disponible. No exige un filing cada
mes. Un replay de las 818 filas no soportadas por core con el mapper antiguo y
los hechos ya archivados recupera cero filas; no hay evidencia de snapshots
obsoletos ni de imputation necesaria. Sectores no soportados son otra causa
estructural, distinta de ausencia histórica de datos.

## Corrección del mapping

El lector previo de total debt no reconoce DebtAndCapitalLeaseObligations.
La [definición publicada por XBRL US](https://xbrl.us/data-rule/dqc_0015-le-V2pr/)
lo identifica como agregado de deuda a corto y largo plazo y arrendamientos
financieros. El contrato previo ya usa DebtCurrent (también incluye obligaciones
de arrendamiento) en total debt; el candidato es deuda financiera total/activos,
no únicamente obligaciones no corrientes. Sec-tags-4 reconoce el agregado
reportado, con su procedencia, sin fabricar un balance.

Se requiere instant USD con disponibilidad anterior a la decisión. Un agregado ya conocido se propaga hasta una nueva revisión; no se impone que activos y deuda actualicen en el mismo filing, conforme al motor existente.
LongTermDebtAndCapitalLeaseObligations es un componente no corriente, no un alias del total: puede combinarse únicamente con DebtCurrent del mismo periodo. Totales alternativos contradictorios fallan cerrado. No se suman calendarios de repago ni se asume cero cuando
falta un componente. Donde existe el agregado publicado se usa también para
corregir valores antes calculados desde componentes incompletos. Donde no hay
agregado verificable se conserva el mapper previo y sus faltantes.

La hipótesis, nombres de features, candidatos M0–M4 y umbrales permanecen iguales.
La corrección numérica se aplica únicamente en la versión nueva de snapshots US;
las versiones originales permanecen inmutables. Precio/risk y sus ranks se copian
exactamente; sólo ranks fundamentales se recalculan para la misma cohorte/fecha.
Analyzer, pesos V0 y servicios de simulación no importan este módulo.

Las versiones locales intermedias del experimento de reparación fueron archivadas
antes de cerrar la interpretación de la taxonomía; se conservan por append-only,
pero First ML selecciona exclusivamente v4. Cada versión tiene su hash de código.
Los valores no se rellenan ni se ajusta median/scaler fuera de un TRAIN futuro.

## Evidencia, límites y reconstrucción

La recuperación usa hechos normalizados con fact_id, accession y available_at;
visible conserva el corte estricto existente available_at < decision_at. No se
usa period_end como fecha de conocimiento ni se retrotraen revisiones futuras.
No se leen holdout/OOT outcomes ni se generan targets durante la reconstrucción.

El informe distingue recuperación demostrada, candidatos de pipeline todavía
no verificados, identidad histórica sin resolver y sectores estructuralmente
excluidos. La ausencia en el archivo local no prueba ausencia histórica real;
no se presenta un mapping ambiguo como recuperable. Para DIS/AVGO se archivan
submissions oficiales de sus CIK actuales; no se importan fundamentales de
predecesores a sus issuer_id actuales sin prueba temporal de identidad.

Reproducción: rebuild_first_ml_fundamentals.py, gen_data_readiness_first_ml.py,
gen_first_ml_fundamental_gap.py. Versiones anteriores y documentos SEC originales
conservados, sin migración. La readiness se recalcula con el contrato congelado;
si falla, los déficits permanecen publicados. Ningún modelo se entrena aquí.
