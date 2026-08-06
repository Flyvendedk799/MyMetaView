import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PlusIcon,
  GlobeAltIcon,
  EyeIcon,
  DocumentTextIcon,
  ArrowUpRightIcon,
  EllipsisHorizontalIcon,
  TrashIcon,
  PencilSquareIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/ui/PageHeader'
import { StatusBadge } from '../../components/ui/Badge'
import { IllustratedEmptyState } from '../../components/ui/EmptyState'
import { SkeletonCard } from '../../components/ui/Skeleton'
import { ConfirmDialog } from '../../components/ui/Modal'
import { fetchSites, deleteSite, publishSite, unpublishSite, type PublishedSite } from '../../api/client'

export default function SitesList() {
  const navigate = useNavigate()
  const [sites, setSites] = useState<PublishedSite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<PublishedSite | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [activeMenu, setActiveMenu] = useState<number | null>(null)

  useEffect(() => {
    loadSites()
  }, [])

  async function loadSites() {
    try {
      setLoading(true)
      setError('')
      const data = await fetchSites()
      setSites(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sites')
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) return
    try {
      setDeleteLoading(true)
      await deleteSite(deleteConfirm.id)
      setSites(sites.filter(s => s.id !== deleteConfirm.id))
      setDeleteConfirm(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete site')
    } finally {
      setDeleteLoading(false)
    }
  }

  async function handlePublish(site: PublishedSite) {
    try {
      const updated = await publishSite(site.id)
      setSites(sites.map(s => s.id === site.id ? updated : s))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish site')
    }
  }

  async function handleUnpublish(site: PublishedSite) {
    try {
      const updated = await unpublishSite(site.id)
      setSites(sites.map(s => s.id === site.id ? updated : s))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unpublish site')
    }
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  return (
    <div>
      <PageHeader
        title="My Sites"
        description="Manage your hosted blog and news sites"
        actions={
          <Button 
            onClick={() => navigate('/app/sites/new')}
            icon={<PlusIcon className="w-5 h-5" />}
          >
            Create Site
          </Button>
        }
      />

      {error && (
        <div className="alert alert-error mb-6 animate-fade-in">
          <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <div className="flex-1">{error}</div>
          <button onClick={() => setError('')} className="text-error-700 hover:text-error-900">
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : sites.length === 0 ? (
        <Card>
          <IllustratedEmptyState
            illustration="sites"
            title="No sites yet"
            description="Create your first white-label blog or news site. Connect your domain and choose a template to get started."
            action={{
              label: 'Create Your First Site',
              onClick: () => navigate('/app/sites/new'),
              icon: <PlusIcon className="w-5 h-5" />,
            }}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-stagger">
          {sites.map((site, index) => (
            <Card 
              key={site.id} 
              variant="hover"
              className="group relative"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {/* Gradient accent top */}
              <div className="absolute top-0 left-0 right-0 h-1 bg-accent-500 rounded-t-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-bold text-secondary-900 truncate group-hover:text-primary-600 transition-colors">
                      {site.name}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-secondary-500">
                    <GlobeAltIcon className="w-4 h-4 flex-shrink-0" />
                    <span className="truncate">{site.domain?.name || 'No domain'}</span>
                  </div>
                </div>
                
                {/* Actions dropdown */}
                <div className="relative">
                  <button
                    onClick={() => setActiveMenu(activeMenu === site.id ? null : site.id)}
                    className="p-2 text-secondary-400 hover:text-secondary-600 hover:bg-secondary-100 rounded-lg transition-colors"
                  >
                    <EllipsisHorizontalIcon className="w-5 h-5" />
                  </button>
                  
                  {activeMenu === site.id && (
                    <>
                      <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setActiveMenu(null)}
                      />
                      <div className="dropdown absolute right-0 w-48 z-20">
                        <button
                          onClick={() => {
                            navigate(`/app/sites/${site.id}`)
                            setActiveMenu(null)
                          }}
                          className="dropdown-item"
                        >
                          <EyeIcon className="w-4 h-4 text-secondary-400" />
                          View Dashboard
                        </button>
                        <button
                          onClick={() => {
                            navigate(`/app/sites/${site.id}/posts`)
                            setActiveMenu(null)
                          }}
                          className="dropdown-item"
                        >
                          <DocumentTextIcon className="w-4 h-4 text-secondary-400" />
                          Manage Posts
                        </button>
                        <button
                          onClick={() => {
                            navigate(`/app/sites/${site.id}/settings`)
                            setActiveMenu(null)
                          }}
                          className="dropdown-item"
                        >
                          <PencilSquareIcon className="w-4 h-4 text-secondary-400" />
                          Edit Settings
                        </button>
                        
                        <div className="dropdown-divider" />
                        
                        {site.status === 'published' ? (
                          <button
                            onClick={() => {
                              handleUnpublish(site)
                              setActiveMenu(null)
                            }}
                            className="dropdown-item text-warning-600"
                          >
                            <ArrowPathIcon className="w-4 h-4" />
                            Unpublish
                          </button>
                        ) : (
                          <button
                            onClick={() => {
                              handlePublish(site)
                              setActiveMenu(null)
                            }}
                            className="dropdown-item text-success-600"
                          >
                            <ArrowUpRightIcon className="w-4 h-4" />
                            Publish
                          </button>
                        )}
                        
                        <button
                          onClick={() => {
                            setDeleteConfirm(site)
                            setActiveMenu(null)
                          }}
                          className="dropdown-item text-error-600"
                        >
                          <TrashIcon className="w-4 h-4" />
                          Delete Site
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Status & Template */}
              <div className="flex items-center gap-3 mb-4">
                <StatusBadge status={site.status as any} />
                <span className="text-xs text-secondary-400">
                  {site.template_id || 'Modern Blog'}
                </span>
              </div>

              {/* Stats preview */}
              <div className="grid grid-cols-3 gap-2 py-4 border-t border-secondary-100">
                <div className="text-center">
                  <p className="text-lg font-bold text-secondary-900">—</p>
                  <p className="text-xs text-secondary-500">Posts</p>
                </div>
                <div className="text-center border-x border-secondary-100">
                  <p className="text-lg font-bold text-secondary-900">—</p>
                  <p className="text-xs text-secondary-500">Pages</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold text-secondary-900">—</p>
                  <p className="text-xs text-secondary-500">Views</p>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between pt-4 border-t border-secondary-100">
                <p className="text-xs text-secondary-500">
                  Updated {formatDate(site.updated_at)}
                </p>
                
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate(`/app/sites/${site.id}`)}
                  >
                    Open
                  </Button>
                  {site.status === 'published' && site.domain?.name && (
                    <a
                      href={`https://${site.domain.name}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-secondary-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    >
                      <ArrowUpRightIcon className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            </Card>
          ))}
          
          {/* Add new site card */}
          <Card
            variant="interactive"
            className="flex flex-col items-center justify-center min-h-[280px] border-2 border-dashed border-secondary-200 hover:border-primary-300 bg-secondary-50/50"
            onClick={() => navigate('/app/sites/new')}
          >
            <div className="w-14 h-14 rounded-2xl bg-primary-100 flex items-center justify-center mb-4">
              <PlusIcon className="w-7 h-7 text-primary-600" />
            </div>
            <p className="font-semibold text-secondary-700">Create New Site</p>
            <p className="text-sm text-secondary-500 mt-1">Start with a template</p>
          </Card>
        </div>
      )}

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        isOpen={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        onConfirm={handleDelete}
        title="Delete Site?"
        message={`Are you sure you want to delete "${deleteConfirm?.name}"? This action cannot be undone and will permanently delete all posts, pages, and media.`}
        confirmText="Delete Site"
        variant="danger"
        loading={deleteLoading}
      />
    </div>
  )
}
