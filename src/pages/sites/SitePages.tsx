import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  HomeIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { fetchSitePages, deleteSitePage, type SitePage } from '../../api/client'

export default function SitePages() {
  const { siteId } = useParams<{ siteId: string }>()
  const navigate = useNavigate()
  const [pages, setPages] = useState<SitePage[]>([])
  const [loading, setLoading] = useState(true)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  useEffect(() => {
    if (siteId) loadPages()
  }, [siteId])

  async function loadPages() {
    if (!siteId) return
    try {
      setLoading(true)
      const data = await fetchSitePages(parseInt(siteId))
      setPages(data)
    } catch (err) {
      console.error('Failed to load pages:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(pageId: number) {
    if (!siteId) return
    try {
      await deleteSitePage(parseInt(siteId), pageId)
      setPages(pages.filter(p => p.id !== pageId))
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete page:', err)
    }
  }

  function getStatusBadge(status: string) {
    const styles: Record<string, string> = {
      published: 'pill-success',
      draft: 'pill bg-secondary-100 text-secondary-600',
    }
    return (
      <span className={styles[status] || styles.draft}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-secondary-900 tracking-display-sm">Pages</h1>
          <p className="text-secondary-500">Static pages for your site (About, Contact, etc.)</p>
        </div>
        <Button onClick={() => navigate(`/app/sites/${siteId}/pages/new`)}>
          <PlusIcon className="w-5 h-5 mr-2" />
          New Page
        </Button>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : pages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-secondary-500">
            <p className="font-medium mb-2">No pages yet</p>
            <p className="text-sm mb-4">Create static pages like About, Contact, Terms of Service</p>
            <Button onClick={() => navigate(`/app/sites/${siteId}/pages/new`)}>
              Create Page
            </Button>
          </div>
        ) : (
          <div className="divide-y divide-secondary-100">
            {pages.map((page) => (
              <div
                key={page.id}
                className="flex items-center justify-between py-4 px-2 hover:bg-secondary-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {page.is_homepage && (
                    <HomeIcon className="w-5 h-5 text-primary-500" title="Homepage" />
                  )}
                  <div>
                    <h3 className="font-medium text-secondary-900">{page.title}</h3>
                    <p className="font-mono text-[13px] text-secondary-500">/page/{page.slug}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {getStatusBadge(page.status)}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => navigate(`/app/sites/${siteId}/pages/${page.id}`)}
                      className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <PencilSquareIcon className="w-4 h-4 text-secondary-600" />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(page.id)}
                      className="p-2 hover:bg-error-50 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <TrashIcon className="w-4 h-4 text-error-500" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/50">
          <div className="bg-surface rounded-2xl p-6 max-w-sm w-full shadow-overlay border border-line">
            <h3 className="text-lg font-semibold text-secondary-900 mb-2">Delete Page?</h3>
            <p className="text-secondary-500 text-sm mb-6">
              This action cannot be undone. The page will be permanently deleted.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="btn flex-1 bg-error-500 text-paper border border-error-500 hover:bg-error-600 hover:border-error-600 focus:ring-error-500"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
