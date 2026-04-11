import { useState, useEffect } from 'react'

type BriefPanelProps = {
  selectedNodeIds: string[]
  selectedNodeLabels: string[]
  apiEnabled: boolean
  onGo: (brief: string, nodeIds: string[], nodeLabels: string[], extraContext?: string) => Promise<void>
  isGoing: boolean
}

export function BriefPanel({
  selectedNodeIds,
  selectedNodeLabels,
  apiEnabled,
  onGo,
  isGoing,
}: BriefPanelProps) {
  const [brief, setBrief] = useState('')
  const [extraContext, setExtraContext] = useState('')
  const [pinnedIds, setPinnedIds] = useState<string[]>([])
  const [pinnedLabels, setPinnedLabels] = useState<string[]>([])

  // Capture new selections; don't clear when user clicks away
  useEffect(() => {
    if (selectedNodeIds.length > 0) {
      setPinnedIds(selectedNodeIds)
      setPinnedLabels(selectedNodeLabels)
    }
  }, [selectedNodeIds, selectedNodeLabels])

  const dismissNode = (idx: number) => {
    setPinnedIds((prev) => prev.filter((_, i) => i !== idx))
    setPinnedLabels((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleGo = async () => {
    const trimmed = brief.trim()
    if (!trimmed) return
    await onGo(trimmed, pinnedIds, pinnedLabels, extraContext.trim() || undefined)
    setBrief('')
    setExtraContext('')
    setPinnedIds([])
    setPinnedLabels([])
  }

  return (
    <section className="brief-panel">
      <h2>What needs fixing?</h2>

      {apiEnabled ? (
        <div className="brief-form">
          {pinnedIds.length > 0 ? (
            <div className="brief-nodes">
              <span className="brief-nodes-label">Starting around:</span>
              <div className="brief-pills">
                {pinnedLabels.map((label, i) => (
                  <span key={pinnedIds[i]} className="brief-pill">
                    {label}
                    <button
                      type="button"
                      className="brief-pill-x"
                      onClick={() => dismissNode(i)}
                      aria-label={`Remove ${label}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <p className="brief-node-hint">
              Click or lasso nodes on the map to point at an area, or just describe in general.
            </p>
          )}

          <textarea
            className="brief-textarea"
            placeholder="Describe what's wrong, in plain terms. The AI will investigate from there."
            value={brief}
            rows={4}
            onChange={(e) => setBrief(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void handleGo()
            }}
          />

          <details className="brief-extra">
            <summary className="brief-extra-toggle">Add context (optional)</summary>
            <textarea
              className="brief-extra-textarea"
              placeholder="Constraints, examples, or background the AI should know…"
              rows={2}
              value={extraContext}
              onChange={(e) => setExtraContext(e.target.value)}
            />
          </details>

          <div className="brief-actions">
            <button
              type="button"
              className="brief-go-btn"
              onClick={() => void handleGo()}
              disabled={!brief.trim() || isGoing}
            >
              {isGoing ? 'Starting…' : 'Start working →'}
            </button>
            <span className="brief-hint">⌘↵</span>
          </div>
        </div>
      ) : (
        <p className="brief-api-note">Start the API to use AI assistance.</p>
      )}
    </section>
  )
}
