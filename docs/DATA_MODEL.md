# Modelo de datos

> Generado por `scripts/gen_data_model_doc.py` desde `pitquant.db.models`. No editar a mano.

Convenciones: `*_at` = instante UTC timezone-aware; `*_date` = fecha de calendario; intervalos semiabiertos `[from, to)`; 🔒 = tabla append-only (guard ORM + trigger PostgreSQL).

Tablas: **88**.

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
| `role` | VARCHAR(20) | no |  |
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

### `official_code_isin_evidence` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `evidence_id` | VARCHAR(36) | no | PK |
| `code` | VARCHAR(20) | no |  |
| `isin` | VARCHAR(12) | no |  |
| `observed_on` | DATE | no |  |
| `issuer_name` | VARCHAR(300) | no |  |
| `market` | VARCHAR(100) | sí |  |
| `source_kind` | VARCHAR(40) | no |  |
| `source_url` | VARCHAR(1000) | no |  |
| `capture_timestamp` | VARCHAR(20) | sí |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `source_sha256` | VARCHAR(64) | no |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_official_code_isin_evidence_code (code)
- INDEX ix_official_code_isin_evidence_isin (isin)
- UNIQUE (source_sha256, code, isin, observed_on)

### `official_isin_transitions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `transition_id` | VARCHAR(36) | no | PK |
| `issuer_name` | VARCHAR(300) | no |  |
| `old_isin` | VARCHAR(12) | no |  |
| `new_isin` | VARCHAR(12) | no |  |
| `kind` | VARCHAR(30) | no |  |
| `continuity` | VARCHAR(20) | no |  |
| `effective_date` | DATE | no |  |
| `documents` | JSON | no |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `continuity IN ('SAME_SECURITY','NEW_SECURITY')`
- CHECK `old_isin <> new_isin`
- INDEX ix_official_isin_transitions_new_isin (new_isin)
- INDEX ix_official_isin_transitions_old_isin (old_isin)
- UNIQUE (old_isin, new_isin, effective_date)

### `security_identifier_evidence` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `evidence_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `id_type` | VARCHAR(10) | no |  |
| `value` | VARCHAR(20) | no |  |
| `kind` | VARCHAR(12) | no |  |
| `observed_on` | DATE | no |  |
| `source_kind` | VARCHAR(40) | no |  |
| `source_url` | VARCHAR(1000) | no |  |
| `archive_id` | VARCHAR(36) | sí | FK→`raw_source_archive.archive_id` |
| `source_sha256` | VARCHAR(64) | sí |  |
| `excerpt` | VARCHAR(600) | sí |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `kind IN ('OFFICIAL','DERIVED','VENDOR','UNRESOLVED')`
- INDEX ix_security_identifier_evidence_security_id (security_id)
- UNIQUE (security_id, id_type, value, observed_on, source_url)

### `sp500_discovery_rows` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `row_id` | VARCHAR(36) | no | PK |
| `source` | VARCHAR(60) | no |  |
| `source_sha256` | VARCHAR(64) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `row_date` | DATE | no |  |
| `added_tickers` | JSON | no |  |
| `removed_tickers` | JSON | no |  |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_sp500_discovery_rows_row_date (row_date)

### `sp500_announcements` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `announcement_row_id` | VARCHAR(36) | no | PK |
| `source_tier` | VARCHAR(24) | no |  |
| `source_url` | VARCHAR(1000) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `source_sha256` | VARCHAR(64) | no |  |
| `announcement_at` | DATETIME | no |  |
| `stated_change_date` | DATE | sí |  |
| `timing` | VARCHAR(20) | no |  |
| `effective_at` | DATETIME | sí |  |
| `added_ticker` | VARCHAR(12) | no |  |
| `added_name` | VARCHAR(120) | no |  |
| `removed_ticker` | VARCHAR(12) | no |  |
| `removed_name` | VARCHAR(120) | no |  |
| `reason_class` | VARCHAR(30) | no |  |
| `excerpt` | VARCHAR(500) | no |  |
| `notes` | JSON | no |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_sp500_announcements_added_ticker (added_ticker)
- INDEX ix_sp500_announcements_removed_ticker (removed_ticker)
- UNIQUE (source_sha256, added_ticker, removed_ticker, parser_version)

### `sp500_membership_events` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `event_id` | VARCHAR(36) | no | PK |
| `run_id` | VARCHAR(36) | no |  |
| `discovery_row_id` | VARCHAR(36) | sí | FK→`sp500_discovery_rows.row_id` |
| `announcement_row_id` | VARCHAR(36) | sí | FK→`sp500_announcements.announcement_row_id` |
| `added_ticker` | VARCHAR(12) | sí |  |
| `added_security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `removed_ticker` | VARCHAR(12) | sí |  |
| `removed_security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `announcement_at` | DATETIME | sí |  |
| `stated_change_date` | DATE | sí |  |
| `timing` | VARCHAR(20) | sí |  |
| `effective_at` | DATETIME | sí |  |
| `discovery_date` | DATE | sí |  |
| `source_tier` | VARCHAR(24) | no |  |
| `source_url` | VARCHAR(1000) | sí |  |
| `raw_source_hash` | VARCHAR(64) | sí |  |
| `status` | VARCHAR(40) | no |  |
| `reason` | VARCHAR(300) | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `status IN ('OFFICIAL_CONFIRMED','OFFICIAL_REPUBLISHED_CONFIRMED','DISCOVERY_ONLY','DATE_TBA','CONFLICT','UNRESOLVED')`
- INDEX ix_sp500_membership_events_run_id (run_id)

