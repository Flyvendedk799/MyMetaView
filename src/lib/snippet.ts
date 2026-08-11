/**
 * Canonical location of the embed snippet.
 *
 * The authoritative value lives on the backend (PUBLIC_BASE_URL) and reaches the
 * Install page through /api/v1/install/config. This constant is the fallback for
 * places that show the tag without loading that config — keep the default in
 * step with the backend's.
 */
export const SNIPPET_BASE_URL: string = (
  import.meta.env.VITE_SNIPPET_BASE_URL || 'https://mymetaview.com'
).replace(/\/$/, '')

export const SNIPPET_URL = `${SNIPPET_BASE_URL}/snippet.js`

/** Build the tag a customer pastes. */
export function buildSnippetTag(domain?: string): string {
  const site = domain ? ` data-site="${domain}"` : ''
  return `<script src="${SNIPPET_URL}"${site} defer></script>`
}

/** Matches the backend's HEARTBEAT_FRESH_FOR window. */
const HEARTBEAT_FRESH_MS = 7 * 24 * 60 * 60 * 1000

/**
 * True when the snippet has checked in recently enough to call it installed.
 * Timestamps arrive as naive UTC, so tag them before parsing.
 */
export function isSnippetLive(lastSeenAt?: string | null): boolean {
  if (!lastSeenAt) return false
  const stamp = /[Z+]|-\d{2}:\d{2}$/.test(lastSeenAt) ? lastSeenAt : `${lastSeenAt}Z`
  const seen = new Date(stamp).getTime()
  if (Number.isNaN(seen)) return false
  return Date.now() - seen <= HEARTBEAT_FRESH_MS
}
