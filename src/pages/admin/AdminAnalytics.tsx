import { useState, useEffect } from 'react'
import {
  UsersIcon,
  GlobeAltIcon,
  PhotoIcon,
  ArrowTrendingUpIcon,
  CursorArrowRaysIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import {
  fetchAdminAnalyticsOverview,
  fetchAdminAnalyticsUsers,
  type AdminAnalyticsOverview,
  type AdminAnalyticsUserItem,
} from '../../api/client'

export default function AdminAnalytics() {
  const [overview, setOverview] = useState<AdminAnalyticsOverview | null>(null)
  const [users, setUsers] = useState<AdminAnalyticsUserItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadAnalytics()
    // Refresh every 30 seconds
    const interval = setInterval(loadAnalytics, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadAnalytics = async () => {
    try {
      setLoading(true)
      setError(null)
      const [overviewData, usersData] = await Promise.all([
        fetchAdminAnalyticsOverview(),
        fetchAdminAnalyticsUsers(20),
      ])
      setOverview(overviewData)
      setUsers(usersData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }

  const ctr_24h = overview && overview.total_impressions_24h > 0
    ? (overview.total_clicks_24h / overview.total_impressions_24h * 100)
    : 0
  const ctr_30d = overview && overview.total_impressions_30d > 0
    ? (overview.total_clicks_30d / overview.total_impressions_30d * 100)
    : 0

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Admin / Analytics</h1>
        <p className="text-secondary-600">System-wide analytics and usage metrics</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Loading analytics...</p>
          </div>
        </Card>
      ) : overview ? (
        <>
          {/* Summary Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Total Users</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_users.toLocaleString()}</p>
                </div>
                <UsersIcon className="w-8 h-8 text-primary-500" />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Active Subscribers</p>
                  <p className="text-2xl font-bold text-secondary">{overview.active_subscribers.toLocaleString()}</p>
                </div>
                <UsersIcon className="w-8 h-8 text-success-500" />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Total Domains</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_domains.toLocaleString()}</p>
                </div>
                <GlobeAltIcon className="w-8 h-8 text-primary-500" />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Total Previews</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_previews.toLocaleString()}</p>
                </div>
                <PhotoIcon className="w-8 h-8 text-primary" />
              </div>
            </Card>
          </div>

          {/* Traffic Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Impressions (24h)</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_impressions_24h.toLocaleString()}</p>
                </div>
                <ArrowTrendingUpIcon className="w-8 h-8 text-warning-500" />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Clicks (24h)</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_clicks_24h.toLocaleString()}</p>
                </div>
                <CursorArrowRaysIcon className="w-8 h-8 text-success-500" />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Impressions (30d)</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_impressions_30d.toLocaleString()}</p>
                </div>
                <ArrowTrendingUpIcon className="w-8 h-8 text-primary-500" />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Clicks (30d)</p>
                  <p className="text-2xl font-bold text-secondary">{overview.total_clicks_30d.toLocaleString()}</p>
                </div>
                <CursorArrowRaysIcon className="w-8 h-8 text-primary" />
              </div>
            </Card>
          </div>

          {/* CTR Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <Card className="p-6">
              <h3 className="text-sm font-medium text-secondary-600 mb-2">CTR (24h)</h3>
              <p className="text-3xl font-bold text-secondary">{ctr_24h.toFixed(2)}%</p>
            </Card>
            <Card className="p-6">
              <h3 className="text-sm font-medium text-secondary-600 mb-2">CTR (30d)</h3>
              <p className="text-3xl font-bold text-secondary">{ctr_30d.toFixed(2)}%</p>
            </Card>
          </div>

          {/* Top Users */}
          <Card>
            <h2 className="text-xl font-semibold text-secondary mb-4">Top Users by Usage</h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-secondary-200">
                    <th className="text-left py-3 px-4 font-semibold text-secondary-700">User</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">Impressions (30d)</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">Clicks (30d)</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">Active Domains</th>
                    <th className="text-right py-3 px-4 font-semibold text-secondary-700">Active Previews</th>
                  </tr>
                </thead>
                <tbody>
                  {users.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-secondary-500">
                        No user data available
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.user_id} className="border-b border-secondary-100 hover:bg-secondary-50">
                        <td className="py-3 px-4">
                          <p className="font-medium text-secondary-900">{user.email}</p>
                        </td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900">
                          {user.impressions_30d.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900">
                          {user.clicks_30d.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900">
                          {user.active_domains}
                        </td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900">
                          {user.active_previews}
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

