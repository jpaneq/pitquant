# BTC Engine V0 — delivery report

This delivers independent BTC contracts, auditable UI, archive and test harness. It does not claim scientifically validated prediction, a real OOS baseline, or validated strategy performance.

1. **Source HEAD:** f212b3d061d3bf94428c5a0fb9fd70149298ae39.

2. **Branch:** feature/btc-engine-v0; independent managed worktree; no merge into master.

3. **Final HEAD:** Resolve with git rev-parse HEAD in this branch; the exact delivered SHA is in the final chat response. This document is included in that commit.

4. **Files changed:** See the inventory below. Equity engine.py and equity features/horizons are unchanged.

5. **Migrations:** btc_v0_20261004 from0019, then btc_v0_20261004_r1. Four append-only tables; PostgreSQL triggers and unique vintage/decision keys.

6. **BTC adapters:** Binance data-only spot, futures funding/OI/basis/taker/long-short and discovered Coin Metrics Community. Bitcoin Core NOT_CONFIGURED.

7. **Spot:** Real calls succeeded; BTCUSDT closed1D bars and raw originals archived. Sparse probes have a middle gap; no complete-history claim.

8. **Funding:** Real calls succeeded; earliest probe2019-09-10, latest collection from2026-04-21; no complete backfill or historical PIT claim.

9. **OI:** Real hourly collection archived; first observed archived exchange timestamp2026-09-13 13:00UTC; first knowledge2026-10-04.

10. **Basis:** Real hourly collection archived; earliest observed2026-09-13 12:00UTC, first knowledge2026-10-04.

11. **Coin Metrics:** Catalog originals persisted; actual access tested per metric. Incremental requests use canonical Z UTC timestamps.

12. **Network actually available:** active_addresses, transaction_count, fees, hash_rate, supply, market_cap, MVRV. transaction_volume, difficulty, realized_cap return403, explicitUNAVAILABLE.

13. **Earliest usable dates:** Historical PIT usable date NULL. Archived metric dates, timestamps, completeness and hashes are in BTC_DATA_READINESS.md. Earliest spot boundary2017-08-18; earliest native network boundary2009-01-04; hash rate2009-01-10; marketcap/MVRV2010-07-19.

14. **BTC_CORE_V0:** Price/momentum/trend/highs/drawdown/volatility/volume and available network. Funding optional. Full definitions BTC_FEATURES_V0.md; true ATH NULL.

15. **Derivatives features:** Funding means/z-score, OIchanges, premium/basis/annualized basis, taker/longshort; sign/extreme states as context. Missing/null reasons and retention visible.

16. **Prediction contract:** Append-only hashes; expected return, p_up, quantiles and uncertainty NULL; NOT_YET_VALIDATED. No invented probabilities or fan.

17. **Horizons:** 7,30,90,180,365 calendar days, separate from equities.

18. **Targets:** Raw log and simple BTC return; UP iff positive. Strategic excess compares matched BTC buy-and-hold only.

19. **Baselines:** Prepared ElasticNet/LogisticRegression with training-only imputation/scaling. Synthetic pipeline execution checked in temporary isolated scikit-learn installation; no real training.

20. **Analyzer:** Bitcoin navigation; transparent feature families, regime, source availability, missing reasons and Why/Provenance.

21. **Prediction Lab:** Five horizon cards with status/expected/p_up/quantiles/model/data quality; frozen inputs and time chart.

22. **Time Machine:** Evidence set/date selection; freeze before reveal; reveal horizon selector; original feature hash retained. Unknown historical data remain absent.

23. **Strategy Lab:** TRADE_PLAN_ONLY rule contract, BUY_AND_HOLD benchmark; PREDICTION_ONLY and HYBRID disabled. No validated strategy superiority.

24. **Trade Plan:** Long MARKET, stop2ATR, TP1+2ATR/TP2+4ATR, half exits, confirmed zones shown; NOT_YET_BACKTEST_VALIDATED; predictor not used.

25. **Simulation integration:** Existing Simulation Lab tables/events/observations/outcomes/postmortems/hypotheses/replay. Engine pinned btc-v0, fractional BTC and24/7 bars; existing equity engine unchanged.

26. **Forward Paper:** Real archive activated2026-10-04; hourly heartbeat ACTIVE. Daily00UTC snapshot with explicit <=15min latency. No auto prediction trade, missed closes stay missing.

27. **Historical harness:** Version/date/horizon inputs; sufficient frozen PIT history required. Purged WF independent horizon baseline, OOS prediction/reveal/error/calibration records prepared. Rule-plan strategy tests reuse simulations and return trade returns/drawdown/R/excess; overlapping trades are never represented as a portfolio curve. Portfolio turnover/ablation are future challenger work.

28. **Blind replay:** Persist immutable T0/features/prediction before outcome access; experimental model record commits before reveal. Exact target and maturity required.

29. **Calibration:** Bins50–55,55–60,60–65,65–70,70–75,75+; expected versus actual. No real OOS calibration exists yet.

30. **Buy-and-hold:** Paper outcomes compare BTC T0 to last execution-bar close, pin reference into replay. CASH0; costs default0/COSTS_NOT_MODELED; no performance claim.

