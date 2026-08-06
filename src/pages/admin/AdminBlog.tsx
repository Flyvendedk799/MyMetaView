import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  EyeIcon,
  MagnifyingGlassIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ClockIcon,
  ArchiveBoxIcon,
  FunnelIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import {
  adminFetchBlogPosts,
  adminDeleteBlogPost,
  adminPublishBlogPost,
  adminUnpublishBlogPost,
  adminFetchBlogCategories,
  type BlogPostListItem,
  type BlogCategory,
  type PaginatedBlogPosts,
} from '../../api/client'

const statusConfig: Record<string, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  draft: { label: 'Draft', color: 'bg-secondary-100 text-secondary-700', icon: DocumentTextIcon },
  published: { label: 'Published', color: 'bg-success-100 text-success-700', icon: CheckCircleIcon },
  scheduled: { label: 'Scheduled', color: 'bg-primary-100 text-primary-700', icon: ClockIcon },
  archived: { label: 'Archived', color: 'bg-warning-100 text-warning-700', icon: ArchiveBoxIcon },
}

export default function AdminBlog() {
  const [posts, setPosts] = useState<BlogPostListItem[]>([])
  const [categories, setCategories] = useState<BlogCategory[]>([])
  const [pagination, setPagination] = useState<Omit<PaginatedBlogPosts, 'items'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<number | undefined>()
  const [searchQuery, setSearchQuery] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  useEffect(() => {
    loadPosts()
  }, [page, statusFilter, categoryFilter])

  useEffect(() => {
    loadCategories()
  }, [])

  async function loadPosts() {
    setLoading(true)
    try {
      const data = await adminFetchBlogPosts({
        page,
        per_page: 20,
        status: statusFilter || undefined,
        category_id: categoryFilter,
        search: searchQuery || undefined,
      })
      setPosts(data.items)
      setPagination({
        total: data.total,
        page: data.page,
        per_page: data.per_page,
        total_pages: data.total_pages,
        has_next: data.has_next,
        has_prev: data.has_prev,
      })
    } catch (error) {
      console.error('Failed to load posts:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadCategories() {
    try {
      const data = await adminFetchBlogCategories()
      setCategories(data)
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }

  async function handleDelete(postId: number) {
    try {
      await adminDeleteBlogPost(postId)
      setPosts(posts.filter(p => p.id !== postId))
      setDeleteConfirm(null)
    } catch (error) {
      console.error('Failed to delete post:', error)
    }
  }

  async function handlePublish(postId: number) {
    try {
      const updated = await adminPublishBlogPost(postId)
      setPosts(posts.map(p => p.id === postId ? { ...p, status: updated.status, published_at: updated.published_at } : p))
    } catch (error) {
      console.error('Failed to publish post:', error)
    }
  }

  async function handleUnpublish(postId: number) {
    try {
      const updated = await adminUnpublishBlogPost(postId)
      setPosts(posts.map(p => p.id === postId ? { ...p, status: updated.status } : p))
    } catch (error) {
      console.error('Failed to unpublish post:', error)
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setPage(1)
    loadPosts()
  }

  function formatDate(dateString?: string) {
    if (!dateString) return '—'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const statusCounts = posts.reduce((acc, post) => {
    acc[post.status] = (acc[post.status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Blog Posts</h1>
          <p className="text-secondary-500 text-sm mt-1">
            Manage your blog content, create new posts, and track performance.
          </p>
        </div>
        <Link
          to="/app/admin/blog/new"
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-accent-500 text-white rounded-xl font-semibold hover:bg-accent-600 transition-colors"
        >
          <PlusIcon className="w-5 h-5" />
          New Post
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-secondary-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-secondary-100 flex items-center justify-center">
              <DocumentTextIcon className="w-5 h-5 text-secondary-600" />
            </div>
            <div>
              <div className="text-2xl font-bold text-secondary-900">{pagination?.total || 0}</div>
              <div className="text-xs text-secondary-500">Total Posts</div>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-secondary-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-success-100 flex items-center justify-center">
              <CheckCircleIcon className="w-5 h-5 text-success-600" />
            </div>
            <div>
              <div className="text-2xl font-bold text-secondary-900">{statusCounts.published || 0}</div>
              <div className="text-xs text-secondary-500">Published</div>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-secondary-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-secondary-100 flex items-center justify-center">
              <PencilSquareIcon className="w-5 h-5 text-secondary-600" />
            </div>
            <div>
              <div className="text-2xl font-bold text-secondary-900">{statusCounts.draft || 0}</div>
              <div className="text-xs text-secondary-500">Drafts</div>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-secondary-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
              <ClockIcon className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <div className="text-2xl font-bold text-secondary-900">{statusCounts.scheduled || 0}</div>
              <div className="text-xs text-secondary-500">Scheduled</div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-secondary-200 p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <form onSubmit={handleSearch} className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search posts..."
                className="w-full pl-10 pr-4 py-2.5 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500"
              />
            </div>
          </form>
          
          <div className="flex gap-3">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2.5 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 text-sm"
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="published">Published</option>
              <option value="scheduled">Scheduled</option>
              <option value="archived">Archived</option>
            </select>
            
            <select
              value={categoryFilter || ''}
              onChange={(e) => {
                setCategoryFilter(e.target.value ? parseInt(e.target.value) : undefined)
                setPage(1)
              }}
              className="px-3 py-2.5 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 text-sm"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
            
            <button
              onClick={() => {
                setStatusFilter('')
                setCategoryFilter(undefined)
                setSearchQuery('')
                setPage(1)
                loadPosts()
              }}
              className="p-2.5 border border-secondary-200 rounded-lg hover:bg-secondary-50 transition-colors"
              title="Reset filters"
            >
              <ArrowPathIcon className="w-5 h-5 text-secondary-500" />
            </button>
          </div>
        </div>
      </div>

      {/* Posts Table */}
      <div className="bg-white rounded-xl border border-secondary-200 overflow-hidden">
        {loading ? (
          <div className="p-8">
            <div className="animate-pulse space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className="w-16 h-12 bg-secondary-200 rounded" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-secondary-200 rounded w-3/4" />
                    <div className="h-3 bg-secondary-200 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : posts.length === 0 ? (
          <div className="p-8 text-center">
            <DocumentTextIcon className="w-12 h-12 text-secondary-300 mx-auto mb-4" />
            <h3 className="font-semibold text-secondary-900 mb-1">No posts found</h3>
            <p className="text-secondary-500 text-sm mb-4">
              {searchQuery || statusFilter || categoryFilter
                ? 'Try adjusting your filters'
                : 'Get started by creating your first blog post'}
            </p>
            <Link
              to="/app/admin/blog/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent-500 text-white rounded-lg font-semibold hover:bg-accent-600 transition-colors text-sm"
            >
              <PlusIcon className="w-4 h-4" />
              Create Post
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-secondary-50 border-b border-secondary-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Post</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Category</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Views</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Date</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-secondary-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-secondary-100">
                {posts.map((post) => {
                  const status = statusConfig[post.status] || statusConfig.draft
                  const StatusIcon = status.icon
                  
                  return (
                    <tr key={post.id} className="hover:bg-secondary-50 transition-colors">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          {post.featured_image ? (
                            <img
                              src={post.featured_image}
                              alt={post.title}
                              className="w-16 h-12 object-cover rounded-lg"
                            />
                          ) : (
                            <div className="w-16 h-12 bg-secondary-100 rounded-lg flex items-center justify-center">
                              <DocumentTextIcon className="w-6 h-6 text-secondary-400" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <div className="font-medium text-secondary-900 truncate max-w-[300px]">
                              {post.title}
                            </div>
                            <div className="text-xs text-secondary-500 truncate max-w-[300px]">
                              /blog/{post.slug}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        {post.category ? (
                          <span
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium text-white"
                            style={{ backgroundColor: post.category.color }}
                          >
                            {post.category.name}
                          </span>
                        ) : (
                          <span className="text-secondary-400 text-sm">—</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${status.color}`}>
                          <StatusIcon className="w-3.5 h-3.5" />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-secondary-600">{post.views_count.toLocaleString()}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="text-sm text-secondary-600">
                          {formatDate(post.published_at || post.created_at)}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-end gap-2">
                          {post.status === 'published' && (
                            <a
                              href={`/blog/${post.slug}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-2 text-secondary-400 hover:text-secondary-600 hover:bg-secondary-100 rounded-lg transition-colors"
                              title="View"
                            >
                              <EyeIcon className="w-4 h-4" />
                            </a>
                          )}
                          <Link
                            to={`/app/admin/blog/${post.id}`}
                            className="p-2 text-secondary-400 hover:text-accent-600 hover:bg-accent-50 rounded-lg transition-colors"
                            title="Edit"
                          >
                            <PencilSquareIcon className="w-4 h-4" />
                          </Link>
                          {post.status === 'draft' && (
                            <button
                              onClick={() => handlePublish(post.id)}
                              className="p-2 text-secondary-400 hover:text-success-600 hover:bg-success-50 rounded-lg transition-colors"
                              title="Publish"
                            >
                              <CheckCircleIcon className="w-4 h-4" />
                            </button>
                          )}
                          {post.status === 'published' && (
                            <button
                              onClick={() => handleUnpublish(post.id)}
                              className="p-2 text-secondary-400 hover:text-warning-600 hover:bg-warning-50 rounded-lg transition-colors"
                              title="Unpublish"
                            >
                              <ArchiveBoxIcon className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => setDeleteConfirm(post.id)}
                            className="p-2 text-secondary-400 hover:text-error-600 hover:bg-error-50 rounded-lg transition-colors"
                            title="Delete"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pagination && pagination.total_pages > 1 && (
          <div className="px-4 py-3 border-t border-secondary-100 flex items-center justify-between">
            <div className="text-sm text-secondary-500">
              Showing {((page - 1) * (pagination.per_page)) + 1} to {Math.min(page * pagination.per_page, pagination.total)} of {pagination.total} posts
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={!pagination.has_prev}
                className="px-3 py-1.5 border border-secondary-200 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-secondary-50 transition-colors"
              >
                Previous
              </button>
              <span className="px-3 py-1.5 text-sm font-medium">
                {page} / {pagination.total_pages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={!pagination.has_next}
                className="px-3 py-1.5 border border-secondary-200 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-secondary-50 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Category Management Link */}
      <div className="bg-white rounded-xl border border-secondary-200 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-secondary-900">Categories</h3>
            <p className="text-sm text-secondary-500 mt-1">
              Manage blog categories to organize your content
            </p>
          </div>
          <Link
            to="/app/admin/blog/categories"
            className="px-4 py-2 border border-secondary-200 rounded-lg text-sm font-medium hover:bg-secondary-50 transition-colors"
          >
            Manage Categories
          </Link>
        </div>
        {categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {categories.map((cat) => (
              <span
                key={cat.id}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium text-white"
                style={{ backgroundColor: cat.color }}
              >
                {cat.name}
                <span className="opacity-70">({cat.post_count || 0})</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="text-lg font-bold text-secondary-900 mb-2">Delete Post?</h3>
            <p className="text-secondary-500 text-sm mb-6">
              This action cannot be undone. The post will be permanently deleted.
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

