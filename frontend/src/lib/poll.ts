export interface PollOptions<T> {
  interval: number
  shouldStop: (value: T) => boolean
  onValue: (value: T) => void
  onError?: (err: unknown) => void
  signal: AbortSignal
}

export async function poll<T>(fetcher: () => Promise<T>, opts: PollOptions<T>) {
  let backoff = opts.interval
  while (!opts.signal.aborted) {
    try {
      const value = await fetcher()
      opts.onValue(value)
      if (opts.shouldStop(value)) return value
      backoff = opts.interval
    } catch (err) {
      opts.onError?.(err)
      backoff = Math.min(backoff * 2, 10000)
    }
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, backoff)
      opts.signal.addEventListener('abort', () => {
        clearTimeout(timer)
        resolve()
      }, { once: true })
    })
  }
}
