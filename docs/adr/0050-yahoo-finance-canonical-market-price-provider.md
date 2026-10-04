# ADR-0050 — Yahoo Finance as canonical market price provider

Accepted 2026-10-05. Supersedes the exploratory-source restriction of ADR-0043/0049. Contract: `yahoo-market-data-v1`. BTC is outside this change.

Yahoo Finance is `CANONICAL_PROVIDER_FOR_PITQUANT`, provider `YAHOO_FINANCE`, role `CANONICAL_MARKET_PRICE_SOURCE`. This covers equities, ETFs, indices, benchmarks, FX and available splits/dividends. Its evidence tier remains VENDOR: it is not an official exchange source. Canonical choice and per-series quality are independent.

The chart endpoint is keyless and supports the existing daily pipeline. Its limitations include missing bars, revisions, incomplete actions, inaccurate OHLC, changing endpoints and incomplete pre-listing history. No silent fallback to another price provider is permitted in ML. EODHD and other known vendors are preserved as `LEGACY_EXCLUDED`; synthetic is `SYNTHETIC_EXCLUDED`; unknown is `UNKNOWN_SOURCE_BLOCKED`.

Yahoo quote OHLC are split-adjusted. The parser reconstructs nominal historical OHLC using the archived subsequent splits, retaining the payload and its hash. Vendor adjusted close is separately stored in ProviderAdjustedPrice, never substituted for raw close. Pre-split volume is unavailable when its adjustment is unverifiable; raw volume is not fabricated. Dividend amounts are restored to their historical share units. Technical series and total-return levels are rebuilt by the existing corporate-action engine as-of each decision; securities and benchmarks use the same total-return convention.

[Yahoo defines adjusted close as accounting for splits and distributions](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html). This does not establish that its vendor-adjusted series is identical to the project's explicit reinvestment convention: it remains a QA reference.

Market/session timestamp, semantic availability at session close, actual retrieval and archived vintage are distinct. Historical downloads made today do not establish historical provider publication or revision availability. The frozen project close convention is unchanged; future/incomplete sessions are excluded. FX retains availability from 00:00 UTC on the following day and its existing maximum-age guard.

Research uses only Yahoo bars and Yahoo simple corporate actions through an explicit optional source filter; the live V0 path keeps its existing behavior. New append-only versions are `research-features-v1-yahoo-v1` and `research-targets-v2-yahoo-v2`. Prior snapshots and providers remain stored. A source-vintage hash, code commit and provider contract identify the new generation; no original snapshots are rewritten.

D05 checks identity/currency metadata, duplicate/order guards, OHLC, session chronology, missing sessions, beginning of coverage, corporate-action coverage and archived deterministic reconstruction. Naming the provider Yahoo never closes these checks. Active session coverage remains 98%; delisted 95%; unknown leading history remains blocked. Missing or unreproducible data stay blocked with explicit reasons.

SPY and URTH remain ETF proxies. ^IBEX remains PRICE_RETURN_ONLY and cannot produce eligible excess total returns. Spain's existing URTH+PIT-FX proxy fallback is explicit. First ML remains US canonical-membership-only; no benchmark is selected using outcomes.

La versión yahoo-v1 de objetivos se conserva archivada; yahoo-v2 corrige la etiqueta histórica de FX a CANONICAL_SOURCE sin actualizar resultados ni filas previas.
