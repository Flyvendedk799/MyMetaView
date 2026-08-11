import {
  ArrowTrendingUpIcon,
  PhotoIcon,
  StarIcon,
  SparklesIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'
import { useState, useEffect, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Alert from '../components/ui/Alert'
import EmptyState from '../components/ui/EmptyState'
import { useDomains } from '../hooks/useDomains'
import { usePreviews } from '../hooks/usePreviews'
import { useAnalyticsSummary } from '../hooks/useAnalyticsSummary'
import { isSnippetLive } from '../lib/snippet'
import { getDemoContext } from '../lib/demoContext'

export default function Dashboard() {
  const navigate = useNavigate()
  const { domains, loading: domainsLoading, error: domainsError } = useDomains()
  const { previews, loading: previewsLoading, error: previewsError } = usePreviews()
  const { summary, loading: analyticsLoading, error: analyticsError } = useAnalyticsSummary('30d')
  const [setupCollapsed, setSetupCollapsed] = useState(
    () => localStorage.getItem('setup_collapsed') === 'true'
  )
  const demoContext = useMemo(() => getDemoContext(), [])

  const verifiedDomains = domains.filter(d => d.status === 'verified')
  const hasVerifiedDomain = verifiedDomains.length > 0
  const hasSnippetInstalled = domains.some(d => isSnippetLive(d.snippet_last_seen_at))

  const isLoading = domainsLoading || previewsLoading

  const onboardingSteps = [
    {
      id: 1,
      title: demoContext?.domain
        ? `Connect ${demoContext.domain}`
        : 'Connect your domain',
      description: demoContext?.domain
        ? 'Pick up where your demo left off — add the domain you previewed.'
        : 'Connect your website domain to start generating previews.',
      completed: domains.length > 0,
      cta: 'Add domain',
      action: () =>
        navigate(
          demoContext?.domain
            ? `/app/domains?add=${encodeURIComponent(demoContext.domain)}`
            : '/app/domains'
        ),
    },
    {
      id: 2,
      title: 'Verify the domain',
      description: 'Prove ownership with a DNS record, HTML file, or meta tag.',
      completed: hasVerifiedDomain,
      cta: 'Verify domain',
      action: () => navigate('/app/domains'),
    },
    {
      id: 3,
      title: 'Generate your first previews',
      description: 'Create branded preview cards for your most-shared pages.',
      completed: previews.length > 0,
      cta: 'Generate previews',
      action: () => navigate('/app/previews'),
    },
    {
      id: 4,
      title: 'Install on your site',
      description: 'Add the snippet, Cloudflare Worker, or WordPress plugin so shared links use your cards.',
      completed: hasSnippetInstalled,
      cta: 'Open install guide',
      action: () => navigate('/app/install'),
    },
  ]

  const completedSteps = onboardingSteps.filter(s => s.completed).length
  const setupComplete = completedSteps === onboardingSteps.length
  // The checklist stays until every step is done — it used to vanish forever
  // the moment the first domain was added.
  const showSetup = !isLoading && !setupComplete

  const toggleSetup = () => {
    const next = !setupCollapsed
    localStorage.setItem('setup_collapsed', String(next))
    setSetupCollapsed(next)
  }

  const statsConfig = [
    {
      name: 'Impressions',
      value: (summary?.total_impressions ?? 0).toLocaleString(),
      description: 'Crawler fetches of your previews · 30 days',
      icon: EyeIcon,
    },
    {
      name: 'Clicks',
      value: (summary?.total_clicks ?? 0).toLocaleString(),
      description:
        summary && summary.total_impressions > 0
          ? `${summary.ctr}% click-through rate`
          : 'Visitors arriving from social links',
      icon: ArrowTrendingUpIcon,
    },
    {
      name: 'Previews',
      value: (summary?.total_previews ?? previews.length).toLocaleString(),
      description: `Across ${domains.length} ${domains.length === 1 ? 'domain' : 'domains'}`,
      icon: PhotoIcon,
    },
    {
      name: 'Brand score',
      value: (summary?.brand_score ?? 0).toString(),
      description:
        (summary?.brand_score ?? 0) >= 80
          ? 'Excellent setup'
          : (summary?.brand_score ?? 0) >= 50
          ? 'Good — keep going'
          : 'Set up your brand →',
      icon: StarIcon,
      onClick: () => navigate('/app/brand'),
    },
  ]

  const loadError = domainsError || previewsError

  return (
    <div>
      <div className="mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Dashboard</h1>
          <p className="text-[15px] text-secondary-600">
            {domains.length === 0 && previews.length === 0
              ? "Welcome! Let's get your first preview live."
              : `${domains.length} ${domains.length === 1 ? 'domain' : 'domains'} connected · ${previews.length.toLocaleString()} ${previews.length === 1 ? 'preview' : 'previews'} generated`}
          </p>
        </div>
        <Button variant="accent" onClick={() => navigate('/app/previews')}>
          New preview
        </Button>
      </div>

      {loadError && (
        <div className="mb-6">
          <Alert variant="error" title="Some dashboard data failed to load">
            {loadError}
          </Alert>
        </div>
      )}

      {/* Setup checklist — persistent until every step is complete */}
      {showSetup && (
        <Card className="mb-8">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center">
                <SparklesIcon className="w-6 h-6 text-primary-500" />
              </div>
              <div>
                <h2 className="font-display text-xl font-semibold tracking-display-sm text-secondary-900">
                  Setup · {completedSteps}/{onboardingSteps.length} complete
                </h2>
                <p className="text-sm text-secondary-600">
                  {completedSteps === 0
                    ? 'Four steps from first visit to live previews on your site'
                    : 'Almost there — finish the remaining steps to go live'}
                </p>
              </div>
            </div>
            <button
              onClick={toggleSetup}
              className="text-secondary-400 hover:text-secondary-600 transition-colors p-1"
              aria-label={setupCollapsed ? 'Expand setup checklist' : 'Collapse setup checklist'}
            >
              {setupCollapsed ? <ChevronDownIcon className="w-5 h-5" /> : <ChevronUpIcon className="w-5 h-5" />}
            </button>
          </div>

          {!setupCollapsed && (
            <div className="space-y-4 mt-6">
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
                        {step.cta}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {isLoading ? (
        <Card>
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-secondary-500 text-sm">Loading dashboard data...</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6 sm:mb-8">
          {statsConfig.map((stat) => (
            <Card
              key={stat.name}
              padding="sm"
              className={`!p-5 ${stat.onClick ? 'cursor-pointer hover:border-primary-500 transition-colors' : ''}`}
              onClick={stat.onClick}
            >
              <div className="flex flex-col gap-1.5">
                <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">{stat.name}</span>
                <span className="font-display text-[32px] leading-tight font-semibold tracking-display text-secondary-900 tabular-nums">
                  {analyticsLoading && !summary ? '–' : stat.value}
                </span>
                <span className="text-[13px] text-secondary-600">{stat.description}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {!isLoading && !analyticsLoading && !analyticsError && summary && summary.total_impressions === 0 && previews.length > 0 && (
        <div className="mb-6">
          <Alert variant="info" title="No impressions recorded yet">
            Impressions are counted when a social platform fetches one of your previews.
            {hasSnippetInstalled
              ? ' Share a link from a connected domain to see your first data.'
              : ' Finish the install step so shared links start serving your cards.'}
          </Alert>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="none" className="overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-line">
            <h3 className="text-[17px] font-semibold text-secondary-900">Recent previews</h3>
            <Link to="/app/previews" className="text-[13px] font-medium text-primary-500 hover:text-accent-500 transition-colors">
              View all
            </Link>
          </div>
          {previews.length === 0 ? (
            <div className="p-5">
              <EmptyState
                icon={<PhotoIcon className="w-6 h-6" />}
                title="No previews yet"
                description="Generate previews for your most-shared pages and they'll appear here."
                action={{
                  label: 'Generate your first preview',
                  onClick: () => navigate('/app/previews'),
                }}
              />
            </div>
          ) : (
            <div>
              {previews.slice(0, 5).map((preview) => (
                <div key={preview.id} className="flex items-center gap-4 px-5 py-3.5 border-b border-secondary-100 last:border-0">
                  <span className="flex-1 text-[13px] text-secondary-900 truncate">
                    {preview.title || preview.url}
                  </span>
                  <span className="font-mono text-[12px] text-secondary-500 truncate max-w-[140px]">{preview.domain}</span>
                  <span className="text-[13px] text-secondary-500 tabular-nums whitespace-nowrap">
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
              <p className="font-medium text-secondary-900">Add a domain</p>
              <p className="text-sm text-secondary-500">Connect another website</p>
            </button>
            <button
              onClick={() => navigate('/app/brand')}
              className="w-full text-left px-4 py-3 rounded-lg border border-line hover:border-primary-500 transition-colors"
            >
              <p className="font-medium text-secondary-900">Customize brand</p>
              <p className="text-sm text-secondary-500">Colors, logo, and card style</p>
            </button>
            <button
              onClick={() => navigate('/app/analytics')}
              className="w-full text-left px-4 py-3 rounded-lg border border-line hover:border-primary-500 transition-colors"
            >
              <p className="font-medium text-secondary-900">View analytics</p>
              <p className="text-sm text-secondary-500">Impressions, clicks, and CTR</p>
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
