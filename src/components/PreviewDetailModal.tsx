/**
 * Preview detail: how one preview actually looks where it matters.
 *
 * Platform-accurate mockups (Facebook, X, LinkedIn, Slack), the exact meta
 * tags being served, per-size card exports, and the actions you reach for
 * with a finished card: copy, download, open.
 */
import { useEffect, useMemo, useState } from 'react'
import {
  ArrowDownTrayIcon,
  ArrowTopRightOnSquareIcon,
  ClipboardIcon,
  CheckIcon,
} from '@heroicons/react/24/outline'
import Modal from './ui/Modal'
import Button from './ui/Button'
import PlatformPreviewCard from './PlatformPreviewCard'
import { buildPlatformCards } from '../api/client'
import type { Preview, PreviewVariant, PlatformCard } from '../api/types'
import type { DemoPreviewResponseV2 } from '../api/client'

const PLATFORMS = [
  { id: 'facebook', name: 'Facebook', color: '#1877F2', icon: '', aspectRatio: '1.91:1', maxTitleLength: 88, maxDescLength: 110 },
  { id: 'twitter', name: 'X', color: '#0F1419', icon: '', aspectRatio: '1.91:1', maxTitleLength: 70, maxDescLength: 125 },
  { id: 'linkedin', name: 'LinkedIn', color: '#0A66C2', icon: '', aspectRatio: '1.91:1', maxTitleLength: 96, maxDescLength: 0 },
  { id: 'slack', name: 'Slack', color: '#4A154B', icon: '', aspectRatio: 'flexible', maxTitleLength: 120, maxDescLength: 160 },
]

interface PreviewDetailModalProps {
  preview: Preview | null
  variant: PreviewVariant | null
  isOpen: boolean
  onClose: () => void
}

