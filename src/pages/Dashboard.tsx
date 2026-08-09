import {
  ArrowTrendingUpIcon,
  GlobeAltIcon,
  PhotoIcon,
  StarIcon,
  SparklesIcon,
  XMarkIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { useState, useEffect, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import { useDomains } from '../hooks/useDomains'
import { usePreviews } from '../hooks/usePreviews'
import { useAnalyticsSummary } from '../hooks/useAnalyticsSummary'

export default function Dashboard() {
  const navigate = useNavigate()
  const { domains, loading: domainsLoading } = useDomains()
  const { previews, loading: previewsLoading } = usePreviews()
  const { summary, loading: analyticsLoading } = useAnalyticsSummary('30d')
  const [onboardingDismissed, setOnboardingDismissed] = useState(false)

  // Check if onboarding should be shown
  useEffect(() => {
    const dismissed = localStorage.getItem('onboarding_dismissed') === 'true'
    setOnboardingDismissed(dismissed)
  }, [])

  const shouldShowOnboarding = !onboardingDismissed &&
    !domainsLoading &&
    !previewsLoading &&
    domains.length === 0 &&
    previews.length === 0

  const handleDismissOnboarding = () => {
    localStorage.setItem('onboarding_dismissed', 'true')
    setOnboardingDismissed(true)
  }

  const verifiedDomains = domains.filter(d => d.status === 'verified')
  const hasVerifiedDomain = verifiedDomains.length > 0

  // Calculate new domains count (domains created in last 30 days)
  const newDomainsCount = useMemo(() => {
    if (!domains.length) return 0
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
    return domains.filter((d) => {
      const createdDate = new Date(d.created_at)
      return createdDate >= thirtyDaysAgo
    }).length
  }, [domains])

  const statsConfig = [
    {
      name: 'Monthly clicks',
      value: summary?.total_clicks.toLocaleString() || '0',
      description: 'Last 30 days',
      descriptionTone: 'text-secondary-600',
      icon: ArrowTrendingUpIcon,
    },
    {
      name: 'New domains',
      value: newDomainsCount.toString(),
      description: 'Added this month',
      descriptionTone: 'text-secondary-600',
      icon: GlobeAltIcon,
    },
    {
      name: 'Previews generated',
      value: summary?.total_previews.toLocaleString() || '0',
      description: 'Across all domains',
      descriptionTone: 'text-secondary-600',
      icon: PhotoIcon,
    },
    {
      name: 'Brand score',
      value: summary?.brand_score.toString() || '0',
      description:
        (summary?.brand_score ?? 0) >= 80
          ? 'Excellent consistency'
          : (summary?.brand_score ?? 0) >= 50
          ? 'Good consistency'
          : (summary?.brand_score ?? 0) > 0
          ? 'Room to improve'
          : 'Set up your brand',
      descriptionTone: 'text-secondary-600',
      icon: StarIcon,
    },
  ]

  const isLoading = domainsLoading || analyticsLoading || previewsLoading

  const onboardingSteps = [
    {
      id: 1,
      title: 'Add your first domain',
      description: 'Connect your website domain to start generating previews',
      completed: domains.length > 0,
      action: () => navigate('/app/domains'),
    },
    {
      id: 2,
      title: 'Verify the domain',
      description: 'Complete DNS verification to activate your domain',
      completed: hasVerifiedDomain,
      action: () => navigate('/app/domains'),
    },
    {
      id: 3,
      title: 'Generate your first AI preview',
      description: 'Create beautiful preview cards for your URLs',
      completed: previews.length > 0,
      action: () => navigate('/app/previews'),
    },
    {
      id: 4,
      title: 'Install the snippet on your site',
      description: 'Add our embed code to enable automatic previews',
      completed: false, // This would require checking if snippet is installed
      action: () => navigate('/app/previews'),
    },
  ]

  return (
    <div>
      <div className="mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Dashboard</h1>
          <p className="text-[15px] text-secondary-600">
            {domains.length === 0 && previews.length === 0
              ? "Welcome! Let's get you started with your first preview."
              : `${domains.length} ${domains.length === 1 ? 'domain' : 'domains'} connected · ${previews.length.toLocaleString()} ${previews.length === 1 ? 'preview' : 'previews'} generated`}
          </p>
        </div>
        <Button variant="accent" onClick={() => navigate('/app/previews')}>
          New preview
        </Button>
      </div>

      {/* Onboarding Panel */}
      {shouldShowOnboarding && (
        <Card className="mb-8">
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center">
                <SparklesIcon className="w-6 h-6 text-primary-500" />
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold tracking-display-sm text-secondary-900">Getting Started</h2>
                <p className="text-sm text-secondary-600">Follow these steps to set up your preview system</p>
              </div>
            </div>
            <button
              onClick={handleDismissOnboarding}
              className="text-secondary-400 hover:text-secondary-600 transition-colors"
              aria-label="Dismiss onboarding"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            {onboardingSteps.map((step) => (
              <div
                key={step.id}
                className={`flex items-start space-x-4 p-4 rounded-xl border transition-colors ${
                  step.completed
                    ? 'bg-success-50 border-success-100'
                    : 'bg-surface border-line hover:border-primary-500'
                }`}
              >
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  step.completed ? 'bg-success-500' : 'bg-secondary-100'
                }`}>
                  {step.completed ? (
                    <CheckCircleIcon className="w-5 h-5 text-paper" />
                  ) : (
                    <span className="text-sm font-semibold text-secondary-600">{step.id}</span>
                  )}
                </div>
                <div className="flex-1">
                  <h3 className={`font-medium mb-1 ${
                    step.completed ? 'text-success-700' : 'text-secondary-900'
                  }`}>
                    {step.title}
                  </h3>
                  <p className="text-sm text-secondary-600 mb-3">{step.description}</p>
                  {!step.completed && (
                    <Button size="sm" onClick={step.action}>
                      {step.id === 1 ? 'Add Domain' : step.id === 2 ? 'Verify Domain' : step.id === 3 ? 'Generate Preview' : 'View Instructions'}
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {isLoading ? (
        <Card>
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-secondary-500 text-sm">Loading dashboard data...</p>
          </div>
        </Card>
      ) : domains.length === 0 && previews.length === 0 && onboardingDismissed ? (
        <Card>
          <EmptyState
            icon={<SparklesIcon className="w-8 h-8" />}
            title="Get started with your first preview"
            description="Connect a domain and generate your first AI-powered preview to see how your links will appear when shared."
            action={{
              label: 'Add Your First Domain',
              onClick: () => navigate('/app/domains'),
            }}
          />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6 sm:mb-8">
            {statsConfig.map((stat) => (
              <Card key={stat.name} padding="sm" className="!p-5">
                <div className="flex flex-col gap-1.5">
                  <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">{stat.name}</span>
                  <span className="font-display text-[32px] leading-tight font-semibold tracking-display text-secondary-900 tabular-nums">{stat.value}</span>
                  <span className={`text-[13px] ${stat.descriptionTone}`}>{stat.description}</span>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="none" className="overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-line">
            <h3 className="text-[17px] font-semibold text-secondary-900">Recent activity</h3>
            <Link to="/app/activity" className="text-[13px] font-medium text-primary-500 hover:text-accent-500 transition-colors">
              View all
            </Link>
          </div>
          {previews.length === 0 ? (
            <div className="p-5">
              <EmptyState
                icon={<PhotoIcon className="w-6 h-6" />}
                title="No activity yet"
                description="Once you generate previews, your recent activity will appear here."
                action={{
                  label: 'Generate Your First Preview',
                  onClick: () => navigate('/app/previews'),
                }}
              />
            </div>
          ) : (
            <div>
              {previews.slice(0, 5).map((preview) => (
                <div key={preview.id} className="flex items-center gap-4 px-5 py-3.5 border-b border-secondary-100 last:border-0">
                  <span className="flex-1 font-mono text-[13px] text-secondary-900 truncate">
                    {preview.title || 'Preview generated'}
                  </span>
                  <span className="pill-success">Live</span>
                  <span className="text-[13px] text-secondary-500 tabular-nums">
                    {new Date(preview.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h3 className="text-[17px] font-semibold text-secondary-900 mb-4">Quick actions</h3>
          <div className="space-y-3">
            <button
              onClick={() => navigate('/app/domains')}
              className="w-full text-left px-4 py-3 rounded-lg border border-line hover:border-primary-500 transition-colors"
            >
              <p className="font-medium text-secondary-900">Add New Domain</p>
              <p className="text-sm text-secondary-500">Connect a new website</p>
            </button>
            <button
              onClick={() => navigate('/app/brand')}
              className="w-full text-left px-4 py-3 rounded-lg border border-line hover:border-primary-500 transition-colors"
            >
              <p className="font-medium text-secondary-900">Customize Brand</p>
              <p className="text-sm text-secondary-500">Update your preview style</p>
            </button>
            <button
              onClick={() => navigate('/app/previews')}
              className="w-full text-left px-4 py-3 rounded-lg border border-line hover:border-primary-500 transition-colors"
            >
              <p className="font-medium text-secondary-900">Generate Preview</p>
              <p className="text-sm text-secondary-500">Create a new AI preview</p>
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
