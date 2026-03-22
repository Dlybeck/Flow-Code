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
  if (!res.ok) {
    parts.push(`HTTP ${res.status}`)
  }
  if (data.ok === false) {
    const errList = data.errors
    if (Array.isArray(errList) && errList.length) {
      parts.push(errList.map(String).join('; '))
    } else {
      parts.push('Server reported ok: false (see JSON below).')
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
      const ok = res.ok && data.ok === true
      if (!ok) {
        setBannerErr(formatUpdateMapFailure(res, data))
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setLogText(msg)
      setBannerErr(
        `${msg} (is the API running with VITE_BRAINSTORM_API, e.g. npm run dev:studio?)`,
      )
    } finally {
      setBusy(false)
      onDone()
    }
  }, [onDone])

  return (
    <section className="apply-bundle-section">
      <h2>Update map</h2>
      <p className="apply-bundle-locate">
        Fills friendly <strong>titles</strong> and <strong>descriptions</strong> for{' '}
        <strong>folders</strong>, <strong>files</strong> (gray nodes), <strong>symbols</strong>{' '}
        (accent nodes), and <strong>flow</strong> nodes without a symbol (e.g. the unresolved-call
        boundary) via <code>overlay.json</code> keys <code>by_flow_node_id</code>. Deepest folders
        first, using child file labels as context. Hover a file node to see the full blurb. Uses
        DeepSeek from <code>.env</code>; <code>UPDATE_MAP_DRY_RUN=1</code> skips the API.
      </p>
      <div className="mock-card apply-bundle-card">
        <div className="apply-bundle-actions">
          <button type="button" disabled={busy} onClick={() => void run()}>
            {busy ? 'Running…' : 'Run Update map'}
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
