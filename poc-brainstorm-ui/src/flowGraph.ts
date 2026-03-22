/**
 * React Flow graph from execution IR (function nodes, contains + calls edges).
 */
import type { Edge, Node } from '@xyflow/react'

import type { FlowDoc, FlowNode } from './flowTypes'

export const FLOW_BOUNDARY_PREFIX = 'py:boundary:'
const UNKNOWN_CALL_STROKE = '#d29922'
const RESOLVED_CALL_STROKE = '#58a6ff'

function isBoundaryFlowNode(n: FlowNode): boolean {
  return n.kind === 'dynamic_callsite' || n.id.startsWith(FLOW_BOUNDARY_PREFIX)
}

function isUncertainFlowCall(e: { kind: string; confidence: string }): boolean {
  return e.kind === 'calls' && e.confidence !== 'resolved'
}

/** Count uncertain call edges per source node (full doc, before hiding). */
export function flowHiddenUncertainCounts(doc: FlowDoc): Map<string, number> {
  const m = new Map<string, number>()
  for (const e of doc.edges) {
    if (!isUncertainFlowCall(e)) continue
    m.set(e.from, (m.get(e.from) ?? 0) + 1)
  }
  return m
}

/**
 * Drop boundary nodes and uncertain call edges for a simpler default map.
 * Use with {@link flowHiddenUncertainCounts} on the original doc for per-node badges.
 */
export function filterFlowDocUncertainty(
  doc: FlowDoc,
  showUncertainDetail: boolean,
): FlowDoc {
  if (showUncertainDetail) return doc
  const boundaryIds = new Set(
    doc.nodes.filter(isBoundaryFlowNode).map((n) => n.id),
  )
  return {
    ...doc,
    nodes: doc.nodes.filter((n) => !boundaryIds.has(n.id)),
    edges: doc.edges.filter(
      (e) =>
        !boundaryIds.has(e.to) && !isUncertainFlowCall(e),
    ),
  }
}

/**
 * Stable fingerprint of the visible execution graph (same filter as the canvas).
 * When unchanged, the UI may keep user-dragged node positions across overlay/poll refreshes.
 */
/** Stable fingerprint of an already-filtered visible doc (nodes + edges). */
export function flowVisibleDocSignature(doc: FlowDoc): string {
  const nids = [...doc.nodes.map((x) => x.id)].sort().join('\0')
  const eparts = doc.edges.map((e) => {
    const id = e.id ?? `${e.from}->${e.to}`
    return `${id}|${e.from}|${e.to}|${e.kind}|${e.confidence}`
  })
  eparts.sort()
  return `${nids}\n${eparts.join('\n')}`
}

export function flowStructureSignature(
  doc: FlowDoc | null,
  showUncertainDetail: boolean,
): string {
  if (!doc?.nodes?.length) return ''
  const v = filterFlowDocUncertainty(doc, showUncertainDetail)
  return flowVisibleDocSignature(v)
}

/** Node ids that have at least one outgoing `contains` edge (in this doc). */
export function flowIdsWithContainsChildren(doc: FlowDoc): Set<string> {
  const s = new Set<string>()
  for (const e of doc.edges) {
    if (e.kind === 'contains') s.add(e.from)
  }
  return s
}

/**
 * Descendants reachable via `contains` edges only (does not include the
 * collapsed nodes themselves).
 */
export function flowHiddenDescendants(
  doc: FlowDoc,
  collapsed: Set<string>,
): Set<string> {
  const children = new Map<string, string[]>()
  for (const e of doc.edges) {
    if (e.kind !== 'contains') continue
    const list = children.get(e.from) ?? []
    list.push(e.to)
    children.set(e.from, list)
  }
  const hidden = new Set<string>()
  const stack = [...collapsed]
  while (stack.length) {
    const u = stack.pop()!
    for (const v of children.get(u) ?? []) {
      if (hidden.has(v)) continue
      hidden.add(v)
      stack.push(v)
    }
  }
  return hidden
}