### `sp500_anchors` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `anchor_id` | VARCHAR(36) | no | PK |
| `as_of_date` | DATE | no |  |
| `source_type` | VARCHAR(30) | no |  |
| `evidence_kind` | VARCHAR(50) | no |  |
| `evidence_tier` | VARCHAR(40) | no |  |
| `form` | VARCHAR(12) | no |  |
| `accession` | VARCHAR(20) | no |  |
| `filer_cik` | VARCHAR(10) | no |  |
| `source_available_at` | DATETIME | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `source_sha256` | VARCHAR(64) | no |  |
| `member_count` | INTEGER | no |  |
| `resolved_count` | INTEGER | no |  |
| `unresolved_count` | INTEGER | no |  |
| `excluded_count` | INTEGER | no |  |
| `status` | VARCHAR(20) | no |  |
| `notes` | JSON | no |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `source_available_at >= as_of_date`
- INDEX ix_sp500_anchors_as_of_date (as_of_date)
- UNIQUE (accession, parser_version)

### `sp500_anchor_members` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `member_id` | VARCHAR(36) | no | PK |
| `anchor_id` | VARCHAR(36) | no | FK→`sp500_anchors.anchor_id` |
| `security_id` | VARCHAR(36) | sí | FK→`securities.security_id` |
| `cusip` | VARCHAR(9) | sí |  |
| `isin` | VARCHAR(12) | sí |  |
| `ticker_as_reported` | VARCHAR(20) | sí |  |
| `issuer_name` | VARCHAR(300) | no |  |
| `title` | VARCHAR(300) | sí |  |
| `lei` | VARCHAR(20) | sí |  |
| `source_position` | INTEGER | no |  |
| `shares` | FLOAT | sí |  |
| `value_usd` | FLOAT | sí |  |
| `pct_net_assets` | FLOAT | sí |  |
| `classification` | VARCHAR(30) | no |  |
| `identity_basis` | VARCHAR(30) | no |  |
| `status` | VARCHAR(20) | no |  |

- CHECK `classification IN ('INDEX_EQUITY_CANDIDATE','NON_EQUITY','TRANSIENT_CORPORATE_ACTION','UNRESOLVED')`
- INDEX ix_sp500_anchor_members_anchor_id (anchor_id)
- INDEX ix_sp500_anchor_members_security_id (security_id)

### `sp500_anchor_crosschecks` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `check_id` | VARCHAR(36) | no | PK |
| `anchor_a_id` | VARCHAR(36) | no | FK→`sp500_anchors.anchor_id` |
| `anchor_b_id` | VARCHAR(36) | no | FK→`sp500_anchors.anchor_id` |
| `metrics` | JSON | no |  |
| `details` | JSON | no |  |
| `created_at` | DATETIME | no |  |

### `sp500_membership_segments` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `segment_id` | VARCHAR(36) | no | PK |
| `anchor_a_id` | VARCHAR(36) | no | FK→`sp500_anchors.anchor_id` |
| `anchor_b_id` | VARCHAR(36) | no | FK→`sp500_anchors.anchor_id` |
| `run_id` | VARCHAR(36) | sí |  |
| `engine_version` | VARCHAR(40) | no |  |
| `n_confirmed_events` | INTEGER | no |  |
| `n_delta_added` | INTEGER | no |  |
| `n_delta_removed` | INTEGER | no |  |
| `forward_ok` | BOOLEAN | no |  |
| `backward_ok` | BOOLEAN | no |  |
| `status` | VARCHAR(24) | no |  |
| `deltas` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `status IN ('VALIDATED','LOCAL_GAPS','IDENTITY_UNRESOLVED')`
- INDEX ix_sp500_membership_segments_anchor_a_id (anchor_a_id)
- INDEX ix_sp500_membership_segments_anchor_b_id (anchor_b_id)

### `security_ticker_alias` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `alias_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `ticker` | VARCHAR(20) | no |  |
| `valid_from` | DATE | sí |  |
| `valid_to` | DATE | sí |  |
| `bounds` | VARCHAR(10) | no |  |
| `source` | VARCHAR(60) | no |  |
| `source_hash` | VARCHAR(64) | sí |  |
| `confidence` | VARCHAR(12) | no |  |
| `note` | VARCHAR(300) | sí |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `bounds IN ('EXACT','PARTIAL')`
- CHECK `valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from`
- INDEX ix_security_ticker_alias_security_id (security_id)
- INDEX ix_security_ticker_alias_ticker (ticker)

