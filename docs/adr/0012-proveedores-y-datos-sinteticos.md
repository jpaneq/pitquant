# ADR-0012 — Datos sintéticos etiquetados y proveedores intercambiables

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- Interfaces ABC: `PriceProvider`, `FundamentalProvider`, `IndexMembershipProvider`,
  `CorporateActionsProvider`, `MacroProvider`, `AnalystEstimatesProvider`.
- Cada provider declara `name`, `is_synthetic`, `is_point_in_time` y `capabilities`.
- `SyntheticProvider`: datos generados con semilla, nombres `SYN*`, `source="SYNTHETIC"`.
  El Security Master marca `is_synthetic=True`; la API y los informes muestran una banda
  "DATOS SINTÉTICOS" y los backtests sobre ellos no pueden registrarse como resultados reales.
- `AnalystEstimatesProvider` sin histórico PIT verificable → la feature queda desactivada
  (`capabilities.point_in_time_estimates = False`), nunca reconstruida.
