import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeftIcon,
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  SwatchIcon,
} from '@heroicons/react/24/outline'
import {
  adminFetchBlogCategories,
  adminCreateBlogCategory,
  adminUpdateBlogCategory,
  adminDeleteBlogCategory,
  type BlogCategory,
  type BlogCategoryCreate,
} from '../../api/client'

const colorPresets = [
  '#f97316', // orange
  '#ef4444', // red
  '#8b5cf6', // violet
  '#3b82f6', // blue
  '#06b6d4', // cyan
  '#10b981', // emerald
  '#84cc16', // lime
  '#f59e0b', // amber
  '#ec4899', // pink
  '#6366f1', // indigo
]

export default function AdminBlogCategories() {
  const [categories, setCategories] = useState<BlogCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  
  const [formData, setFormData] = useState<BlogCategoryCreate>({
    name: '',
    slug: '',
    description: '',
    color: '#f97316',
    icon: '',
    is_active: true,
    sort_order: 0,
    meta_title: '',
    meta_description: '',
  })

  useEffect(() => {
    loadCategories()
  }, [])

  async function loadCategories() {
    setLoading(true)
    try {
      const data = await adminFetchBlogCategories()
      setCategories(data)
    } catch (error) {
      console.error('Failed to load categories:', error)
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setFormData({
      name: '',
      slug: '',
      description: '',
      color: '#f97316',
      icon: '',
      is_active: true,
      sort_order: 0,
      meta_title: '',
      meta_description: '',
    })
    setEditingId(null)
    setIsCreating(false)
  }

  function startEdit(category: BlogCategory) {
    setFormData({
      name: category.name,
      slug: category.slug,
      description: category.description || '',
      color: category.color,
      icon: category.icon || '',
      is_active: category.is_active,
      sort_order: category.sort_order,
      meta_title: category.meta_title || '',
      meta_description: category.meta_description || '',
    })
    setEditingId(category.id)
    setIsCreating(false)
  }

  async function handleSave() {
    try {
      if (editingId) {
        const updated = await adminUpdateBlogCategory(editingId, formData)
        setCategories(categories.map(c => c.id === editingId ? { ...c, ...updated } : c))
      } else {
        const created = await adminCreateBlogCategory(formData)
        setCategories([...categories, created])
      }
      resetForm()
    } catch (error) {
      console.error('Failed to save category:', error)
      alert('Failed to save category. Please try again.')
    }
  }

  async function handleDelete(id: number) {
    try {
      await adminDeleteBlogCategory(id)
      setCategories(categories.filter(c => c.id !== id))
      setDeleteConfirm(null)
    } catch (error) {
      console.error('Failed to delete category:', error)
      alert('Failed to delete category. Please try again.')
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/app/admin/blog"
          className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
        >
          <ArrowLeftIcon className="w-5 h-5 text-secondary-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Blog Categories</h1>
          <p className="text-secondary-500 text-sm mt-1">
            Organize your blog posts with categories
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Categories List */}
        <div className="bg-white rounded-xl border border-secondary-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-secondary-100 flex items-center justify-between">
            <h2 className="font-semibold text-secondary-900">All Categories</h2>
            <button
              onClick={() => {
                resetForm()
                setIsCreating(true)
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent-500 text-white rounded-lg text-sm font-medium hover:bg-accent-600 transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              Add
            </button>
          </div>
          
          {loading ? (
            <div className="p-6 space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="animate-pulse flex items-center gap-3">
                  <div className="w-4 h-4 bg-secondary-200 rounded-full" />
                  <div className="flex-1 h-4 bg-secondary-200 rounded" />
                </div>
              ))}
            </div>
          ) : categories.length === 0 ? (
            <div className="p-8 text-center">
              <SwatchIcon className="w-12 h-12 text-secondary-300 mx-auto mb-4" />
              <p className="text-secondary-500">No categories yet</p>
            </div>
          ) : (
            <div className="divide-y divide-secondary-100">
              {categories.map((category) => (
                <div
                  key={category.id}
                  className={`px-6 py-4 flex items-center justify-between hover:bg-secondary-50 transition-colors ${
                    editingId === category.id ? 'bg-accent-50' : ''
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: category.color }}
                    />
                    <div>
                      <div className="font-medium text-secondary-900 flex items-center gap-2">
                        {category.name}
                        {!category.is_active && (
                          <span className="text-xs text-secondary-400">(hidden)</span>
                        )}
                      </div>
                      <div className="text-xs text-secondary-500">
                        {category.post_count || 0} posts • /{category.slug}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => startEdit(category)}
                      className="p-1.5 text-secondary-400 hover:text-accent-600 hover:bg-accent-50 rounded-lg transition-colors"
                    >
                      <PencilSquareIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(category.id)}
                      className="p-1.5 text-secondary-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-colors"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Edit/Create Form */}
        {(isCreating || editingId) && (
          <div className="bg-white rounded-xl border border-secondary-200 p-6">
            <h2 className="font-semibold text-secondary-900 mb-4">
              {editingId ? 'Edit Category' : 'New Category'}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-secondary-600 mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Marketing Tips"
                  className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500"
                />
              </div>
              
              <div>
                <label className="block text-sm text-secondary-600 mb-1">Slug</label>
                <input
                  type="text"
                  value={formData.slug}
                  onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                  placeholder="marketing-tips (auto-generated if empty)"
                  className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500"
                />
              </div>
              
              <div>
                <label className="block text-sm text-secondary-600 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Brief description of this category..."
                  rows={2}
                  className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 resize-none"
                />
              </div>
              
              <div>
                <label className="block text-sm text-secondary-600 mb-2">Color</label>
                <div className="flex items-center gap-2 flex-wrap">
                  {colorPresets.map((color) => (
                    <button
                      key={color}
                      onClick={() => setFormData({ ...formData, color })}
                      className={`w-8 h-8 rounded-full transition-transform hover:scale-110 ${
                        formData.color === color ? 'ring-2 ring-offset-2 ring-secondary-400' : ''
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                  <input
                    type="color"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="w-8 h-8 rounded-full cursor-pointer"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm text-secondary-600 mb-1">Sort Order</label>
                <input
                  type="number"
                  value={formData.sort_order}
                  onChange={(e) => setFormData({ ...formData, sort_order: parseInt(e.target.value) || 0 })}
                  className="w-24 px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500"
                />
                <p className="text-xs text-secondary-400 mt-1">Lower numbers appear first</p>
              </div>
              
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="w-4 h-4 text-accent-500 border-secondary-300 rounded focus:ring-accent-500"
                />
                <span className="text-sm text-secondary-700">Active (visible on blog)</span>
              </label>
              
              <div className="border-t border-secondary-100 pt-4 mt-4">
                <h3 className="text-sm font-medium text-secondary-700 mb-3">SEO (Optional)</h3>
                <div className="space-y-3">
                  <input
                    type="text"
                    value={formData.meta_title}
                    onChange={(e) => setFormData({ ...formData, meta_title: e.target.value })}
                    placeholder="SEO title"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 text-sm"
                  />
                  <input
                    type="text"
                    value={formData.meta_description}
                    onChange={(e) => setFormData({ ...formData, meta_description: e.target.value })}
                    placeholder="SEO description"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 text-sm"
                  />
                </div>
              </div>
              
              <div className="flex gap-3 pt-2">
                <button
                  onClick={resetForm}
                  className="flex-1 px-4 py-2 border border-secondary-200 rounded-lg font-medium hover:bg-secondary-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!formData.name}
                  className="flex-1 px-4 py-2 bg-accent-500 text-white rounded-lg font-medium hover:bg-accent-600 transition-colors disabled:opacity-50"
                >
                  {editingId ? 'Update' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

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

