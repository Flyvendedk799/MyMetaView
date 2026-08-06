import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  PhotoIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CalendarIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import RichTextEditor from '../../components/editor/RichTextEditor'
import MediaPickerModal from '../../components/media/MediaPickerModal'
import {
  fetchSitePost,
  createSitePost,
  updateSitePost,
  fetchSiteCategories,
  type SitePost,
  type SitePostCreate,
  type SitePostUpdate,
  type SiteCategory,
  type SiteMedia,
} from '../../api/client'

export default function SitePostEditor() {
  const { siteId, postId } = useParams<{ siteId: string; postId?: string }>()
  const navigate = useNavigate()
  const isNew = !postId || postId === 'new'

  // Form state
  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [content, setContent] = useState('')
  const [excerpt, setExcerpt] = useState('')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [tags, setTags] = useState('')
  const [featuredImage, setFeaturedImage] = useState('')
  const [featuredImageAlt, setFeaturedImageAlt] = useState('')
  const [status, setStatus] = useState<'draft' | 'published' | 'scheduled'>('draft')
  const [scheduledAt, setScheduledAt] = useState('')
  const [isPinned, setIsPinned] = useState(false)
  const [isFeatured, setIsFeatured] = useState(false)

  // SEO fields
  const [metaTitle, setMetaTitle] = useState('')
  const [metaDescription, setMetaDescription] = useState('')
  const [metaKeywords, setMetaKeywords] = useState('')

  // UI state
  const [categories, setCategories] = useState<SiteCategory[]>([])
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showSeo, setShowSeo] = useState(false)
  const [showMediaPicker, setShowMediaPicker] = useState(false)
  const [autoSlug, setAutoSlug] = useState(true)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)

  useEffect(() => {
    if (siteId) {
      loadCategories()
      if (!isNew) {
        loadPost()
      }
    }
  }, [siteId, postId])

  // Auto-generate slug from title
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

  async function loadCategories() {
    if (!siteId) return
    try {
      const data = await fetchSiteCategories(parseInt(siteId))
      setCategories(data)
    } catch (err) {
      console.error('Failed to load categories:', err)
    }
  }

  async function loadPost() {
    if (!siteId || !postId) return
    try {
      setLoading(true)
      const post = await fetchSitePost(parseInt(siteId), parseInt(postId))
      
      setTitle(post.title)
      setSlug(post.slug)
      setContent(post.content || '')
      setExcerpt(post.excerpt || '')
      setCategoryId(post.category_id || null)
      setTags(post.tags || '')
      setFeaturedImage(post.featured_image || '')
      setFeaturedImageAlt(post.featured_image_alt || '')
      setStatus(post.status as 'draft' | 'published' | 'scheduled')
      setScheduledAt(post.scheduled_at || '')
      setIsPinned(post.is_pinned || false)
      setIsFeatured(post.is_featured || false)
      setMetaTitle(post.meta_title || '')
      setMetaDescription(post.meta_description || '')
      setMetaKeywords(post.meta_keywords || '')
      setAutoSlug(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load post')
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

      const postData: SitePostCreate | SitePostUpdate = {
        title: title.trim(),
        slug: slug.trim() || undefined,
        content,
        excerpt: excerpt.trim() || undefined,
        category_id: categoryId || undefined,
        tags: tags.trim() || undefined,
        featured_image: featuredImage || undefined,
        featured_image_alt: featuredImageAlt || undefined,
        status: finalStatus,
        scheduled_at: finalStatus === 'scheduled' && scheduledAt ? scheduledAt : undefined,
        is_pinned: isPinned,
        is_featured: isFeatured,
        meta_title: metaTitle.trim() || undefined,
        meta_description: metaDescription.trim() || undefined,
        meta_keywords: metaKeywords.trim() || undefined,
      }

      if (isNew) {
        await createSitePost(parseInt(siteId), postData as SitePostCreate)
      } else {
        await updateSitePost(parseInt(siteId), parseInt(postId!), postData as SitePostUpdate)
      }

      setLastSaved(new Date())
      
      if (publishStatus === 'published') {
        navigate(`/app/sites/${siteId}/posts`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save post')
    } finally {
      setSaving(false)
    }
  }

  function handleMediaSelect(media: SiteMedia) {
    setFeaturedImage(media.file_path)
    setFeaturedImageAlt(media.alt_text || '')
    setShowMediaPicker(false)
  }

  function handleInsertImage() {
    // This would open media picker for inline images
    // For now, we'll just show an alert
    setShowMediaPicker(true)
  }

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </Card>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(`/app/sites/${siteId}/posts`)}
            className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-secondary">
              {isNew ? 'New Post' : 'Edit Post'}
            </h1>
            {lastSaved && (
              <p className="text-sm text-muted">
                Last saved: {lastSaved.toLocaleTimeString()}
              </p>
            )}
          </div>
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
        <Card className="mb-6 bg-error-50 border-error-200">
          <div className="flex items-center gap-2">
            <XMarkIcon className="w-5 h-5 text-error-600" />
            <p className="text-error-800">{error}</p>
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
              placeholder="Post title..."
              className="w-full text-3xl font-bold border-0 focus:outline-none focus:ring-0 placeholder-secondary-300"
            />
          </Card>

          {/* Content Editor */}
          <Card className="p-0 overflow-hidden">
            <RichTextEditor
              content={content}
              onChange={setContent}
              placeholder="Write your post content..."
              onInsertImage={handleInsertImage}
              minHeight="400px"
            />
          </Card>

          {/* Excerpt */}
          <Card>
            <label className="block text-sm font-medium text-secondary-700 mb-2">
              Excerpt
            </label>
            <textarea
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
              placeholder="Brief summary of the post (used in listings and meta description)..."
              rows={3}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none"
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
              <div className="mt-4 space-y-4 pt-4 border-t">
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">
                    Meta Title
                    <span className="text-secondary-400 ml-2">({metaTitle.length}/70)</span>
                  </label>
                  <input
                    type="text"
                    value={metaTitle}
                    onChange={(e) => setMetaTitle(e.target.value.slice(0, 70))}
                    placeholder="SEO title (defaults to post title)"
                    className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
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
                    placeholder="SEO description (defaults to excerpt)"
                    rows={2}
                    className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">
                    Meta Keywords
                  </label>
                  <input
                    type="text"
                    value={metaKeywords}
                    onChange={(e) => setMetaKeywords(e.target.value)}
                    placeholder="keyword1, keyword2, keyword3"
                    className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status & Scheduling */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Publish</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">
                  Status
                </label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as 'draft' | 'published' | 'scheduled')}
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="draft">Draft</option>
                  <option value="published">Published</option>
                  <option value="scheduled">Scheduled</option>
                </select>
              </div>

              {status === 'scheduled' && (
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">
                    <CalendarIcon className="w-4 h-4 inline mr-1" />
                    Publish Date
                  </label>
                  <input
                    type="datetime-local"
                    value={scheduledAt}
                    onChange={(e) => setScheduledAt(e.target.value)}
                    className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              )}

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isPinned}
                    onChange={(e) => setIsPinned(e.target.checked)}
                    className="w-4 h-4 text-primary border-secondary-300 rounded focus:ring-primary"
                  />
                  <span className="text-sm text-secondary-700">Pin to top</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isFeatured}
                    onChange={(e) => setIsFeatured(e.target.checked)}
                    className="w-4 h-4 text-primary border-secondary-300 rounded focus:ring-primary"
                  />
                  <span className="text-sm text-secondary-700">Featured</span>
                </label>
              </div>
            </div>
          </Card>

          {/* URL Slug */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">URL Slug</h3>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={slug}
                onChange={(e) => {
                  setSlug(e.target.value)
                  setAutoSlug(false)
                }}
                placeholder="post-url-slug"
                className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-mono text-sm"
              />
            </div>
            <p className="text-xs text-secondary-500 mt-2">
              /posts/{slug || 'post-url-slug'}
            </p>
          </Card>

          {/* Category */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Category</h3>
            <select
              value={categoryId || ''}
              onChange={(e) => setCategoryId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">No category</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </Card>

          {/* Tags */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Tags</h3>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="tag1, tag2, tag3"
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="text-xs text-secondary-500 mt-2">Separate tags with commas</p>
          </Card>

          {/* Featured Image */}
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Featured Image</h3>
            {featuredImage ? (
              <div className="relative">
                <img
                  src={featuredImage}
                  alt={featuredImageAlt}
                  className="w-full aspect-video object-cover rounded-lg"
                />
                <button
                  onClick={() => {
                    setFeaturedImage('')
                    setFeaturedImageAlt('')
                  }}
                  className="absolute top-2 right-2 p-1 bg-white rounded-full shadow hover:bg-secondary-100"
                >
                  <XMarkIcon className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowMediaPicker(true)}
                className="w-full aspect-video border-2 border-dashed border-secondary-300 rounded-lg flex flex-col items-center justify-center text-secondary-400 hover:border-primary hover:text-primary transition-colors"
              >
                <PhotoIcon className="w-8 h-8 mb-2" />
                <span className="text-sm">Add Featured Image</span>
              </button>
            )}
            {featuredImage && (
              <div className="mt-3">
                <label className="block text-sm font-medium text-secondary-700 mb-1">
                  Alt Text
                </label>
                <input
                  type="text"
                  value={featuredImageAlt}
                  onChange={(e) => setFeaturedImageAlt(e.target.value)}
                  placeholder="Describe the image..."
                  className="w-full px-3 py-2 text-sm border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Media Picker Modal */}
      {showMediaPicker && siteId && (
        <MediaPickerModal
          isOpen={showMediaPicker}
          onClose={() => setShowMediaPicker(false)}
          onSelect={handleMediaSelect}
          siteId={parseInt(siteId)}
          title="Select Featured Image"
        />
      )}
    </div>
  )
}
