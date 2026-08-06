import { useEffect } from 'react'

const SITE_URL = 'https://mymetaview.com'
const SITE_NAME = 'MetaView'
const DEFAULT_TITLE = 'MetaView — AI-Powered URL Previews, On Brand'
const DEFAULT_DESCRIPTION =
  'MetaView writes the metadata your pages are missing — starting with the share image. ' +
  'Connect a domain and every link you post arrives with a title, description, and a generated og:image that matches your brand.'
const DEFAULT_IMAGE = `${SITE_URL}/og-image.png`

interface SeoProps {
  /** Page title. Rendered as "<title> — MetaView" unless it already mentions the brand. */
  title?: string
  description?: string
  /** Path for the canonical URL, e.g. "/demo". Defaults to the current path. */
  path?: string
  /** Absolute URL of the share image. */
  image?: string
  /** og:type — "website" for pages, "article" for blog posts. */
  type?: 'website' | 'article'
  /** Set on private/app routes so crawlers skip them. */
  noindex?: boolean
}

function setMeta(attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function setCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

/**
 * Per-route SEO. Renders nothing; keeps document head in sync with the route.
 * The static defaults live in index.html — this component overrides them on
 * navigation and restores nothing on unmount (the next page's Seo takes over).
 */
export default function Seo({
  title,
  description = DEFAULT_DESCRIPTION,
  path,
  image = DEFAULT_IMAGE,
  type = 'website',
  noindex = false,
}: SeoProps) {
  useEffect(() => {
    const fullTitle = title
      ? title.includes(SITE_NAME) ? title : `${title} — ${SITE_NAME}`
      : DEFAULT_TITLE
    const url = `${SITE_URL}${path ?? window.location.pathname}`

    document.title = fullTitle
    setMeta('name', 'description', description)
    setMeta('name', 'robots', noindex ? 'noindex, nofollow' : 'index, follow, max-image-preview:large')
    setCanonical(url)

    setMeta('property', 'og:type', type)
    setMeta('property', 'og:site_name', SITE_NAME)
    setMeta('property', 'og:url', url)
    setMeta('property', 'og:title', fullTitle)
    setMeta('property', 'og:description', description)
    setMeta('property', 'og:image', image)

    setMeta('name', 'twitter:card', 'summary_large_image')
    setMeta('name', 'twitter:title', fullTitle)
    setMeta('name', 'twitter:description', description)
    setMeta('name', 'twitter:image', image)
  }, [title, description, path, image, type, noindex])

  return null
}
