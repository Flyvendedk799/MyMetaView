import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import {
  fetchSiteCategories,
  createSiteCategory,
  updateSiteCategory,
  deleteSiteCategory,
  type SiteCategory,
  type SiteCategoryCreate,
  type SiteCategoryUpdate,
} from '../../api/client'

interface CategoryFormData {
  name: string
  slug: string
  description: string
  color: string
}

const DEFAULT_COLORS = [
  '#f97316', '#ef4444', '#ec4899', '#a855f7', '#6366f1',
  '#3b82f6', '#06b6d4', '#14b8a6', '#22c55e', '#84cc16',
]

export default function SiteCategories() {
  const { siteId } = useParams<{ siteId: string }>()
  const [categories, setCategories] = useState<SiteCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [formData, setFormData] = useState<CategoryFormData>({
    name: '',
    slug: '',
    description: '',
    color: DEFAULT_COLORS[0],
  })

  useEffect(() => {
    if (siteId) loadCategories()
  }, [siteId])

  async function loadCategories() {
    if (!siteId) return
    try {
      setLoading(true)
      const data = await fetchSiteCategories(parseInt(siteId))
      setCategories(data)
    } catch (err) {
      console.error('Failed to load categories:', err)
    } finally {
      setLoading(false)
    }
  }

  function openCreateModal() {
    setFormData({
      name: '',
      slug: '',
      description: '',
      color: DEFAULT_COLORS[Math.floor(Math.random() * DEFAULT_COLORS.length)],
    })
    setEditingId(null)
    setShowModal(true)
    setError('')
  }

  function openEditModal(category: SiteCategory) {
    setFormData({
      name: category.name,
      slug: category.slug,
      description: category.description || '',
      color: category.color || DEFAULT_COLORS[0],
    })
    setEditingId(category.id)
    setShowModal(true)
    setError('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!siteId || !formData.name.trim()) {
      setError('Name is required')
      return
    }

    try {
      setSaving(true)
      setError('')

      if (editingId) {
        const updated = await updateSiteCategory(parseInt(siteId), editingId, {
          name: formData.name.trim(),
          slug: formData.slug.trim() || undefined,
          description: formData.description.trim() || undefined,
          color: formData.color,
        } as SiteCategoryUpdate)
        setCategories(categories.map(c => c.id === editingId ? updated : c))
      } else {
        const created = await createSiteCategory(parseInt(siteId), {
          name: formData.name.trim(),
          slug: formData.slug.trim() || undefined,
          description: formData.description.trim() || undefined,
          color: formData.color,
        } as SiteCategoryCreate)
        setCategories([...categories, created])
      }

      setShowModal(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save category')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(categoryId: number) {
    if (!siteId) return
    try {
      await deleteSiteCategory(parseInt(siteId), categoryId)
      setCategories(categories.filter(c => c.id !== categoryId))
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete category:', err)
    }
  }

  function generateSlug(name: string) {
    return name
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/[\s_-]+/g, '-')
      .replace(/^-+|-+$/g, '')
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-secondary">Categories</h1>
          <p className="text-muted">Organize your posts into categories</p>
        </div>
        <Button onClick={openCreateModal}>
          <PlusIcon className="w-5 h-5 mr-2" />
          New Category
        </Button>
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : categories.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-secondary-500">
            <p className="font-medium mb-2">No categories yet</p>
            <p className="text-sm mb-4">Create your first category to organize posts</p>
            <Button onClick={openCreateModal}>Create Category</Button>
          </div>
        ) : (
          <div className="divide-y">
            {categories.map((category) => (
              <div
                key={category.id}
                className="flex items-center justify-between py-4 px-2 hover:bg-secondary-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: category.color || '#6b7280' }}
                  />
                  <div>
                    <h3 className="font-medium text-secondary-900">{category.name}</h3>
                    <p className="text-sm text-secondary-500">/category/{category.slug}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-secondary-500">
                    {(category as any).post_count || 0} posts
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => openEditModal(category)}
                      className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <PencilSquareIcon className="w-4 h-4 text-secondary-600" />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(category.id)}
                      className="p-2 hover:bg-error-50 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <TrashIcon className="w-4 h-4 text-error-600" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-xl font-semibold text-secondary-900">
                {editingId ? 'Edit Category' : 'New Category'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-4 space-y-4">
              {error && (
                <div className="p-3 bg-error-50 border border-error-200 rounded-lg text-error-800 text-sm">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({
                      ...formData,
                      name: e.target.value,
                      slug: formData.slug || generateSlug(e.target.value),
                    })
                  }}
                  placeholder="Category name"
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">
                  Slug
                </label>
                <input
                  type="text"
                  value={formData.slug}
                  onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                  placeholder="category-slug"
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-mono text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Brief description of this category"
                  rows={3}
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-2">
                  Color
                </label>
                <div className="flex items-center gap-3">
                  <div className="flex gap-2 flex-wrap">
                    {DEFAULT_COLORS.map((color) => (
                      <button
                        key={color}
                        type="button"
                        onClick={() => setFormData({ ...formData, color })}
                        className={`w-8 h-8 rounded-full border-2 transition-all ${
                          formData.color === color
                            ? 'border-secondary-900 scale-110'
                            : 'border-transparent hover:scale-105'
                        }`}
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                  <input
                    type="color"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="w-8 h-8 border border-secondary-300 rounded cursor-pointer"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-medium hover:bg-secondary-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="text-lg font-bold text-secondary-900 mb-2">Delete Category?</h3>
            <p className="text-secondary-500 text-sm mb-6">
              Posts in this category will become uncategorized. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 px-4 py-2 border border-secondary-200 rounded-lg font-medium hover:bg-secondary-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="flex-1 px-4 py-2 bg-error-500 text-white rounded-lg font-medium hover:bg-error-600 transition-colors"
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
