import { useState, useEffect, useMemo, useRef } from 'react'
import { ChartBarIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import {
  fetchAnalyticsOverview,
  fetchDomainAnalytics,
  fetchPreviewAnalytics,
  type AnalyticsOverview,
  type DomainAnalyticsItem,
  type PreviewAnalyticsItem,
} from '../api/client'

export default function Analytics() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [domains, setDomains] = useState<DomainAnalyticsItem[]>([])
  const [previews, setPreviews] = useState<PreviewAnalyticsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState<'7d' | '30d'>('30d')
  
  // Cache last fetch time
  const lastFetchTime = useRef<number>(0)
  const CACHE_TTL = 30000 // 30 seconds

  useEffect(() => {
    loadAnalytics()
  }, [])

  const loadAnalytics = async (force = false) => {
    // Check if data is fresh (less than 30s old)
    const now = Date.now()
    if (!force && overview && (now - lastFetchTime.current) < CACHE_TTL) {
      return // Use cached data
    }
    
    try {
      setLoading(true)
      setError(null)
      const [overviewData, domainsData, previewsData] = await Promise.all([
        fetchAnalyticsOverview(),
        fetchDomainAnalytics(),
        fetchPreviewAnalytics(10),
      ])
      setOverview(overviewData)
      setDomains(domainsData)
      setPreviews(previewsData)
      lastFetchTime.current = now
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }
  
  // Debounce period changes
  useEffect(() => {
    const timer = setTimeout(() => {
      loadAnalytics(true) // Force reload on period change
    }, 300)
    
    return () => clearTimeout(timer)
  }, [period])

  // Generate date labels for last 30 days
  const dateLabels = overview?.impressions_timeseries.map((point) => {
    const date = new Date(point.date)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }) || []

  const maxImpressions = overview
    ? Math.max(...overview.impressions_timeseries.map((p) => p.value), 1)
    : 1
  const maxClicks = overview
    ? Math.max(...overview.clicks_timeseries.map((p) => p.value), 1)
    : 1

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Analytics</h1>
        <p className="text-secondary-600">Track performance and engagement metrics for your previews.</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
            <p className="text-muted">Loading analytics...</p>
          </div>
        </Card>
      ) : !overview || (overview.total_impressions === 0 && overview.total_clicks === 0) ? (
        <Card>
          <EmptyState
            icon={<ChartBarIcon className="w-8 h-8" />}
            title="No analytics data yet"
            description="Once your previews start receiving impressions and clicks, analytics data will appear here. Generate previews and share your links to see performance metrics."
            action={{
              label: 'Generate Your First Preview',
              onClick: () => window.location.href = '/app/previews',
            }}
          />
        </Card>
      ) : overview ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <Card>
              <h3 className="text-sm font-medium text-secondary-600 mb-2">Total Impressions</h3>
              <p className="text-3xl font-bold text-secondary">{overview.total_impressions.toLocaleString()}</p>
              <p className="text-sm text-secondary-600 mt-2">Last 30 days</p>
            </Card>
            <Card>
              <h3 className="text-sm font-medium text-secondary-600 mb-2">Total Clicks</h3>
              <p className="text-3xl font-bold text-secondary">{overview.total_clicks.toLocaleString()}</p>
              <p className="text-sm text-secondary-600 mt-2">Last 30 days</p>
            </Card>
            <Card>
              <h3 className="text-sm font-medium text-secondary-600 mb-2">Click-Through Rate</h3>
              <p className="text-3xl font-bold text-secondary">{overview.ctr.toFixed(2)}%</p>
              <p className="text-sm text-secondary-600 mt-2">Average CTR</p>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Impressions Chart */}
            <Card className="lg:col-span-2">
              <h3 className="text-lg font-semibold text-secondary mb-4">Impressions Over Time</h3>
              <div className="h-64 bg-brand-50 rounded-lg flex items-end justify-between p-4 border border-secondary-100">
                {overview.impressions_timeseries.map((point, i) => {
                  const height = (point.value / maxImpressions) * 100
                  return (
                    <div
                      key={i}
                      className="flex-1 mx-0.5 bg-primary rounded-t-lg transition-all hover:bg-primary/80 cursor-pointer"
                      style={{ height: `${Math.max(height, 2)}%` }}
                      title={`${point.value} impressions on ${point.date}`}
                    />
                  )
                })}
              </div>
              <div className="flex items-center justify-between mt-4 text-xs text-secondary-500 overflow-x-auto">
                {dateLabels.map((label, i) => (
                  <span key={i} className="flex-shrink-0 px-1">
                    {i % 5 === 0 ? label : ''}
                  </span>
                ))}
              </div>
            </Card>

            {/* Top Domains */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary mb-4">Top Domains</h3>
              <div className="space-y-4">
                {domains.length === 0 ? (
                  <p className="text-sm text-secondary-500">No domain data available</p>
                ) : (
                  domains
                    .sort((a, b) => b.impressions_30d - a.impressions_30d)
                    .slice(0, 5)
                    .map((item) => (
                      <div key={item.domain_id} className="flex items-center justify-between pb-4 border-b border-secondary-100 last:border-0">
                        <div className="flex-1">
                          <p className="text-sm font-medium text-secondary-900">{item.domain_name}</p>
                          <p className="text-xs text-secondary-500">
                            {item.impressions_30d.toLocaleString()} impressions, {item.clicks_30d.toLocaleString()} clicks
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-secondary-900">{item.ctr_30d.toFixed(1)}%</p>
                          <p className="text-xs text-secondary-500">CTR</p>
                        </div>
                      </div>
                    ))
                )}
              </div>
            </Card>
          </div>

          {/* Top Previews */}
          <Card>
            <h3 className="text-lg font-semibold text-secondary mb-4">Top Previews</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-secondary-200">
                    <th className="text-left py-3 px-4 font-semibold text-secondary-700">Preview</th>
                    <th className="text-left py-3 px-4 font-semibold text-secondary-700">Domain</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">Impressions</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">Clicks</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">CTR</th>
                  </tr>
                </thead>
                <tbody>
                  {previews.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-secondary-500">
                        No preview data available
                      </td>
                    </tr>
                  ) : (
                    previews.map((item) => (
                      <tr key={item.preview_id} className="border-b border-secondary-100 hover:bg-secondary-50">
                        <td className="py-3 px-4">
                          <p className="font-medium text-secondary-900">{item.title}</p>
                          <p className="text-xs text-secondary-500 line-clamp-1">{item.url}</p>
                        </td>
                        <td className="py-3 px-4 text-sm text-secondary-600">{item.domain}</td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900">
                          {item.impressions_30d.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900">
                          {item.clicks_30d.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-sm font-semibold text-secondary-900">
                          {item.ctr_30d.toFixed(2)}%
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  )
}
