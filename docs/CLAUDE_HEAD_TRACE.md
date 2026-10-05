# Claude HEAD trace: d90309e → 1b0cc6a

Two commits and eighteen changed paths. Both are preserved. No D02, fold generation, target semantics, holdout, readiness gate, model or feature contract changed. The new API payload belongs to the trade viewer only.

## c7569b0

Visor visual de operaciones: velas, tendencia, entrada/objetivo/stop y salida de cada decisión de la rutina y de las simulaciones (/operaciones, /trades)

- `frontend/src/App.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/AppSwitcher.tsx`
- `frontend/src/features/bitcoin/BitcoinPage.tsx`
- `frontend/src/features/routine/RoutinePage.tsx`
- `frontend/src/features/trades/OperacionesPage.tsx`
- `frontend/src/features/trades/TradeChart.tsx`
- `src/pitquant/api/app.py`
- `src/pitquant/api/trades.py`
- `src/pitquant/positions/trade_view.py`
- `tests/unit/test_trade_view.py`

## 1b0cc6a

BTC: pestañas arriba con explicación y contenido propio por pestaña (Analyzer / Prediction Lab / Strategy Lab / Simulations / Research)

- `frontend/artifacts/btc-analyzer.png`
- `frontend/artifacts/btc-live-market.png`
- `frontend/artifacts/btc-simulation.png`
- `frontend/artifacts/btc-time-machine.png`
- `frontend/artifacts/positions-btc.png`
- `frontend/artifacts/positions-equity.png`
- `frontend/artifacts/routine-report.png`
- `frontend/src/features/bitcoin/BitcoinPage.tsx`

One synthetic unit test was added in `test_trade_view.py`, covering bars, SMA200, frozen entry/target/stop levels, markers and pending outcomes. No existing PIT/target/fold tests were edited.