### `sec_13f_list_entries` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `entry_id` | VARCHAR(36) | no | PK |
| `quarter` | VARCHAR(6) | no |  |
| `cusip` | VARCHAR(9) | no |  |
| `issuer_name` | VARCHAR(200) | no |  |
| `issuer_description` | VARCHAR(100) | no |  |
| `status_added_deleted` | VARCHAR(10) | sí |  |
| `raw_source_hash` | VARCHAR(64) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `parser_version` | VARCHAR(40) | no |  |
| `ingested_at` | DATETIME | no |  |

- INDEX ix_sec_13f_list_entries_cusip (cusip)
- INDEX ix_sec_13f_list_entries_quarter (quarter)

### `security_succession` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `succession_id` | VARCHAR(36) | no | PK |
| `security_predecessor_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `security_successor_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `effective_at` | DATETIME | sí |  |
| `event_type` | VARCHAR(64) | no |  |
| `exchange_ratio` | FLOAT | sí |  |
| `membership_continuity` | BOOLEAN | no |  |
| `source` | VARCHAR(80) | no |  |
| `source_hash` | VARCHAR(64) | sí |  |
| `note` | VARCHAR(400) | sí |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `event_type IN ('NAME_CHANGE_SAME_SECURITY','TICKER_CHANGE_SAME_SECURITY','NAME_TICKER_CHANGE_SAME_SECURITY','NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY','IDENTIFIER_CHANGE_SAME_SECURITY','SECURITY_REPLACEMENT_SUCCESSOR','SHARE_CLASS_CHANGE','TRUE_INDEX_EXIT','TRUE_INDEX_ENTRY','SAME_SECURITY_IDENTITY_LINK')`
- CHECK `security_predecessor_id != security_successor_id`
- INDEX ix_security_succession_security_predecessor_id (security_predecessor_id)
- INDEX ix_security_succession_security_successor_id (security_successor_id)

### `simulations` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `simulation_id` | VARCHAR(36) | no | PK |
| `created_at` | DATETIME | no |  |
| `mode` | VARCHAR(20) | no |  |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `asset_type` | VARCHAR(10) | no |  |
| `decision_at` | DATETIME | no |  |
| `analyzer_version` | VARCHAR(60) | no |  |
| `feature_version` | VARCHAR(40) | no |  |
| `model_id` | VARCHAR(64) | sí |  |
| `model_version` | VARCHAR(64) | sí |  |
| `rules_version` | VARCHAR(40) | no |  |
| `prediction_status` | VARCHAR(30) | no |  |
| `price_snapshot` | JSON | no |  |
| `fundamental_snapshot` | JSON | no |  |
| `technical_snapshot` | JSON | no |  |
| `valuation_snapshot` | JSON | no |  |
| `support_resistance_snapshot` | JSON | no |  |
| `trade_plan_snapshot` | JSON | no |  |
| `market_regime_snapshot` | JSON | no |  |
| `data_quality` | JSON | no |  |
| `funding_snapshot` | JSON | sí |  |
| `open_interest_snapshot` | JSON | sí |  |
| `basis_snapshot` | JSON | sí |  |
| `onchain_snapshot` | JSON | sí |  |
| `plan_origin` | VARCHAR(14) | no |  |
| `original_pitquant_plan` | JSON | sí |  |
| `final_simulated_plan` | JSON | no |  |
| `side` | VARCHAR(5) | no |  |
| `entry_type` | VARCHAR(20) | no |  |
| `entry_zone_low` | FLOAT | no |  |
| `entry_zone_high` | FLOAT | no |  |
| `entry_price_actual` | FLOAT | sí |  |
| `stop_loss` | FLOAT | no |  |
| `invalidation_level` | FLOAT | sí |  |
| `target_1` | FLOAT | no |  |
| `target_2` | FLOAT | sí |  |
| `target_3_optional` | FLOAT | sí |  |
| `risk_reward_expected` | FLOAT | sí |  |
| `position_size_simulated` | FLOAT | no |  |
| `capital_at_risk` | FLOAT | no |  |
| `time_horizon_sessions` | INTEGER | no |  |
| `expiration_at` | DATETIME | no |  |
| `benchmark_security_id` | VARCHAR(36) | sí |  |
| `snapshot_hash` | VARCHAR(64) | sí |  |
| `source_provenance` | JSON | sí |  |
| `simulation_engine_version` | VARCHAR(20) | no |  |
| `is_synthetic` | BOOLEAN | no |  |

- CHECK `asset_type IN ('EQUITY','BTC')`
- CHECK `created_at >= decision_at`
- CHECK `mode IN ('MANUAL_SIMULATION','AUTO_PAPER')`
- CHECK `plan_origin IN ('PITQUANT','USER_MODIFIED','USER_DEFINED')`
- INDEX ix_simulations_security_id (security_id)

