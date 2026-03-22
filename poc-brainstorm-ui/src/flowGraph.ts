/**
 * React Flow graph from execution IR (function nodes, contains + calls edges).
 */
import type { Edge, Node } from '@xyflow/react'

import type { FlowDoc, FlowNode } from './flowTypes'

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

/** Build nodes and edges. `t-fc-*` / `t-fk-*` participate in dagre (contains + calls). */
export function buildFlowGraph(doc: FlowDoc): { nodes: Node[]; edges: Edge[] } {
  const ep = new Set(doc.entrypoints.filter((x) => typeof x === 'string'))
  const pos = new Map<string, { x: number; y: number }>()
  let i = 0
  for (const n of doc.nodes) {
    pos.set(n.id, { x: 80 + (i % 5) * 200, y: 80 + Math.floor(i / 5) * 100 })
    i += 1
  }

  const nodes: Node[] = doc.nodes.map((n) => {
    const isEp = ep.has(n.id)
    return {
      id: n.id,
      type: isEp ? 'surface' : 'feature',
      position: pos.get(n.id) ?? { x: 0, y: 0 },
      data: {
        label: shortLabel(n.label),
        subtitle: isEp ? `entry · ${locSubtitle(n)}` : locSubtitle(n),
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
      const dashed =
        e.confidence !== 'resolved'
          ? { strokeDasharray: '6 4' as const }
          : {}
      edges.push({
        id: `t-fk-${idStr}-${hi++}`,
        source: e.from,
        target: e.to,
        style: {
          stroke: '#58a6ff',
          strokeWidth: 1.5,
          ...dashed,
        },
        label: e.confidence === 'resolved' ? 'calls' : e.confidence,
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
