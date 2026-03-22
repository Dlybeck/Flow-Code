/**
 * Build React Flow nodes/edges from RAW index JSON (schema 0).
 * Hierarchy: project root → directories → files → symbols (when expanded).
 * Import edges: dashed links between files (internal modules only).
 */
import type { Edge, Node } from '@xyflow/react'

import {
  effectiveIndexMeta,
  type RawFile,
  type RawIndexDoc,
  type RawSymbol,
} from './rawTypes'

export const ROOT_ID = 'raw-root'

/** Python-style module name from repo-relative path (mirrors raw-indexer). */
export function moduleQualnameFromPath(relPath: string): string {
  let parts = relPath.split('/')
  if (parts[0] === 'src') parts = parts.slice(1)
  if (!parts.length) return ''
  const last = parts[parts.length - 1]!
  if (last.endsWith('.py')) {
    const stem = last.slice(0, -3)
    if (stem === '__init__') {
      parts = parts.slice(0, -1)
    } else {
      parts = [...parts.slice(0, -1), stem]
    }
  }
  return parts.join('.')
}

function dirnamePosix(p: string): string {
  const i = p.lastIndexOf('/')
  return i === -1 ? '' : p.slice(0, i)
}

function collectDirsFromFiles(files: RawFile[]): Set<string> {
  const dirs = new Set<string>()
  for (const f of files) {
    let d = dirnamePosix(f.path)
    while (d) {
      dirs.add(d)
      d = dirnamePosix(d)
    }
  }
  return dirs
}

/** Immediate child directory paths of `parentPath` (posix, '' = repo root). */
function childDirs(parentPath: string, allDirs: Set<string>): string[] {
  const out: string[] = []
  for (const d of allDirs) {
    if (dirnamePosix(d) === parentPath) out.push(d)
  }
  return out.sort()
}

function filesInDir(dir: string, files: RawFile[]): RawFile[] {
  return files.filter((f) => dirnamePosix(f.path) === dir).sort((a, b) => a.path.localeCompare(b.path))
}

function projectLabel(rootPath: string): string {
  const parts = rootPath.split(/[/\\]/).filter(Boolean)
  return parts[parts.length - 1] ?? 'Project'
}

function symbolsForFile(fileId: string, symbols: RawSymbol[]): RawSymbol[] {
  return symbols.filter((s) => s.file_id === fileId).sort((a, b) => a.line - b.line)
}

function buildModuleToFile(files: RawFile[]): Map<string, string> {
  const m = new Map<string, string>()
  for (const f of files) {
    const mq = moduleQualnameFromPath(f.path)
    if (mq) m.set(mq, f.id)
  }
  return m
}

