# Evidencia documental de los adapters (generado)

Generado con `scripts/archive_adapter_docs.py`. Cada página oficial está en `raw_source_archive` (proveedor `VENDOR_DOCS`). Para cada campo que el adapter interpreta, se cita la frase oficial que lo justifica; si la página no la contiene, el campo es **UNVERIFIED** y el adapter lo marca así.

## Páginas archivadas

| Página | URL | retrieved_at | SHA-256 |
|---|---|---|---|
| SHARADAR:stocks | https://sharadar.com/docs/stocks | 2026-10-02T07:46:28.012625+00:00 | `4bd36b85f735e13555b3b374de1b73483be8fb16c9a16acc37b3d8359f118c13` |
| SHARADAR:actions | https://sharadar.com/docs/actions | 2026-10-02T07:46:29.207993+00:00 | `9bd2b1c14f2f033158c09f55c1d101489a94d9cb2d9242d45e56d0d758879bc6` |
| SHARADAR:tickers | https://sharadar.com/docs/tickers | 2026-10-02T07:46:30.408453+00:00 | `b22a881c42e6ea0f05e6c4b2325e6fb99149c87c83637ce71099516af8fdd853` |
| SHARADAR:sp500 | https://sharadar.com/docs/sp500 | 2026-10-02T07:46:31.650508+00:00 | `e74d02a077b8c511a82e5240fb5559ef1dc8d90fca51e663b7897525bdbee8af` |
| EODHD:eod | https://eodhd.com/financial-apis/api-for-historical-data-and-volumes | 2026-10-02T07:46:34.043816+00:00 | `c2810e21040f5c1bde3aa412ac3bd24ec8c6039dcebaf3506eba7a07db1b37fa` |
| EODHD:div_splits | https://eodhd.com/financial-apis/api-splits-dividends | 2026-10-02T07:45:42.799195+00:00 | `617712a346b7c0d734540ae2aa53751e091d7aaf0e87d62de6b7705fe14b1571` |

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
| splits.split | 'new/old' ratio | VERIFIED | «"split": "2.000000/1.000000"» (EODHD:div_splits) |
