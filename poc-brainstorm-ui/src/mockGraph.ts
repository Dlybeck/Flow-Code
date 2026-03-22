/**
 * Throwaway mock data for the brainstorming POC.
 * Edit this file to reshape the “product” without touching React layout.
 */
import type { Edge, Node } from '@xyflow/react'

export type NodeKind = 'capability' | 'surface' | 'feature' | 'code' | 'floating'

export type MockNode = {
  id: string
  label: string
  kind: NodeKind
  /** Show “double-click to drill” affordance */
  expandable?: boolean
}

/** Declarative tree: parent id → ordered child ids */
export const CHILDREN: Record<string, string[]> = {
  root: ['ui', 'ai', 'config', 'db'],
  ui: ['ui-home', 'ui-account', 'ui-about'],
  'ui-account': ['ui-account-profile', 'ui-account-privacy'],
  ai: ['ai-prompts', 'ai-runtime'],
  db: ['db-schema', 'db-migrations'],
}

/** Static node metadata */
export const META: Record<string, MockNode> = {
  ui: { id: 'ui', label: 'UI', kind: 'capability', expandable: true },
  ai: { id: 'ai', label: 'AI inference', kind: 'capability', expandable: true },
  config: { id: 'config', label: 'Config', kind: 'capability' },
  db: { id: 'db', label: 'DB', kind: 'capability', expandable: true },

  'ui-home': { id: 'ui-home', label: 'Home', kind: 'surface' },
  'ui-account': {
    id: 'ui-account',
    label: 'Account',
    kind: 'surface',
    expandable: true,
  },
  'ui-about': { id: 'ui-about', label: 'About', kind: 'surface' },

  'ui-account-profile': {
    id: 'ui-account-profile',
    label: 'Personal info',
    kind: 'feature',
  },
  'ui-account-privacy': {
    id: 'ui-account-privacy',
    label: 'Privacy settings',
    kind: 'feature',
  },

  'ai-prompts': { id: 'ai-prompts', label: 'Prompt templates', kind: 'feature' },
  'ai-runtime': {
    id: 'ai-runtime',
    label: 'inference.ts',
    kind: 'code',
  },

  'db-schema': { id: 'db-schema', label: 'schema.sql', kind: 'code' },
  'db-migrations': { id: 'db-migrations', label: 'migrations/', kind: 'code' },

  'float-dead': {
    id: 'float-dead',
    label: 'old_banner.tsx\n(floating — unlinked)',
    kind: 'floating',
  },
  'float-orphan': {
    id: 'float-orphan',
    label: 'utils/legacy.py\n(orphan file)',
    kind: 'floating',
  },
}

/** Cross-links (not parent/child): optional architecture edges */
export const EXTRA_EDGES: { from: string; to: string; label?: string }[] = [
  { from: 'ui', to: 'ai', label: 'calls' },
  { from: 'ai', to: 'config' },
  { from: 'db', to: 'ai' },
]

const typeForKind = (k: NodeKind): string => {
  switch (k) {
    case 'capability':
      return 'capability'
    case 'surface':
      return 'surface'
    case 'feature':
      return 'feature'
    case 'code':
      return 'code'
    case 'floating':
      return 'floating'
    default:
      return 'feature'
  }
}

export function buildGraph(expanded: Set<string>): { nodes: Node[]; edges: Edge[] } {
  const vis = new Set<string>()
  const roots = CHILDREN.root

  const dfs = (id: string) => {
    if (!META[id]) return
    vis.add(id)
    const kids = CHILDREN[id]
    if (!kids) return
    const isOpen = id === 'root' || expanded.has(id)
    if (!isOpen) return
    for (const c of kids) dfs(c)
  }
  for (const r of roots) dfs(r)

  const pos = new Map<string, { x: number; y: number }>()
  roots.forEach((id, i) => pos.set(id, { x: 40 + i * 220, y: 32 }))

  const placeChildren = (parentId: string) => {
    const kids = CHILDREN[parentId]
    if (!kids || !vis.has(parentId)) return
    if (parentId !== 'root' && !expanded.has(parentId)) return
    const p = pos.get(parentId)!
    const py = p.y + 120
    const gap = 20
    const w = 150
    const totalW = kids.length * w + (kids.length - 1) * gap
    const x0 = p.x - totalW / 2 + w / 2
    kids.forEach((kid, i) => {
      if (!vis.has(kid)) return
      pos.set(kid, { x: x0 + i * (w + gap), y: py })
      placeChildren(kid)
    })
  }
  for (const r of roots) placeChildren(r)

  const nodes: Node[] = []
  for (const id of vis) {
    const m = META[id]
    if (!m) continue
    nodes.push({
      id,
      type: typeForKind(m.kind),
      position: pos.get(id) ?? { x: 0, y: 0 },
      data: {
        label: m.label,
        expandable: Boolean(m.expandable && CHILDREN[id]?.length),
      },
    })
  }

  nodes.push({
    id: 'float-dead',
    type: 'floating',
    position: { x: 620, y: 380 },
    data: { label: META['float-dead'].label, expandable: false },
  })
  nodes.push({
    id: 'float-orphan',
    type: 'floating',
    position: { x: 620, y: 480 },
    data: { label: META['float-orphan'].label, expandable: false },
  })

  const edges: Edge[] = []
  for (const id of vis) {
    const kids = CHILDREN[id]
    if (!kids) continue
    if (id !== 'root' && !expanded.has(id)) continue
    for (const c of kids) {
      if (!vis.has(c)) continue
      edges.push({
        id: `${id}-${c}`,
        source: id,
        target: c,
        animated: false,
        style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
      })
    }
  }

  for (const e of EXTRA_EDGES) {
    if (vis.has(e.from) && vis.has(e.to)) {
      edges.push({
        id: `x-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        style: { stroke: '#484f58', strokeDasharray: '6 4' },
        label: e.label,
        labelStyle: { fill: 'var(--text-muted)', fontSize: 10 },
        labelBgStyle: { fill: 'transparent' },
      })
    }
  }

  return { nodes, edges }
}
