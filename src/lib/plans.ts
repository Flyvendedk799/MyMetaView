/**
 * Plan presentation helpers — the ONE place the UI turns backend plan data
 * (backend/core/plans.py, served via GET /plans and /plans/me) into human copy.
 *
 * Both the marketing pricing table (Landing) and the in-app billing page read
 * from here, so tiers can never drift apart again. The numbers themselves come
 * from the backend at runtime; FALLBACK_PLANS below is a byte-for-byte mirror of
 * plans.py used only until the fetch resolves (and if it ever fails).
 */
import type { PublicPlan } from '../api/types'

// Gated feature keys — mirror backend/core/plans.py exactly. Use these when
// checking a plan's `features` array so the strings never drift.
export const FEATURES = {
  BRAND: 'brand_customization',
  CARD_CONTROLS: 'card_controls',
  HIDE_WATERMARK: 'hide_watermark',
  VARIANTS: 'variants',
  ADV_ANALYTICS: 'advanced_analytics',
  API: 'api_access',
  TEAM: 'team_seats',
  WHITE_LABEL: 'white_label',
} as const

// Backend feature keys → human labels. Keys must match plans.py exactly.
export const FEATURE_LABELS: Record<string, string> = {
  brand_customization: 'Custom colors, logo & fonts',
  card_controls: 'Card layout & style controls',
  hide_watermark: 'Remove the MetaView watermark',
  variants: 'A/B/C preview variants',
  advanced_analytics: 'Advanced analytics',
  api_access: 'API access',
  team_seats: 'Team roles & permissions',
  white_label: 'Full white-label',
}

// Marketing supplement — copy that isn't a limit or a gated feature (support
// tier, one-line pitch, call-to-action). Keyed by plan key.
export const PLAN_MARKETING: Record<
  string,
  { description: string; cta: string; support: string }
> = {
  free: { description: 'Kick the tires', cta: 'Get started', support: 'Community support' },
  starter: { description: 'Perfect for small websites', cta: 'Start free trial', support: 'Email support' },
  growth: { description: 'For growing businesses', cta: 'Start free trial', support: 'Priority support' },
  agency: { description: 'For agencies and teams', cta: 'Contact sales', support: 'Dedicated support' },
}

// Stripe price IDs per plan key. plans.py maps starter→BASIC, growth→PRO,
// agency→AGENCY via its `stripe_env`; we mirror that mapping here.
export const PLAN_PRICE_IDS: Record<string, string> = {
  starter: (import.meta.env.VITE_STRIPE_PRICE_TIER_BASIC as string) || '',
  growth: (import.meta.env.VITE_STRIPE_PRICE_TIER_PRO as string) || '',
  agency: (import.meta.env.VITE_STRIPE_PRICE_TIER_AGENCY as string) || '',
}

/** The plan we highlight as "most popular" across the UI. */
export const HIGHLIGHTED_PLAN_KEY = 'growth'

export function formatDomains(n: number | null): string {
  if (n === null) return 'Unlimited domains'
  return n === 1 ? '1 domain' : `${n} domains`
}

export function formatPreviews(n: number | null): string {
  if (n === null) return 'Unlimited AI previews'
  return `${n.toLocaleString()} AI previews / month`
}

/** Build the feature-bullet list for a plan, driven entirely by backend data. */
export function planToBullets(plan: PublicPlan): string[] {
  const bullets: string[] = [formatDomains(plan.domains), formatPreviews(plan.previews_month)]

  // Team seats: only surface when there's more than the default single seat.
  if (plan.team_seats === null) bullets.push('Unlimited team seats')
  else if (plan.team_seats > 1) bullets.push(`${plan.team_seats} team seats`)

  for (const feature of plan.features) {
    // `team_seats` seat count is already conveyed by the seats line above.
    if (feature === 'team_seats') continue
    const label = FEATURE_LABELS[feature]
    if (label) bullets.push(label)
  }

  const support = PLAN_MARKETING[plan.key]?.support
  if (support) bullets.push(support)

  return bullets
}

export interface DisplayPlan {
  key: string
  name: string
  price: string
  period: string
  description: string
  features: string[]
  cta: string
  highlighted: boolean
  priceId: string
}

/** Adapt a backend PublicPlan into everything the pricing cards need. */
export function toDisplayPlan(plan: PublicPlan): DisplayPlan {
  return {
    key: plan.key,
    name: plan.name,
    price: `$${plan.price}`,
    period: '/mo',
    description: PLAN_MARKETING[plan.key]?.description ?? '',
    features: planToBullets(plan),
    cta: PLAN_MARKETING[plan.key]?.cta ?? 'Start free trial',
    highlighted: plan.key === HIGHLIGHTED_PLAN_KEY,
    priceId: PLAN_PRICE_IDS[plan.key] ?? '',
  }
}

// Byte-for-byte mirror of PLANS in backend/core/plans.py (public_plans order).
// Rendered instantly so the pricing table is never empty or wrong before the
// /plans fetch resolves. If you change plans.py, change this too.
export const FALLBACK_PLANS: PublicPlan[] = [
  {
    key: 'starter',
    name: 'Starter',
    price: 19,
    domains: 3,
    previews_month: 500,
    team_seats: 1,
    features: ['brand_customization'],
  },
  {
    key: 'growth',
    name: 'Growth',
    price: 49,
    domains: 15,
    previews_month: 5000,
    team_seats: 3,
    features: [
      'advanced_analytics',
      'brand_customization',
      'card_controls',
      'hide_watermark',
      'variants',
    ],
  },
  {
    key: 'agency',
    name: 'Agency',
    price: 149,
    domains: null,
    previews_month: null,
    team_seats: null,
    features: [
      'advanced_analytics',
      'api_access',
      'brand_customization',
      'card_controls',
      'hide_watermark',
      'team_seats',
      'variants',
      'white_label',
    ],
  },
]
