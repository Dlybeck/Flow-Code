/** Presentation overlay keyed by RAW ids (SPEC); optional file + symbol maps. */

export type OverlayEntry = {
  displayName?: string
  userDescription?: string
}

export type OverlayDoc = {
  schema_version?: number
  by_symbol_id?: Record<string, OverlayEntry>
  by_file_id?: Record<string, OverlayEntry>
  by_directory_id?: Record<string, OverlayEntry>
  /** Diagram root node id raw-root (matches RAW graph). */
  by_root_id?: Record<string, OverlayEntry>
}

export function parseOverlayDoc(data: unknown): OverlayDoc {
  if (data === null || typeof data !== 'object') {
    return {
      by_symbol_id: {},
      by_file_id: {},
      by_directory_id: {},
      by_root_id: {},
    }
  }
  const d = data as OverlayDoc
  return {
    schema_version: typeof d.schema_version === 'number' ? d.schema_version : 0,
    by_symbol_id:
      d.by_symbol_id && typeof d.by_symbol_id === 'object'
        ? d.by_symbol_id
        : {},
    by_file_id:
      d.by_file_id && typeof d.by_file_id === 'object' ? d.by_file_id : {},
    by_directory_id:
      d.by_directory_id && typeof d.by_directory_id === 'object'
        ? d.by_directory_id
        : {},
    by_root_id:
      d.by_root_id && typeof d.by_root_id === 'object' ? d.by_root_id : {},
  }
}

export function emptyOverlay(): OverlayDoc {
  return {
    schema_version: 0,
    by_symbol_id: {},
    by_file_id: {},
    by_directory_id: {},
    by_root_id: {},
  }
}
