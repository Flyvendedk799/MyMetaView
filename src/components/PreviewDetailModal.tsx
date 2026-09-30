/**
 * Preview detail: how one preview actually looks where it matters.
 *
 * Studio is the spatial view. "Where it appears" is the real title, description,
 * and image inside Facebook, X, LinkedIn, and Slack chrome. "Tags & files" is
 * the markup being served plus per-size card downloads.
 */
import { useState } from 'react'
import Modal from './ui/Modal'
import Button from './ui/Button'
import SpatialPreviewStudio from './SpatialPreviewStudio'
import { buildPlatformCards } from '../api/client'
import type {
  CardAccent,
  CardLayout,
  CardPanel,
  PlatformCard,
  Preview,
  PreviewRestyleRequest,
  PreviewVariant,
} from '../api/types'

interface PreviewDetailModalProps {
  preview: Preview | null
  variant: PreviewVariant | null
  isOpen: boolean
  onClose: () => void
  onRestyle?: (direction: PreviewRestyleRequest) => Promise<void>
  onSaveCopy?: (patch: { title: string; description: string }) => Promise<void>
}

type Panel = 'studio' | 'platforms' | 'files'

const LAYOUTS: CardLayout[] = ['typographic', 'split', 'stat', 'profile', 'editorial', 'product']
const PANELS: CardPanel[] = ['primary', 'secondary', 'dark', 'light']
const ACCENTS: CardAccent[] = ['bar', 'dot', 'shape']

function escapeAttr(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
}

function metaMarkup(title: string, description: string, image: string, url: string, site: string): string {
  const rows = [
    ['og:title', title],
    ['og:description', description],
    ['og:image', image],
    ['og:url', url],
    ['og:type', 'website'],
    ['og:site_name', site],
  ]
  const og = rows
    .filter(([, content]) => content)
    .map(([property, content]) => `<meta property="${property}" content="${escapeAttr(content)}" />`)
  const twitter = [
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${escapeAttr(title)}" />`,
    description ? `<meta name="twitter:description" content="${escapeAttr(description)}" />` : '',
    image ? `<meta name="twitter:image" content="${escapeAttr(image)}" />` : '',
  ].filter(Boolean)
  return [...og, ...twitter].join('\n')
}

