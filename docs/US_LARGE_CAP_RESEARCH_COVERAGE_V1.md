# US Large Cap Research Coverage V1

Auditoría de disponibilidad, identidad y missingness. No es un nuevo coverage contract científico ni un resultado de modelo.

## Comparación

| Medida | Current First ML | Universo ampliado |
|---|---:|---:|
| Configured issuers verificados | 55 | 469 |
| Emisores elegibles en algún mes | 45 | 274 |
| Mediana mensual | 38.0 | 181.0 |
| Mínimo mensual | 33 | 143 |
| Issuer-months | 3280 | 16275 |
| Sectores representados | 4 | 8 |

Frozen PRIMARY_COMMON_COHORT includes the previous label-safe contract; expanded candidate measures data availability only, without labels or training gates.

Incremento de mediana: 376.32%. Es una comparación de tamaño, con contratos distintos: no demuestra que esas observaciones sean entrenables.

## Distribuciones de emisores mensuales

| Etapa | Mínimo | P10 | Mediana | P90 | Máximo |
|---|---:|---:|---:|---:|---:|
| MEMBERSHIP | 283 | 294.0 | 341.0 | 368.0 | 370 |
| PRICE | 258 | 270.0 | 310.0 | 344.0 | 352 |
| FUNDAMENTALS | 154 | 170.0 | 200.0 | 248.0 | 252 |
| COMBINED | 143 | 157.0 | 181.0 | 237.0 | 239 |

MEMBERSHIP cuenta emisores identificados con período aceptado. membership_verified en la tabla siguiente cuenta securities corroboradas aunque falte resolver su emisor. PRICE/FUNDAMENTALS incluyen identidad y membresía; COMBINED es su intersección. Clases de un emisor se deduplican; los pendientes de identidad nunca son emisores ficticios.

Milestone de ingeniería ≥200 en cada mes: False. Scientific coverage gate: NOT_DEFINED.

## Los 85 meses

