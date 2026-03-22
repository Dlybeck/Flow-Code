import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Edge,
  type Node,
  Panel,
  ReactFlow,
  SelectionMode,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { BoundaryNode, FeatureNode, SurfaceNode } from './CustomNodes'
import { layoutVisibleGraph } from './layoutGraph'
import { applyOverlayToFlowNodes } from './mergeOverlay'
import type { OverlayDoc } from './overlayTypes'
import { emptyOverlay, parseOverlayDoc } from './overlayTypes'
import { ApplyBundlePanel } from './ApplyBundlePanel'
import { UpdateMapPanel } from './UpdateMapPanel'
import { brainstormApiEnabled, flowDataUrl, overlayDataUrl } from './apiConfig'
import {
  applyFlowCollapse,
  buildFlowGraph,
  filterFlowDocUncertainty,
  flowHiddenUncertainCounts,
  flowIdsWithContainsChildren,
  flowVisibleDocSignature,
} from './flowGraph'
import type { FlowDoc } from './flowTypes'
import { parseFlowDoc } from './flowTypes'
import './App.css'

const nodeTypes = {
  surface: SurfaceNode,
  feature: FeatureNode,
  boundary: BoundaryNode,
}

type GraphCanvasProps = {
  flowDoc: FlowDoc | null
  overlayDoc: OverlayDoc | null
  /** When false, hide boundary node + dashed uncertain calls; nodes show a dot if some were hidden. */
  showFlowUncertainDetail: boolean
}

function FitViewWhenGraphChanges({
  nodeCount,
  nodeIdsKey,
}: {
  nodeCount: number
  nodeIdsKey: string
}) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    if (nodeCount === 0) return
    const id = requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 200 })
    })
    return () => cancelAnimationFrame(id)
  }, [nodeCount, nodeIdsKey, fitView])
  return null
}

