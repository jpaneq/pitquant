import clsx from 'clsx'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { Card, CardBody, CardHeader, PanelError, Skeleton } from '../../components/ui/primitives'
import { ColumnChart, Legend, LineChart } from '../forward/charts'

type Num = number | null
type Component = { metric: string; label: string; value: Num; own_median: Num; peer_median: Num; own_pct: Num; peer_pct: Num }
export type Sheet = {
  ticker: string; name: string; sector: string | null; sector_supported: boolean; currency: string
  price: number; price_date: string; latest_period: string | null; latest_filing_at: string | null
  ttm: Record<string, Num>; profitability: Record<string, Num>; growth: Record<string, Num>
  balance: Record<string, Num>; capital_allocation: Record<string, Num>
  valuation: Record<string, Num>
  history: { period: string; revenue: Num; net_income: Num; fcf: Num; operating_margin: Num; net_margin: Num; debt_to_assets: Num }[]
  valuation_history: { date: string; pe: Num }[]
  cheapness: { label: string; score?: Num; vs_own_history?: Num; vs_peers?: Num; peers_n?: number; reason?: string | null; components: Component[] }
}

const C1 = 'var(--series-1)'
const C2 = 'var(--series-2)'
const pct = (n: Num, d = 1) => n == null ? '—' : `${(n * 100).toFixed(d)}%`
const signed = (n: Num) => n == null ? '—' : `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)}%`
function money(n: Num) {
  if (n == null) return '—'
  const a = Math.abs(n), s = n < 0 ? '−' : ''
  if (a >= 1e12) return `${s}${(a / 1e12).toFixed(2)} billones $`
  if (a >= 1e9) return `${s}${(a / 1e9).toFixed(1)} mil M$`
  if (a >= 1e6) return `${s}${(a / 1e6).toFixed(0)} M$`
  return `${s}${a.toFixed(0)} $`
}
const short = (n: number) => { const a = Math.abs(n); return a >= 1e12 ? `${(n / 1e12).toFixed(1)} bill.` : a >= 1e9 ? `${(n / 1e9).toFixed(0)} mil M` : a === 0 ? '0' : `${(n / 1e6).toFixed(0)} M` }
const date = (iso: string | null) => iso ? new Date(iso).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' }) : '—'

const BAND: Record<string, { text: string; tone: string }> = {
  MUY_BARATA: { text: 'Muy barata', tone: 'text-up' },
  BARATA: { text: 'Barata', tone: 'text-up' },
  PRECIO_NORMAL: { text: 'En su precio', tone: 'text-fg' },
  CARA: { text: 'Cara', tone: 'text-down' },
  MUY_CARA: { text: 'Muy cara', tone: 'text-down' },
  NO_APLICABLE: { text: 'No aplicable', tone: 'text-muted' },
  SIN_DATOS: { text: 'Sin datos', tone: 'text-muted' },
}

export function CompanyPage() {
  const { ticker = 'AAPL' } = useParams()
  const nav = useNavigate()
  const list = useQuery({ queryKey: ['companies'], queryFn: ({ signal }) => api<{ ticker: string; name: string }[]>('/companies', signal) })
  const sheet = useQuery({ queryKey: ['company', ticker], queryFn: ({ signal }) => api<Sheet>(`/companies/${ticker}`, signal), staleTime: 3_600_000 })
  return <section aria-label="Ficha de empresa" className="mx-auto max-w-7xl space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold">Fichas de empresas</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">Lo que cuentan las cuentas que cada empresa presenta en la SEC, en una página, y si hoy su precio es caro o barato comparado con lo que gana.</p>
      </div>
      <label className="text-sm">Empresa{' '}
        <select aria-label="Empresa" value={ticker} onChange={e => nav(`/empresas/${e.target.value}`)} className="ml-1 rounded-md border border-border bg-surface-2 px-2 py-1.5">
          {(list.data ?? [{ ticker, name: ticker }]).map(c => <option key={c.ticker} value={c.ticker}>{c.ticker} · {c.name}</option>)}
        </select>
      </label>
    </header>
    {sheet.isPending ? <div className="space-y-3"><p className="text-sm text-muted">Calculando la ficha… la primera vez tarda unos 20 segundos porque la compara con las otras 54 empresas.</p><Skeleton className="h-40" /><Skeleton className="h-64" /></div>
      : sheet.isError ? <PanelError what="Ficha" error={sheet.error} onRetry={() => sheet.refetch()} />
        : <Factsheet s={sheet.data} />}
  </section>
}

