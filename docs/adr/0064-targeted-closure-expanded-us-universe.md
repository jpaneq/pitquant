# ADR-0064 — Targeted closure of expanded US research universe

Status: accepted for data engineering; coverage contract proposed, training disabled.

Starting state: `b8bb890494310879f98066b5b95304644f4d42ad`.

The historical roster is fixed at 696 securities. This phase closes recoverable
data gaps without further open discovery, estimator fitting or outcome analysis.
The three frozen outer folds, purge, embargo and holdout boundary remain intact.

## Storage and source revisions

Archive objects use transparent APFS compression. Each original and compressed
copy is verified against the content-addressed SHA before atomic replacement.
Paths, logical bytes, source hashes and the ArchiveStore API remain unchanged.
An append-only compaction ledger records allocated space before/after. Compression
is an optional macOS maintenance operation, not a Linux runtime requirement.
Non-macOS execution fails before mutation. No evidence is deleted to meet quota.

The original cache is frozen. Exactly the 186 reserve-blocked URLs are retried in
a separate append-only cache revision. All succeed; offline ingestion is restricted
to their 39 CIK. No fresh SEC discovery occurs during ingestion. Failed source
records and the original candidate DB remain intact. The new DB starts as an APFS
copy-on-write clone; production data/pitquant.db is never written.

## Semantic mapping

XBRL_MAPPING_DEBT names technical mapping debt. Standard income concepts must not
be confused with financial debt. The previous sec-tags-4 functions and model
artifacts remain immutable. A new isolated sec-tags-5 function derives parent
income as ProfitLoss minus NetIncomeLossAttributableToNoncontrollingInterest,
requiring identical accession, period and USD unit, both visible before decision.
It does not assume absent NCI is zero or replace a reported same-accession parent
income. Derived fact IDs embed both original IDs; existing TTM periodization and
PIT revision selection are reused. Two concepts make one joint repair rule.
The freshest-period rule excludes 72 previously usable issuer-months when a newer
derived income period lacks matching prior FY/YTD components. No stale fallback is
introduced to inflate coverage. Gross recoveries and exclusions are separately
reported; net combined expansion is 466 issuer-months.

All 113 concepts exceeding the fixed work budget are reviewed with primary SEC
taxonomy definitions. Two are accepted only for the composite; 104 direct mappings
are rejected and seven revenue components are deferred pending primary total
calculation context. Common-stockholder earnings, preferred adjustments,
pro forma amounts, investment assets, cash-flow adjustments and segment/customer
components do not silently replace consolidated revenue or parent income.

## Dated class identities and Yahoo

Existing exact primary aliases can repair identity only with a verified SEC source,
matching native filing accession/CIK and publication before the research boundary.
Current tickers alone do not prove a historical class. Native collision checks and
ADR-0056 evidence tiers remain in force. No successor price splice is permitted.

The existing Under Armour 2016 10-K (`0001336917-17-000017`, available
2017-02-24T14:30Z) independently identifies Class A UA/UAA and Class C UA.C/UA
with the explicit dates. Class A's vendor retrieval symbol is UAA; its dated
historical ticker remains UA before 2016-12-07. The class correction also allows
the unchanged ADR-0056 corroborator to classify 20 previously unverified monthly
periods; it does not manufacture an official S&P event. Class C retains its Yahoo
OHLC error and remains price-ineligible. Class C's issuance was a distribution of
a different security. The present return engine cannot value that distribution:
scientific price-feature and label windows crossing 2016-04-08 are excluded. This
explicit legal event exception is evidenced and versioned, not an issuer-specific
fundamental substitution.

The work budget covers the 20 leading identity and 20 Yahoo cases, plus the two
archived class repairs. Unresolved historical identity, ambiguous CIKs, reused
tickers and provider failures remain visible. They exclude security-periods, not
entire monthly cohorts. Unsupported financial SIC divisions remain excluded.

## Scientific constructibility

The complete frozen PRICE/FUNDAMENTAL/RISK schemas are built with native causal
engines. Mandatory cores must be finite. Optional fields retain explicit missing
reasons and the previous train-only imputation contract; no preprocessing is fit.
PIT guards run on every constructed feature. Technical rolling panels reuse the
native, truncation-tested functions. Valuation uses RAW closes and known actions.

12M constructibility uses timestamp/null-presence metadata and a conservative
complete session window for security and benchmark. Future price amounts,
returns, targets and model metrics are neither calculated nor exported. Legal
successions and sealed boundary crossings are excluded. Benchmark queries select
time columns only. Baseline scientific availability is independently rebuilt from
the original retained DB, rather than inferred from the final coverage counts.

The structural contract is proposed: at least 100 issuers and 50% of verified
membership, at least five broad SIC groups, largest-group share at most 60%, and
top-three share at most 90%, in every frozen train/test month. The 100-issuer
benchmark predates observed coverage; 150 remains descriptive. These requirements
represent breadth, not effective sample size, statistical power or permission to
train. All 85 measured months meet the proposal. Missing removed-issuer prices and
unsupported financial families still restrict population inference; lifecycle
unknowns alone do not invalidate otherwise sound research identities.

## Preservation and reproducibility

Original universe/candidate files stay immutable. The earlier coverage JSON is
retained byte-for-byte as US_LARGE_CAP_RESEARCH_COVERAGE_EXPANSION_BASELINE_V1.json.
Tests verify both baseline and new candidate against their own pinned hashes;
baseline tests are not redirected to changed data. Targeted snapshots and
intermediate revisions are separately hashed. Replay uses retained copied DBs,
original cache revisions and content-addressed sources. The SEC contact exists
only in the runtime environment, never artifacts or logs.

STOP is satisfied: capacity resolved, high-impact mappings reviewed, leading
identity/Yahoo cases repaired or classified, scientific coverage measured and
remaining long tail quantified. Freeze this expanded data candidate and design
the final ranking experiment separately. No training here: new_fits=0,
dev_adaptive_iteration=2, holdout outcomes=0, OOT outcomes=0.
