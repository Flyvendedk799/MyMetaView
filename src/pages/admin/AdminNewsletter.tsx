import { useState, useEffect } from 'react'
import {
  MagnifyingGlassIcon,
  ArrowDownTrayIcon,
  EnvelopeIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import {
  fetchNewsletterSubscribers,
  exportNewsletterSubscribers,
  type NewsletterSubscriber,
  type NewsletterSubscriberList,
} from '../../api/client'

export default function AdminNewsletter() {
  const [subscribers, setSubscribers] = useState<NewsletterSubscriber[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [perPage] = useState(50)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [isExporting, setIsExporting] = useState(false)

  useEffect(() => {
    loadSubscribers()
  }, [page, search, sourceFilter])

  const loadSubscribers = async () => {
    try {
      setLoading(true)
      setError(null)
      const data: NewsletterSubscriberList = await fetchNewsletterSubscribers({
        page,
        per_page: perPage,
        search: search || undefined,
        source: sourceFilter !== 'all' ? sourceFilter : undefined,
      })
      setSubscribers(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load subscribers')
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async (format: 'csv' | 'xlsx') => {
    try {
      setIsExporting(true)
      const blob = await exportNewsletterSubscribers(format, sourceFilter !== 'all' ? sourceFilter : undefined)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `newsletter_subscribers_${new Date().toISOString().split('T')[0]}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export subscribers')
    } finally {
      setIsExporting(false)
    }
  }

  // Get unique sources for filter
  const uniqueSources = Array.from(new Set(subscribers.map(s => s.source)))

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-secondary mb-2">Admin / Newsletter Subscribers</h1>
          <p className="text-secondary-600">Manage newsletter email subscriptions</p>
        </div>
        <div className="flex items-center space-x-3">
          <Button
            onClick={() => handleExport('csv')}
            disabled={isExporting || total === 0}
            className="flex items-center space-x-2"
          >
            <ArrowDownTrayIcon className="w-4 h-4" />
            <span>Export CSV</span>
          </Button>
          <Button
            onClick={() => handleExport('xlsx')}
            disabled={isExporting || total === 0}
            variant="secondary"
            className="flex items-center space-x-2"
          >
            <ArrowDownTrayIcon className="w-4 h-4" />
            <span>Export XLSX</span>
          </Button>
        </div>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {/* Search and Filters */}
      <Card className="mb-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1) // Reset to first page on search
              }}
              placeholder="Search by email..."
              className="w-full pl-10 pr-4 py-2.5 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
          </div>
          <select
            value={sourceFilter}
            onChange={(e) => {
              setSourceFilter(e.target.value)
              setPage(1) // Reset to first page on filter change
            }}
            className="px-4 py-2.5 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          >
            <option value="all">All Sources</option>
            {uniqueSources.map((source) => (
              <option key={source} value={source}>
                {source.charAt(0).toUpperCase() + source.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-secondary-600 mb-1">Total Subscribers</p>
              <p className="text-2xl font-bold text-secondary">{total.toLocaleString()}</p>
            </div>
            <EnvelopeIcon className="w-8 h-8 text-primary" />
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-secondary-600 mb-1">Active</p>
              <p className="text-2xl font-bold text-success-600">
                {subscribers.filter(s => s.is_active).length.toLocaleString()}
              </p>
            </div>
            <CheckCircleIcon className="w-8 h-8 text-success-500" />
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-secondary-600 mb-1">This Page</p>
              <p className="text-2xl font-bold text-secondary-900">{subscribers.length.toLocaleString()}</p>
            </div>
            <XCircleIcon className="w-8 h-8 text-secondary-400" />
          </div>
        </Card>
      </div>

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Loading subscribers...</p>
          </div>
        </Card>
      ) : (
        <>
          <Card className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-secondary-200">
                  <th className="text-left py-3 px-4 font-semibold text-secondary-700">Email</th>
                  <th className="text-left py-3 px-4 font-semibold text-secondary-700">Source</th>
                  <th className="text-left py-3 px-4 font-semibold text-secondary-700">Subscribed At</th>
                  <th className="text-left py-3 px-4 font-semibold text-secondary-700">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-secondary-700">Consent</th>
                  <th className="text-left py-3 px-4 font-semibold text-secondary-700">IP Address</th>
                </tr>
              </thead>
              <tbody>
                {subscribers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-12 text-secondary-500">
                      No subscribers found
                    </td>
                  </tr>
                ) : (
                  subscribers.map((subscriber) => (
                    <tr key={subscriber.id} className="border-b border-secondary-100 hover:bg-secondary-50">
                      <td className="py-3 px-4 font-medium text-secondary-900">{subscriber.email}</td>
                      <td className="py-3 px-4">
                        <span className="inline-block px-2 py-1 bg-secondary-100 text-secondary-700 text-xs font-medium rounded capitalize">
                          {subscriber.source}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-secondary-600">
                        {new Date(subscriber.subscribed_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4">
                        {subscriber.is_active ? (
                          <span className="inline-flex items-center space-x-1 text-success-600">
                            <CheckCircleIcon className="w-4 h-4" />
                            <span className="text-sm font-medium">Active</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 text-error-600">
                            <XCircleIcon className="w-4 h-4" />
                            <span className="text-sm font-medium">Inactive</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {subscriber.consent_given ? (
                          <span className="text-success-600 text-sm font-medium">Yes</span>
                        ) : (
                          <span className="text-error-600 text-sm font-medium">No</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-sm text-secondary-500">
                        {subscriber.ip_address || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-between">
              <div className="text-sm text-secondary-600">
                Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of {total} subscribers
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  variant="secondary"
                >
                  Previous
                </Button>
                <span className="px-4 py-2 text-sm text-secondary-700">
                  Page {page} of {totalPages}
                </span>
                <Button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  variant="secondary"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

