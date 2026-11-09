# ADR-0065 — Fondos de inversión elegidos por el propietario (por ISIN)

Fecha: 2026-11-08. Estado: aceptado (petición del propietario: "darle fondos para analizar").

## Decisión

- El propietario añade fondos de inversión por **ISIN** desde `/pilotos` («Mis fondos»). Se
  valida el dígito de control (ISO 6166) y se busca en Yahoo la serie de valor liquidativo
  (identificador Morningstar `0P….F`). Sólo se aceptan listados `MUTUALFUND` con sufijo `.F`,
  mapeado al calendario `XFRA` en `market/exchanges.py`.
- La lista es **append-only** en el diario (`FUND_WATCH` / `FUND_UNWATCH`); quitar un fondo no
  borra su historial.
- Los valores liquidativos entran por la tubería normal de precios (`normalize` + `store_batch`,
  archivo crudo). Un VL no tiene máximos, mínimos ni volumen: `high = low = close`, volumen
  ausente (lo imputa el modelo como cualquier hueco).
- Cada noche el **campeón de acciones** (el modelo que decida la política vigente) emite un
  pronóstico por fondo a 20 sesiones `XFRA`, congelado antes del resultado
  (`FUND_PREDICTION`), con revisiones en las sesiones 1/5/10/20 (`FUND_REVIEW`/`FUND_OUTCOME`).
  Si el campeón usa fundamentales (v3), en los fondos van como ausentes.
- Los fondos se miden **aparte**: tipos de registro propios; nunca entran en el examen, los
  reentrenos, la política ni las estadísticas de acciones.
- Requisitos: ≥ 201 VL para tener pronóstico; VL de hace más de 7 días ⇒ `STALE_NAV`, sin
  pronóstico (no se rellena después).

## Consecuencias

- El modelo no se entrenó con fondos: el acierto en fondos dice si transfiere, nada más.
- Las clases de distribución (que reparten dividendos) infravaloran el retorno; las de
  acumulación lo recogen en el VL.
- Datos de Yahoo/Morningstar: no oficiales, uso personal.
