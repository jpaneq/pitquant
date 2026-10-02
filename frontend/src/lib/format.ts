// Pure UI transforms only (units/rounding for display). Calculations live in the backend.
export function fmtNum(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  return x.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
export function fmtPct(x: number | null | undefined, digits = 1, signed = false): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  const s = (x * 100).toFixed(digits) + '%'
  return signed && x > 0 ? '+' + s : s
}
export function fmtCompact(x: number | null | undefined, currency = ''): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  const a = Math.abs(x)
  const sign = x < 0 ? '-' : ''
  const c = currency ? currency : ''
  if (a >= 1e12) return `${sign}${c}${(a / 1e12).toFixed(2)}T`
  if (a >= 1e9) return `${sign}${c}${(a / 1e9).toFixed(2)}B`
  if (a >= 1e6) return `${sign}${c}${(a / 1e6).toFixed(1)}M`
  if (a >= 1e3) return `${sign}${c}${(a / 1e3).toFixed(1)}K`
  return `${sign}${c}${a.toFixed(2)}`
}
export function fmtMoney(x: number | null | undefined, currency = 'USD'): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  return x.toLocaleString('en-US', { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
export function fmtMult(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  return `${x.toFixed(digits)}×`
}
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.slice(0, 10)
}
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'
}
export function signClass(x: number | null | undefined): string {
  if (x === null || x === undefined || x === 0) return 'text-muted'
  return x > 0 ? 'text-up' : 'text-down'
}
export const REASONS: Record<string, string> = {
  missing_fundamental: 'not reported / not resolved',
  insufficient_history: 'not enough history',
  denominator_invalid: 'denominator not meaningful',
  NOT_MEANINGFUL: 'not meaningful (sign change)',
  unresolved_tag: 'conflicting source tags',
  sign_unexpected: 'unexpected sign in source',
  stale_data: 'source data too old',
  missing_price: 'price unavailable',
}
export const reasonText = (r?: string): string => (r ? (REASONS[r] ?? r) : 'unavailable')