31. **PIT/leakage:** Exchange plus availability cutoffs; future candle/funding/network excluded; revisions append-only including reversion; frozenT0 never recalculated; holdout sealed; no synthetic/forward/historical mixing.

32. **Readiness:** All five historical horizon gates false, derivative history false; zero usable audited historical frozen snapshots.

33. **Scientific first baseline:** Cannot run scientifically with present archive. Readiness returns trained=false/BLOCKED_BY_DATA; criteria unchanged.

34. **OOS results:** None: no real training or evaluation. Synthetic outcomes validate plumbing only.

35. **Exact blockers:** NO_SUFFICIENT_HISTORICAL_PIT_SNAPSHOTS_BEFORE_FROZEN_HOLDOUT; current downloads lack historical publication/revision evidence; price/funding middle gaps; limited derivative retention;403 metrics optional, not mandatory core blockers.

36. **Backend tests:** 667 passed,14 skipped,19 PostgreSQL tests deselected. Inherited optional ML/real-data skips; no BTC PIT skips.

37. **PIT tests:** 302 passed,398 deselected; no skipped PIT tests.

38. **Frontend:** 50 Vitest tests; strict TypeScript/build/lint. Existing lint warnings in WatchlistPage/SeriesChart retained.

39. **Playwright:** 12 passed,1 existing optional visual-spec skipped. Two new BTC tests exercise synthetic paper/postmortem and freeze-before-reveal Time Machine.

40. **PostgreSQL:** 19 passed strict; migration upgrade/check/downgrade OK. Direct SQL BTC snapshot mutation rejected.

41. **GitHub Actions:** Push branch to trigger existing six-job workflow. Verify exact final SHA via gh run list --branch feature/btc-engine-v0 and gh run view; final chat records the observed result.

42. **Migration conflicts/rebase:** MUST_REBASE_MIGRATIONS_BEFORE_MERGE; reconcile graph from0019 with master future migrations and regenerate schema docs. No silent0020 and no merge.

43. **Screenshots:** frontend/artifacts/btc-analyzer.png, btc-simulation.png, btc-time-machine.png. All explicitly SYNTHETIC. Visually reviewed; audit JSON is collapsed behind details in final UI.

44. **Next step:** Preserve and back up forward originals/vintages; audit missed closes and provider access. Obtain documented historical availability before any real baseline. Then version a challenger protocol/holdout, run core baseline OOS before derivatives ablation/boosting. Run the prepared rule-plan strategy harness when gates permit; do not promote automatically.

## File inventory

- `docs/BTC_ARCHITECTURE.md`
- `docs/DATA_MODEL.md`
- `docs/BTC_DELIVERY_REPORT.md`
- `scripts/gen_data_model_doc.py`
- `docs/BTC_DATA_READINESS.md`
- `docs/BTC_FEATURES_V0.md`
- `docs/BTC_RESEARCH_PROTOCOL.md`
- `docs/adr/btc-v0-separate-pit-prediction-and-forward-validation-vertical.md`
- `frontend/artifacts/btc-analyzer.png`
- `frontend/artifacts/btc-simulation.png`
- `frontend/artifacts/btc-time-machine.png`
- `frontend/e2e/analyzer.spec.ts` (existing ambiguous text selector made exact; equity behavior unchanged)
- `frontend/e2e/btc.spec.ts`
- `frontend/playwright.config.ts`
- `frontend/src/App.tsx`
- `frontend/src/__tests__/bitcoin.test.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/features/bitcoin/BitcoinPage.tsx`
- `migrations/versions/btc_v0_20261004_btc_independent_pit_vertical.py`
- `migrations/versions/btc_v0_20261004_r1_revision_vintages.py`
- `scripts/btc_archive.py`
- `src/pitquant/api/app.py`
- `src/pitquant/api/btc.py`
- `src/pitquant/api/simulations.py`
- `src/pitquant/btc/__init__.py`
- `src/pitquant/btc/archive.py`
- `src/pitquant/btc/contracts.py`
- `src/pitquant/btc/features.py`
- `src/pitquant/btc/fixtures.py`
- `src/pitquant/btc/models.py`
- `src/pitquant/btc/providers.py`
- `src/pitquant/btc/research.py`
- `src/pitquant/btc/simulation.py`
- `src/pitquant/db/models.py`
- `src/pitquant/simulation/registry.py`
- `src/pitquant/simulation/service.py`
- `tests/e2e/serve.py`
- `tests/integration/test_postgres.py`
- `tests/unit/test_btc_v0.py`

## Local evidence archive and operations

Real evidence lives in data/btc.db and data/archive in this worktree, not Git. Heartbeat btc-archivo-forward-horario is ACTIVE hourly at minute10. Keep app/computer running and worktree on disk. The immutable initial holdout is2025-10-01–2026-09-30. Backfill fetched today is not PIT at historical dates.

CI repair: one run failed an existing Analyzer E2E because its regex matched two visible disclaimer elements. The assertion now selects the exact disclaimer; no equity product logic changed.
