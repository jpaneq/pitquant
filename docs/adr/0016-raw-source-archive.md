# ADR-0016 — Archivo de fuentes crudas (raw_source_archive)

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- Todo documento externo relevante (headers e instancias SEC, submissions, companyfacts,
  ficheros S&P DJI, PDF histórico de BME, avisos) se guarda **byte a byte** en un almacén
  direccionado por SHA-256 (`data/archive/ab/cd/<sha>`), escritura atómica.
- `raw_source_archive` registra cada obtención: proveedor, URL/identificador,
  `retrieved_at`, `published_at` (publicación/aceptación), SHA-256, MIME, tamaño, ruta y
  `parser_version`. Append-only.
- La lectura re-verifica el hash: un objeto alterado o corrupto hace fallar la
  reconstrucción en vez de alimentarla.
- Eventos de índice, builds y hechos llevan `raw_source_hash` / `archive_id`, de modo que
  siempre se puede responder *por qué* el sistema creó un universo o un fundamental.

## Consecuencias
Nunca dependemos de que una URL siga existiendo o sirva el mismo contenido. El volumen
(SEC: miles de filings por empresa grande) se controla con deduplicación por hash.
