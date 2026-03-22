/**
 * Mock “test runner” copy for the POC — encodes parent → child aggregation idea.
 */
import { CHILDREN, META } from './mockGraph'

/** Must match `buildGraph` visibility rules */
function collectVisible(expanded: Set<string>): Set<string> {
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
  return vis
}

function visibleChildren(nodeId: string, vis: Set<string>): string[] {
  const kids = CHILDREN[nodeId]
  if (!kids) return []
  return kids.filter((k) => vis.has(k))
}

/**
 * Parent: own smoke + recursive child plan.
 * Leaf: single built-in test line.
 */
export function buildMockTestReport(
  nodeId: string,
  expanded: Set<string>,
): string {
  if (!META[nodeId]) return `Unknown node: ${nodeId}`

  const m = META[nodeId]
  if (m.kind === 'floating') {
    return [
      `Node: ${m.label.replace(/\n/g, ' ')}`,
      '— mock: orphan / unlinked scan (no anchor tests)',
      '— action in real product: attach or delete',
    ].join('\n')
  }

  const vis = collectVisible(expanded)
  if (!vis.has(nodeId)) {
    return `${m.label} is not visible (collapse parent or expand path).`
  }

  const lines: string[] = [`▸ ${m.label} (${m.kind})`, '']

  const allKids = CHILDREN[nodeId] ?? []
  const kids = visibleChildren(nodeId, vis)
  const hasOwnSmoke =
    m.kind === 'capability' || m.kind === 'surface' || m.kind === 'feature'

  if (allKids.length > 0 && kids.length === 0) {
    lines.push(
      `  [parent] ${allKids.length} child test(s) not in view — expand node to fan out (mock)`,
    )
    if (hasOwnSmoke) {
      lines.push('  [parent smoke] root slice for this node (mock) … OK')
    }
    return lines.join('\n')
  }

  if (kids.length === 0) {
    lines.push('  [leaf] built-in unit test (mock) … OK')
    lines.push(`  — covers: ${m.label} boundary + anchors`)
    return lines.join('\n')
  }

  if (hasOwnSmoke) {
    lines.push('  [parent smoke] root slice for this node (mock) … OK')
    lines.push('  — wiring / exports / entrypoints only')
    lines.push('')
  }

  lines.push(`  Fan-out: ${kids.length} visible child node(s) —`)
  for (const k of kids) {
    const cm = META[k]
    lines.push(`    • ${cm?.label ?? k}`)
    lines.push(indentBlock(buildMockTestReport(k, expanded), '      '))
    lines.push('')
  }

  lines.push('  Aggregate result (mock): all of the above passed')
  return lines.join('\n')
}

function indentBlock(s: string, pad: string): string {
  return s
    .split('\n')
    .map((line) => (line ? pad + line : ''))
    .join('\n')
}
