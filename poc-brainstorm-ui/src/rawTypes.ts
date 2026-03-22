/** Matches `packages/raw-indexer` JSON output (schema_version 0). */

/** Document-level honesty (Phase 4); older indexes may omit — parser fills defaults. */
export type RawIndexMeta = {
  completeness: 'complete' | 'partial' | 'unknown'
  engine?: string
  known_limits?: string[]
}

export type RawFileAnalysis = {
  completeness: 'complete' | 'failed'
  parse_ok: boolean
  error?: string
}

export type RawFile = {
  id: string
  path: string
  sha256: string
  analysis?: RawFileAnalysis
}

export type RawSymbol = {
  id: string
  kind: string
  name: string
  qualified_name: string
  file_id: string
  line: number
  end_line: number
}

export type RawEdge =
  | {
      kind: 'import'
      from_file: string
      module: string
      line: number
    }
  | {
      kind: 'import_from'
      from_file: string
      module: string
      names: string[]
      line: number
      level: number
    }

/** Optional Pyright/Basedpyright attachment (`index --diagnostics`). */
export type RawDiagnostics = {
  schema_version?: number
  partial?: boolean
  note?: string
  engine?: string
  summary?: {
    errorCount?: number
    warningCount?: number
    informationCount?: number
    filesAnalyzed?: number
  }
  by_path?: Record<
    string,
    Array<{
      line: number
      severity: string
      message: string
      rule?: string
    }>
  >
}

export type RawIndexDoc = {
  schema_version: number
  indexer: string
  index_meta?: RawIndexMeta
  diagnostics?: RawDiagnostics
  root: string
  files: RawFile[]
  symbols: RawSymbol[]
  edges: RawEdge[]
}

function defaultIndexMeta(): RawIndexMeta {
  return {
    completeness: 'unknown',
    known_limits: ['This index predates coverage metadata — re-run raw-indexer to refresh.'],
  }
}

export function effectiveIndexMeta(doc: RawIndexDoc): RawIndexMeta {
  const m = doc.index_meta
  if (!m || typeof m !== 'object') return defaultIndexMeta()
  const completeness =
    m.completeness === 'complete' || m.completeness === 'partial' || m.completeness === 'unknown'
      ? m.completeness
      : 'unknown'
  return {
    completeness,
    engine: typeof m.engine === 'string' ? m.engine : undefined,
    known_limits: Array.isArray(m.known_limits)
      ? m.known_limits.filter((x): x is string => typeof x === 'string')
      : undefined,
  }
}

export function parseRawIndexDoc(data: unknown): RawIndexDoc {
  const d = data as RawIndexDoc
  if (d.schema_version !== 0) {
    throw new Error(`Unsupported schema_version: ${String(d?.schema_version)}`)
  }
  if (!Array.isArray(d.files) || !Array.isArray(d.symbols) || !Array.isArray(d.edges)) {
    throw new Error('Invalid RAW document: missing files, symbols, or edges')
  }
  return {
    ...d,
    index_meta: d.index_meta,
    files: d.files.map((f) => ({ ...f })),
  }
}
