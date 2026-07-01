import { useCallback, useRef, useState } from 'react'
import type { JobMode } from '../api/client'
import { bytes } from '../lib/format'

interface Props {
  onSubmit: (file: File, mode: JobMode) => void
  disabled?: boolean
}

export function Dropzone({ onSubmit, disabled }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [mode, setMode] = useState<JobMode>('2stem')
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setFile(f)
  }, [])

  const openPicker = () => inputRef.current?.click()
  const clearFile = (e: React.MouseEvent) => {
    e.stopPropagation()
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="w-full max-w-xl space-y-4">
      <div
        role="button"
        tabIndex={0}
        onClick={openPicker}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker() } }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={
          'block cursor-pointer rounded-lg border-2 border-dashed p-10 text-center transition outline-none focus-visible:border-violet-400 ' +
          (dragOver
            ? 'border-violet-400 bg-violet-400/10'
            : 'border-neutral-700 hover:border-neutral-500 bg-neutral-900/40')
        }
      >
        <input
          ref={inputRef}
          type="file"
          accept="audio/*,.mp3,.wav,.flac,.m4a,.ogg,.opus"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <div>
            <div className="font-medium text-neutral-100">{file.name}</div>
            <div className="text-sm text-neutral-400">{bytes(file.size)}</div>
            <button
              type="button"
              onClick={clearFile}
              className="mt-3 text-xs text-neutral-400 hover:text-neutral-200 underline"
            >
              Choose a different file
            </button>
          </div>
        ) : (
          <div>
            <div className="text-lg text-neutral-200">Drop an audio file</div>
            <div className="text-sm text-neutral-500 mt-1">or click to browse</div>
          </div>
        )}
      </div>

      <fieldset className="grid grid-cols-2 gap-3">
        <ModeRadio
          checked={mode === '2stem'}
          onChange={() => setMode('2stem')}
          label="2 stems"
          sub="Vocals + Instrumental"
        />
        <ModeRadio
          checked={mode === '4stem'}
          onChange={() => setMode('4stem')}
          label="4 stems"
          sub="Vocals · Drums · Bass · Other"
        />
      </fieldset>

      <button
        type="button"
        disabled={!file || disabled}
        onClick={() => file && onSubmit(file, mode)}
        className="w-full rounded-md bg-violet-500 px-4 py-3 font-medium text-white transition disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500 hover:bg-violet-400"
      >
        {disabled ? 'Working…' : 'Separate'}
      </button>
    </div>
  )
}

function ModeRadio({ checked, onChange, label, sub }: { checked: boolean; onChange: () => void; label: string; sub: string }) {
  return (
    <label
      className={
        'cursor-pointer rounded-md border p-3 text-center transition ' +
        (checked
          ? 'border-violet-400 bg-violet-400/10 text-neutral-100'
          : 'border-neutral-800 hover:border-neutral-600 text-neutral-300')
      }
    >
      <input type="radio" name="mode" checked={checked} onChange={onChange} className="sr-only" />
      <div className="font-medium">{label}</div>
      <div className="text-xs text-neutral-400 mt-0.5">{sub}</div>
    </label>
  )
}
