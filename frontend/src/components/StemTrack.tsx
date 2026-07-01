import type { StemEngine } from '../audio/StemEngine'

interface Props {
  engine: StemEngine
  name: string
  downloadUrl: string
}

export function StemTrack({ engine, name, downloadUrl }: Props) {
  const state = engine.trackState(name)
  if (!state) return null
  const { volume, muted, soloed } = state

  return (
    <div className="grid grid-cols-[5.5rem_2.5rem_2.5rem_1fr_auto] items-center gap-3 px-4 py-3 odd:bg-neutral-900/30">
      <div className="font-medium capitalize">{name}</div>

      <button
        onClick={() => engine.setMuted(name, !muted)}
        title={muted ? 'Unmute' : 'Mute'}
        className={
          'rounded px-2 py-1 text-xs font-semibold border transition ' +
          (muted
            ? 'border-amber-500 bg-amber-500/15 text-amber-200'
            : 'border-neutral-700 text-neutral-300 hover:border-neutral-500')
        }
      >
        M
      </button>

      <button
        onClick={() => engine.setSoloed(name, !soloed)}
        title={soloed ? 'Unsolo' : 'Solo'}
        className={
          'rounded px-2 py-1 text-xs font-semibold border transition ' +
          (soloed
            ? 'border-violet-400 bg-violet-400/15 text-violet-200'
            : 'border-neutral-700 text-neutral-300 hover:border-neutral-500')
        }
      >
        S
      </button>

      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={volume}
        onChange={(e) => engine.setVolume(name, parseFloat(e.target.value))}
        className="w-full accent-violet-500"
      />

      <a
        href={downloadUrl}
        download={`${name}.wav`}
        title="Download stem"
        className="rounded bg-neutral-800 px-3 py-1.5 text-xs hover:bg-neutral-700"
      >
        Download
      </a>
    </div>
  )
}
