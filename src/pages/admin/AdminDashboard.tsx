import { useState, useEffect } from 'react'
import {
  UsersIcon,
  GlobeAltIcon,
  PhotoIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import { fetchAdminSystemOverview, getDemoCacheDisabled, setDemoCacheDisabled as updateDemoCacheDisabled, type SystemOverview } from '../../api/client'

export default function AdminDashboard() {
  const [overview, setOverview] = useState<SystemOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [demoCacheDisabled, setDemoCacheDisabled] = useState<boolean>(false)
  const [cacheToggleLoading, setCacheToggleLoading] = useState(false)
  const [cacheToggleError, setCacheToggleError] = useState<string | null>(null)

  useEffect(() => {
    loadOverview()
    loadDemoCacheSetting()
    // Refresh every 30 seconds
    const interval = setInterval(loadOverview, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadOverview = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchAdminSystemOverview()
      setOverview(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load system overview')
    } finally {
      setLoading(false)
    }
  }

  const loadDemoCacheSetting = async () => {
    try {
      const disabled = await getDemoCacheDisabled()
      setDemoCacheDisabled(disabled)
      console.log('Demo cache setting loaded:', disabled)
    } catch (err) {
      console.error('Failed to load demo cache setting:', err)
      setCacheToggleError(err instanceof Error ? err.message : 'Failed to load setting')
    }
  }

  const handleToggleDemoCache = async () => {
    try {
      setCacheToggleLoading(true)
      setCacheToggleError(null)
      const newValue = !demoCacheDisabled
      
      // Update the setting and get the confirmed value from server
      const confirmedValue = await updateDemoCacheDisabled(newValue)
      setDemoCacheDisabled(confirmedValue)
      console.log('Demo cache setting updated:', confirmedValue)
      
      // Verify it matches what we expected
      if (confirmedValue !== newValue) {
        console.warn(`Setting mismatch: expected ${newValue}, got ${confirmedValue}`)
        setCacheToggleError('Setting was updated but verification failed. Please refresh the page.')
        // Reload to get the actual current state
        await loadDemoCacheSetting()
      }
    } catch (err) {
      console.error('Failed to update demo cache setting:', err)
      setCacheToggleError(err instanceof Error ? err.message : 'Failed to update setting')
      // Reload the current setting on error to sync UI
      await loadDemoCacheSetting()
    } finally {
      setCacheToggleLoading(false)
    }
  }

  const stats = [
    {
      name: 'Total Users',
      value: overview?.total_users.toLocaleString() || '0',
      icon: UsersIcon,
      color: 'text-primary-500',
    },
    {
      name: 'Active Subscribers',
      value: overview?.active_subscribers.toLocaleString() || '0',
      icon: UsersIcon,
      color: 'text-success-500',
    },
    {
      name: 'Total Domains',
      value: overview?.total_domains.toLocaleString() || '0',
      icon: GlobeAltIcon,
      color: 'text-primary-500',
    },
    {
      name: 'Verified Domains',
      value: overview?.verified_domains.toLocaleString() || '0',
      icon: GlobeAltIcon,
      color: 'text-accent',
    },
    {
      name: 'Previews (24h)',
      value: overview?.previews_generated_24h.toLocaleString() || '0',
      icon: PhotoIcon,
      color: 'text-primary',
    },
    {
      name: 'Queue Length',
      value: overview?.redis_queue_length.toLocaleString() || '0',
      icon: ChartBarIcon,
      color: 'text-warning-500',
    },
    {
      name: 'Errors (24h)',
      value: overview?.errors_past_24h.toLocaleString() || '0',
      icon: ExclamationTriangleIcon,
      color: 'text-error-500',
    },
    {
      name: 'Jobs Running',
      value: overview?.jobs_running.toLocaleString() || '0',
      icon: ChartBarIcon,
      color: 'text-primary-500',
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Admin / Dashboard</h1>
        <p className="text-secondary-600">System-wide overview and metrics</p>
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
            <p className="text-secondary-500">Loading system overview...</p>
          </div>
        </Card>
      ) : (
        <>
          {/* System Overview Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            {stats.map((stat) => {
              const Icon = stat.icon
              return (
                <Card key={stat.name} className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-secondary-600 mb-1">{stat.name}</p>
                      <p className="text-2xl font-bold text-secondary">{stat.value}</p>
                    </div>
                    <Icon className={`w-8 h-8 ${stat.color}`} />
                  </div>
                </Card>
              )
            })}
          </div>

          {/* Demo Cache Toggle */}
          <Card className="mb-6 p-6">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <h2 className="text-xl font-semibold text-secondary mb-2">Demo Cache Control</h2>
                <p className="text-secondary-600 text-sm mb-4">
                  When enabled, demo routes generate fresh previews on each request instead of using cached results.
                  Useful for development testing.
                </p>
                {cacheToggleError && (
                  <p className="text-error-600 text-sm mb-2">{cacheToggleError}</p>
                )}
              </div>
              <div className="ml-6">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={demoCacheDisabled}
                    onChange={handleToggleDemoCache}
                    disabled={cacheToggleLoading}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-secondary-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-secondary-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                  <span className="ml-3 text-sm font-medium text-secondary-700">
                    {demoCacheDisabled ? 'Cache Disabled' : 'Cache Enabled'}
                  </span>
                </label>
              </div>
            </div>
          </Card>

          {/* Charts Placeholder */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <h2 className="text-xl font-semibold text-secondary mb-4">Daily Previews Generated</h2>
              <div className="h-64 flex items-center justify-center bg-secondary-50 rounded-lg">
                <p className="text-secondary-500">Chart placeholder - integrate charting library</p>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="text-xl font-semibold text-secondary mb-4">New Signups</h2>
              <div className="h-64 flex items-center justify-center bg-secondary-50 rounded-lg">
                <p className="text-secondary-500">Chart placeholder - integrate charting library</p>
              </div>
            </Card>

            <Card className="p-6">
              <h2 className="text-xl font-semibold text-secondary mb-4">Queue Activity</h2>
              <div className="h-64 flex items-center justify-center bg-secondary-50 rounded-lg">
                <p className="text-secondary-500">Chart placeholder - integrate charting library</p>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

