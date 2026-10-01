# ADR-0001 — Modelo de datos bitemporal y append-only

**Estado:** aceptada · **Fecha:** 2026-10-01

## Contexto
El requisito central es que ninguna simulación use información no publicada en `as_of`.
Los datos fundamentales y macro se revisan; los índices cambian; los tickers se reutilizan.

## Decisión
Todo hecho se guarda con dos ejes temporales: validez (`period_start`, `period_end`) y
conocimiento (`available_at`, `ingested_at`). Las revisiones son filas nuevas con
`revision_id`; nunca `UPDATE` sobre datos de mercado o fundamentales. La lectura se hace
siempre mediante `as_of_view(as_of)`.

Si la fuente da sólo fecha de publicación, `available_at` = cierre de esa sesión en la
zona horaria del mercado + latencia configurable (`pit.default_publication_lag_minutes`).

## Alternativas descartadas
- *Snapshots diarios completos*: reproducibles pero caros y no capturan la hora de publicación.
- *Tablas "última versión"*: imposibilitan reconstruir el pasado → look-ahead garantizado.

## Consecuencias
+ Reconstrucción exacta de cualquier fecha. + Auditoría trivial.
− Más almacenamiento y consultas as-of más complejas (mitigado con DuckDB `ASOF JOIN`).