/** Drop nodes hidden under collapsed parents and any edges touching them. */
export function applyFlowCollapse(doc: FlowDoc, collapsed: Set<string>): FlowDoc {
  const hidden = flowHiddenDescendants(doc, collapsed)
  return {
    ...doc,
    nodes: doc.nodes.filter((n) => !hidden.has(n.id)),
    edges: doc.edges.filter(
      (e) => !hidden.has(e.from) && !hidden.has(e.to),
    ),
  }
}

function shortLabel(qname: string): string {
  const i = qname.lastIndexOf('.')
  return i === -1 ? qname : qname.slice(i + 1)
}

function locSubtitle(n: FlowNode): string {
  const p = n.location?.path
  const line = n.location?.start_line
  if (p && line) return `${p}:${line}`
  if (p) return p
  return n.label
}

function flowNodeReactType(n: FlowNode, entryIds: Set<string>): string {
  if (isBoundaryFlowNode(n)) {
    return 'boundary'
  }
  if (entryIds.has(n.id)) return 'surface'
  return 'feature'
}

/** Build nodes and edges. `t-fc-*` / `t-fk-*` participate in dagre (contains + calls). */
export function buildFlowGraph(doc: FlowDoc): { nodes: Node[]; edges: Edge[] } {
  const entryIds = new Set(doc.entrypoints.filter((x) => typeof x === 'string'))
  const pos = new Map<string, { x: number; y: number }>()
  let i = 0
  for (const n of doc.nodes) {
    pos.set(n.id, { x: 80 + (i % 5) * 200, y: 80 + Math.floor(i / 5) * 100 })
    i += 1
  }

  const nodes: Node[] = doc.nodes.map((n) => {
    const rt = flowNodeReactType(n, entryIds)
    const isEp = entryIds.has(n.id)
    const isBoundary = rt === 'boundary'
    return {
      id: n.id,
      type: rt,
      position: pos.get(n.id) ?? { x: 0, y: 0 },
      data: {
        label: shortLabel(n.label),
        subtitle: isBoundary
          ? 'Groups calls to targets not shown as their own boxes (e.g. libraries, decorators)'
          : isEp
            ? `entry · ${locSubtitle(n)}`
            : locSubtitle(n),
        rawLabel: n.label,
        rawSubtitle: n.id,
        rawSymbolId:
          typeof n.raw_symbol_id === 'string' ? n.raw_symbol_id : undefined,
        expandable: false,
      },
    }
  })

  const edges: Edge[] = []
  let hi = 0
  for (const e of doc.edges) {
    const idStr = typeof e.id === 'string' ? e.id : `e:${hi}`
    if (e.kind === 'contains') {
      edges.push({
        id: `t-fc-${idStr}-${hi++}`,
        source: e.from,
        target: e.to,
        style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
      })
    } else if (e.kind === 'calls') {
      const uncertain = e.confidence !== 'resolved'
      const dashed = uncertain ? { strokeDasharray: '6 4' as const } : {}
      edges.push({
        id: `t-fk-${idStr}-${hi++}`,
        source: e.from,
        target: e.to,
        data: { flowUncertain: uncertain },
        style: {
          stroke: uncertain ? UNKNOWN_CALL_STROKE : RESOLVED_CALL_STROKE,
          strokeWidth: uncertain ? 1.75 : 1.5,
          ...dashed,
        },
        label: uncertain ? 'uncertain' : 'calls',
        labelStyle: { fill: 'var(--text-muted)', fontSize: 9 },
        labelBgStyle: { fill: 'transparent' },
      })
    } else {
      edges.push({
        id: `t-fe-${idStr}-${hi++}`,
        source: e.from,
        target: e.to,
        style: { stroke: '#8b949e', strokeWidth: 1 },
        label: e.kind,
        labelStyle: { fill: 'var(--text-muted)', fontSize: 9 },
        labelBgStyle: { fill: 'transparent' },
      })
    }
  }

  return { nodes, edges }
}
