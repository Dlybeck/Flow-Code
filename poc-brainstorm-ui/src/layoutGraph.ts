import dagre from 'dagre'
import type { Edge, Node } from '@xyflow/react'

const NODE_W = 176
const NODE_H = 88

/** Tree / contains edges only — cross-links confuse hierarchical layout */
function isHierarchyEdge(e: Edge) {
  return !e.id.startsWith('x-')
}

export function layoutVisibleGraph(
  nodes: Node[],
  edges: Edge[],
): Map<string, { x: number; y: number }> {
  const allowed = new Set(nodes.map((n) => n.id))

  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({
    rankdir: 'TB',
    nodesep: 28,
    ranksep: 72,
    marginx: 24,
    marginy: 24,
  })

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_W, height: NODE_H })
  }

  for (const e of edges) {
    if (!isHierarchyEdge(e)) continue
    if (!allowed.has(e.source) || !allowed.has(e.target)) continue
    g.setEdge(e.source, e.target)
  }

  dagre.layout(g)

  const out = new Map<string, { x: number; y: number }>()
  for (const n of nodes) {
    const pos = g.node(n.id)
    if (pos) {
      out.set(n.id, {
        x: pos.x - NODE_W / 2,
        y: pos.y - NODE_H / 2,
      })
    }
  }
  return out
}