| Mes | Candidatos | Membresía verificada | Precio | Fundamentales | Combinado issuers | Securities | Excl. membership | Identidad | Precio | Fund. | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2014-09 | 507 | 306 | 258 | 154 | 143 | 143 | 201 | 193 | 239 | 334 | 66 |
| 2014-10 | 507 | 308 | 260 | 156 | 145 | 145 | 199 | 192 | 237 | 332 | 66 |
| 2014-11 | 507 | 308 | 260 | 158 | 147 | 147 | 199 | 192 | 237 | 330 | 66 |
| 2014-12 | 507 | 307 | 260 | 160 | 149 | 149 | 200 | 193 | 237 | 328 | 66 |
| 2015-01 | 507 | 308 | 261 | 161 | 150 | 150 | 199 | 192 | 236 | 327 | 66 |
| 2015-02 | 507 | 310 | 262 | 162 | 151 | 151 | 197 | 191 | 235 | 327 | 66 |
| 2015-03 | 507 | 310 | 262 | 164 | 151 | 151 | 197 | 191 | 235 | 325 | 66 |
| 2015-04 | 514 | 314 | 269 | 169 | 156 | 156 | 200 | 194 | 238 | 328 | 68 |
| 2015-05 | 514 | 315 | 270 | 170 | 157 | 157 | 199 | 193 | 237 | 327 | 69 |
| 2015-06 | 514 | 315 | 270 | 170 | 157 | 157 | 199 | 193 | 237 | 327 | 69 |
| 2015-07 | 514 | 316 | 270 | 171 | 157 | 157 | 198 | 194 | 237 | 326 | 69 |
| 2015-08 | 514 | 317 | 272 | 173 | 160 | 160 | 197 | 192 | 235 | 324 | 69 |
| 2015-09 | 514 | 318 | 272 | 175 | 161 | 161 | 196 | 192 | 235 | 322 | 69 |
| 2015-10 | 509 | 325 | 273 | 177 | 162 | 162 | 184 | 185 | 227 | 315 | 70 |
| 2015-11 | 510 | 327 | 274 | 177 | 162 | 162 | 183 | 185 | 227 | 317 | 70 |
| 2015-12 | 509 | 327 | 275 | 179 | 164 | 164 | 182 | 182 | 225 | 314 | 69 |
| 2016-01 | 509 | 328 | 276 | 178 | 163 | 163 | 181 | 182 | 224 | 316 | 69 |
| 2016-02 | 509 | 329 | 277 | 177 | 162 | 162 | 180 | 181 | 222 | 318 | 72 |
| 2016-03 | 509 | 330 | 277 | 179 | 163 | 163 | 179 | 182 | 222 | 315 | 71 |
| 2016-04 | 504 | 336 | 281 | 181 | 164 | 164 | 168 | 174 | 215 | 308 | 73 |
| 2016-05 | 504 | 339 | 282 | 185 | 166 | 166 | 165 | 172 | 214 | 305 | 73 |
| 2016-06 | 504 | 344 | 287 | 183 | 165 | 165 | 160 | 168 | 209 | 310 | 75 |
| 2016-07 | 504 | 348 | 290 | 188 | 169 | 169 | 156 | 166 | 206 | 307 | 75 |
| 2016-08 | 504 | 349 | 292 | 187 | 168 | 168 | 155 | 166 | 204 | 308 | 75 |
| 2016-09 | 504 | 349 | 292 | 189 | 170 | 170 | 155 | 166 | 204 | 306 | 75 |
| 2016-10 | 504 | 354 | 295 | 191 | 171 | 171 | 150 | 162 | 201 | 304 | 75 |
| 2016-11 | 504 | 354 | 296 | 191 | 171 | 171 | 150 | 162 | 200 | 304 | 75 |
| 2016-12 | 504 | 354 | 296 | 192 | 172 | 172 | 150 | 162 | 200 | 303 | 75 |
| 2017-01 | 504 | 354 | 296 | 193 | 172 | 172 | 150 | 162 | 200 | 302 | 75 |
| 2017-02 | 504 | 356 | 297 | 195 | 174 | 174 | 148 | 161 | 199 | 301 | 75 |
| 2017-03 | 504 | 357 | 298 | 195 | 174 | 174 | 147 | 160 | 198 | 301 | 76 |
| 2017-04 | 504 | 359 | 301 | 195 | 175 | 175 | 145 | 159 | 195 | 301 | 79 |
| 2017-05 | 504 | 360 | 302 | 195 | 176 | 176 | 144 | 158 | 194 | 301 | 79 |
| 2017-06 | 504 | 360 | 302 | 194 | 175 | 175 | 144 | 158 | 194 | 302 | 79 |
| 2017-07 | 504 | 362 | 302 | 192 | 173 | 173 | 142 | 156 | 194 | 304 | 80 |
| 2017-08 | 504 | 364 | 304 | 193 | 174 | 174 | 140 | 155 | 192 | 304 | 81 |
| 2017-09 | 504 | 366 | 305 | 192 | 173 | 173 | 138 | 152 | 190 | 305 | 83 |
| 2017-10 | 504 | 367 | 307 | 194 | 175 | 175 | 137 | 152 | 188 | 304 | 83 |
| 2017-11 | 504 | 368 | 308 | 196 | 177 | 177 | 136 | 151 | 187 | 303 | 83 |
| 2017-12 | 504 | 368 | 308 | 197 | 178 | 178 | 136 | 151 | 187 | 302 | 83 |
| 2018-01 | 504 | 367 | 308 | 197 | 178 | 178 | 137 | 151 | 187 | 302 | 83 |
| 2018-02 | 504 | 368 | 310 | 198 | 179 | 179 | 136 | 150 | 185 | 301 | 83 |
| 2018-03 | 504 | 368 | 310 | 200 | 181 | 181 | 136 | 149 | 185 | 297 | 83 |
| 2018-04 | 504 | 369 | 312 | 200 | 183 | 183 | 135 | 148 | 182 | 297 | 84 |
| 2018-05 | 504 | 370 | 314 | 203 | 186 | 186 | 134 | 147 | 180 | 294 | 84 |
| 2018-06 | 504 | 371 | 314 | 205 | 188 | 188 | 133 | 146 | 180 | 293 | 84 |
| 2018-07 | 504 | 375 | 314 | 205 | 188 | 188 | 129 | 143 | 180 | 294 | 84 |
| 2018-08 | 504 | 375 | 316 | 205 | 188 | 188 | 129 | 143 | 178 | 294 | 84 |
| 2018-09 | 504 | 376 | 317 | 206 | 189 | 189 | 128 | 143 | 177 | 293 | 83 |
| 2018-10 | 504 | 375 | 318 | 206 | 189 | 189 | 129 | 142 | 176 | 293 | 84 |
| 2018-11 | 504 | 376 | 319 | 205 | 188 | 188 | 128 | 140 | 175 | 294 | 84 |
| 2018-12 | 504 | 379 | 322 | 206 | 189 | 189 | 125 | 138 | 172 | 293 | 84 |
| 2019-01 | 504 | 381 | 323 | 208 | 190 | 190 | 123 | 137 | 171 | 291 | 84 |
| 2019-02 | 504 | 380 | 322 | 208 | 190 | 190 | 124 | 137 | 171 | 290 | 84 |
| 2019-03 | 504 | 378 | 323 | 229 | 212 | 212 | 126 | 136 | 168 | 267 | 84 |
| 2019-04 | 504 | 376 | 323 | 234 | 217 | 217 | 128 | 135 | 168 | 261 | 84 |
| 2019-05 | 504 | 375 | 322 | 235 | 218 | 218 | 129 | 135 | 169 | 260 | 83 |
| 2019-06 | 505 | 375 | 323 | 230 | 214 | 214 | 130 | 135 | 169 | 266 | 83 |
| 2019-07 | 504 | 372 | 322 | 228 | 213 | 213 | 132 | 136 | 168 | 267 | 84 |
| 2019-08 | 504 | 372 | 322 | 226 | 211 | 211 | 132 | 135 | 167 | 269 | 84 |
| 2019-09 | 504 | 370 | 322 | 221 | 207 | 207 | 134 | 134 | 165 | 272 | 84 |
| 2019-10 | 505 | 383 | 332 | 231 | 217 | 217 | 122 | 134 | 165 | 270 | 83 |
| 2019-11 | 505 | 384 | 333 | 238 | 224 | 224 | 121 | 134 | 165 | 264 | 83 |
| 2019-12 | 505 | 384 | 335 | 239 | 226 | 226 | 121 | 134 | 163 | 263 | 83 |
| 2020-01 | 505 | 385 | 336 | 238 | 225 | 225 | 120 | 133 | 162 | 264 | 82 |
| 2020-02 | 505 | 385 | 337 | 238 | 225 | 225 | 120 | 133 | 161 | 264 | 81 |
| 2020-03 | 505 | 385 | 337 | 246 | 231 | 231 | 120 | 133 | 161 | 256 | 81 |
| 2020-04 | 505 | 386 | 341 | 252 | 237 | 237 | 119 | 133 | 158 | 251 | 81 |
| 2020-05 | 505 | 389 | 340 | 251 | 236 | 236 | 116 | 132 | 159 | 252 | 81 |
| 2020-06 | 505 | 389 | 342 | 247 | 234 | 234 | 116 | 131 | 157 | 256 | 81 |
| 2020-07 | 505 | 389 | 344 | 246 | 234 | 234 | 116 | 131 | 155 | 257 | 80 |
| 2020-08 | 505 | 389 | 344 | 247 | 235 | 235 | 116 | 131 | 155 | 256 | 80 |
| 2020-09 | 505 | 389 | 344 | 248 | 236 | 236 | 116 | 131 | 155 | 255 | 80 |
| 2020-10 | 505 | 390 | 343 | 247 | 234 | 234 | 115 | 131 | 156 | 256 | 80 |
| 2020-11 | 505 | 390 | 344 | 247 | 234 | 234 | 115 | 131 | 155 | 256 | 79 |
| 2020-12 | 505 | 391 | 344 | 247 | 234 | 234 | 114 | 130 | 155 | 256 | 79 |
| 2021-01 | 505 | 391 | 344 | 250 | 237 | 237 | 114 | 130 | 155 | 253 | 78 |
| 2021-02 | 505 | 391 | 346 | 250 | 238 | 238 | 114 | 129 | 153 | 253 | 78 |
| 2021-03 | 505 | 392 | 346 | 250 | 238 | 238 | 113 | 128 | 153 | 253 | 78 |
| 2021-04 | 505 | 392 | 348 | 249 | 237 | 237 | 113 | 129 | 151 | 254 | 77 |
| 2021-05 | 505 | 392 | 349 | 249 | 238 | 238 | 113 | 129 | 150 | 254 | 77 |
| 2021-06 | 505 | 392 | 350 | 249 | 239 | 239 | 113 | 129 | 149 | 254 | 77 |
| 2021-07 | 505 | 392 | 350 | 248 | 238 | 238 | 113 | 128 | 149 | 255 | 77 |
| 2021-08 | 505 | 392 | 351 | 248 | 239 | 239 | 113 | 128 | 148 | 255 | 77 |
| 2021-09 | 505 | 393 | 352 | 247 | 239 | 239 | 112 | 128 | 147 | 256 | 77 |

