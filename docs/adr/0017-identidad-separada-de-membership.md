# ADR-0017 — Identidad de la emisión separada de la membership; elegibilidad para validación final

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Amplía:** ADR-0013, ADR-0014

## Contexto
Una fuente puede demostrar que «la compañía que cotizaba como XYZ» era miembro del índice
en una fecha sin demostrar **qué emisión** era. Hasta ahora:
- la reconstrucción provisional del S&P 500 proyectaba hacia atrás el ticker del snapshot
  moderno durante toda la historia;
- en el IBEX, una reentrada sin ISIN se suponía la misma emisión que la salida anterior.

Ambas cosas convierten un ticker en identidad de forma silenciosa. Un backtest que use esas
observaciones puede atribuir precios o fundamentales de otra emisión.

## Decisión
1. **`identity_status`** (`RESOLVED` | `IDENTITY_UNRESOLVED`) en `index_events` e
   `index_membership`, independiente de que la membership se conozca. Sólo es `RESOLVED`
   cuando la fuente fija la emisión con un identificador (ISIN/CUSIP/id permanente) en esa
   fecha.
   - S&P licenciado: identificador obligatorio → `RESOLVED`.
   - S&P provisional: los miembros iniciales obtenidos invirtiendo anuncios son
     `IDENTITY_UNRESOLVED` y **sin ticker** en `coverage_start`. Los tickers sólo se
     registran desde la fecha en que una fuente los afirma (`ticker_observations`: snapshot
     en su fecha, anuncio en la suya). Las altas por anuncio con identificador son `RESOLVED`.
   - BME: `RESOLVED` sólo con ISIN del aviso o de otro documento oficial fechado
     (`identities[(ticker, fecha)]`). **Una reentrada sin ISIN recibe identidad nueva** y
     queda `IDENTITY_UNRESOLVED`; nunca se fusiona con la emisión anterior.
2. **Fail closed en backtests:** `IndexUniverse.backtest_universe()` lanza
   `IdentityUnresolvedError` si algún miembro de esa fecha no está resuelto. No se eliminan
   miembros en silencio (eso sería sesgo de supervivencia). `universe()` sigue disponible
   para investigación y expone `identity_status`.
3. **`membership_builds.eligible_for_final_model_validation`**: `true` sólo si la fuente es
   `CANONICAL`, el build es `ok` y no hay intervalos sin resolver. Por defecto `false`
   (incluidos los builds anteriores a la migración `0002`).
4. **Puerta del holdout:** `evaluate_candidate_on_holdout` exige `membership_build_ids` (el
   linaje de universo del candidato) y rechaza, **antes de desbloquear y registrar**, cualquier
   build no elegible. Un resultado provisional no puede tocar el holdout ni promover un
   Champion.

## Consecuencias
- El IBEX 35 no es backtestable hasta aportar ISIN oficiales por miembro y fecha (ver
  `docs/BME_PARSER.md`). Es deliberado: mejor sin dato que con dato de otra emisión.
- El S&P 500 provisional sirve para investigación de ingestión, nunca para backtest
  definitivo.
- Migración `0002_identity_status` (columnas + CHECK; los valores por defecto preservan
  filas existentes).
