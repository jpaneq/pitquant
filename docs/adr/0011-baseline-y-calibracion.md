# ADR-0011 — Baseline interpretable, probabilidad calibrada aparte

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- Fase 5: scoring lineal por bloques con subscores 0–100 basados en **percentiles
  cross-sectionales sector-neutrales** calculados sólo con el universo de la fecha.
  Winsorización por fecha (p1/p99) sin estadísticas de otras fechas.
- Pesos por horizonte en config (`model_6m`, `model_12m`); los valores del prompt
  (45/40/15 y 60/25/15) son **hipótesis**, versionadas como `scoring_version`.
- `P(outperform)` = calibrador isotónico (Platt si hay < 1.000 observaciones) ajustado
  sólo con predicciones OOS de folds anteriores con label disponible.
- Señal: BUY si `p ≥ p_buy` y confianza suficiente; SELL si `p ≤ p_sell`; en otro caso HOLD.
  Avisos de calidad de datos de severidad ≥ media degradan a HOLD.
- ML (fase 10) entra sólo como *challenger* contra este baseline.