Los motivos de exclusión se solapan; no deben sumarse para estimar pérdidas marginales. Los detalles de cada security-period están en el candidato comprimido.

## Sectores

| Sector SIC descriptivo | Issuers | Issuer-months | Porcentaje |
|---|---:|---:|---:|
| Agriculture | 1 | 15 | 0.09% |
| Construction | 3 | 80 | 0.49% |
| Manufacturing | 138 | 8047 | 49.44% |
| Mining | 10 | 591 | 3.63% |
| Retail | 28 | 1704 | 10.47% |
| Services | 48 | 2638 | 16.21% |
| Transport, Comms, Utilities | 38 | 2648 | 16.27% |
| Wholesale | 8 | 552 | 3.39% |

## Bloqueos ordenados

Para identidades sin resolver se informa security-periods, no issuer-months inventados. Los impactos por causa/concepto se solapan y no equivalen a observaciones recuperables automáticamente.

### MEMBERSHIP

| Motivo | Issuer-months conocidos afectados | Security-periods sin issuer |
|---|---:|---:|
| HISTORICAL_REFERENCE_DISAGREEMENT_OR_MISSING | 1278 | 10550 |
| UNRESOLVED_SECURITY_PERIOD_OR_IDENTITY | 57 | 182 |
| CONTRADICTORY_MEMBERSHIP_SOURCES | 2 | 0 |
| NO_SUPPORTED_MEMBERSHIP_AT_T | 0 | 239 |

