import { useState } from 'react'
import { Button } from '../../components/ui/primitives'

export function ReportButton({ sec }: { sec: string }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const get = async (format: 'json' | 'markdown') => {
    setBusy(format)
    setErr(null)
    try {
      const res = await fetch(`/analyzer/${sec}/report?format=${format}`)
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const blob = await res.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `pitquant-analysis-${sec}.${format === 'json' ? 'json' : 'md'}`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(null)
    }
  }
  return (
    <div className="flex items-center gap-2">
      <Button onClick={() => get('markdown')} disabled={busy !== null}>{busy === 'markdown' ? 'Generating…' : 'Generate Analysis Report (MD)'}</Button>
      <Button onClick={() => get('json')} disabled={busy !== null}>{busy === 'json' ? 'Generating…' : 'JSON'}</Button>
      {err ? <span role="alert" className="text-xs text-warn">Report failed: {err}</span> : null}
    </div>
  )
}
