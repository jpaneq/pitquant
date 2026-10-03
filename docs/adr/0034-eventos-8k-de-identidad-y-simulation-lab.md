# ADR-0034 — Eventos 8-K de identidad (D-02) y Simulation Lab V0 (paper trading)

**Estado:** aceptada · **Fecha:** 2026-10-03 · **Migraciones:** `0015` (tipos de sucesión), `0016` (Simulation Lab).

## A. D-02: identidad con evidencia SEC
1. **Tres eventos 8-K** (Priceline→Booking, Coach→Tapestry, Praxair→Linde) se aplican sólo si el 8-K se descarga y archiva (SHA-256), su propia
   cabecera dice 8-K y el accession declarado, el texto contiene los nombres, y las listas 13(f) muestran los CUSIP declarados.
   - Priceline→Booking: `NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY`; el cambio legal de nombre (2018-02-21) y el de ticker (PCLN válido hasta
     2018-02-26, BKNG desde 2018-02-27) NO se colapsan; la fecha de transición de CUSIP queda `PARTIAL`.
   - Coach→Tapestry: `NAME_TICKER_CHANGE_SAME_SECURITY` (2017-10-31), membresía continua, CUSIP `PARTIAL`.
   - Praxair→Linde plc: `SECURITY_REPLACEMENT_SUCCESSOR` 1:1 (2018-10-31), security nueva, continuidad de membresía.
2. La fecha de CUSIP `PARTIAL` no bloquea la membresía mensual (membresía READY, identidad PARTIAL). Abreviaturas de la lista 13F
   (HLDGS, GRP, INTL) se expanden con una tabla fija, nunca por similitud.
3. Los gaps llevan `blocks_monthly_membership` y `blocking_decision_dates`. Resultado: blockers de membresía 54 → 46; identidad 11 → 8.

## B. Simulation Lab V0
- **Paper trading y forward validation; sin dinero real, sin broker, sin tocar modelos.** `MANUAL_SIMULATION` activo; `AUTO_PAPER` es un contrato
  DESACTIVADO mientras Prediction Engine sea `NOT_YET_VALIDATED`.
- **Snapshot T0 inmutable** (`simulations`): precio, fundamentales, técnico, valoración, S/R, plan, régimen, calidad de datos, versiones;
  `prediction_status = NOT_YET_VALIDATED`, sin probabilidad/retorno/confianza. Extensiones BTC (funding, open interest, basis, on-chain) nulas;
  `asset_type` EQUITY | BTC (sólo EQUITY tiene motor).
- **Plan** `PITQUANT | USER_MODIFIED | USER_DEFINED`; USER_MODIFIED guarda el plan original y el simulado.
- **Máquina de estados** (daily bars): CREATED, WAITING_ENTRY, ENTERED, PARTIAL_TP, TP1, TP2, STOPPED, INVALIDATED, EXPIRED, CLOSED_MANUAL,
  AMBIGUOUS_INTRABAR (nunca se elige la lectura favorable; los gaps se resuelven en la apertura). Con dos objetivos, 50 % se cierra en el 1.
- **Resultados** en tablas aparte y append-only (`simulation_outcomes`): retorno, exceso vs benchmark, R, MFE, MAE, max drawdown, días a entrada/stop/TP,
  holding; `prediction_direction_correct` y `trade_plan_execution_correct` quedan NULL hasta que exista un modelo validado.
- **Evolución de la tesis** (`simulation_observations`): snapshots posteriores comparados con T0, sin modificarlo. **Post-mortem** explícito y
  auditable (`simulation_postmortems`), sólo para simulaciones cerradas; ninguna causa automática.
- **Sin aprendizaje automático:** el Simulation Lab no escribe en datasets, versiones de modelo ni champion; puede generar `ResearchHypothesis`
  (Challenger → backtest → walk-forward OOS → comparación → promoción HUMANA). El Research Lab sólo LEE `SimulationEvidenceSummary`
  (`/research/simulation-evidence`). Tests estáticos impiden que dataset builder, features o backtest lean tablas de simulación.
- **UI:** `/simulations`, `/simulations/:id` (banner PAPER TRADE — NO REAL MONEY; gráfica, timeline, snapshot, plan original vs simulado,
  post-mortem) y botón «Simulate trade» en el Analyzer, deshabilitado con `PRICE_DATA_REQUIRED` sin precios (KO). Métricas agregadas sólo con N ≥ 10.
- **Límites V0:** long only; retorno de precio (sin dividendos); splits posteriores al T0 se reexpresan en unidades de T0; una decisión intradía
  empieza a operar a partir de la sesión siguiente.