### `simulation_observations` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `observation_id` | VARCHAR(36) | no | PK |
| `simulation_id` | VARCHAR(36) | no | FK→`simulations.simulation_id` |
| `observed_at` | DATETIME | no |  |
| `kind` | VARCHAR(20) | no |  |
| `payload` | JSON | no |  |
| `created_at` | DATETIME | no |  |
| `horizon_label` | VARCHAR(120) | sí |  |
| `source_bar_date` | DATE | sí |  |
| `observation_schema_version` | INTEGER | sí |  |
| `analyzer_version` | VARCHAR(60) | sí |  |
| `feature_version` | VARCHAR(40) | sí |  |

- INDEX ix_simulation_observations_simulation_id (simulation_id)
- UNIQUE (simulation_id, horizon_label)

### `simulation_outcomes` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `outcome_id` | VARCHAR(36) | no | PK |
| `simulation_id` | VARCHAR(36) | no | FK→`simulations.simulation_id` |
| `evaluated_at` | DATETIME | no |  |
| `state` | VARCHAR(20) | no |  |
| `is_closed` | BOOLEAN | no |  |
| `entry_date` | DATE | sí |  |
| `entry_price` | FLOAT | sí |  |
| `exit_date` | DATE | sí |  |
| `realized_return` | FLOAT | sí |  |
| `excess_return_vs_benchmark` | FLOAT | sí |  |
| `realized_r` | FLOAT | sí |  |
| `mfe` | FLOAT | sí |  |
| `mae` | FLOAT | sí |  |
| `max_drawdown` | FLOAT | sí |  |
| `days_to_entry` | INTEGER | sí |  |
| `days_to_stop` | INTEGER | sí |  |
| `days_to_tp1` | INTEGER | sí |  |
| `days_to_tp2` | INTEGER | sí |  |
| `holding_period` | INTEGER | sí |  |
| `prediction_direction_correct` | BOOLEAN | sí |  |
| `trade_plan_execution_correct` | BOOLEAN | sí |  |
| `timeline` | JSON | no |  |
| `details` | JSON | no |  |
| `created_at` | DATETIME | no |  |
| `prediction_outcome` | VARCHAR(30) | sí |  |
| `execution_outcome` | VARCHAR(30) | sí |  |
| `event_count` | INTEGER | sí |  |
| `engine_version` | VARCHAR(30) | sí |  |
| `bars_to_entry` | INTEGER | sí |  |

- INDEX ix_simulation_outcomes_simulation_id (simulation_id)

### `simulation_events` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `event_id` | VARCHAR(36) | no | PK |
| `simulation_id` | VARCHAR(36) | no | FK→`simulations.simulation_id` |
| `sequence_number` | INTEGER | no |  |
| `event_type` | VARCHAR(30) | no |  |
| `occurred_at` | DATE | no |  |
| `source_bar_timestamp` | DATE | sí |  |
| `payload_json` | JSON | no |  |
| `engine_version` | VARCHAR(30) | no |  |
| `event_schema_version` | INTEGER | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_simulation_events_simulation_id (simulation_id)
- UNIQUE (simulation_id, sequence_number)

### `simulation_counterfactuals` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `counterfactual_id` | VARCHAR(36) | no | PK |
| `simulation_id` | VARCHAR(36) | no | FK→`simulations.simulation_id` |
| `evaluated_at` | DATETIME | no |  |
| `plan_label` | VARCHAR(40) | no |  |
| `last_bar` | DATE | sí |  |
| `state` | VARCHAR(20) | no |  |
| `plan` | JSON | no |  |
| `metrics` | JSON | no |  |
| `details` | JSON | no |  |
| `timeline` | JSON | no |  |
| `label` | VARCHAR(20) | no |  |
| `simulation_engine_version` | VARCHAR(20) | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_simulation_counterfactuals_simulation_id (simulation_id)

### `simulation_postmortems` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `postmortem_id` | VARCHAR(36) | no | PK |
| `simulation_id` | VARCHAR(36) | no | FK→`simulations.simulation_id` |
| `primary_cause` | VARCHAR(40) | no |  |
| `secondary_causes` | JSON | no |  |
| `notes` | VARCHAR(2000) | sí |  |
| `classified_by` | VARCHAR(60) | no |  |
| `metrics` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_simulation_postmortems_simulation_id (simulation_id)

### `research_hypotheses` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `hypothesis_id` | VARCHAR(36) | no | PK |
| `source` | VARCHAR(30) | no |  |
| `statement` | VARCHAR(1000) | no |  |
| `evidence` | JSON | no |  |
| `status` | VARCHAR(20) | no |  |
| `created_by` | VARCHAR(60) | no |  |
| `created_at` | DATETIME | no |  |

