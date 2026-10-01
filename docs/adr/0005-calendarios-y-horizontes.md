# ADR-0005 — Calendarios bursátiles y aritmética de horizontes

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- Librería `exchange_calendars` (XNYS para NYSE/Nasdaq, XMAD para BME) envuelta tras la
  interfaz `MarketCalendar`, para poder sustituirla o parchear festivos.
- Todos los timestamps son timezone-aware; internamente se normaliza a UTC. Pasar un
  datetime naive lanza `NaiveDatetimeError`.
- Horizonte de `n` meses: `fecha_ejecución + n meses de calendario` → primera sesión
  `≥` esa fecha. Nunca `+180/+365 días`.
- `next_session_open(ts)`: apertura de la primera sesión cuyo `open > ts` (estricto).
  Gestiona cierres anticipados y DST porque usa los horarios del calendario.
- Si el calendario no cubre el rango solicitado → error, no extrapolación.

## Alternativa
`pandas_market_calendars`: equivalente; se eligió `exchange_calendars` por mejor
mantenimiento de XMAD y API de sesiones/minutos más explícita.
