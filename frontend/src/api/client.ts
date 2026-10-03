export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  if (!res.ok) {
    let detail: unknown = undefined
    try {
      detail = (await res.json())?.detail
    } catch {
      /* body is not JSON */
    }
    const msg = typeof detail === 'string' ? detail : (detail as { message?: string } | undefined)?.message ?? res.statusText
    throw new ApiError(res.status, msg, detail)
  }
  return (await res.json()) as T
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) {
    let detail: unknown = undefined
    try {
      detail = (await res.json())?.detail
    } catch {
      /* body is not JSON */
    }
    const msg = typeof detail === 'string' ? detail : (detail as { message?: string } | undefined)?.message ?? res.statusText
    throw new ApiError(res.status, msg, detail)
  }
  return (await res.json()) as T
}
