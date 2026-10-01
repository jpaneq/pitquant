# ADR-0014 — Holdout sellado y evaluación explícita

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Complementa:** ADR-0009

## Contexto
El holdout oct-2022 → sep-2025 se fijó antes de ver resultados (D-09, confirmado por el
propietario). El riesgo restante es erosionarlo por repetición: mirar sus métricas a
menudo lo convierte en otro conjunto de validación.

## Decisión
- Las métricas del holdout sólo se producen con `evaluate_candidate_on_holdout`:
  modelo **congelado**, motivo obligatorio, solicitante registrado, **una vez por versión
  de modelo**. Cada acceso queda en `holdout_access_log`.
- Los resultados se guardan **sellados** en `holdout_evaluations` (append-only, con
  `metrics_hash`). No hay endpoint de API ni vista de dashboard que los lea; un test
  verifica que ninguna ruta los expone.
- Leer un resultado sellado (`read_sealed_evaluation`) es también una operación explícita
  y registrada (p. ej. para el comité de promoción).
- Toda consulta de analytics/backtest de desarrollo llama a `guard_analytics_range`, que
  falla si el rango toca el holdout.
- Contador de candidatos evaluados: a partir de 5 se emite aviso para aplicar correcciones
  por múltiples pruebas (Deflated Sharpe, PBO) antes de fiarse de ninguno.