export function buildRawGraph(
  doc: RawIndexDoc,
  expanded: Set<string>,
): { nodes: Node[]; edges: Edge[] } {
  const files = doc.files
  const symbols = doc.symbols
  const indexCov = effectiveIndexMeta(doc).completeness
  const allDirs = collectDirsFromFiles(files)
  const modToFile = buildModuleToFile(files)

  const vis = new Set<string>()
  const edges: Edge[] = []

  /**
   * Always emit the directory node (so it stays on canvas when collapsed).
   * If `expanded` does not contain this dir, stop — no subdirs/files/symbols.
   */
  const emitDirectory = (dirPath: string, parentId: string) => {
    const dirId = `dir:${dirPath}`
    vis.add(dirId)
    edges.push({
      id: `t-${parentId}-${dirId}`,
      source: parentId,
      target: dirId,
      style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
    })

    if (!expanded.has(dirId)) {
      return
    }

    for (const sub of childDirs(dirPath, allDirs)) {
      emitDirectory(sub, dirId)
    }

    for (const f of filesInDir(dirPath, files)) {
      vis.add(f.id)
      edges.push({
        id: `t-${dirId}-${f.id}`,
        source: dirId,
        target: f.id,
        style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
      })

      if (!expanded.has(f.id)) continue
      for (const sym of symbolsForFile(f.id, symbols)) {
        vis.add(sym.id)
        edges.push({
          id: `t-${f.id}-${sym.id}`,
          source: f.id,
          target: sym.id,
          style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
        })
      }
    }
  }

  vis.add(ROOT_ID)

  if (expanded.has(ROOT_ID)) {
    const top = childDirs('', allDirs)
    if (top.length === 0) {
      for (const f of filesInDir('', files)) {
        vis.add(f.id)
        edges.push({
          id: `t-${ROOT_ID}-${f.id}`,
          source: ROOT_ID,
          target: f.id,
          style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
        })
        if (expanded.has(f.id)) {
          for (const sym of symbolsForFile(f.id, symbols)) {
            vis.add(sym.id)
            edges.push({
              id: `t-${f.id}-${sym.id}`,
              source: f.id,
              target: sym.id,
              style: { stroke: 'var(--edge)', strokeWidth: 1.5 },
            })
          }
        }
      }
    } else {
      for (const d of top) {
        emitDirectory(d, ROOT_ID)
      }
    }
  }

  // Positions — dagre auto-layout overwrites for non-float nodes
  const pos = new Map<string, { x: number; y: number }>()
  let i = 0
  for (const id of vis) {
    pos.set(id, { x: 100 + (i % 4) * 200, y: 100 + Math.floor(i / 4) * 120 })
    i += 1
  }

  const nodes: Node[] = []

  const rootExpandable =
    childDirs('', allDirs).length > 0 || filesInDir('', files).length > 0

  nodes.push({
    id: ROOT_ID,
    type: 'capability',
    position: pos.get(ROOT_ID)!,
    data: {
      label: projectLabel(doc.root),
      expandable: rootExpandable,
      subtitle: 'Double-click to open folders and files',
      rawSubtitle: `RAW · ${doc.indexer} · index: ${indexCov}`,
    },
  })

  for (const id of vis) {
    if (id === ROOT_ID) continue

    if (id.startsWith('dir:')) {
      const path = id.slice('dir:'.length)
      const subs = childDirs(path, allDirs).length
      const fc = filesInDir(path, files).length
      const isOpen = expanded.has(id)
      nodes.push({
        id,
        type: 'capability',
        position: pos.get(id) ?? { x: 0, y: 0 },
        data: {
          label: path,
          expandable: subs > 0 || fc > 0,
          subtitle: isOpen ? 'directory · expanded' : 'directory · collapsed',
        },
      })
    } else if (id.startsWith('file:')) {
      const f = files.find((x) => x.id === id)
      const path = f?.path ?? id
      const base = path.split('/').pop() ?? path
      const failed =
        f?.analysis?.completeness === 'failed' || f?.analysis?.parse_ok === false
      const symCount = symbolsForFile(id, symbols).length
      nodes.push({
        id,
        type: 'code',
        position: pos.get(id) ?? { x: 0, y: 0 },
        data: {
          label: base,
          expandable: !failed && symCount > 0,
          subtitle: failed ? `${path} · not indexed` : path,
          rawSubtitle: failed ? (f?.analysis?.error ?? 'parse failed') : path,
          ...(failed && f?.analysis?.error ? { title: f.analysis.error } : {}),
        },
      })
    } else {
      const sym = symbols.find((s) => s.id === id)
      const label = sym ? `${sym.name} · ${sym.kind}` : id
      nodes.push({
        id,
        type: 'feature',
        position: pos.get(id) ?? { x: 0, y: 0 },
        data: {
          label,
          expandable: false,
          subtitle: sym?.qualified_name,
        },
      })
    }
  }

  let xi = 0
  for (const e of doc.edges) {
    if (e.kind !== 'import_from' && e.kind !== 'import') continue
    const mod = e.module
    if (!mod) continue
    const targetFile = modToFile.get(mod)
    if (!targetFile) continue
    if (!vis.has(e.from_file) || !vis.has(targetFile)) continue
    edges.push({
      id: `x-imp-${xi++}`,
      source: e.from_file,
      target: targetFile,
      style: { stroke: '#6e7681', strokeDasharray: '6 4' },
      label: mod.split('.').pop(),
      labelStyle: { fill: 'var(--text-muted)', fontSize: 10 },
      labelBgStyle: { fill: 'transparent' },
    })
  }

  return { nodes, edges }
}

/** Default expansion: project + all dirs open; files visible; symbols hidden until file is toggled. */
export function defaultRawExpanded(doc: RawIndexDoc): Set<string> {
  const s = new Set<string>([ROOT_ID])
  const dirs = collectDirsFromFiles(doc.files)
  for (const d of dirs) {
    s.add(`dir:${d}`)
  }
  return s
}
