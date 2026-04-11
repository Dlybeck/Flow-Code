/**
 * Phase 3: when set (e.g. `VITE_BRAINSTORM_API=/api/brainstorm`), the POC loads
 * RAW + overlay from the HTTP API instead of `public/*.json`.
 */
const base = (import.meta.env.VITE_BRAINSTORM_API as string | undefined)?.trim() ?? ''

export function brainstormApiEnabled(): boolean {
  return base.length > 0
}

export function rawDataUrl(): string {
  return base ? `${base}/raw` : '/raw.json'
}

export function overlayDataUrl(): string {
  return base ? `${base}/overlay` : '/overlay.json'
}

/** Execution IR (function graph): same host as RAW via Vite proxy or static `public/flow.json`. */
export function flowDataUrl(): string {
  return base ? `${base}/flow` : '/flow.json'
}

/** POST JSON change package; only valid when {@link brainstormApiEnabled}. */
export function applyBundleUrl(): string {
  return `${base}/apply-bundle`
}

export function updateMapUrl(): string {
  return `${base}/update-map`
}

export function commentsUrl(): string {
  return base ? `${base}/comments` : '/comments.json'
}

// ─── Work session (PM-to-developer flow) ────────────────────────────────────

/** POST /go — submit a brief + optional node anchors; returns { session_id } */
export function goUrl(): string {
  return `${base}/go`
}

/** GET /status/:id — poll for phase, activity_message, check_in, summary */
export function goStatusUrl(sessionId: string): string {
  return `${base}/status/${encodeURIComponent(sessionId)}`
}

/** POST /status/:id/reply — submit a check-in answer */
export function replyUrl(sessionId: string): string {
  return `${base}/status/${encodeURIComponent(sessionId)}/reply`
}

/** POST /status/:id/cancel */
export function cancelUrl(sessionId: string): string {
  return `${base}/status/${encodeURIComponent(sessionId)}/cancel`
}

/** POST /status/:id/undo */
export function undoUrl(sessionId: string): string {
  return `${base}/status/${encodeURIComponent(sessionId)}/undo`
}
