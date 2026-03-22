/**
 * Execution IR (flow.json) — language-neutral graph; see docs/product-vision/EXECUTION-MAP-PLAN.md
 */

export type FlowEdge = {
  id?: string
  from: string
  to: string
  kind: string
  confidence: string
}

export type FlowNode = {
  id: string
  kind: string
  language: string
  label: string
  location?: {
    path?: string
    start_line?: number
    end_line?: number
  }
  raw_symbol_id?: string
}

export type FlowDoc = {
  schema_version: number
  repo_root?: string
  languages: string[]
  entrypoints: string[]
  nodes: FlowNode[]
  edges: FlowEdge[]
  producers?: unknown[]
}

export function parseFlowDoc(raw: unknown): FlowDoc {
  if (!raw || typeof raw !== 'object') {
    throw new Error('flow: root must be an object')
  }
  const o = raw as Record<string, unknown>
  if (o.schema_version !== 0) {
    throw new Error(`flow: unsupported schema_version ${String(o.schema_version)}`)
  }
  if (!Array.isArray(o.languages)) {
    throw new Error('flow: languages must be an array')
  }
  if (!Array.isArray(o.entrypoints)) {
    throw new Error('flow: entrypoints must be an array')
  }
  if (!Array.isArray(o.nodes)) {
    throw new Error('flow: nodes must be an array')
  }
  if (!Array.isArray(o.edges)) {
    throw new Error('flow: edges must be an array')
  }
  return o as unknown as FlowDoc
}
