import { useState, useEffect } from 'react'
import Seo from '../components/Seo'
import { Link, useSearchParams } from 'react-router-dom'
import {
  MagnifyingGlassIcon,
  CalendarIcon,
  ClockIcon,
  EyeIcon,
  TagIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowUpRightIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import {
  fetchBlogPosts,
  fetchBlogCategories,
  fetchFeaturedBlogPosts,
  type BlogPostListItem,
  type BlogCategory,
  type PaginatedBlogPosts,
} from '../api/client'

export default function Blog() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [posts, setPosts] = useState<BlogPostListItem[]>([])
  const [featuredPosts, setFeaturedPosts] = useState<BlogPostListItem[]>([])
  const [categories, setCategories] = useState<BlogCategory[]>([])
  const [pagination, setPagination] = useState<Omit<PaginatedBlogPosts, 'items'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  
  const currentPage = parseInt(searchParams.get('page') || '1')
  const currentCategory = searchParams.get('category') || ''
  const currentTag = searchParams.get('tag') || ''

  useEffect(() => {
    loadData()
  }, [currentPage, currentCategory, currentTag, searchParams.get('search')])

  useEffect(() => {
    loadCategories()
    loadFeaturedPosts()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const data = await fetchBlogPosts({
        page: currentPage,
        per_page: 9,
        category: currentCategory || undefined,
        tag: currentTag || undefined,
        search: searchParams.get('search') || undefined,
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
      console.error('Failed to load blog posts:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadCategories() {
    try {
      const data = await fetchBlogCategories()
      setCategories(data)
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }

  async function loadFeaturedPosts() {
    try {
      const data = await fetchFeaturedBlogPosts(3)
      setFeaturedPosts(data)
    } catch (error) {
      console.error('Failed to load featured posts:', error)
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    const params = new URLSearchParams(searchParams)
    if (searchQuery) {
      params.set('search', searchQuery)
    } else {
      params.delete('search')
    }
    params.set('page', '1')
    setSearchParams(params)
  }

  function handleCategoryFilter(slug: string) {
    const params = new URLSearchParams(searchParams)
    if (slug) {
      params.set('category', slug)
    } else {
      params.delete('category')
    }
    params.set('page', '1')
    setSearchParams(params)
  }

  function handlePageChange(page: number) {
    const params = new URLSearchParams(searchParams)
    params.set('page', page.toString())
    setSearchParams(params)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function formatDate(dateString?: string) {
    if (!dateString) return ''
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const showFeatured = !currentCategory && !currentTag && !searchParams.get('search') && currentPage === 1

  return (
    <div className="min-h-screen bg-paper">
      <Seo title="Blog" description="Guides and best practices for og:images, metadata SEO, and share-ready launches from the MetaView team." path="/blog" />
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90  border-b border-secondary-100/80 transition-all duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
          <div className="flex items-center justify-between h-16 sm:h-18">
            <Link to="/" className="flex items-center space-x-2 sm:space-x-3 group cursor-pointer">
              <div className="relative">
                <div className="w-9 h-9 sm:w-10 sm:h-10 bg-primary-500 rounded-xl flex items-center justify-center shadow-lg shadow-accent-500/25 group-hover:scale-110 group-hover:shadow-accent-500/40 transition-all duration-300">
                  <span className="text-white font-black text-base sm:text-lg">M</span>
                </div>
              </div>
              <span className="text-lg sm:text-xl font-black text-secondary-900 tracking-tight">MetaView</span>
            </Link>
            <div className="hidden md:flex items-center space-x-8">
              <Link to="/" className="text-secondary-600 hover:text-secondary-900 font-semibold text-sm">Home</Link>
              <Link to="/blog" className="text-accent-600 font-semibold text-sm">Blog</Link>
              <Link to="/#pricing" className="text-secondary-600 hover:text-secondary-900 font-semibold text-sm">Pricing</Link>
              <Link to="/app" className="text-secondary-600 hover:text-secondary-900 font-semibold text-sm">Login</Link>
            </div>
            <Link
              to="/app"
              className="px-5 py-2.5 bg-accent-500 text-white rounded-xl font-bold text-sm transition-all duration-300 hover:scale-105 hover:shadow-lg hover:shadow-accent-500/30"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-28 sm:pt-32 pb-12 px-4 sm:px-6 lg:px-12 bg-ink text-white relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0">
          <div className="absolute top-0 right-0 w-96 h-96 bg-accent-500/10 rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-0 w-96 h-96 bg-warning-500/10 rounded-full blur-3xl" />
          <div className="absolute inset-0 opacity-5" style={{
            backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.3) 1px, transparent 0)',
            backgroundSize: '48px 48px'
          }} />
        </div>
        
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="max-w-3xl">
            <div className="flex items-center justify-between mb-6">
              <div className="inline-flex items-center space-x-2 px-3 py-1.5 bg-accent-500/20 rounded-full border border-accent-500/30 backdrop-blur-sm">
                <SparklesIcon className="w-4 h-4 text-accent-400" />
                <span className="text-xs font-bold text-accent-300">MetaView Blog</span>
              </div>
              <a
                href="/api/v1/blog/feed.xml"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white/10 backdrop-blur-sm border border-white/20 rounded-full text-xs font-medium text-white hover:bg-white/20 transition-colors"
                title="RSS Feed"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6.503 20.752c0 1.794-1.456 3.248-3.251 3.248-1.796 0-3.252-1.454-3.252-3.248 0-1.794 1.456-3.248 3.252-3.248 1.795.001 3.251 1.454 3.251 3.248zm-6.503-12.572v4.811c6.05.062 10.96 4.966 11.022 11.009h4.817c-.062-8.71-7.118-15.758-15.839-15.82zm0-7.18v4.81c9.88.058 17.883 8.094 17.94 17.971h4.817c-.057-12.65-10.28-22.872-22.757-22.781z"/>
                </svg>
                RSS
              </a>
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight mb-6">
              Insights & Resources
            </h1>
            <p className="text-lg sm:text-xl text-secondary-300 mb-8 max-w-2xl">
              Tips, strategies, and best practices for optimizing your URL previews and boosting click-through rates.
            </p>
            
            {/* Search Bar */}
            <form onSubmit={handleSearch} className="flex gap-3 max-w-xl">
              <div className="relative flex-1">
                <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search articles..."
                  className="w-full pl-12 pr-4 py-3.5 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder-secondary-400 focus:outline-none focus:ring-2 focus:ring-accent-500/50 focus:border-accent-500/50 transition-all"
                />
              </div>
              <button
                type="submit"
                className="px-6 py-3.5 bg-accent-500 text-white rounded-xl font-bold hover:shadow-lg hover:shadow-accent-500/30 transition-all hover:scale-105"
              >
                Search
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="py-6 border-b border-secondary-100 bg-white sticky top-16 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
          <div className="flex items-center gap-3 overflow-x-auto pb-2 scrollbar-hide">
            <button
              onClick={() => handleCategoryFilter('')}
              className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap transition-all ${
                !currentCategory
                  ? 'bg-secondary-900 text-white'
                  : 'bg-secondary-100 text-secondary-600 hover:bg-secondary-200'
              }`}
            >
              All Posts
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => handleCategoryFilter(cat.slug)}
                className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap transition-all flex items-center gap-2 ${
                  currentCategory === cat.slug
                    ? 'bg-secondary-900 text-white'
                    : 'bg-secondary-100 text-secondary-600 hover:bg-secondary-200'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: cat.color }}
                />
                {cat.name}
                {cat.post_count !== undefined && (
                  <span className={`text-xs ${currentCategory === cat.slug ? 'text-secondary-300' : 'text-secondary-400'}`}>
                    ({cat.post_count})
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Posts */}
      {showFeatured && featuredPosts.length > 0 && (
        <section className="py-12 px-4 sm:px-6 lg:px-12 bg-white">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <h2 className="text-2xl font-bold text-secondary-900">Featured Articles</h2>
              <span className="text-sm text-accent-600 font-medium">Editor's picks</span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main Featured Post */}
              {featuredPosts[0] && (
                <Link
                  to={`/blog/${featuredPosts[0].slug}`}
                  className="lg:col-span-2 group relative bg-ink rounded-2xl overflow-hidden min-h-[400px] flex flex-col justify-end"
                >
                  {featuredPosts[0].featured_image && (
                    <img
                      src={featuredPosts[0].featured_image}
                      alt={featuredPosts[0].title}
                      className="absolute inset-0 w-full h-full object-cover opacity-60 group-hover:opacity-40 group-hover:scale-105 transition-all duration-500"
                    />
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-secondary-900 via-secondary-900/70 to-transparent" />
                  <div className="relative p-8 z-10">
                    {featuredPosts[0].category && (
                      <span
                        className="inline-block px-3 py-1 rounded-full text-xs font-bold text-white mb-4"
                        style={{ backgroundColor: featuredPosts[0].category.color }}
                      >
                        {featuredPosts[0].category.name}
                      </span>
                    )}
                    <h3 className="text-2xl sm:text-3xl font-bold text-white mb-3 group-hover:text-accent-300 transition-colors">
                      {featuredPosts[0].title}
                    </h3>
                    <p className="text-secondary-300 mb-4 line-clamp-2">{featuredPosts[0].excerpt}</p>
                    <div className="flex items-center gap-4 text-sm text-secondary-400">
                      <span className="flex items-center gap-1.5">
                        <CalendarIcon className="w-4 h-4" />
                        {formatDate(featuredPosts[0].published_at)}
                      </span>
                      {featuredPosts[0].read_time_minutes && (
                        <span className="flex items-center gap-1.5">
                          <ClockIcon className="w-4 h-4" />
                          {featuredPosts[0].read_time_minutes} min read
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              )}
              
              {/* Secondary Featured Posts */}
              <div className="flex flex-col gap-6">
                {featuredPosts.slice(1, 3).map((post) => (
                  <Link
                    key={post.id}
                    to={`/blog/${post.slug}`}
                    className="group relative bg-white rounded-xl border border-secondary-200 overflow-hidden hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
                  >
                    {post.featured_image && (
                      <div className="h-40 overflow-hidden">
                        <img
                          src={post.featured_image}
                          alt={post.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                      </div>
                    )}
                    <div className="p-5">
                      {post.category && (
                        <span
                          className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold text-white mb-3"
                          style={{ backgroundColor: post.category.color }}
                        >
                          {post.category.name}
                        </span>
                      )}
                      <h4 className="font-bold text-secondary-900 mb-2 group-hover:text-accent-600 transition-colors line-clamp-2">
                        {post.title}
                      </h4>
                      <div className="flex items-center gap-3 text-xs text-secondary-500">
                        <span>{formatDate(post.published_at)}</span>
                        {post.read_time_minutes && (
                          <span>{post.read_time_minutes} min</span>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Main Content */}
      <section className="py-12 px-4 sm:px-6 lg:px-12">
        <div className="max-w-7xl mx-auto">
          {/* Active Filters */}
          {(currentCategory || currentTag || searchParams.get('search')) && (
            <div className="flex items-center gap-3 mb-8 flex-wrap">
              <span className="text-sm text-secondary-500">Filtering by:</span>
              {currentCategory && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-accent-100 text-accent-700 rounded-full text-sm font-medium">
                  Category: {currentCategory}
                  <button
                    onClick={() => handleCategoryFilter('')}
                    className="hover:text-accent-900"
                  >
                    Ã—
                  </button>
                </span>
              )}
              {searchParams.get('search') && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm font-medium">
                  Search: {searchParams.get('search')}
                  <button
                    onClick={() => {
                      const params = new URLSearchParams(searchParams)
                      params.delete('search')
                      setSearchParams(params)
                      setSearchQuery('')
                    }}
                    className="hover:text-primary-900"
                  >
                    Ã—
                  </button>
                </span>
              )}
            </div>
          )}

          {/* Posts Grid */}
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="bg-secondary-200 h-48 rounded-xl mb-4" />
                  <div className="bg-secondary-200 h-4 rounded w-1/4 mb-3" />
                  <div className="bg-secondary-200 h-6 rounded w-3/4 mb-2" />
                  <div className="bg-secondary-200 h-4 rounded w-full" />
                </div>
              ))}
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-16">
              <div className="w-16 h-16 bg-secondary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <MagnifyingGlassIcon className="w-8 h-8 text-secondary-400" />
              </div>
              <h3 className="text-xl font-bold text-secondary-900 mb-2">No posts found</h3>
              <p className="text-secondary-500 mb-6">Try adjusting your search or filter criteria.</p>
              <button
                onClick={() => {
                  setSearchParams({})
                  setSearchQuery('')
                }}
                className="text-accent-600 font-semibold hover:text-accent-700"
              >
                Clear all filters
              </button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {posts.map((post, index) => (
                  <Link
                    key={post.id}
                    to={`/blog/${post.slug}`}
                    className="group bg-white rounded-xl border border-secondary-200 overflow-hidden hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    {post.featured_image ? (
                      <div className="h-48 overflow-hidden relative">
                        <img
                          src={post.featured_image}
                          alt={post.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                        {post.is_pinned && (
                          <span className="absolute top-3 left-3 px-2 py-0.5 bg-warning-500 text-white text-xs font-bold rounded-full">
                            Pinned
                          </span>
                        )}
                      </div>
                    ) : (
                      <div className="h-48 bg-brand-100 flex items-center justify-center relative">
                        <SparklesIcon className="w-12 h-12 text-accent-300" />
                        {post.is_pinned && (
                          <span className="absolute top-3 left-3 px-2 py-0.5 bg-warning-500 text-white text-xs font-bold rounded-full">
                            Pinned
                          </span>
                        )}
                      </div>
                    )}
                    <div className="p-6">
                      <div className="flex items-center gap-3 mb-3">
                        {post.category && (
                          <span
                            className="px-2.5 py-0.5 rounded-full text-xs font-semibold text-white"
                            style={{ backgroundColor: post.category.color }}
                          >
                            {post.category.name}
                          </span>
                        )}
                        {post.read_time_minutes && (
                          <span className="flex items-center gap-1 text-xs text-secondary-500">
                            <ClockIcon className="w-3.5 h-3.5" />
                            {post.read_time_minutes} min
                          </span>
                        )}
                      </div>
                      <h3 className="text-lg font-bold text-secondary-900 mb-2 group-hover:text-accent-600 transition-colors line-clamp-2">
                        {post.title}
                      </h3>
                      {post.excerpt && (
                        <p className="text-secondary-500 text-sm mb-4 line-clamp-2">{post.excerpt}</p>
                      )}
                      <div className="flex items-center justify-between pt-4 border-t border-secondary-100">
                        <div className="flex items-center gap-2">
                          {post.author_avatar ? (
                            <img
                              src={post.author_avatar}
                              alt={post.author_name || 'Author'}
                              className="w-6 h-6 rounded-full object-cover"
                            />
                          ) : (
                            <div className="w-6 h-6 rounded-full bg-brand-100" />
                          )}
                          <span className="text-xs text-secondary-600 font-medium">
                            {post.author_name || 'MetaView Team'}
                          </span>
                        </div>
                        <span className="text-xs text-secondary-400">
                          {formatDate(post.published_at)}
                        </span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>

              {/* Pagination */}
              {pagination && pagination.total_pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-12">
                  <button
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={!pagination.has_prev}
                    className="p-2 rounded-lg border border-secondary-200 text-secondary-600 hover:bg-secondary-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeftIcon className="w-5 h-5" />
                  </button>
                  
                  {[...Array(pagination.total_pages)].map((_, i) => {
                    const page = i + 1
                    // Show first, last, current, and adjacent pages
                    if (
                      page === 1 ||
                      page === pagination.total_pages ||
                      (page >= currentPage - 1 && page <= currentPage + 1)
                    ) {
                      return (
                        <button
                          key={page}
                          onClick={() => handlePageChange(page)}
                          className={`w-10 h-10 rounded-lg font-semibold transition-all ${
                            page === currentPage
                              ? 'bg-accent-500 text-white'
                              : 'border border-secondary-200 text-secondary-600 hover:bg-secondary-50'
                          }`}
                        >
                          {page}
                        </button>
                      )
                    }
                    // Show ellipsis
                    if (page === currentPage - 2 || page === currentPage + 2) {
                      return (
                        <span key={page} className="px-2 text-secondary-400">
                          ...
                        </span>
                      )
                    }
                    return null
                  })}
                  
                  <button
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={!pagination.has_next}
                    className="p-2 rounded-lg border border-secondary-200 text-secondary-600 hover:bg-secondary-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronRightIcon className="w-5 h-5" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* Newsletter CTA */}
      <section className="py-16 px-4 sm:px-6 lg:px-12 bg-primary-500">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Stay Updated</h2>
          <p className="text-accent-100 mb-8">
            Get the latest insights on URL previews, SEO optimization, and growth strategies delivered to your inbox.
          </p>
          <form className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
            <input
              type="email"
              placeholder="Enter your email"
              className="flex-1 px-4 py-3 rounded-xl bg-white/20 backdrop-blur-sm border border-white/30 text-white placeholder-paper/60 focus:outline-none focus:ring-2 focus:ring-white/50"
            />
            <button
              type="submit"
              className="px-6 py-3 bg-white text-accent-600 rounded-xl font-bold hover:bg-accent-50 transition-colors"
            >
              Subscribe
            </button>
          </form>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-secondary-900 text-white py-12 px-4 sm:px-6 lg:px-12">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <Link to="/" className="flex items-center space-x-2.5">
              <div className="w-9 h-9 bg-primary-500 rounded-xl flex items-center justify-center">
                <span className="text-white font-black text-sm">M</span>
              </div>
              <span className="text-lg font-black">MetaView</span>
            </Link>
            <div className="flex items-center gap-6 text-sm text-secondary-400">
              <Link to="/" className="hover:text-white transition-colors">Home</Link>
              <Link to="/blog" className="hover:text-white transition-colors">Blog</Link>
              <Link to="/#pricing" className="hover:text-white transition-colors">Pricing</Link>
              <Link to="/app" className="hover:text-white transition-colors">Dashboard</Link>
            </div>
            <span className="text-sm text-secondary-500">Â© 2024 MetaView. All rights reserved.</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

