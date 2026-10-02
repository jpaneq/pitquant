# ADR-0028 — Developer UI V0.1

**Estado:** aceptada · **Fecha:** 2026-10-02

Interfaz mínima de desarrollo, no la UI final. Toda la lógica vive en FastAPI (`pitquant.api.dev`, rutas
`/dev/*`, sólo lectura); la página (`/dev/`) es HTML + JS sin dependencias que sólo llama a esos endpoints.
Pantallas: System Status (gates D02/D05/SEC/CNMV/identidad/market data/corporate actions/total
return/feature engine/labels/modelo y **holdout SEALED**), Security Explorer (ticker, CUSIP, ISIN, nombre
de emisor o `CIK:`), Time Machine (`reconstruct`), Feature Inspector (valor, estado, razón, fórmula y
procedencia por feature) y Universe Explorer (S&P 500 por fecha con evidencia, no resueltos y readiness).
Las fechas del holdout se rechazan (HTTP 403). No hay BUY/HOLD/SELL, plan de operación, SL/TP,
probabilidades ni optimización de cartera.