### `prediction_snapshots` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `prediction_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `decision_at` | DATETIME | no |  |
| `generated_at` | DATETIME | no |  |
| `horizon_months` | INTEGER | no |  |
| `model_id` | VARCHAR(80) | no |  |
| `model_version` | VARCHAR(80) | no |  |
| `feature_set_version` | VARCHAR(80) | no |  |
| `dataset_version` | VARCHAR(80) | sí |  |
| `expected_excess_return` | FLOAT | sí |  |
| `p_outperform` | FLOAT | sí |  |
| `return_quantile_10` | FLOAT | sí |  |
| `return_quantile_25` | FLOAT | sí |  |
| `return_quantile_50` | FLOAT | sí |  |
| `return_quantile_75` | FLOAT | sí |  |
| `return_quantile_90` | FLOAT | sí |  |
| `uncertainty` | JSON | sí |  |
| `benchmark` | VARCHAR(60) | no |  |
| `data_quality` | JSON | no |  |
| `feature_contributions` | JSON | sí |  |
| `warnings` | JSON | no |  |
| `prediction_status` | VARCHAR(24) | no |  |
| `is_synthetic` | BOOLEAN | no |  |
| `data_available_at` | DATETIME | sí |  |
| `provenance` | JSON | no |  |
| `commit_sha` | VARCHAR(48) | sí |  |
| `created_at` | DATETIME | no |  |

- CHECK `(prediction_status = 'SYNTHETIC_FIXTURE') = is_synthetic`
- CHECK `data_available_at IS NULL OR data_available_at <= decision_at`
- CHECK `decision_at <= generated_at`
- CHECK `horizon_months IN (6, 12)`
- CHECK `p_outperform IS NULL OR (p_outperform >= 0 AND p_outperform <= 1)`
- CHECK `prediction_status <> 'NOT_YET_VALIDATED' OR (expected_excess_return IS NULL AND p_outperform IS NULL AND return_quantile_10 IS NULL AND return_quantile_25 IS NULL AND return_quantile_50 IS NULL AND return_quantile_75 IS NULL AND return_quantile_90 IS NULL AND uncertainty IS NULL AND feature_contributions IS NULL)`
- CHECK `prediction_status IN ('NOT_YET_VALIDATED','SYNTHETIC_FIXTURE')`
- INDEX ix_prediction_snapshot_lookup (security_id, decision_at, horizon_months)
- INDEX ix_prediction_snapshots_security_id (security_id)

### `prediction_outcomes` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `outcome_row_id` | VARCHAR(36) | no | PK |
| `prediction_id` | VARCHAR(36) | no | FK→`prediction_snapshots.prediction_id` |
| `realized_outcome_id` | VARCHAR(36) | sí | FK→`realized_outcomes.outcome_id` |
| `source` | VARCHAR(24) | no |  |
| `resolved_at` | DATETIME | no |  |
| `actual_return` | FLOAT | sí |  |
| `benchmark_return` | FLOAT | sí |  |
| `actual_excess_return` | FLOAT | sí |  |
| `actual_outperform` | BOOLEAN | sí |  |
| `predicted_excess_return` | FLOAT | sí |  |
| `prediction_error` | FLOAT | sí |  |
| `predicted_outperform` | BOOLEAN | sí |  |
| `classification_correct` | BOOLEAN | sí |  |
| `direction_correct` | BOOLEAN | sí |  |
| `is_synthetic` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_prediction_outcomes_prediction_id (prediction_id)

### `strategy_definitions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `strategy_row_id` | VARCHAR(36) | no | PK |
| `strategy_id` | VARCHAR(80) | no |  |
| `strategy_version` | INTEGER | no |  |
| `family` | VARCHAR(20) | no |  |
| `name` | VARCHAR(120) | no |  |
| `prediction_horizon_months` | INTEGER | sí |  |
| `prediction_model_requirement` | JSON | no |  |
| `entry_rules` | JSON | no |  |
| `exit_rules` | JSON | no |  |
| `risk_rules` | JSON | no |  |
| `trade_plan_rules` | JSON | no |  |
| `rebalance_frequency` | VARCHAR(20) | no |  |
| `max_positions` | INTEGER | no |  |
| `position_sizing` | JSON | no |  |
| `costs` | JSON | no |  |
| `status` | VARCHAR(28) | no |  |
| `parent_version` | INTEGER | sí |  |
| `spec_hash` | VARCHAR(64) | no |  |
| `created_by` | VARCHAR(60) | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `family IN ('TRADE_PLAN_ONLY','PREDICTION_ONLY','HYBRID','BUY_AND_HOLD')`
- CHECK `max_positions >= 1`
- INDEX ix_strategy_definitions_strategy_id (strategy_id)
- UNIQUE (strategy_id, strategy_version)

### `strategy_runs` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `run_id` | VARCHAR(36) | no | PK |
| `run_kind` | VARCHAR(14) | no |  |
| `strategy_row_id` | VARCHAR(36) | no | FK→`strategy_definitions.strategy_row_id` |
| `strategy_id` | VARCHAR(80) | no |  |
| `strategy_version` | INTEGER | no |  |
| `universe` | JSON | no |  |
| `activated_at` | DATETIME | sí |  |
| `dataset_version` | VARCHAR(80) | sí |  |
| `model_id` | VARCHAR(80) | sí |  |
| `model_version` | VARCHAR(80) | sí |  |
| `simulation_engine_version` | VARCHAR(20) | no |  |
| `commit_sha` | VARCHAR(48) | no |  |
| `readiness` | JSON | no |  |
| `blocked_reasons` | JSON | no |  |
| `params` | JSON | no |  |
| `is_synthetic` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `run_kind IN ('HISTORICAL','FORWARD_PAPER','SYNTHETIC')`
- INDEX ix_strategy_runs_strategy_row_id (strategy_row_id)

