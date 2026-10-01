# ADR-0003 — Almacenamiento: PostgreSQL + Parquet/DuckDB

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- **PostgreSQL 16**: Security Master, membresías, corporate actions, registro de modelos,
  predicciones, snapshots, experimentos, accesos al holdout, data quality issues.
  Integridad referencial, triggers de inmutabilidad, transacciones.
- **Parquet particionado** (`dataset/market=XNYS/year=2020/…`) + **DuckDB** para OHLCV y
  `fundamental_facts` masivos: lectura columnar, `ASOF JOIN` nativo, sin servidor.
- **SQLite en memoria** sólo para tests: los modelos SQLAlchemy usan tipos portables.
  Los tests de integración contra PostgreSQL real corren en CI (servicio Docker).

## Justificación
Volumen esperado: ~1.500 valores históricos × 25 años × 252 sesiones ≈ 10 M filas OHLCV;
cabe en Parquet en un Mac Mini. PostgreSQL aporta garantías que DuckDB no ofrece para
registros concurrentes e inmutables.

## Alternativas
TimescaleDB (añade dependencia sin necesidad clara), ArcticDB (buen candidato si el volumen
crece; la capa `PriceStore` está desacoplada para poder sustituirlo).
