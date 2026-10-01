# Modelo de datos

> Generado por `scripts/gen_data_model_doc.py` desde `pitquant.db.models`. No editar a mano.

Convenciones: `*_at` = instante UTC timezone-aware; `*_date` = fecha de calendario; intervalos semiabiertos `[from, to)`; 🔒 = tabla append-only (guard ORM + trigger PostgreSQL).

Tablas: **42**.

## Procedencia y calidad

### `data_sources`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `source_id` | INTEGER | no | PK |
| `name` | VARCHAR(100) | no |  |
| `provider_type` | VARCHAR(50) | no |  |
| `is_synthetic` | BOOLEAN | no |  |
| `is_point_in_time` | BOOLEAN | no |  |
| `description` | TEXT | sí |  |

- UNIQUE (name)

### `raw_records` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `raw_record_id` | VARCHAR(36) | no | PK |
| `source_id` | INTEGER | no | FK→`data_sources.source_id` |
| `original_identifier` | VARCHAR(200) | no |  |
| `retrieved_at` | DATETIME | no |  |
| `payload` | JSON | no |  |
| `payload_hash` | VARCHAR(64) | no |  |

- UNIQUE (source_id, original_identifier, payload_hash)

### `raw_source_archive` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `archive_id` | VARCHAR(36) | no | PK |
| `provider` | VARCHAR(100) | no |  |
| `source_identifier` | VARCHAR(1000) | no |  |
| `retrieved_at` | DATETIME | no |  |
| `published_at` | DATETIME | sí |  |
| `sha256` | VARCHAR(64) | no |  |
| `mime_type` | VARCHAR(100) | no |  |
| `size_bytes` | INTEGER | no |  |
| `storage_uri` | VARCHAR(500) | no |  |
| `parser_version` | VARCHAR(50) | sí |  |
| `notes` | TEXT | sí |  |

- INDEX ix_raw_source_archive_sha256 (sha256)

### `data_quality_issues`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `issue_id` | VARCHAR(36) | no | PK |
| `entity` | VARCHAR(50) | no |  |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `check_name` | VARCHAR(100) | no |  |
| `severity` | VARCHAR(20) | no |  |
| `details` | JSON | no |  |
| `detected_at` | DATETIME | no |  |
| `resolved_at` | DATETIME | sí |  |
| `raw_record_id` | VARCHAR(36) | sí | FK→`raw_records.raw_record_id` |

## Security Master

### `issuers`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `issuer_id` | VARCHAR(36) | no | PK |
| `name` | VARCHAR(300) | no |  |
| `country` | VARCHAR(2) | sí |  |

### `securities`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `security_id` | VARCHAR(36) | no | PK |
| `issuer_id` | VARCHAR(36) | sí | FK→`issuers.issuer_id` |
| `name` | VARCHAR(300) | no |  |
| `exchange` | VARCHAR(10) | no |  |
| `currency` | VARCHAR(3) | no |  |
| `country` | VARCHAR(2) | sí |  |
| `listing_start` | DATE | sí |  |
| `listing_end` | DATE | sí |  |
| `delisted` | BOOLEAN | no |  |
| `delisting_reason` | VARCHAR(30) | sí |  |
| `acquirer_security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `successor_security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `is_synthetic` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `listing_end IS NULL OR listing_start IS NULL OR listing_end >= listing_start`

### `provider_keys`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `source_id` | INTEGER | no | FK→`data_sources.source_id` |
| `provider_key` | VARCHAR(100) | no |  |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |

- UNIQUE (source_id, provider_key)

### `ticker_history`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `ticker` | VARCHAR(20) | no |  |
| `exchange` | VARCHAR(10) | no |  |
| `valid_from` | DATE | no |  |
| `valid_to` | DATE | sí |  |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |

- CHECK `valid_to IS NULL OR valid_to > valid_from`
- INDEX ix_ticker_history_security_id (security_id)
- INDEX ix_ticker_lookup (ticker, exchange, valid_from)

### `identifier_history`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `id_type` | VARCHAR(10) | no |  |
| `value` | VARCHAR(20) | no |  |
| `valid_from` | DATE | no |  |
| `valid_to` | DATE | sí |  |

