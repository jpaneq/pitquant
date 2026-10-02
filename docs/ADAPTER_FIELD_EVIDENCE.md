# Evidencia documental de los adapters (generado)

Generado con `scripts/archive_adapter_docs.py`. Cada página oficial está en `raw_source_archive` (proveedor `VENDOR_DOCS`). Para cada campo que el adapter interpreta, se cita la frase oficial que lo justifica; si la página no la contiene, el campo es **UNVERIFIED** y el adapter lo marca así.

## Páginas archivadas

| Página | URL | retrieved_at | SHA-256 |
|---|---|---|---|
| SHARADAR:stocks | https://sharadar.com/docs/stocks | 2026-10-02T09:45:42.928777+00:00 | `f5644fd45360ccef7301c8e4a68c82cab4b051cb90a20e8b1fedecd149aeec49` |
| SHARADAR:actions | https://sharadar.com/docs/actions | 2026-10-02T09:45:44.145972+00:00 | `c9cabcee99002db3323984e291cfb4679a952c60a863f1ef84895340d34a2449` |
| SHARADAR:tickers | https://sharadar.com/docs/tickers | 2026-10-02T09:45:45.379581+00:00 | `65919963f2c69990affd7972687c60ec08a524a1b6e968230f4114bc72420bce` |
| SHARADAR:sp500 | https://sharadar.com/docs/sp500 | 2026-10-02T09:45:46.627757+00:00 | `a4d92010e0fa37d07b6c9b5393b4011a3e31587f877bcf82227aca5c7bac9299` |
| EODHD:eod | https://eodhd.com/financial-apis/api-for-historical-data-and-volumes | 2026-10-02T07:46:34.043816+00:00 | `c2810e21040f5c1bde3aa412ac3bd24ec8c6039dcebaf3506eba7a07db1b37fa` |
| EODHD:div_splits | https://eodhd.com/financial-apis/api-splits-dividends | 2026-10-02T07:46:19.740754+00:00 | `c60331c5aae18bc1c38292e59cab21b49e691041b9c5ed5fbf2d80dc2d9fb9ab` |
| ALPHAVANTAGE:daily | https://www.alphavantage.co/documentation/ | 2026-10-02T09:45:52.996946+00:00 | `65c9951083c9b64a8070b8f40c90b5e7146b599940c636069e69ff566dce93bb` |

## Campos

| Campo | Uso en el adapter | Estado | Frase oficial |
|---|---|---|---|
| SEP.open/high/low/close | SPLIT-adjusted; raw = closeunadj | VERIFIED | «Close Price - Split Adjusted» (SHARADAR:stocks) |
| SEP.closeunadj | RAW close (base series) | VERIFIED | «Close Price - Unadjusted» (SHARADAR:stocks) |
| SEP.closeadj | QA only (vendor adjusted) | VERIFIED | «Close Price - Adjusted for Splits Dividends and Spinoffs» (SHARADAR:stocks) |
| SEP.volume | split-adjusted; de-adjusted with closeunadj/close | VERIFIED | «Volume - Split Adjusted» (SHARADAR:stocks) |
| SEP.lastupdated | vendor_last_updated (QA) | VERIFIED | «Last Updated Date» (SHARADAR:stocks) |
| pagination limit | default 10000: a full page may be truncated | VERIFIED | «limit The number of records to return. 10000» (SHARADAR:stocks) |
| pagination offset | skip, alias offset | VERIFIED | «skip The number of results to skip before returning data. Alias: offset» (SHARADAR:stocks) |
| ACTIONS.dividend value basis (split-adjusted?) | kept as value_basis=UNVERIFIED | **UNVERIFIED** | no aparece en SHARADAR:actions |
| ACTIONS.date semantics (ex vs effective) | treated as the action date | **UNVERIFIED** | no aparece en SHARADAR:actions |
| ACTIONS.tickerchangefrom/to direction | pairing check only | **UNVERIFIED** | no aparece en SHARADAR:actions |
| ACTIONS.acquisition counterpart | contraticker = acquirer; no consideration type, so MERGER + delisting ACQUIRED | VERIFIED | «delisted as a result of an acquisition will specify the aquiring company in the contraticker» (SHARADAR:actions) |
| ACTIONS.spinoff value meaning | value kept as vendor ratio; valuation needed for total return | **UNVERIFIED** | no aparece en SHARADAR:actions |
| TICKERS.permaticker | permanent id of a share class | VERIFIED | «permaticker, a unique and unchanging identifier for a security (share class)» (SHARADAR:tickers) |
| TICKERS.ticker reuse | never an identity: resolved by date | **UNVERIFIED** | no aparece en SHARADAR:tickers |
| TICKERS.first/lastpricedate | life window for (ticker, date) | VERIFIED | «First Price Date» (SHARADAR:tickers) |
| SP500.date semantics | EFFECTIVE date of the change | VERIFIED | «effective date of the change» (SHARADAR:sp500) |
| SP500.historical rows | historical QUARTERLY snapshots (checked vs events) | VERIFIED | «historical quarterly snapshots of the index constituents» (SHARADAR:sp500) |
| SP500.contraticker | counterpart of an add/remove | VERIFIED | «Contra Ticker Symbol contraticker» (SHARADAR:sp500) |
| eod.open/high/low/close | RAW as traded | VERIFIED | «close number Closing price, as traded» (EODHD:eod) |
| eod.adjusted_close | QA only | VERIFIED | «adjusted_close number Closing price adjusted for both splits and dividends» (EODHD:eod) |
| eod.volume | adjusted for splits only; de-adjusted | VERIFIED | «volume integer Traded volume, adjusted for splits» (EODHD:eod) |
| renamed symbols | a ticker is not an identity | VERIFIED | «A renamed ticker does not — FB» (EODHD:eod) |
| div.date | ex-dividend date | VERIFIED | «Ex-dividend date — the day the share starts trading without the right to this payment» (EODHD:div_splits) |
| div.unadjustedValue | actual payout (used as amount) | VERIFIED | «unadjustedValue number The amount actually paid» (EODHD:div_splits) |
| div.value | split-adjusted (QA only) | VERIFIED | «Split-adjusted amount per share» (EODHD:div_splits) |
| div.declaration/record/payment dates | announcement/record/payment | VERIFIED | «declarationDate": "2026-04-30", "recordDate": "2026-05-11", "paymentDate": "2026-05-14", "period": "Quarterly", "value": 0» (EODHD:div_splits) |
| TIME_SERIES_DAILY OHLCV | RAW as-traded; adjusted endpoint never used | VERIFIED | «returns raw (as-traded) daily time series» (ALPHAVANTAGE:daily) |
| outputsize=compact | latest 100 data points (free-tier backfill is NOT possible) | VERIFIED | «compact returns only the latest 100 data points in the daily time series» (ALPHAVANTAGE:daily) |
| splits.split | 'new/old' ratio | VERIFIED | «"split": "2.000000/1.000000"» (EODHD:div_splits) |
