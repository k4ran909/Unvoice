import { useEffect, useRef, useState } from 'react'
import { Dropzone } from './components/Dropzone'
import { ErrorBanner } from './components/ErrorBanner'
import { ProgressPanel } from './components/ProgressPanel'
import { StemPlayer } from './components/StemPlayer'
import { createJob, getJob, HttpError } from './api/client'
import type { Job, JobMode } from './api/client'
import { poll } from './lib/poll'

type Stage = 'idle' | 'uploading' | 'processing' | 'ready' | 'error'

export default function App() {
  const [stage, setStage] = useState<Stage>('idle')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const submit = async (file: File, mode: JobMode) => {
    setError(null)
    setStage('uploading')
    setJob(null)
    try {
      const { job_id } = await createJob(file, mode)
      setStage('processing')

      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac

      await poll<Job>(() => getJob(job_id), {
        interval: 1500,
        signal: ac.signal,
        shouldStop: (j) => j.status === 'done' || j.status === 'error',
        onValue: (j) => {
          setJob(j)
          if (j.status === 'done') setStage('ready')
          else if (j.status === 'error') {
            setStage('error')
            setError(j.error ?? 'Separation failed')
          }
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : 'Connection error')
        },
      })
    } catch (err) {
      setStage('error')
      const msg = err instanceof HttpError
        ? (err.body?.error?.message ?? err.message)
        : (err instanceof Error ? err.message : 'Upload failed')
      setError(msg)
    }
  }

  const reset = () => {
    abortRef.current?.abort()
    setJob(null)
    setError(null)
    setStage('idle')
  }

  const busy = stage === 'uploading' || stage === 'processing'

  return (
    <div className="min-h-full flex flex-col">
      <header className="border-b border-neutral-900 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="text-xl font-semibold tracking-tight">Unvoice</div>
          <div className="text-xs text-neutral-500">vocal-removal MVP</div>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center gap-6 px-6 py-12">
        <div className="text-center max-w-xl space-y-2">
          <h1 className="text-3xl font-semibold">Split vocals from any track</h1>
          <p className="text-neutral-400 text-sm">
            Drop an audio file, pick 2-stem or 4-stem, download the result.
          </p>
        </div>

        <ErrorBanner message={error} onDismiss={() => setError(null)} />

        {stage === 'idle' || stage === 'error' ? (
          <Dropzone onSubmit={submit} disabled={busy} />
        ) : (
          <>
            <ProgressPanel job={job} />
            {stage === 'ready' && job && <StemPlayer job={job} />}
            {(stage === 'ready' || stage === 'error') && (
              <button
                onClick={reset}
                className="text-sm text-neutral-400 hover:text-neutral-200 underline"
              >
                Start over
              </button>
            )}
          </>
        )}
      </main>
    </div>
  )
}
