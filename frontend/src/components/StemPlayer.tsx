import { useMemo, useState } from 'react'
import { stemUrl, type Job } from '../api/client'
import { useStemEngine } from '../audio/useStemEngine'
import type { StemDef } from '../audio/StemEngine'
import { mmss } from '../lib/format'
import { StemTrack } from './StemTrack'

export function StemPlayer({ job }: { job: Job }) {
  const stemDefs = useMemo<StemDef[]>(() =>
    Object.keys(job.stems).map((name) => ({ name, url: stemUrl(job, name) })),
    [job],
  )

  const {
    engine, ready, loading, loadProgress, error,
    position, duration, playing,
  } = useStemEngine(stemDefs)

  // While the user drags the scrubber we show their target value and suppress
  // the rAF position. Commit the seek on release so we don't tear down + rebuild
  // the AudioBufferSourceNodes on every step.
  const [scrub, setScrub] = useState<number | null>(null)

  if (error) {
    return <div className="w-full max-w-xl text-red-300 text-sm">Player error: {error}</div>
  }

  if (loading || !ready || !engine) {
    return (
      <div className="w-full max-w-xl rounded-md border border-neutral-800 bg-neutral-900/40 p-5 space-y-2">
        <div className="text-sm text-neutral-300">Decoding stems…</div>
        <div className="h-1.5 w-full overflow-hidden rounded bg-neutral-800">
          <div
            className="h-full bg-violet-500 transition-all"
            style={{ width: `${Math.round(loadProgress * 100)}%` }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-xl space-y-3">
      <div className="rounded-md border border-neutral-800 bg-neutral-900/40">
        <div className="flex items-center gap-4 px-4 py-3 border-b border-neutral-800">
          <button
            onClick={() => engine.toggle()}
            className="rounded-full bg-violet-500 hover:bg-violet-400 w-11 h-11 flex items-center justify-center text-white text-lg"
            aria-label={playing ? 'Pause' : 'Play'}
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.01}
            value={scrub ?? Math.min(position, duration)}
            onInput={(e) => setScrub(parseFloat((e.target as HTMLInputElement).value))}
            onChange={(e) => {
              const t = parseFloat(e.target.value)
              setScrub(null)
              engine.seek(t)
            }}
            onPointerUp={() => {
              if (scrub !== null) {
                const t = scrub
                setScrub(null)
                engine.seek(t)
              }
            }}
            className="flex-1 accent-violet-500"
          />
          <div className="font-mono text-sm text-neutral-400 tabular-nums">
            {mmss(scrub ?? position)} / {mmss(duration)}
          </div>
        </div>
        <div className="divide-y divide-neutral-800/60">
          {engine.trackNames().map((name) => (
            <StemTrack
              key={name}
              engine={engine}
              name={name}
              downloadUrl={stemUrl(job, name)}
            />
          ))}
        </div>
      </div>
      <div className="text-xs text-neutral-500 text-center">
        M = mute · S = solo · drag to seek
      </div>
    </div>
  )
}
