import { useState, useEffect } from 'react'
import { ArrowPathIcon, ExclamationTriangleIcon, CloudArrowUpIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { fetchAdminSystemOverview, fetchAdminWorkerHealth, triggerDeployment, type SystemOverview, type WorkerHealth } from '../../api/client'

export default function AdminSystem() {
  const [overview, setOverview] = useState<SystemOverview | null>(null)
  const [workerHealth, setWorkerHealth] = useState<WorkerHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [restarting, setRestarting] = useState(false)
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

  const handleRestartWorkers = async () => {
    if (!window.confirm('Are you sure you want to restart workers? This will interrupt any running jobs.')) {
      return
    }

    try {
      setRestarting(true)
      // Worker restart endpoint would be implemented here
      // For now, this is a placeholder - Railway handles worker restarts via service restart
      await new Promise((resolve) => setTimeout(resolve, 2000))
      alert('Worker restart initiated (service restart required)')
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to restart workers')
    } finally {
      setRestarting(false)
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
                  {deploymentResult.success ? 'âœ“ ' : 'âœ— '}
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

          {/* Worker Management */}
          <Card className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-secondary">Worker Management</h2>
              <Button
                onClick={handleRestartWorkers}
                disabled={restarting}
                variant="secondary"
              >
                {restarting ? (
                  <span className="flex items-center space-x-2">
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                    <span>Restarting...</span>
                  </span>
                ) : (
                  <span className="flex items-center space-x-2">
                    <ArrowPathIcon className="w-5 h-5" />
                    <span>Restart Workers</span>
                  </span>
                )}
              </Button>
            </div>
            <p className="text-sm text-secondary-600">
              Worker status monitoring and management. Restart workers if they become unresponsive.
            </p>
            <div className="mt-4 p-4 bg-secondary-50 rounded-lg">
              <p className="text-sm text-secondary-600">
                <strong>Note:</strong> Worker restart functionality is currently stubbed. Implement actual worker management endpoint.
              </p>
            </div>
          </Card>

          {/* Error Logs Placeholder */}
          <Card>
            <h2 className="text-xl font-semibold text-secondary mb-4">Recent Errors</h2>
            <div className="p-4 bg-secondary-50 rounded-lg">
              <p className="text-sm text-secondary-600">
                Error logs will be displayed here once error logging is fully implemented in webhooks and jobs.
              </p>
              <p className="text-xs text-secondary-500 mt-2">
                Latest {overview?.errors_past_24h || 0} errors in the past 24 hours.
              </p>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

