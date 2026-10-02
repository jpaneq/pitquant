import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './client'
import type {
  Analysis, ChartData, DataQuality, Filings, FundamentalHistory, Fundamentals, Prediction, PositionSize,
  SearchResponse, Summary, Technicals, TradePlan, Valuation,
} from './types'

// Stable query keys: ['analyzer', security, panel, ...params]. Separate queries per panel so a failing
// panel never blanks the page. Cadences follow the product spec (quote while the market is open is polled
// by the header; everything else is slow-moving).
const MIN = 60_000
const HOUR = 60 * MIN
export const qk = {
  search: (q: string) => ['search', q] as const,
  panel: (sec: string, panel: string, ...p: unknown[]) => ['analyzer', sec, panel, ...p] as const,
}

export const useSearch = (q: string) =>
  useQuery({ queryKey: qk.search(q), queryFn: ({ signal }) => api<SearchResponse>(`/search?q=${encodeURIComponent(q)}`, signal), enabled: q.trim().length >= 1, staleTime: 5 * MIN, placeholderData: keepPreviousData })

export const useSummary = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'summary'), queryFn: ({ signal }) => api<Summary>(`/analyzer/${sec}/summary`, signal), staleTime: 5 * MIN, retry: (n, e) => (e as { status?: number }).status !== 404 && n < 1 })

export const useQuote = (sec: string, open: boolean) =>
  useQuery({ queryKey: qk.panel(sec, 'quote'), queryFn: ({ signal }) => api<Summary['quote']>(`/analyzer/${sec}/quote`, signal), refetchInterval: open ? 45_000 : false, staleTime: open ? 30_000 : 5 * MIN })

export const useChart = (sec: string, range: string) =>
  useQuery({ queryKey: qk.panel(sec, 'chart', range), queryFn: ({ signal }) => api<ChartData>(`/analyzer/${sec}/chart?range=${range}`, signal), staleTime: 5 * MIN, placeholderData: keepPreviousData })

export const useTechnicals = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'technicals'), queryFn: ({ signal }) => api<Technicals>(`/analyzer/${sec}/technicals`, signal), staleTime: 5 * MIN })

export const useFundamentals = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'fundamentals'), queryFn: ({ signal }) => api<Fundamentals>(`/analyzer/${sec}/fundamentals`, signal), staleTime: 6 * HOUR })

export const useFundamentalHistory = (sec: string, period: string) =>
  useQuery({ queryKey: qk.panel(sec, 'fhistory', period), queryFn: ({ signal }) => api<FundamentalHistory>(`/analyzer/${sec}/fundamental-history?period=${period}`, signal), staleTime: 6 * HOUR })

export const useValuation = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'valuation'), queryFn: ({ signal }) => api<Valuation>(`/analyzer/${sec}/valuation`, signal), staleTime: 6 * HOUR })

export const useAnalysis = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'analysis'), queryFn: ({ signal }) => api<Analysis>(`/analyzer/${sec}/analysis`, signal), staleTime: 5 * MIN })

export const useTradePlan = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'trade-plan'), queryFn: ({ signal }) => api<TradePlan>(`/analyzer/${sec}/trade-plan`, signal), staleTime: 5 * MIN })

export const usePrediction = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'prediction'), queryFn: ({ signal }) => api<Prediction>(`/analyzer/${sec}/prediction`, signal), staleTime: HOUR })

export const useFilings = (sec: string) =>
  useQuery({ queryKey: qk.panel(sec, 'filings'), queryFn: ({ signal }) => api<Filings>(`/analyzer/${sec}/filings`, signal), staleTime: 6 * HOUR })

export const useDataQuality = (sec: string, enabled: boolean) =>
  useQuery({ queryKey: qk.panel(sec, 'data-quality'), queryFn: ({ signal }) => api<DataQuality>(`/analyzer/${sec}/data-quality`, signal), enabled, staleTime: 5 * MIN })

export const usePositionSize = (sec: string, p: { capital: number; risk: number; entry: number; stop: number } | null) =>
  useQuery({ queryKey: qk.panel(sec, 'position-size', p), queryFn: ({ signal }) => api<PositionSize>(`/analyzer/${sec}/position-size?capital=${p!.capital}&risk_pct=${p!.risk}&entry=${p!.entry}&stop=${p!.stop}`, signal), enabled: p !== null })