- CHECK `valid_to IS NULL OR valid_to > valid_from`
- INDEX ix_identifier_history_security_id (security_id)
- INDEX ix_identifier_lookup (id_type, value, valid_from)

### `issuer_identifiers`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `issuer_id` | VARCHAR(36) | no | FK→`issuers.issuer_id` |
| `id_type` | VARCHAR(10) | no |  |
| `value` | VARCHAR(30) | no |  |
| `valid_from` | DATE | no |  |
| `valid_to` | DATE | sí |  |
| `source` | VARCHAR(100) | no |  |

- CHECK `valid_to IS NULL OR valid_to > valid_from`
- INDEX ix_issuer_identifier_lookup (id_type, value, valid_from)
- INDEX ix_issuer_identifiers_issuer_id (issuer_id)

### `sector_classification`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `scheme` | VARCHAR(20) | no |  |
| `sector` | VARCHAR(100) | no |  |
| `industry_group` | VARCHAR(100) | sí |  |
| `industry` | VARCHAR(100) | sí |  |
| `sub_industry` | VARCHAR(100) | sí |  |
| `valid_from` | DATE | no |  |
| `valid_to` | DATE | sí |  |
| `available_at` | DATETIME | no |  |

- INDEX ix_sector_classification_security_id (security_id)

## Identidad (ADR-0020)

### `security_identity_snapshots` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `source` | VARCHAR(50) | no |  |
| `reference_date` | DATE | no |  |
| `scope` | VARCHAR(40) | no |  |
| `isin` | VARCHAR(12) | no |  |
| `issuer_legal_name` | VARCHAR(300) | no |  |
| `instrument_name` | VARCHAR(300) | no |  |
| `instrument_class` | VARCHAR(10) | no |  |
| `cfi` | VARCHAR(6) | sí |  |
| `currency` | VARCHAR(3) | sí |  |
| `nominal` | VARCHAR(30) | sí |  |
| `issue_date` | DATE | sí |  |
| `issuer_id` | VARCHAR(36) | sí | FK→`issuers.issuer_id` |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `member_name` | VARCHAR(200) | no |  |
| `source_hash` | VARCHAR(64) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_security_identity_snapshots_isin (isin)
- INDEX ix_security_identity_snapshots_reference_date (reference_date)
- UNIQUE (source, reference_date, isin, source_hash)

### `identity_resolution_runs` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `run_id` | VARCHAR(36) | no | PK |
| `index_code` | VARCHAR(20) | no |  |
| `build_id` | VARCHAR(36) | no | FK→`membership_builds.build_id` |
| `engine_version` | VARCHAR(30) | no |  |
| `inputs_hash` | VARCHAR(64) | no |  |
| `canonical_start` | DATE | no |  |
| `metrics` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_identity_resolution_runs_build_id (build_id)

### `membership_identity_segments` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `run_id` | VARCHAR(36) | no | FK→`identity_resolution_runs.run_id` |
| `membership_id` | INTEGER | no | FK→`index_membership.id` |
| `segment_from` | DATE | no |  |
| `segment_to` | DATE | sí |  |
| `status` | VARCHAR(30) | no |  |
| `period_class` | VARCHAR(30) | no |  |
| `isin` | VARCHAR(12) | sí |  |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `issuer_id` | VARCHAR(36) | sí | FK→`issuers.issuer_id` |
| `evidence` | JSON | no |  |

- CHECK `segment_to IS NULL OR segment_to > segment_from`
- CHECK `status IN ('EXACT_OFFICIAL_IDENTIFIER','MULTI_SOURCE_CONFIRMED','PROVISIONAL','UNRESOLVED')`
- INDEX ix_membership_identity_segments_membership_id (membership_id)
- INDEX ix_membership_identity_segments_run_id (run_id)

## Universo