function PlatformMock({
  name,
  title,
  description,
  image,
  domain,
  chrome,
}: {
  name: string
  title: string
  description: string
  image: string
  domain: string
  chrome: string
}) {
  return (
    <div className="rounded-xl border border-secondary-200 overflow-hidden bg-white">
      <div className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-secondary-500 border-b border-secondary-100">
        {name}
      </div>
      <div className={chrome}>
        {image ? (
          <img src={image} alt="" className="w-full aspect-[1.91/1] object-cover bg-secondary-100" />
        ) : (
          <div className="w-full aspect-[1.91/1] bg-secondary-100" />
        )}
        <div className="p-3">
          <p className="text-[11px] uppercase tracking-wide text-secondary-400 truncate">{domain}</p>
          <p className="text-sm font-semibold text-secondary-900 line-clamp-2 mt-0.5">{title || 'Untitled'}</p>
          {description && (
            <p className="text-xs text-secondary-600 line-clamp-2 mt-1">{description}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function PreviewDetailModal({
  preview,
  variant,
  isOpen,
  onClose,
  onRestyle,
  onSaveCopy,
}: PreviewDetailModalProps) {
  const [panel, setPanel] = useState<Panel>('platforms')
  const [copied, setCopied] = useState(false)
  const [cards, setCards] = useState<PlatformCard[] | null>(null)
  const [cardsError, setCardsError] = useState<string | null>(null)
  const [rendering, setRendering] = useState(false)
  const [layout, setLayout] = useState<CardLayout>('typographic')
  const [panelColor, setPanelColor] = useState<CardPanel>('primary')
  const [accent, setAccent] = useState<CardAccent>('bar')
  const [saving, setSaving] = useState(false)

  if (!preview) return null

  const title = variant?.title || preview.title
  const description = variant?.description || preview.description || ''
  const image = variant?.image_url || preview.image_url || preview.highlight_image_url || ''
  const studioPreview = {
    ...preview,
    title,
    description,
    composited_preview_image_url: image,
    layout: preview.layout,
  }
  const markup = metaMarkup(title, description, image, preview.url, preview.domain)

  const copyTags = async () => {
    await navigator.clipboard.writeText(markup)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  const renderSizes = async () => {
    setRendering(true)
    setCardsError(null)
    try {
      const res = await buildPlatformCards(preview.id)
      setCards(res.cards)
      if (res.missing?.length) {
        setCardsError(`Could not render: ${res.missing.join(', ')}`)
      }
    } catch (err) {
      setCardsError(err instanceof Error ? err.message : 'Could not render sizes')
    } finally {
      setRendering(false)
    }
  }

  const applyRestyle = async () => {
    if (!onRestyle) return
    setSaving(true)
    try {
      await onRestyle({ layout, panel: panelColor, accent })
    } finally {
      setSaving(false)
    }
  }

  const saveCopy = async (patch: { title: string; description: string }) => {
    if (!onSaveCopy) return
    setSaving(true)
    try {
      await onSaveCopy(patch)
    } finally {
      setSaving(false)
    }
  }

  const tabs: { id: Panel; label: string }[] = [
    { id: 'platforms', label: 'Where it appears' },
    { id: 'files', label: 'Tags & files' },
    { id: 'studio', label: 'Studio' },
  ]

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title || 'Preview'} size="full">
      <div className="flex flex-col gap-4 min-h-[70vh]">
        <div className="flex gap-1 p-1 bg-secondary-100 rounded-lg w-fit" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={panel === tab.id}
              onClick={() => setPanel(tab.id)}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                panel === tab.id ? 'bg-white text-secondary-900 shadow-sm' : 'text-secondary-600 hover:text-secondary-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {panel === 'platforms' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <PlatformMock name="Facebook" title={title} description={description} image={image} domain={preview.domain} chrome="bg-[#f0f2f5]" />
            <PlatformMock name="X" title={title} description={description} image={image} domain={preview.domain} chrome="bg-white" />
            <PlatformMock name="LinkedIn" title={title} description={description} image={image} domain={preview.domain} chrome="bg-[#f3f2ef]" />
            <PlatformMock name="Slack" title={title} description={description} image={image} domain={preview.domain} chrome="bg-white" />
          </div>
        )}

        {panel === 'files' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-secondary-600">
                These are the tags a crawler receives for this URL.
              </p>
              <Button variant="secondary" onClick={copyTags}>
                {copied ? 'Copied' : 'Copy tags'}
              </Button>
            </div>
            <pre className="text-xs bg-secondary-900 text-paper rounded-xl p-4 overflow-x-auto whitespace-pre-wrap">{markup}</pre>
            <div className="flex flex-wrap items-center gap-3">
              <a href={preview.url} target="_blank" rel="noreferrer" className="text-sm text-primary-600 hover:underline">
                Open live URL
              </a>
              {image && (
                <a href={image} download className="text-sm text-primary-600 hover:underline">
                  Download wide card
                </a>
              )}
              <Button onClick={renderSizes} disabled={rendering || !preview.can_rerender}>
                {rendering ? 'Rendering…' : 'Render platform sizes'}
              </Button>
            </div>
            {!preview.can_rerender && (
              <p className="text-xs text-secondary-500">
                Regenerate this preview once to enable per-size renders.
              </p>
            )}
            {cardsError && <p className="text-sm text-error-600">{cardsError}</p>}
            {cards && cards.length > 0 && (
              <ul className="space-y-2">
                {cards.map((card) => (
                  <li key={card.size} className="flex items-center justify-between gap-3 text-sm">
                    <span className="capitalize text-secondary-800">
                      {card.size} · {card.width}×{card.height}
                    </span>
                    <a href={card.image_url} download className="text-primary-600 hover:underline">
                      Download
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {panel === 'studio' && (
          <div className="h-[75vh] -mx-6 -mb-6 overflow-hidden bg-[#09090b]">
            <SpatialPreviewStudio
              preview={studioPreview}
              saving={saving}
              onRestyle={preview.can_rerender ? applyRestyle : undefined}
              onSaveCopy={saveCopy}
              layouts={LAYOUTS}
              panels={PANELS}
              accents={ACCENTS}
              layout={layout}
              panelColor={panelColor}
              accent={accent}
              onLayout={(value) => setLayout(value as CardLayout)}
              onPanelColor={(value) => setPanelColor(value as CardPanel)}
              onAccent={(value) => setAccent(value as CardAccent)}
            />
          </div>
        )}
      </div>
    </Modal>
  )
}
