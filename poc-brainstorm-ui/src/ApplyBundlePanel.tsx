/**
 * Phase 5: minimal steering — POST a change package to the API, then refresh the graph.
 * The user does not edit JSON by hand in the product vision; this is the dev / POC surface
 * until AI proposes the same payload in-app.
 */
import { useCallback, useState } from 'react'

import { applyBundleUrl } from './apiConfig'

type Props = {
  onApplied: () => void
}

export function ApplyBundlePanel({ onApplied }: Props) {
  const [unifiedDiff, setUnifiedDiff] = useState('')
  const [skipValidate, setSkipValidate] = useState(false)
  const [pytestOnly, setPytestOnly] = useState(true)
  const [busy, setBusy] = useState(false)
  const [logText, setLogText] = useState<string | null>(null)

  const postBundle = useCallback(
    async (body: Record<string, unknown>) => {
      setBusy(true)
      setLogText(null)
      try {
        const res = await fetch(applyBundleUrl(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        const data = await res.json().catch(() => ({ parse_error: true }))
        setLogText(JSON.stringify(data, null, 2))
        if (res.ok && data.ok === true) {
          onApplied()
        }
      } catch (e) {
        setLogText(e instanceof Error ? e.message : String(e))
      } finally {
        setBusy(false)
      }
    },
    [onApplied],
  )

  const onDryRun = useCallback(() => {
    void postBundle({
      schema_version: 0,
      unified_diff: unifiedDiff,
      dry_run: true,
    })
  }, [postBundle, unifiedDiff])

  const onApply = useCallback(() => {
    if (
      !window.confirm(
        'Apply this patch to the repo configured as BRAINSTORM_GOLDEN_REPO on the API server?',
      )
    ) {
      return
    }
    void postBundle({
      schema_version: 0,
      unified_diff: unifiedDiff,
      skip_validate: skipValidate,
      pytest_only: pytestOnly,
    })
  }, [postBundle, unifiedDiff, skipValidate, pytestOnly])

  return (
    <section className="apply-bundle-section">
      <h2>Apply change package</h2>
      <p className="apply-bundle-locate">
        <strong>Where to paste:</strong> use the large text box <strong>below</strong> (this
        right-hand column). You need <code>npm run dev:api</code> and the API running (
        <code>npm run api</code>).
      </p>
      <p className="apply-bundle-hint">
        <code>POST {applyBundleUrl()}</code> — unified diff for{' '}
        <code>patch -p1</code> from repo root. On success the API refreshes{' '}
        <code>raw.json</code>; click <strong>Reload RAW + overlay</strong> in the header if the
        graph does not update.
      </p>
      <div className="mock-card apply-bundle-card">
        <textarea
          className="apply-bundle-textarea"
          rows={10}
          value={unifiedDiff}
          onChange={(e) => setUnifiedDiff(e.target.value)}
          placeholder="--- a/src/…"
          spellCheck={false}
          disabled={busy}
        />
        <label className="apply-bundle-check">
          <input
            type="checkbox"
            checked={skipValidate}
            onChange={(e) => setSkipValidate(e.target.checked)}
            disabled={busy}
          />
          Skip validate (pytest + typecheck)
        </label>
        <label className="apply-bundle-check">
          <input
            type="checkbox"
            checked={pytestOnly}
            onChange={(e) => setPytestOnly(e.target.checked)}
            disabled={busy || skipValidate}
          />
          If validating: pytest only
        </label>
        <div className="apply-bundle-actions">
          <button type="button" disabled={busy} onClick={onDryRun}>
            Dry-run patch
          </button>
          <button type="button" disabled={busy} onClick={onApply}>
            Apply
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
