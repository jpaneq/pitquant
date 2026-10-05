# D02 critical path to first ML

**Not achieved.** Usable READY months: 60 → 72; longest usable run: 60 → 72/85; calendar folds: 0 → 1/3. Membership-only ready months: 72. No training.

Scope: 2015-09 through 2017-09, processed newest first. Shared segment proofs closed six-month blocks; the chronology stops at the still-blocked 2016-09 decision. Original baseline rows and all 93 original cards are preserved unchanged in `D02_CRITICAL_PATH_FIRST_ML.json`; current comparison and exact source provenance are in `D02_CRITICAL_PATH_RESULT.json`. Raw anchors remain unchanged.

| Measure | Count |
|---|---|
| Original critical cards | 93 |
| Original cards closed | 57 |
| Current inside-critical membership cards | 36 |
| Outside-critical membership cards (inventoried, not cleanup target) | 131 |
| Current global weak identities | 40 |

## Current monthly table, descending

| Month | Status | Cards | Events | Identity cards | Ambiguities | Conflicts | Weak instruments | Minimum action |
|---|---|---|---|---|---|---|---|---|
| 2017-09 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-08 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-07 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-06 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-05 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-04 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-03 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-02 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2017-01 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2016-12 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2016-11 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2016-10 | READY | 0 | 0 | 0 | 0 | 0 | 0 | None |
| 2016-09 | BLOCKED | 1 | 1 | 0 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-08 | BLOCKED | 1 | 1 | 0 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-07 | BLOCKED | 1 | 1 | 0 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-06 | BLOCKED | 1 | 1 | 0 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-05 | BLOCKED | 1 | 1 | 0 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-04 | BLOCKED | 1 | 1 | 0 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-03 | BLOCKED | 12 | 10 | 1 | 0 | 1 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-02 | BLOCKED | 12 | 10 | 1 | 0 | 1 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2016-01 | BLOCKED | 11 | 10 | 1 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2015-12 | BLOCKED | 11 | 10 | 1 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2015-11 | BLOCKED | 11 | 10 | 1 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2015-10 | BLOCKED | 11 | 10 | 1 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |
| 2015-09 | BLOCKED | 23 | 17 | 6 | 0 | 0 | not fully reconstructible | Close the listed official-event cards and replay; identity set cannot yet be fully certified |

A blocked month has no fully certified member set: its weak-instrument count is unknown, not zero. Identity cards are distinct from weak identities within a reconstructed member set. Card totals count instrument legs, not independent corporate transactions.

## Reviewed closures

One Broadcom Ltd card changed from contradiction to missing addition and remains blocked; its changed gap ID is not counted as resolved.

Dated SEC transactions distinguish Dominion, Tesoro, CSC/DXC, Dow/DowDuPont, GGP, L-3, FMC/TechnipFMC, Alcoa/Arconic, DaVita, McGraw/S&P Global, XL and Tyco/JCI. Ratios are specific to the predecessor: CSC and Dow 1:1, FMC 1:1, XL 1:1, L-3 1:1, Tyco 0.955:1; RTN, DuPont and old Johnson Controls are separate legs. Sources, header CIK/accession checks, classes, CUSIPs/ISINs, legal/trading dates, precision and hashes are in `D02_CRITICAL_IDENTITY_RESOLUTIONS.json`.

Parser fixes retain Nemours' final s, resolve exact same-release full names, accept 'at the open', and admit an index-less pair only if the exact S&P 500 summary table confirms both legs. A pretraded N-30D pair is adjusted only when the same official next-session pair supports both sides. Two document-specific BR artifacts preserve explicit class A. Closed SEC issuer abbreviations resolve only exact names and compatible explicit classes in every anchor quarter; a mismatch remains blocked. No issuer, ticker or spelling similarity merges securities.

**Time precision:** L-3 and Alcoa filings state local times without a timezone. The stored UTC values are monthly reconstruction boundaries, not verified legal UTC instants; reviewed precision notes supersede the initial ET wording retained in immutable local link notes. Neither uncertain instant can change the first NYSE monthly decision here. Intraday use would require explicit timezone evidence. Alcoa's reverse split and spin-off remain separate from the name/identifier event; no research return remapping was performed.

