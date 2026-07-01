// Framework-agnostic multi-track player. One AudioContext, one source-and-gain
// pair per stem, one shared master gain. All transport (play/pause/seek) acts
// on every stem in the same JS tick so the browser schedules them to the
// sample. Solo/mute/volume all route through per-stem GainNode.gain.

export interface StemDef {
  name: string
  url: string
}

interface Track {
  name: string
  buffer: AudioBuffer | null
  gain: GainNode
  source: AudioBufferSourceNode | null
  volume: number      // user-chosen [0..1]
  muted: boolean
  soloed: boolean
}

export type EngineListener = () => void

const SCHEDULE_AHEAD = 0.05  // 50 ms cushion for sample-aligned starts
const DECLICK = 0.01

export class StemEngine {
  private ctx: AudioContext
  private master: GainNode
  private tracks = new Map<string, Track>()
  private order: string[] = []
  private listeners = new Set<EngineListener>()

  private playing = false
  private playbackStartedAt = 0  // ctx.currentTime when the current play began
  private startOffset = 0        // seconds into the buffer at the start of current play
  private pausedAt = 0           // last known position when paused
  private duration = 0

  constructor() {
    const Ctor = window.AudioContext || (window as any).webkitAudioContext
    this.ctx = new Ctor()
    this.master = this.ctx.createGain()
    this.master.gain.value = 1
    this.master.connect(this.ctx.destination)
  }

  // ----- Lifecycle ---------------------------------------------------------

  async load(stems: StemDef[], onProgress?: (loaded: number, total: number) => void): Promise<void> {
    this.dispose(false)
    this.order = stems.map((s) => s.name)
    let loaded = 0

    await Promise.all(stems.map(async (s) => {
      const resp = await fetch(s.url)
      if (!resp.ok) throw new Error(`fetch ${s.name} failed: ${resp.status}`)
      const buf = await resp.arrayBuffer()
      const decoded = await this.ctx.decodeAudioData(buf)

      const gain = this.ctx.createGain()
      gain.gain.value = 1
      gain.connect(this.master)

      this.tracks.set(s.name, {
        name: s.name,
        buffer: decoded,
        gain,
        source: null,
        volume: 1,
        muted: false,
        soloed: false,
      })

      this.duration = Math.max(this.duration, decoded.duration)
      loaded++
      onProgress?.(loaded, stems.length)
    }))

    this.startOffset = 0
    this.pausedAt = 0
    this.playing = false
    this.emit()
  }

  dispose(disposeContext = true) {
    this.stopAllSources()
    for (const t of this.tracks.values()) {
      try { t.gain.disconnect() } catch { /* ignore */ }
    }
    this.tracks.clear()
    this.order = []
    if (disposeContext) {
      this.master.disconnect()
      void this.ctx.close()
    }
    this.playing = false
    this.startOffset = 0
    this.pausedAt = 0
    this.duration = 0
  }

  // ----- Transport ---------------------------------------------------------

  async play() {
    if (this.playing) return
    if (this.tracks.size === 0) return
    if (this.ctx.state === 'suspended') await this.ctx.resume()

    // If the previous play ran to the end, restart from 0. Otherwise pin
    // pausedAt to [0, duration) so the AudioBufferSourceNode has something
    // non-empty to play.
    if (this.pausedAt >= this.duration - 1e-3) this.pausedAt = 0
    this.startOffset = Math.max(0, Math.min(this.pausedAt, this.duration))
    const startAt = this.ctx.currentTime + SCHEDULE_AHEAD
    this.playbackStartedAt = startAt

    for (const t of this.tracks.values()) {
      this.startSource(t, startAt, this.startOffset)
    }
    this.playing = true
    this.emit()
  }

  pause() {
    if (!this.playing) return
    this.pausedAt = this.currentTime()
    this.stopAllSources()
    this.playing = false
    this.emit()
  }

  async toggle() {
    if (this.playing) this.pause()
    else await this.play()
  }

  async seek(seconds: number) {
    const t = Math.max(0, Math.min(seconds, this.duration))
    const wasPlaying = this.playing
    if (this.playing) {
      this.stopAllSources()
      this.playing = false
    }
    this.pausedAt = t
    if (wasPlaying) {
      await this.play()
    } else {
      this.emit()
    }
  }

  currentTime(): number {
    if (this.playing) {
      const elapsed = this.ctx.currentTime - this.playbackStartedAt
      return Math.min(this.startOffset + Math.max(elapsed, 0), this.duration)
    }
    return this.pausedAt
  }

  getDuration() { return this.duration }
  isPlaying() { return this.playing }

  // ----- Per-track controls ------------------------------------------------

  setVolume(name: string, volume: number) {
    const t = this.tracks.get(name); if (!t) return
    t.volume = Math.max(0, Math.min(1, volume))
    this.applyGains()
    this.emit()
  }
  setMuted(name: string, muted: boolean) {
    const t = this.tracks.get(name); if (!t) return
    t.muted = muted
    this.applyGains()
    this.emit()
  }
  setSoloed(name: string, soloed: boolean) {
    const t = this.tracks.get(name); if (!t) return
    t.soloed = soloed
    this.applyGains()
    this.emit()
  }

  trackState(name: string): { volume: number; muted: boolean; soloed: boolean } | null {
    const t = this.tracks.get(name); if (!t) return null
    return { volume: t.volume, muted: t.muted, soloed: t.soloed }
  }

  trackNames(): string[] { return [...this.order] }

  // ----- Subscriptions -----------------------------------------------------

  subscribe(fn: EngineListener): () => void {
    this.listeners.add(fn)
    return () => { this.listeners.delete(fn) }
  }

  // ----- Internals ---------------------------------------------------------

  private startSource(t: Track, when: number, offset: number) {
    if (!t.buffer) return
    const src = this.ctx.createBufferSource()
    src.buffer = t.buffer
    src.connect(t.gain)
    src.onended = () => {
      // Auto-stop when the longest stem reaches the end. We treat any source
      // ending as "session done" — every stem has identical duration so the
      // first ended is the right signal.
      if (this.playing && src === t.source) {
        this.pausedAt = this.duration
        this.stopAllSources()
        this.playing = false
        this.emit()
      }
    }
    src.start(when, offset)
    t.source = src
  }

  private stopAllSources() {
    for (const t of this.tracks.values()) {
      if (t.source) {
        try { t.source.onended = null; t.source.stop() } catch { /* ignore */ }
        try { t.source.disconnect() } catch { /* ignore */ }
        t.source = null
      }
    }
  }

  private applyGains() {
    const anySoloed = [...this.tracks.values()].some((t) => t.soloed)
    const now = this.ctx.currentTime
    for (const t of this.tracks.values()) {
      const isAudible = !t.muted && (anySoloed ? t.soloed : true)
      const target = isAudible ? t.volume : 0
      try {
        t.gain.gain.cancelScheduledValues(now)
        t.gain.gain.setTargetAtTime(target, now, DECLICK)
      } catch {
        t.gain.gain.value = target
      }
    }
  }

  private emit() {
    for (const fn of this.listeners) {
      try { fn() } catch (err) { console.warn('engine listener threw', err) }
    }
  }
}
