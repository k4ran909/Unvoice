import { useEffect, useRef, useState } from 'react'
import { StemEngine, type StemDef } from './StemEngine'

export interface UseStemEngineResult {
  engine: StemEngine | null
  ready: boolean
  loading: boolean
  loadProgress: number  // 0..1, fraction of stems decoded
  error: string | null
  position: number
  duration: number
  playing: boolean
  /** Render counter — bumped on every engine event so components re-read state */
  tick: number
}

export function useStemEngine(stems: StemDef[] | null): UseStemEngineResult {
  const engineRef = useRef<StemEngine | null>(null)
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadProgress, setLoadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!stems) return
    let cancelled = false
    const engine = new StemEngine()
    engineRef.current = engine

    setReady(false)
    setLoading(true)
    setError(null)
    setLoadProgress(0)

    engine.load(stems, (loaded, total) => {
      if (!cancelled) setLoadProgress(loaded / total)
    })
      .then(() => {
        if (cancelled) { engine.dispose(); return }
        setReady(true)
        setLoading(false)
        setDuration(engine.getDuration())
      })
      .catch((err) => {
        if (cancelled) return
        setLoading(false)
        setError(err instanceof Error ? err.message : 'Failed to load stems')
        engine.dispose()
      })

    const unsubscribe = engine.subscribe(() => {
      if (cancelled) return
      setPlaying(engine.isPlaying())
      setTick((n) => n + 1)
    })

    return () => {
      cancelled = true
      unsubscribe()
      engine.dispose()
      engineRef.current = null
    }
  }, [stems])

  useEffect(() => {
    let raf = 0
    let stopped = false
    const tickPos = () => {
      if (stopped) return
      const e = engineRef.current
      if (e) setPosition(e.currentTime())
      raf = requestAnimationFrame(tickPos)
    }
    raf = requestAnimationFrame(tickPos)
    return () => { stopped = true; cancelAnimationFrame(raf) }
  }, [])

  return {
    engine: engineRef.current,
    ready, loading, loadProgress, error,
    position, duration, playing, tick,
  }
}
