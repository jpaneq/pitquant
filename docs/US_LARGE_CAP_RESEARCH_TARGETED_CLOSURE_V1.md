# Targeted closure of expanded US research universe

Base `b8bb890494310879f98066b5b95304644f4d42ad`. Universo cerrado: 696 securities; no nuevas empresas, modelos ni outcomes.

## Capacidad y recuperación

186/186 URLs SEC recuperadas; 39 CIK. Compresión APFS verificada: 16.52 GiB ahorrados en 1420 originales. Reserva de 5 GiB intacta. Bytes, SHA, rutas, fallos originales y revisiones conservados.

Ganancia exclusiva de capacidad: 107 issuer-months fundamentales; 106 combinados. No equivale a los 418 casos asociados del informe previo.

## Semántica y mappings

XBRL_MAPPING_DEBT significa deuda técnica de mapping, nunca deuda financiera. sec-tags-4 y los artefactos ML previos permanecen intactos. sec-tags-5 añade únicamente NetIncomeLoss = ProfitLoss − NetIncomeLossAttributableToNoncontrollingInterest, con misma accession, moneda USD y período, ambos conocidos antes del T0. Una participación ausente nunca es cero; un NetIncomeLoss reportado no se sobreescribe. La procedencia conserva ambos fact_id originales. Dos conceptos forman una sola regla; sus ganancias no se suman dos veces.

