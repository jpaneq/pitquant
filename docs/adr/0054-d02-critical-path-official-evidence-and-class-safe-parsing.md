# ADR-0054 — D02 critical path, official evidence and class-safe parsing

Status: accepted for evidence reconstruction; no model training or coverage-gate change.

## Decision

Prioritize the 25 decisions 2015-09..2017-09 newest first, immediately before the original 60-month run. Reuse shared segment proofs, stop at 85 consecutive usable READY months and three calendar folds, and stop chronologically at an official-evidence blocker rather than clean unrelated history. Membership readiness alone does not certify usable cohorts: every reconstructed member must have official instrument identity evidence.

The frozen first-ML contract remains train_min=36, H=12, embargo=1, test=12, min_folds=3, required_securities=100. Its inclusive endpoints and inequality `train_decision + H + embargo <= test_start` are documented by exact fold ranges, not changed. Calendar folds do not prove mature labels or justify using the holdout.

## Evidence and parser rules

- SEC complete-submission header must match the requested accession and filer CIK. The primary HTML is the `<DOCUMENT>` whose declared type equals the header form and whose sequence is 1; arbitrary first HTML/exhibits are forbidden. Each reviewed transaction declares its actual form (8-K, 8-K12B or 10-K), exact transaction phrases and before/after quarterly official CUSIPs.
- S&P supplies membership events. A paragraph without the index name is parsed only when its exact added/deleted names occur as the one added/deleted pair in the same S&P 500 summary table. MidCap/SmallCap summary rows do not qualify. `at the open` has its stated session meaning. Exact same-release full company mentions resolve abbreviations; the final s in Nemours is retained.
- A company-only exact name must not hide explicit share-class candidates. The resolver retains the full exact company/class candidate pool and requires unique segment plausibility. It never joins the candidates or infers that A=C; multiple plausible instruments remain unresolved.
- An N-30D portfolio that pretrades the next session's official replacement is adjusted as derived index state only when the **same official pair** proves both legs: remove the held-ahead addition and restore the absent outgoing member. This fixes Coty/Diamond Offshore for the 2016-09-30 portfolio. Original anchor rows and bytes are unchanged; unpaired removals do not justify restoration.
- Document-specific BR artifacts at accession `0001193125-16-777823`, hash `997f53d43c213337fc103c27ea92e7653ab558dea8999835959429ab7222222a`, positions 88 and 286 restore CBRE Class A and LyondellBasell Class A. The exact HTML breaks and explicit classes are checked. They are extraction corrections, not corporate actions or issuer substitutions.
- Closed, reviewed SEC 13(f) issuer formats expand inverted initials/legal abbreviations for the weak instruments actually blocking the critical window: DuPont, Harman, Dun & Bradstreet, St Jude, Transocean, Whole Foods, Owens-Illinois, Ryder, Mallinckrodt, and Cablevision. Explicit concatenated `SHS - A` / `CL A` rows preserve class A. Each bridge still requires a unique compatible row with the **same CUSIP in every anchor quarter**; no similarity, ticker reuse, global class inference or relaxed cardinality is allowed. The original SEC rows and hashes remain available in the result manifest.

## Corporate-event distinctions

Twelve reviewed SEC cases and their exact source assertions are reproduced by `apply_d02_critical_identity.py`. Name/ticker/identifier continuity is distinct from a new issuer/security (CSC/DXC, Dow/DowDuPont, L-3 holding/operating, FMC/TechnipFMC and XL redomiciliation). Tyco's continuing legal issuer consolidates shares 0.955:1 and changes name/CUSIP; it is a distinct instrument succession, not a mere alias. Old Johnson Controls' merger consideration remains separate. DuPont's 1.282 ratio is not Dow's 1:1; Technip's 2:1 is not FMC's 1:1. Alcoa's reverse split and Alcoa Corporation distribution are separate from the retained parent's Arconic name event; no research price units/returns are remapped here.

Legal date, ticker session and CUSIP evidence date remain separate. Quarterly CUSIP observations do not certify an exact transition day unless the primary filing states it. L-3 and Alcoa state local clock times without specifying a timezone: their stored UTC values are reconstruction boundaries for monthly decisions, **not verified legal UTC instants**. Reviewed manifest precision notes supersede the initial ET wording retained in immutable local notes. Those uncertain instants cannot change the first NYSE monthly decision in these cases; intraday reuse requires additional official timezone evidence. No immutable note/source is overwritten to disguise that limitation.

## Remaining blocker and reproducibility

Under Armour's SEC annual filing verifies the completed Class C distribution and initial UA.C listing, but does not establish the effective S&P 500 addition. A discovery CSV date, Class A continuity, issuer distribution or modern index methodology cannot close that membership card. Official S&P searches and the insufficient issuer filing are recorded in `D02_CRITICAL_SOURCE_ATTEMPTS.json`; search misses do not prove a document does not exist.

The original 93-card baseline is preserved in `D02_CRITICAL_PATH_FIRST_ML.json`; `D02_CRITICAL_PATH_RESULT.json` compares stable IDs, current monthly status, inside/outside residuals, source URLs/accessions/hashes, parser versions and exact folds. Report generators read existing data and fit nothing. Parser/graph/name/document versions retain earlier immutable runs.

The human has approved designing a later statistical coverage gate, not applying a substitute threshold now. Research-series XOM/RTX/GOOGL/GE bindings remain separately PARTIAL. BTC, scheduler, V0/P0, features, labels, champion/master, holdout/OOT and training are outside this change.
