import { useState, useEffect, useRef } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import {
  CalendarIcon,
  ClockIcon,
  EyeIcon,
  TagIcon,
  ArrowLeftIcon,
  ShareIcon,
  BookmarkIcon,
  ChevronRightIcon,
  SparklesIcon,
  LinkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline'
import {
  fetchBlogPostBySlug,
  fetchRecentBlogPosts,
  fetchBlogCategories,
  type BlogPost as BlogPostType,
  type BlogPostListItem,
  type BlogCategory,
} from '../api/client'
import { useToast } from '../components/ui/Toast'

// Clean markdown renderer - requires proper markdown syntax
function renderContent(content: string, featuredImageUrl?: string, contentImageUrl?: string): JSX.Element {
  const processInline = (text: string): string => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-secondary-900">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
      .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-accent-50 text-accent-600 rounded text-[0.9em] font-mono border border-accent-100">$1</code>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-accent-600 hover:text-accent-700 underline decoration-accent-300 underline-offset-2 transition-colors font-medium" target="_blank" rel="noopener noreferrer">$1</a>')
  }

  // Pre-process content to clean up common paste artifacts and recover structure
  let cleanedContent = content
    .replace(/\*{4,}/g, '') // Remove 4+ asterisks
    .replace(/\*{3}/g, '**') // Convert *** to **
    .replace(/\*\*\s*\*\*/g, '') // Remove empty bold markers
    .replace(/^\s*[-•]\s*$/gm, '') // Remove standalone bullets on their own line
    // Remove image markdown if it matches featured_image (already displayed)
    .replace(new RegExp(`!\\[.*?\\]\\(${featuredImageUrl?.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') || ''}\\)`, 'g'), '')
    // Recover structure: add newlines before markdown patterns that are inline
    .replace(/([.!?])\s*(#{2,3}\s)/g, '$1\n\n$2') // Add newline before ## or ### after sentence
    .replace(/([.!?])\s*(\d+\.\s+[A-Z])/g, '$1\n\n$2') // Add newline before "1. Title" after sentence
    .replace(/([.!?])\s*(-\s+[A-Z])/g, '$1\n\n$2') // Add newline before "- Item" after sentence
    .replace(/\n{3,}/g, '\n\n') // Max 2 consecutive newlines

  const lines = cleanedContent.split('\n')
  type BlockType = { type: string; content: string; lines?: string[] }
  const blocks: BlockType[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()
    
    if (!trimmed) {
      i++
      continue
    }

    // Code blocks
    if (trimmed.startsWith('```')) {
      const lang = trimmed.slice(3)
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      blocks.push({ type: 'code', content: codeLines.join('\n'), lines: [lang] })
      i++
      continue
    }

    // Markdown images: ![](url) or ![alt](url)
    if (/^!\[.*?\]\(.+\)$/.test(trimmed)) {
      const match = trimmed.match(/^!\[(.*?)\]\((.+)\)$/)
      if (match) {
        const alt = match[1]
        const url = match[2]
        // Skip if it's the same as featured_image (already displayed)
        if (featuredImageUrl && url === featuredImageUrl) {
          i++
          continue
        }
        blocks.push({ type: 'image', content: url, lines: [alt] })
        i++
        continue
      }
    }

    // Headings
    if (trimmed.startsWith('## ')) {
      blocks.push({ type: 'h2', content: trimmed.slice(3) })
      i++
      continue
    }
    if (trimmed.startsWith('### ')) {
      blocks.push({ type: 'h3', content: trimmed.slice(4) })
      i++
      continue
    }

    // Blockquote
    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('>')) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
        i++
      }
      blocks.push({ type: 'quote', content: quoteLines.join(' ') })
      continue
    }

    // Skip standalone dashes or asterisks (broken list artifacts)
    if (trimmed === '-' || trimmed === '*' || trimmed === '•') {
      i++
      continue
    }

    // Bullet lists
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
      const listItems: string[] = []
      while (i < lines.length) {
        const currentLine = lines[i].trim()
        if (currentLine.startsWith('- ') || currentLine.startsWith('* ') || currentLine.startsWith('• ')) {
          listItems.push(currentLine.replace(/^[-*•]\s+/, ''))
          i++
        } else if (currentLine === '' || currentLine === '-' || currentLine === '*') {
          // Skip empty lines and standalone dashes within list context
          i++
        } else {
          break
        }
      }
      if (listItems.length > 0) {
        blocks.push({ type: 'ul', content: '', lines: listItems })
      }
      continue
    }

    // Numbered items - check if it's a list (multiple consecutive) or a section title (single with paragraph after)
    if (/^\d+\.\s/.test(trimmed)) {
      // Look ahead to see if next non-empty line is also numbered
      let j = i + 1
      while (j < lines.length && !lines[j].trim()) j++
      const nextLine = j < lines.length ? lines[j].trim() : ''
      const isNextAlsoNumbered = /^\d+\.\s/.test(nextLine)
      
      if (isNextAlsoNumbered) {
        // It's a true numbered list - collect all items
        const listItems: string[] = []
        while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
          listItems.push(lines[i].trim().replace(/^\d+\.\s/, ''))
          i++
          // Skip empty lines between list items
          while (i < lines.length && !lines[i].trim()) i++
        }
        blocks.push({ type: 'ol', content: '', lines: listItems })
      } else {
        // It's a numbered section title (like "1. Match the Message")
        const num = trimmed.match(/^(\d+)\./)?.[1] || ''
        const title = trimmed.replace(/^\d+\.\s*/, '')
        blocks.push({ type: 'numbered-section', content: title, lines: [num] })
        i++
      }
      continue
    }

    // Horizontal rule
    if (trimmed === '---' || trimmed === '***') {
      blocks.push({ type: 'hr', content: '' })
      i++
      continue
    }

    // Callout/highlight box (custom: starts with !)
    if (trimmed.startsWith('! ')) {
      blocks.push({ type: 'callout', content: trimmed.slice(2) })
      i++
      continue
    }

    // Regular paragraph - combine consecutive lines
    const paraLines: string[] = [trimmed]
    i++
    while (i < lines.length) {
      const nextLine = lines[i].trim()
      if (!nextLine || nextLine.startsWith('#') || nextLine.startsWith('>') || 
          nextLine.startsWith('- ') || nextLine.startsWith('* ') || 
          /^\d+\.\s/.test(nextLine) || nextLine.startsWith('```') ||
          nextLine.startsWith('! ') || nextLine === '---' || nextLine === '***') {
        break
      }
      paraLines.push(nextLine)
      i++
    }
    blocks.push({ type: 'paragraph', content: paraLines.join(' ') })
  }

  let paragraphCount = 0
  let h2Count = 0
  const maxContentImages = 2 // Max images to insert in content
  const insertedImageIndices: number[] = [] // Track where we've inserted images
  
  // Smart image placement - determine best place to insert content image
  const shouldInsertContentImage = (index: number, blocksArray: BlockType[]): boolean => {
    // Must have a content image (different from featured image)
    if (!contentImageUrl || !isValidImageUrl(contentImageUrl)) return false
    if (insertedImageIndices.length >= maxContentImages) return false
    
    // Don't insert at the very start (featured image is there)
    if (index < 3) return false
    
    // Check if there's already an image nearby (within next 4 blocks)
    for (let i = index + 1; i < Math.min(index + 5, blocksArray.length); i++) {
      if (blocksArray[i].type === 'image') return false
    }
    
    // Check previous blocks - don't insert right after another image
    for (let i = Math.max(0, index - 2); i < index; i++) {
      if (blocksArray[i].type === 'image') return false
    }
    
    const currentBlock = blocksArray[index]
    
    // Good placement opportunities:
    // 1. After H2 heading (but not the first one - that's too early)
    if (currentBlock.type === 'h2' && h2Count >= 1 && h2Count <= 3) {
      return true
    }
    
    // 2. After a substantial paragraph (3+ sentences worth of content)
    if (currentBlock.type === 'paragraph') {
      const wordCount = currentBlock.content.split(/\s+/).length
      // Insert after paragraphs with 30+ words (substantial content)
      if (wordCount >= 30 && paragraphCount >= 2) {
        return true
      }
    }
    
    // 3. After H3 if we're deeper in the article
    if (currentBlock.type === 'h3' && h2Count >= 2) {
      return true
    }
    
    return false
  }

  const elements = blocks.map((block, index) => {
    switch (block.type) {
      case 'code':
        return (
          <div key={index} className="my-8 rounded-xl overflow-hidden border border-secondary-200 shadow-lg">
            {block.lines?.[0] && (
              <div className="bg-secondary-800 px-4 py-2.5 text-xs font-mono text-secondary-400 border-b border-secondary-700 flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-error-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-warning-500/80"></span>
                <span className="w-3 h-3 rounded-full bg-success-500/80"></span>
                <span className="ml-2">{block.lines[0]}</span>
              </div>
            )}
            <pre className="bg-secondary-900 p-5 overflow-x-auto">
              <code className="text-sm font-mono text-secondary-100 leading-relaxed">{block.content}</code>
            </pre>
          </div>
        )

      case 'h2': {
        h2Count++
        const id = block.content.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
        const shouldInsertImage = shouldInsertContentImage(index, blocks)
        
        return (
          <>
            <h2 key={index} id={id} className="text-2xl sm:text-3xl font-bold text-secondary-900 mt-12 mb-4 leading-tight">
              {block.content}
            </h2>
            {shouldInsertImage && contentImageUrl && isValidImageUrl(contentImageUrl) && !insertedImageIndices.includes(index) && (() => {
              insertedImageIndices.push(index)
              return (
                <div key={`${index}-img`} className="my-8">
                  <img
                    src={contentImageUrl}
                    alt={block.content}
                    className="w-full h-auto rounded-xl shadow-lg"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement
                      target.style.display = 'none'
                    }}
                  />
                </div>
              )
            })()}
          </>
        )
      }

      case 'h3': {
        const id = block.content.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
        const shouldInsertImage = shouldInsertContentImage(index, blocks)
        
        return (
          <>
            <h3 key={index} id={id} className="text-xl sm:text-2xl font-bold text-secondary-900 mt-10 mb-3 leading-tight">
              {block.content}
            </h3>
            {shouldInsertImage && contentImageUrl && isValidImageUrl(contentImageUrl) && !insertedImageIndices.includes(index) && (() => {
              insertedImageIndices.push(index)
              return (
                <div key={`${index}-img`} className="my-8">
                  <img
                    src={contentImageUrl}
                    alt={block.content}
                    className="w-full h-auto rounded-xl shadow-lg"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement
                      target.style.display = 'none'
                    }}
                  />
                </div>
              )
            })()}
          </>
        )
      }

      case 'numbered-section':
        // Clean up any stray asterisks from the title
        const cleanTitle = block.content.replace(/\*+$/, '').replace(/^\*+/, '').trim()
        return (
          <div key={index} className="mt-10 mb-4 flex items-start gap-4">
            <span className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-500 text-white font-bold text-sm flex items-center justify-center shadow-lg shadow-accent-500/20">
              {block.lines?.[0]}
            </span>
            <h3 className="text-xl sm:text-2xl font-bold text-secondary-900 leading-tight pt-0.5">
              {cleanTitle}
            </h3>
          </div>
        )

      case 'image':
        // Only render if it's a valid image URL
        if (!isValidImageUrl(block.content)) {
          return null
        }
        return (
          <div key={index} className="my-10">
            <img
              src={block.content}
              alt={block.lines?.[0] || ''}
              className="w-full h-auto rounded-xl shadow-lg"
              onError={(e) => {
                const target = e.target as HTMLImageElement
                target.style.display = 'none'
              }}
            />
          </div>
        )

      case 'quote':
        return (
          <blockquote key={index} className="my-8 pl-6 py-4 border-l-4 border-accent-500 bg-accent-50/50 rounded-r-xl">
            <p 
              className="text-lg sm:text-xl italic text-secondary-700 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: processInline(block.content) }}
            />
          </blockquote>
        )

      case 'callout':
        return (
          <div key={index} className="my-8 p-6 bg-ink rounded-xl shadow-lg">
            <p className="text-lg sm:text-xl font-semibold text-white leading-relaxed text-center">
              {block.content}
            </p>
          </div>
        )

      case 'ul':
        return (
          <ul key={index} className="my-6 space-y-3 pl-2">
            {block.lines?.map((item, i) => (
              <li key={i} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-accent-500 mt-2.5"></span>
                <span 
                  className="text-lg text-secondary-700 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: processInline(item) }}
                />
              </li>
            ))}
          </ul>
        )

      case 'ol':
        return (
          <ol key={index} className="my-6 space-y-4">
            {block.lines?.map((item, i) => (
              <li key={i} className="flex items-start gap-4">
                <span className="flex-shrink-0 w-7 h-7 rounded-full bg-accent-500 text-white font-bold text-sm flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <span 
                  className="text-lg text-secondary-700 leading-relaxed flex-1"
                  dangerouslySetInnerHTML={{ __html: processInline(item) }}
                />
              </li>
            ))}
          </ol>
        )

      case 'hr':
        return (
          <hr key={index} className="my-10 border-none h-px bg-line" />
        )

      case 'paragraph':
      default:
        paragraphCount++
        const shouldInsertImagePara = shouldInsertContentImage(index, blocks)
        
        return (
          <>
            <p 
              key={index} 
              className="text-lg text-secondary-700 leading-relaxed mb-6"
              dangerouslySetInnerHTML={{ __html: processInline(block.content) }}
            />
            {shouldInsertImagePara && contentImageUrl && isValidImageUrl(contentImageUrl) && !insertedImageIndices.includes(index) && (() => {
              insertedImageIndices.push(index)
              return (
                <div key={`${index}-img`} className="my-8">
                  <img
                    src={contentImageUrl}
                    alt=""
                    className="w-full h-auto rounded-xl shadow-lg"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement
                      target.style.display = 'none'
                    }}
                  />
                </div>
              )
            })()}
          </>
        )
    }
  })

  return <>{elements}</>
}

