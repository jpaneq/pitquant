# ADR-0010 — Inmutabilidad de snapshots y predicciones

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- `feature_snapshots`, `predictions`, `live_predictions`, `holdout_access_log`: append-only.
- Doble barrera: listener SQLAlchemy `before_update`/`before_delete` que lanza
  `ImmutableRecordError`, y trigger PL/pgSQL en PostgreSQL (migración 0001) que rechaza
  `UPDATE`/`DELETE` incluso desde SQL directo.
- Cada snapshot tiene `content_hash` = SHA-256 del JSON canónico (claves ordenadas, floats
  con `repr` estable, timestamps ISO-UTC). La predicción referencia el hash; el test de
  reproducibilidad regenera el snapshot y compara hashes.
- Correcciones = nueva fila con `supersedes_id`, nunca edición.