### IDENTITY

| Motivo | Issuer-months conocidos afectados | Security-periods sin issuer |
|---|---:|---:|
| PRIMARY_ISSUER_HISTORY_NOT_SUPPORTED_AT_DECISION | 206 | 0 |
| AMBIGUOUS_HISTORICAL_PRIMARY_CIK | 0 | 5414 |
| COMMON_CLASS_TICKER_NOT_IN_PRIMARY_SUBMISSIONS_OR_DATED_EVENT | 0 | 4201 |
| MULTIPLE_HISTORICAL_INSTRUMENTS_REQUIRE_DATED_VENDOR_BINDING | 0 | 960 |
| NO_UNIQUE_PRIMARY_CIK_TICKER_MATCH | 0 | 842 |
| NO_EXACT_OFFICIAL_CURRENT_OR_FORMER_NAME | 0 | 765 |
| PREEXISTING_FIRST_ML_IDENTITY_AUDIT_PARTIAL | 0 | 170 |
| NO_PRIMARY_INSTRUMENT_IDENTIFIER | 0 | 113 |
| PRIMARY_ISSUER_HISTORY_STARTS_AFTER_RESEARCH_PERIOD | 0 | 106 |
| PRIMARY_ISSUER_HISTORY_ENDS_BEFORE_SECURITY_PERIOD | 0 | 104 |
| ISSUER_CONFLICT | 0 | 85 |
| PRIMARY_ISSUER_HISTORY_UNAVAILABLE | 0 | 85 |
| PRIMARY_ISSUER_HISTORY_STARTS_AFTER_SECURITY_PERIOD | 0 | 21 |

