/**
 * Carries the visitor's demo session into the app after signup.
 *
 * The public demo stores the URL that was previewed; the dashboard's setup
 * checklist and the Domains page read it so a new account can pick up
 * exactly where the demo left off instead of starting from a blank form.
 */

const KEY = 'mmv:demo-context'

export interface DemoContext {
  url: string
  domain: string
  savedAt: number
}

// Old enough that resuming it would confuse more than help.
const MAX_AGE_MS = 24 * 60 * 60 * 1000

export function saveDemoContext(url: string): void {
  try {
    const parsed = new URL(url)
    const domain = parsed.hostname.replace(/^www\./, '')
    const ctx: DemoContext = { url, domain, savedAt: Date.now() }
    localStorage.setItem(KEY, JSON.stringify(ctx))
  } catch {
    // Not a parseable URL — nothing worth carrying over.
  }
}

export function getDemoContext(): DemoContext | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const ctx = JSON.parse(raw) as DemoContext
    if (!ctx?.domain || Date.now() - (ctx.savedAt || 0) > MAX_AGE_MS) {
      localStorage.removeItem(KEY)
      return null
    }
    return ctx
  } catch {
    return null
  }
}

export function clearDemoContext(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // storage unavailable — nothing to clear
  }
}