### `index_events` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `event_id` | VARCHAR(36) | no | PK |
| `index_code` | VARCHAR(20) | no |  |
| `event_type` | VARCHAR(30) | no |  |
| `parent_event_id` | VARCHAR(36) | sí | FK→`index_events.event_id` |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `ticker` | VARCHAR(20) | sí |  |
| `new_ticker` | VARCHAR(20) | sí |  |
| `identifier` | VARCHAR(20) | sí |  |
| `effective_date` | DATE | no |  |
| `announced_at` | DATETIME | sí |  |
| `reason` | VARCHAR(300) | sí |  |
| `membership_source` | VARCHAR(100) | no |  |
| `source_event_id` | VARCHAR(200) | no |  |
| `source_confidence` | VARCHAR(40) | no |  |
| `raw_source_hash` | VARCHAR(64) | no |  |
| `archive_id` | VARCHAR(36) | sí | FK→`raw_source_archive.archive_id` |
| `identity_status` | VARCHAR(30) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `event_type IN ('INDEX_ADD','INDEX_DELETE','TICKER_CHANGE','ORDINARY_REVIEW','EXTRAORDINARY_REVIEW','INITIAL_SNAPSHOT')`
- CHECK `identity_status IN ('RESOLVED','IDENTITY_UNRESOLVED')`
- INDEX ix_index_events_seq (index_code, membership_source, effective_date)
- UNIQUE (membership_source, source_event_id, raw_source_hash)

### `membership_builds` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `build_id` | VARCHAR(36) | no | PK |
| `index_code` | VARCHAR(20) | no |  |
| `membership_source` | VARCHAR(100) | no |  |
| `source_confidence` | VARCHAR(40) | no |  |
| `raw_source_hash` | VARCHAR(64) | no |  |
| `events_hash` | VARCHAR(64) | no |  |
| `n_events` | INTEGER | no |  |
| `status` | VARCHAR(20) | no |  |
| `eligible_for_final_model_validation` | BOOLEAN | no |  |
| `report` | JSON | no |  |
| `built_at` | DATETIME | no |  |

### `index_membership` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `build_id` | VARCHAR(36) | no | FK→`membership_builds.build_id` |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `index_code` | VARCHAR(20) | no |  |
| `ticker_at_inclusion` | VARCHAR(20) | sí |  |
| `effective_from` | DATE | no |  |
| `effective_to` | DATE | sí |  |
| `inclusion_reason` | VARCHAR(300) | sí |  |
| `exclusion_reason` | VARCHAR(300) | sí |  |
| `announced_at` | DATETIME | sí |  |
| `membership_source` | VARCHAR(100) | no |  |
| `source_event_id` | VARCHAR(36) | no | FK→`index_events.event_id` |
| `exclusion_event_id` | VARCHAR(36) | sí | FK→`index_events.event_id` |
| `source_confidence` | VARCHAR(40) | no |  |
| `raw_source_hash` | VARCHAR(64) | no |  |
| `identity_status` | VARCHAR(30) | no |  |

- CHECK `effective_to IS NULL OR effective_to > effective_from`
- CHECK `identity_status IN ('RESOLVED','IDENTITY_UNRESOLVED')`
- INDEX ix_membership_asof (build_id, index_code, effective_from, effective_to)

## Mercado

### `prices`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `security_id` | VARCHAR(36) | no | PK FK→`securities.security_id` |
| `session_date` | DATE | no | PK |
| `source_id` | INTEGER | no | PK FK→`data_sources.source_id` |
| `open` | FLOAT | sí |  |
| `high` | FLOAT | sí |  |
| `low` | FLOAT | sí |  |
| `close` | FLOAT | no |  |
| `volume` | FLOAT | sí |  |
| `currency` | VARCHAR(3) | no |  |
| `bar_close_at` | DATETIME | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `close > 0`
- CHECK `high IS NULL OR low IS NULL OR high >= low`

### `provider_adjusted_prices`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `security_id` | VARCHAR(36) | no | PK FK→`securities.security_id` |
| `session_date` | DATE | no | PK |
| `provider` | VARCHAR(50) | no | PK |
| `adj_close` | FLOAT | no |  |
| `vendor_last_updated` | DATE | sí |  |
| `source_hash` | VARCHAR(64) | no |  |
| `ingested_at` | DATETIME | no |  |

