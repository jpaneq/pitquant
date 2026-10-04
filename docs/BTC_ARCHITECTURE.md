# BTC V0 architecture

Branch `feature/btc-engine-v0`, source `f212b3d061d3bf94428c5a0fb9fd70149298ae39`. Independent vertical; no master merge.

Canonical decision: 00:00:00 UTC, preceding completed 1D candle; Bitcoin runs seven days/week. Provider latency is explicit: forward snapshots may use data retrieved within 15 minutes after close, never a candle ending after close. Manual simulations created intraday start at the following UTC midnight. Prices are BTCUSDT; USDT is not USD.

`btc/providers.py` → RawSourceArchive + append-only BTCDatum revisions → `btc/features.py` → BTCFeatureSnapshot → five BTCPredictionSnapshots → explicit reveal / BTCResearchRecord. All snapshots include data/feature/model/strategy/engine versions, commit SHA and hashes. Model outputs remain NULL until validated.

Simulation, SimulationEvent, SimulationObservation, SimulationOutcome, SimulationPostMortem, ResearchHypothesis, engine registry and replay are reused. `btc-v0` wraps the frozen SimulationEngineV1 daily OHLC algorithm; no edits to that engine. Compatibility tests cover fractional BTC, weekends and conservative ambiguity. BTC events persist its buy-and-hold benchmark reference for deterministic replay. Equity list/summary/update queries explicitly retain equity scope. No D-02/SEC/S&P or equity feature/horizon changes.

Four new append-only tables have ORM protections and PostgreSQL UPDATE/DELETE triggers. Initial branch revision `btc_v0_20261004` descends from `0019`; `btc_v0_20261004_r1` preserves reverting source vintages and uniquely pins a decision/cohort/feature version. MUST_REBASE_MIGRATIONS_BEFORE_MERGE. Reconcile master migration graph after a future rebase, regenerate schema documentation and rerun PostgreSQL upgrade/check/downgrade. Migration downgrade is for disposable test databases; repeated reverting vintages cannot be collapsed into the old unique key without losing evidence.

Pages: `/bitcoin`, `/bitcoin/predictions`, `/bitcoin/strategies`, `/bitcoin/simulations`, `/bitcoin/research`. Evidence selectors isolate HISTORICAL_OOS, FORWARD_PAPER, SYNTHETIC. Fixtures explicitly say SYNTHETIC BTC and never constitute market evidence.

Run the isolated archive:

```sh
PITQUANT_DATABASE_URL=sqlite:///data/btc.db python scripts/btc_archive.py --discover --activate
PITQUANT_DATABASE_URL=sqlite:///data/btc.db python scripts/btc_archive.py --readiness-only
```

The local database and originals under `data/` are intentionally excluded from Git. A Codex heartbeat `btc-archivo-forward-horario` runs hourly at minute 10 in this worktree; it collects originals, freezes daily closes only within the latency window and updates existing paper trades. No automatic prediction trading. Keep this worktree available, computer on and app running. Missed closes stay missing. Back up the local DB and archive together. CLI app startup must use this worktree's `src` and BTC DB, not the equity DB.

Optional interfaces: BitcoinCoreNetworkProvider = NOT_CONFIGURED; BTCMacroSnapshot optional. No Glassnode, entity-adjusted core data, broker keys or real order execution.