export function Factsheet({ s }: { s: Sheet }) {
  const g = s.growth, p = s.profitability, b = s.balance, c = s.capital_allocation, t = s.ttm
  const hist = s.history.slice(-24)
  const pe = s.valuation_history.filter(v => v.pe != null && (v.pe as number) < 200)
  const peMedian = pe.length ? [...pe.map(v => v.pe as number)].sort((x, y) => x - y)[Math.floor(pe.length / 2)] : null
  return <>
    <div className="rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div><h2 className="text-xl font-semibold">{s.name} <span className="text-muted">· {s.ticker}</span></h2><p className="text-sm text-muted">{s.sector ?? 'Sector no disponible'}</p></div>
        <div className="text-right"><div className="num text-2xl font-semibold">{s.price.toFixed(2)} {s.currency === 'USD' ? '$' : s.currency}</div><div className="text-xs text-muted">cierre del {date(s.price_date)} · capitalización {money(s.valuation.market_cap)}</div></div>
      </div>
      <p className="mt-2 text-xs text-muted">Últimas cuentas: periodo cerrado el {date(s.latest_period)}, presentadas a la SEC el {date(s.latest_filing_at)}. Cifras anuales = suma de los últimos 12 meses.</p>
    </div>

    <CheapCard s={s} />

    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Kpi label="Ventas (12 meses)" value={money(t.revenue)} sub={<>{signed(g.revenue_yoy)} en un año · {signed(g.revenue_cagr5)} anual en 5 años</>} good={g.revenue_yoy} />
      <Kpi label="Beneficio neto" value={money(t.net_income)} sub={<>margen {pct(p.net_margin)} · {signed(g.net_income_yoy)} en un año</>} good={g.net_income_yoy} />
      <Kpi label="Caja libre generada" value={money(t.fcf)} sub={<>el {pct(p.fcf_margin, 0)} de lo que vende · {signed(g.fcf_yoy)} en un año</>} good={g.fcf_yoy} />
      <Kpi label="Rentabilidad" value={pct(p.operating_margin)} sub={<>margen operativo · rentabilidad sobre activos {pct(p.roa)}</>} />
      <Kpi label="Deuda neta" value={money(b.net_debt)} sub={<>deuda / activos {pct(b.debt_to_assets, 0)} · caja {money(b.cash)}</>} good={b.net_debt == null ? null : -b.net_debt} />
      <Kpi label="Devuelve al accionista" value={pct(c.shareholder_yield)} sub={<>dividendo {pct(c.dividend_yield)} + recompras {pct(c.buyback_yield)} · acciones {signed(c.shares_growth1)} en un año</>} />
    </div>

    <div className="space-y-5">
      <Card><CardHeader title="Ventas y beneficio" sub="Últimos 12 meses en cada trimestre" /><CardBody>
        <ColumnChart label="Ventas y beneficio" x={hist.map(h => h.period.slice(0, 7))} format={short}
          series={[{ key: 'rev', label: 'Ventas', color: C1, values: hist.map(h => h.revenue) }, { key: 'ni', label: 'Beneficio neto', color: C2, values: hist.map(h => h.net_income) }]} />
        <Legend items={[{ label: 'Ventas', color: C1 }, { label: 'Beneficio neto', color: C2 }]} />
      </CardBody></Card>
      <Card><CardHeader title="Márgenes" sub="De cada 100 $ que vende, cuánto queda" /><CardBody>
        <LineChart label="Márgenes" x={hist.map(h => h.period.slice(0, 7))} yMin={Math.min(0, ...hist.map(h => h.net_margin ?? 0))} yMax={Math.max(0.1, ...hist.map(h => (h.operating_margin ?? 0) * 1.15))} format={v => pct(v, 0)}
          series={[{ key: 'op', label: 'Margen operativo', color: C1, values: hist.map(h => h.operating_margin) }, { key: 'net', label: 'Margen neto', color: C2, values: hist.map(h => h.net_margin) }]} />
        <Legend items={[{ label: 'Margen operativo', color: C1 }, { label: 'Margen neto', color: C2 }]} />
      </CardBody></Card>
    </div>

    {pe.length > 12 && <Card><CardHeader title="¿Cuánto pagas por cada dólar de beneficio?" sub="PER: precio / beneficio. Más alto = más caro. La línea discontinua es su valor habitual (mediana de 10 años)." /><CardBody>
      <LineChart label="PER histórico" x={pe.map(v => v.date.slice(0, 7))} yMin={0} yMax={Math.ceil(Math.max(...pe.map(v => v.pe as number)) / 20) * 20} format={v => v.toFixed(0)}
        series={[{ key: 'pe', label: 'PER', color: C1, values: pe.map(v => v.pe) }, { key: 'med', label: 'Habitual', color: 'var(--muted)', dashed: true, values: pe.map(() => peMedian) }]} />
      <Legend items={[{ label: 'PER', color: C1 }, { label: `Habitual (${peMedian?.toFixed(0)})`, color: 'var(--muted)', dashed: true }]} />
    </CardBody></Card>}

    <p className="text-xs text-muted">Fuente: SEC EDGAR (informes 10-K y 10-Q); cada dato cuenta desde el día en que se presentó. Precios de Yahoo. No es una recomendación de inversión.</p>
  </>
}