### `corporate_action_events` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `event_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `event_type` | VARCHAR(30) | no |  |
| `announcement_date` | DATE | sí |  |
| `ex_date` | DATE | sí |  |
| `record_date` | DATE | sí |  |
| `payment_date` | DATE | sí |  |
| `effective_date` | DATE | sí |  |
| `available_at` | DATETIME | no |  |
| `ratio` | FLOAT | sí |  |
| `cash_amount` | FLOAT | sí |  |
| `currency` | VARCHAR(3) | sí |  |
| `target_security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `details` | JSON | no |  |
| `provider` | VARCHAR(50) | no |  |
| `source_tier` | VARCHAR(20) | no |  |
| `provider_event_id` | VARCHAR(200) | no |  |
| `source_hash` | VARCHAR(64) | no |  |
| `archive_id` | VARCHAR(36) | sí | FK→`raw_source_archive.archive_id` |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `event_type IN ('CASH_DIVIDEND','SPECIAL_DIVIDEND','STOCK_DIVIDEND','SPLIT','REVERSE_SPLIT','RIGHTS_ISSUE','SCRIP_DIVIDEND','SPINOFF','CASH_ACQUISITION','STOCK_ACQUISITION','MERGER','DELISTING','BANKRUPTCY','TICKER_CHANGE','EXCHANGE_CHANGE','LISTING','RETURN_OF_CAPITAL','ISIN_CHANGE')`
- CHECK `ratio IS NULL OR ratio > 0`
- CHECK `source_tier IN ('OFFICIAL','VENDOR','FIXTURE')`
- INDEX ix_corporate_action_events_security_id (security_id)
- UNIQUE (provider, provider_event_id, source_hash)

### `corporate_actions`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `action_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `action_type` | VARCHAR(30) | no |  |
| `announced_at` | DATETIME | no |  |
| `ex_date` | DATE | no |  |
| `effective_date` | DATE | sí |  |
| `ratio` | FLOAT | sí |  |
| `cash_amount` | FLOAT | sí |  |
| `currency` | VARCHAR(3) | sí |  |
| `target_security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `details` | JSON | no |  |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_corporate_actions_security_id (security_id)

### `dividends`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `dividend_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `dividend_type` | VARCHAR(30) | no |  |
| `announced_at` | DATETIME | no |  |
| `ex_date` | DATE | no |  |
| `pay_date` | DATE | sí |  |
| `gross_amount` | FLOAT | no |  |
| `currency` | VARCHAR(3) | no |  |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |
| `ingested_at` | DATETIME | no |  |

- CHECK `gross_amount >= 0`
- INDEX ix_dividends_security_id (security_id)
- UNIQUE (security_id, ex_date, dividend_type, source_id)

### `benchmarks`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `benchmark_code` | VARCHAR(30) | no | PK |
| `name` | VARCHAR(200) | no |  |
| `kind` | VARCHAR(20) | no |  |
| `return_type` | VARCHAR(10) | no |  |
| `currency` | VARCHAR(3) | no |  |
| `index_code` | VARCHAR(20) | sí |  |
| `sector` | VARCHAR(100) | sí |  |

- CHECK `return_type IN ('TR','NTR')`

### `benchmark_levels`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `benchmark_code` | VARCHAR(30) | no | PK FK→`benchmarks.benchmark_code` |
| `session_date` | DATE | no | PK |
| `level` | FLOAT | no |  |
| `available_at` | DATETIME | no |  |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |

## Fundamentales, estimaciones y macro

### `financial_statements`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `statement_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `statement_type` | VARCHAR(20) | no |  |
| `fiscal_period` | VARCHAR(10) | no |  |
| `period_start` | DATE | sí |  |
| `period_end` | DATE | no |  |
| `published_at` | DATETIME | no |  |
| `available_at` | DATETIME | no |  |
| `revision_id` | INTEGER | no |  |
| `filing_ref` | VARCHAR(100) | sí |  |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |
| `raw_record_id` | VARCHAR(36) | sí | FK→`raw_records.raw_record_id` |
| `ingested_at` | DATETIME | no |  |

- CHECK `available_at >= published_at`
- INDEX ix_financial_statements_security_id (security_id)

