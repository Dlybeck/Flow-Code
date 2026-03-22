/**
 * Merge overlay display fields into execution-map nodes. Keeps technical
 * fallbacks in rawLabel / rawSubtitle for the Test panel and tooling.
 */
import type { Node } from '@xyflow/react'

import type { OverlayDoc } from './overlayTypes'

type NodeData = Record<string, unknown> & {
  label: string
  subtitle?: string
  rawLabel?: string
  rawSubtitle?: string
  expandable?: boolean
}

/** Overlay on execution-IR nodes: match `by_symbol_id` via `data.rawSymbolId`. */
export function applyOverlayToFlowNodes(
  nodes: Node[],
  overlay: OverlayDoc | null,
): Node[] {
  if (!overlay) return nodes
  const bySym = overlay.by_symbol_id ?? {}
  const byFlow = overlay.by_flow_node_id ?? {}
  return nodes.map((n) => {
    const d = n.data as NodeData & { rawSymbolId?: string }
    const rid = d.rawSymbolId
    const sym = rid ? bySym[rid] : undefined
    const flowEnt = byFlow[n.id]
    const ent = sym ?? flowEnt
    if (!ent) return n
    const next: NodeData = { ...d }
    if (ent.displayName) {
      next.rawLabel = next.rawLabel ?? d.label
      next.label = ent.displayName
    }
    if (ent.userDescription !== undefined && ent.userDescription !== '') {
      next.rawSubtitle = next.rawSubtitle ?? d.subtitle
      next.subtitle = ent.userDescription
    }
    return { ...n, data: next }
  })
}
