# Analysis Engine V0 (`analysis-v0.1`)

**Qué es:** análisis estructurado, determinista y explicable de datos reales (fundamentales SEC, técnicos, valoración, riesgo). **Qué no es:** un predictor validado, ni BUY/HOLD/SELL, ni un score global. Etiqueta permanente: `RULE_BASED / OWN_HISTORY_CONTEXT`, `not_a_prediction: true`.

## Categorías y etiquetas (`ABSOLUTE_RULE_V0` salvo indicación)
| categoría | regla | cobertura |
|---|---|---|
| Fundamentals | de 5 comprobaciones (margen operativo > 10 %, margen FCF > 5 %, ROA > 5 %, CFO/NI ≥ 0,8, margen neto > 0): ≥4 Strong, ≥2 Moderate, si no Weak | `Insufficient` si < 60 % de las comprobaciones o < 2 disponibles |
| Growth | de 5 métricas (YoY y CAGR 3 años de ingresos/EBIT/FCF) cuántas > 5 %: ≥4 Strong, ≥2 Moderate | idem |
| Valuation | percentil medio de P/E, P/S y (100 − percentil de FCF yield) frente a la **propia historia de 5 años**: ≤30 Cheap, ≥70 Expensive | `Insufficient` sin historia |
| Trend / Momentum / Relative strength | clasificación de tendencia; retornos 63/126 d y mom 12-1; fuerza relativa 63/126/252 d vs benchmark proxy | `Insufficient` si faltan datos |
| Risk | vol 63d y drawdown 12M por tramos (Low/Moderate/High) | |
| Data quality | precio ≥ 252 barras, frescura EOD, cobertura fundamental ≥ 80 % | High/Medium/Low |

No existe universo actual de pares con fundamentales, así que **no hay percentiles de industria/sector**: sólo la propia historia (valoración). Los umbrales absolutos están versionados, no se han optimizado con resultados y se muestran como tales. Una categoría con poca cobertura es `Insufficient`, nunca «Strong»; lo ausente **no** se imputa a 50.

## Positivos y riesgos
Hasta 3 + 3 desde reglas estructuradas, cada uno con `reason_code`, `metric`, `value`, `reference`, `rendered_text` (nada generativo): margen operativo/FCF altos, crecimiento, cobertura de intereses, shareholder yield, tendencia, fuerza relativa, valoración cara/barata vs su historia, beneficios negativos, apalancamiento, ratio corriente < 1, drawdown, volatilidad, sobreextensión, baja conversión de caja.

## Perfiles especiales
Bancos/aseguradoras/REIT: fundamentales y crecimiento `Insufficient` con la nota «SPECIALIZED FUNDAMENTAL PROFILE NOT YET SUPPORTED».

## Predicción
Panel siempre `NOT_YET_VALIDATED` mientras no exista un Champion calibrado (registro `models.role`); sin probabilidades, retornos esperados ni confianza. Contrato preparado (6M/12M, P10…P90, calibración, OOD).

## Versión y tests
`analysis_score_version = analysis-v0.1`. Tests: `test_analysis_labels_never_strong_with_poor_coverage_and_missing_is_not_50`, contrato API, componente `PredictionPanel`.
