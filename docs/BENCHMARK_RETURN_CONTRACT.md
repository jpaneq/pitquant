# Contrato de retorno de benchmark (ADR-0049, generado)

Versión `benchmark-contract-1`. `future_excess_total_return = retorno total del valor − retorno del benchmark`, sólo si ambos están en la MISMA base de retorno y de divisa.

## Reglas

* Valor con retorno total frente a benchmark de precio (`PRICE_RETURN`) ⇒ `PRICE_RETURN_ONLY` / `NOT_COMPARABLE_RETURN_BASIS`: el exceso NO se calcula (NULL) y la fila queda fuera del ML.
* Divisa distinta: el valor se convierte a USD en cada instante con FX PIT (`fx_rates`, Yahoo, VENDOR/CANONICAL, disponible a las 00:00 UTC del día siguiente a la cotización; máx. 7 días de antigüedad). Sin FX ⇒ `FX_MISMATCH` / `FX_DATA_NOT_READY`. Nunca el tipo actual para el histórico.
* ETF ⇒ siempre `ETF_PROXY`, nunca el índice oficial. `READY` se reserva a una serie oficial de retorno total; `PROXY_ACCEPTABLE` (ETF con dividendos y base comparable) es el estado aprobado por metodología para el primer ML. `APPROVED_FOR_ML = {READY, PROXY_ACCEPTABLE}`.
* Benchmarks: XNYS→SPY; XMAD→IBEX 35 Total Return (ES0SI0000047) **MISSING**, `^IBEX` es sólo precio (`PRICE_RETURN_ONLY`), fallback URTH+FX diagnóstico; resto→URTH+FX (URTH empieza en 2012-01).
* Campos guardados por fila (`research_targets.details.benchmark_contract`): benchmark_id, benchmark_security_id, benchmark_name, benchmark_type, benchmark_return_type, benchmark_currency, security_currency, return_currency_basis, currency_conversion_method, fx_source, fx_available_at, fx_rate_date, benchmark_start_price, benchmark_end_price, benchmark_total_return, benchmark_source, benchmark_version, benchmark_provenance, benchmark_quality_status, comparability, skipped_candidates.

## Estado por mercado (horizonte 12M, filas con objetivo calculable o no)

| market | region | security_ccy | benchmark | bench_ccy | return_type | currency_basis | quality | comparables/filas | bloqueo |
|---|---|---|---|---|---|---|---|---|---|
| XAMS | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 117/153 | — |
| XASX | ASIA | AUD | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 351/459 | — |
| XCSE | EU | DKK | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 117/153 | — |
| XETR | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 351/459 | — |
| XLON | EU | GBP | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 702/918 | — |
| XMAD | ES | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 1521/1989 | — |
| XMIL | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 234/306 | — |
| XNYS | US | USD | SPY_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 7055/8375 | — |
| XPAR | EU | EUR | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 585/765 | — |
| XSWX | EU | CHF | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 234/306 | — |
| XTKS | ASIA | JPY | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 585/765 | — |
| XTSE | NA | CAD | URTH_ETF_PROXY_V1 | USD | TOTAL_RETURN | USD | PROXY_ACCEPTABLE | 428/560 | — |

## Resumen

| comparabilidad (filas OK) | n |
|---|---|
| BENCHMARK_UNAVAILABLE_IN_WINDOW | 528 |
| COMPARABLE | 12280 |

| método de conversión (filas OK) | n |
|---|---|
| NONE_SAME_CURRENCY | 7055 |
| SECURITY_TOTAL_RETURN_CONVERTED_TO_USD_AT_PIT_FX | 5753 |
