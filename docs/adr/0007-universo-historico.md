# ADR-0007 — Universo histórico y ocultación de información de salida

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- `index_membership(security_id, index_code, inclusion_date, exclusion_date,
  inclusion_reason, exclusion_reason, announced_at, source)` con intervalos semiabiertos
  `[inclusion, exclusion)` y validación de no solapamiento por `(security_id, index_code)`.
- `universe(index, as_of)` devuelve `UniverseMember` que **no expone** `exclusion_date`
  ni `exclusion_reason` cuando son posteriores a `as_of`.
- Las fechas de membresía son de **efectividad** (no de anuncio). Para análisis
  event-driven sobre anuncios se usa `announced_at` por separado.
- Prohibido construir el universo histórico a partir de constituyentes actuales: el
  `IndexMembershipProvider` debe declarar `is_point_in_time = True` o el ingestor lo rechaza.

## Consecuencias
Requiere una fuente histórica de cambios de índice (ver `PENDING_DECISIONS.md`, D-02/D-03).
