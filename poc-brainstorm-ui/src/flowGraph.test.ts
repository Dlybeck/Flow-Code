import { describe, expect, it } from 'vitest'

import { buildFlowGraph } from './flowGraph'
import type { FlowDoc } from './flowTypes'

const mini: FlowDoc = {
  schema_version: 0,
  languages: ['python'],
  entrypoints: ['py:fn:app.main'],
  nodes: [
    {
      id: 'py:fn:app.main',
      kind: 'function',
      language: 'python',
      label: 'app.main',
    },
    {
      id: 'py:fn:app.main.helper',
      kind: 'function',
      language: 'python',
      label: 'app.main.helper',
    },
    {
      id: 'py:fn:app.util',
      kind: 'function',
      language: 'python',
      label: 'app.util',
      raw_symbol_id: 'sym:util',
    },
  ],
  edges: [
    {
      from: 'py:fn:app.main',
      to: 'py:fn:app.main.helper',
      kind: 'contains',
      confidence: 'resolved',
    },
    {
      from: 'py:fn:app.main.helper',
      to: 'py:fn:app.util',
      kind: 'calls',
      confidence: 'resolved',
    },
  ],
}

describe('buildFlowGraph', () => {
  it('emits one node per IR node and marks entrypoints as surface', () => {
    const { nodes } = buildFlowGraph(mini)
    expect(nodes).toHaveLength(3)
    const main = nodes.find((n) => n.id === 'py:fn:app.main')
    expect(main?.type).toBe('surface')
    const util = nodes.find((n) => n.id === 'py:fn:app.util')
    expect(util?.type).toBe('feature')
    expect((util?.data as { rawSymbolId?: string }).rawSymbolId).toBe(
      'sym:util',
    )
  })

  it('emits contains and calls edges with distinct ids', () => {
    const { edges } = buildFlowGraph(mini)
    const kinds = edges.map((e) => ({
      id: e.id,
      dashed: Boolean((e.style as { strokeDasharray?: string })?.strokeDasharray),
    }))
    expect(edges.length).toBeGreaterThanOrEqual(2)
    expect(kinds.some((k) => String(k.id).startsWith('t-fc-'))).toBe(true)
    expect(kinds.some((k) => String(k.id).startsWith('t-fk-'))).toBe(true)
  })
})
