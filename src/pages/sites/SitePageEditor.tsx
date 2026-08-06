import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import RichTextEditor from '../../components/editor/RichTextEditor'
import {
  fetchSitePage,
  createSitePage,
  updateSitePage,
  type SitePage,
  type SitePageCreate,
  type SitePageUpdate,
} from '../../api/client'

export default function SitePageEditor() {
  const { siteId, pageId } = useParams<{ siteId: string; pageId?: string }>()
  const navigate = useNavigate()
  const isNew = !pageId || pageId === 'new'

  // Form state
  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [content, setContent] = useState('')
  const [status, setStatus] = useState<'draft' | 'published'>('draft')
  const [isHomepage, setIsHomepage] = useState(false)

  // SEO fields
  const [metaTitle, setMetaTitle] = useState('')
  const [metaDescription, setMetaDescription] = useState('')

  // UI state
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showSeo, setShowSeo] = useState(false)
  const [autoSlug, setAutoSlug] = useState(true)

  useEffect(() => {
    if (siteId && !isNew) {
      loadPage()
    }
  }, [siteId, pageId])

  useEffect(() => {
    if (autoSlug && title) {
      const generatedSlug = title
        .toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 250)
      setSlug(generatedSlug)
    }
  }, [title, autoSlug])

  async function loadPage() {
    if (!siteId || !pageId) return
    try {
      setLoading(true)
      const page = await fetchSitePage(parseInt(siteId), parseInt(pageId))
      
      setTitle(page.title)
      setSlug(page.slug)
      setContent(page.content || '')
      setStatus(page.status as 'draft' | 'published')
      setIsHomepage(page.is_homepage || false)
      setMetaTitle(page.meta_title || '')
      setMetaDescription(page.meta_description || '')
      setAutoSlug(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load page')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(publishStatus?: 'draft' | 'published') {
    if (!siteId || !title.trim()) {
      setError('Title is required')
      return
    }

    try {
      setSaving(true)
      setError('')

      const finalStatus = publishStatus || status

      const pageData: SitePageCreate | SitePageUpdate = {
        title: title.trim(),
        slug: slug.trim() || undefined,
        content,
        status: finalStatus,
        is_homepage: isHomepage,
        meta_title: metaTitle.trim() || undefined,
        meta_description: metaDescription.trim() || undefined,
      }

      if (isNew) {
        await createSitePage(parseInt(siteId), pageData as SitePageCreate)
      } else {
        await updateSitePage(parseInt(siteId), parseInt(pageId!), pageData as SitePageUpdate)
      }

      navigate(`/app/sites/${siteId}/pages`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save page')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </Card>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(`/app/sites/${siteId}/pages`)}
            className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </button>
          <h1 className="font-display text-2xl font-semibold text-secondary-900 tracking-display-sm">
            {isNew ? 'New Page' : 'Edit Page'}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => handleSave('draft')} disabled={saving}>
            {saving ? 'Saving...' : 'Save Draft'}
          </Button>
          <Button onClick={() => handleSave('published')} disabled={saving}>
            {saving ? 'Publishing...' : 'Publish'}
          </Button>
        </div>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-100">
          <div className="flex items-center gap-2">
            <XMarkIcon className="w-5 h-5 text-error-500" />
            <p className="text-error-600">{error}</p>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Title */}
          <Card>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Page title..."
              className="w-full font-display text-3xl font-semibold tracking-display text-secondary-900 bg-transparent border-0 focus:outline-none focus:ring-0 placeholder-secondary-300"
            />
          </Card>

          {/* Content Editor */}
          <Card className="p-0 overflow-hidden">
            <RichTextEditor
              content={content}
              onChange={setContent}
              placeholder="Write your page content..."
              minHeight="400px"
            />
          </Card>

          {/* SEO Section */}
          <Card>
            <button
              onClick={() => setShowSeo(!showSeo)}
              className="w-full flex items-center justify-between text-left"
            >
              <span className="font-semibold text-secondary-900">SEO Settings</span>
              {showSeo ? (
                <ChevronUpIcon className="w-5 h-5 text-secondary-500" />
              ) : (
                <ChevronDownIcon className="w-5 h-5 text-secondary-500" />
              )}
            </button>
            
            {showSeo && (
              <div className="mt-4 space-y-4 pt-4 border-t border-line">
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">
                    Meta Title
                    <span className="text-secondary-400 ml-2">({metaTitle.length}/70)</span>
                  </label>
                  <input
                    type="text"
                    value={metaTitle}
                    onChange={(e) => setMetaTitle(e.target.value.slice(0, 70))}
                    placeholder="SEO title (defaults to page title)"
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">
                    Meta Description
                    <span className="text-secondary-400 ml-2">({metaDescription.length}/160)</span>
                  </label>
                  <textarea
                    value={metaDescription}
                    onChange={(e) => setMetaDescription(e.target.value.slice(0, 160))}
                    placeholder="SEO description"
                    rows={2}
                    className="input resize-none"
                  />
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Publish</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">
                  Status
                </label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as 'draft' | 'published')}
                  className="select"
                >
                  <option value="draft">Draft</option>
                  <option value="published">Published</option>
                </select>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isHomepage}
                  onChange={(e) => setIsHomepage(e.target.checked)}
                  className="w-4 h-4 text-primary-500 border-secondary-300 rounded focus:ring-primary-500"
                />
                <span className="text-sm text-secondary-700">Set as Homepage</span>
              </label>
            </div>
          </Card>

          {/* URL Slug */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">URL Slug</h3>
            <input
              type="text"
              value={slug}
              onChange={(e) => {
                setSlug(e.target.value)
                setAutoSlug(false)
              }}
              placeholder="page-url-slug"
              className="input font-mono text-[13px]"
            />
            <p className="font-mono text-xs text-secondary-500 mt-2">
              /page/{slug || 'page-url-slug'}
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}
