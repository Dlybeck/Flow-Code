import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
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

import {
  CapabilityNode,
  CodeNode,
  FeatureNode,
  FloatingNode,
  SurfaceNode,
} from './CustomNodes'
import { layoutVisibleGraph, reapplyDraggedSubtrees } from './layoutGraph'
import { applyOverlayToFlowNodes, applyOverlayToNodes } from './mergeOverlay'
import { buildGraph } from './mockGraph'
import { buildMockTestReport } from './mockTests'
import type { OverlayDoc } from './overlayTypes'
import { emptyOverlay, parseOverlayDoc } from './overlayTypes'
import { ApplyBundlePanel } from './ApplyBundlePanel'
import { UpdateMapPanel } from './UpdateMapPanel'
import {
  brainstormApiEnabled,
  flowDataUrl,
  overlayDataUrl,
  rawDataUrl,
} from './apiConfig'
import { buildFlowGraph } from './flowGraph'
import type { FlowDoc } from './flowTypes'
import { parseFlowDoc } from './flowTypes'
import { ROOT_ID, buildRawGraph, defaultRawExpanded } from './rawGraph'
import type { RawIndexDoc } from './rawTypes'
import { effectiveIndexMeta, parseRawIndexDoc } from './rawTypes'
import './App.css'

const nodeTypes = {
  capability: CapabilityNode,
  surface: SurfaceNode,
  feature: FeatureNode,
  code: CodeNode,
  floating: FloatingNode,
}

type GraphMode = 'flow' | 'mock' | 'raw'

type GraphCanvasProps = {
  graphMode: GraphMode
  flowDoc: FlowDoc | null
  rawDoc: RawIndexDoc | null
  overlayDoc: OverlayDoc | null
}

/**
 * `fitView` on the ReactFlow element only runs once on mount; when `nodes` are filled
 * in a later effect (common for flow/RAW), the viewport stays wrong until this runs.
 */
function FitViewWhenGraphChanges({
  graphMode,
  nodeCount,
  nodeIdsKey,
}: {
  graphMode: GraphMode
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
  }, [graphMode, nodeCount, nodeIdsKey, fitView])
  return null
}

