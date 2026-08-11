import { useState, useEffect } from 'react'
import { TrashIcon, ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { fetchAdminPreviews, deleteAdminPreview, fetchAdminPreviewVariants, deleteAdminPreviewVariant } from '../../api/client'
import type { AdminPreview, PreviewVariant } from '../../api/types'

export default function AdminPreviews() {
  const [previews, setPreviews] = useState<AdminPreview[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [filterDomain, setFilterDomain] = useState<string>('')
  const [filterUser, setFilterUser] = useState<string>('')
  const [expandedPreviews, setExpandedPreviews] = useState<Set<number>>(new Set())
  const [variants, setVariants] = useState<Record<number, PreviewVariant[]>>({})
  const limit = 50

  useEffect(() => {
    loadPreviews()
  }, [page])

  const loadPreviews = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchAdminPreviews(page * limit, limit)
      setPreviews(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load previews')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (previewId: number, previewTitle: string) => {
    if (!window.confirm(`Are you sure you want to delete preview "${previewTitle}"? This action cannot be undone.`)) {
      return
    }

    try {
      await deleteAdminPreview(previewId)
      await loadPreviews()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete preview')
    }
  }
  
  const handleToggleExpand = async (previewId: number) => {
    const isExpanded = expandedPreviews.has(previewId)
    if (isExpanded) {
      setExpandedPreviews(prev => {
        const newSet = new Set(prev)
        newSet.delete(previewId)
        return newSet
      })
    } else {
      setExpandedPreviews(prev => new Set(prev).add(previewId))
      // Load variants if not already loaded
      if (!variants[previewId]) {
        try {
          const variantData = await fetchAdminPreviewVariants(previewId)
          setVariants(prev => ({ ...prev, [previewId]: variantData }))
        } catch (err) {
          console.error(`Failed to load variants for preview ${previewId}:`, err)
        }
      }
    }
  }
  
  const handleDeleteVariant = async (variantId: number, previewId: number) => {
    if (!window.confirm('Are you sure you want to delete this variant?')) {
      return
    }
    
    try {
      await deleteAdminPreviewVariant(variantId)
      // Reload variants
      const variantData = await fetchAdminPreviewVariants(previewId)
      setVariants(prev => ({ ...prev, [previewId]: variantData }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete variant')
    }
  }

  const filteredPreviews = previews.filter((preview) => {
    if (filterDomain && !preview.domain.toLowerCase().includes(filterDomain.toLowerCase())) {
      return false
    }
    if (filterUser && !preview.user_email.toLowerCase().includes(filterUser.toLowerCase())) {
      return false
    }
    return true
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Admin / Previews</h1>
        <p className="text-muted">View and manage all previews across the system</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-secondary-700 mb-2">Filter by Domain</label>
          <input
            type="text"
            placeholder="Search domain..."
            value={filterDomain}
            onChange={(e) => setFilterDomain(e.target.value)}
            className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-secondary-700 mb-2">Filter by User</label>
          <input
            type="text"
            placeholder="Search user email..."
            value={filterUser}
            onChange={(e) => setFilterUser(e.target.value)}
            className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
          />
        </div>
      </div>

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Loading previews...</p>
          </div>
        </Card>
      ) : (
        <>
          <Card className="p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-secondary-200">
                <thead className="bg-secondary-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase w-12"></th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">Title</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">URL</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">Domain</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">User</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">Type</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">Clicks</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-secondary-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-secondary-200">
                  {filteredPreviews.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-secondary-500">
                        No previews found
                      </td>
                    </tr>
                  ) : (
                    filteredPreviews.map((preview) => {
                      const isExpanded = expandedPreviews.has(preview.id)
                      const previewVariants = variants[preview.id] || []
                      
                      return (
                        <>
                          <tr key={preview.id} className="hover:bg-secondary-50">
                            <td className="px-6 py-4 whitespace-nowrap">
                              {previewVariants.length > 0 && (
                                <button
                                  onClick={() => handleToggleExpand(preview.id)}
                                  className="text-secondary-500 hover:text-secondary-700"
                                >
                                  {isExpanded ? (
                                    <ChevronDownIcon className="w-5 h-5" />
                                  ) : (
                                    <ChevronRightIcon className="w-5 h-5" />
                                  )}
                                </button>
                              )}
                            </td>
                            <td className="px-6 py-4">
                              <div className="text-sm font-medium text-secondary-900">{preview.title}</div>
                            </td>
                            <td className="px-6 py-4">
                              <div className="text-sm text-secondary-500 max-w-xs truncate">{preview.url}</div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="text-sm text-secondary-900">{preview.domain}</div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="text-sm text-secondary-900">{preview.user_email}</div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="px-2 py-1 text-xs font-medium bg-secondary-100 text-secondary-800 rounded-full capitalize">
                                {preview.type}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="text-sm text-secondary-900">{preview.monthly_clicks.toLocaleString()}</div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                              <button
                                onClick={() => handleDelete(preview.id, preview.title)}
                                className="text-error-600 hover:text-error-800"
                              >
                                <TrashIcon className="w-5 h-5" />
                              </button>
                            </td>
                          </tr>
                          {isExpanded && previewVariants.length > 0 && (
                            <tr>
                              <td colSpan={8} className="px-6 py-4 bg-secondary-50">
                                <div className="ml-8">
                                  <h4 className="text-sm font-semibold text-secondary-700 mb-2">Variants</h4>
                                  <div className="space-y-2">
                                    {previewVariants.map((variant) => (
                                      <div key={variant.id} className="bg-white p-3 rounded-lg border border-secondary-200 flex items-center justify-between">
                                        <div className="flex-1">
                                          <div className="flex items-center space-x-2 mb-1">
                                            <span className="text-xs font-medium text-secondary-500">Variant {variant.variant_key.toUpperCase()}</span>
                                            <span className="text-sm font-medium text-secondary-900">{variant.title}</span>
                                          </div>
                                          {variant.description && (
                                            <p className="text-xs text-secondary-600 line-clamp-1">{variant.description}</p>
                                          )}
                                        </div>
                                        <button
                                          onClick={() => handleDeleteVariant(variant.id, preview.id)}
                                          className="text-error-600 hover:text-error-800 ml-4"
                                        >
                                          <TrashIcon className="w-4 h-4" />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <Button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              variant="secondary"
            >
              Previous
            </Button>
            <span className="text-secondary-600">Page {page + 1}</span>
            <Button
              onClick={() => setPage(page + 1)}
              disabled={previews.length < limit}
              variant="secondary"
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

