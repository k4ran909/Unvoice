import type { Job } from '../api/client'

interface Props {
  job: Job | null
  error?: string | null
}

const STATUS_LABEL: Record<string, string> = {
  queued: 'Queued',
  running: 'Separating',
  done: 'Done',
  error: 'Failed',
}

export function ProgressPanel({ job, error }: Props) {
  if (!job && !error) return null

  const pct = job ? Math.round((job.progress ?? 0) * 100) : 0
  const label = job ? STATUS_LABEL[job.status] ?? job.status : 'Error'

  return (
    <div className="w-full max-w-xl rounded-md border border-neutral-800 bg-neutral-900/40 p-5 space-y-3">
      <div className="flex justify-between text-sm text-neutral-300">
        <span className="font-medium">{label}</span>
        {job && job.status !== 'error' && <span className="text-neutral-500">{pct}%</span>}
      </div>
      <div className="h-2 w-full overflow-hidden rounded bg-neutral-800">
        <div
          className="h-full bg-violet-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      {error && <div className="text-sm text-red-400">{error}</div>}
      {job?.error && <div className="text-sm text-red-400">{job.error}</div>}
    </div>
  )
}
