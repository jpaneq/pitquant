# ADR-0041 — Posiciones simuladas y revisión «ampliar / mantener / vender»

Estado: aceptada (2026-10-04). Migración `0022` (tablas append-only). Acciones y BTC.

## Decisión
1. **Compras simuladas** (`paper_positions` + `paper_position_events` OPEN/ADD/REDUCE/CLOSE): sin broker ni dinero real. El estado (cantidad, coste medio, P&L realizado) se pliega del log de eventos. El stop protector se fija al comprar (usuario, o por defecto precio − 2·ATR14, regla `ATR14_2X_AT_OPEN`).
2. **Revisión V0** (`positions/review.py`, `position-review-v0`): motor de REGLAS determinista, **no** predicción ni validado con backtest. Reglas: tendencia, media de 200, momentum 6 m, valoración y fundamentales (sólo acciones; en BTC se omiten y se dice), soporte cercano. Cada regla aporta `raw × peso` y los pesos dependen del **horizonte en meses** (corto ≤3, medio ≤8, largo ≥9). Reglas duras: stop tocado → VENDER; objetivo cumplido (con señal ya débil) o horizonte vencido sin respaldo → VENDER. Umbrales `sell ≤ −2`, `add ≥ +2,5`; ampliar exige tendencia alcista, sin estiramiento (≤3 ATR sobre la media 50, RSI ≤70), objetivo no cumplido y ≥1 mes de plazo. Pesos y umbrales: `UNVALIDATED_STRATEGY_PARAMETER`; cambiarlos = versión nueva del motor.
3. **Faltan datos ⇒ la regla se salta**, nunca se adivina (`missing_rules`). Sin precio real de BTC (`PRICE_UNAVAILABLE`) no se puede comprar y nunca se usa un fixture como respaldo.
4. **La revisión en vivo no se guarda**; guardarla es una acción explícita (`position_reviews`, con reglas, contexto y hash) para poder evaluar más tarde si las recomendaciones habrían ayudado.
5. **Trade plan en todas las vistas:** acciones (bajo el gráfico) y BTC (`GET /btc/trade-plan`, última vela diaria cerrada, sin congelar).
6. Fixture/E2E: posiciones marcadas `is_synthetic` y «SYNTHETIC TEST DATA».
