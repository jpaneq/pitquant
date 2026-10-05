> Análisis sustituido por [PROPUESTA-first-ml-security-coverage.md](PROPUESTA-first-ml-security-coverage.md), todavía NO aplicada. La aproximación de independencia y los umbrales ilustrativos de este documento no justifican cambiar el gate.

# Propuesta (NO aplicada) — Research minimum security coverage

Estado: PROPUESTA para decisión del propietario. **No se ha modificado ningún gate**: `required_securities = 100` sigue vigente.

## Origen del valor 100
Aparece como umbral de `SECURITIES` en `research/model_contracts.py` (RUN 3, ADR-0048) y como «≥ 96 cohortes» en `research_readiness.py` (BASELINE_TRAINING_READY). No está derivado de un cálculo estadístico documentado: es un orden de magnitud razonable para una sección transversal mensual.

## Razón estadística (qué sí importa)
El poder de un IC/clasificador depende del número de observaciones independientes por mes (secciones transversales) y de su cobertura temporal, no de un conteo total de tickers. Con ~45 valores elegibles por mes, el error estándar de un IC mensual ≈ 1/√45 ≈ 0,15; promediado sobre ≥36 meses no solapados baja a ≈ 0,025. Con 100 valores ≈ 0,017. La diferencia 45 vs 100 reduce potencia en ≈ 1,5×, no la invalida.

## Alternativas
A) Mantener 100 (estado actual). B) Exigir un mínimo de nombres elegibles POR MES (p. ej. ≥ 40) y un nº mínimo de meses con esa cobertura, además de un máximo de concentración sectorial. C) Mantener 100 como objetivo y 40 por mes como mínimo operativo.

## Impacto
Hoy 45 valores tendrían filas elegibles si D05 se aceptara; con 100 el gate no cierra nunca sin ampliar el universo (que sigue siendo la lista actual, no la membresía histórica).

## Recomendación
Opción B/C tras aceptar D02 y D05; no relajar antes. Decisión del propietario.
