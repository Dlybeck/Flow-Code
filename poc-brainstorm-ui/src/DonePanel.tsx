import { useState } from 'react'
import type { WorkResult } from './WorkingPanel'

type DonePanelProps = {
  result: WorkResult
  nodeIdToLabel: Map<string, string>
  onResolve: () => void
  onRetry: (what: string) => void
  onUndo: () => void
  canUndo: boolean
  onFocusNodes: (ids: string[]) => void
  onUpdateMap: () => Promise<void>
}

export function DonePanel({
  result,
  nodeIdToLabel,
  onResolve,
  onRetry,
  onUndo,
  canUndo,
  onFocusNodes,
  onUpdateMap,
}: DonePanelProps) {
  const [retryOpen, setRetryOpen] = useState(false)
  const [retryText, setRetryText] = useState('')
  const [resolving, setResolving] = useState(false)
  const [updatingMap, setUpdatingMap] = useState(false)
  const [mapUpdated, setMapUpdated] = useState(false)

  const handleUpdateMap = async () => {
    setUpdatingMap(true)
    try {
      await onUpdateMap()
      setMapUpdated(true)
    } finally {
      setUpdatingMap(false)
    }
  }

  const handleResolve = () => {
    setResolving(true)
    setTimeout(onResolve, 300)
  }

  const changedNodes = result.changed_node_ids
    .map((id) => ({ id, label: nodeIdToLabel.get(id) }))
    .filter((n): n is { id: string; label: string } => Boolean(n.label))

  const handleRetry = () => {
    const trimmed = retryText.trim()
    if (!trimmed) return
    onRetry(trimmed)
  }

  return (
    <section className={`done-panel${resolving ? ' resolving' : ''}`}>
      <h2>Done — here's what changed</h2>

      <p className="done-summary">{result.summary}</p>

      {result.note ? (
        <div className="done-note">
          <span className="done-note-label">One thing to note:</span> {result.note}
        </div>
      ) : null}

      {result.changed_node_ids.length > 0 && !mapUpdated ? (
        <div className="done-map-stale">
          <span>Map is out of date — {result.changed_node_ids.length} area{result.changed_node_ids.length !== 1 ? 's' : ''} changed.</span>
          <button type="button" onClick={() => void handleUpdateMap()} disabled={updatingMap}>
            {updatingMap ? 'Updating…' : 'Update map →'}
          </button>
        </div>
      ) : mapUpdated ? (
        <div className="done-map-stale done-map-updated">Map updated.</div>
      ) : null}

      {changedNodes.length > 0 ? (
        <div className="done-areas">
          <p className="done-areas-label">Areas touched:</p>
          <div className="done-areas-chips">
            {changedNodes.map((n) => (
              <button
                key={n.id}
                type="button"
                className="done-area-chip"
                onClick={() => onFocusNodes([n.id])}
                title="Pan map to this node"
              >
                {n.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="done-actions">
        <button type="button" className="done-resolve-btn" onClick={handleResolve}>
          Looks good — mark resolved
        </button>

        {retryOpen ? (
          <div className="done-retry-form">
            <textarea
              className="done-retry-textarea"
              placeholder="What's not right?"
              value={retryText}
              rows={3}
              onChange={(e) => setRetryText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleRetry()
              }}
            />
            <button
              type="button"
              className="done-retry-submit"
              disabled={!retryText.trim()}
              onClick={handleRetry}
            >
              Re-brief →
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="done-retry-btn"
            onClick={() => setRetryOpen(true)}
          >
            Something's off — try again
          </button>
        )}

        {canUndo ? (
          <button type="button" className="done-undo-btn" onClick={onUndo}>
            Undo this
          </button>
        ) : null}
      </div>
    </section>
  )
}
