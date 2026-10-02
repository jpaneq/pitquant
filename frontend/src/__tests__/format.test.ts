import { fmtCompact, fmtMoney, fmtNum, fmtPct, reasonText, signClass } from '../lib/format'

describe('format', () => {
  it('renders null/NaN as an em dash, never as 0', () => {
    expect(fmtNum(null)).toBe('—')
    expect(fmtPct(undefined)).toBe('—')
    expect(fmtCompact(Number.NaN)).toBe('—')
    expect(fmtMoney(null)).toBe('—')
  })
  it('formats percent with explicit sign when asked', () => {
    expect(fmtPct(0.1234, 1)).toBe('12.3%')
    expect(fmtPct(0.1234, 1, true)).toBe('+12.3%')
    expect(fmtPct(-0.05, 1, true)).toBe('-5.0%')
  })
  it('compacts large numbers with units', () => {
    expect(fmtCompact(4.82e12, '$')).toBe('$4.82T')
    expect(fmtCompact(466_823_000_000, '$')).toBe('$466.82B')
    expect(fmtCompact(-1_500_000)).toBe('-1.5M')
  })
  it('uses green/red only for signed financial deltas', () => {
    expect(signClass(0.01)).toBe('text-up')
    expect(signClass(-0.01)).toBe('text-down')
    expect(signClass(null)).toBe('text-muted')
  })
  it('explains unavailable metrics', () => {
    expect(reasonText('NOT_MEANINGFUL')).toMatch(/not meaningful/)
    expect(reasonText(undefined)).toBe('unavailable')
  })
})