### `strategy_run_events` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `event_id` | VARCHAR(36) | no | PK |
| `run_id` | VARCHAR(36) | no | FK→`strategy_runs.run_id` |
| `event_type` | VARCHAR(20) | no |  |
| `occurred_at` | DATETIME | no |  |
| `payload` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_strategy_run_events_run_id (run_id)

### `strategy_decisions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `decision_id` | VARCHAR(36) | no | PK |
| `run_id` | VARCHAR(36) | no | FK→`strategy_runs.run_id` |
| `strategy_id` | VARCHAR(80) | no |  |
| `strategy_version` | INTEGER | no |  |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `decision_at` | DATETIME | no |  |
| `prediction_snapshot_id` | VARCHAR(36) | sí | FK→`prediction_snapshots.prediction_id` |
| `trade_plan_snapshot` | JSON | sí |  |
| `trade_plan_hash` | VARCHAR(64) | sí |  |
| `rule_inputs` | JSON | no |  |
| `rules_evaluated` | JSON | no |  |
| `rules_passed` | JSON | no |  |
| `rules_failed` | JSON | no |  |
| `decision` | VARCHAR(10) | no |  |
| `exit_reason` | VARCHAR(30) | sí |  |
| `is_synthetic` | BOOLEAN | no |  |
| `created_at` | DATETIME | no |  |

- CHECK `decision IN ('ENTER','HOLD','EXIT','NO_ACTION')`
- INDEX ix_strategy_decisions_run_id (run_id)
- INDEX ix_strategy_decisions_security_id (security_id)

### `strategy_simulation_links` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `link_id` | VARCHAR(36) | no | PK |
| `decision_id` | VARCHAR(36) | no | FK→`strategy_decisions.decision_id` |
| `simulation_id` | VARCHAR(36) | no | FK→`simulations.simulation_id` |
| `role` | VARCHAR(8) | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_strategy_simulation_links_decision_id (decision_id)
- INDEX ix_strategy_simulation_links_simulation_id (simulation_id)

### `strategy_run_results` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `result_id` | VARCHAR(36) | no | PK |
| `run_id` | VARCHAR(36) | no | FK→`strategy_runs.run_id` |
| `evaluated_at` | DATETIME | no |  |
| `prediction_series_hash` | VARCHAR(64) | no |  |
| `metrics` | JSON | no |  |
| `flags` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_strategy_run_results_run_id (run_id)

### `index_anchor_snapshots` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `snapshot_id` | VARCHAR(36) | no | PK |
| `source` | VARCHAR(10) | no |  |
| `as_of` | DATE | no |  |
| `source_url` | VARCHAR(1000) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `source_sha256` | VARCHAR(64) | no |  |
| `key_level` | VARCHAR(12) | no |  |
| `holdings` | JSON | no |  |
| `excluded` | JSON | no |  |
| `parser_version` | VARCHAR(50) | no |  |
| `ingested_at` | DATETIME | no |  |

### `index_current_anchors` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `anchor_id` | VARCHAR(36) | no | PK |
| `index_code` | VARCHAR(20) | no |  |
| `as_of` | DATE | sí |  |
| `status` | VARCHAR(30) | no |  |
| `key_level` | VARCHAR(12) | no |  |
| `members` | JSON | no |  |
| `spy_snapshot_id` | VARCHAR(36) | sí | FK→`index_anchor_snapshots.snapshot_id` |
| `ivv_snapshot_id` | VARCHAR(36) | sí | FK→`index_anchor_snapshots.snapshot_id` |
| `reconciled` | INTEGER | no |  |
| `applied_events` | JSON | no |  |
| `differences` | JSON | no |  |
| `notes` | JSON | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `status IN ('OFFICIAL_SPDJI','MULTI_SOURCE_CONFIRMED','CONFLICT','BLOCKED')`

### `security_profiles` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `profile_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `current_ticker` | VARCHAR(20) | sí |  |
| `display_name` | VARCHAR(300) | no |  |
| `exchange` | VARCHAR(40) | sí |  |
| `country` | VARCHAR(2) | sí |  |
| `sic` | VARCHAR(8) | sí |  |
| `sic_description` | VARCHAR(200) | sí |  |
| `sector` | VARCHAR(100) | sí |  |
| `industry` | VARCHAR(200) | sí |  |
| `profile_type` | VARCHAR(24) | no |  |
| `source` | VARCHAR(40) | no |  |
| `source_url` | VARCHAR(1000) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `source_sha256` | VARCHAR(64) | no |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `profile_type IN ('STANDARD_CORPORATE','BANK','INSURER','REIT','OTHER_SPECIAL')`
- INDEX ix_security_profiles_current_ticker (current_ticker)
- INDEX ix_security_profiles_security_id (security_id)