### `sec_filings` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `accession_number` | VARCHAR(25) | no | PK |
| `cik` | VARCHAR(10) | no |  |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `form` | VARCHAR(20) | no |  |
| `is_amendment` | BOOLEAN | no |  |
| `filed_date` | DATE | no |  |
| `report_period` | DATE | sí |  |
| `accepted_at` | DATETIME | no |  |
| `submissions_acceptance_raw` | VARCHAR(40) | sí |  |
| `available_at` | DATETIME | no |  |
| `availability_policy` | VARCHAR(40) | no |  |
| `primary_document` | VARCHAR(300) | sí |  |
| `header_archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `xbrl_archive_id` | VARCHAR(36) | sí | FK→`raw_source_archive.archive_id` |
| `ingested_at` | DATETIME | no |  |

- CHECK `available_at >= accepted_at`
- INDEX ix_sec_filings_cik (cik)

### `cnmv_filings` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `filing_id` | VARCHAR(36) | no | PK |
| `nreg` | VARCHAR(20) | no |  |
| `doc_kind` | VARCHAR(30) | no |  |
| `cif` | VARCHAR(20) | no |  |
| `company` | VARCHAR(300) | no |  |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `issuer_id` | VARCHAR(36) | sí | FK→`issuers.issuer_id` |
| `period_start` | DATE | sí |  |
| `period_end` | DATE | no |  |
| `period_label` | VARCHAR(60) | sí |  |
| `publication_date` | DATE | no |  |
| `publication_time` | VARCHAR(8) | sí |  |
| `last_modification_date` | DATE | sí |  |
| `modifications` | JSON | no |  |
| `availability_precision` | VARCHAR(20) | no |  |
| `effective_available_at` | DATETIME | no |  |
| `availability_rule` | VARCHAR(80) | no |  |
| `source_url` | VARCHAR(500) | no |  |
| `detail_archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `data_archive_id` | VARCHAR(36) | sí | FK→`raw_source_archive.archive_id` |
| `data_sha256` | VARCHAR(64) | sí |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `availability_precision IN ('DATE_ONLY','DATETIME')`
- INDEX ix_cnmv_filings_issuer_id (issuer_id)
- INDEX ix_cnmv_filings_nreg (nreg)
- UNIQUE (nreg, data_sha256)

### `fundamental_facts` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `fact_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `issuer_id` | VARCHAR(36) | sí | FK→`issuers.issuer_id` |
| `taxonomy` | VARCHAR(30) | no |  |
| `concept` | VARCHAR(200) | no |  |
| `fiscal_period` | VARCHAR(10) | sí |  |
| `period_start` | DATE | sí |  |
| `period_end` | DATE | no |  |
| `value` | FLOAT | sí |  |
| `unit` | VARCHAR(30) | no |  |
| `currency` | VARCHAR(3) | sí |  |
| `available_at` | DATETIME | no |  |
| `revision_id` | INTEGER | no |  |
| `cik` | VARCHAR(10) | sí |  |
| `accession_number` | VARCHAR(25) | sí | FK→`sec_filings.accession_number` |
| `form` | VARCHAR(20) | sí |  |
| `filed_date` | DATE | sí |  |
| `accepted_at` | DATETIME | sí |  |
| `is_amendment` | BOOLEAN | no |  |
| `source_document` | VARCHAR(500) | sí |  |
| `statement_id` | VARCHAR(36) | sí | FK→`financial_statements.statement_id` |
| `cnmv_filing_id` | VARCHAR(36) | sí | FK→`cnmv_filings.filing_id` |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |
| `raw_record_id` | VARCHAR(36) | sí | FK→`raw_records.raw_record_id` |
| `ingested_at` | DATETIME | no |  |

- CHECK `accepted_at IS NULL OR available_at >= accepted_at`
- CHECK `security_id IS NOT NULL OR issuer_id IS NOT NULL`
- INDEX ix_fact_asof (security_id, concept, period_end, available_at)
- INDEX ix_fact_issuer_asof (issuer_id, concept, period_end, available_at)
- INDEX ix_fundamental_facts_accession_number (accession_number)
- INDEX ix_fundamental_facts_cnmv_filing_id (cnmv_filing_id)
- INDEX ix_fundamental_facts_issuer_id (issuer_id)
- UNIQUE (security_id, taxonomy, concept, unit, period_start, period_end, fiscal_period, revision_id, accession_number, source_id)

### `analyst_estimates`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `estimate_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `metric` | VARCHAR(30) | no |  |
| `target_period_end` | DATE | no |  |
| `statistic` | VARCHAR(20) | no |  |
| `value` | FLOAT | sí |  |
| `available_at` | DATETIME | no |  |
| `source_id` | INTEGER | no | FK→`data_sources.source_id` |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_estimate_asof (security_id, metric, target_period_end, available_at)

