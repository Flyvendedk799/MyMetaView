import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  CheckIcon,
  CloudArrowUpIcon,
  DocumentTextIcon,
  EyeIcon,
  PhotoIcon,
  SparklesIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  GlobeAltIcon,
  MagnifyingGlassIcon,
  HashtagIcon,
  LinkIcon,
  UserIcon,
  CalendarIcon,
  PencilIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline'
import {
  adminFetchBlogPost,
  adminCreateBlogPost,
  adminUpdateBlogPost,
  adminFetchBlogCategories,
  adminPublishBlogPost,
  type BlogPost,
  type BlogPostCreate,
  type BlogCategory,
} from '../../api/client'

// Generate URL-friendly slug
function generateSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .substring(0, 250)
}

// Calculate reading time from content
function calculateReadTime(content: string): number {
  const words = content.trim().split(/\s+/).length
  return Math.max(1, Math.round(words / 225))
}

// Generate excerpt from content
function generateExcerpt(content: string, maxLength: number = 160): string {
  const cleanContent = content
    .replace(/[#*_\[\]()]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
  
  if (cleanContent.length <= maxLength) return cleanContent
  return cleanContent.substring(0, maxLength - 3).replace(/\s+\S*$/, '') + '...'
}

// Convert HTML to Markdown using DOM parsing (for paste handling)
function htmlToMarkdown(html: string): string {
  const temp = document.createElement('div')
  temp.innerHTML = html
  
  // Remove unwanted elements
  temp.querySelectorAll('script, style, meta, link').forEach(el => el.remove())
  
  function getTextContent(el: Element): string {
    return (el.textContent || '').replace(/\s+/g, ' ').trim()
  }
  
  function processElement(el: Element): string {
    const tag = el.tagName.toLowerCase()
    
    // Handle specific tags
    switch (tag) {
      case 'h1':
      case 'h2':
        return `\n\n## ${getTextContent(el)}\n\n`
      case 'h3':
      case 'h4':
      case 'h5':
      case 'h6':
        return `\n\n### ${getTextContent(el)}\n\n`
      case 'p':
        return `\n\n${processChildren(el)}\n\n`
      case 'br':
        return '\n'
      case 'strong':
      case 'b':
        return `**${processChildren(el)}**`
      case 'em':
      case 'i':
        return `*${processChildren(el)}*`
      case 'a': {
        const href = el.getAttribute('href') || ''
        return `[${getTextContent(el)}](${href})`
      }
      case 'ul': {
        const items = Array.from(el.children)
          .filter(c => c.tagName.toLowerCase() === 'li')
          .map(li => `- ${getTextContent(li)}`)
        return `\n\n${items.join('\n')}\n\n`
      }
      case 'ol': {
        const items = Array.from(el.children)
          .filter(c => c.tagName.toLowerCase() === 'li')
          .map((li, i) => `${i + 1}. ${getTextContent(li)}`)
        return `\n\n${items.join('\n')}\n\n`
      }
      case 'li':
        return getTextContent(el)
      case 'blockquote':
        return `\n\n> ${getTextContent(el)}\n\n`
      case 'pre':
        return `\n\n\`\`\`\n${el.textContent || ''}\n\`\`\`\n\n`
      case 'code':
        return `\`${el.textContent || ''}\``
      case 'div':
      case 'section':
      case 'article':
        return `\n${processChildren(el)}\n`
      default:
        return processChildren(el)
    }
  }
  
  function processChildren(el: Element): string {
    let result = ''
    el.childNodes.forEach(node => {
      if (node.nodeType === Node.TEXT_NODE) {
        result += (node.textContent || '').replace(/\s+/g, ' ')
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        result += processElement(node as Element)
      }
    })
    return result
  }
  
  let md = processChildren(temp)
  
  // Clean up
  md = md.replace(/\*\*\s*\*\*/g, '')  // Empty bold
  md = md.replace(/\*\s*\*/g, '')      // Empty italic
  md = md.replace(/\n{3,}/g, '\n\n')   // Max 2 newlines
  md = md.replace(/^[ \t]+|[ \t]+$/gm, '') // Trim each line
  md = md.trim()
  
  return md
}

export default function AdminBlogEditor() {
  const { postId } = useParams<{ postId: string }>()
  const navigate = useNavigate()
  const isEditing = postId && postId !== 'new'
  
  const [loading, setLoading] = useState(isEditing)
  const [saving, setSaving] = useState(false)
  const [categories, setCategories] = useState<BlogCategory[]>([])
  const [activeTab, setActiveTab] = useState<'write' | 'preview'>('write')
  const [expandedSections, setExpandedSections] = useState({
    seo: true,
    social: false,
    advanced: false,
  })
  
  // Form state
  const [formData, setFormData] = useState<BlogPostCreate>({
    title: '',
    slug: '',
    excerpt: '',
    content: '',
    featured_image: '',
    featured_image_alt: '',
    og_image: '',
    author_name: '',
    author_bio: '',
    author_avatar: '',
    category_id: undefined,
    tags: '',
    status: 'draft',
    is_featured: false,
    is_pinned: false,
    meta_title: '',
    meta_description: '',
    meta_keywords: '',
    canonical_url: '',
    no_index: false,
    schema_type: 'Article',
    twitter_title: '',
    twitter_description: '',
    twitter_image: '',
  })
  
  const [autoSlug, setAutoSlug] = useState(true)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const [imageCheckStatus, setImageCheckStatus] = useState<{
    checking: boolean
    accessible: boolean | null
    error: string | null
  }>({ checking: false, accessible: null, error: null })

  useEffect(() => {
    loadCategories()
    if (isEditing) {
      loadPost(parseInt(postId))
    }
  }, [postId])

  // Auto-generate slug from title
  useEffect(() => {
    if (autoSlug && formData.title && !isEditing) {
      setFormData(prev => ({ ...prev, slug: generateSlug(prev.title) }))
    }
  }, [formData.title, autoSlug, isEditing])

  async function loadPost(id: number) {
    setLoading(true)
    try {
      const post = await adminFetchBlogPost(id)
      setFormData({
        title: post.title,
        slug: post.slug,
        excerpt: post.excerpt || '',
        content: post.content,
        featured_image: post.featured_image || '',
        featured_image_alt: post.featured_image_alt || '',
        og_image: post.og_image || '',
        author_name: post.author_name || '',
        author_bio: post.author_bio || '',
        author_avatar: post.author_avatar || '',
        category_id: post.category_id || undefined,
        tags: post.tags || '',
        status: post.status as any,
        is_featured: post.is_featured,
        is_pinned: post.is_pinned,
        meta_title: post.meta_title || '',
        meta_description: post.meta_description || '',
        meta_keywords: post.meta_keywords || '',
        canonical_url: post.canonical_url || '',
        no_index: post.no_index,
        schema_type: post.schema_type,
        twitter_title: post.twitter_title || '',
        twitter_description: post.twitter_description || '',
        twitter_image: post.twitter_image || '',
      })
      setAutoSlug(false)
    } catch (error) {
      console.error('Failed to load post:', error)
      navigate('/app/admin/blog')
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

  async function handleSave(publish: boolean = false) {
    setSaving(true)
    try {
      // Validate required fields
      if (!formData.title || !formData.content) {
        alert('Title and content are required fields.')
        setSaving(false)
        return
      }

      // Ensure status is valid
      const validStatuses = ['draft', 'published', 'scheduled', 'archived']
      const status = publish ? 'published' : (formData.status || 'draft')
      if (!validStatuses.includes(status)) {
        alert(`Invalid status. Must be one of: ${validStatuses.join(', ')}`)
        setSaving(false)
        return
      }

      // Validate field length limits
      const validationErrors: string[] = []
      if (formData.title && formData.title.length > 200) {
        validationErrors.push('Title must be at most 200 characters')
      }
      if (formData.slug && formData.slug.length > 250) {
        validationErrors.push('Slug must be at most 250 characters')
      }
      if (formData.meta_title && formData.meta_title.length > 70) {
        validationErrors.push('Meta title must be at most 70 characters')
      }
      if (formData.meta_description && formData.meta_description.length > 160) {
        validationErrors.push('Meta description must be at most 160 characters')
      }
      if (formData.meta_keywords && formData.meta_keywords.length > 300) {
        validationErrors.push('Meta keywords must be at most 300 characters')
      }
      if (formData.featured_image && formData.featured_image.length > 500) {
        validationErrors.push('Featured image URL must be at most 500 characters')
      }
      if (formData.featured_image_alt && formData.featured_image_alt.length > 200) {
        validationErrors.push('Featured image alt text must be at most 200 characters')
      }
      if (formData.og_image && formData.og_image.length > 500) {
        validationErrors.push('OG image URL must be at most 500 characters')
      }
      if (formData.author_name && formData.author_name.length > 100) {
        validationErrors.push('Author name must be at most 100 characters')
      }
      if (formData.author_avatar && formData.author_avatar.length > 500) {
        validationErrors.push('Author avatar URL must be at most 500 characters')
      }
      if (formData.canonical_url && formData.canonical_url.length > 500) {
        validationErrors.push('Canonical URL must be at most 500 characters')
      }
      if (formData.twitter_title && formData.twitter_title.length > 70) {
        validationErrors.push('Twitter title must be at most 70 characters')
      }
      if (formData.twitter_description && formData.twitter_description.length > 200) {
        validationErrors.push('Twitter description must be at most 200 characters')
      }
      if (formData.twitter_image && formData.twitter_image.length > 500) {
        validationErrors.push('Twitter image URL must be at most 500 characters')
      }
      if (formData.schema_type && formData.schema_type.length > 50) {
        validationErrors.push('Schema type must be at most 50 characters')
      }
      
      if (validationErrors.length > 0) {
        alert(`Validation errors:\n${validationErrors.join('\n')}`)
        setSaving(false)
        return
      }

      const dataToSave = {
        ...formData,
        status: status as 'draft' | 'published' | 'scheduled' | 'archived',
      }
      
      if (isEditing) {
        await adminUpdateBlogPost(parseInt(postId), dataToSave)
      } else {
        const created = await adminCreateBlogPost(dataToSave as BlogPostCreate)
        navigate(`/app/admin/blog/${created.id}`, { replace: true })
      }
      
      setLastSaved(new Date())
      
      if (publish) {
        // Navigate back to list after publishing
        navigate('/app/admin/blog')
      }
    } catch (error: any) {
      console.error('Failed to save post:', error)
      
      // Extract detailed error message
      let errorMessage = 'Failed to save post. Please try again.'
      if (error?.message) {
        errorMessage = error.message
        // FastAPI validation errors are already formatted by fetchApi
        // Just use the message directly
      }
      
      // Show error in alert (for now - could be improved with a modal)
      alert(`Error: ${errorMessage}`)
    } finally {
      setSaving(false)
    }
  }

  async function handlePublish() {
    if (isEditing) {
      setSaving(true)
      try {
        await adminUpdateBlogPost(parseInt(postId), formData)
        await adminPublishBlogPost(parseInt(postId))
        navigate('/app/admin/blog')
      } catch (error) {
        console.error('Failed to publish:', error)
        alert('Failed to publish. Please try again.')
      } finally {
        setSaving(false)
      }
    } else {
      await handleSave(true)
    }
  }

  function updateFormData(field: keyof BlogPostCreate, value: any) {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  function toggleSection(section: keyof typeof expandedSections) {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  // Auto-generate meta description from excerpt or content
  function autoGenerateMetaDescription() {
    const text = formData.excerpt || generateExcerpt(formData.content)
    setFormData(prev => ({ ...prev, meta_description: text.substring(0, 160) }))
  }

  // Import JSON file
  function handleImportJSON(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const jsonData = JSON.parse(e.target?.result as string) as BlogPostCreate
        
        // Validate required fields
        if (!jsonData.title || !jsonData.content) {
          alert('Invalid JSON file: Missing title or content')
          return
        }

        // Populate form with imported data
        setFormData({
          title: jsonData.title || '',
          slug: jsonData.slug || generateSlug(jsonData.title),
          excerpt: jsonData.excerpt || '',
          content: jsonData.content || '',
          featured_image: jsonData.featured_image || '',
          featured_image_alt: jsonData.featured_image_alt || '',
          og_image: jsonData.og_image || jsonData.featured_image || '',
          author_name: jsonData.author_name || '',
          author_bio: jsonData.author_bio || '',
          author_avatar: jsonData.author_avatar || '',
          category_id: jsonData.category_id,
          tags: jsonData.tags || '',
          status: jsonData.status || 'draft',
          is_featured: jsonData.is_featured || false,
          is_pinned: jsonData.is_pinned || false,
          meta_title: jsonData.meta_title || jsonData.title || '',
          meta_description: jsonData.meta_description || '',
          meta_keywords: jsonData.meta_keywords || '',
          canonical_url: jsonData.canonical_url || '',
          no_index: jsonData.no_index || false,
          schema_type: jsonData.schema_type || 'Article',
          twitter_title: jsonData.twitter_title || jsonData.title?.substring(0, 70) || '',
          twitter_description: jsonData.twitter_description || jsonData.meta_description || '',
          twitter_image: jsonData.twitter_image || jsonData.featured_image || '',
        })

        setAutoSlug(false) // Don't auto-generate slug if imported
        alert('✅ Blog post imported successfully!')
      } catch (error) {
        console.error('Failed to import JSON:', error)
        alert('Failed to import JSON file. Please check the file format.')
      }
    }
    reader.readAsText(file)
    
    // Reset file input
    event.target.value = ''
  }

  const readTime = calculateReadTime(formData.content)
  const effectiveMetaTitle = formData.meta_title || formData.title
  const effectiveMetaDesc = formData.meta_description || formData.excerpt || generateExcerpt(formData.content)

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin w-8 h-8 border-4 border-accent-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-secondary-50 -m-8 p-8">
      {/* Top Bar */}
      <div className="bg-white border-b border-secondary-200 -mx-8 -mt-8 px-8 py-4 mb-6 sticky top-0 z-30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/app/admin/blog')}
              className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="w-5 h-5 text-secondary-600" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-secondary-900">
                {isEditing ? 'Edit Post' : 'New Post'}
              </h1>
              {lastSaved && (
                <p className="text-xs text-secondary-500">
                  Last saved {lastSaved.toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {!isEditing && (
              <label className="px-4 py-2 border border-secondary-200 rounded-lg font-medium hover:bg-secondary-50 transition-colors cursor-pointer flex items-center gap-2">
                <ArrowDownTrayIcon className="w-5 h-5 text-secondary-600" />
                <span className="text-secondary-700">Import JSON</span>
                <input
                  type="file"
                  accept=".json,application/json"
                  onChange={handleImportJSON}
                  className="hidden"
                />
              </label>
            )}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-secondary-100 rounded-lg">
              <span className={`w-2 h-2 rounded-full ${
                formData.status === 'published' ? 'bg-success-500' :
                formData.status === 'scheduled' ? 'bg-primary-500' :
                'bg-secondary-400'
              }`} />
              <span className="text-sm font-medium text-secondary-700 capitalize">{formData.status}</span>
            </div>
            <button
              onClick={() => handleSave()}
              disabled={saving}
              className="px-4 py-2 border border-secondary-200 rounded-lg font-medium hover:bg-secondary-50 transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Draft'}
            </button>
            <button
              onClick={handlePublish}
              disabled={saving || !formData.title || !formData.content}
              className="px-4 py-2 bg-accent-500 text-white rounded-lg font-medium hover:bg-accent-600 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <CloudArrowUpIcon className="w-5 h-5" />
              {formData.status === 'published' ? 'Update' : 'Publish'}
            </button>
          </div>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Main Editor */}
        <div className="flex-1 space-y-6">
          {/* Title */}
          <div className="bg-white rounded-xl border border-secondary-200 p-6">
            <input
              type="text"
              value={formData.title}
              onChange={(e) => updateFormData('title', e.target.value)}
              onPaste={(e) => {
                const plainText = e.clipboardData.getData('text/plain')
                if (plainText && plainText.includes('\\n')) {
                  e.preventDefault()
                  // Strip literal \n from title
                  const converted = plainText.replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim()
                  updateFormData('title', converted)
                }
              }}
              placeholder="Post title..."
              className="w-full text-3xl font-bold text-secondary-900 placeholder-secondary-400 border-none outline-none"
            />
            <div className="flex items-center gap-2 mt-4">
              <span className="text-sm text-secondary-500">/blog/</span>
              <input
                type="text"
                value={formData.slug}
                onChange={(e) => {
                  setAutoSlug(false)
                  updateFormData('slug', e.target.value)
                }}
                placeholder="post-slug"
                className="flex-1 text-sm text-secondary-600 border-none outline-none bg-secondary-50 px-2 py-1 rounded"
              />
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-white rounded-xl border border-secondary-200 overflow-hidden">
            <div className="flex border-b border-secondary-200">
              <button
                onClick={() => setActiveTab('write')}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'write'
                    ? 'text-accent-600 border-b-2 border-accent-500 bg-accent-50/50'
                    : 'text-secondary-500 hover:text-secondary-700'
                }`}
              >
                <PencilIcon className="w-4 h-4 inline mr-2" />
                Write
              </button>
              <button
                onClick={() => setActiveTab('preview')}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'preview'
                    ? 'text-accent-600 border-b-2 border-accent-500 bg-accent-50/50'
                    : 'text-secondary-500 hover:text-secondary-700'
                }`}
              >
                <EyeIcon className="w-4 h-4 inline mr-2" />
                Preview
              </button>
            </div>
            
            <div className="p-6">
              {activeTab === 'write' ? (
                <div className="space-y-4">
                  {/* Excerpt */}
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-2">Excerpt</label>
                    <textarea
                      value={formData.excerpt}
                      onChange={(e) => updateFormData('excerpt', e.target.value)}
                      onPaste={(e) => {
                        const plainText = e.clipboardData.getData('text/plain')
                        if (plainText && plainText.includes('\\n')) {
                          e.preventDefault()
                          // Convert literal \n to spaces for excerpt (single paragraph)
                          const converted = plainText.replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim()
                          updateFormData('excerpt', converted)
                        }
                      }}
                      placeholder="Brief summary of the post (shown in listings)..."
                      rows={2}
                      className="w-full px-4 py-3 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 resize-none"
                    />
                    <div className="flex justify-between mt-1">
                      <span className="text-xs text-secondary-400">Recommended: 150-200 characters</span>
                      <span className={`text-xs ${(formData.excerpt?.length || 0) > 200 ? 'text-error-500' : 'text-secondary-400'}`}>
                        {formData.excerpt?.length || 0}/200
                      </span>
                    </div>
                  </div>
                  
                  {/* Content */}
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-2">Content (Markdown)</label>
                    
                    {/* Formatting Toolbar */}
                    <div className="flex items-center gap-1 p-2 bg-secondary-50 border border-secondary-200 border-b-0 rounded-t-lg">
                      <button
                        type="button"
                        onClick={() => {
                          const textarea = document.getElementById('content-editor') as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const end = textarea.selectionEnd
                          const text = formData.content
                          const selected = text.substring(start, end)
                          const newText = text.substring(0, start) + `**${selected}**` + text.substring(end)
                          updateFormData('content', newText)
                          setTimeout(() => {
                            textarea.focus()
                            textarea.setSelectionRange(start + 2, end + 2)
                          }, 0)
                        }}
                        className="p-2 hover:bg-secondary-200 rounded text-secondary-700 font-bold text-sm"
                        title="Bold (wrap selection)"
                      >
                        B
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const textarea = document.getElementById('content-editor') as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const end = textarea.selectionEnd
                          const text = formData.content
                          const selected = text.substring(start, end)
                          const newText = text.substring(0, start) + `*${selected}*` + text.substring(end)
                          updateFormData('content', newText)
                          setTimeout(() => {
                            textarea.focus()
                            textarea.setSelectionRange(start + 1, end + 1)
                          }, 0)
                        }}
                        className="p-2 hover:bg-secondary-200 rounded text-secondary-700 italic text-sm"
                        title="Italic (wrap selection)"
                      >
                        I
                      </button>
                      <div className="w-px h-5 bg-secondary-300 mx-1" />
                      <button
                        type="button"
                        onClick={() => {
                          const textarea = document.getElementById('content-editor') as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const text = formData.content
                          const lineStart = text.lastIndexOf('\n', start - 1) + 1
                          const newText = text.substring(0, lineStart) + '## ' + text.substring(lineStart)
                          updateFormData('content', newText)
                        }}
                        className="p-2 hover:bg-secondary-200 rounded text-secondary-700 text-sm font-semibold"
                        title="Heading 2"
                      >
                        H2
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const textarea = document.getElementById('content-editor') as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const text = formData.content
                          const lineStart = text.lastIndexOf('\n', start - 1) + 1
                          const newText = text.substring(0, lineStart) + '### ' + text.substring(lineStart)
                          updateFormData('content', newText)
                        }}
                        className="p-2 hover:bg-secondary-200 rounded text-secondary-700 text-sm"
                        title="Heading 3"
                      >
                        H3
                      </button>
                      <div className="w-px h-5 bg-secondary-300 mx-1" />
                      <button
                        type="button"
                        onClick={() => {
                          const textarea = document.getElementById('content-editor') as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const text = formData.content
                          const lineStart = text.lastIndexOf('\n', start - 1) + 1
                          const newText = text.substring(0, lineStart) + '- ' + text.substring(lineStart)
                          updateFormData('content', newText)
                        }}
                        className="p-2 hover:bg-secondary-200 rounded text-secondary-700 text-sm"
                        title="Bullet point"
                      >
                        •
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const textarea = document.getElementById('content-editor') as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const text = formData.content
                          const lineStart = text.lastIndexOf('\n', start - 1) + 1
                          const newText = text.substring(0, lineStart) + '> ' + text.substring(lineStart)
                          updateFormData('content', newText)
                        }}
                        className="p-2 hover:bg-secondary-200 rounded text-secondary-700 text-sm"
                        title="Blockquote"
                      >
                        "
                      </button>
                      <div className="flex-1" />
                      <span className="text-xs text-secondary-400 px-2">Paste formatted text - it auto-converts to Markdown!</span>
                    </div>
                    
                    <textarea
                      id="content-editor"
                      value={formData.content}
                      onChange={(e) => updateFormData('content', e.target.value)}
                      onPaste={(e) => {
                        const html = e.clipboardData.getData('text/html')
                        const plainText = e.clipboardData.getData('text/plain')
                        
                        // Check if plain text contains literal \n sequences (from n8n)
                        if (plainText && plainText.includes('\\n')) {
                          e.preventDefault()
                          // Convert literal \n to actual newlines
                          const converted = plainText
                            .replace(/\\n\\n/g, '\n\n')  // Double newlines first
                            .replace(/\\n/g, '\n')       // Then single newlines
                            .replace(/\\t/g, '\t')       // Tabs too
                          const textarea = e.target as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const end = textarea.selectionEnd
                          const text = formData.content
                          const newText = text.substring(0, start) + converted + text.substring(end)
                          updateFormData('content', newText)
                        } else if (html) {
                          e.preventDefault()
                          const markdown = htmlToMarkdown(html)
                          const textarea = e.target as HTMLTextAreaElement
                          const start = textarea.selectionStart
                          const end = textarea.selectionEnd
                          const text = formData.content
                          const newText = text.substring(0, start) + markdown + text.substring(end)
                          updateFormData('content', newText)
                        }
                      }}
                      placeholder="Write your post content here or paste formatted text from Word/Google Docs...

## Section Heading

Regular paragraph text goes here. Use **bold** and *italic* for emphasis.

- Bullet point one
- Bullet point two
- Bullet point three

> This is a blockquote for important callouts

### Subsection Heading

More content here..."
                      rows={20}
                      className="w-full px-4 py-3 border border-secondary-200 rounded-b-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 font-mono text-sm resize-y min-h-[400px]"
                    />
                    <div className="flex justify-between mt-1">
                      <span className="text-xs text-secondary-400">
                        {formData.content.split(/\s+/).filter(Boolean).length} words • ~{readTime} min read
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="prose prose-lg max-w-none">
                  {formData.content ? (
                    <div className="space-y-4">
                      {formData.content.split('\n').map((line, i) => {
                        const trimmed = line.trim()
                        if (trimmed.startsWith('## ')) {
                          return <h2 key={i} className="text-2xl font-bold mt-6 mb-3">{trimmed.slice(3)}</h2>
                        }
                        if (trimmed.startsWith('### ')) {
                          return <h3 key={i} className="text-xl font-bold mt-4 mb-2">{trimmed.slice(4)}</h3>
                        }
                        if (trimmed.startsWith('> ')) {
                          return <blockquote key={i} className="border-l-4 border-accent-500 pl-4 italic text-secondary-600">{trimmed.slice(2)}</blockquote>
                        }
                        if (trimmed.startsWith('- ')) {
                          return <li key={i} className="ml-4">{trimmed.slice(2)}</li>
                        }
                        if (trimmed) {
                          return <p key={i} className="text-secondary-700">{trimmed}</p>
                        }
                        return null
                      })}
                    </div>
                  ) : (
                    <p className="text-secondary-400 italic">Start writing to see preview...</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="w-96 space-y-6">
          {/* Featured Image */}
          <div className="bg-white rounded-xl border border-secondary-200 p-6">
            <h3 className="font-semibold text-secondary-900 mb-4 flex items-center gap-2">
              <PhotoIcon className="w-5 h-5 text-secondary-400" />
              Featured Image
            </h3>
            {formData.featured_image ? (
              <div className="space-y-3">
                <img
                  src={formData.featured_image}
                  alt={formData.featured_image_alt || 'Preview'}
                  className="w-full h-40 object-cover rounded-lg"
                />
                <button
                  onClick={() => updateFormData('featured_image', '')}
                  className="text-sm text-error-500 hover:text-error-600"
                >
                  Remove image
                </button>
              </div>
            ) : (
              <div className="border-2 border-dashed border-secondary-200 rounded-lg p-6 text-center">
                <PhotoIcon className="w-8 h-8 text-secondary-300 mx-auto mb-2" />
                <p className="text-sm text-secondary-500">Enter image URL below</p>
              </div>
            )}
            <input
              type="text"
              value={formData.featured_image}
              onChange={(e) => {
                updateFormData('featured_image', e.target.value)
                // Reset image check status when URL changes
                setImageCheckStatus({ checking: false, accessible: null, error: null })
              }}
              onBlur={async () => {
                // Check image accessibility when user leaves the field
                const url = formData.featured_image?.trim()
                if (url && /^https?:\/\//i.test(url)) {
                  setImageCheckStatus({ checking: true, accessible: null, error: null })
                  try {
                    // Use HEAD request to check if image is accessible
                    const response = await fetch(url, {
                      method: 'HEAD',
                      mode: 'no-cors', // Use no-cors to avoid CORS issues, but we can't read response
                    })
                    // Since we can't read response in no-cors mode, try loading image instead
                    const img = new Image()
                    img.crossOrigin = 'anonymous'
                    await new Promise((resolve, reject) => {
                      img.onload = () => {
                        setImageCheckStatus({ checking: false, accessible: true, error: null })
                        resolve(true)
                      }
                      img.onerror = () => {
                        setImageCheckStatus({ checking: false, accessible: false, error: 'Image is not accessible. Please check the URL.' })
                        reject(new Error('Image load failed'))
                      }
                      img.src = url
                      // Timeout after 5 seconds
                      setTimeout(() => {
                        if (!img.complete) {
                          setImageCheckStatus({ checking: false, accessible: false, error: 'Image check timed out. URL may not be accessible.' })
                          reject(new Error('Timeout'))
                        }
                      }, 5000)
                    })
                  } catch (error) {
                    // Error already handled in onerror
                  }
                }
              }}
              placeholder="https://example.com/image.jpg"
              className="w-full mt-3 px-3 py-2 text-sm border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20"
            />
            {formData.featured_image && (() => {
              const url = formData.featured_image.trim()
              
              // Comprehensive validation
              if (!url || url.length < 10 || url.length > 2048) {
                return (
                  <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                    <span>❌</span>
                    <span>Error: Invalid URL length</span>
                  </p>
                )
              }
              
              if (!/^https?:\/\//i.test(url)) {
                return (
                  <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                    <span>❌</span>
                    <span>Error: URL must start with http:// or https://</span>
                  </p>
                )
              }
              
              if (/[\s\n\r]/.test(url)) {
                return (
                  <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                    <span>❌</span>
                    <span>Error: URL contains invalid characters (spaces, newlines)</span>
                  </p>
                )
              }
              
              try {
                const urlObj = new URL(url)
                const path = urlObj.pathname.toLowerCase()
                
                const hasImageExtension = /\.(jpg|jpeg|png|webp|gif|svg)(\?|$|#)/i.test(path)
                const trustedDomains = [
                  'steamcdn-a.akamaihd.net',
                  'images.unsplash.com',
                  'cdn.cloudflare.com',
                  'i.imgur.com',
                  'i.redd.it',
                  'media.steampowered.com',
                  'cdn.akamai.steamstatic.com',
                ]
                const isFromTrustedDomain = trustedDomains.some(domain => urlObj.hostname.includes(domain))
                const rejectedPatterns = [
                  /serpapi\.com/i,
                  /googleusercontent\.com\/imgres/i,
                  /\.html/i,
                  /\.php/i,
                  /\.aspx/i,
                  /\/page\//i,
                  /\/article\//i,
                  /\/news\//i,
                  /cdn2\.unrealengine\.com/i,
                  /epicgames\.com\/[^/]*\.(html|php|aspx)/i,
                  /\/thumb\//i,
                  /\/preview\//i,
                  /\?.*format=/i,
                ]
                const isRejected = rejectedPatterns.some(pattern => pattern.test(url))
                const suspiciousPathPatterns = [/\/api\//i, /\/embed\//i, /\/redirect\//i, /\/proxy\//i]
                const hasSuspiciousPath = suspiciousPathPatterns.some(pattern => pattern.test(path))
                const hasImageLikePath = path.length > 1 && !/^\/(page|article|news|home|index)/i.test(path)
                
                if (!hasImageExtension && !isFromTrustedDomain) {
                  return (
                    <p className="text-xs text-warning-600 mt-1 flex items-center gap-1">
                      <span>⚠️</span>
                      <span>Warning: This doesn't appear to be a direct image link. Use URLs ending in .jpg, .png, .webp, etc.</span>
                    </p>
                  )
                }
                
                if (isRejected) {
                  return (
                    <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                      <span>❌</span>
                      <span>Error: This URL type is not supported. Please use a direct image link.</span>
                    </p>
                  )
                }
                
                if (hasSuspiciousPath || !hasImageLikePath) {
                  return (
                    <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                      <span>❌</span>
                      <span>Error: URL path looks suspicious or doesn't appear to be an image</span>
                    </p>
                  )
                }
                
                // Show accessibility check result if available
                if (imageCheckStatus.checking) {
                  return (
                    <p className="text-xs text-primary-600 mt-1 flex items-center gap-1">
                      <span>⏳</span>
                      <span>Checking image accessibility...</span>
                    </p>
                  )
                }
                
                if (imageCheckStatus.accessible === false && imageCheckStatus.error) {
                  return (
                    <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                      <span>❌</span>
                      <span>{imageCheckStatus.error}</span>
                    </p>
                  )
                }
                
                if (imageCheckStatus.accessible === true) {
                  return (
                    <p className="text-xs text-success-600 mt-1 flex items-center gap-1">
                      <span>✅</span>
                      <span>Valid image URL and accessible</span>
                    </p>
                  )
                }
                
                return (
                  <p className="text-xs text-success-600 mt-1 flex items-center gap-1">
                    <span>✅</span>
                    <span>Valid image URL format (click outside field to check accessibility)</span>
                  </p>
                )
              } catch (e) {
                return (
                  <p className="text-xs text-error-600 mt-1 flex items-center gap-1">
                    <span>❌</span>
                    <span>Error: Invalid URL format</span>
                  </p>
                )
              }
            })()}
            <input
              type="text"
              value={formData.featured_image_alt}
              onChange={(e) => updateFormData('featured_image_alt', e.target.value)}
              placeholder="Image alt text (for accessibility)"
              className="w-full mt-2 px-3 py-2 text-sm border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20"
            />
          </div>

          {/* Category & Tags */}
          <div className="bg-white rounded-xl border border-secondary-200 p-6">
            <h3 className="font-semibold text-secondary-900 mb-4 flex items-center gap-2">
              <HashtagIcon className="w-5 h-5 text-secondary-400" />
              Organization
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-secondary-600 mb-1">Category</label>
                <select
                  value={formData.category_id || ''}
                  onChange={(e) => updateFormData('category_id', e.target.value ? parseInt(e.target.value) : undefined)}
                  className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                >
                  <option value="">No category</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-secondary-600 mb-1">Tags</label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => updateFormData('tags', e.target.value)}
                  onPaste={(e) => {
                    const plainText = e.clipboardData.getData('text/plain')
                    if (plainText && plainText.includes('\\n')) {
                      e.preventDefault()
                      // Strip literal \n from tags
                      const converted = plainText.replace(/\\n/g, ', ').replace(/,\s*,/g, ',').replace(/\s+/g, ' ').trim()
                      updateFormData('tags', converted)
                    }
                  }}
                  placeholder="seo, marketing, tips"
                  className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                />
                <p className="text-xs text-secondary-400 mt-1">Comma-separated</p>
              </div>
            </div>
          </div>

          {/* Author */}
          <div className="bg-white rounded-xl border border-secondary-200 p-6">
            <h3 className="font-semibold text-secondary-900 mb-4 flex items-center gap-2">
              <UserIcon className="w-5 h-5 text-secondary-400" />
              Author
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                value={formData.author_name}
                onChange={(e) => updateFormData('author_name', e.target.value)}
                placeholder="Author name"
                className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
              />
              <input
                type="text"
                value={formData.author_avatar}
                onChange={(e) => updateFormData('author_avatar', e.target.value)}
                placeholder="Avatar URL"
                className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
              />
              <textarea
                value={formData.author_bio}
                onChange={(e) => updateFormData('author_bio', e.target.value)}
                placeholder="Brief author bio..."
                rows={2}
                className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm resize-none"
              />
            </div>
          </div>

          {/* Visibility */}
          <div className="bg-white rounded-xl border border-secondary-200 p-6">
            <h3 className="font-semibold text-secondary-900 mb-4">Visibility</h3>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_featured}
                  onChange={(e) => updateFormData('is_featured', e.target.checked)}
                  className="w-4 h-4 text-accent-500 border-secondary-300 rounded focus:ring-accent-500"
                />
                <span className="text-sm text-secondary-700">Featured post</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.is_pinned}
                  onChange={(e) => updateFormData('is_pinned', e.target.checked)}
                  className="w-4 h-4 text-accent-500 border-secondary-300 rounded focus:ring-accent-500"
                />
                <span className="text-sm text-secondary-700">Pin to top</span>
              </label>
            </div>
          </div>

          {/* SEO Section */}
          <div className="bg-white rounded-xl border border-secondary-200 overflow-hidden">
            <button
              onClick={() => toggleSection('seo')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-secondary-50 transition-colors"
            >
              <h3 className="font-semibold text-secondary-900 flex items-center gap-2">
                <MagnifyingGlassIcon className="w-5 h-5 text-secondary-400" />
                SEO Settings
              </h3>
              {expandedSections.seo ? (
                <ChevronUpIcon className="w-5 h-5 text-secondary-400" />
              ) : (
                <ChevronDownIcon className="w-5 h-5 text-secondary-400" />
              )}
            </button>
            {expandedSections.seo && (
              <div className="px-6 pb-6 space-y-4 border-t border-secondary-100 pt-4">
                {/* Google Preview */}
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <p className="text-xs text-secondary-500 mb-2">Google Preview</p>
                  <div className="text-primary-600 text-lg hover:underline cursor-pointer truncate">
                    {effectiveMetaTitle || 'Post Title'}
                  </div>
                  <div className="text-success-700 text-sm truncate">
                    mymetaview.com/blog/{formData.slug || 'post-slug'}
                  </div>
                  <div className="text-secondary-600 text-sm line-clamp-2">
                    {effectiveMetaDesc || 'Add a meta description to improve SEO...'}
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">
                    Meta Title
                    <span className={`ml-2 ${(formData.meta_title?.length || 0) > 70 ? 'text-error-500' : (formData.meta_title?.length || 0) > 60 ? 'text-warning-500' : 'text-secondary-400'}`}>
                      ({formData.meta_title?.length || 0}/70)
                    </span>
                    {(formData.meta_title?.length || 0) > 70 && (
                      <span className="ml-2 text-xs text-error-600">⚠️ Exceeds limit</span>
                    )}
                  </label>
                  <input
                    type="text"
                    value={formData.meta_title}
                    onChange={(e) => updateFormData('meta_title', e.target.value)}
                    placeholder={formData.title || 'SEO title (defaults to post title)'}
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  />
                </div>
                
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-sm text-secondary-600">
                      Meta Description
                      <span className={`ml-2 ${(formData.meta_description?.length || 0) > 160 ? 'text-error-500' : 'text-secondary-400'}`}>
                        ({formData.meta_description?.length || 0}/160)
                      </span>
                    </label>
                    <button
                      onClick={autoGenerateMetaDescription}
                      className="text-xs text-accent-500 hover:text-accent-600"
                    >
                      Auto-generate
                    </button>
                  </div>
                  <textarea
                    value={formData.meta_description}
                    onChange={(e) => updateFormData('meta_description', e.target.value)}
                    onPaste={(e) => {
                      const plainText = e.clipboardData.getData('text/plain')
                      if (plainText && plainText.includes('\\n')) {
                        e.preventDefault()
                        // Convert literal \n to spaces for meta description (single line)
                        const converted = plainText.replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim().substring(0, 160)
                        updateFormData('meta_description', converted)
                      }
                    }}
                    placeholder="Brief description for search results..."
                    rows={3}
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm resize-none"
                  />
                </div>
                
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">Keywords</label>
                  <input
                    type="text"
                    value={formData.meta_keywords}
                    onChange={(e) => updateFormData('meta_keywords', e.target.value)}
                    placeholder="keyword1, keyword2, keyword3"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  />
                </div>

                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.no_index}
                    onChange={(e) => updateFormData('no_index', e.target.checked)}
                    className="w-4 h-4 text-accent-500 border-secondary-300 rounded focus:ring-accent-500"
                  />
                  <span className="text-sm text-secondary-700">No index (hide from search engines)</span>
                </label>
              </div>
            )}
          </div>

          {/* Social Media Section */}
          <div className="bg-white rounded-xl border border-secondary-200 overflow-hidden">
            <button
              onClick={() => toggleSection('social')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-secondary-50 transition-colors"
            >
              <h3 className="font-semibold text-secondary-900 flex items-center gap-2">
                <GlobeAltIcon className="w-5 h-5 text-secondary-400" />
                Social Media
              </h3>
              {expandedSections.social ? (
                <ChevronUpIcon className="w-5 h-5 text-secondary-400" />
              ) : (
                <ChevronDownIcon className="w-5 h-5 text-secondary-400" />
              )}
            </button>
            {expandedSections.social && (
              <div className="px-6 pb-6 space-y-4 border-t border-secondary-100 pt-4">
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">Open Graph Image</label>
                  <input
                    type="text"
                    value={formData.og_image}
                    onChange={(e) => updateFormData('og_image', e.target.value)}
                    placeholder="https://... (1200x630 recommended)"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">Twitter Title</label>
                  <input
                    type="text"
                    value={formData.twitter_title}
                    onChange={(e) => updateFormData('twitter_title', e.target.value)}
                    placeholder="Custom title for Twitter"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">Twitter Description</label>
                  <input
                    type="text"
                    value={formData.twitter_description}
                    onChange={(e) => updateFormData('twitter_description', e.target.value)}
                    placeholder="Custom description for Twitter"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Advanced Section */}
          <div className="bg-white rounded-xl border border-secondary-200 overflow-hidden">
            <button
              onClick={() => toggleSection('advanced')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-secondary-50 transition-colors"
            >
              <h3 className="font-semibold text-secondary-900 flex items-center gap-2">
                <LinkIcon className="w-5 h-5 text-secondary-400" />
                Advanced
              </h3>
              {expandedSections.advanced ? (
                <ChevronUpIcon className="w-5 h-5 text-secondary-400" />
              ) : (
                <ChevronDownIcon className="w-5 h-5 text-secondary-400" />
              )}
            </button>
            {expandedSections.advanced && (
              <div className="px-6 pb-6 space-y-4 border-t border-secondary-100 pt-4">
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">Canonical URL</label>
                  <input
                    type="text"
                    value={formData.canonical_url}
                    onChange={(e) => updateFormData('canonical_url', e.target.value)}
                    placeholder="https://example.com/original-post"
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  />
                  <p className="text-xs text-secondary-400 mt-1">Use if this content was originally published elsewhere</p>
                </div>
                <div>
                  <label className="block text-sm text-secondary-600 mb-1">Schema Type</label>
                  <select
                    value={formData.schema_type}
                    onChange={(e) => updateFormData('schema_type', e.target.value)}
                    className="w-full px-3 py-2 border border-secondary-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500/20 text-sm"
                  >
                    <option value="Article">Article</option>
                    <option value="BlogPosting">Blog Posting</option>
                    <option value="NewsArticle">News Article</option>
                    <option value="TechArticle">Tech Article</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

