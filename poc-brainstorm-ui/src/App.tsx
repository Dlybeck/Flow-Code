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
import { BriefPanel } from './BriefPanel'
import { WorkingPanel, type WorkResult } from './WorkingPanel'
import { DonePanel } from './DonePanel'
import {
  brainstormApiEnabled,
  flowDataUrl,
  goUrl,
  overlayDataUrl,
  undoUrl,
  updateMapUrl,
} from './apiConfig'
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

type SidebarMode = 'brief' | 'working' | 'done'

type GraphCanvasProps = {
  flowDoc: FlowDoc | null
  overlayDoc: OverlayDoc | null
  showFlowUncertainDetail: boolean
  onSelectionChange: (nodeIds: string[], nodeLabels: string[]) => void
  focusNodeIds: string[] | null
  changedNodeIds: Set<string>
  /** True while the AI is re-labeling all nodes — drives cascade scan animation */
  isAnnotating: boolean
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
  onSelectionChange,
  focusNodeIds,
  changedNodeIds,
  isAnnotating,
}: GraphCanvasProps) {
  const [flowCollapsed, setFlowCollapsed] = useState<Set<string>>(() => new Set())
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
    const viewDoc = filterFlowDocUncertainty(flowDoc, showFlowUncertainDetail)
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
      data: { ...n.data, expandable: expandableIds.has(n.id) },
    }))
    let withOverlay = applyOverlayToFlowNodes(nodesLaidOut, overlayDoc)
    if (!showFlowUncertainDetail) {
      withOverlay = withOverlay.map((n) => ({
        ...n,
        data: { ...n.data, hiddenUncertainCount: hiddenBySource.get(n.id) ?? 0 },
      }))
    }

    // Compute per-node scan delay for cascading relabeling animation
    let minY = 0
    let yRange = 1
    if (isAnnotating && withOverlay.length > 0) {
      const ys = withOverlay.map((n) => n.position.y)
      minY = Math.min(...ys)
      const maxY = Math.max(...ys)
      yRange = maxY - minY || 1
    }

    const withDelta = withOverlay.map((n) => {
      const isChanged = changedNodeIds.has(n.id)
      const scanDelay = isAnnotating
        ? Math.round(((n.position.y - minY) / yRange) * 2500) / 1000
        : undefined
      return {
        ...n,
        data: { ...n.data, isChanged, isAnnotating: isAnnotating && isChanged, isRelabeling: isAnnotating, scanDelay },
      }
    })

    return { collapsedDoc, builtNodes: withDelta, builtEdges: fe }
  }, [flowDoc, flowCollapsed, overlayDoc, showFlowUncertainDetail, changedNodeIds, isAnnotating])

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
        const position =
          preserveFlowPositions && old !== undefined ? old.position : n.position
        return { ...n, position }
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

  const onNodeDoubleClick = useCallback((_evt: MouseEvent, node: Node) => {
    const d = node.data as { expandable?: boolean }
    if (!d.expandable) return
    setFlowCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(node.id)) next.delete(node.id)
      else next.add(node.id)
      return next
    })
  }, [])

  const { fitView } = useReactFlow()

  useEffect(() => {
    if (!focusNodeIds || focusNodeIds.length === 0) return
    const focusSet = new Set(focusNodeIds)
    setNodes((prev) => prev.map((n) => ({ ...n, selected: focusSet.has(n.id) })))
    requestAnimationFrame(() => {
      void fitView({
        nodes: focusNodeIds.map((id) => ({ id })),
        padding: 0.4,
        duration: 350,
      })
    })
  }, [focusNodeIds, fitView, setNodes])

  const handleSelectionChange = useCallback(
    ({ nodes: selected }: { nodes: Node[]; edges: Edge[] }) => {
      onSelectionChange(
        selected.map((n) => n.id),
        selected.map((n) => (n.data as { label: string }).label),
      )
    },
    [onSelectionChange],
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
      onSelectionChange={handleSelectionChange}
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
      <FitViewWhenGraphChanges nodeCount={builtNodes.length} nodeIdsKey={fitViewKey} />
      {isAnnotating && <div className="graph-scan-line" aria-hidden />}
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      <Controls showInteractive={false} />

      <Panel position="top-left" className="flow-toolbar">
        <button type="button" onClick={autoLayout}>
          Auto-layout
        </button>
        <p className="hint">
          <strong>Click</strong> or lasso to select nodes.{' '}
          <strong>Double-click</strong> to collapse/expand. Amber dot = hidden uncertain calls.
        </p>
      </Panel>

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
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([])
  const [selectedNodeLabels, setSelectedNodeLabels] = useState<string[]>([])
  const [changedNodeIds, setChangedNodeIds] = useState<Set<string>>(new Set())
  const [isRelabeling, setIsRelabeling] = useState(false)
  const [focusNodeIds, setFocusNodeIds] = useState<string[] | null>(null)

  // Sidebar state machine
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>('brief')
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [workingBrief, setWorkingBrief] = useState('')
  const [workingNodeLabels, setWorkingNodeLabels] = useState<string[]>([])
  const [doneResult, setDoneResult] = useState<WorkResult | null>(null)
  const [isGoing, setIsGoing] = useState(false)

  const reloadInFlightRef = useRef(false)
  const reloadNoticeClearRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollFlowSigRef = useRef<string>('')

  // Build nodeId → label map for DonePanel chips
  const nodeIdToLabel = useMemo(() => {
    const m = new Map<string, string>()
    if (!flowDoc) return m
    for (const n of flowDoc.nodes) {
      if (n.id && n.label) m.set(n.id, n.label)
    }
    return m
  }, [flowDoc])

  const loadOverlayFromResponse = useCallback(async (res: Response) => {
    if (!res.ok) {
      setOverlayDoc(emptyOverlay())
      return
    }
    setOverlayDoc(parseOverlayDoc(await res.json()))
  }, [])

  type LoadMode = 'initial' | 'reload' | 'poll'

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

      if (loud) setFlowHint(null)

      let overlayHttpOk = false
      if (loadMode !== 'poll') {
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
      }

      let nextFlow: FlowDoc | null = null
      let flowOk = false
      let flowStatus: number | undefined
      try {
        const flowUrl = urlWithReloadBuster(flowDataUrl(), loadMode)
        const flowRes = await fetch(flowUrl, fetchOpts)
        flowStatus = flowRes.status
        if (flowRes.ok) {
          const rawJson = await flowRes.json()
          flowOk = true
          if (loud) setFlowHint(null)
          if (loadMode === 'poll') {
            const sig = JSON.stringify(rawJson)
            if (sig !== pollFlowSigRef.current) {
              pollFlowSigRef.current = sig
              nextFlow = parseFlowDoc(rawJson)
            }
          } else {
            nextFlow = parseFlowDoc(rawJson)
          }
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
        if (loud && brainstormApiEnabled()) {
          setFlowHint(
            'Could not load GET /flow (is the API running?). Try npm run dev:studio from repo root.',
          )
        }
      }

      if (loadMode === 'poll') {
        if (nextFlow !== null) setFlowDoc(nextFlow)
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
          setReloadNotice(`Reloaded ${timeStr} — execution map and overlay refreshed.`)
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

  const handleUpdateMap = useCallback(async () => {
    setIsRelabeling(true)
    try {
      await fetch(updateMapUrl(), { method: 'POST' })
      await reloadGraphData()
    } finally {
      setIsRelabeling(false)
    }
  }, [reloadGraphData])

  useEffect(() => {
    return () => {
      if (reloadNoticeClearRef.current) clearTimeout(reloadNoticeClearRef.current)
    }
  }, [])

  const handleSelectionChange = useCallback(
    (nodeIds: string[], nodeLabels: string[]) => {
      setSelectedNodeIds(nodeIds)
      setSelectedNodeLabels(nodeLabels)
    },
    [],
  )

  const handleFocusNodes = useCallback((nodeIds: string[]) => {
    setFocusNodeIds([...nodeIds])
  }, [])

  // ─── Work session handlers ─────────────────────────────────────────────────

  const handleGo = useCallback(
    async (brief: string, nodeIds: string[], nodeLabels: string[], extraContext?: string) => {
      setIsGoing(true)
      try {
        const res = await fetch(goUrl(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ brief, node_ids: nodeIds, node_labels: nodeLabels, extra_context: extraContext ?? '' }),
        })
        if (!res.ok) {
          const err = (await res.json().catch(() => ({}))) as { detail?: string }
          alert(`Could not start: ${err.detail ?? res.statusText}`)
          return
        }
        const { session_id } = (await res.json()) as { session_id: string }
        setWorkingBrief(brief)
        setWorkingNodeLabels(nodeLabels)
        setActiveSessionId(session_id)
        setSidebarMode('working')
      } catch (e) {
        alert(`Error: ${e instanceof Error ? e.message : String(e)}`)
      } finally {
        setIsGoing(false)
      }
    },
    [],
  )

  const handleWorkingDone = useCallback((result: WorkResult) => {
    setDoneResult(result)
    setChangedNodeIds(new Set(result.changed_node_ids))
    setSidebarMode('done')
  }, [])

  const handleCancel = useCallback((prefilledBrief: string) => {
    setActiveSessionId(null)
    setWorkingBrief(prefilledBrief)
    setSidebarMode('brief')
  }, [])

  const handleResolve = useCallback(() => {
    setDoneResult(null)
    setChangedNodeIds(new Set())
    setActiveSessionId(null)
    setSidebarMode('brief')
  }, [])

  const handleRetry = useCallback(
    async (what: string) => {
      if (!doneResult) return
      setSidebarMode('brief')
      // Pre-fill brief from the retry text and re-submit with same node context
      // (user will hit "Start working →" manually, or we auto-go)
      setWorkingBrief(what)
      // Auto-go: reconstruct node ids from the previous done result
      await handleGo(what, doneResult.changed_node_ids, [])
    },
    [doneResult, handleGo],
  )

  const handleUndo = useCallback(async () => {
    if (!activeSessionId) return
    try {
      await fetch(undoUrl(activeSessionId), { method: 'POST' })
    } catch {
      // best-effort
    }
    setDoneResult(null)
    setChangedNodeIds(new Set())
    setActiveSessionId(null)
    setSidebarMode('brief')
  }, [activeSessionId])

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Execution map</h1>
        <div className="app-status">
          {brainstormApiEnabled() ? (
            <span className="status-badge api">API</span>
          ) : (
            <span className="status-badge static">Static</span>
          )}
          {import.meta.env.DEV ? <span className="status-badge dev">Dev</span> : null}
        </div>
        {flowDoc ? (
          <label className="flow-uncertain-toggle">
            <input
              type="checkbox"
              checked={showFlowUncertainDetail}
              onChange={(e) => setShowFlowUncertainDetail(e.target.checked)}
            />
            Uncertain detail
          </label>
        ) : null}
        {flowHint ? <p className="flow-hint">{flowHint}</p> : null}
      </header>

      <div className="flow-wrap">
        <ReactFlowProvider>
          <GraphCanvas
            flowDoc={flowDoc}
            overlayDoc={overlayDoc}
            showFlowUncertainDetail={showFlowUncertainDetail}
            onSelectionChange={handleSelectionChange}
            focusNodeIds={focusNodeIds}
            changedNodeIds={changedNodeIds}
            isAnnotating={isRelabeling}
          />
        </ReactFlowProvider>
      </div>

      <aside className="side-panel">
        <p className="side-hero">
          Your codebase as a map. Select an area, describe the problem, and the AI will investigate and fix it.
        </p>

        {sidebarMode === 'working' && activeSessionId ? (
          <WorkingPanel
            sessionId={activeSessionId}
            briefSummary={workingBrief}
            nodeLabels={workingNodeLabels}
            onCancel={handleCancel}
            onDone={handleWorkingDone}
            onPhaseChange={(_phase) => setIsRelabeling(false)}
          />
        ) : sidebarMode === 'done' && doneResult ? (
          <DonePanel
            result={doneResult}
            nodeIdToLabel={nodeIdToLabel}
            onResolve={handleResolve}
            onRetry={(what) => void handleRetry(what)}
            onUndo={() => void handleUndo()}
            canUndo={activeSessionId !== null}
            onFocusNodes={handleFocusNodes}
            onUpdateMap={handleUpdateMap}
          />
        ) : (
          <BriefPanel
            selectedNodeIds={selectedNodeIds}
            selectedNodeLabels={selectedNodeLabels}
            apiEnabled={brainstormApiEnabled()}
            onGo={handleGo}
            isGoing={isGoing}
          />
        )}

        <section className="legend-section">
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
              <span className="legend-hidden-uncertain-dot" /> Hidden uncertain calls
              <span className="legend-muted"> (detail off)</span>
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
          <p className="reload-notice" role="status" aria-live="polite">
            {reloadNotice}
          </p>
        ) : null}

        {brainstormApiEnabled() ? (
          <details className="side-details">
            <summary>Developer tools</summary>
            <UpdateMapPanel onDone={triggerReload} />
            <ApplyBundlePanel onApplied={triggerReload} />
          </details>
        ) : null}
      </aside>
    </div>
  )
}
