# ADR-0013 — Membership de índices derivada de un flujo de eventos

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Sustituye parcialmente:** ADR-0007

## Contexto
D-02 y D-03 exigen que toda entrada/salida tenga causa, que se distinga anuncio de
efectividad, que un cambio de ticker no se confunda con rotación y que una corrección
posterior del proveedor no altere reconstrucciones antiguas.

## Decisión
- Los proveedores **no cargan intervalos**: emiten eventos inmutables (`index_events`):
  `INDEX_ADD`, `INDEX_DELETE`, `TICKER_CHANGE`, `ORDINARY_REVIEW`, `EXTRAORDINARY_REVIEW`
  (padres de sus altas/bajas vía `parent_event_id`) e `INITIAL_SNAPSHOT`.
- `build_membership` valida la secuencia (no añadir un miembro, no eliminar un no miembro,
  cambio de ticker sólo de miembros, tamaño en `expected_size` tras cada fecha) y genera un
  **`membership_build` inmutable**. Cada intervalo guarda `membership_source`,
  `source_event_id`, `exclusion_event_id`, `effective_from`, `effective_to`,
  `source_confidence` y `raw_source_hash`.
- `TICKER_CHANGE` mantiene el `security_id` y el intervalo; en `ticker_history` se cierran
  y abren filas (dos registros, mismo valor).
- `announced_at` y `effective_date` son campos distintos. `universe()` usa sólo el efectivo;
  `announced_changes(as_of)` expone lo anunciado y aún no efectivo, para uso event-driven.
- Confianza: `CANONICAL`, `PROVISIONAL_RESEARCH_SOURCE`, `SYNTHETIC`, `CROSSCHECK_ONLY`.
  Las fuentes `CROSSCHECK_ONLY` (Wikipedia, Kaggle, repos comunitarios) **no pueden
  generar builds**; sólo `cross_check()` para QA. `IndexUniverse.source_status()` permite
  etiquetar como no definitivo todo backtest sobre un build provisional.
- Una corrección del proveedor = bytes nuevos = `raw_source_hash` nuevo = build nuevo. Las
  reconstrucciones antiguas siguen siendo reproducibles fijando el `build_id` en su
  `DataVersion`.

## Fuentes
- S&P 500: `SPDJILicensedFileProvider` (CANONICAL, licencia S&P DJI) y
  `SPDJIAnnouncementReconstructionProvider` (PROVISIONAL_RESEARCH_SOURCE: snapshot conocido
  + anuncios oficiales recorridos hacia atrás).
- IBEX 35: `BMEHistoricalCompositionProvider` (CANONICAL: PDF oficial + avisos), ver
  `docs/BME_PARSER.md`.
