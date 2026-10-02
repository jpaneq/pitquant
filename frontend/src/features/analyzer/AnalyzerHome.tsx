import { Link } from 'react-router-dom'
import { Card, CardBody } from '../../components/ui/primitives'

const GOLDEN = [['AAPL', 'Apple Inc.'], ['MSFT', 'Microsoft Corp.'], ['KO', 'Coca-Cola Co.']] as const
export function AnalyzerHome() {
  return (
    <div className="mx-auto max-w-2xl pt-10">
      <h1 className="text-2xl font-semibold tracking-tight">Analyzer</h1>
      <p className="mt-1 text-sm text-muted">Type a ticker, company, CUSIP or ISIN in the search bar. Any listed security can be analysed; S&amp;P 500 / IBEX membership is a research-universe concept, not a requirement.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {GOLDEN.map(([t, n]) => (
          <Link key={t} to={`/analyzer/${t}`}>
            <Card className="transition-colors hover:border-accent/60"><CardBody><div className="num text-lg font-semibold">{t}</div><div className="text-xs text-muted">{n}</div></CardBody></Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