### `feature_set_versions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `feature_set_version_id` | VARCHAR(36) | no | PK |
| `name` | VARCHAR(60) | no |  |
| `feature_version` | VARCHAR(50) | no |  |
| `tag_map_version` | VARCHAR(50) | no |  |
| `features` | JSON | no |  |
| `set_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (set_hash)

### `label_definitions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `label_definition_id` | VARCHAR(36) | no | PK |
| `label_version` | VARCHAR(50) | no |  |
| `horizon_months` | INTEGER | no |  |
| `target_kind` | VARCHAR(40) | no |  |
| `benchmark` | VARCHAR(60) | no |  |
| `benchmark_type` | VARCHAR(20) | no |  |
| `definition` | JSON | no |  |
| `definition_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (definition_hash)

### `model_configs` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `model_config_id` | VARCHAR(36) | no | PK |
| `kind` | VARCHAR(30) | no |  |
| `name` | VARCHAR(80) | no |  |
| `params` | JSON | no |  |
| `grid` | JSON | no |  |
| `config_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (config_hash)

### `dataset_versions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `dataset_version_id` | VARCHAR(36) | no | PK |
| `dataset_hash` | VARCHAR(64) | no |  |
| `universe` | VARCHAR(120) | no |  |
| `universe_version` | VARCHAR(120) | no |  |
| `start_date` | DATE | no |  |
| `end_date` | DATE | no |  |
| `snapshot_frequency` | VARCHAR(20) | no |  |
| `feature_set_version_id` | VARCHAR(36) | no | FK→`feature_set_versions.feature_set_version_id` |
| `label_definition_id` | VARCHAR(36) | no | FK→`label_definitions.label_definition_id` |
| `benchmark` | VARCHAR(60) | no |  |
| `n_rows` | INTEGER | no |  |
| `n_eligible` | INTEGER | no |  |
| `n_securities` | INTEGER | no |  |
| `holdout_dates_excluded` | INTEGER | no |  |
| `builder_version` | VARCHAR(40) | no |  |
| `rows_path` | VARCHAR(500) | sí |  |
| `summary` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (dataset_hash)

### `research_experiments` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `experiment_id` | VARCHAR(36) | no | PK |
| `name` | VARCHAR(120) | no |  |
| `status` | VARCHAR(20) | no |  |
| `commit_sha` | VARCHAR(40) | no |  |
| `dataset_version_id` | VARCHAR(36) | sí | FK→`dataset_versions.dataset_version_id` |
| `dataset_hash` | VARCHAR(64) | sí |  |
| `feature_set_version_id` | VARCHAR(36) | no | FK→`feature_set_versions.feature_set_version_id` |
| `label_definition_id` | VARCHAR(36) | no | FK→`label_definitions.label_definition_id` |
| `model_config_id` | VARCHAR(36) | no | FK→`model_configs.model_config_id` |
| `universe_version` | VARCHAR(120) | no |  |
| `benchmark_version` | VARCHAR(80) | no |  |
| `train_start` | DATE | sí |  |
| `train_end` | DATE | sí |  |
| `validation_start` | DATE | sí |  |
| `validation_end` | DATE | sí |  |
| `purge_months` | INTEGER | no |  |
| `embargo_months` | INTEGER | no |  |
| `window_kind` | VARCHAR(12) | no |  |
| `seed` | INTEGER | no |  |
| `library_versions` | JSON | no |  |
| `spec` | JSON | no |  |
| `spec_hash` | VARCHAR(64) | no |  |
| `blocked_reasons` | JSON | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (spec_hash)

### `research_folds` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `fold_id` | VARCHAR(36) | no | PK |
| `experiment_id` | VARCHAR(36) | no | FK→`research_experiments.experiment_id` |
| `fold_index` | INTEGER | no |  |
| `train_start` | DATE | no |  |
| `train_end` | DATE | no |  |
| `validation_start` | DATE | no |  |
| `validation_end` | DATE | no |  |
| `n_train` | INTEGER | sí |  |
| `n_validation` | INTEGER | sí |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_research_folds_experiment_id (experiment_id)

### `research_predictions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `research_prediction_id` | VARCHAR(36) | no | PK |
| `experiment_id` | VARCHAR(36) | no | FK→`research_experiments.experiment_id` |
| `fold_id` | VARCHAR(36) | sí | FK→`research_folds.fold_id` |
| `model_id` | VARCHAR(80) | no |  |
| `model_version` | VARCHAR(80) | no |  |
| `generated_at` | DATETIME | no |  |
| `decision_at` | DATETIME | no |  |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `feature_snapshot_id` | VARCHAR(36) | no | FK→`feature_snapshots.snapshot_id` |
| `expected_excess_return` | FLOAT | sí |  |
| `probability` | FLOAT | sí |  |
| `uncertainty` | JSON | no |  |
| `calibration_version` | VARCHAR(80) | sí |  |
| `created_at` | DATETIME | no |  |

- CHECK `decision_at <= generated_at`
- INDEX ix_research_predictions_experiment_id (experiment_id)