### `macro_data`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | INTEGER | no | PK |
| `series_code` | VARCHAR(50) | no |  |
| `observation_date` | DATE | no |  |
| `value` | FLOAT | sí |  |
| `available_at` | DATETIME | no |  |
| `source_id` | INTEGER | sí | FK→`data_sources.source_id` |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_macro_asof (series_code, observation_date, available_at)
- UNIQUE (series_code, observation_date, available_at)

## Features, modelos y predicciones

### `feature_snapshots` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `snapshot_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `as_of` | DATETIME | no |  |
| `feature_version` | VARCHAR(50) | no |  |
| `data_version` | VARCHAR(50) | no |  |
| `code_version` | VARCHAR(64) | no |  |
| `features` | JSON | no |  |
| `availability` | JSON | no |  |
| `missing_mask` | JSON | no |  |
| `imputed_mask` | JSON | no |  |
| `dq_warnings` | JSON | no |  |
| `max_available_at` | DATETIME | sí |  |
| `content_hash` | VARCHAR(64) | no |  |
| `is_synthetic` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `max_available_at IS NULL OR max_available_at <= as_of`
- INDEX ix_snapshot_lookup (security_id, as_of, feature_version, data_version)

### `models`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `model_id` | VARCHAR(50) | no | PK |
| `horizon` | VARCHAR(5) | no |  |
| `kind` | VARCHAR(20) | no |  |
| `role` | VARCHAR(20) | no |  |
| `description` | TEXT | sí |  |

### `model_versions`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `model_version` | VARCHAR(80) | no | PK |
| `model_id` | VARCHAR(50) | no | FK→`models.model_id` |
| `scoring_version` | VARCHAR(50) | no |  |
| `feature_version` | VARCHAR(50) | no |  |
| `code_version` | VARCHAR(64) | no |  |
| `config_hash` | VARCHAR(64) | no |  |
| `params` | JSON | no |  |
| `artifact_uri` | VARCHAR(500) | sí |  |
| `trained_until` | DATETIME | sí |  |
| `seed` | INTEGER | no |  |
| `frozen` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

### `predictions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `prediction_id` | VARCHAR(36) | no | PK |
| `snapshot_id` | VARCHAR(36) | no | FK→`feature_snapshots.snapshot_id` |
| `snapshot_hash` | VARCHAR(64) | no |  |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `as_of` | DATETIME | no |  |
| `execution_at` | DATETIME | no |  |
| `horizon` | VARCHAR(5) | no |  |
| `model_version` | VARCHAR(80) | no | FK→`model_versions.model_version` |
| `signal` | VARCHAR(4) | no |  |
| `probability` | FLOAT | sí |  |
| `expected_excess_return` | FLOAT | sí |  |
| `confidence` | FLOAT | sí |  |
| `scores` | JSON | no |  |
| `explanation` | JSON | no |  |
| `data_version` | VARCHAR(50) | no |  |
| `feature_version` | VARCHAR(50) | no |  |
| `scoring_version` | VARCHAR(50) | no |  |
| `config_hash` | VARCHAR(64) | no |  |
| `code_version` | VARCHAR(64) | no |  |
| `seed` | INTEGER | no |  |
| `supersedes_id` | VARCHAR(36) | sí | FK→`predictions.prediction_id` |
| `created_at` | DATETIME | no |  |

- CHECK `execution_at > as_of`
- CHECK `probability IS NULL OR (probability >= 0 AND probability <= 1)`
- CHECK `signal IN ('BUY','HOLD','SELL')`
- INDEX ix_prediction_lookup (security_id, as_of, horizon, model_version)

### `live_predictions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | VARCHAR(36) | no | PK |
| `prediction_id` | VARCHAR(36) | no | FK→`predictions.prediction_id` |
| `registered_at` | DATETIME | no |  |
| `evaluation_due_at` | DATETIME | no |  |

- CHECK `evaluation_due_at > registered_at`
- UNIQUE (prediction_id)

## Backtest e investigación

