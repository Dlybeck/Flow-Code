/**
 * Merge overlay display fields into graph nodes. Keeps technical fallbacks in
 * rawLabel / rawSubtitle for the Test panel and tooling.
 */
import type { Node } from '@xyflow/react'

import type { OverlayDoc } from './overlayTypes'
import { ROOT_ID } from './rawGraph'

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
  const byDir = overlay.by_directory_id ?? {}
  const byRoot = overlay.by_root_id ?? {}
  const rootEntry = byRoot[ROOT_ID]

  return nodes.map((n) => {
    const sym = bySym[n.id]
    const fil = byFile[n.id]
    const dir = byDir[n.id]
    const d = n.data as NodeData

    if (n.id === ROOT_ID && rootEntry) {
      const next: NodeData = { ...d }
      if (rootEntry.displayName) {
        next.rawLabel = next.rawLabel ?? d.label
        next.label = rootEntry.displayName
      }
      if (
        rootEntry.userDescription !== undefined &&
        rootEntry.userDescription !== ''
      ) {
        next.rawSubtitle =
          typeof d.rawSubtitle === 'string' && d.rawSubtitle.length > 0
            ? d.rawSubtitle
            : d.subtitle
        next.subtitle = rootEntry.userDescription
      }
      return { ...n, data: next }
    }

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

    if (dir && n.id.startsWith('dir:')) {
      const next: NodeData = { ...d }
      if (dir.displayName) {
        next.rawLabel = next.rawLabel ?? d.label
        next.label = dir.displayName
      }
      if (dir.userDescription !== undefined && dir.userDescription !== '') {
        next.rawSubtitle = next.rawSubtitle ?? d.subtitle
        next.subtitle = dir.userDescription
      }
      return { ...n, data: next }
    }

    return n
  })
}