function Kpi({ label, value, sub, good }: { label: string; value: string; sub: React.ReactNode; good?: Num }) {
  return <div className="rounded-lg border border-border bg-surface p-4">
    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{label}</div>
    <div className={clsx('num mt-1 text-xl font-semibold', good != null && (good >= 0 ? 'text-up' : 'text-down'))}>{value}</div>
    <div className="num mt-0.5 text-xs text-muted">{sub}</div>
  </div>
}

function CheapCard({ s }: { s: Sheet }) {
  const ch = s.cheapness
  const band = BAND[ch.label] ?? BAND.SIN_DATOS
  if (ch.label === 'NO_APLICABLE') return <Card><CardBody><b>¿Cara o barata?</b> <span className="text-muted">No aplicable: {s.sector}. Bancos y aseguradoras se valoran con otras métricas (valor en libros, solvencia) que este indicador no usa.</span></CardBody></Card>
  return <Card>
    <CardHeader title="¿Cara o barata?" sub="Compara lo que la empresa gana, vende y genera en caja con lo que cuesta hoy." />
    <CardBody className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div>
        <div className={clsx('text-3xl font-semibold', band.tone)}>{band.text}</div>
        <Scale value={ch.score ?? null} />
        <div className="mt-4 space-y-2 text-sm">
          <Sub label="Frente a su propia historia (10 años)" value={ch.vs_own_history ?? null} />
          <Sub label={`Frente a las otras ${ch.peers_n ?? ''} empresas`} value={ch.vs_peers ?? null} />
        </div>
        <p className="mt-3 text-xs text-muted">0 = la más cara, 100 = la más barata. Barata no significa que vaya a subir: es una foto de cuánto pagas, no un pronóstico.</p>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">De dónde sale</h3>
        <table className="num w-full text-left text-xs [&_td]:py-1.5 [&_td]:pr-3 [&_th]:pr-3">
          <thead className="text-muted"><tr><th>Por cada 100 $ de precio…</th><th>Hoy</th><th>Lo habitual</th><th>Las demás</th></tr></thead>
          <tbody>{ch.components.map(c => <tr key={c.metric} className="border-t border-border">
            <td>{c.label}</td><td className="font-semibold">{pct(c.value)}</td><td>{pct(c.own_median)}</td><td>{pct(c.peer_median)}</td>
          </tr>)}</tbody>
        </table>
        <p className="mt-2 text-xs text-muted">Ejemplo: «Beneficio / precio 2,7%» significa que por cada 100 $ que pagas por la acción, la empresa gana 2,70 $ al año. Si hoy es menos de lo habitual, está más cara de lo normal.</p>
      </div>
    </CardBody>
  </Card>
}

function Scale({ value }: { value: number | null }) {
  const labels = ['Muy cara', 'Cara', 'En su precio', 'Barata', 'Muy barata']
  const colors = ['bg-down/70', 'bg-down/35', 'bg-surface-2', 'bg-up/35', 'bg-up/70']
  return <div className="mt-3" aria-label={value == null ? 'Sin datos' : `Puntuación ${Math.round(value)} de 100`}>
    <div className="relative flex h-3 gap-0.5">
      {colors.map((c, i) => <span key={i} className={clsx('flex-1 first:rounded-l last:rounded-r', c)} />)}
      {value != null && <span className="absolute -top-1 h-5 w-1 -translate-x-1/2 rounded bg-fg" style={{ left: `${value}%` }} />}
    </div>
    <div className="mt-1 flex justify-between text-[10px] text-muted">{labels.map(l => <span key={l}>{l}</span>)}</div>
  </div>
}

function Sub({ label, value }: { label: string; value: number | null }) {
  return <div>
    <div className="flex justify-between text-xs"><span className="text-muted">{label}</span><b className="num">{value == null ? '—' : `${Math.round(value)}/100`}</b></div>
    <div className="mt-1 h-1.5 rounded-full bg-surface-2"><div className={clsx('h-1.5 rounded-full', value != null && value >= 50 ? 'bg-up/70' : 'bg-down/70')} style={{ width: `${value ?? 0}%` }} /></div>
  </div>
}
