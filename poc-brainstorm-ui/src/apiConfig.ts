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
