import { useCallback, useState } from 'react'

import { updateMapUrl } from './apiConfig'

type Props = {
  onDone: () => void
}

function formatUpdateMapFailure(
  res: Response,
  data: Record<string, unknown>,
): string {
  const parts: string[] = []
  if (!res.ok) parts.push(`HTTP ${res.status}`)
  if (data.ok === false) {
    const errList = data.errors
    if (Array.isArray(errList) && errList.length) {
      parts.push(errList.map(String).join('; '))
    } else {
      parts.push('Server reported ok: false.')
    }
  }
  return parts.join(' — ') || 'Update map did not succeed.'
}

export function UpdateMapPanel({ onDone }: Props) {
  const [busy, setBusy] = useState(false)
  const [logText, setLogText] = useState<string | null>(null)
  const [bannerErr, setBannerErr] = useState<string | null>(null)

  const run = useCallback(async () => {
    setBusy(true)
    setLogText(null)
    setBannerErr(null)
    try {
      const res = await fetch(updateMapUrl(), { method: 'POST' })
      const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
      setLogText(JSON.stringify(data, null, 2))
      if (!res.ok || data.ok !== true) {
        setBannerErr(formatUpdateMapFailure(res, data))
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setLogText(msg)
      setBannerErr(msg)
    } finally {
      setBusy(false)
      onDone()
    }
  }, [onDone])

  return (
    <section className="apply-bundle-section">
      <h2>Update map</h2>
      <div className="mock-card apply-bundle-card">
        <div className="apply-bundle-actions">
          <button type="button" disabled={busy} onClick={() => void run()}>
            {busy ? 'Running…' : 'Run'}
          </button>
        </div>
        {bannerErr ? (
          <p className="apply-bundle-err" role="alert">
            {bannerErr}
          </p>
        ) : null}
        {logText ? (
          <pre className="apply-bundle-log" role="status">
            {logText}
          </pre>
        ) : null}
      </div>
    </section>
  )
}
