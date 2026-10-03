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
  timeline: { date: string; state: string; note: string }[]
}
export type SimRow = {
  simulation_id: string
  created_at: string
  security_id: string
  decision_at: string
  plan_origin: string
  mode: string
  state: string
  outcome: Outcome | null
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
export type SimDetail = {
  banner: string
  simulation: Record<string, unknown> & { simulation_id: string; stop_loss: number; target_1: number; target_2: number | null; entry_zone_low: number; entry_zone_high: number; invalidation_level: number | null; plan_origin: string; decision_at: string; prediction_status: string; support_resistance_snapshot: { supports?: { lower: number; upper: number }[]; resistances?: { lower: number; upper: number }[] }; original_pitquant_plan: Record<string, unknown> | null; final_simulated_plan: Record<string, unknown>; trade_plan_snapshot: { label?: string } }
  outcomes: Outcome[]
  observations: { observation_id: string; observed_at: string; kind: string; payload: { comparison?: Record<string, unknown> } }[]
  postmortems: { primary_cause: string; secondary_causes: string[]; classified_by: string; notes: string | null }[]
  bars: Bar[]
  analysis_now: Record<string, unknown>
}