### PRICE

| Motivo | Issuer-months conocidos afectados | Security-periods sin issuer |
|---|---:|---:|
| MARKET_DATA_UNAVAILABLE | 2509 | 0 |
| INSUFFICIENT_PRICE_HISTORY | 262 | 0 |
| IDENTITY_UNRESOLVED | 206 | 12866 |
| VENDOR_INSTRUMENT_MISMATCH | 160 | 0 |

### FUNDAMENTALS

| Motivo | Issuer-months conocidos afectados | Security-periods sin issuer |
|---|---:|---:|
| UNSUPPORTED_SECTOR | 4415 | 2176 |
| MAPPING_GAP | 3476 | 0 |
| unresolved_tag | 2581 | 0 |
| NO_PRIMARY_FACTS_ARCHIVED | 576 | 0 |
| MAPPING_GAP;unresolved_tag | 365 | 0 |
| INSUFFICIENT_HISTORY | 214 | 0 |
| NOT_MEANINGFUL;denominator_invalid | 125 | 0 |
| NOT_MEANINGFUL | 25 | 0 |
| MAPPING_GAP;denominator_invalid | 23 | 0 |
| denominator_invalid | 10 | 0 |
| MAPPING_GAP;NOT_MEANINGFUL | 8 | 0 |
| MAPPING_GAP;denominator_invalid;unresolved_tag | 4 | 0 |
| NO_VERIFIED_PRIMARY_FACTS | 0 | 10690 |

### UNSUPPORTED_SECTOR

| Motivo | Issuer-months conocidos afectados | Security-periods sin issuer |
|---|---:|---:|
| 67 | 1728 | 516 |
| 63 | 1088 | 723 |
| 62 | 799 | 85 |
| 60 | 269 | 682 |
| 61 | 225 | 85 |
| 64 | 221 | 85 |
| 65 | 85 | 0 |

## Deuda de conceptos XBRL

Existing mapped tags and unrelated tax/comprehensive-income concepts are excluded. Lexical candidates are counted only where their existing core family has MAPPING_GAP and the concept was already available. Presence does not prove semantic equivalence or that mapping repairs coverage; impacts overlap.

No se declara XBRL_TAG_UNMAPPED por mera ausencia de un ratio. Se agrupan conceptos no usados como candidatos de revisión semántica; falta de historia, datos no comparables, conflictos y problemas de ingesta conservan sus propios motivos. No hay mappings nuevos.