## Remaining critical cards

| Gap ID | Segment | Instrument | Category | Official proof required |
|---|---|---|---|---|
| e165e78849d521c286b0 | 2015-03-31→2015-09-30 | Laboratory Corp. of America Holdings | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| f0cc5692bd0bce476a62 | 2015-03-31→2015-09-30 | Health Care REIT, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| dc22bb93050a9aa7d1c5 | 2015-03-31→2015-09-30 | News Corp. (Class B) | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| b90d1b8e5ed9be70322c | 2015-03-31→2015-09-30 | Alphabet, Inc. (Class C) | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 9975561bbd86d605d534 | 2015-03-31→2015-09-30 | WestRock Co. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 260b8ac8b650438679b6 | 2015-03-31→2015-09-30 | Alphabet, Inc. (Class A) | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 44fdf340690c77c3a25f | 2015-03-31→2015-09-30 | MeadWestvaco Corp. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| f5d21137d6351abe81d2 | 2015-03-31→2015-09-30 | Actavis PLC | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 775ad4ebdb8a3e9f1e46 | 2015-03-31→2015-09-30 | Kraft Heinz Co. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 55ff93bd6e220947454a | 2015-03-31→2015-09-30 | Google, Inc. (Class C) | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| efea0e5c230ed42b0a57 | 2015-03-31→2015-09-30 | Twenty-First Century Fox, Inc. (Class B) | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| bc21d9429ac9a7d88d1e | 2015-03-31→2015-09-30 | WEC Energy Group, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 4014d7c5461a5cdfc7ed | 2015-03-31→2015-09-30 | Allergan PLC | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 773157b6ab379b614ad3 | 2015-03-31→2015-09-30 | Kraft Foods Group, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 9e84a8070786d6765738 | 2015-03-31→2015-09-30 | Gannett Co., Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 4a733a71a16cc4b19b5b | 2015-03-31→2015-09-30 | Welltower, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| cce5f52831d09f95a80b | 2015-03-31→2015-09-30 | Noble Corp. PLC | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 6288ce30ff6ca090c074 | 2015-03-31→2015-09-30 | TEGNA, Inc. | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 3dfc145a83e78bbe08ef | 2015-03-31→2015-09-30 | Comcast Corp. (Special Class A) | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 32f800082db059fb0795 | 2015-03-31→2015-09-30 | Laboratory Corp. of AmericaHoldings | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| a5179c57e07bc68517bf | 2015-03-31→2015-09-30 | PayPal Holdings, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| da1151e425832bcbe2eb | 2015-03-31→2015-09-30 | Wisconsin Energy Corp. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 35cf8ce953c75ab6b4e6 | 2015-03-31→2015-09-30 | Google, Inc. (Class A) | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 863202f5c4256d4f50b9 | 2015-09-30→2016-03-31 | Willis Towers Watson PLC | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 12a490a52ac07a0c6868 | 2015-09-30→2016-03-31 | Avago Technologies, Ltd. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 6188a99eed2cc5eaefbb | 2015-09-30→2016-03-31 | HP, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 7594a7ce86e97edf85ef | 2015-09-30→2016-03-31 | US Bancorp | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 7cccaeafbc8bf8a9315d | 2015-09-30→2016-03-31 | Roper Technologies, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 9369adca69da6c677b1a | 2015-09-30→2016-03-31 | Roper Industries, Inc. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 6b0e257649daf7ee6719 | 2015-09-30→2016-03-31 | Hewlett-Packard Co. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 0c498944897e0669457c | 2015-09-30→2016-03-31 | Broadcom, Ltd. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 48e76ec550ab6d971b4d | 2015-09-30→2016-03-31 | Chubb Corp. | PRIMARY_DELTA_UNEXPLAINED | Audit the linked primary release and both anchor rows; resolve contradictory event legs, transient positions or legal predecessor/successor with official evidence. |
| 948c6451731ed389c0c0 | 2015-09-30→2016-03-31 | U.S. Bancorp | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| c227fe2ba3c93644647f | 2015-09-30→2016-03-31 | Comcast Corp. (Special Class A) | SECURITY_IDENTITY_ONLY | Official dated CUSIP/class observation and issuer/exchange transaction evidence linking exactly these instruments. Same issuer/name/ticker is insufficient. |
| 9c97d251e2be894e1c76 | 2015-09-30→2016-03-31 | ACE, Ltd. | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |
| 6c5a95f6a607858fc601 | 2016-03-31→2016-09-30 | Under Armour, Inc. Class C | PRIMARY_EVENT_MISSING | Dated S&P release proving the actual addition/removal effective session; issuer 8-K may corroborate a transaction, not index membership by itself. |

