import { useState, useEffect } from 'react'
import { CheckCircleIcon, XCircleIcon, ClockIcon, ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { createCheckoutSession, createBillingPortal, changeSubscriptionPlan, getPlans, getMyPlan } from '../api/client'
import type { PublicPlan, MyPlan } from '../api/types'
import { useOrganization } from '../hooks/useOrganization'
import { useAuth } from '../hooks/useAuth'
import { planToBullets, PLAN_MARKETING, planPriceId, HIGHLIGHTED_PLAN_KEY } from '../lib/plans'

// Tier ordering for upgrade/downgrade math (matches backend/core/plans.py).
const PLAN_RANK: Record<string, number> = { free: 0, starter: 1, growth: 2, agency: 3 }

function formatLimit(n: number | null): string {
  return n === null ? 'Unlimited' : n.toLocaleString()
}

function usagePercent(used: number, limit: number | null): number {
  if (limit === null || limit === 0) return 0
  return Math.min(100, Math.round((used / limit) * 100))
}

export default function Billing() {
  const { currentOrg } = useOrganization()
  const [myPlan, setMyPlan] = useState<MyPlan | null>(null)
  const [plans, setPlans] = useState<PublicPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const { refreshUser } = useAuth()

  useEffect(() => {
    loadData()

    // Reload if returning from a successful Stripe checkout. The auth user is
    // refreshed too so PaidRoute and the rest of the app see the new plan
    // without a hard reload.
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('success') === 'true') {
      setTimeout(() => {
        loadData()
        refreshUser()
        window.history.replaceState({}, '', window.location.pathname)
      }, 2000)
    }
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [me, tiers] = await Promise.all([getMyPlan(), getPlans()])
      setMyPlan(me)
      setPlans(tiers)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load billing information')
    } finally {
      setLoading(false)
    }
  }

  const handleManageBilling = async () => {
    try {
      setIsProcessing(true)
      setError(null)
      const result = await createBillingPortal()
      window.location.href = result.portal_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open the billing portal')
      setIsProcessing(false)
    }
  }

  // Active subscribers get a prorated change-plan; everyone else (free / trialing
  // without a card / canceled) goes through a fresh Stripe checkout.
  const handleSelectPlan = async (planKey: string) => {
    const plan = plans.find((p) => p.key === planKey)
    const priceId = plan ? planPriceId(plan) : ''
    if (!priceId || priceId.trim() === '') {
      setError('Checkout isn’t configured for this plan yet. Please contact support.')
      return
    }
    try {
      setIsProcessing(true)
      setError(null)
      if (myPlan?.status === 'active') {
        await changeSubscriptionPlan(priceId)
        // Refresh so usage/limits reflect the new plan.
        await loadData()
      } else {
        const result = await createCheckoutSession(priceId)
        window.location.href = result.checkout_url
        return
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update your plan')
    } finally {
      setIsProcessing(false)
    }
  }

  const getStatusBadge = (status: string | null) => {
    switch (status) {
      case 'active':
        return (
          <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-success-100 text-success-800">
            <CheckCircleIcon className="w-4 h-4 mr-1" />
            Active
          </span>
        )
      case 'trialing':
        return (
          <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-primary-100 text-primary-800">
            <ClockIcon className="w-4 h-4 mr-1" />
            Trial
          </span>
        )
      case 'past_due':
        return (
          <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-warning-100 text-warning-800">
            <ClockIcon className="w-4 h-4 mr-1" />
            Past Due
          </span>
        )
      case 'canceled':
        return (
          <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-secondary-100 text-secondary-800">
            <XCircleIcon className="w-4 h-4 mr-1" />
            Canceled
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-secondary-100 text-secondary-800">
            Free
          </span>
        )
    }
  }

  const formatDate = (iso: string | null | undefined) => {
    if (!iso) return null
    return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const daysUntil = (iso: string | null | undefined) => {
    if (!iso) return null
    const diff = new Date(iso).getTime() - new Date().getTime()
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
    return days > 0 ? days : 0
  }

  const currentRank = myPlan ? (PLAN_RANK[myPlan.key] ?? 0) : 0
  const isActive = myPlan?.status === 'active'
  const trialDaysLeft = daysUntil(myPlan?.trial_ends_at)

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Billing & Subscription</h1>
        <p className="text-muted">
          Manage subscription and billing preferences for {currentOrg?.name || 'your organization'}.
        </p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <p className="text-secondary-500">Loading billing information...</p>
          </div>
        </Card>
      ) : (
        <>
          {/* Current Plan + Usage */}
          <Card className="mb-6">
            <h2 className="text-xl font-semibold text-secondary mb-4">Current Plan</h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600">Status</p>
                  <div className="mt-1">{getStatusBadge(myPlan?.status ?? null)}</div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-secondary-600">Plan</p>
                  <p className="mt-1 text-lg font-semibold text-secondary-900">
                    {myPlan?.name || 'Free'}
                    {myPlan && myPlan.price > 0 && (
                      <span className="text-sm text-secondary-500 font-normal"> · ${myPlan.price}/mo</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Trial banner */}
              {myPlan?.status === 'trialing' && myPlan.trial_ends_at && (
                <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <ClockIcon className="w-5 h-5 text-primary-600" />
                    <div>
                      <p className="text-sm font-medium text-primary-900">
                        {myPlan.name} trial — full access
                      </p>
                      <p className="text-sm text-primary-700">
                        {trialDaysLeft && trialDaysLeft > 0
                          ? `${trialDaysLeft} day${trialDaysLeft === 1 ? '' : 's'} remaining (ends ${formatDate(myPlan.trial_ends_at)})`
                          : `Trial ended on ${formatDate(myPlan.trial_ends_at)}`}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Usage meters. The two preview meters are different things:
                  `previews_month` is how many previews the account may hold,
                  `ai_previews_month` is how many get the art director. Past the
                  AI allowance generation continues on the template lane. */}
              {myPlan && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                    <UsageMeter label="Domains" used={myPlan.usage.domains} limit={myPlan.limits.domains} />
                    <UsageMeter
                      label="Previews this month"
                      used={myPlan.usage.previews_month}
                      limit={myPlan.limits.previews_month}
                    />
                  </div>
                  {myPlan.limits.ai_previews_month !== undefined && (
                    <div className="pt-4">
                      <UsageMeter
                        label="AI-designed previews this month"
                        used={myPlan.usage.ai_previews_month ?? 0}
                        limit={myPlan.limits.ai_previews_month ?? null}
                      />
                      <p className="text-xs text-secondary-500 mt-2">
                        Every preview past this allowance is still generated — from your
                        page&rsquo;s own metadata instead of a fresh AI design.
                      </p>
                    </div>
                  )}
                </>
              )}

              {isActive && (
                <div className="pt-4 border-t border-secondary-200">
                  <Button onClick={handleManageBilling} disabled={isProcessing} variant="secondary">
                    {isProcessing ? 'Loading...' : 'Manage Billing'}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* Plan chooser */}
          <Card>
            <h2 className="text-xl font-semibold text-secondary mb-1">
              {isActive ? 'Change Your Plan' : 'Choose Your Plan'}
            </h2>
            <p className="text-sm text-secondary-600 mb-6">
              {isActive
                ? 'Switch to a different plan. Changes are prorated automatically.'
                : 'Start a plan any time. You keep full Growth access until your trial ends.'}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {plans.map((plan) => {
                const rank = PLAN_RANK[plan.key] ?? 0
                const isCurrent = myPlan?.key === plan.key
                const upgrade = rank > currentRank && !isCurrent
                const downgrade = rank < currentRank && !isCurrent
                const popular = plan.key === HIGHLIGHTED_PLAN_KEY
                const bullets = planToBullets(plan)
                const marketing = PLAN_MARKETING[plan.key]
                const priceConfigured = !!planPriceId(plan)

                return (
                  <div
                    key={plan.key}
                    className={`border-2 rounded-lg p-6 relative ${
                      isCurrent
                        ? 'border-primary bg-primary/5'
                        : upgrade
                        ? 'border-success-200 hover:border-success-300'
                        : downgrade
                        ? 'border-accent-200 hover:border-accent-300'
                        : popular
                        ? 'border-primary'
                        : 'border-secondary-200'
                    }`}
                  >
                    {isCurrent ? (
                      <span className="absolute top-0 right-0 bg-primary text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg">
                        Current Plan
                      </span>
                    ) : upgrade ? (
                      <span className="absolute top-0 right-0 bg-success-500 text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg flex items-center">
                        <ArrowUpIcon className="w-3 h-3 mr-1" />
                        Upgrade
                      </span>
                    ) : downgrade ? (
                      <span className="absolute top-0 right-0 bg-accent-500 text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg flex items-center">
                        <ArrowDownIcon className="w-3 h-3 mr-1" />
                        Downgrade
                      </span>
                    ) : popular ? (
                      <span className="absolute top-0 right-0 bg-primary text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg">
                        Popular
                      </span>
                    ) : null}

                    <h3 className="text-lg font-semibold text-secondary-900 mb-1">{plan.name}</h3>
                    {marketing?.description && (
                      <p className="text-sm text-secondary-500 mb-3">{marketing.description}</p>
                    )}
                    <p className="text-3xl font-bold text-secondary mb-4">
                      ${plan.price}
                      <span className="text-lg text-secondary-600">/mo</span>
                    </p>
                    <ul className="space-y-2 mb-6 text-sm text-secondary-600">
                      {bullets.map((feature, idx) => (
                        <li key={idx} className="flex items-center">
                          <CheckCircleIcon className="w-4 h-4 mr-2 text-success-500 flex-shrink-0" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                    <Button
                      onClick={() => handleSelectPlan(plan.key)}
                      disabled={isProcessing || isCurrent || !priceConfigured}
                      className="w-full"
                      variant={isCurrent ? 'secondary' : upgrade || popular ? 'primary' : 'secondary'}
                    >
                      {isCurrent
                        ? 'Current Plan'
                        : isProcessing
                        ? 'Processing...'
                        : !priceConfigured
                        ? 'Coming soon'
                        : upgrade
                        ? `Upgrade to ${plan.name}`
                        : downgrade
                        ? `Switch to ${plan.name}`
                        : `Choose ${plan.name}`}
                    </Button>
                  </div>
                )
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

function UsageMeter({
  label,
  used,
  limit,
}: {
  label: string
  used: number
  limit: number | null
}) {
  const pct = usagePercent(used, limit)
  const nearCap = limit !== null && pct >= 90
  return (
    <div className="bg-secondary-50 border border-secondary-200 rounded-lg p-4">
      <div className="flex items-baseline justify-between mb-2">
        <p className="text-sm font-medium text-secondary-700">{label}</p>
        <p className="text-sm text-secondary-600">
          {used.toLocaleString()}
          <span className="text-secondary-400"> / {formatLimit(limit)}</span>
        </p>
      </div>
      <div className="h-2 w-full rounded-full bg-secondary-200 overflow-hidden">
        <div
          className={`h-full rounded-full ${nearCap ? 'bg-warning-500' : 'bg-primary-500'}`}
          style={{ width: `${limit === null ? 6 : Math.max(pct, 2)}%` }}
        />
      </div>
    </div>
  )
}