### `backtest_runs`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `run_id` | VARCHAR(36) | no | PK |
| `model_version` | VARCHAR(80) | no | FK→`model_versions.model_version` |
| `config` | JSON | no |  |
| `config_hash` | VARCHAR(64) | no |  |
| `universe_codes` | JSON | no |  |
| `start_date` | DATE | no |  |
| `end_date` | DATE | no |  |
| `frequency` | VARCHAR(20) | no |  |
| `overlapping` | BOOLEAN | no |  |
| `is_synthetic` | BOOLEAN | no |  |
| `touches_holdout` | BOOLEAN | no |  |
| `status` | VARCHAR(20) | no |  |
| `report` | JSON | sí |  |
| `created_at` | DATETIME | no |  |
| `finished_at` | DATETIME | sí |  |

### `backtest_observations` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | VARCHAR(36) | no | PK |
| `run_id` | VARCHAR(36) | no | FK→`backtest_runs.run_id` |
| `prediction_id` | VARCHAR(36) | no | FK→`predictions.prediction_id` |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `as_of` | DATETIME | no |  |
| `horizon` | VARCHAR(5) | no |  |
| `t_exec` | DATETIME | no |  |
| `label_end` | DATETIME | no |  |
| `label_available_at` | DATETIME | no |  |

- CHECK `label_available_at >= label_end`
- CHECK `label_end > t_exec`
- CHECK `t_exec > as_of`
- INDEX ix_backtest_observations_run_id (run_id)

### `realized_returns` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | VARCHAR(36) | no | PK |
| `prediction_id` | VARCHAR(36) | no | FK→`predictions.prediction_id` |
| `horizon` | VARCHAR(5) | no |  |
| `t_exec` | DATETIME | no |  |
| `label_end` | DATETIME | no |  |
| `label_available_at` | DATETIME | no |  |
| `stock_total_return` | FLOAT | no |  |
| `market_total_return` | FLOAT | no |  |
| `sector_total_return` | FLOAT | sí |  |
| `market_excess_return` | FLOAT | no |  |
| `sector_excess_return` | FLOAT | sí |  |
| `absolute_return` | FLOAT | no |  |
| `volatility` | FLOAT | sí |  |
| `downside_volatility` | FLOAT | sí |  |
| `max_drawdown` | FLOAT | sí |  |
| `max_adverse_excursion` | FLOAT | sí |  |
| `max_favorable_excursion` | FLOAT | sí |  |
| `delisted_during_horizon` | BOOLEAN | no |  |
| `return_currency` | VARCHAR(3) | no |  |
| `computed_at` | DATETIME | no |  |

- UNIQUE (prediction_id, horizon)

### `experiments`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `experiment_id` | VARCHAR(36) | no | PK |
| `name` | VARCHAR(200) | no |  |
| `hypothesis` | TEXT | no |  |
| `model_version` | VARCHAR(80) | sí | FK→`model_versions.model_version` |
| `baseline_model_version` | VARCHAR(80) | sí |  |
| `n_variants` | INTEGER | no |  |
| `period_start` | DATE | sí |  |
| `period_end` | DATE | sí |  |
| `metrics` | JSON | no |  |
| `created_at` | DATETIME | no |  |

### `error_analysis`

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | VARCHAR(36) | no | PK |
| `prediction_id` | VARCHAR(36) | no | FK→`predictions.prediction_id` |
| `category` | VARCHAR(40) | no |  |
| `details` | JSON | no |  |
| `hypothesis` | TEXT | sí |  |
| `created_at` | DATETIME | no |  |

### `holdout_access_log` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `id` | VARCHAR(36) | no | PK |
| `model_version` | VARCHAR(80) | no | FK→`model_versions.model_version` |
| `reason` | TEXT | no |  |
| `requested_by` | VARCHAR(100) | no |  |
| `accessed_at` | DATETIME | no |  |

### `holdout_evaluations` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `evaluation_id` | VARCHAR(36) | no | PK |
| `access_id` | VARCHAR(36) | no | FK→`holdout_access_log.id` |
| `model_version` | VARCHAR(80) | no | FK→`model_versions.model_version` |
| `holdout_start` | DATE | no |  |
| `holdout_end` | DATE | no |  |
| `metrics` | JSON | no |  |
| `n_observations` | INTEGER | no |  |
| `metrics_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (access_id)
