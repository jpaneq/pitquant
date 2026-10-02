# Fundamental Engine V1 (`fundamental-v1.0`, tags `sec-tags-2`)

**Implementado:** `src/pitquant/analyzer/fundamental_v1.py` sobre `features/v0/fundamentals.py` (periodización/TTM/resolución de tags). **No** hay nueva ingestión SEC ni otro almacén de hechos.

## Reglas
- Sólo hechos con `available_at < decision_at`; de cada periodo manda la **última revisión conocida** (restatements sólo tras presentarse).
- **TTM** = FY(previo) + YTD(actual) − YTD(mismo periodo del año anterior), o el FY en cierre de ejercicio. Los YTD no se suman como trimestres. Trimestres discretos (`discrete_quarters`): 3M directo, o Q2 = H1 − Q1, Q3 = 9M − H1, Q4 = FY − 9M.
- **Mapa de tags versionado** (no «el primer tag que exista»): ingresos (`RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet`), `GrossProfit`, `OperatingIncomeLoss`, `NetIncomeLoss`, `NetCashProvidedByUsedInOperatingActivities`, `PaymentsToAcquirePropertyPlantAndEquipment`, `Assets`, `Liabilities`, `StockholdersEquity`, `CashAndCashEquivalentsAtCarryingValue`, `AssetsCurrent`, `LiabilitiesCurrent`, `InterestExpense`, `PaymentsOfDividends*`, `PaymentsForRepurchaseOfCommonStock`, `ProceedsFromIssuanceOfCommonStock`, acciones `EntityCommonStockSharesOutstanding`. Gana el candidato con el periodo más reciente; dos tags con valores distintos para el mismo periodo → `unresolved_tag` (fail closed).
- **Capex**: el tag es un *pago* (positivo = salida). Un TTM negativo es `sign_unexpected` y se retiene el FCF; nunca `abs()` ciego. FCF = CFO − capex.
- Faltante = `value: null` + `reason` (`missing_fundamental`, `insufficient_history`, `denominator_invalid`, `NOT_MEANINGFUL`, `unresolved_tag`, `sign_unexpected`, `stale_data`). Nada se imputa.

## Métricas
TTM (revenue, gross profit, operating income, net income, CFO, capex, FCF) · rentabilidad (`gross_profitability`, márgenes, ROA, ROE con activos/equity medios = (inicio+fin)/2; ROE nulo si equity ≤ 0) · calidad (`cfo_to_net_income` sólo si |NI| > 1 M$; `accruals_to_assets`) · crecimiento (YoY y CAGR 3/5 años; **`NOT_MEANINGFUL`** si el valor inicial o final es ≤ 0 o cambia de signo) · inversión (`asset_growth1/3`, `capex_to_assets`, `capex_growth_yoy`) · balance (caja, deuda total sin doble contar, deuda neta, deuda/activos, deuda/equity, caja/activos, ratio corriente, cobertura de intereses) · capital allocation (`shares_growth1/3` **alineado a splits**, `dividend_yield` desde corporate actions, `dividends_to_fcf`, `buyback_yield`, `net_equity_issuance`, `shareholder_yield`; las acciones son de portada, nunca promedio ponderado).
`coverage {available, expected}` acompaña a cada respuesta.

## Perfiles especiales
`profile_type` (SIC): `STANDARD_CORPORATE` completo; `BANK`/`INSURER`/`REIT`/`OTHER_SPECIAL` → «SPECIALIZED FUNDAMENTAL PROFILE NOT YET SUPPORTED»: no se aplican FCF/ROA industriales; precio, técnicos y riesgo sí funcionan. Sector = división SIC, industria = descripción SIC (la SEC no publica GICS).

## Historia para gráficos
`history_series`: trimestral (discretos) o anual de revenue, operating income, net income, FCF, márgenes, acciones, caja y deuda, con YoY cuando el valor previo es positivo.

## Límites
Sin comparación con pares (no hay universo actual con fundamentales) ni EBITDA. Conceptos XBRL sin normalizar quedan `missing_fundamental`.
