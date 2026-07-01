const BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'

export type JobMode = '2stem' | '4stem'
export type JobStatus = 'queued' | 'running' | 'done' | 'error'

export interface Job {
  id: string
  mode: JobMode
  status: JobStatus
  progress: number
  stems: Record<string, string>
  error: string | null
}

export interface ApiError {
  code: string
  message: string
}

class HttpError extends Error {
  status: number
  body: { error?: ApiError }
  constructor(status: number, body: { error?: ApiError }) {
    super(body.error?.message ?? `HTTP ${status}`)
    this.status = status
    this.body = body
  }
}

async function parseOrThrow(resp: Response) {
  let body: any = null
  const text = await resp.text()
  if (text) {
    try { body = JSON.parse(text) } catch { body = { raw: text } }
  }
  if (!resp.ok) throw new HttpError(resp.status, body ?? {})
  return body
}

export async function createJob(file: File, mode: JobMode): Promise<{ job_id: string; status: JobStatus }> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('mode', mode)
  const resp = await fetch(`${BASE}/jobs`, { method: 'POST', body: fd })
  return parseOrThrow(resp)
}

export async function getJob(id: string): Promise<Job> {
  const resp = await fetch(`${BASE}/jobs/${encodeURIComponent(id)}`)
  return parseOrThrow(resp)
}

export function stemUrl(job: Job, stem: string): string {
  // job.stems contains server-side paths like "/api/jobs/<id>/stems/<name>".
  // If VITE_API_BASE_URL is something other than "/api", rewrite the prefix
  // so that a deployment with the API on a different host still works.
  const raw = job.stems[stem]
  if (!raw) return ''
  if (BASE === '/api') return raw
  return raw.replace(/^\/api/, BASE.replace(/\/$/, ''))
}

export { HttpError }
