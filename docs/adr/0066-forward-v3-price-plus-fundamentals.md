# ADR-0066 — v3: precio + fundamentales publicados en la SEC

Fecha: 2026-11-08. Estado: aceptado (petición del propietario: que el algoritmo "extraiga los
datos publicados o que se publiquen").

## Contexto

El examen de ADR-0064 mostró que los 10 datos de precio no superan a «siempre sube». La
investigación previa (`docs/research/QUANT_ALGORITHM_EVIDENCE_2026-11-01.md`) señalaba value y
quality como las familias con mejor evidencia pública.

## Decisión

- **Datos.** `fundamentals-universe` (ADR-0046) para las 55 acciones del universo; el ciclo
  diario (`scripts/forward_daily.py`) vuelve a consultar la SEC cada noche y sólo incorpora
  filings nuevos. La identificación que exige la SEC ("Nombre correo") se lee del entorno o de
  `data/sec_user_agent.txt` (no versionado) y nunca se archiva.
- **Seis indicadores, elegidos antes de ver resultados** (`forward/fundamentals.py`):
  margen operativo, ROA, crecimiento de ventas interanual, deuda/activos, earnings yield y FCF
  yield. Los calcula el mismo motor point-in-time del dataset de investigación
  (`research.fundamentals_v1`): cada filing cuenta desde su `ACCEPTANCE-DATETIME`, se evalúa en
  la primera sesión de cada mes (apertura, con el cierre previo) y se arrastra a los días de ese
  mes. `guard_snapshot` falla si algún dato es posterior a la decisión. Bancos/aseguradoras
  (sector no soportado) y huecos quedan ausentes; nunca 0.
- **Modelo v3** (`forward-logistic-pricefund-v3`): mismo algoritmo, parámetros, horizonte y
  universo que v2; 16 entradas. `fit_model(extra_features=…)` sin cambiar V1/v2.
- **Examen v3 único** (`forward/learning_v3.py`): mismas decisiones que el examen v2; brazo B =
  procedimiento v2 (reutiliza sus reentrenos de examen), brazo C = procedimiento v3. Reglas
  preregistradas y predicciones congeladas antes de los resultados. Política `LEARNING_V3` si
  logloss(B) − logloss(C) > 0; si no, se mantiene la vigente.
- **Regla de cambio v2 ↔ v3** con pronósticos reales: la misma que v1 ↔ v2 (≥ 200 pares en ≥ 20
  fechas, IC 90 % sin cero).

## Consecuencias

- **Adaptatividad:** la ventana del examen ya se usó en ADR-0064 (sabemos que el precio solo
  falla ahí). Los indicadores no se eligieron con esos resultados y nada se ajusta, pero el
  examen es menos virgen que el primero; la prueba limpia son los pronósticos reales.
- Coste: calcular los fundamentales mensuales de 55 empresas lleva minutos y se hace una vez
  al mes (reentreno); el pronóstico diario sólo calcula los dos últimos meses.
- Sesgo de supervivencia y vintage actual, como en ADR-0064.