function GraphCanvas({ graphMode, flowDoc, rawDoc, overlayDoc }: GraphCanvasProps) {
  const [mockExpanded, setMockExpanded] = useState<Set<string>>(
    () => new Set(['ui']),
  )
  const [rawExpanded, setRawExpanded] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    if (rawDoc) {
      setRawExpanded(defaultRawExpanded(rawDoc))
    }
  }, [rawDoc])

  const [testText, setTestText] = useState<string | null>(null)

  /** Previous frame positions (after drag); read in useMemo without listing as a dep */
  const displayedSnapshotRef = useRef<Pick<Node, 'id' | 'position'>[]>([])

  const { nodes: builtNodes, edges: builtEdges } = useMemo(() => {
    if (graphMode === 'flow') {
      if (!flowDoc) {
        return { nodes: [] as Node[], edges: [] as Edge[] }
      }
      const { nodes: fn, edges: fe } = buildFlowGraph(flowDoc)
      const posMap = layoutVisibleGraph(fn, fe)
      let nodesLaidOut = fn.map((n) => ({
        ...n,
        position: posMap.get(n.id) ?? n.position,
      }))
      /* eslint-disable-next-line react-hooks/refs */
      const dragSnapshot = displayedSnapshotRef.current
      nodesLaidOut = reapplyDraggedSubtrees(nodesLaidOut, fe, dragSnapshot)
      const withOverlay = applyOverlayToFlowNodes(nodesLaidOut, overlayDoc)
      return { nodes: withOverlay, edges: fe }
    }
    if (graphMode === 'mock') {
      const { nodes: mockNodes, edges: mockEdges } = buildGraph(mockExpanded)
      /* Same subtree shift as RAW: merge keeps dragged parent pos while children came from fresh layout. */
      /* eslint-disable-next-line react-hooks/refs */
      const dragSnapshot = displayedSnapshotRef.current
      return {
        nodes: reapplyDraggedSubtrees(mockNodes, mockEdges, dragSnapshot),
        edges: mockEdges,
      }
    }
    if (!rawDoc) {
      return { nodes: [] as Node[], edges: [] as Edge[] }
    }
    const { nodes: rawNodes, edges: rawEdges } = buildRawGraph(
      rawDoc,
      rawExpanded,
    )
    const posMap = layoutVisibleGraph(rawNodes, rawEdges)
    let nodesLaidOut = rawNodes.map((n) => ({
      ...n,
      position: posMap.get(n.id) ?? n.position,
    }))
    /* Ref = previous committed positions (synced in useEffect); omitting from deps avoids layout loops. */
    /* eslint-disable-next-line react-hooks/refs */
    const dragSnapshot = displayedSnapshotRef.current
    nodesLaidOut = reapplyDraggedSubtrees(nodesLaidOut, rawEdges, dragSnapshot)
    const withOverlay = applyOverlayToNodes(nodesLaidOut, overlayDoc)
    return { nodes: withOverlay, edges: rawEdges }
  }, [graphMode, mockExpanded, rawDoc, rawExpanded, overlayDoc])

  const [nodes, setNodes, onNodesChange] = useNodesState(builtNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(builtEdges)

  useEffect(() => {
    displayedSnapshotRef.current = nodes.map((n) => ({
      id: n.id,
      position: { ...n.position },
    }))
  }, [nodes])

  useEffect(() => {
    setEdges(builtEdges)
  }, [builtEdges, setEdges])

  useEffect(() => {
    setNodes((prev) => {
      const prevMap = new Map(prev.map((n) => [n.id, n]))
      return builtNodes.map((n: Node) => {
        const old = prevMap.get(n.id)
        const position =
          graphMode === 'raw' || graphMode === 'flow'
            ? n.position
            : (old?.position ?? n.position)
        return {
          ...n,
          position,
          data: {
            ...n.data,
            onTest: (e: MouseEvent) => {
              e.stopPropagation()
              if (graphMode === 'mock') {
                setTestText(buildMockTestReport(n.id, mockExpanded))
              } else if (graphMode === 'flow') {
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
                    '  (execution map — static contains + calls)',
                  ]
                    .filter(Boolean)
                    .join('\n'),
                )
              } else {
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
                    d.rawLabel ? `  indexed name: ${d.rawLabel}` : '',
                    d.subtitle ? `  ${d.subtitle}` : '',
                    d.rawSubtitle && d.rawSubtitle !== d.subtitle
                      ? `  (indexed) ${d.rawSubtitle}`
                      : '',
                    '',
                    '  (RAW — run tests via raw-indexer validate)',
                  ]
                    .filter(Boolean)
                    .join('\n'),
                )
              }
            },
          },
        }
      })
    })
  }, [builtNodes, graphMode, mockExpanded, rawExpanded, setNodes])

  const autoLayout = useCallback(() => {
    setNodes((nds) => {
      const posMap = layoutVisibleGraph(nds, edges)
      return nds.map((n) => {
        if (n.type === 'floating') return n
        const p = posMap.get(n.id)
        if (!p) return n
        return { ...n, position: p }
      })
    })
  }, [edges, setNodes])

  const onNodeDoubleClick = useCallback(
    (_evt: MouseEvent, node: Node) => {
      if (graphMode === 'flow') {
        return
      }
      if (graphMode === 'raw') {
        const id = node.id
        if (
          id !== ROOT_ID &&
          !id.startsWith('dir:') &&
          !id.startsWith('file:')
        ) {
          return
        }
        const d = node.data as { expandable?: boolean }
        if (!d.expandable) return
        setRawExpanded((prev) => {
          const next = new Set(prev)
          if (next.has(id)) next.delete(id)
          else next.add(id)
          return next
        })
        return
      }

      const d = node.data as { expandable?: boolean }
      if (!d.expandable) return
      setMockExpanded((prev) => {
        const next = new Set(prev)
        if (next.has(node.id)) next.delete(node.id)
        else next.add(node.id)
        return next
      })
    },
    [graphMode],
  )

  if (graphMode === 'flow' && !flowDoc) {
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

  if (graphMode === 'raw' && !rawDoc) {
    return (
      <div className="flow-empty">
        <p>No RAW document loaded.</p>
      </div>
    )
  }

  const fitViewKey = `${graphMode}:${nodes.map((n) => n.id).join('|')}`

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
        graphMode={graphMode}
        nodeCount={nodes.length}
        nodeIdsKey={fitViewKey}
      />
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      <Controls showInteractive={false} />

      <Panel position="top-left" className="flow-toolbar">
        <button type="button" onClick={autoLayout}>
          Auto-layout open
        </button>
        <p className="hint">
          {graphMode === 'flow'
            ? 'Main view: function-level execution map. Gray edges = contains (nesting); blue = resolved calls. Route-style nodes = entrypoints. Friendly titles from overlay match RAW symbol ids when present.'
            : graphMode === 'raw'
              ? 'Double-click a directory to expand/collapse its children (the folder stays). Double-click a file to show/hide symbols. Layout is auto-applied from tree edges; dashed = internal imports.'
              : 'Drag on empty canvas to box-select. Shift+click to add to selection. Drag selected group together. Middle / right-drag to pan (or Space+drag).'}
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
  const [graphMode, setGraphMode] = useState<GraphMode>('flow')
  const [flowDoc, setFlowDoc] = useState<FlowDoc | null>(null)
  const [rawDoc, setRawDoc] = useState<RawIndexDoc | null>(null)
  const [overlayDoc, setOverlayDoc] = useState<OverlayDoc | null>(null)
  const [rawErr, setRawErr] = useState<string | null>(null)
  const [flowHint, setFlowHint] = useState<string | null>(null)

  const loadOverlayFromResponse = useCallback(async (res: Response) => {
    if (!res.ok) {
      setOverlayDoc(emptyOverlay())
      return
    }
    setOverlayDoc(parseOverlayDoc(await res.json()))
  }, [])

  type LoadMode = 'initial' | 'reload' | 'poll'

  const loadGraphBundle = useCallback(
    async (loadMode: LoadMode) => {
      const loud = loadMode !== 'poll'
      const fetchOpts: RequestInit = { cache: 'no-store' }

      if (loud) {
        setRawErr(null)
        setFlowHint(null)
      }

      try {
        const rawRes = await fetch(rawDataUrl(), fetchOpts)
        if (!rawRes.ok) {
          if (loud) {
            throw new Error(`raw index HTTP ${rawRes.status}`)
          }
          return
        }
        const doc = parseRawIndexDoc(await rawRes.json())
        setRawDoc(doc)
        if (loud) setRawErr(null)

        try {
          const ovrRes = await fetch(overlayDataUrl(), fetchOpts)
          await loadOverlayFromResponse(ovrRes)
        } catch {
          setOverlayDoc(emptyOverlay())
        }

        let nextFlow: FlowDoc | null | undefined
        let flowOk = false
        try {
          const flowRes = await fetch(flowDataUrl(), fetchOpts)
          if (flowRes.ok) {
            nextFlow = parseFlowDoc(await flowRes.json())
            flowOk = true
            if (loud) setFlowHint(null)
          } else if (loud) {
            nextFlow = null
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
            nextFlow = null
            if (brainstormApiEnabled()) {
              setFlowHint(
                'Could not load GET /flow (is the API running?). Try npm run dev:studio from repo root.',
              )
            }
          }
        }

        if (loadMode === 'poll') {
          if (flowOk && nextFlow !== undefined) setFlowDoc(nextFlow)
        } else {
          setFlowDoc(nextFlow ?? null)
          setGraphMode(nextFlow ? 'flow' : 'raw')
        }
      } catch (e) {
        if (loud) {
          setRawErr(
            e instanceof Error
              ? e.message
              : `Could not load ${rawDataUrl()}`,
          )
        }
      }
    },
    [loadOverlayFromResponse],
  )

  useEffect(() => {
    void loadGraphBundle('initial')
  }, [loadGraphBundle])

  /** Dev-only: pick up new public/*.json or API reindex without clicking Reload. */
  useEffect(() => {
    if (!import.meta.env.DEV) return undefined
    const ms = 4000
    const id = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      void loadGraphBundle('poll')
    }, ms)
    return () => window.clearInterval(id)
  }, [loadGraphBundle])

  const onPickRawFile = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = () => {
        try {
          const text = String(reader.result ?? '')
          const doc = parseRawIndexDoc(JSON.parse(text))
          setRawDoc(doc)
          setGraphMode('raw')
          setRawErr(null)
        } catch (err) {
          setRawErr(err instanceof Error ? err.message : 'Invalid JSON')
        }
      }
      reader.readAsText(file)
      e.target.value = ''
    },
    [],
  )

  const onPickFlowFile = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const text = String(reader.result ?? '')
        const doc = parseFlowDoc(JSON.parse(text))
        setFlowDoc(doc)
        setGraphMode('flow')
        setRawErr(null)
      } catch (err) {
        setRawErr(err instanceof Error ? err.message : 'Invalid flow JSON')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }, [])

  const reloadGraphData = useCallback(() => {
    void loadGraphBundle('reload')
  }, [loadGraphBundle])

  const onPickOverlayFile = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = () => {
        try {
          const text = String(reader.result ?? '')
          setOverlayDoc(parseOverlayDoc(JSON.parse(text)))
        } catch (err) {
          setRawErr(
            err instanceof Error ? err.message : 'Invalid overlay JSON',
          )
        }
      }
      reader.readAsText(file)
      e.target.value = ''
    },
    [],
  )

  const indexMetaView = rawDoc ? effectiveIndexMeta(rawDoc) : null

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="explainer-link">
            <a href="/repo-model.html" target="_blank" rel="noreferrer">
              Visual: disk + graph + shared code →
            </a>
          </p>
          <h1>Brainstorm POC — execution map</h1>
          <p className="sub">
            <strong>Flow</strong> is the primary view (function-level contains + calls).{' '}
            <strong>RAW</strong> is the filesystem/symbol index; <strong>overlay</strong> adds
            friendly labels (by RAW symbol id, including on flow nodes when{' '}
            <code>raw_symbol_id</code> is set).{' '}
            {brainstormApiEnabled() ? (
              <>
                API: <code>{flowDataUrl()}</code>, <code>{rawDataUrl()}</code>,{' '}
                <code>{overlayDataUrl()}</code> (Vite → FastAPI).{' '}
              </>
            ) : (
              <>
                Static: <code>public/flow.json</code>, <code>raw.json</code>,{' '}
                <code>overlay.json</code>.{' '}
              </>
            )}
            <strong>Mock</strong> uses <code>src/mockGraph.ts</code>.
            {import.meta.env.DEV ? (
              <>
                {' '}
                <em>Dev:</em> graph data refetches every 4s when this tab is visible (no
                reload button needed after <code>index:golden</code> or reindex).
              </>
            ) : null}
          </p>
          <div className="mode-bar">
            <label>
              <input
                type="radio"
                name="mode"
                checked={graphMode === 'flow'}
                onChange={() => setGraphMode('flow')}
                disabled={!flowDoc}
              />
              Flow (execution)
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                checked={graphMode === 'raw'}
                onChange={() => setGraphMode('raw')}
                disabled={!rawDoc}
              />
              RAW (index)
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                checked={graphMode === 'mock'}
                onChange={() => setGraphMode('mock')}
              />
              Mock
            </label>
            <button type="button" onClick={reloadGraphData}>
              Reload flow + RAW + overlay
            </button>
            <label>
              Load flow file
              <input
                type="file"
                accept="application/json,.json"
                onChange={onPickFlowFile}
              />
            </label>
            <label>
              Load RAW file
              <input
                type="file"
                accept="application/json,.json"
                onChange={onPickRawFile}
              />
            </label>
            <label>
              Load overlay file
              <input
                type="file"
                accept="application/json,.json"
                onChange={onPickOverlayFile}
              />
            </label>
          </div>
          {rawErr ? <p className="raw-err">{rawErr}</p> : null}
          {flowHint ? <p className="flow-hint">{flowHint}</p> : null}
        </div>
      </header>

      <div className="flow-wrap">
        <ReactFlowProvider>
          <GraphCanvas
            graphMode={graphMode}
            flowDoc={flowDoc}
            rawDoc={rawDoc}
            overlayDoc={overlayDoc}
          />
        </ReactFlowProvider>
      </div>

      <aside className="side-panel">
        {brainstormApiEnabled() ? (
          <>
            <UpdateMapPanel onDone={reloadGraphData} />
            <ApplyBundlePanel onApplied={reloadGraphData} />
          </>
        ) : null}

        <section>
          <h2>Legend</h2>
          <div className="legend">
            <div className="legend-row">
              <span className="swatch surface" /> Flow entrypoint
            </div>
            <div className="legend-row">
              <span className="swatch feature" /> Function (flow / symbol)
            </div>
            <div className="legend-row">
              <span className="swatch cap" /> Project / directory (RAW)
            </div>
            <div className="legend-row">
              <span className="swatch code" /> File (RAW)
            </div>
            <div className="legend-row">
              <span className="legend-edge solid" /> Contains / tree
            </div>
            <div className="legend-row">
              <span className="legend-edge call" /> Calls (flow)
            </div>
            <div className="legend-row">
              <span className="swatch float" /> Floating / dead code signal
            </div>
          </div>
        </section>

        {indexMetaView ? (
          <section>
            <h2>Index coverage</h2>
            <div className="mock-card index-coverage">
              <p>
                <strong>{indexMetaView.completeness}</strong>
                {indexMetaView.engine ? ` · engine: ${indexMetaView.engine}` : null}
              </p>
              <ul className="index-limits">
                {(indexMetaView.known_limits ?? []).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          </section>
        ) : null}

        {rawDoc?.diagnostics?.summary ? (
          <section>
            <h2>Type checker</h2>
            <div className="mock-card index-coverage">
              <p>
                <strong>{rawDoc.diagnostics.engine ?? 'pyright'}</strong>
                {' · '}
                errors {rawDoc.diagnostics.summary.errorCount ?? 0}, warnings{' '}
                {rawDoc.diagnostics.summary.warningCount ?? 0}
              </p>
              {rawDoc.diagnostics.note ? (
                <p className="diag-note">{rawDoc.diagnostics.note}</p>
              ) : null}
            </div>
          </section>
        ) : null}

        <section>
          <h2>Refresh index</h2>
          <div className="mock-card">
            <code style={{ fontSize: 10, wordBreak: 'break-all' }}>
              npm run index:golden
            </code>
            <br />
            Writes <code>public/raw.json</code> and <code>public/flow.json</code>.
            <br />
            {brainstormApiEnabled() ? (
              <>
                <code>POST /reindex</code> refreshes RAW + flow on the server; then use{' '}
                <strong>Reload flow + RAW + overlay</strong>. Overlay:{' '}
                <code>PATCH /overlay</code> or edit <code>public/overlay.json</code>.
              </>
            ) : (
              <>
                Edit <code>public/overlay.json</code> for labels (keys = RAW symbol ids).
              </>
            )}{' '}
            Check stale keys:{' '}
            <code style={{ fontSize: 10 }}>npm run check:orphans</code>
          </div>
        </section>

        <section>
          <h2>Mock check-in</h2>
          <div className="mock-card">
            <strong>Agent idle</strong>
            Next: periodic summary would appear here (goal-based run, not
            chatty).
          </div>
        </section>

        <section>
          <h2>Mock goal</h2>
          <div className="mock-card">
            <strong>“Wire Account → privacy copy”</strong>
            In a real build, work would attach to a subtree; tests would map to
            the same nodes.
          </div>
        </section>
      </aside>
    </div>
  )
}
