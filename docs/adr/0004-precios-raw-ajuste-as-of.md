# ADR-0004 — Precios raw + ajuste as-of

**Estado:** aceptada · **Fecha:** 2026-10-01

## Contexto
Los proveedores entregan precios "ajustados" calculados con TODOS los eventos conocidos
hoy. Usarlos en un snapshot histórico filtra información de splits y dividendos futuros
(los niveles de precio pasados cambian por eventos que aún no han ocurrido).

## Decisión
- Persistir únicamente OHLCV **raw** y la tabla de `corporate_actions` (con `ex_date`,
  `announced_at`, `ratio`, `cash_amount`, `currency`).
- `adjusted_series(security_id, as_of)` recalcula los factores aplicando sólo eventos con
  `ex_date ≤ as_of` (y `announced_at ≤ as_of`).
- Total return: reinversión del dividendo bruto en el ex-date (configurable neto de
  retención por mercado en fase de costes).
- Se cachea por `(security_id, as_of_bucket)` porque es inmutable.

## Consecuencias
+ Imposible que un split futuro altere una feature. − Cálculo extra (vectorizado, barato).
