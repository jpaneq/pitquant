import type { PlanView, SimEvent } from '../../lib/simulation'

export type Outcome = {
  outcome_id: string
  evaluated_at: string
  state: string
  is_closed: boolean
  entry_date: string | null
  entry_price: number | null
  exit_date: string | null
  realized_return: number | null
  excess_return_vs_benchmark: number | null
  realized_r: number | null
  mfe: number | null
  mae: number | null
  max_drawdown: number | null
  days_to_entry: number | null
  days_to_stop: number | null
  days_to_tp1: number | null
  days_to_tp2: number | null
  holding_period: number | null
  prediction_direction_correct: boolean | null
  trade_plan_execution_correct: boolean | null
  prediction_outcome?: string | null
  execution_outcome?: string | null
  timeline: { date: string; state: string; note: string }[]
  details?: { return_basis?: string; metrics_extra?: Record<string, number | null>; targets_touched?: number[]; position_remaining?: number | null; ambiguity?: { kind: string; scenarios: { order: string; realized_r: number }[] }; exit_policy?: string; fills?: { entry: { price: number; method: string } } }
}
export type SimRow = {
  simulation_id: string
  created_at: string
  security_id: string
  security?: string
  decision_at: string
  plan_origin: string
  mode: string
  setup_type?: string
  state: string
  outcome: Outcome | null
  mae_pct?: number | null
  mfe_pct?: number | null
  mae_r?: number | null
  mfe_r?: number | null
  exit_policy?: string
  entry_zone: [number, number]
  stop_loss: number
  target_1: number
  target_2: number | null
  banner: string
}
export type Evidence = {
  n_simulations: number
  n_closed: number
  n_entered_closed: number
  by_state: Record<string, number>
  stats_available: boolean
  hit_rate: number | null
  mean_r: number | null
  mean_return: number | null
  mean_excess_return: number | null
  mean_mae: number | null
  mean_mfe: number | null
  min_n: number
  note: string
}
export type SimSummary = { banner: string; groups: Record<string, number>; evidence: Evidence }
export type Bar = { date: string; open: number; high: number; low: number; close: number }
export type Comparison = {
  plan_origin: string
  pitquant_original: PlanView
  user_plan: PlanView
  real: { state: string; triggered: boolean; entry_price: number | null; realized_r: number | null; mae_pct: number | null; mfe_pct: number | null; targets_touched: number[] | null; label: string } | null
  counterfactual: { state: string; triggered: boolean; entry_price: number | null; realized_r: number | null; mae_pct: number | null; mfe_pct: number | null; targets_touched: number[] | null; last_bar: string; label: string } | null
}
export type Explain = { snapshot_hash: string | null; snapshot_verified: boolean; provenance: Record<string, unknown>; versions: Record<string, string | null>; exit_policy: string; events: number; banner: string }
export type SimDetail = {
  banner: string
  simulation: Record<string, unknown> & {
    simulation_id: string
    stop_loss: number
    target_1: number
    target_2: number | null
    target_3_optional: number | null
    entry_zone_low: number
    entry_zone_high: number
    invalidation_level: number | null
    plan_origin: string
    decision_at: string
    created_at: string
    entry_type: string
    prediction_status: string
    rules_version: string
    analyzer_version: string
    feature_version: string
    support_resistance_snapshot: { supports?: { lower: number; upper: number }[]; resistances?: { lower: number; upper: number }[] }
    original_pitquant_plan: Record<string, unknown> | null
    final_simulated_plan: Record<string, unknown>
    trade_plan_snapshot: { label?: string }
    price_snapshot: Record<string, unknown>
    fundamental_snapshot: Record<string, unknown>
    technical_snapshot: Record<string, unknown>
    valuation_snapshot: Record<string, unknown>
    data_quality: Record<string, unknown>
    snapshot_hash?: string | null
  }
  outcomes: Outcome[]
  observations: { observation_id: string; observed_at: string; kind: string; payload: { comparison?: Record<string, unknown> } }[]
  postmortems: { primary_cause: string; secondary_causes: string[]; classified_by: string; notes: string | null }[]
  bars: Bar[]
  analysis_now: Record<string, unknown>
  current?: Record<string, unknown>
  events: SimEvent[]
  comparison: Comparison
  explain: Explain
  plan_levels: { exit_policy: string; risk_reward: Record<string, number> | null; sizing: Record<string, unknown> | null }
}
export type PostMortemFacts = {
  facts: { prediction_outcome: string | null; prediction_status: string; execution_outcome: string | null; state: string; entry_quality: Record<string, unknown>; stop_quality: Record<string, unknown>; target_quality: Record<string, unknown>; metrics: Record<string, number | null>; diagnostic_flags: { flag: string; definition: string }[]; note: string }
  classifications: { primary_cause: string; secondary_causes: string[]; classified_by: string; notes: string | null }[]
}
export type InsightRow = { segment: string; n: number; n_entered: number; sample: 'OK' | 'INSUFFICIENT_SAMPLE'; return?: { mean: number | null; median: number | null }; r?: { mean: number | null; median: number | null }; mae_pct?: { mean: number | null; median: number | null }; mfe_pct?: { mean: number | null; median: number | null }; stop_rate?: number; target_touch_rate?: number; expiration_rate?: number; ambiguous_rate?: number }
export type Insights = { by: string; segments: InsightRow[]; min_n: number; note: string; available_segmentations: string[] }