function GraphCanvas({
  flowDoc,
  overlayDoc,
  showFlowUncertainDetail,
}: GraphCanvasProps) {
  const [testText, setTestText] = useState<string | null>(null)
  const [flowCollapsed, setFlowCollapsed] = useState<Set<string>>(
    () => new Set(),
  )
  const flowStructSigRef = useRef('')

  useEffect(() => {
    setFlowCollapsed(new Set())
  }, [flowDoc])

  const { collapsedDoc, builtNodes, builtEdges } = useMemo(() => {
      if (!flowDoc) {
        return {
          collapsedDoc: null as FlowDoc | null,
          builtNodes: [] as Node[],
          builtEdges: [] as Edge[],
        }
      }
      const viewDoc = filterFlowDocUncertainty(
        flowDoc,
        showFlowUncertainDetail,
      )
      const hiddenBySource = showFlowUncertainDetail
        ? new Map<string, number>()
        : flowHiddenUncertainCounts(flowDoc)
      const collapsedDoc = applyFlowCollapse(viewDoc, flowCollapsed)
      const expandableIds = flowIdsWithContainsChildren(viewDoc)
      const { nodes: fn, edges: fe } = buildFlowGraph(collapsedDoc)
      const posMap = layoutVisibleGraph(fn, fe)
      const nodesLaidOut = fn.map((n) => ({
        ...n,
        position: posMap.get(n.id) ?? n.position,
        data: {
          ...n.data,
          expandable: expandableIds.has(n.id),
        },
      }))
      let withOverlay = applyOverlayToFlowNodes(nodesLaidOut, overlayDoc)
      if (!showFlowUncertainDetail) {
        withOverlay = withOverlay.map((n) => ({
          ...n,
          data: {
            ...n.data,
            hiddenUncertainCount: hiddenBySource.get(n.id) ?? 0,
          },
        }))
      }
      return {
        collapsedDoc,
        builtNodes: withOverlay,
        builtEdges: fe,
      }
    }, [
      flowDoc,
      flowCollapsed,
      overlayDoc,
      showFlowUncertainDetail,
    ])

  const collapsedKey = useMemo(
    () => [...flowCollapsed].sort().join('|'),
    [flowCollapsed],
  )

  const fitViewKey = useMemo(() => {
    const ids = builtNodes.map((n) => n.id).join('|')
    const eids = builtEdges.map((e) => e.id).join('|')
    return `flow:${showFlowUncertainDetail}:${collapsedKey}:${ids}:${eids}`
  }, [builtEdges, builtNodes, collapsedKey, showFlowUncertainDetail])

  const [nodes, setNodes, onNodesChange] = useNodesState(builtNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(builtEdges)

  useLayoutEffect(() => {
    const flowSig =
      collapsedDoc && collapsedDoc.nodes.length > 0
        ? flowVisibleDocSignature(collapsedDoc)
        : ''
    let preserveFlowPositions = false
    if (flowSig !== '') {
      if (flowSig === flowStructSigRef.current) {
        preserveFlowPositions = true
      } else {
        flowStructSigRef.current = flowSig
      }
    }

    setNodes((prev) => {
      const prevMap = new Map(prev.map((n) => [n.id, n]))
      return builtNodes.map((n: Node) => {
        const old = prevMap.get(n.id)
        let position: { x: number; y: number }
        if (preserveFlowPositions && old !== undefined) {
          position = old.position
        } else {
          position = n.position
        }
        return {
          ...n,
          position,
          data: {
            ...n.data,
            onTest: (e: MouseEvent) => {
              e.stopPropagation()
              const d = n.data as {
                label?: string
                subtitle?: string
                rawLabel?: string
                rawSubtitle?: string
              }
              setTestText(
                [
                  `▸ ${d.label ?? n.id}`,
                  `  id: ${n.id}`,
                  d.rawLabel ? `  qualified: ${d.rawLabel}` : '',
                  d.subtitle ? `  ${d.subtitle}` : '',
                  d.rawSubtitle && d.rawSubtitle !== d.subtitle
                    ? `  (technical) ${d.rawSubtitle}`
                    : '',
                  '',
                  '  (execution map — contains + calls)',
                ]
                  .filter(Boolean)
                  .join('\n'),
              )
            },
          },
        }
      })
    })
    setEdges(builtEdges)
  }, [builtEdges, builtNodes, collapsedDoc, setEdges, setNodes])

  const autoLayout = useCallback(() => {
    setNodes((nds) => {
      const posMap = layoutVisibleGraph(nds, edges)
      return nds.map((n) => {
        const p = posMap.get(n.id)
        if (!p) return n
        return { ...n, position: p }
      })
    })
  }, [edges, setNodes])

  const onNodeDoubleClick = useCallback(
    (_evt: MouseEvent, node: Node) => {
      const d = node.data as { expandable?: boolean }
      if (!d.expandable) return
      setFlowCollapsed((prev) => {
        const next = new Set(prev)
        if (next.has(node.id)) next.delete(node.id)
        else next.add(node.id)
        return next
      })
    },
    [],
  )

  if (!flowDoc) {
    return (
      <div className="flow-empty">
        <p>No execution map loaded.</p>
        <p className="hint">
          Add <code>public/flow.json</code> (run <code>npm run index:golden</code>) or use the API
          and <code>POST /reindex</code>.
        </p>
      </div>
    )
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeDoubleClick={onNodeDoubleClick}
      nodeTypes={nodeTypes}
      minZoom={0.35}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable={false}
      deleteKeyCode={null}
      edgesReconnectable={false}
      edgesFocusable={false}
      elementsSelectable
      selectionOnDrag
      panOnDrag={[1, 2]}
      selectionMode={SelectionMode.Partial}
      multiSelectionKeyCode="Shift"
      panActivationKeyCode="Space"
    >
      <FitViewWhenGraphChanges
        nodeCount={builtNodes.length}
        nodeIdsKey={fitViewKey}
      />
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      <Controls showInteractive={false} />

      <Panel position="top-left" className="flow-toolbar">
        <button type="button" onClick={autoLayout}>
          Auto-layout open
        </button>
        <p className="hint">
          <strong>Double-click</strong> a function to collapse or expand nested functions (contains).
          Gray = contains, blue = resolved calls. Amber dot = hidden uncertain calls (detail off).
        </p>
      </Panel>

      {testText ? (
        <Panel position="top-right" className="test-panel">
          <pre>{testText}</pre>
          <button
            type="button"
            className="close-test"
            onClick={() => setTestText(null)}
          >
            Close
          </button>
        </Panel>
      ) : null}

      <MiniMap
        nodeStrokeWidth={2}
        zoomable
        pannable
        style={{ background: 'var(--bg-panel)' }}
      />
    </ReactFlow>
  )
}

export default function App() {
  const [showFlowUncertainDetail, setShowFlowUncertainDetail] = useState(false)
  const [flowDoc, setFlowDoc] = useState<FlowDoc | null>(null)
  const [overlayDoc, setOverlayDoc] = useState<OverlayDoc | null>(null)
  const [flowHint, setFlowHint] = useState<string | null>(null)
  const [reloadBusy, setReloadBusy] = useState(false)
  const [reloadNotice, setReloadNotice] = useState<string | null>(null)
  const reloadInFlightRef = useRef(false)
  const reloadNoticeClearRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  )

  const loadOverlayFromResponse = useCallback(async (res: Response) => {
    if (!res.ok) {
      setOverlayDoc(emptyOverlay())
      return
    }
    setOverlayDoc(parseOverlayDoc(await res.json()))
  }, [])

  type LoadMode = 'initial' | 'reload' | 'poll'

  /** Avoid stale static `public/*.json` when the user explicitly reloads. */
  function urlWithReloadBuster(url: string, mode: LoadMode): string {
    if (mode !== 'reload') return url
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}cb=${Date.now()}`
  }

  type BundleReloadSummary = {
    flowOk: boolean
    flowStatus?: number
    overlayHttpOk: boolean
  }

  const loadGraphBundle = useCallback(
    async (loadMode: LoadMode): Promise<BundleReloadSummary | undefined> => {
      const loud = loadMode !== 'poll'
      const fetchOpts: RequestInit = { cache: 'no-store' }

      if (loud) {
        setFlowHint(null)
      }

      let overlayHttpOk = false
      try {
        const ovrBase = overlayDataUrl()
        let ovrUrl =
          brainstormApiEnabled() && ovrBase.includes('/api/brainstorm')
            ? `${ovrBase}?cb=${Date.now()}`
            : ovrBase
        ovrUrl = urlWithReloadBuster(ovrUrl, loadMode)
        const ovrRes = await fetch(ovrUrl, fetchOpts)
        overlayHttpOk = ovrRes.ok
        await loadOverlayFromResponse(ovrRes)
      } catch {
        setOverlayDoc(emptyOverlay())
      }

      let nextFlow: FlowDoc | null = null
      let flowOk = false
      let flowStatus: number | undefined
      try {
        const flowUrl = urlWithReloadBuster(flowDataUrl(), loadMode)
        const flowRes = await fetch(flowUrl, fetchOpts)
        flowStatus = flowRes.status
        if (flowRes.ok) {
          nextFlow = parseFlowDoc(await flowRes.json())
          flowOk = true
          if (loud) setFlowHint(null)
        } else if (loud) {
          if (brainstormApiEnabled() && flowRes.status === 404) {
            setFlowHint(
              'No execution map on the API yet (GET /flow → 404). Run npm run dev:studio or npm run index:golden, or POST /reindex.',
            )
          } else {
            setFlowHint(null)
          }
        }
      } catch {
        if (loud) {
          if (brainstormApiEnabled()) {
            setFlowHint(
              'Could not load GET /flow (is the API running?). Try npm run dev:studio from repo root.',
            )
          }
        }
      }

      if (loadMode === 'poll') {
        if (flowOk) setFlowDoc(nextFlow)
        return undefined
      }
      setFlowDoc(nextFlow)
      return { flowOk, flowStatus, overlayHttpOk }
    },
    [loadOverlayFromResponse],
  )

  useEffect(() => {
    void loadGraphBundle('initial')
  }, [loadGraphBundle])

  useEffect(() => {
    if (!import.meta.env.DEV) return undefined
    const ms = 4000
    const id = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      void loadGraphBundle('poll')
    }, ms)
    return () => window.clearInterval(id)
  }, [loadGraphBundle])

  const reloadGraphData = useCallback(async () => {
    if (reloadInFlightRef.current) return
    reloadInFlightRef.current = true
    setReloadBusy(true)
    setReloadNotice(null)
    if (reloadNoticeClearRef.current) {
      clearTimeout(reloadNoticeClearRef.current)
      reloadNoticeClearRef.current = null
    }
    try {
      const summary = await loadGraphBundle('reload')
      const timeStr = new Date().toLocaleTimeString(undefined, {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
      })
      if (summary) {
        if (summary.flowOk) {
          setReloadNotice(
            `Reloaded ${timeStr} — execution map and overlay refreshed.`,
          )
        } else {
          const why =
            summary.flowStatus === 404
              ? 'flow not found (404)'
              : summary.flowStatus
                ? `flow HTTP ${summary.flowStatus}`
                : 'flow request failed'
          setReloadNotice(
            `Reloaded ${timeStr} — ${why}. Overlay ${summary.overlayHttpOk ? 'OK' : 'unavailable'}.`,
          )
        }
      }
    } finally {
      reloadInFlightRef.current = false
      setReloadBusy(false)
    }
    reloadNoticeClearRef.current = setTimeout(() => {
      setReloadNotice(null)
      reloadNoticeClearRef.current = null
    }, 8000)
  }, [loadGraphBundle])

  const triggerReload = useCallback(() => {
    void reloadGraphData()
  }, [reloadGraphData])

  useEffect(() => {
    return () => {
      if (reloadNoticeClearRef.current) {
        clearTimeout(reloadNoticeClearRef.current)
      }
    }
  }, [])

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="explainer-link">
            <a href="/repo-model.html" target="_blank" rel="noreferrer">
              Visual: disk + graph + shared code →
            </a>
          </p>
          <h1>Execution map</h1>
          <p className="sub">
            AI-derived <strong>execution flow</strong> (contains + calls). Friendly labels from{' '}
            <strong>overlay</strong> when ids match.{' '}
            {brainstormApiEnabled() ? (
              <span className="sub-meta">API-backed JSON.</span>
            ) : (
              <span className="sub-meta">
                Static <code>public/flow.json</code> + <code>overlay.json</code>.
              </span>
            )}
            {import.meta.env.DEV ? (
              <span className="sub-meta">
                {' '}
                Dev auto-refresh ~4s.
              </span>
            ) : null}
          </p>
          <div className="mode-bar">
            {flowDoc ? (
              <label className="flow-uncertain-toggle">
                <input
                  type="checkbox"
                  checked={showFlowUncertainDetail}
                  onChange={(e) =>
                    setShowFlowUncertainDetail(e.target.checked)
                  }
                />
                Show uncertain detail
              </label>
            ) : null}
          </div>
          {flowHint ? <p className="flow-hint">{flowHint}</p> : null}
        </div>
      </header>

      <div className="flow-wrap">
        <ReactFlowProvider>
          <GraphCanvas
            flowDoc={flowDoc}
            overlayDoc={overlayDoc}
            showFlowUncertainDetail={showFlowUncertainDetail}
          />
        </ReactFlowProvider>
      </div>

      <aside className="side-panel">
        <div className="side-chat-slot" aria-label="Chat placeholder">
          <p className="side-chat-placeholder">
            Assistant chat will go here — use the canvas for now.
          </p>
        </div>

        <section>
          <h2>Legend</h2>
          <div className="legend legend-compact">
            <div className="legend-row">
              <span className="swatch surface" /> Entry
            </div>
            <div className="legend-row">
              <span className="swatch feature" /> Function
            </div>
            <div className="legend-row">
              <span className="swatch boundary" /> Uncertain boundary
            </div>
            <div className="legend-row">
              <span className="legend-edge solid" /> Contains
            </div>
            <div className="legend-row">
              <span className="legend-edge call" /> Call (resolved)
            </div>
            <div className="legend-row">
              <span className="legend-edge uncertain" /> Call (uncertain)
            </div>
            <div className="legend-row">
              <span className="legend-hidden-uncertain-dot" /> Hidden unboxed calls
              <span className="legend-muted"> (hover dot; detail off)</span>
            </div>
          </div>
        </section>

        <button
          type="button"
          className="side-reload-btn"
          onClick={triggerReload}
          disabled={reloadBusy}
          aria-busy={reloadBusy}
        >
          {reloadBusy ? 'Reloading…' : 'Reload map + overlay'}
        </button>
        {reloadNotice ? (
          <p
            className="reload-notice"
            role="status"
            aria-live="polite"
          >
            {reloadNotice}
          </p>
        ) : null}

        {brainstormApiEnabled() ? (
          <details className="side-details">
            <summary>API tools</summary>
            <UpdateMapPanel onDone={triggerReload} />
            <ApplyBundlePanel onApplied={triggerReload} />
          </details>
        ) : null}
      </aside>
    </div>
  )
}
