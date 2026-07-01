interface Props {
  message: string | null
  onDismiss?: () => void
}

export function ErrorBanner({ message, onDismiss }: Props) {
  if (!message) return null
  return (
    <div className="w-full max-w-xl rounded-md border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 flex justify-between items-start gap-4">
      <span>{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="text-red-300/70 hover:text-red-200">×</button>
      )}
    </div>
  )
}
