import { useState, useEffect } from 'react'
import Card from '../../components/ui/Card'
import { fetchApi } from '../../api/client'

interface ErrorRecord {
  id: number
  path: string
  method: string
  user_id: number | null
  organization_id: number | null
  error_message: string
  stacktrace: string | null
  request_id: string | null
  timestamp: string
}

export default function AdminErrors() {
  const [errors, setErrors] = useState<ErrorRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedError, setSelectedError] = useState<ErrorRecord | null>(null)

  useEffect(() => {
    loadErrors()
  }, [])

  const loadErrors = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchApi<ErrorRecord[]>('/api/v1/admin/errors?limit=50&skip=0')
      setErrors(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load errors')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="heading-3 mb-2">Admin / Errors</h1>
        <p className="text-muted">View and analyze system errors</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-100">
          <p className="text-error-600">Error: {error}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Loading errors...</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <Card>
              <h2 className="text-xl font-semibold text-secondary-900 mb-4">Recent Errors</h2>
              <div className="space-y-2">
                {errors.length === 0 ? (
                  <p className="text-secondary-500 text-center py-8">No errors found</p>
                ) : (
                  errors.map((err) => (
                    <div
                      key={err.id}
                      onClick={() => setSelectedError(err)}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                        selectedError?.id === err.id
                          ? 'border-primary-500 bg-brand-50'
                          : 'border-secondary-200 hover:border-secondary-300'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-mono text-[13px] font-medium text-secondary-900">{err.method} {err.path}</p>
                          <p className="text-sm text-secondary-600 mt-1 line-clamp-2">{err.error_message}</p>
                          <p className="font-mono text-xs text-secondary-400 mt-2">
                            {new Date(err.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>

          <div>
            {selectedError ? (
              <Card>
                <h2 className="text-xl font-semibold text-secondary-900 mb-4">Error Details</h2>
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-secondary-600">Path</p>
                    <p className="font-mono text-[13px] text-secondary-900">{selectedError.method} {selectedError.path}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-secondary-600">Message</p>
                    <p className="text-sm text-secondary-900">{selectedError.error_message}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-secondary-600">Timestamp</p>
                    <p className="font-mono text-[13px] text-secondary-900">
                      {new Date(selectedError.timestamp).toLocaleString()}
                    </p>
                  </div>
                  {selectedError.request_id && (
                    <div>
                      <p className="text-sm font-medium text-secondary-600">Request ID</p>
                      <p className="font-mono text-[13px] text-secondary-900">{selectedError.request_id}</p>
                    </div>
                  )}
                  {selectedError.stacktrace && (
                    <div>
                      <p className="text-sm font-medium text-secondary-600 mb-2">Stacktrace</p>
                      <pre className="font-mono text-xs text-secondary-700 bg-secondary-50 p-3 rounded overflow-auto max-h-96">
                        {selectedError.stacktrace}
                      </pre>
                    </div>
                  )}
                </div>
              </Card>
            ) : (
              <Card>
                <p className="text-secondary-500 text-center py-8">Select an error to view details</p>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

