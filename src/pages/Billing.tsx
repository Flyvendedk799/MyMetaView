import { useState, useEffect } from 'react'
import { CheckCircleIcon, XCircleIcon, ClockIcon, ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { createCheckoutSession, createBillingPortal, getBillingStatus, changeSubscriptionPlan } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { useOrganization } from '../hooks/useOrganization'

interface BillingStatus {
  subscription_status: string
  subscription_plan?: string | null
  trial_ends_at?: string | null
}

const PLAN_DETAILS = {
  basic: {
    name: 'Basic',
    price: '$9',
    period: '/mo',
    priceId: import.meta.env.VITE_STRIPE_PRICE_TIER_BASIC || '',
    features: [
      '100 previews/month',
      'Basic support',
      'Standard features',
    ],
  },
  pro: {
    name: 'Pro',
    price: '$29',
    period: '/mo',
    priceId: import.meta.env.VITE_STRIPE_PRICE_TIER_PRO || '',
    features: [
      '1,000 previews/month',
      'Priority support',
      'Advanced features',
      'API access',
    ],
  },
  agency: {
    name: 'Agency',
    price: '$99',
    period: '/mo',
    priceId: import.meta.env.VITE_STRIPE_PRICE_TIER_AGENCY || '',
    features: [
      'Unlimited previews',
      'Dedicated support',
      'White-label options',
      'Custom integrations',
    ],
  },
}

const PLAN_ORDER: Array<'basic' | 'pro' | 'agency'> = ['basic', 'pro', 'agency']

export default function Billing() {
  const { user } = useAuth()
  const { currentOrg } = useOrganization()
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  useEffect(() => {
    loadBillingStatus()
    
    // Reload status if returning from Stripe checkout
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('success') === 'true') {
      // Wait a moment for Stripe webhook to process, then reload
      setTimeout(() => {
        loadBillingStatus()
        window.history.replaceState({}, '', window.location.pathname)
      }, 2000)
    }
  }, [])

  const loadBillingStatus = async () => {
    try {
      setLoading(true)
      setError(null)
      const status = await getBillingStatus()
      setBillingStatus(status)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load billing status')
    } finally {
      setLoading(false)
    }
  }

  const handleUpgrade = async (priceId: string) => {
    if (!priceId || priceId.trim() === '') {
      setError('Price ID is missing. Please contact support.')
      return
    }
    try {
      setIsProcessing(true)
      setError(null)
      const result = await createCheckoutSession(priceId)
      window.location.href = result.checkout_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create checkout session')
      setIsProcessing(false)
    }
  }

  const handleChangePlan = async (priceId: string) => {
    if (!priceId || priceId.trim() === '') {
      setError('Price ID is missing. Please contact support.')
      return
    }
    try {
      setIsProcessing(true)
      setError(null)
      const status = await changeSubscriptionPlan(priceId)
      setBillingStatus(status)
      // Show success message
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to change subscription plan')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleManageBilling = async () => {
    try {
      setIsProcessing(true)
      setError(null)
      const result = await createBillingPortal()
      window.location.href = result.portal_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create billing portal session')
      setIsProcessing(false)
    }
  }

  const getStatusBadge = (status: string) => {
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
            Inactive
          </span>
        )
    }
  }

  const formatTrialEnd = (trialEndsAt: string | null | undefined) => {
    if (!trialEndsAt) return null
    const date = new Date(trialEndsAt)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const getDaysUntilTrialEnd = (trialEndsAt: string | null | undefined) => {
    if (!trialEndsAt) return null
    const endDate = new Date(trialEndsAt)
    const now = new Date()
    const diffTime = endDate.getTime() - now.getTime()
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    return diffDays > 0 ? diffDays : 0
  }

  const currentPlan = billingStatus?.subscription_plan?.toLowerCase() as keyof typeof PLAN_DETAILS | undefined
  const currentPlanIndex = currentPlan ? PLAN_ORDER.indexOf(currentPlan) : -1

  const isUpgrade = (planKey: keyof typeof PLAN_DETAILS) => {
    if (currentPlanIndex === -1) return false
    return PLAN_ORDER.indexOf(planKey) > currentPlanIndex
  }

  const isDowngrade = (planKey: keyof typeof PLAN_DETAILS) => {
    if (currentPlanIndex === -1) return false
    return PLAN_ORDER.indexOf(planKey) < currentPlanIndex
  }

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
          {/* Current Subscription Status */}
          <Card className="mb-6">
            <h2 className="text-xl font-semibold text-secondary mb-4">Current Plan</h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600">Subscription Status</p>
                  <div className="mt-1">
                    {getStatusBadge(billingStatus?.subscription_status || 'inactive')}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm text-secondary-600">Plan</p>
                  <p className="mt-1 text-lg font-semibold text-secondary-900 capitalize">
                    {billingStatus?.subscription_status === 'active' 
                      ? (currentPlan ? PLAN_DETAILS[currentPlan]?.name || 'Active Subscription' : 'Active Subscription')
                      : (currentPlan ? PLAN_DETAILS[currentPlan]?.name || 'Free' : 'Free')}
                  </p>
                </div>
              </div>

              {/* Current Plan Benefits */}
              {billingStatus?.subscription_status === 'active' && currentPlan && PLAN_DETAILS[currentPlan] && (
                <div className="bg-primary/5 border border-primary/20 rounded-lg p-6 mt-4">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-secondary mb-1">
                        {PLAN_DETAILS[currentPlan].name} Plan
                      </h3>
                      <p className="text-2xl font-bold text-primary">
                        {PLAN_DETAILS[currentPlan].price}
                        <span className="text-base text-secondary-600 font-normal">
                          {PLAN_DETAILS[currentPlan].period}
                        </span>
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-secondary-700 mb-3">Your plan includes:</p>
                    <ul className="space-y-2">
                      {PLAN_DETAILS[currentPlan].features.map((feature, index) => (
                        <li key={index} className="flex items-center text-sm text-secondary-600">
                          <CheckCircleIcon className="w-5 h-5 text-primary mr-2 flex-shrink-0" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {billingStatus?.trial_ends_at && (
                <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <ClockIcon className="w-5 h-5 text-primary-600" />
                    <div>
                      <p className="text-sm font-medium text-primary-900">Trial Period</p>
                      <p className="text-sm text-primary-700">
                        {billingStatus.trial_ends_at
                          ? (() => {
                              const trialEnd = billingStatus.trial_ends_at
                              const daysLeft = getDaysUntilTrialEnd(trialEnd)
                              if (daysLeft === null) return 'No trial period'
                              return daysLeft > 0
                                ? `${daysLeft} days remaining (ends ${formatTrialEnd(trialEnd)})`
                                : `Trial ended on ${formatTrialEnd(trialEnd)}`
                            })()
                          : 'No trial period'}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {billingStatus?.subscription_status === 'active' && (
                <div className="pt-4 border-t border-secondary-200">
                  <Button onClick={handleManageBilling} disabled={isProcessing} variant="secondary">
                    {isProcessing ? 'Loading...' : 'Manage Billing'}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* Plan Comparison & Upgrade/Downgrade Options */}
          {billingStatus?.subscription_status === 'active' ? (
            <Card>
              <h2 className="text-xl font-semibold text-secondary mb-4">Change Your Plan</h2>
              <p className="text-sm text-secondary-600 mb-6">
                Switch to a different plan. Changes are prorated automatically.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {PLAN_ORDER.map((planKey) => {
                  const plan = PLAN_DETAILS[planKey]
                  const isCurrent = currentPlan === planKey
                  const upgrade = isUpgrade(planKey)
                  const downgrade = isDowngrade(planKey)
                  
                  return (
                    <div
                      key={planKey}
                      className={`border-2 rounded-lg p-6 relative ${
                        isCurrent
                          ? 'border-primary bg-primary/5'
                          : upgrade
                          ? 'border-success-200 hover:border-success-300'
                          : downgrade
                          ? 'border-accent-200 hover:border-accent-300'
                          : 'border-secondary-200'
                      }`}
                    >
                      {isCurrent && (
                        <span className="absolute top-0 right-0 bg-primary text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg">
                          Current Plan
                        </span>
                      )}
                      {upgrade && (
                        <span className="absolute top-0 right-0 bg-success-500 text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg flex items-center">
                          <ArrowUpIcon className="w-3 h-3 mr-1" />
                          Upgrade
                        </span>
                      )}
                      {downgrade && (
                        <span className="absolute top-0 right-0 bg-accent-500 text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg flex items-center">
                          <ArrowDownIcon className="w-3 h-3 mr-1" />
                          Downgrade
                        </span>
                      )}
                      
                      <h3 className="text-lg font-semibold text-secondary-900 mb-2">{plan.name}</h3>
                      <p className="text-3xl font-bold text-secondary mb-4">
                        {plan.price}
                        <span className="text-lg text-secondary-600">/mo</span>
                      </p>
                      <ul className="space-y-2 mb-6 text-sm text-secondary-600">
                        {plan.features.map((feature, idx) => (
                          <li key={idx} className="flex items-center">
                            <CheckCircleIcon className="w-4 h-4 mr-2 text-success-500 flex-shrink-0" />
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                      <Button
                        onClick={() => handleChangePlan(plan.priceId)}
                        disabled={isProcessing || isCurrent || !plan.priceId}
                        className="w-full"
                        variant={isCurrent ? 'secondary' : upgrade ? 'primary' : 'secondary'}
                      >
                        {isCurrent
                          ? 'Current Plan'
                          : isProcessing
                          ? 'Processing...'
                          : !plan.priceId
                          ? 'Price ID not configured'
                          : upgrade
                          ? 'Upgrade to ' + plan.name
                          : 'Switch to ' + plan.name}
                      </Button>
                    </div>
                  )
                })}
              </div>
            </Card>
          ) : (
            <Card>
              <h2 className="text-xl font-semibold text-secondary mb-4">Upgrade Your Plan</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {PLAN_ORDER.map((planKey) => {
                  const plan = PLAN_DETAILS[planKey]
                  const isPopular = planKey === 'pro'
                  
                  return (
                    <div
                      key={planKey}
                      className={`border-2 rounded-lg p-6 relative ${
                        isPopular ? 'border-primary' : 'border-secondary-200'
                      }`}
                    >
                      {isPopular && (
                        <span className="absolute top-0 right-0 bg-primary text-white text-xs px-3 py-1 rounded-bl-lg rounded-tr-lg">
                          Popular
                        </span>
                      )}
                      <h3 className="text-lg font-semibold text-secondary-900 mb-2">{plan.name}</h3>
                      <p className="text-3xl font-bold text-secondary mb-4">
                        {plan.price}
                        <span className="text-lg text-secondary-600">/mo</span>
                      </p>
                      <ul className="space-y-2 mb-6 text-sm text-secondary-600">
                        {plan.features.map((feature, idx) => (
                          <li key={idx} className="flex items-center">
                            <CheckCircleIcon className="w-4 h-4 mr-2 text-success-500 flex-shrink-0" />
                            <span>{feature}</span>
                          </li>
                        ))}
                      </ul>
                      <Button
                        onClick={() => handleUpgrade(plan.priceId)}
                        disabled={isProcessing || !plan.priceId}
                        className="w-full"
                        variant={isPopular ? 'primary' : 'secondary'}
                      >
                        {isProcessing
                          ? 'Processing...'
                          : !plan.priceId
                          ? 'Price ID not configured'
                          : 'Upgrade to ' + plan.name}
                      </Button>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
