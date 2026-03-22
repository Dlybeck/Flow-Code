/**
 * Merge overlay display fields into graph nodes. Keeps technical fallbacks in
 * rawLabel / rawSubtitle for the Test panel and tooling.
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

export function applyOverlayToNodes(
  nodes: Node[],
  overlay: OverlayDoc | null,
): Node[] {
  if (!overlay) return nodes

  const bySym = overlay.by_symbol_id ?? {}
  const byFile = overlay.by_file_id ?? {}

  return nodes.map((n) => {
    const sym = bySym[n.id]
    const fil = byFile[n.id]
    const d = n.data as NodeData

    if (sym) {
      const next: NodeData = { ...d }
      if (sym.displayName) {
        next.rawLabel = next.rawLabel ?? d.label
        next.label = sym.displayName
      }
      if (sym.userDescription !== undefined && sym.userDescription !== '') {
        next.rawSubtitle = next.rawSubtitle ?? d.subtitle
        next.subtitle = sym.userDescription
      }
      return { ...n, data: next }
    }

    if (fil && n.id.startsWith('file:')) {
      const next: NodeData = { ...d }
      if (fil.displayName) {
        next.rawLabel = next.rawLabel ?? d.label
        next.label = fil.displayName
      }
      if (fil.userDescription !== undefined && fil.userDescription !== '') {
        next.rawSubtitle = next.rawSubtitle ?? d.subtitle
        next.subtitle = fil.userDescription
      }
      return { ...n, data: next }
    }

    return n
  })
}
