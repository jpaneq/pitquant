# ADR-0063 — Independent forward direction pilots V1

Date: 2026-11-03. Status: experimental, no automatic orders or promotion.

Two fixed logistic regressions (L2, C=1, max_iter=2000, seed=20261103,
lbfgs; median imputation and standardization fitted only on training data),
separate equity 20 XNYS sessions / BTC 30 calendar days. At most two numerical
threads. No tuning from the 290 legacy rule decisions, no restart of invalidated
ranking experiments. Source HEAD: 9a68d9c; branch codex/forward-pilots-v1.

Features and formulas are frozen in `forward.engine` and each append-only
PROTOCOL before fit. Inputs require 201 consecutive closes; missing prices are
not filled. Optional volume alone may be median-imputed. Model, protocol and
compact training arrays are published without overwrite; model coefficients,
preprocessing statistics, row metadata and hashes are archived (no pickle).
Ten stocks fixed by existing price availability: AAPL, MSFT, KO, JNJ, JPM, XOM,
PG, AMZN, GOOGL, NVDA. This is a small current-constituent convenience sample,
not a survivorship-free US universe and not the S&P 500.

Historical labels end strictly before equity 2022-10-01 / BTC 2025-10-01.
Current archived vintages are not certified historical PIT data; retrospective
results are labelled accordingly. Cutoff filtering precedes target construction;
training rows whose target crosses a boundary are excluded. Historical replay
is monthly chronological refitting with fixed parameters and mature past
labels, not random splitting or evaluating a full-history fit on its own past.
Reserved historical outcomes remain unread. Current context used for a newly
issued real-time forecast is a separate cohort; it does not unseal old outcomes.

Each new forecast freezes actual generation time, source vintage/hash, features,
reference close, model ID/hash, probability and target date. It is a direction
forecast, not an expected return or target price. Stale/missing current closes
block new forecasts. Reviews append at equity sessions 1/5/10/20 and BTC days
1/7/14/30; direction success is assessed only at maturity. TR ratios use the
same refreshed series for both endpoints to avoid rebasing errors. No forecast
is reconstructed retrospectively as forward evidence.

Manual simulations reuse Simulation Lab/BTC conservative daily-bar engines and
freeze forecast linkage and original plan. The plan may enter later than the
forecast reference close; execution success and horizon direction success are
separate. Costs are explicitly NOT_MODELED in this pilot. No net profitability
claim or portfolio return sums overlapping fully-funded decisions. Per-trade
aggregate statistics require at least ten closed simulations; missing benchmark
observations stay missing. Legacy fills remain reference-price simulations.

V1 is never replaced. An explicit monthly --candidate may refit identical
parameters using permitted history plus mature own forward outcomes. No mature
new labels means no fit. Candidates and V1 issue same-date future forecasts;
no automatic selection/promotion. Feature/algorithm/rule changes need a separately
registered version. Daily review is prepared as a manual terminal command; no
previous BTC automation has been reactivated.

Migration 0028 creates an append-only journal with PostgreSQL and SQLite raw-SQL
triggers, plus ORM immutability. Prior datasets/models/champion are unchanged.

## Corrección técnica de las reglas anteriores

20/86 compras se emitieron con precio etiquetado STALE. Las nuevas decisiones
exigen LIVE/EOD para abrir; STALE/UNAVAILABLE/desconocido conservan análisis y
contrafactual pero no orden. Política FRESH_QUOTE_REQUIRED_V2. No se reescriben
las decisiones antiguas ni se reajustan los parámetros de señal, ATR o volatilidad.

Timestamp note: the first cycle's payload generated_at is its input cutoff
(2026-11-03T12:00:15Z); persisted created_at records actual issuance seconds
later, after fitting. The UI uses issued_at=created_at. Original payloads are
unchanged. Subsequent cycles sample the actual clock per forecast. Neither
time is used to reconstruct past forward forecasts.
