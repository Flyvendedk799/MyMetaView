import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  DocumentTextIcon,
  FolderIcon,
  DocumentIcon,
  EyeIcon,
  PlusIcon,
  PencilSquareIcon,
  Cog6ToothIcon,
  PhotoIcon,
  Bars3Icon,
  PaintBrushIcon,
  GlobeAltIcon,
  ClockIcon,
  ArrowUpRightIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import Card, { CardHeader, CardTitle } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/ui/PageHeader'
import { StatusBadge } from '../../components/ui/Badge'
import { SkeletonStats, SkeletonList } from '../../components/ui/Skeleton'
import {
  fetchSiteById,
  fetchSiteStats,
  fetchSitePosts,
  type PublishedSite,
  type SiteStats,
  type SitePostListItem,
} from '../../api/client'

export default function SiteDashboard() {
  const { siteId } = useParams<{ siteId: string }>()
  const navigate = useNavigate()
  const [site, setSite] = useState<PublishedSite | null>(null)
  const [stats, setStats] = useState<SiteStats | null>(null)
  const [recentPosts, setRecentPosts] = useState<SitePostListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (siteId) {
      loadData()
    }
  }, [siteId])

  async function loadData() {
    if (!siteId) return
    try {
      setLoading(true)
      const [siteData, statsData, postsData] = await Promise.all([
        fetchSiteById(parseInt(siteId)),
        fetchSiteStats(parseInt(siteId)).catch(() => null),
        fetchSitePosts(parseInt(siteId), { per_page: 5 }).catch(() => ({ items: [] })),
      ])
      setSite(siteData)
      setStats(statsData)
      setRecentPosts(postsData.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load site')
    } finally {
      setLoading(false)
    }
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-24 skeleton rounded-xl" />
        <SkeletonStats count={4} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <SkeletonList count={4} className="card" />
          </div>
          <div className="space-y-6">
            <div className="h-48 skeleton rounded-xl" />
            <div className="h-48 skeleton rounded-xl" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !site) {
    return (
      <Card className="text-center py-12">
        <p className="text-error-600 mb-4">{error || 'Site not found'}</p>
        <Button variant="secondary" onClick={() => navigate('/app/sites')}>
          Back to Sites
        </Button>
      </Card>
    )
  }

  const statCards = [
    {
      name: 'Total Posts',
      value: stats?.total_posts || 0,
      icon: DocumentTextIcon,
      color: 'text-primary-500',
      bgColor: 'bg-primary-50',
      action: () => navigate(`/app/sites/${siteId}/posts`),
    },
    {
      name: 'Published',
      value: stats?.published_posts || 0,
      icon: DocumentIcon,
      color: 'text-success-500',
      bgColor: 'bg-success-50',
      action: () => navigate(`/app/sites/${siteId}/posts?status=published`),
    },
    {
      name: 'Categories',
      value: stats?.categories || 0,
      icon: FolderIcon,
      color: 'text-accent-500',
      bgColor: 'bg-accent-50',
      action: () => navigate(`/app/sites/${siteId}/categories`),
    },
    {
      name: 'Total Views',
      value: stats?.total_views || 0,
      icon: EyeIcon,
      color: 'text-warning-500',
      bgColor: 'bg-warning-50',
    },
  ]

  const quickActions = [
    { 
      name: 'New Post', 
      description: 'Create a new blog post',
      icon: PlusIcon, 
      color: 'text-primary-500 bg-primary-50',
      path: 'posts/new' 
    },
    { 
      name: 'New Page', 
      description: 'Add a static page',
      icon: DocumentIcon, 
      color: 'text-success-500 bg-success-50',
      path: 'pages/new' 
    },
    { 
      name: 'Upload Media', 
      description: 'Add images to your library',
      icon: PhotoIcon, 
      color: 'text-accent-500 bg-accent-50',
      path: 'media' 
    },
  ]

  const quickLinks = [
    { name: 'Posts', icon: DocumentTextIcon, path: 'posts', color: 'text-primary-500' },
    { name: 'Pages', icon: DocumentIcon, path: 'pages', color: 'text-success-500' },
    { name: 'Categories', icon: FolderIcon, path: 'categories', color: 'text-accent-500' },
    { name: 'Media', icon: PhotoIcon, path: 'media', color: 'text-warning-500' },
    { name: 'Menus', icon: Bars3Icon, path: 'menus', color: 'text-error-500' },
    { name: 'Branding', icon: PaintBrushIcon, path: 'branding', color: 'text-secondary-500' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl bg-primary-500 p-6 md:p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -mr-32 -mt-32 blur-3xl" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-accent-400/20 rounded-full -ml-24 -mb-24 blur-2xl" />
        
        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl md:text-3xl font-bold">{site.name}</h1>
              <StatusBadge status={site.status as any} />
            </div>
            <div className="flex items-center gap-4 text-white/80 text-sm">
              <span className="flex items-center gap-1.5">
                <GlobeAltIcon className="w-4 h-4" />
                {site.domain?.name || 'No domain connected'}
              </span>
              <span className="flex items-center gap-1.5">
                <ClockIcon className="w-4 h-4" />
                Updated {formatDate(site.updated_at)}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {site.status === 'published' && site.domain?.name && (
              <a
                href={`https://${site.domain.name}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-white/20 hover:bg-white/30 rounded-xl font-medium transition-colors backdrop-blur-sm"
              >
                <EyeIcon className="w-4 h-4" />
                View Site
                <ArrowUpRightIcon className="w-3 h-3" />
              </a>
            )}
            <Button 
              onClick={() => navigate(`/app/sites/${siteId}/posts/new`)}
              className="bg-white text-primary-600 hover:bg-white/90"
            >
              <PlusIcon className="w-5 h-5" />
              New Post
            </Button>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-stagger">
        {statCards.map((stat, index) => {
          const Icon = stat.icon
          return (
            <Card
              key={stat.name}
              variant="hover"
              className={`relative overflow-hidden ${stat.action ? 'cursor-pointer' : ''}`}
              onClick={stat.action}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="absolute top-0 right-0 w-24 h-24 bg-brand-50 rounded-full -mr-8 -mt-8" />
              
              <div className="flex items-start justify-between relative">
                <div>
                  <p className="text-sm font-medium text-secondary-500 mb-1">{stat.name}</p>
                  <p className="text-3xl font-bold text-secondary-900 tabular-nums">
                    {typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}
                  </p>
                </div>
                <div className={`p-3 rounded-xl ${stat.bgColor}`}>
                  <Icon className={`w-6 h-6 ${stat.color}`} />
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Posts */}
        <Card className="lg:col-span-2">
          <CardHeader 
            action={
              <Link
                to={`/app/sites/${siteId}/posts`}
                className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
              >
                View all →
              </Link>
            }
          >
            <CardTitle subtitle={`${recentPosts.length} recent posts`}>
              Recent Posts
            </CardTitle>
          </CardHeader>
          
          {recentPosts.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-2xl bg-secondary-100 flex items-center justify-center mx-auto mb-4">
                <DocumentTextIcon className="w-8 h-8 text-secondary-400" />
              </div>
              <p className="font-medium text-secondary-700 mb-2">No posts yet</p>
              <p className="text-sm text-secondary-500 mb-4">Create your first post to get started</p>
              <Button
                variant="secondary"
                onClick={() => navigate(`/app/sites/${siteId}/posts/new`)}
              >
                Create Your First Post
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-secondary-100">
              {recentPosts.map((post, index) => (
                <div
                  key={post.id}
                  className="py-4 first:pt-0 last:pb-0 flex items-center justify-between hover:bg-secondary-50 -mx-6 px-6 transition-colors group"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="flex items-center gap-4 min-w-0">
                    {post.featured_image ? (
                      <img
                        src={post.featured_image}
                        alt=""
                        className="w-14 h-14 object-cover rounded-xl flex-shrink-0"
                      />
                    ) : (
                      <div className="w-14 h-14 bg-secondary-100 rounded-xl flex items-center justify-center flex-shrink-0">
                        <DocumentTextIcon className="w-6 h-6 text-secondary-400" />
                      </div>
                    )}
                    <div className="min-w-0">
                      <h4 className="font-semibold text-secondary-900 truncate group-hover:text-primary-600 transition-colors">
                        {post.title}
                      </h4>
                      <div className="flex items-center gap-3 mt-1">
                        <StatusBadge status={post.status as any} size="sm" />
                        <span className="text-xs text-secondary-500 flex items-center gap-1">
                          <ClockIcon className="w-3 h-3" />
                          {formatDate(post.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => navigate(`/app/sites/${siteId}/posts/${post.id}`)}
                    className="p-2 text-secondary-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <PencilSquareIcon className="w-5 h-5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <Card>
            <CardTitle className="mb-4">Quick Actions</CardTitle>
            <div className="space-y-2">
              {quickActions.map((action) => {
                const Icon = action.icon
                return (
                  <button
                    key={action.name}
                    onClick={() => navigate(`/app/sites/${siteId}/${action.path}`)}
                    className="w-full text-left px-4 py-3 rounded-xl border border-secondary-100 hover:border-primary-200 hover:bg-primary-50/50 transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${action.color}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <p className="font-medium text-secondary-900 group-hover:text-primary-600 transition-colors">
                          {action.name}
                        </p>
                        <p className="text-xs text-secondary-500">{action.description}</p>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </Card>

          {/* Quick Links */}
          <Card>
            <CardTitle className="mb-4">Quick Links</CardTitle>
            <div className="grid grid-cols-3 gap-2">
              {quickLinks.map((link) => {
                const Icon = link.icon
                return (
                  <button
                    key={link.name}
                    onClick={() => navigate(`/app/sites/${siteId}/${link.path}`)}
                    className="flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-secondary-50 transition-colors group"
                  >
                    <Icon className={`w-5 h-5 ${link.color} group-hover:scale-110 transition-transform`} />
                    <span className="text-xs font-medium text-secondary-600">{link.name}</span>
                  </button>
                )
              })}
            </div>
          </Card>

          {/* Site Info */}
          <Card>
            <CardTitle className="mb-4">Site Info</CardTitle>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between items-center py-2 border-b border-secondary-100">
                <span className="text-secondary-500">Template</span>
                <span className="font-medium text-secondary-900 flex items-center gap-1.5">
                  <SparklesIcon className="w-4 h-4 text-accent-500" />
                  {site.template_id || 'Modern Blog'}
                </span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-secondary-100">
                <span className="text-secondary-500">Created</span>
                <span className="font-medium text-secondary-900">
                  {new Date(site.created_at).toLocaleDateString()}
                </span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-secondary-500">Last Updated</span>
                <span className="font-medium text-secondary-900">
                  {new Date(site.updated_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
