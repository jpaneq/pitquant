// Contract types mirroring the FastAPI DTOs (docs/PRODUCT_ANALYZER_STATUS.md). Rendering only: the
// frontend never computes finance.
export type Metric = { value: number | null; reason?: string; available_at?: string }
export type Label = { label: string; coverage?: string; reference_type?: string; note?: string; [k: string]: unknown }

export type SearchHit = {
  security_id: string
  ticker: string | null
  name: string
  exchange: string | null
  country: string | null
  asset_class: string
  status: string
  match_type: 'EXACT' | 'IDENTIFIER' | 'PREFIX' | 'NAME' | 'FUZZY'
  score: number
}
export type SearchResponse = { query: string; exact: boolean; needs_confirmation?: boolean; results: SearchHit[] }

export type Quote = {
  status: string
  as_of: string
  price?: number
  previous_close?: number | null
  change?: number | null
  change_pct?: number | null
  currency: string
  timestamp?: string | null
  session?: string
  kind?: string
  badge: 'REALTIME_REFERENCE' | 'DELAYED' | 'EOD' | 'STALE' | 'NO_DATA'
  freshness?: { status: string; sessions_behind: number | null; age_hours: number | null }
  market_status?: string
  source?: string | null
  source_note?: string | null
  market_cap?: number | null
  reason?: string
}

export type SecurityInfo = {
  security_id: string
  issuer_id: string | null
  ticker: string | null
  name: string
  exchange: string | null
  currency: string
  country: string | null
  sector: string | null
  industry: string | null
  sector_source: string | null
  profile_type: string
  asset_class: string
  identifiers: string[]
}

export type Summary = {
  as_of: string
  security: SecurityInfo
  quote: Quote
  availability: Record<string, string | number | string[]> & { analyzer_eligibility: string }
  summary: Record<string, string>
  summary_detail: Record<string, Label>
  positives: Reason[]
  risks: Reason[]
  warnings: string[]
  data_notice: { live_reference: string; required_env: string | null; mode: string }
  engine_versions: Record<string, string>
}
export type Reason = { reason_code: string; metric: string; value: number; reference: string; rendered_text: string }

export type Candle = { time: string; open: number; high: number; low: number; close: number; volume: number }
export type Point = { time: string; value: number }
export type ChartData = {
  status: string
  as_of: string
  range?: string
  n_bars?: number
  price_basis?: string
  currency?: string
  sources?: string[]
  candles: Candle[]
  overlays?: Record<string, Point[]>
  panes?: Record<string, Point[]>
  corporate_actions?: { kind: string; date: string; ratio: number | null; cash: number | null }[]
}

export type Zone = {
  kind: string
  lower: number
  upper: number
  midpoint: number
  touches: number
  first_touch: string
  last_touch: string
  strength: number
  distance_pct: number
  distance_atr: number
  reasons: string[]
}
export type Technicals = {
  status: string
  as_of: string
  engine_version: string
  last_session?: string
  n_bars?: number
  warnings: string[]
  trend?: { state: string; score: number; items_available: number; evidence: { code: string; text: string; available: boolean; positive?: boolean; metric?: number }[] }
  indicators?: Record<string, number | null>
  momentum?: Record<string, number | null>
  relative_strength?: Record<string, number | string | null>
  risk?: Record<string, number | null>
  volume?: Record<string, number | null>
  overextension?: Record<string, number | null>
  support_resistance?: { supports: Zone[]; resistances: Zone[] }
}

export type MetricGroup = Record<string, Metric | string | number | undefined>
export type Fundamentals = {
  status: string
  as_of: string
  engine_version: string
  latest_period?: string
  latest_filing_available_at?: string | null
  warnings: string[]
  coverage?: { available: number; expected: number }
  ttm?: MetricGroup
  profitability?: MetricGroup
  quality?: MetricGroup
  growth?: MetricGroup
  investment?: MetricGroup
  balance?: MetricGroup
  capital_allocation?: MetricGroup
}
export type HistoryPoint = { date: string; value: number; yoy: number | null }
export type FundamentalHistory = { status: string; period: string; series: Record<string, HistoryPoint[]> }

export type Valuation = {
  status: string
  as_of: string
  engine_version: string
  price?: number
  price_date?: string
  shares?: number | null
  market_cap?: number | null
  current?: Record<string, number | null>
  own_history?: Record<string, { percentile: number | null; median?: number; p10?: number; p90?: number; window_years?: number; sample_count: number; reason?: string }>
  peer_context?: { reference_type: string | null; sample_count: number; percentile: number | null; reason?: string }
  warnings: string[]
}

export type Setup = {
  type: string
  profile: string
  entry_zone: { lower: number; upper: number }
  entry: number
  invalidation_level: number
  stop: number
  risk_per_share: number
  stop_distance_pct: number
  stop_distance_atr: number
  structural_target: { price: number; potential_pct: number; r_multiple: number; label: string } | null
  r_targets: { r_multiple: number; price: number; potential_pct: number; label: string }[]
  confluence: string[]
  conditions: string[]
  warnings: string[]
}
export type TradePlan = {
  status: string
  as_of: string
  engine_version: string
  validation_status: string
  label: string
  reason?: string
  trend_context?: { state: string }
  setups: Setup[]
}
export type Analysis = {
  status: string
  labels: Record<string, Label>
  positives: Reason[]
  risks: Reason[]
  engine_version: string
  notes: string[]
}
export type Prediction = {
  model_status: string
  message: string
  horizons: Record<string, { expected_excess_return: number | null; p_outperform: number | null; quantiles: Record<string, number | null>; confidence: number | null; calibration_quality: number | null }>
}
export type Filing = { form: string; filed_date: string; accepted_at: string; report_period: string | null; accession: string; link: string | null }
export type Filings = { status: string; source: string; filings: Filing[] }
export type DataQuality = {
  overall: { label: string; warnings: string[] }
  panels: Record<string, Record<string, unknown>>
  corporate_actions: { kind: string; date: string; ratio: number | null; cash: number | null; tier: string }[]
  providers: { provider: string; env_var: string | null; configured: boolean; note?: string }[]
  benchmark: string | null
}
export type PositionSize = { status: string; reason?: string; shares?: number; notional?: number; risk_amount?: number; risk_per_share?: number; actual_risk?: number; notional_pct_of_capital?: number; capped_by_capital_no_leverage?: boolean }