### `realized_outcomes` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `outcome_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `decision_at` | DATETIME | no |  |
| `horizon_months` | INTEGER | no |  |
| `label_version` | VARCHAR(50) | no |  |
| `security_total_return` | FLOAT | sí |  |
| `benchmark_total_return` | FLOAT | sí |  |
| `excess_total_return` | FLOAT | sí |  |
| `outperform` | BOOLEAN | sí |  |
| `label_available_at` | DATETIME | no |  |
| `status` | VARCHAR(20) | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_realized_outcomes_security_id (security_id)

### `metric_sets` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `metric_set_id` | VARCHAR(36) | no | PK |
| `experiment_id` | VARCHAR(36) | no | FK→`research_experiments.experiment_id` |
| `fold_id` | VARCHAR(36) | sí | FK→`research_folds.fold_id` |
| `kind` | VARCHAR(20) | no |  |
| `metrics` | JSON | no |  |
| `computed_at` | DATETIME | no |  |

- INDEX ix_metric_sets_experiment_id (experiment_id)

### `champion_challenger_comparisons` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `comparison_id` | VARCHAR(36) | no | PK |
| `champion_experiment_id` | VARCHAR(36) | sí | FK→`research_experiments.experiment_id` |
| `challenger_experiment_id` | VARCHAR(36) | no | FK→`research_experiments.experiment_id` |
| `metrics` | JSON | no |  |
| `decision` | VARCHAR(20) | no |  |
| `reviewer` | VARCHAR(120) | sí |  |
| `created_at` | DATETIME | no |  |

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

## Bitcoin PIT V0 (branch independiente)

### `btc_data` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `datum_id` | VARCHAR(36) | no | PK |
| `source` | VARCHAR(40) | no |  |
| `metric` | VARCHAR(60) | no |  |
| `cohort` | VARCHAR(20) | no |  |
| `exchange_timestamp` | DATETIME | no |  |
| `available_at` | DATETIME | no |  |
| `retrieved_at` | DATETIME | no |  |
| `payload` | JSON | no |  |
| `raw_hash` | VARCHAR(64) | no |  |
| `archive_id` | VARCHAR(36) | no | FK→`raw_source_archive.archive_id` |
| `value_hash` | VARCHAR(64) | no |  |

- INDEX ix_btc_data_available_at (available_at)
- INDEX ix_btc_data_exchange_timestamp (exchange_timestamp)
- INDEX ix_btc_data_metric (metric)
- INDEX ix_btc_data_source (source)
- UNIQUE (source, metric, cohort, exchange_timestamp, value_hash, retrieved_at)

### `btc_feature_snapshots` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `snapshot_id` | VARCHAR(36) | no | PK |
| `decision_at` | DATETIME | no |  |
| `cohort` | VARCHAR(20) | no |  |
| `feature_version` | VARCHAR(40) | no |  |
| `data_version` | VARCHAR(40) | no |  |
| `model_version` | VARCHAR(60) | sí |  |
| `strategy_version` | VARCHAR(40) | no |  |
| `simulation_engine_version` | VARCHAR(20) | no |  |
| `commit_sha` | VARCHAR(40) | no |  |
| `payload` | JSON | no |  |
| `snapshot_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_btc_feature_snapshots_decision_at (decision_at)
- UNIQUE (decision_at, cohort, feature_version)
- UNIQUE (snapshot_hash)

### `btc_prediction_snapshots` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `prediction_id` | VARCHAR(36) | no | PK |
| `snapshot_id` | VARCHAR(36) | no | FK→`btc_feature_snapshots.snapshot_id` |
| `horizon` | INTEGER | no |  |
| `payload` | JSON | no |  |
| `prediction_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- UNIQUE (prediction_hash)
- UNIQUE (snapshot_id, horizon)

### `btc_research_records` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `record_id` | VARCHAR(36) | no | PK |
| `kind` | VARCHAR(30) | no |  |
| `cohort` | VARCHAR(20) | no |  |
| `prediction_id` | VARCHAR(36) | sí | FK→`btc_prediction_snapshots.prediction_id` |
| `payload` | JSON | no |  |
| `record_hash` | VARCHAR(64) | no |  |
| `created_at` | DATETIME | no |  |

- INDEX ix_btc_research_records_kind (kind)
- UNIQUE (record_hash)

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

### `corporate_action_ingestions` 🔒

| Columna | Tipo | Nulo | Clave |
|---|---|---|---|
| `ingestion_id` | VARCHAR(36) | no | PK |
| `security_id` | VARCHAR(36) | no | FK→`securities.security_id` |
| `provider` | VARCHAR(50) | no |  |
| `period_start` | DATE | no |  |
| `period_end` | DATE | no |  |
| `status` | VARCHAR(12) | no |  |
| `events_found` | INTEGER | no |  |
| `source_hash` | VARCHAR(64) | sí |  |
| `detail` | VARCHAR(300) | sí |  |
| `ingested_at` | DATETIME | no |  |

- CHECK `period_end >= period_start`
- CHECK `status IN ('COMPLETED','FAILED')`
- INDEX ix_corporate_action_ingestions_security_id (security_id)

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
| `issuer_id` | VARCHAR(36) | sí | FK→`issuers.issuer_id` |
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
- INDEX ix_sec_filings_issuer_id (issuer_id)

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