## Honest stopping condition and minimum next action

The newest remaining segment 2016-03→09 is blocked by Under Armour Class C. The SEC annual filing proves distribution April 7 and initial UA.C listing April 8, but not the index-effective date. Targeted searches of official S&P press/indexnews sources retrieved no sufficient dated Class C inclusion notice. Secondary dates remain discovery only, and issuer evidence cannot substitute for S&P membership. `D02_CRITICAL_SOURCE_ATTEMPTS.json` records the attempts and insufficient official document with its hash. Obtain that notice and replay this segment before moving to 2015-09→2016-03 and the September 2015 decision. Do not infer absence of an official document from search misses.

## Exact current calendar folds

| Fold | Train | N train | Excluded decisions | Embargo | Test |
|---|---|---|---|---|---|
| 0 | 2016-10..2019-10 | 37 | 2019-11..2020-10 | 2020-10..2020-10 | 2020-11..2021-10 |

Frozen inequality: train decision + H12 + embargo1 <= test start. Inclusive endpoints yield 37 training decision months in the first fold and 12 excluded decision months; the embargo lies within that excluded span. This documents the existing contract without changing it. Calendar feasibility alone does not certify mature 12M labels; holdout/OOT remain sealed and no labels/features are rebuilt.

## Gate matrix

| Gate | Status | Evidence |
|---|---|---|
| D02_MONTHLY_RESEARCH_READY | BLOCKED | 72/141 months READY, longest run 72, folds 1 |
| US_SECURITY_IDENTITY_READY | PARTIAL | 40 weak identity securities; 0 unresolved anchor lines |
| D05_READY | READY | Yahoo Finance (CANONICAL_PROVIDER_FOR_PITQUANT, VENDOR) |
| BENCHMARK_RETURN_BASIS_READY | READY | US rows comparable 7055/7055; non-US via USD conversion (PROXY) |
| RESEARCH_SECURITY_COVERAGE_READY | BLOCKED | 51 usable (strict); 51 if D05 were accepted; 100 with snapshots |
| US_FUNDAMENTALS_READY | READY | 40 securities |
| HOLDOUT_SEALED | READY | 0 snapshots inside the holdout |
| RESEARCH_DATA_READY | BLOCKED | derived |
| FIRST_ML_BASELINE_READY | BLOCKED | false |

Required securities=100 unchanged. The user has approved the *later methodological design* of a statistical coverage gate; no 100→51 reduction or substitute threshold is applied. XOM/RTX/GOOGL/GE research-series bindings remain PARTIAL, with their separate issues unchanged; see `FIRST_ML_SECURITY_IDENTITY.json`. Full source originals stay in the content-addressed archive; all new proof checks use pre-holdout historical sources.

Reproduce from repository root with the explicit project DB: `apply_d02_critical_identity.py` (runtime SEC contact), `apply_d02_document_breaks.py`, `apply_d02_critical_weak_identity.py`, `ingest_sp500_evidence.py --offline`, `build_sp500_anchor_graph.py`, `gen_d02_extended_audit.py`, `gen_data_readiness_first_ml.py`, `gen_d02_critical_provenance.py`, `gen_d02_critical_report.py`. No BTC, champion/master, model training or deployment is involved.
