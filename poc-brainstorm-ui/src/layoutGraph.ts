import dagre from 'dagre'
import type { Edge, Node } from '@xyflow/react'

const NODE_W = 176
const NODE_H = 88

/** Tree / contains edges only — cross-links confuse hierarchical layout */
function isHierarchyEdge(e: Edge) {
  return !e.id.startsWith('x-')
}

const POS_EPS = 2

function approxEq(a: number, b: number) {
  return Math.abs(a - b) < POS_EPS
}

/** Parent → direct children from hierarchy edges only (`t-*`). */
export function hierarchyChildrenFromEdges(edges: Edge[]): Map<string, string[]> {
  const m = new Map<string, string[]>()
  for (const e of edges) {
    if (!isHierarchyEdge(e)) continue
    const list = m.get(e.source) ?? []
    list.push(e.target)
    m.set(e.source, list)
  }
  return m
}

function collectSubtree(rootId: string, children: Map<string, string[]>): Set<string> {
  const out = new Set<string>([rootId])
  const st = [rootId]
  while (st.length) {
    const u = st.pop()!
    for (const c of children.get(u) ?? []) {
      if (out.has(c)) continue
      out.add(c)
      st.push(c)
    }
  }
  return out
}

/**
 * After dagre, restore user drags: if a node was on-screen before with a
 * different position, shift that node and its entire visible subtree by the same
 * delta so children stay under a moved collapsed parent when it re-expands.
 */
export function reapplyDraggedSubtrees(
  laidOut: Node[],
  edges: Edge[],
  prev: Pick<Node, 'id' | 'position'>[],
): Node[] {
  if (prev.length === 0) return laidOut

  const initialPos = new Map(laidOut.map((n) => [n.id, { ...n.position }]))
  const prevPos = new Map(prev.map((n) => [n.id, { ...n.position }]))
  const children = hierarchyChildrenFromEdges(edges)

  const moved = new Set<string>()
  for (const n of laidOut) {
    const old = prevPos.get(n.id)
    if (!old) continue
    const cur = initialPos.get(n.id)!
    if (approxEq(old.x, cur.x) && approxEq(old.y, cur.y)) continue
    moved.add(n.id)
  }

  if (moved.size === 0) return laidOut

  const maximal: string[] = []
  for (const id of moved) {
    let inner = false
    for (const other of moved) {
      if (other === id) continue
      if (collectSubtree(other, children).has(id)) {
        inner = true
        break
      }
    }
    if (!inner) maximal.push(id)
  }

  const adjusted = new Map<string, { x: number; y: number }>()
  for (const [id, p] of initialPos) adjusted.set(id, p)

  const absorbed = new Set<string>()
  for (const rootId of maximal) {
    if (absorbed.has(rootId)) continue
    const old = prevPos.get(rootId)
    const base = initialPos.get(rootId)
    if (!old || !base) continue
    const delta = { x: old.x - base.x, y: old.y - base.y }
    if (approxEq(delta.x, 0) && approxEq(delta.y, 0)) continue

    for (const id of collectSubtree(rootId, children)) {
      absorbed.add(id)
      const b = initialPos.get(id)
      if (!b) continue
      adjusted.set(id, { x: b.x + delta.x, y: b.y + delta.y })
    }
  }

  return laidOut.map((n) => ({
    ...n,
    position: adjusted.get(n.id) ?? n.position,
  }))
}

export function layoutVisibleGraph(
  nodes: Node[],
  edges: Edge[],
): Map<string, { x: number; y: number }> {
  const nonFloat = nodes.filter((n) => n.type !== 'floating')
  const floatIds = new Set(nodes.filter((n) => n.type === 'floating').map((n) => n.id))
  const allowed = new Set(nonFloat.map((n) => n.id))

  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({
    rankdir: 'TB',
    nodesep: 28,
    ranksep: 72,
    marginx: 24,
    marginy: 24,
  })

  for (const n of nonFloat) {
    g.setNode(n.id, { width: NODE_W, height: NODE_H })
  }

  for (const e of edges) {
    if (!isHierarchyEdge(e)) continue
    if (!allowed.has(e.source) || !allowed.has(e.target)) continue
    if (floatIds.has(e.source) || floatIds.has(e.target)) continue
    g.setEdge(e.source, e.target)
  }

  dagre.layout(g)

  const out = new Map<string, { x: number; y: number }>()
  for (const n of nonFloat) {
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
