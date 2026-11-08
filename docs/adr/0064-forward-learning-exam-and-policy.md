# ADR-0064 — Aprendizaje continuo: examen único, reentreno mensual y política autocorregida

Fecha: 2026-11-08. Estado: aceptado por el propietario ("algoritmo que vaya aprendiendo a
futuro"). Parte de `codex/forward-pilots-v1` (ADR-0063). Sin órdenes automáticas.

## Contexto

V1 (ADR-0063) son dos regresiones logísticas fijas entrenadas antes del sello (acciones
< 2022-10-01, BTC < 2025-10-01). El reentreno era manual y nunca promovía. El propietario
quiere un sistema que aprenda solo. La base de datos del otro Mac no está disponible; todo se
reconstruye con datos gratuitos (Yahoo para acciones, Binance para BTC) y V1 se reproduce con
las mismas 27.370 / 2.560 filas.

## Decisión

Código en `src/pitquant/forward/learning.py`; ciclo diario `scripts/forward_daily.py`.

1. **Examen único, por mercado.** Se usa una sola vez el periodo sellado para lo que se
   reservó: decisiones desde el sello hasta el último objetivo maduro. Dos brazos sobre las
   mismas filas: **A** V1 congelado; **B** el *procedimiento* de aprendizaje (reentreno el día 1
   de cada mes con etiquetas maduras antes de ese día; mismas features y parámetros que V1).
   Reglas preregistradas en `EXAM_PROTOCOL` antes de calcular nada; predicciones congeladas
   (fichero + SHA-256 en `EXAM_PREDICTIONS`) antes de leer resultados. Métrica principal: log
   loss. Intervalos del 90 % por bootstrap de **meses completos** (horizontes solapados).
2. **Política.** `LEARNING` si la media de logloss(A) − logloss(B) > 0; si no, `FROZEN_V1`.
3. **Reentreno mensual** (`model:forward-logistic-price-v2-learning:<mercado>:<AAAA-MM>`) con
   todas las etiquetas maduras antes de la fecha. Universo de acciones: 55 grandes compañías
   de EE. UU. de la lista de la rutina (congelado en el código). Bajo `LEARNING`, el último
   reentreno es el campeón automáticamente: lo validado es el procedimiento.
4. **Autocorrección.** V1 y el último reentreno emiten pronósticos reales a la vez. Con
   ≥ 200 pares maduros en ≥ 20 fechas, la política cambia si el intervalo del 90 % (bootstrap
   por fecha) de la diferencia de log loss excluye el cero a favor del otro brazo. Cada cambio
   queda en un registro `POLICY` inmutable.
5. **Programación**: `Instalar_aprendizaje_diario.command` (launchd, 23:30 todos los días).

Cambios compatibles en el motor: `fit_model` acepta `cutoff`, `family`, `label` y
`archive`; por defecto reproduce V1. Binance: si `data-api.binance.vision` rechaza la
conexión se usa `api.binance.com` (mismas velas; el host queda en el archivo crudo).

## Resultado del examen (2026-11-08, vintage actual, no PIT histórico)

| Mercado | Decisiones | Acierto V1 / reentreno / siempre sube | Log loss V1 / reentreno / tasa base | Señal vs tasa base |
|---|---|---|---|---|
| Acciones (55, oct-2022 → oct-2026, 49 meses) | 55.495 | 57,0 % / 57,0 % / 57,0 % | 0,6876 / 0,6859 / 0,6873 | Ninguno (intervalos tocan cero) |
| BTC (oct-2025 → oct-2026, 13 meses) | 373 | 52,0 % / 48,8 % / 49,3 % | 0,6922 / 0,6951 / 0,7030 | Ninguno |

Acciones: el reentreno mejora a V1 (+1,7 milésimas de log loss, intervalo 0,4 a 3,1) →
política `LEARNING`. BTC: diferencia indistinguible de cero (13 meses) → `FROZEN_V1`.
**Ninguno de los dos brazos demuestra ventaja frente a predecir la tasa base**: hoy las
features de solo-precio no contienen señal útil a 20 sesiones / 30 días. El sistema aprende,
pero no tiene todavía nada que explotar.

## Consecuencias

- El periodo sellado queda consumido para esta familia; no vuelve a ser prueba virgen.
- Mejorar requiere **features nuevas** (fundamentales, value/quality ya investigados en
  `docs/research/QUANT_ALGORITHM_EVIDENCE_2026-11-01.md`), registradas como versión nueva con
  su propio protocolo; el reentreno de coeficientes por sí solo no crea señal.
- Sesgo de supervivencia (universo de hoy) y vintage actual: el examen es retrospectivo.
- Costes no modelados; ningún resultado se presenta como rentabilidad.