Se revisan todos los conceptos con ≥100 issuer-months o ≥5 issuers. Las definiciones primarias SEC están archivadas por hash. Los componentes de bienes/servicios, sectores, geografías, pro forma, EPS y activos available-for-sale no equivalen automáticamente a totales. Los ingresos componentizados requieren el cálculo primario del total; no se aceptan por nombre parecido. [Guía FASB de OCI](https://xbrl.fasb.org/impdocs/OCI_TIG/othercompincome.htm) y [guía técnica US GAAP 2019](https://storage.fasb.org/2019_US_GAAP_Financial_Reporting_Taxonomy_Technical_Guide.pdf).

| Concepto | Familia | Issuers | Issuer-months asociados | Feature | Confianza | Mapping | Estado |
|---|---|---:|---:|---|---|---|---|
| ProfitLoss | CONSOLIDATED_INCOME | 91 | 3080 | fund_net_margin | HIGH | True | ACCEPTED_SAME_ACCESSION_COMPOSITE_ONLY |
| NetIncomeLossAttributableToNoncontrollingInterest | NONCONTROLLING_INCOME | 61 | 1951 | fund_net_margin | HIGH | True | ACCEPTED_SAME_ACCESSION_COMPOSITE_ONLY |
| NetIncomeLossAvailableToCommonStockholdersBasic | COMMON_STOCKHOLDER_EARNINGS_AFTER_PREFERRED_ADJUSTMENTS | 49 | 1871 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SalesRevenueGoodsNet | REVENUE_COMPONENT_OR_OTHER_FLOW | 44 | 1804 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| BusinessAcquisitionsProFormaRevenue | ACQUISITION_PRO_FORMA_OR_ACQUIREE_COMPONENT | 43 | 1504 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AdjustmentsNoncashItemsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivitiesOther | CASH_FLOW_RECONCILIATION_OR_ACCOUNTING_CHANGE | 36 | 1434 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| BusinessAcquisitionsProFormaNetIncomeLoss | ACQUISITION_PRO_FORMA_OR_ACQUIREE_COMPONENT | 32 | 1235 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| NetIncomeLossAvailableToCommonStockholdersDiluted | COMMON_STOCKHOLDER_EARNINGS_AFTER_PREFERRED_ADJUSTMENTS | 35 | 1225 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 39 | 1170 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| DisposalGroupIncludingDiscontinuedOperationRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 33 | 974 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableforsaleSecuritiesGrossUnrealizedGain | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 20 | 821 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProceedsFromSaleOfAvailableForSaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 23 | 711 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SalesRevenueServicesNet | REVENUE_COMPONENT_OR_OTHER_FLOW | 20 | 706 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| AvailableForSaleSecuritiesNoncurrent | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 16 | 676 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossUnrealizedLosses1 | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 17 | 655 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 24 | 621 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ContractWithCustomerLiabilityRevenueRecognized | REVENUE_COMPONENT_OR_OTHER_FLOW | 30 | 557 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProceedsFromSaleAndMaturityOfAvailableForSaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 12 | 548 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossUnrealizedLoss | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 16 | 546 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesAfterOneThroughFiveYearsFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 15 | 545 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| FairValueMeasurementWithUnobservableInputsReconciliationRecurringBasisAssetPurchasesSalesIssuancesSettlements | REVENUE_COMPONENT_OR_OTHER_FLOW | 13 | 545 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesFairValueDisclosure | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 20 | 536 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| PaymentsToAcquireAvailableForSaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 14 | 528 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesCurrent | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 17 | 521 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossUnrealizedGains | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 13 | 492 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 16 | 483 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EquityMethodInvestmentSummarizedFinancialInformationNetIncomeLoss | INCOME_COMPONENT_NOT_PARENT_NET_INCOME | 12 | 476 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RevenuesFromTransactionsWithOtherOperatingSegmentsOfSameEntity | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 15 | 453 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingInformationRevenue | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 12 | 452 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EntityWideDisclosureOnGeographicAreasRevenueFromExternalCustomersAttributedToEntitysCountryOfDomicile | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 11 | 446 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RevenueFromRelatedParties | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 12 | 446 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossRealizedGains | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 15 | 411 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EquityMethodInvestmentSummarizedFinancialInformationRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 12 | 407 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| NetIncomeLossAttributableToRedeemableNoncontrollingInterest | NONCONTROLLING_INCOME_COMPONENT | 9 | 391 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EntityWideDisclosureOnGeographicAreasRevenueFromExternalCustomersAttributedToForeignCountries | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 10 | 390 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesAfterFiveThroughTenYearsFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 11 | 367 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| GainLossOnSalesOfAssetsAndAssetImpairmentCharges | REVENUE_COMPONENT_OR_OTHER_FLOW | 13 | 348 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| OtherSalesRevenueNet | REVENUE_COMPONENT_OR_OTHER_FLOW | 14 | 348 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| AvailableForSaleSecuritiesGrossRealizedLosses | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 12 | 345 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| BusinessCombinationProFormaInformationRevenueOfAcquireeSinceAcquisitionDateActual | ACQUISITION_PRO_FORMA_OR_ACQUIREE_COMPONENT | 11 | 335 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RevenueRemainingPerformanceObligation | REVENUE_COMPONENT_OR_OTHER_FLOW | 22 | 334 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtSecuritiesCurrent | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 11 | 318 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossRealizedGainsLossesSaleProceeds | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 9 | 279 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesAfterTenYearsFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 7 | 276 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RelatedPartyTransactionRevenuesFromTransactionsWithRelatedParty | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 7 | 269 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingInformationRevenueFromExternalCustomers | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 9 | 264 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProceedsFromSaleOfAvailableForSaleSecuritiesDebt | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 15 | 262 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| PaymentsToAcquireAvailableForSaleSecuritiesDebt | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 11 | 258 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| OtherThanTemporaryImpairmentLossesInvestmentsAvailableforsaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 7 | 251 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EquityMethodInvestmentSummarizedFinancialInformationGrossProfitLoss | INCOME_COMPONENT_NOT_PARENT_NET_INCOME | 7 | 250 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossUnrealizedGainLoss | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 4 | 238 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ResultsOfOperationsOilAndGasProducingActivitiesNetIncomeExcludingCorporateOverheadAndInterestCosts | INCOME_COMPONENT_NOT_PARENT_NET_INCOME | 8 | 236 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| NetIncomeLossIncludingPortionAttributableToNonredeemableNoncontrollingInterest | NONCONTROLLING_INCOME_COMPONENT | 10 | 232 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| FairValueMeasurementWithUnobservableInputsReconciliationRecurringBasisAssetSales | REVENUE_COMPONENT_OR_OTHER_FLOW | 8 | 230 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingSegmentOperatingProfitLoss | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 5 | 229 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtSecuritiesNoncurrent | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 9 | 227 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| PaymentsToAcquireAvailableForSaleSecuritiesEquity | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 4 | 227 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesGrossRealizedGainLossNet | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 7 | 219 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| NewAccountingPronouncementOrChangeInAccountingPrincipleEffectOfChangeOnNetIncome | CASH_FLOW_RECONCILIATION_OR_ACCOUNTING_CHANGE | 4 | 213 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesEquitySecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 11 | 212 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingInformationProfitLoss | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 5 | 205 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesNextRollingTwelveMonthsFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 4 | 202 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AdjustmentsNoncashItemsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities | CASH_FLOW_RECONCILIATION_OR_ACCOUNTING_CHANGE | 4 | 199 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 8 | 195 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RevenueRecognitionGiftCardsBreakage | REVENUE_COMPONENT_OR_OTHER_FLOW | 5 | 194 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPositionLessThanTwelveMonthsFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 10 | 193 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesWithoutSingleMaturityDateFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 3 | 192 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities | CASH_FLOW_RECONCILIATION_OR_ACCOUNTING_CHANGE | 6 | 190 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ResultsOfOperationsRevenueFromOilAndGasProducingActivities | REVENUE_COMPONENT_OR_OTHER_FLOW | 7 | 190 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| BusinessAcquisitionProFormaRevenue | ACQUISITION_PRO_FORMA_OR_ACQUIREE_COMPONENT | 6 | 187 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| DecreaseDueToSalesOfMineralsInPlace | REVENUE_COMPONENT_OR_OTHER_FLOW | 7 | 187 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| BusinessAcquisitionProFormaNetIncomeLoss | ACQUISITION_PRO_FORMA_OR_ACQUIREE_COMPONENT | 6 | 184 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| GainsLossesOnSalesOfAssets | REVENUE_COMPONENT_OR_OTHER_FLOW | 5 | 184 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPositionTwelveMonthsOrLongerFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 10 | 181 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingInformationIntersegmentRevenue | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 4 | 175 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EquityMethodInvestmentSummarizedFinancialInformationNetSalesOrGrossRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 6 | 167 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 3 | 164 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| LossesGainsOnSalesOfAssetsAndAssetImpairmentCharges | REVENUE_COMPONENT_OR_OTHER_FLOW | 3 | 162 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ElectricUtilityRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 7 | 156 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| SegmentReportingReconcilingItemForOperatingProfitLossFromSegmentToConsolidatedAmount | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 3 | 155 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesEquitySecuritiesNoncurrent | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 3 | 153 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingSegmentRevenue | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 3 | 151 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| OilAndGasRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 6 | 150 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| InterestRevenueExpenseNet | REVENUE_COMPONENT_OR_OTHER_FLOW | 6 | 149 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| OtherThanTemporaryImpairmentLossesInvestmentsPortionRecognizedInEarningsNetAvailableforsaleSecurities | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 5 | 148 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProceedsFromSalesOfBusinessAffiliateAndProductiveAssets | REVENUE_COMPONENT_OR_OTHER_FLOW | 7 | 147 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SalesReturnsGoods | REVENUE_COMPONENT_OR_OTHER_FLOW | 2 | 146 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPositionFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 9 | 145 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| HealthCareOrganizationPatientServiceRevenueLessProvisionForBadDebts | REVENUE_COMPONENT_OR_OTHER_FLOW | 3 | 145 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| HealthCareOrganizationPatientServiceRevenueProvisionforBadDebts | REVENUE_COMPONENT_OR_OTHER_FLOW | 3 | 145 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesRollingYearTwoThroughFiveFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 3 | 142 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProceedsFromSaleOfAvailableForSaleSecuritiesEquity | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 5 | 140 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AntidilutiveSecuritiesExcludedFromComputationOfNetIncomePerOutstandingUnitAmount | INCOME_COMPONENT_NOT_PARENT_NET_INCOME | 2 | 139 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableforsaleSecuritiesGrossRealizedGainLossExcludingOtherThanTemporaryImpairments | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 4 | 137 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EntityWideRevenueMajorCustomerAmount | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 3 | 135 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesDebtMaturitiesRollingYearSixThroughTenFairValue | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 3 | 134 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| NetIncomeLossAttributableToNonredeemableNoncontrollingInterest | NONCONTROLLING_INCOME_COMPONENT | 4 | 132 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| NewAccountingPronouncementOrChangeInAccountingPrincipleEffectOfChangeOnNetRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 2 | 132 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| LeveragedLeasesIncomeStatementNetIncomeFromLeveragedLeases | INCOME_COMPONENT_NOT_PARENT_NET_INCOME | 2 | 130 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPositionLessThan12MonthsAccumulatedLoss | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 7 | 127 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SegmentReportingReconcilingItemsForOperatingProfitLoss | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 2 | 127 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| SalesRevenueServicesGross | REVENUE_COMPONENT_OR_OTHER_FLOW | 3 | 126 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| HealthCareOrganizationPatientServiceRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 2 | 125 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| ResultsOfOperationsSalesRevenueToUnaffiliatedEnterprises | REVENUE_COMPONENT_OR_OTHER_FLOW | 3 | 119 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| EntityWideRevenueMajorCustomerPercentage | SEGMENT_GEOGRAPHIC_OR_CUSTOMER_COMPONENT | 2 | 115 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| GasDomesticRegulatedRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 3 | 114 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPositionLessThan12MonthsAggregateLosses | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 5 | 108 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RevenueRemainingPerformanceObligationPercentage | REVENUE_COMPONENT_OR_OTHER_FLOW | 5 | 104 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ProvedDevelopedAndUndevelopedReservesSalesOfMineralsInPlace | REVENUE_COMPONENT_OR_OTHER_FLOW | 4 | 103 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| ContractsRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 2 | 102 | fund_net_margin;fund_revenue_yoy | CONDITIONAL | False | DEFERRED_NEEDS_PRIMARY_TOTAL_CALCULATION_CONTEXT |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPosition12MonthsOrLongerAccumulatedLoss | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 6 | 77 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| RoyaltyRevenue | REVENUE_COMPONENT_OR_OTHER_FLOW | 5 | 55 | — | HIGH | False | REJECTED_DIRECT_MAPPING |
| AvailableForSaleSecuritiesContinuousUnrealizedLossPositionAccumulatedLoss | INVESTMENT_ASSET_OR_INVESTMENT_CASH_FLOW | 5 | 35 | — | HIGH | False | REJECTED_DIRECT_MAPPING |

Regla conjunta sec-tags-5: +371 fundamentales y +347 combinados recuperados. También excluye 72 combinados previos: una ventana de income más reciente no tiene todos los FY/YTD comparables para TTM. No se recupera el valor anterior por conveniencia. Ganancia combinada neta del mapping: 275; neta de todas las reparaciones: 466. El JSON conserva pérdidas y motivos individuales.

## Identidad y mercado

Presupuesto: 20 principales casos de identidad y 20 de mercado, más reparaciones con evidencia primaria ya archivada. Prioridad por recuperación combinada conocida; cuando la identidad no permite cuantificar issuer-months, se muestra el potencial de security-periods de membresía, sin fingir equivalencia. Las fichas JSON conservan clasificadores, nombres, símbolos, documentos y límites.

El 10-K SEC 0001336917-17-000017 confirma Class A UA hasta 2016-12-06/UAA desde 2016-12-07 y Class C UA.C desde 2016-04-08/UA desde 2016-12-07. Se repara el vínculo de ambas clases y se obtiene UAA: símbolo del proveedor distinto del ticker histórico fechado. Nunca se empalman clases ni sucesoras. UA conserva su fallo de OHLC original; su identidad válida no habilita precios inválidos. La distribución de Class C del 2016-04-08 no se interpreta como split de Class A: las ventanas de features y labels que la atraviesan quedan fuera del candidato científico.

Ganancia de alias/mercado: +85 issuer-months combinados. La reparación de identidad aislada no se presenta como ganancia independiente si sus precios siguen bloqueados.

## Candidato científico

Se construyen con los motores existentes todas las familias PRICE, FUNDAMENTAL y RISK. Los cores deben tener valores finitos; los campos opcionales conservan NULL y motivo, tal como exige el contrato congelado de imputación sólo en TRAIN. No se ajusta imputación, escalado, selección ni modelo. El panel técnico usa los rolling causales nativos con pruebas de truncación; valoración utiliza precio RAW y acciones conocidas en T0. Los checks PIT validan cada field construido.

Label constructibility verifica exclusivamente timestamps, presencia de observaciones, sesiones esperadas, divisa USD y límites legales de la misma security durante 12 meses. Nunca se calcula ni publica un retorno futuro. Los precios numéricos futuros no se normalizan ni entran en features. El benchmark usa SELECT de fechas/cierres temporales, sin precios futuros. Las ventanas posteriores a 2022-09-30 y las que cruzan una sucesión quedan excluidas. Se reutilizan exactamente F1/F2/F3 y su separación congelada; no se rediseñan folds.

## Antes y después

| Etapa | Antes min/med/max | Después min/med/max |
|---|---|---|
| MEMBERSHIP | 283/341.0/370 | 284/341.0/370 |
| PRICE | 258/310.0/352 | 259/311.0/353 |
| FUNDAMENTALS | 154/200.0/252 | 158/205.0/260 |
| COMBINED | 143/181.0/239 | 147/187.0/252 |
| SCIENTIFIC | 143/181.0/239 | 147/187.0/252 |

| Fold | Fase | min | P10 | Mediana | P90 | max |
|---|---|---:|---:|---:|---:|---:|
| F1 | TRAIN | 147 | 153.6 | 168.0 | 178.0 | 180 |
| F1 | TEST | 189 | 190.1 | 211.5 | 220.7 | 222 |
| F2 | TRAIN | 147 | 154.8 | 174.0 | 188.4 | 191 |
| F2 | TEST | 220 | 228.3 | 240.0 | 244.0 | 246 |
| F3 | TRAIN | 147 | 155.0 | 177.0 | 209.0 | 222 |
| F3 | TEST | 244 | 244.0 | 249.0 | 251.0 | 252 |

## Representación y límites

Sectores/mes: `{'minimum': 6, 'p10': 6.0, 'median': 7.0, 'p90': 8.0, 'maximum': 8}`. Mayor sector: `{'minimum': 0.47305389221556887, 'p10': 0.4813776393215645, 'median': 0.5, 'p90': 0.5112160642570281, 'maximum': 0.5374149659863946}`. Top-3: `{'minimum': 0.7810650887573964, 'p10': 0.7901234567901234, 'median': 0.8211382113821138, 'p90': 0.8319389485585076, 'maximum': 0.8377192982456141}`. SIC actual es CURRENT_PROFILE_NOT_PIT, descriptivo, nunca predictor. Las divisiones 60/61/62/63/64/65/67 siguen excluidas de los ratios industriales.

Supervivencia: `{"CURRENT_REFERENCE_MEMBER": 331, "CURRENT_STATUS_UNRESOLVED": 161, "EXPLICIT_ACQUIRED_OR_SUCCESSOR": 0, "EXPLICIT_BANKRUPT": 0, "EXPLICIT_DELISTED": 0, "PRIMARY_MERGER_PREDECESSOR": 5, "PRIMARY_REPLACEMENT_PREDECESSOR": 14, "REMOVED_FROM_CURRENT_REFERENCE": 190, "REMOVED_OR_REPLACED_HISTORICAL_SECURITY": 14}`. Explicit lifecycle counts are lower bounds. Removal, a replacement, or a Yahoo 404 does not by itself prove delisting/acquisition/bankruptcy. Unknown cases remain unknown.

Exclusion counts overlap. Units without resolved issuers are security-periods, explicitly prefixed UNRESOLVED; known units are issuer-months. Yahoo and historical identity loss are concentrated among removed issuers; inference is restricted to the documented research-eligible cohort, not all S&P constituents.

Las exclusiones por motivo, sector, año y lifecycle se publican sin outcomes. Estados de lifecycle desconocidos no invalidan una identidad/membresía válida; no se infiere quiebra o adquisición de un 404. Se conserva el sesgo de disponibilidad de empresas retiradas y no se anuncia representatividad completa del índice.

Curva acumulada de recuperación combinada, top1/5/10/20/todas: `{'1': 347, '5': 499, '10': 537, '20': 538, 'all': 538}`; cuenta uniones de issuer-months, no asociaciones solapadas. Cola residual: `{'mapping_below_budget': 134, 'unresolved_securities': 226, 'identity_cases_outside_review_budget': 212, 'yahoo_cases_outside_review_budget': 298}`.

## Contrato propuesto y cierre

{
  "name": "EXPANDED_US_RESEARCH_COVERAGE_V1",
  "status": "PROPOSED_NOT_A_STATISTICAL_GATE",
  "minimum_issuers_per_month": 100,
  "minimum_valid_membership_coverage_fraction": 0.5,
  "minimum_represented_sectors": 5,
  "maximum_largest_sector_share": 0.6,
  "maximum_top3_sector_share": 0.9,
  "apply_to": "Every frozen TRAIN and TEST month; neither monthly minimum nor folds may be weakened.",
  "denominator": "Unique research-valid membership issuers (including unsupported financial families); unresolved security-periods reported separately.",
  "justification": "100 is the pre-existing structural cross-section benchmark, independent of the observed minimum. At least half the verified membership prevents claiming breadth from a narrow slice. Five broad SIC groups, a 60% single-group cap and 90% top-three cap prevent near-single-sector cohorts. These are proposed engineering representation requirements, not proof of statistical power.",
  "nullable_feature_policy": "All frozen family fields must be built with a value or explicit missing reason, mandatory price/fundamental cores non-null; optional missing values preserve the frozen train-only imputation contract. No preprocessing fitted here.",
  "monthly_structural_pass_count": 85
}

El milestone ≥150 es exclusivamente descriptivo. El contrato propuesto no deriva del mínimo observado y no habilita entrenamiento automáticamente. El conteo de representación no estima tamaño efectivo independiente ni potencia estadística.

STOP: bloqueo de almacenamiento eliminado, mappings de alto impacto revisados, principales identidades/Yahoo reparadas o clasificadas, cobertura científica medida y long tail cuantificada. No se persigue completitud perfecta.

Recomendación única: **FREEZE_EXPANDED_DATASET_AND_DESIGN_FINAL_RANKING_EXPERIMENT**.

Candidato `US_LARGE_CAP_RESEARCH_TARGETED_DATASET_V1.json.gz` SHA `c4f09058f52f865104cc23ca72e1674dae558e6ce79cc1e337f8c75b3f825a99`. El JSON conserva todas las filas de disponibilidad/ciencia, fuentes extra y referencia al candidato previo inmutable. Las revisiones intermedias quedan fijadas por SHA y en el archivo local; reejecución con las mismas fuentes y DB copiada, sin red. No escribir en la DB de producción.

dev_adaptive_iteration=2; new_fits=0; holdout outcomes=0; OOT outcomes=0.
