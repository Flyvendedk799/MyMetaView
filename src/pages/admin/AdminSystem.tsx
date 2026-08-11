import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ExclamationTriangleIcon, CloudArrowUpIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { fetchAdminSystemOverview, fetchAdminWorkerHealth, triggerDeployment, type SystemOverview, type WorkerHealth } from '../../api/client'

export default function AdminSystem() {
  const [overview, setOverview] = useState<SystemOverview | null>(null)
  const [workerHealth, setWorkerHealth] = useState<WorkerHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deploying, setDeploying] = useState(false)
  const [deploymentResult, setDeploymentResult] = useState<{ success: boolean; message: string; branch_merged?: string } | null>(null)

  useEffect(() => {
    loadData()
    // Refresh every 10 seconds
    const interval = setInterval(loadData, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [overviewData, healthData] = await Promise.all([
        fetchAdminSystemOverview(),
        fetchAdminWorkerHealth(),
      ])
      setOverview(overviewData)
      setWorkerHealth(healthData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load system data')
    } finally {
      setLoading(false)
    }
  }

  const handleDeploy = async () => {
    if (!window.confirm('This will merge the latest claude branch into main and push to trigger Railway deployment. Continue?')) {
      return
    }

    try {
      setDeploying(true)
      setDeploymentResult(null)
      setError(null)
      const result = await triggerDeployment()
      setDeploymentResult(result)
      if (result.success) {
        // Clear any previous errors
        setError(null)
      } else {
        setError(result.message)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to trigger deployment'
      setError(errorMessage)
      setDeploymentResult({
        success: false,
        message: errorMessage
      })
    } finally {
      setDeploying(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Admin / System</h1>
        <p className="text-muted">Monitor system health and manage workers</p>
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
            <p className="text-secondary-500">Loading system status...</p>
          </div>
        </Card>
      ) : (
        <>
          {/* System Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Redis Queue Length</p>
                  <p className="text-2xl font-bold text-secondary">
                    {overview?.redis_queue_length.toLocaleString() || '0'}
                  </p>
                </div>
                <div className={`w-3 h-3 rounded-full ${
                  (overview?.redis_queue_length || 0) > 100 ? 'bg-error-500' : 'bg-success-500'
                }`}></div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Jobs Running</p>
                  <p className="text-2xl font-bold text-secondary">
                    {overview?.jobs_running.toLocaleString() || '0'}
                  </p>
                </div>
                <div className={`w-3 h-3 rounded-full ${
                  (overview?.jobs_running || 0) > 0 ? 'bg-warning-500' : 'bg-secondary-300'
                }`}></div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Errors (24h)</p>
                  <p className="text-2xl font-bold text-secondary">
                    {overview?.errors_past_24h.toLocaleString() || '0'}
                  </p>
                </div>
                <ExclamationTriangleIcon className={`w-6 h-6 ${
                  (overview?.errors_past_24h || 0) > 0 ? 'text-error-500' : 'text-secondary-300'
                }`} />
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-secondary-600 mb-1">Previews (24h)</p>
                  <p className="text-2xl font-bold text-secondary">
                    {overview?.previews_generated_24h.toLocaleString() || '0'}
                  </p>
                </div>
              </div>
            </Card>
          </div>

          {/* Deployment Management */}
          <Card className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-secondary">Deployment Management</h2>
              <Button
                onClick={handleDeploy}
                disabled={deploying}
                variant="primary"
              >
                {deploying ? (
                  <span className="flex items-center space-x-2">
                    <CloudArrowUpIcon className="w-5 h-5 animate-pulse" />
                    <span>Deploying...</span>
                  </span>
                ) : (
                  <span className="flex items-center space-x-2">
                    <CloudArrowUpIcon className="w-5 h-5" />
                    <span>Deploy Latest Changes</span>
                  </span>
                )}
              </Button>
            </div>
            <p className="text-sm text-secondary-600 mb-4">
              Merge the latest claude branch into main and push to trigger Railway deployment. This will pull changes from remote, find the latest claude branch, merge it, and push to main.
            </p>
            {deploymentResult && (
              <div className={`mt-4 p-4 rounded-lg ${
                deploymentResult.success 
                  ? 'bg-success-50 border border-success-200' 
                  : 'bg-error-50 border border-error-200'
              }`}>
                <p className={`text-sm font-medium ${
                  deploymentResult.success ? 'text-success-800' : 'text-error-800'
                }`}>
                  {deploymentResult.success ? '✓ ' : '✗ '}
                  {deploymentResult.message}
                </p>
                {deploymentResult.branch_merged && (
                  <p className="text-xs text-secondary-600 mt-1">
                    Branch merged: {deploymentResult.branch_merged}
                  </p>
                )}
              </div>
            )}
          </Card>

          {/* Worker Health */}
          <Card className="mb-6">
            <h2 className="text-xl font-semibold text-secondary mb-4">Worker Health</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-sm text-secondary-600 mb-1">Main Queue</p>
                <p className="text-xl font-bold text-secondary">
                  {workerHealth?.main_queue_length.toLocaleString() || '0'}
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-sm text-secondary-600 mb-1">Dead Letter Queue</p>
                <p className="text-xl font-bold text-secondary">
                  {workerHealth?.dlq_length.toLocaleString() || '0'}
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <p className="text-sm text-secondary-600 mb-1">Recent Failures</p>
                <p className="text-xl font-bold text-secondary">
                  {workerHealth?.recent_failures_count.toLocaleString() || '0'}
                </p>
              </div>
            </div>
            <div className="text-sm text-secondary-600 space-y-1">
              <p>
                Last successful job:{' '}
                {workerHealth?.last_successful_job_at
                  ? new Date(workerHealth.last_successful_job_at).toLocaleString()
                  : 'none recorded'}
              </p>
              <p>
                Last failure:{' '}
                {workerHealth?.last_failure_at
                  ? new Date(workerHealth.last_failure_at).toLocaleString()
                  : 'none recorded'}
              </p>
            </div>
            <p className="mt-4 text-sm text-secondary-500">
              Workers restart automatically on each deploy (Railway) — there is no manual restart control.
            </p>
          </Card>

          {/* Recent Errors */}
          <Card>
            <h2 className="text-xl font-semibold text-secondary mb-4">Recent Errors</h2>
            <p className="text-sm text-secondary-600 mb-3">
              {(overview?.errors_past_24h || 0).toLocaleString()} errors in the past 24 hours — errors are tracked in the error log.
            </p>
            <Link to="/app/admin/errors" className="text-sm font-medium text-primary hover:text-primary/80 transition-colors">
              View error log →
            </Link>
          </Card>
        </>
      )}
    </div>
  )
}

