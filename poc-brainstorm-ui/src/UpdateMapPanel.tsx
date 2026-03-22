import { useCallback, useState } from 'react'

import { updateMapUrl } from './apiConfig'

type Props = {
  onDone: () => void
}

export function UpdateMapPanel({ onDone }: Props) {
  const [busy, setBusy] = useState(false)
  const [logText, setLogText] = useState<string | null>(null)

  const run = useCallback(async () => {
    setBusy(true)
    setLogText(null)
    try {
      const res = await fetch(updateMapUrl(), { method: 'POST' })
      const data = await res.json().catch(() => ({}))
      setLogText(JSON.stringify(data, null, 2))
      if (res.ok && data.ok === true) {
        onDone()
      }
    } catch (e) {
      setLogText(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [onDone])

  return (
    <section className="apply-bundle-section">
      <h2>Update map</h2>
      <p className="apply-bundle-locate">
        Fills friendly <strong>titles</strong> and <strong>descriptions</strong> for{' '}
        <strong>folders</strong>, <strong>files</strong> (gray nodes), and{' '}
        <strong>symbols</strong> (accent nodes) in <code>overlay.json</code> (deepest folders
        first, using child file labels as context). Hover a file node to see the full blurb.
        Uses DeepSeek from <code>.env</code>; <code>UPDATE_MAP_DRY_RUN=1</code> skips the API.
      </p>
      <div className="mock-card apply-bundle-card">
        <div className="apply-bundle-actions">
          <button type="button" disabled={busy} onClick={() => void run()}>
            {busy ? 'Running…' : 'Run Update map'}
          </button>
        </div>
        {logText ? (
          <pre className="apply-bundle-log" role="status">
            {logText}
          </pre>
        ) : null}
      </div>
    </section>
  )
}
