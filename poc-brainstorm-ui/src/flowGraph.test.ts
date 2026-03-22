import { describe, expect, it } from 'vitest'

import {
  applyFlowCollapse,
  buildFlowGraph,
  filterFlowDocUncertainty,
  flowHiddenDescendants,
  flowHiddenUncertainCounts,
  flowIdsWithContainsChildren,
  flowStructureSignature,
} from './flowGraph'
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

  it('uses boundary node type and dashed uncertain call edges', () => {
    const doc: FlowDoc = {
      ...mini,
      nodes: [
        ...mini.nodes,
        {
          id: 'py:boundary:unresolved',
          kind: 'dynamic_callsite',
          language: 'python',
          label: 'Unresolved / not traced (v0)',
        },
      ],
      edges: [
        ...mini.edges,
        {
          from: 'py:fn:app.util',
          to: 'py:boundary:unresolved',
          kind: 'calls',
          confidence: 'unknown',
        },
      ],
    }
    const { nodes, edges } = buildFlowGraph(doc)
    expect(nodes.find((n) => n.id === 'py:boundary:unresolved')?.type).toBe(
      'boundary',
    )
    const unk = edges.find(
      (e) => e.target === 'py:boundary:unresolved' && e.label === 'uncertain',
    )
    expect(unk).toBeDefined()
    expect((unk?.style as { strokeDasharray?: string })?.strokeDasharray).toBe(
      '6 4',
    )
  })

  it('filterFlowDocUncertainty hides boundary and uncertain calls; counts preserved from full doc', () => {
    const doc: FlowDoc = {
      ...mini,
      nodes: [
        ...mini.nodes,
        {
          id: 'py:boundary:unresolved',
          kind: 'dynamic_callsite',
          language: 'python',
          label: 'Unresolved',
        },
      ],
      edges: [
        ...mini.edges,
        {
          from: 'py:fn:app.util',
          to: 'py:boundary:unresolved',
          kind: 'calls',
          confidence: 'unknown',
        },
      ],
    }
    const counts = flowHiddenUncertainCounts(doc)
    expect(counts.get('py:fn:app.util')).toBe(1)
    const slim = filterFlowDocUncertainty(doc, false)
    expect(slim.nodes.some((n) => n.id === 'py:boundary:unresolved')).toBe(
      false,
    )
    expect(slim.edges.some((e) => e.confidence === 'unknown')).toBe(false)
    const full = filterFlowDocUncertainty(doc, true)
    expect(full.nodes.length).toBe(doc.nodes.length)
  })

  it('applyFlowCollapse hides contains subtrees when parent is collapsed', () => {
    expect(flowIdsWithContainsChildren(mini).has('py:fn:app.main')).toBe(true)
    const hidden = flowHiddenDescendants(mini, new Set(['py:fn:app.main']))
    expect(hidden.has('py:fn:app.main.helper')).toBe(true)
    expect(hidden.has('py:fn:app.main')).toBe(false)
    const slim = applyFlowCollapse(mini, new Set(['py:fn:app.main']))
    expect(slim.nodes.map((n) => n.id)).toEqual([
      'py:fn:app.main',
      'py:fn:app.util',
    ])
    expect(
      slim.edges.some(
        (e) => e.from === 'py:fn:app.main.helper' || e.to === 'py:fn:app.main.helper',
      ),
    ).toBe(false)
  })

  it('flowStructureSignature changes when uncertain detail toggle would change edges', () => {
    const doc: FlowDoc = {
      ...mini,
      nodes: [
        ...mini.nodes,
        {
          id: 'py:boundary:unresolved',
          kind: 'dynamic_callsite',
          language: 'python',
          label: 'x',
        },
      ],
      edges: [
        ...mini.edges,
        {
          from: 'py:fn:app.util',
          to: 'py:boundary:unresolved',
          kind: 'calls',
          confidence: 'unknown',
        },
      ],
    }
    const a = flowStructureSignature(doc, true)
    const b = flowStructureSignature(doc, false)
    expect(a).not.toBe(b)
    expect(flowStructureSignature(doc, true)).toBe(a)
  })
})
