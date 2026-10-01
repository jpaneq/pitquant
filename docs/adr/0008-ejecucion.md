# ADR-0008 — Ejecución: next_session_open por defecto

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
- `signal_timestamp = as_of`; las features sólo usan barras con cierre `< as_of`.
- `execution_timestamp = next_session_open(as_of)` (estrictamente posterior).
- Modos alternativos por configuración: `next_close`, `next_vwap` (requiere datos
  intradía; hasta entonces lanza `NotImplementedError` explícito), `delay_sessions`.
- El precio de entrada nunca puede tener timestamp `≤ signal_timestamp`; existe test.

## Consecuencias
Captura el gap overnight (realista y conservador frente a ejecutar al cierre de la señal).