export default function PreviewDetailModal({ preview, variant, isOpen, onClose }: PreviewDetailModalProps) {
  const [platform, setPlatform] = useState('facebook')
  const [copied, setCopied] = useState<string | null>(null)
  const [sizes, setSizes] = useState<PlatformCard[] | null>(null)
  const [sizesLoading, setSizesLoading] = useState(false)
  const [sizesError, setSizesError] = useState<string | null>(null)

  // Reset transient state whenever a different preview opens.
  useEffect(() => {
    setPlatform('facebook')
    setCopied(null)
    setSizes(null)
    setSizesError(null)
  }, [preview?.id, isOpen])

  const title = variant?.title || preview?.title || ''
  const description = variant?.description || preview?.description || ''
  // image_url carries the composited card; highlight is the raw screenshot.
  const imageUrl = (variant?.image_url || preview?.image_url || preview?.highlight_image_url) ?? null

  // Adapt the stored preview into the shape the platform mockups render.
  const mockPreview = useMemo(() => {
    if (!preview) return null
    return {
      url: preview.url,
      title,
      description,
      composited_preview_image_url: imageUrl,
      screenshot_url: null,
    } as unknown as DemoPreviewResponseV2
  }, [preview, title, description, imageUrl])

  const metaTags = useMemo(() => {
    if (!preview) return ''
    const esc = (v: string) => v.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
    const lines = [
      `<meta property="og:url" content="${esc(preview.url)}" />`,
      `<meta property="og:title" content="${esc(title)}" />`,
    ]
    if (description) lines.push(`<meta property="og:description" content="${esc(description)}" />`)
    if (imageUrl) lines.push(`<meta property="og:image" content="${esc(imageUrl)}" />`)
    lines.push('<meta name="twitter:card" content="summary_large_image" />')
    if (imageUrl) lines.push(`<meta name="twitter:image" content="${esc(imageUrl)}" />`)
    return lines.join('\n')
  }, [preview, title, description, imageUrl])

  const copy = async (what: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(what)
      setTimeout(() => setCopied(null), 1600)
    } catch {
      // Clipboard unavailable — the user can still select the text manually.
    }
  }

  const download = (url: string, filename: string) => {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.target = '_blank'
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const loadSizes = async () => {
    if (!preview) return
    setSizesLoading(true)
    setSizesError(null)
    try {
      const res = await buildPlatformCards(preview.id)
      setSizes(res.cards)
      if (res.missing.length > 0 && res.cards.length === 0) {
        setSizesError('These sizes could not be rendered for this card.')
      }
    } catch (err) {
      setSizesError(err instanceof Error ? err.message : 'Could not build platform sizes.')
    } finally {
      setSizesLoading(false)
    }
  }

  if (!preview || !mockPreview) return null

  const slug = (() => {
    try {
      return new URL(preview.url).hostname.replace(/^www\./, '').replace(/\./g, '-')
    } catch {
      return `preview-${preview.id}`
    }
  })()

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="How this preview looks" size="lg">
      <div className="space-y-5">
        {/* Platform switcher */}
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((p) => (
            <button
              key={p.id}
              onClick={() => setPlatform(p.id)}
              className={`px-3 py-1.5 rounded-lg text-[13px] font-medium border transition-colors ${
                platform === p.id
                  ? 'bg-secondary-900 text-paper border-secondary-900'
                  : 'bg-surface text-secondary-600 border-line hover:border-secondary-400'
              }`}
            >
              {p.name}
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-line bg-secondary-50 p-4 sm:p-6">
          <PlatformPreviewCard
            preview={mockPreview}
            platform={PLATFORMS.find((p) => p.id === platform) || PLATFORMS[0]}
          />
        </div>

        {/* Primary actions */}
        <div className="flex flex-wrap gap-2">
          {imageUrl && (
            <>
              <Button variant="secondary" size="sm" onClick={() => copy('image', imageUrl)}>
                {copied === 'image' ? <CheckIcon className="w-4 h-4 mr-1.5" /> : <ClipboardIcon className="w-4 h-4 mr-1.5" />}
                Copy image URL
              </Button>
              <Button variant="secondary" size="sm" onClick={() => download(imageUrl, `${slug}-preview.png`)}>
                <ArrowDownTrayIcon className="w-4 h-4 mr-1.5" />
                Download PNG
              </Button>
            </>
          )}
          <Button variant="secondary" size="sm" onClick={() => window.open(preview.url, '_blank', 'noopener')}>
            <ArrowTopRightOnSquareIcon className="w-4 h-4 mr-1.5" />
            Open page
          </Button>
        </div>

        {/* Meta tags being served */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-secondary-900">Meta tags served for this page</h4>
            <button
              onClick={() => copy('meta', metaTags)}
              className="text-[12px] font-medium text-primary-600 hover:text-primary-700 inline-flex items-center gap-1"
            >
              {copied === 'meta' ? <CheckIcon className="w-3.5 h-3.5" /> : <ClipboardIcon className="w-3.5 h-3.5" />}
              Copy
            </button>
          </div>
          <pre className="text-[11px] leading-relaxed font-mono bg-secondary-900 text-secondary-100 rounded-lg p-3 overflow-x-auto">
            {metaTags}
          </pre>
          <p className="text-[12px] text-secondary-500 mt-2">
            Served automatically wherever your install (snippet, Worker, or WordPress plugin) is live —
            or paste them into the page's <code className="font-mono">&lt;head&gt;</code> yourself.
          </p>
        </div>

        {/* Per-platform sizes */}
        {preview.can_rerender && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-secondary-900">Export sizes</h4>
              {!sizes && (
                <Button variant="secondary" size="sm" onClick={loadSizes} loading={sizesLoading}>
                  Build square & portrait
                </Button>
              )}
            </div>
            {sizesError && <p className="text-[12px] text-error-600">{sizesError}</p>}
            {!sizes && !sizesError && (
              <p className="text-[12px] text-secondary-500">
                The wide card serves link previews everywhere. Square (1080×1080) and portrait
                (1080×1350) are composed fresh for feed posts — free, no AI credit used.
              </p>
            )}
            {sizes && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {sizes.map((card) => (
                  <div key={card.size} className="border border-line rounded-lg overflow-hidden">
                    <img src={card.image_url} alt={`${card.size} card`} className="w-full" loading="lazy" />
                    <div className="flex items-center justify-between px-2.5 py-2">
                      <span className="text-[12px] text-secondary-600 capitalize">
                        {card.size} · {card.width}×{card.height}
                      </span>
                      <button
                        onClick={() => download(card.image_url, `${slug}-${card.size}.png`)}
                        className="text-primary-600 hover:text-primary-700"
                        title="Download"
                      >
                        <ArrowDownTrayIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
