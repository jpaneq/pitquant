# ADR-0044 — Backtest retrospectivo de la regla de la rutina (previsión de subida / bajada)

Estado: aceptada (2026-10-05). Sin migración. Complementa ADR-0042/0043.

## Decisión
1. **Qué se mide:** para cada valor, fecha muestreada (cada 21 sesiones) y horizonte (1/3/6/12 meses) la regla emite una previsión: SUBE (entrada justificada), BAJA (puntuación ≤ umbral de venta) o NEUTRAL. Se compara con la rentabilidad al final del horizonte frente a la tasa base, y para SUBE con el primer contacto de objetivo/stop (como la rutina real). Comando: `python -m pitquant.cli backtest-run` → `data/reports/backtest_rutina_*.txt` (también visible en `/rutina`).
2. **Point-in-time:** en cada fecha T la regla sólo ve barras conocidas al cierre de T (`AnalyzerService.technicals(sid, T)`); los resultados usan sólo barras posteriores. Ventanas inmaduras no se puntúan.
3. **Holdout sellado:** una decisión dentro de 2022-10-01→2025-09-30, o cuyo horizonte lo alcance, se omite y se cuenta. Los datos posteriores (≥2025-10) se informan aparte como periodo reciente (muestra pequeña).
4. **Reglas sólo de precio** (tendencia, media 200, momentum 6 m, soporte): valoración y fundamentales no están disponibles point-in-time para casi ningún valor y no se usan.
5. **Honestidad estadística:** intervalos de Wilson; sin tasas con N<10; las ventanas solapadas no son independientes; **sesgo de supervivencia** (la lista son empresas actuales); precios de una fuente no oficial descargados a posteriori; sin costes. Nada se ajusta automáticamente: la tabla de sensibilidad de `target_k` es informativa y avisa del riesgo de sobreajuste.
6. Primer resultado (25 valores, 2012→2026, holdout intacto): la regla de precio **no muestra ventaja visible** sobre la tasa base de subida (≈ +0 a +3 puntos según horizonte) y las llamadas BAJA no anticipan caídas. Es la línea base para decidir qué corregir.
