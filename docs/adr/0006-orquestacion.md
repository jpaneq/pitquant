# ADR-0006 — Orquestación: Prefect 3 (desacoplada)

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
Prefect 3 autoalojado para ingestión diaria, refresh de features, análisis live,
backtests programados y monitorización.

## Justificación
- Python puro, ligero (cabe junto a PostgreSQL en un Mac Mini de 16 GB), self-hosted sin
  dependencia de nube, reintentos y caché por tarea nativos.
- Airflow: más pesado y orientado a DAGs estáticos. Dagster: excelente modelo de *assets*
  y lineage, pero el lineage ya lo garantizan nuestras propias tablas (`provenance`,
  `feature_snapshots`), así que su ventaja principal sería redundante.

## Desacoplamiento
Los jobs en `pitquant.jobs` son **funciones puras e idempotentes** que reciben fecha y
config. Prefect sólo las envuelve como `@flow/@task`; sustituir el orquestador no toca la
lógica.
