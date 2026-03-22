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
import { applyOverlayToNodes } from './mergeOverlay'
import { buildGraph } from './mockGraph'
import { buildMockTestReport } from './mockTests'
import type { OverlayDoc } from './overlayTypes'
import { emptyOverlay, parseOverlayDoc } from './overlayTypes'
import { brainstormApiEnabled, overlayDataUrl, rawDataUrl } from './apiConfig'
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

type GraphMode = 'mock' | 'raw'

type GraphCanvasProps = {
  graphMode: GraphMode
  rawDoc: RawIndexDoc | null
  overlayDoc: OverlayDoc | null
}

function GraphCanvas({ graphMode, rawDoc, overlayDoc }: GraphCanvasProps) {
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
          graphMode === 'raw' ? n.position : (old?.position ?? n.position)
        return {
          ...n,
          position,
          data: {
            ...n.data,
            onTest: (e: MouseEvent) => {
              e.stopPropagation()
              if (graphMode === 'mock') {
                setTestText(buildMockTestReport(n.id, mockExpanded))
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

  if (graphMode === 'raw' && !rawDoc) {
    return (
      <div className="flow-empty">
        <p>No RAW document loaded.</p>
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
      fitView
      fitViewOptions={{ padding: 0.2 }}
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
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      <Controls showInteractive={false} />

      <Panel position="top-left" className="flow-toolbar">
        <button type="button" onClick={autoLayout}>
          Auto-layout open
        </button>
        <p className="hint">
          {graphMode === 'raw'
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
  const [graphMode, setGraphMode] = useState<GraphMode>('mock')
  const [rawDoc, setRawDoc] = useState<RawIndexDoc | null>(null)
  const [overlayDoc, setOverlayDoc] = useState<OverlayDoc | null>(null)
  const [rawErr, setRawErr] = useState<string | null>(null)

  const loadOverlayFromResponse = useCallback(async (res: Response) => {
    if (!res.ok) {
      setOverlayDoc(emptyOverlay())
      return
    }
    setOverlayDoc(parseOverlayDoc(await res.json()))
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const rawRes = await fetch(rawDataUrl())
        if (!rawRes.ok) {
          throw new Error(`raw index HTTP ${rawRes.status}`)
        }
        const doc = parseRawIndexDoc(await rawRes.json())
        if (cancelled) return
        setRawDoc(doc)
        setGraphMode('raw')
        setRawErr(null)
        try {
          const ovrRes = await fetch(overlayDataUrl())
          if (!cancelled) await loadOverlayFromResponse(ovrRes)
        } catch {
          if (!cancelled) setOverlayDoc(emptyOverlay())
        }
      } catch (e) {
        if (!cancelled) {
          setRawErr(
            e instanceof Error
              ? e.message
              : `Could not load ${rawDataUrl()}`,
          )
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [loadOverlayFromResponse])

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

  const reloadRaw = useCallback(() => {
    setRawErr(null)
    fetch(rawDataUrl())
      .then(async (rawRes) => {
        if (!rawRes.ok) throw new Error(`raw index HTTP ${rawRes.status}`)
        setRawDoc(parseRawIndexDoc(await rawRes.json()))
        setGraphMode('raw')
        try {
          const ovrRes = await fetch(overlayDataUrl())
          await loadOverlayFromResponse(ovrRes)
        } catch {
          setOverlayDoc(emptyOverlay())
        }
      })
      .catch((e) => setRawErr(String(e)))
  }, [loadOverlayFromResponse])

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
          <h1>Brainstorm POC — node map</h1>
          <p className="sub">
            <strong>RAW</strong> + <strong>overlay</strong>:{' '}
            {brainstormApiEnabled() ? (
              <>
                API <code>{rawDataUrl()}</code> + <code>{overlayDataUrl()}</code>{' '}
                (Vite proxy to FastAPI).{' '}
              </>
            ) : (
              <>
                <code>public/raw.json</code> and{' '}
                <code>public/overlay.json</code>{' '}
              </>
            )}
            (friendly names keyed by RAW ids). <strong>Mock</strong> uses{' '}
            <code>src/mockGraph.ts</code>. No file-tree shell.
          </p>
          <div className="mode-bar">
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
            <button type="button" onClick={reloadRaw}>
              Reload RAW + overlay
            </button>
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
        </div>
      </header>

      <div className="flow-wrap">
        <ReactFlowProvider>
          <GraphCanvas
            graphMode={graphMode}
            rawDoc={rawDoc}
            overlayDoc={overlayDoc}
          />
        </ReactFlowProvider>
      </div>

      <aside className="side-panel">
        <section>
          <h2>Legend</h2>
          <div className="legend">
            <div className="legend-row">
              <span className="swatch cap" /> Project / directory
            </div>
            <div className="legend-row">
              <span className="swatch surface" /> Screen / route
            </div>
            <div className="legend-row">
              <span className="swatch feature" /> Symbol
            </div>
            <div className="legend-row">
              <span className="swatch code" /> File
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
            {brainstormApiEnabled() ? (
              <>
                Overlay via API <code>PATCH /overlay</code> (validated) or edit{' '}
                <code>public/overlay.json</code> on disk + reload.
              </>
            ) : (
              <>
                Edit <code>public/overlay.json</code> for labels (keep keys in
                sync with RAW ids).
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