| Concepto candidato | Issuers con campo incompleto | Issuer-months afectados |
|---|---:|---:|
| ProfitLoss | 91 | 3080 |
| NetIncomeLossAttributableToNoncontrollingInterest | 61 | 1951 |
| NetIncomeLossAvailableToCommonStockholdersBasic | 49 | 1871 |
| SalesRevenueGoodsNet | 44 | 1804 |
| BusinessAcquisitionsProFormaRevenue | 43 | 1504 |
| AdjustmentsNoncashItemsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivitiesOther | 36 | 1434 |
| BusinessAcquisitionsProFormaNetIncomeLoss | 32 | 1235 |
| NetIncomeLossAvailableToCommonStockholdersDiluted | 35 | 1225 |
| AvailableForSaleSecurities | 39 | 1170 |
| DisposalGroupIncludingDiscontinuedOperationRevenue | 33 | 974 |
| AvailableforsaleSecuritiesGrossUnrealizedGain | 20 | 821 |
| ProceedsFromSaleOfAvailableForSaleSecurities | 23 | 711 |
| SalesRevenueServicesNet | 20 | 706 |
| AvailableForSaleSecuritiesNoncurrent | 16 | 676 |
| AvailableForSaleSecuritiesGrossUnrealizedLosses1 | 17 | 655 |
| AvailableForSaleSecuritiesDebtSecurities | 24 | 621 |
| ContractWithCustomerLiabilityRevenueRecognized | 30 | 557 |
| ProceedsFromSaleAndMaturityOfAvailableForSaleSecurities | 12 | 548 |
| AvailableForSaleSecuritiesGrossUnrealizedLoss | 16 | 546 |
| AvailableForSaleSecuritiesDebtMaturitiesAfterOneThroughFiveYearsFairValue | 15 | 545 |
| FairValueMeasurementWithUnobservableInputsReconciliationRecurringBasisAssetPurchasesSalesIssuancesSettlements | 13 | 545 |
| AvailableForSaleSecuritiesFairValueDisclosure | 20 | 536 |
| PaymentsToAcquireAvailableForSaleSecurities | 14 | 528 |
| AvailableForSaleSecuritiesCurrent | 17 | 521 |
| AvailableForSaleSecuritiesGrossUnrealizedGains | 13 | 492 |
| AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue | 16 | 483 |
| EquityMethodInvestmentSummarizedFinancialInformationNetIncomeLoss | 12 | 476 |
| RevenuesFromTransactionsWithOtherOperatingSegmentsOfSameEntity | 15 | 453 |
| SegmentReportingInformationRevenue | 12 | 452 |
| EntityWideDisclosureOnGeographicAreasRevenueFromExternalCustomersAttributedToEntitysCountryOfDomicile | 11 | 446 |

## Límites observados de colección

SEC: 454 emisores clasificados, `{"COMPLETE": 144, "FAILED": 30, "PARTIAL": 249, "REUSED_PRIMARY_ARCHIVE": 31}`. Yahoo: 550 símbolos clasificados.

Reserva de disco: 186 URLs bloqueadas por capacidad; 39 CIK afectados. 418 issuer-months conocidos tienen a la vez un bloqueo fundamental y una colección afectada por capacidad; no se afirma que todos se repararían al descargar. Los originales se conservan. Continuar esas descargas requiere capacidad adicional y una nueva revisión explícita de evidencia, sin borrar fallos anteriores.

## Decisión

La muestra ampliada aumenta materialmente la información transversal disponible. Antes de un experimento estructural único conviene resolver los mayores vacíos de identidad/membresía histórica y fijar explícitamente el próximo coverage contract. El alcance actual no permite afirmar tamaño efectivo independiente, estabilidad de señal o aptitud estadística: no se han inspeccionado outcomes.

Recomendación única: **CONTINUE_DATA_EXPANSION**. Priorizar períodos históricos excluidos y disponibilidad de empresas desaparecidas, según el ranking; no seguir cambiando algoritmos sobre el dataset anterior ni iniciar otro entrenamiento en esta tarea.

## Hashes del candidato

- membership: `bc97cc9ec2ddf81dce16e66da2c4dfd7527d9e4b740a238d02d865420ad22b2b`
- identity: `aae7968149672b9e25360d054fb28562fef6c20d97bfe4333717918c6799095d`
- price_universe: `7ca5cced746b397b7bd3bc449ed053e442c711499f7315ce7b462c1f9f4b43f7`
- fundamental_universe: `8f9f76029ace786c8005eedf50b2bdc52de40e7512fa34ca56584c04b1fd90fc`
- coverage: `0d10c4b0d73eb5cdcb92db75e7d7dfd1f47e1aa5d6432217f0b4b1fe73542c4e`

dev_adaptive_iteration=2; holdout outcomes=0; OOT outcomes=0; new_fits=0.