interface TocItem {
  id: string
  title: string
  level: number
}

// Compact, collapsible Table of Contents component
function TocSidebar({ toc, scrollToHeading }: { toc: TocItem[], scrollToHeading: (id: string) => void }) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  return (
    <div className="mb-8 border border-secondary-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 bg-secondary-50 hover:bg-secondary-100 transition-colors flex items-center justify-between text-left"
      >
        <span className="text-sm font-semibold text-secondary-900">Table of Contents</span>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4 text-secondary-500" />
        ) : (
          <ChevronDownIcon className="w-4 h-4 text-secondary-500" />
        )}
      </button>
      {isExpanded && (
        <nav className="px-4 py-3 bg-white space-y-1.5 max-h-96 overflow-y-auto">
          {toc.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                scrollToHeading(item.id)
                setIsExpanded(false)
              }}
              className={`block w-full text-left text-xs hover:text-accent-600 transition-colors py-1 ${
                item.level === 3 ? 'pl-4 text-secondary-600' : 'font-medium text-secondary-700'
              }`}
            >
              {item.title}
            </button>
          ))}
        </nav>
      )}
    </div>
  )
}

// Validate image URL - comprehensive validation for direct image links
function isValidImageUrl(url: string): boolean {
  if (!url || typeof url !== 'string') return false
  
  // Trim and check minimum length
  const trimmed = url.trim()
  if (trimmed.length < 10 || trimmed.length > 2048) return false
  
  // Must start with http:// or https://
  if (!/^https?:\/\//i.test(trimmed)) return false
  
  // Check for invalid characters (spaces, newlines, etc.)
  if (/[\s\n\r\x00]/.test(trimmed)) return false
  
  // Try to parse as URL to validate structure
  try {
    const urlObj = new URL(trimmed)
    
    // Must have valid hostname
    if (!urlObj.hostname || urlObj.hostname.length < 3) return false
    
    // Reject localhost and private IPs
    if (/^(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)/i.test(urlObj.hostname)) return false
    
    // Check path - must look like an image path
    const path = urlObj.pathname.toLowerCase()
    
    // Must have image extension in path (before query params)
    const hasImageExtension = /\.(jpg|jpeg|png|webp|gif|svg)(\?|$|#)/i.test(path)
    
    // Check if it's from a trusted CDN or domain
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
    
    // Reject common non-image URLs and inaccessible domains
    const rejectedPatterns = [
      /serpapi\.com/i,
      /googleusercontent\.com\/imgres/i,
      /\.html/i,
      /\.php/i,
      /\.aspx/i,
      /\/page\//i,
      /\/article\//i,
      /\/news\//i,
      /cdn2\.unrealengine\.com/i, // These URLs return Access Denied
      /epicgames\.com\/[^/]*\.(html|php|aspx)/i, // Epic Games pages, not images
      /\/thumb\//i, // Thumbnail pages
      /\/preview\//i, // Preview pages
      /\?.*format=/i, // Query params suggesting it's a page
    ]
    
    const isRejected = rejectedPatterns.some(pattern => pattern.test(trimmed))
    
    // Check for suspicious patterns in path
    const suspiciousPathPatterns = [
      /\/api\//i,
      /\/embed\//i,
      /\/redirect\//i,
      /\/proxy\//i,
    ]
    
    const hasSuspiciousPath = suspiciousPathPatterns.some(pattern => pattern.test(path))
    
    // Path should contain image-like segments (not just / or /page)
    const hasImageLikePath = path.length > 1 && !/^\/(page|article|news|home|index)/i.test(path)
    
    // Final validation:
    // 1. Must have image extension OR be from trusted domain
    // 2. Must not be rejected
    // 3. Must not have suspicious path
    // 4. Must have image-like path structure
    return (hasImageExtension || isFromTrustedDomain) && 
           !isRejected && 
           !hasSuspiciousPath && 
           hasImageLikePath
  } catch (e) {
    // URL parsing failed - invalid URL
    return false
  }
}

export default function BlogPost() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [post, setPost] = useState<BlogPostType | null>(null)
  const [relatedPosts, setRelatedPosts] = useState<BlogPostListItem[]>([])
  const [categories, setCategories] = useState<BlogCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [readingProgress, setReadingProgress] = useState(0)
  const toast = useToast()
  const [toc, setToc] = useState<TocItem[]>([])
  const articleRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (slug) {
      loadPost(slug)
      loadCategories()
    }
  }, [slug])

  async function loadPost(slug: string) {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchBlogPostBySlug(slug)
      setPost(data)
      
      // Load related posts
      const recent = await fetchRecentBlogPosts(4, data.id)
      setRelatedPosts(recent)
    } catch (err: any) {
      console.error('Failed to load post:', err)
      setError('Post not found')
    } finally {
      setLoading(false)
    }
  }

  async function loadCategories() {
    try {
      const data = await fetchBlogCategories()
      setCategories(data)
    } catch (err) {
      console.error('Failed to load categories:', err)
    }
  }

  function formatDate(dateString?: string) {
    if (!dateString) return ''
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  // Generate table of contents from content
  useEffect(() => {
    if (!post?.content) return
    
    const lines = post.content.split('\n')
    const tocItems: TocItem[] = []
    
    lines.forEach((line) => {
      const trimmed = line.trim()
      if (trimmed.startsWith('## ')) {
        const title = trimmed.slice(3)
        const id = title.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
        tocItems.push({ id, title, level: 2 })
      } else if (trimmed.startsWith('### ')) {
        const title = trimmed.slice(4)
        const id = title.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
        tocItems.push({ id, title, level: 3 })
      }
    })
    
    setToc(tocItems)
  }, [post])

  // Reading progress calculation
  useEffect(() => {
    const handleScroll = () => {
      if (!articleRef.current) return
      
      const articleTop = articleRef.current.offsetTop
      const articleHeight = articleRef.current.offsetHeight
      const windowHeight = window.innerHeight
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop
      
      const scrolled = scrollTop - articleTop + 100 // Account for header offset
      const total = articleHeight - windowHeight + 100
      const progress = Math.min(Math.max((scrolled / total) * 100, 0), 100)
      
      setReadingProgress(progress)
    }
    
    window.addEventListener('scroll', handleScroll)
    handleScroll() // Initial calculation
    
    return () => window.removeEventListener('scroll', handleScroll)
  }, [post])

  function shareToTwitter() {
    if (!post) return
    const url = encodeURIComponent(window.location.href)
    const text = encodeURIComponent(post.title)
    window.open(`https://twitter.com/intent/tweet?url=${url}&text=${text}`, '_blank', 'width=550,height=420')
  }

  function shareToFacebook() {
    if (!post) return
    const url = encodeURIComponent(window.location.href)
    window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, '_blank', 'width=550,height=420')
  }

  function shareToLinkedIn() {
    if (!post) return
    const url = encodeURIComponent(window.location.href)
    window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${url}`, '_blank', 'width=550,height=420')
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href)
      toast.success('Link copied to clipboard!')
    } catch (err) {
      toast.error('Failed to copy link')
    }
  }

  function sharePost() {
    if (navigator.share && post) {
      navigator.share({
        title: post.title,
        text: post.excerpt || post.meta_description || '',
        url: window.location.href,
      })
    } else {
      copyLink()
    }
  }

  function scrollToHeading(id: string) {
    const element = document.getElementById(id)
    if (element) {
      const offset = 100 // Account for fixed header
      const elementPosition = element.getBoundingClientRect().top
      const offsetPosition = elementPosition + window.pageYOffset - offset
      
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      })
    }
  }

  function getTags(): string[] {
    if (!post?.tags) return []
    return post.tags.split(',').map(t => t.trim()).filter(Boolean)
  }

  // Generate JSON-LD structured data for SEO
  function getStructuredData() {
    if (!post) return null
    
    return {
      '@context': 'https://schema.org',
      '@type': post.schema_type || 'Article',
      headline: post.meta_title || post.title,
      description: post.meta_description || post.excerpt,
      image: post.og_image || post.featured_image,
      datePublished: post.published_at,
      dateModified: post.updated_at,
      author: {
        '@type': 'Person',
        name: post.author_name || 'MetaView Team',
      },
      publisher: {
        '@type': 'Organization',
        name: 'MetaView',
        logo: {
          '@type': 'ImageObject',
          url: `${window.location.origin}/logo.png`,
        },
      },
      mainEntityOfPage: {
        '@type': 'WebPage',
        '@id': window.location.href,
      },
    }
  }

  // Update document meta tags for SEO
  useEffect(() => {
    if (!post) return
    
    // Set title
    document.title = `${post.meta_title || post.title} | MetaView Blog`
    
    // Helper to update or create meta tag
    const setMetaTag = (name: string, content: string, property?: boolean) => {
      const attr = property ? 'property' : 'name'
      let meta = document.querySelector(`meta[${attr}="${name}"]`) as HTMLMetaElement
      if (!meta) {
        meta = document.createElement('meta')
        meta.setAttribute(attr, name)
        document.head.appendChild(meta)
      }
      meta.setAttribute('content', content)
    }
    
    // Standard meta
    if (post.meta_description || post.excerpt) {
      setMetaTag('description', post.meta_description || post.excerpt || '')
    }
    if (post.meta_keywords) {
      setMetaTag('keywords', post.meta_keywords)
    }
    if (post.no_index) {
      setMetaTag('robots', 'noindex, nofollow')
    }
    
    // Open Graph
    setMetaTag('og:type', 'article', true)
    setMetaTag('og:title', post.meta_title || post.title, true)
    setMetaTag('og:description', post.meta_description || post.excerpt || '', true)
    setMetaTag('og:url', window.location.href, true)
    if (post.og_image || post.featured_image) {
      setMetaTag('og:image', post.og_image || post.featured_image || '', true)
    }
    if (post.published_at) {
      setMetaTag('article:published_time', post.published_at, true)
    }
    setMetaTag('article:modified_time', post.updated_at, true)
    
    // Twitter Card
    setMetaTag('twitter:card', 'summary_large_image')
    setMetaTag('twitter:title', post.twitter_title || post.meta_title || post.title)
    setMetaTag('twitter:description', post.twitter_description || post.meta_description || post.excerpt || '')
    if (post.twitter_image || post.og_image || post.featured_image) {
      setMetaTag('twitter:image', post.twitter_image || post.og_image || post.featured_image || '')
    }
    
    // Canonical URL
    let canonical = document.querySelector('link[rel="canonical"]') as HTMLLinkElement
    if (!canonical) {
      canonical = document.createElement('link')
      canonical.setAttribute('rel', 'canonical')
      document.head.appendChild(canonical)
    }
    canonical.setAttribute('href', post.canonical_url || window.location.href)
    
    // Structured Data (JSON-LD)
    let script = document.querySelector('script[type="application/ld+json"]#blog-post-schema') as HTMLScriptElement
    if (!script) {
      script = document.createElement('script')
      script.setAttribute('type', 'application/ld+json')
      script.id = 'blog-post-schema'
      document.head.appendChild(script)
    }
    script.textContent = JSON.stringify(getStructuredData())
    
    // Cleanup on unmount
    return () => {
      document.title = 'MetaView'
    }
  }, [post])

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="animate-pulse space-y-8 max-w-3xl w-full px-4">
          <div className="h-8 bg-secondary-200 rounded w-3/4" />
          <div className="h-64 bg-secondary-200 rounded-xl" />
          <div className="space-y-3">
            <div className="h-4 bg-secondary-200 rounded w-full" />
            <div className="h-4 bg-secondary-200 rounded w-5/6" />
            <div className="h-4 bg-secondary-200 rounded w-4/5" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !post) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-secondary-900 mb-4">404</h1>
          <p className="text-secondary-500 mb-8">Post not found</p>
          <Link
            to="/blog"
            className="text-accent-600 font-semibold hover:text-accent-700"
          >
            ← Back to Blog
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
        {/* Reading Progress Bar */}
        <div className="fixed top-0 left-0 right-0 z-[60] h-1 bg-secondary-100">
          <div
            className="h-full bg-accent-500 transition-all duration-150"
            style={{ width: `${readingProgress}%` }}
          />
        </div>

        {/* Navigation */}
        <nav className="fixed top-1 left-0 right-0 z-50 bg-white/90  border-b border-secondary-100/80">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
            <div className="flex items-center justify-between h-16">
              <Link to="/" className="flex items-center space-x-2.5 group">
                <div className="w-9 h-9 bg-primary-500 rounded-xl flex items-center justify-center shadow-lg shadow-accent-500/25 group-hover:scale-110 transition-transform">
                  <span className="text-white font-black text-base">M</span>
                </div>
                <span className="text-lg font-black text-secondary-900">MetaView</span>
              </Link>
              <div className="hidden md:flex items-center space-x-8">
                <Link to="/" className="text-secondary-600 hover:text-secondary-900 font-semibold text-sm">Home</Link>
                <Link to="/blog" className="text-accent-600 font-semibold text-sm">Blog</Link>
                <Link to="/#pricing" className="text-secondary-600 hover:text-secondary-900 font-semibold text-sm">Pricing</Link>
              </div>
              <Link
                to="/app"
                className="px-5 py-2.5 bg-accent-500 text-white rounded-xl font-bold text-sm hover:shadow-lg transition-all"
              >
                Get Started
              </Link>
            </div>
          </div>
        </nav>

        {/* Breadcrumb */}
        <div className="pt-24 bg-secondary-50 border-b border-secondary-100">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4">
            <nav className="flex items-center space-x-2 text-sm">
              <Link to="/" className="text-secondary-500 hover:text-secondary-700">Home</Link>
              <ChevronRightIcon className="w-4 h-4 text-secondary-400" />
              <Link to="/blog" className="text-secondary-500 hover:text-secondary-700">Blog</Link>
              {post.category && (
                <>
                  <ChevronRightIcon className="w-4 h-4 text-secondary-400" />
                  <Link
                    to={`/blog?category=${post.category.slug}`}
                    className="text-secondary-500 hover:text-secondary-700"
                  >
                    {post.category.name}
                  </Link>
                </>
              )}
              <ChevronRightIcon className="w-4 h-4 text-secondary-400" />
              <span className="text-secondary-900 font-medium truncate max-w-[200px]">{post.title}</span>
            </nav>
          </div>
        </div>

        {/* Article Header */}
        <header className="py-12 px-4 sm:px-6">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center gap-3 mb-6 flex-wrap">
              {post.category && (
                <Link
                  to={`/blog?category=${post.category.slug}`}
                  className="px-3 py-1 rounded-full text-sm font-semibold text-white hover:opacity-90 transition-opacity"
                  style={{ backgroundColor: post.category.color }}
                >
                  {post.category.name}
                </Link>
              )}
              {post.read_time_minutes && (
                <span className="flex items-center gap-1.5 text-sm text-secondary-500">
                  <ClockIcon className="w-4 h-4" />
                  {post.read_time_minutes} min read
                </span>
              )}
              <span className="flex items-center gap-1.5 text-sm text-secondary-500">
                <EyeIcon className="w-4 h-4" />
                {post.views_count.toLocaleString()} views
              </span>
            </div>
            
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-secondary-900 leading-tight mb-6">
              {post.title}
            </h1>
            
            {post.excerpt && (
              <p className="text-xl text-secondary-600 leading-relaxed mb-8">
                {post.excerpt}
              </p>
            )}
            
            <div className="flex items-center justify-between flex-wrap gap-4 pb-8 border-b border-secondary-100">
              <div className="flex items-center gap-4">
                {post.author_avatar ? (
                  <img
                    src={post.author_avatar}
                    alt={post.author_name || 'Author'}
                    className="w-12 h-12 rounded-full object-cover ring-2 ring-white shadow-lg"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-full bg-brand-100 ring-2 ring-white shadow-lg" />
                )}
                <div>
                  <div className="font-semibold text-secondary-900">
                    {post.author_name || 'MetaView Team'}
                  </div>
                  <div className="text-sm text-secondary-500 flex items-center gap-2">
                    <CalendarIcon className="w-4 h-4" />
                    {formatDate(post.published_at)}
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Social Sharing Buttons */}
                <button
                  onClick={shareToTwitter}
                  className="p-2.5 rounded-xl border border-secondary-200 text-secondary-600 hover:bg-primary-50 hover:text-primary-600 hover:border-primary-200 transition-colors"
                  aria-label="Share on Twitter"
                  title="Share on Twitter"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                  </svg>
                </button>
                <button
                  onClick={shareToFacebook}
                  className="p-2.5 rounded-xl border border-secondary-200 text-secondary-600 hover:bg-primary-50 hover:text-primary-600 hover:border-primary-200 transition-colors"
                  aria-label="Share on Facebook"
                  title="Share on Facebook"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                </button>
                <button
                  onClick={shareToLinkedIn}
                  className="p-2.5 rounded-xl border border-secondary-200 text-secondary-600 hover:bg-primary-50 hover:text-primary-600 hover:border-primary-200 transition-colors"
                  aria-label="Share on LinkedIn"
                  title="Share on LinkedIn"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                  </svg>
                </button>
                <button
                  onClick={copyLink}
                  className="p-2.5 rounded-xl border border-secondary-200 text-secondary-600 hover:bg-secondary-50 hover:text-secondary-900 transition-colors"
                  aria-label="Copy Link"
                  title="Copy Link"
                >
                  <LinkIcon className="w-5 h-5" />
                </button>
                {'share' in navigator && (
                  <button
                    onClick={sharePost}
                    className="p-2.5 rounded-xl border border-secondary-200 text-secondary-600 hover:bg-secondary-50 hover:text-secondary-900 transition-colors"
                    aria-label="Share"
                    title="Share"
                  >
                    <ShareIcon className="w-5 h-5" />
                  </button>
                )}
                <button
                  className="p-2.5 rounded-xl border border-secondary-200 text-secondary-600 hover:bg-secondary-50 hover:text-secondary-900 transition-colors"
                  aria-label="Bookmark"
                  title="Bookmark"
                >
                  <BookmarkIcon className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Featured Image */}
        {post.featured_image && isValidImageUrl(post.featured_image) && (
          <div className="px-4 sm:px-6 mb-12">
            <div className="max-w-5xl mx-auto">
              <img
                src={post.featured_image}
                alt={post.featured_image_alt || post.title}
                className="w-full h-auto rounded-2xl shadow-xl"
                onError={(e) => {
                  // Hide broken images
                  const target = e.target as HTMLImageElement
                  target.style.display = 'none'
                }}
              />
            </div>
          </div>
        )}

        {/* Article Content */}
        <article className="px-4 sm:px-6 pb-16">
          <div className="max-w-3xl mx-auto">
            {/* Table of Contents */}
            {toc.length > 0 && (
              <TocSidebar toc={toc} scrollToHeading={scrollToHeading} />
            )}
            
            <div className="article-body prose prose-lg prose-orange max-w-none" ref={articleRef} style={{
              fontSize: '1.125rem',
              lineHeight: '1.75rem',
            }}>
              {renderContent(post.content, post.featured_image, (post as any).contentImageUrl || (post as any).blogContentImage)}
            </div>
            
            {/* Tags */}
            {getTags().length > 0 && (
              <div className="mt-12 pt-8 border-t border-secondary-100">
                <div className="flex items-center gap-2 flex-wrap">
                  <TagIcon className="w-5 h-5 text-secondary-400" />
                  {getTags().map((tag) => (
                    <Link
                      key={tag}
                      to={`/blog?tag=${encodeURIComponent(tag)}`}
                      className="px-3 py-1 bg-secondary-100 text-secondary-600 rounded-full text-sm font-medium hover:bg-secondary-200 transition-colors"
                    >
                      {tag}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Author Bio */}
            {post.author_bio && (
              <div className="mt-12 p-6 bg-secondary-50 rounded-2xl">
                <div className="flex items-start gap-4">
                  {post.author_avatar ? (
                    <img
                      src={post.author_avatar}
                      alt={post.author_name || 'Author'}
                      className="w-16 h-16 rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-full bg-brand-100" />
                  )}
                  <div>
                    <div className="font-bold text-secondary-900 mb-1">
                      About {post.author_name || 'the Author'}
                    </div>
                    <p className="text-secondary-600">{post.author_bio}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </article>

        {/* Related Posts */}
        {relatedPosts.length > 0 && (
          <section className="py-16 px-4 sm:px-6 bg-secondary-50">
            <div className="max-w-7xl mx-auto">
              <h2 className="text-2xl font-bold text-secondary-900 mb-8">Continue Reading</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {relatedPosts.map((relatedPost) => (
                  <Link
                    key={relatedPost.id}
                    to={`/blog/${relatedPost.slug}`}
                    className="group bg-white rounded-xl border border-secondary-200 overflow-hidden hover:shadow-lg hover:-translate-y-1 transition-all"
                  >
                    {relatedPost.featured_image ? (
                      <div className="h-32 overflow-hidden">
                        <img
                          src={relatedPost.featured_image}
                          alt={relatedPost.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        />
                      </div>
                    ) : (
                      <div className="h-32 bg-brand-100 flex items-center justify-center">
                        <SparklesIcon className="w-8 h-8 text-accent-300" />
                      </div>
                    )}
                    <div className="p-4">
                      <h3 className="font-semibold text-secondary-900 group-hover:text-accent-600 transition-colors line-clamp-2 mb-2">
                        {relatedPost.title}
                      </h3>
                      <span className="text-xs text-secondary-500">
                        {formatDate(relatedPost.published_at)}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* CTA Section */}
        <section className="py-16 px-4 sm:px-6 bg-primary-500">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to boost your CTR?</h2>
            <p className="text-accent-100 mb-8">
              Start creating beautiful, high-converting URL previews today with MetaView.
            </p>
            <Link
              to="/app"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white text-accent-600 rounded-xl font-bold hover:bg-accent-50 transition-colors"
            >
              Start Free Trial
              <ChevronRightIcon className="w-5 h-5" />
            </Link>
          </div>
        </section>

        {/* Footer */}
        <footer className="bg-secondary-900 text-white py-12 px-4 sm:px-6">
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
              </div>
              <span className="text-sm text-secondary-500">© 2024 MetaView. All rights reserved.</span>
            </div>
          </div>
        </footer>
      </div>
  )
}


