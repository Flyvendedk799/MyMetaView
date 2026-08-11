import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PlusIcon, PencilIcon, TrashIcon, PhotoIcon, RectangleStackIcon, ArrowPathIcon, CheckIcon, XMarkIcon, SwatchIcon, EyeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import Alert from '../components/ui/Alert'
import { SkeletonGrid } from '../components/ui/Skeleton'
import PreviewDetailModal from '../components/PreviewDetailModal'
import { useToast } from '../components/ui/Toast'
import { usePreviews } from '../hooks/usePreviews'
import { useDomains } from '../hooks/useDomains'
import {
  fetchPreviewVariants,
  updatePreviewVariant,
  discoverSitemapUrls,
  createBulkPreviewJob,
  getBulkJobStatus,
  getRecentBulkJobs,
  createPreviewJob,
  restylePreview,
} from '../api/client'
import type {
  Preview,
  PreviewCreate,
  PreviewUpdate,
  PreviewVariant,
  BulkJobStatus,
  BulkJobSummary,
  PreviewRestyleRequest,
  CardLayout,
  CardPanel,
  CardAccent,
} from '../api/types'

const filters = ['All', 'Product', 'Blog', 'Landing Page'] as const
type FilterType = typeof filters[number]

/** What each variant tab is arguing. Keyed to PreviewVariant['angle']. */
const ANGLE_LABEL: Record<string, string> = {
  main: 'Main',
  benefit: 'Benefit',
  proof: 'Proof',
  curiosity: 'Curiosity',
  alternate: 'Alt',
}

const ANGLE_HELP: Record<string, string> = {
  main: 'The primary card',
  benefit: 'Leads with what the visitor gets',
  proof: 'Leads with who already trusts it',
  curiosity: 'Leads with the question the page answers',
  alternate: 'An alternative hook',
}

/** Layouts a user can switch a card to, with plain-language names. */
const LAYOUT_CHOICES: { value: CardLayout; label: string; hint: string }[] = [
  { value: 'typographic', label: 'Headline', hint: 'Type only, no imagery' },
  { value: 'split', label: 'Split', hint: 'Headline beside the hero image' },
  { value: 'stat', label: 'Stat', hint: 'Your proof number as the hero' },
  { value: 'editorial', label: 'Editorial', hint: 'Kicker, rule and deck' },
  { value: 'product', label: 'Product', hint: 'Product shot with a price chip' },
  { value: 'profile', label: 'Profile', hint: 'Avatar beside a name' },
]

const PANEL_CHOICES: { value: CardPanel; label: string }[] = [
  { value: 'primary', label: 'Brand' },
  { value: 'secondary', label: 'Secondary' },
  { value: 'dark', label: 'Dark' },
  { value: 'light', label: 'Light' },
]

const ACCENT_CHOICES: { value: CardAccent; label: string; hint: string }[] = [
  { value: 'bar', label: 'Bar', hint: 'A small accent bar under the headline' },
  { value: 'shape', label: 'Shape', hint: 'A soft corner shape in the accent color' },
  { value: 'dot', label: 'Dot', hint: 'A small accent dot' },
]

// Map filter display names to backend type values
const filterToTypeMap: Record<string, string | undefined> = {
  'All': undefined,
  'Product': 'product',
  'Blog': 'blog',
  'Landing Page': 'landing',
}

// Compact relative timestamp for generation-activity rows. created_at is UTC ISO.
function relativeTime(iso: string | null): string {
  if (!iso) return ''
  const then = Date.parse(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  if (Number.isNaN(then)) return ''
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (secs < 45) return 'just now'
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.round(hrs / 24)
  return `${days}d ago`
}

export default function Previews() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('All')
  const [searchParams, setSearchParams] = useSearchParams()
  const filterType = filterToTypeMap[activeFilter]
  const { previews, loading, error, createOrUpdatePreview, updatePreview, deletePreview, replacePreview, refetch } = usePreviews(filterType)
  const { domains } = useDomains()
  const toast = useToast()
  // ?q= from the header search — filters by title, URL, or domain.
  const searchQuery = (searchParams.get('q') || '').trim().toLowerCase()
  const visiblePreviews = useMemo(() => {
    if (!searchQuery) return previews
    return previews.filter((p) =>
      [p.title, p.url, p.domain, p.description || '']
        .some((field) => (field || '').toLowerCase().includes(searchQuery))
    )
  }, [previews, searchQuery])
  const clearSearch = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('q')
    setSearchParams(next, { replace: true })
  }
  // Detail modal — platform mockups, meta tags, downloads.
  const [detailPreview, setDetailPreview] = useState<Preview | null>(null)
  const verifiedDomains = useMemo(() => domains.filter((d) => d.status === 'verified'), [domains])

  // Bulk "cover your site" generation
  const [isBulkOpen, setIsBulkOpen] = useState(false)
  const [bulkDomain, setBulkDomain] = useState('')
  const [bulkUrlText, setBulkUrlText] = useState('')
  const [bulkLoadingSitemap, setBulkLoadingSitemap] = useState(false)
  const [bulkSitemapNote, setBulkSitemapNote] = useState<string | null>(null)
  const [bulkError, setBulkError] = useState<string | null>(null)
  const [bulkStarting, setBulkStarting] = useState(false)
  const bulkUrls = useMemo(
    () => bulkUrlText.split('\n').map((l) => l.trim()).filter(Boolean),
    [bulkUrlText]
  )

  // Per-card regeneration — keyed by the run it started, so the spinner clears
  // when the server says that run is done (no client-side timeout to guess with).
  const [regeneratingIds, setRegeneratingIds] = useState<Record<number, string>>({})
  // Restyle is synchronous, so this is a plain in-flight flag rather than a
  // background-run id like regeneratingIds.
  const [restylingIds, setRestylingIds] = useState<Record<number, boolean>>({})
  const [openRestyleFor, setOpenRestyleFor] = useState<number | null>(null)
  const [regenError, setRegenError] = useState<string | null>(null)

  // Generation activity — every run (single + bulk), visible and resumable even
  // after the tab that started it is closed. The work happens on the server.
  const [activityBatches, setActivityBatches] = useState<BulkJobSummary[]>([])
  const activityPrevStatus = useRef<Record<string, string>>({})

  const loadActivity = useCallback(async () => {
    try {
      const res = await getRecentBulkJobs()
      const batches = res.batches || []
      // Refetch previews when a run has just finished so new cards appear.
      let justFinished = false
      for (const b of batches) {
        const prev = activityPrevStatus.current[b.batch_id]
        if (prev && (prev === 'queued' || prev === 'running') && (b.status === 'completed' || b.status === 'failed')) {
          justFinished = true
        }
        activityPrevStatus.current[b.batch_id] = b.status
      }
      setActivityBatches(batches)
      // Release any card whose regeneration run has landed (or fallen off the list).
      setRegeneratingIds((prev) => {
        const next: Record<number, string> = {}
        let changed = false
        for (const [id, batchId] of Object.entries(prev)) {
          const run = batches.find((b) => b.batch_id === batchId)
          if (run && (run.status === 'queued' || run.status === 'running')) next[Number(id)] = batchId
          else changed = true
        }
        return changed ? next : prev
      })
      if (justFinished) {
        refetch(filterType)
      }
    } catch {
      // transient — keep whatever we had
    }
  }, [refetch, filterType])

  const hasActiveBatch = useMemo(
    () => activityBatches.some((b) => b.status === 'queued' || b.status === 'running'),
    [activityBatches]
  )

  // Per-URL detail for one run, on demand (which pages landed, which failed).
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null)
  const [batchDetail, setBatchDetail] = useState<BulkJobStatus | null>(null)
  const [batchDetailError, setBatchDetailError] = useState<string | null>(null)

  useEffect(() => {
    if (!expandedBatch) {
      setBatchDetail(null)
      setBatchDetailError(null)
      return
    }
    let active = true
    getBulkJobStatus(expandedBatch)
      .then((detail) => {
        if (!active) return
        setBatchDetail(detail)
        setBatchDetailError(null)
      })
      .catch((err) => {
        if (!active) return
        setBatchDetail(null)
        setBatchDetailError(err instanceof Error ? err.message : 'Could not load this run.')
      })
    return () => {
      active = false
    }
    // activityBatches is in the deps so an open run refreshes as it progresses.
  }, [expandedBatch, activityBatches])

  // Initial load once on mount.
  useEffect(() => {
    loadActivity()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Poll only while a run is active; pause when the tab is hidden.
  useEffect(() => {
    if (!hasActiveBatch) return
    const id = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return
      loadActivity()
    }, 3000)
    return () => clearInterval(id)
  }, [hasActiveBatch, loadActivity])

  // Variant state
  const [previewVariants, setPreviewVariants] = useState<Record<number, PreviewVariant[]>>({})
  const [activeVariants, setActiveVariants] = useState<Record<number, 'main' | 'a' | 'b' | 'c'>>({})
  const [loadingVariants, setLoadingVariants] = useState<Record<number, boolean>>({})
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingPreview, setEditingPreview] = useState<number | null>(null)
  const [editingVariant, setEditingVariant] = useState<'main' | 'a' | 'b' | 'c' | null>(null)
  const [formData, setFormData] = useState<PreviewCreate>({
    url: '',
    domain: '',
    title: '',
    type: 'product',
    image_url: null,
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  // Only covers handing the job to the server — generation itself continues without us.
  const [isStartingGeneration, setIsStartingGeneration] = useState(false)

  // Load variants for previews — in parallel; the old serial loop made a
  // 30-card gallery wait through 30 sequential requests.
  useEffect(() => {
    const missing = previews.filter(
      (preview) => !previewVariants[preview.id] && !loadingVariants[preview.id]
    )
    if (missing.length === 0) return
    setLoadingVariants(prev => {
      const next = { ...prev }
      for (const p of missing) next[p.id] = true
      return next
    })
    Promise.allSettled(
      missing.map(async (preview) => {
        const variants = await fetchPreviewVariants(preview.id)
        return { id: preview.id, variants }
      })
    ).then((results) => {
      const loaded: Record<number, PreviewVariant[]> = {}
      for (const r of results) {
        if (r.status === 'fulfilled') loaded[r.value.id] = r.value.variants
      }
      if (Object.keys(loaded).length > 0) {
        setPreviewVariants(prev => ({ ...prev, ...loaded }))
        setActiveVariants(prev => {
          const next = { ...prev }
          for (const id of Object.keys(loaded)) {
            if (!(Number(id) in next)) next[Number(id)] = 'main'
          }
          return next
        })
      }
      setLoadingVariants(prev => {
        const next = { ...prev }
        for (const p of missing) next[p.id] = false
        return next
      })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previews])

  // Solid evergreen placeholder surface per preview type (no gradients in the identity)
  const getPlaceholderSurface = (type: string) => {
    const surfaces: Record<string, string> = {
      product: 'bg-primary-500',
      blog: 'bg-primary-600',
      landing: 'bg-ink',
    }
    return surfaces[type.toLowerCase()] || 'bg-secondary-900'
  }

  const handleOpenCreateModal = useCallback(() => {
    setEditingPreview(null)
    setFormData({
      url: '',
      domain: domains.length > 0 ? domains[0].name : '',
      title: '',
      type: 'product',
      image_url: null,
    })
    setFormError(null)
    setIsModalOpen(true)
  }, [domains])

  // /app/previews?new=1 opens the create dialog (used by the header quick action).
  useEffect(() => {
    if (searchParams.get('new') === null) return
    handleOpenCreateModal()
    const next = new URLSearchParams(searchParams)
    next.delete('new')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, handleOpenCreateModal])

  const handleOpenEditModal = (preview: typeof previews[0], variant: 'main' | 'a' | 'b' | 'c' = 'main') => {
    setEditingPreview(preview.id)
    setEditingVariant(variant)
    
    if (variant === 'main') {
      setFormData({
        url: preview.url,
        domain: preview.domain,
        title: preview.title,
        type: preview.type,
        image_url: preview.image_url || null,
      })
    } else {
      const variantData = previewVariants[preview.id]?.find(v => v.variant_key === variant)
      if (variantData) {
        setFormData({
          url: preview.url,
          domain: preview.domain,
          title: variantData.title,
          type: preview.type,
          image_url: variantData.image_url || preview.highlight_image_url || preview.image_url || null,
        })
      } else {
        setFormData({
          url: preview.url,
          domain: preview.domain,
          title: preview.title,
          type: preview.type,
          image_url: preview.image_url || null,
        })
      }
    }
    setFormError(null)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setEditingPreview(null)
    setEditingVariant(null)
    setFormData({
      url: '',
      domain: '',
      title: '',
      type: 'product',
      image_url: null,
    })
    setFormError(null)
  }
  
  const getDisplayData = (preview: typeof previews[0]) => {
    const activeVariant = activeVariants[preview.id] || 'main'
    
    if (activeVariant === 'main') {
      return {
        title: preview.title,
        description: preview.description,
        image_url: preview.image_url,
      }
    }
    
    const variant = previewVariants[preview.id]?.find(v => v.variant_key === activeVariant)
    if (variant) {
      return {
        title: variant.title,
        description: variant.description,
        image_url: variant.image_url || preview.highlight_image_url || preview.image_url,
      }
    }
    
    return {
      title: preview.title,
      description: preview.description,
      image_url: preview.image_url,
    }
  }

  const handleSubmit = async () => {
    if (!formData.url.trim() || !formData.domain.trim() || !formData.title.trim()) {
      setFormError('URL, Domain, and Title are required')
      return
    }

    try {
      setIsSubmitting(true)
      setFormError(null)

      if (editingPreview !== null) {
        if (editingVariant === 'main') {
          // Update main preview
          const updatePayload: PreviewUpdate = {
            title: formData.title,
            type: formData.type,
            image_url: formData.image_url || null,
          }
          await updatePreview(editingPreview, updatePayload)
        } else {
          // Update variant
          const variantData = previewVariants[editingPreview]?.find(v => v.variant_key === editingVariant)
          if (variantData) {
            await updatePreviewVariant(variantData.id, {
              title: formData.title,
              description: formData.description || undefined,
              image_url: formData.image_url || undefined,
            })
            // Refresh variants
            const variants = await fetchPreviewVariants(editingPreview)
            setPreviewVariants(prev => ({ ...prev, [editingPreview]: variants }))
          }
        }
      } else {
        // Create new preview
        await createOrUpdatePreview(formData)
      }

      handleCloseModal()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save preview')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this preview?')) {
      try {
        await deletePreview(id)
      } catch (err) {
        // Error is handled by hook
      }
    }
  }

  // Hand the job to the server and get out of the way: generation runs in the
  // background, so we close the dialog and let the activity list carry the run.
  const handleGenerateWithAI = async () => {
    if (!formData.url.trim() || !formData.domain.trim()) {
      setFormError('URL and Domain are required for AI generation')
      return
    }

    try {
      setIsStartingGeneration(true)
      setFormError(null)
      await createPreviewJob({ url: formData.url, domain: formData.domain })
      handleCloseModal()
      toast.info('Generating in the background', 'Track it under Generation activity — you can close this tab.')
      loadActivity()
    } catch (err) {
      // Quota / rate-limit / unverified-domain errors come back from this call,
      // so they're still shown in the form the user is looking at.
      setFormError(err instanceof Error ? err.message : 'Failed to start preview generation')
    } finally {
      setIsStartingGeneration(false)
    }
  }

  // ---- Bulk generation ----
  const openBulk = () => {
    setBulkDomain(verifiedDomains.length > 0 ? verifiedDomains[0].name : '')
    setBulkUrlText('')
    setBulkSitemapNote(null)
    setBulkError(null)
    setBulkStarting(false)
    setIsBulkOpen(true)
  }

  const closeBulk = () => setIsBulkOpen(false)

  const handleLoadSitemap = async () => {
    if (!bulkDomain) return
    setBulkLoadingSitemap(true)
    setBulkError(null)
    setBulkSitemapNote(null)
    try {
      const res = await discoverSitemapUrls(bulkDomain)
      if (res.count === 0) {
        setBulkSitemapNote('No sitemap found — paste URLs manually below.')
      } else {
        setBulkUrlText(res.urls.join('\n'))
        setBulkSitemapNote(`Found ${res.count} URL${res.count === 1 ? '' : 's'}.`)
      }
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : 'Could not read the sitemap.')
    } finally {
      setBulkLoadingSitemap(false)
    }
  }

  const handleBulkGenerate = async () => {
    if (!bulkDomain || bulkUrls.length === 0) return
    setBulkError(null)
    setBulkStarting(true)
    try {
      const res = await createBulkPreviewJob(bulkDomain, bulkUrls, false)
      closeBulk()
      const skipped = res.skipped_quota || 0
      toast.info(
        `Generating ${res.queued} preview${res.queued === 1 ? '' : 's'} in the background`,
        skipped > 0
          ? `${skipped} skipped — monthly quota reached. Track progress under Generation activity.`
          : 'Track progress under Generation activity — you can close this tab.'
      )
      loadActivity()
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : 'Bulk generation failed to start.')
    } finally {
      setBulkStarting(false)
    }
  }

  // ---- Per-card regenerate (re-roll) ----
  const handleRegenerate = async (preview: typeof previews[0]) => {
    if (regeneratingIds[preview.id]) return
    setRegenError(null)
    try {
      const { batch_id } = await createPreviewJob({ url: preview.url, domain: preview.domain, force: true })
      // Tie the spinner to the server-side run; loadActivity clears it when done.
      if (batch_id) setRegeneratingIds((prev) => ({ ...prev, [preview.id]: batch_id }))
      toast.info('Regenerating in the background', 'The card updates here when the run finishes.')
      loadActivity()
    } catch (err) {
      setRegenError(err instanceof Error ? err.message : 'Regeneration failed to start')
    }
  }

  /**
   * Restyle is not regeneration: it re-renders the existing card from its stored
   * spec, so it returns synchronously and costs no AI credit. That is why it
   * updates the row in place instead of queueing a background run.
   */
  const handleRestyle = async (
    preview: typeof previews[0],
    direction: PreviewRestyleRequest
  ) => {
    if (restylingIds[preview.id]) return
    setRestylingIds((prev) => ({ ...prev, [preview.id]: true }))
    try {
      const updated = await restylePreview(preview.id, direction)
      replacePreview(updated)
      toast.success('Card restyled', 'No AI credit was used.')
    } catch (err) {
      toast.error(
        'Could not restyle',
        err instanceof Error ? err.message : 'Your existing card is unchanged.'
      )
    } finally {
      setRestylingIds((prev) => {
        const next = { ...prev }
        delete next[preview.id]
        return next
      })
    }
  }

  return (
    <div>
      <div className="mb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Previews</h1>
          <p className="text-[15px] text-secondary-600">
            {previews.length > 0
              ? `${previews.length.toLocaleString()} ${previews.length === 1 ? 'URL' : 'URLs'} covered${domains.length > 0 ? ` across ${domains.length} ${domains.length === 1 ? 'domain' : 'domains'}` : ''}`
              : 'Browse and manage all your generated URL previews.'}
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <Button variant="secondary" onClick={openBulk} className="w-full sm:w-auto">
            <div className="flex items-center justify-center sm:justify-start space-x-2">
              <RectangleStackIcon className="w-5 h-5" />
              <span>Bulk generate</span>
            </div>
          </Button>
          <Button variant="accent" onClick={handleOpenCreateModal} className="w-full sm:w-auto">
            <div className="flex items-center justify-center sm:justify-start space-x-2">
              <PlusIcon className="w-5 h-5" />
              <span>Create Preview</span>
            </div>
          </Button>
        </div>
      </div>

      {error && (
        <Card className="mb-6" padding="md">
          <Alert variant="error">{error}</Alert>
        </Card>
      )}

      {regenError && (
        <Card className="mb-6" padding="md">
          <Alert variant="error" onDismiss={() => setRegenError(null)}>{regenError}</Alert>
        </Card>
      )}

      {/* Generation activity — persistent, tab-independent view of every run */}
      {activityBatches.length > 0 && (
        <Card className="mb-6" padding="md">
          <div className="flex items-center gap-2 mb-1">
            <RectangleStackIcon className="w-4 h-4 text-secondary-500" />
            <h2 className="text-sm font-semibold text-secondary-800">Generation activity</h2>
            {hasActiveBatch && (
              <span className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" title="A run is in progress" />
            )}
          </div>
          <p className="text-xs text-secondary-500 mb-3">
            Runs happen on our servers — you can close this tab and come back.
          </p>
          <div className="divide-y divide-line">
            {activityBatches.slice(0, 6).map((b) => {
              const pct = b.total ? Math.round(((b.completed + b.failed) / b.total) * 100) : 0
              const active = b.status === 'queued' || b.status === 'running'
              const expanded = expandedBatch === b.batch_id
              return (
                <div key={b.batch_id} className="py-2.5">
                  <button
                    type="button"
                    onClick={() => setExpandedBatch(expanded ? null : b.batch_id)}
                    aria-expanded={expanded}
                    title={expanded ? 'Hide the pages in this run' : 'Show the pages in this run'}
                    className="w-full flex items-center gap-3 text-left rounded-lg hover:bg-secondary-50 transition-colors"
                  >
                    <span className="flex-shrink-0">
                      {b.status === 'completed' && (
                        <span className="pill bg-primary-500 text-paper inline-flex items-center gap-1">
                          <CheckIcon className="w-3 h-3" /> Done
                        </span>
                      )}
                      {b.status === 'failed' && (
                        <span className="pill bg-error-50 text-error-700 inline-flex items-center gap-1">
                          <XMarkIcon className="w-3 h-3" /> Failed
                        </span>
                      )}
                      {b.status === 'running' && (
                        <span className="pill bg-secondary-100 text-secondary-700 inline-flex items-center gap-1">
                          <span className="w-3 h-3 border-2 border-secondary-400 border-t-transparent rounded-full animate-spin" /> Running
                        </span>
                      )}
                      {b.status === 'queued' && (
                        <span className="pill bg-secondary-100 text-secondary-500">Queued</span>
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-secondary-700 truncate" title={b.label || b.domain || ''}>
                          {b.label || b.domain || '—'}
                        </span>
                        <span className="text-xs text-secondary-400">·</span>
                        <span className="text-xs text-secondary-500 whitespace-nowrap">
                          {b.kind === 'single' && b.total === 1
                            ? (b.failed > 0 ? 'failed' : b.completed > 0 ? '1 preview' : 'single page')
                            : `${b.completed + b.failed} / ${b.total}${b.failed > 0 ? ` · ${b.failed} failed` : ''}`}
                        </span>
                      </div>
                      {active && (
                        <div className="mt-1.5 w-full h-1.5 bg-secondary-100 rounded-full overflow-hidden">
                          <div className="h-full bg-primary-500 transition-all" style={{ width: `${pct}%` }} />
                        </div>
                      )}
                    </div>
                    <span className="text-[11px] text-secondary-400 whitespace-nowrap flex-shrink-0">
                      {relativeTime(b.created_at)}
                    </span>
                  </button>

                  {expanded && (
                    <div className="mt-2 pl-1">
                      {batchDetailError && (
                        <p className="text-xs text-secondary-500">{batchDetailError}</p>
                      )}
                      {!batchDetailError && !batchDetail && (
                        <p className="text-xs text-secondary-500">Loading run…</p>
                      )}
                      {batchDetail && batchDetail.results.length === 0 && (
                        <p className="text-xs text-secondary-500">
                          No pages finished yet — results appear here as they land.
                        </p>
                      )}
                      {batchDetail && batchDetail.results.length > 0 && (
                        <div className="max-h-48 overflow-y-auto border border-line rounded-lg divide-y divide-line">
                          {batchDetail.results.map((r, i) => (
                            <div key={i} className="flex items-center gap-2 px-3 py-1.5">
                              {r.status === 'finished' ? (
                                <CheckIcon className="w-4 h-4 text-primary-600 flex-shrink-0" />
                              ) : (
                                <XMarkIcon className="w-4 h-4 text-error-600 flex-shrink-0" />
                              )}
                              <span className="font-mono text-[11px] text-secondary-600 truncate flex-1" title={r.url}>
                                {r.url}
                              </span>
                              {r.status === 'failed' && r.error && (
                                <span className="text-[11px] text-error-600 truncate max-w-[40%]" title={r.error}>
                                  {r.error}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {filters.map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`px-4 py-2.5 rounded-lg text-[13px] transition-colors min-h-[44px] ${
              activeFilter === filter
                ? 'bg-primary-500 text-paper font-semibold'
                : 'bg-surface text-secondary-600 font-medium border border-line hover:border-primary-500 hover:text-secondary-900'
            }`}
          >
            {filter}
          </button>
        ))}
        {searchQuery && (
          <span className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-secondary-100 text-[13px] text-secondary-700">
            <MagnifyingGlassIcon className="w-4 h-4" />
            "{searchQuery}"
            <button onClick={clearSearch} className="ml-1 text-secondary-500 hover:text-secondary-800" aria-label="Clear search">
              <XMarkIcon className="w-3.5 h-3.5" />
            </button>
          </span>
        )}
      </div>

      {loading ? (
        <SkeletonGrid count={6} />
      ) : previews.length === 0 ? (
        <Card>
          <EmptyState
            icon={<PhotoIcon className="w-8 h-8" />}
            title={hasActiveBatch ? 'Your first preview is generating' : 'No previews generated yet'}
            description={
              hasActiveBatch
                ? "It runs on our servers and lands here when it's done — feel free to close the tab."
                : 'Create your first AI-powered preview to see how your URLs will appear when shared on social media and messaging platforms.'
            }
            action={{
              label: hasActiveBatch ? 'Generate another' : 'Generate Your First Preview',
              onClick: handleOpenCreateModal,
            }}
          />
        </Card>
      ) : visiblePreviews.length === 0 ? (
        <Card>
          <EmptyState
            icon={<MagnifyingGlassIcon className="w-8 h-8" />}
            title={searchQuery ? `Nothing matches "${searchQuery}"` : `No ${activeFilter.toLowerCase()} previews`}
            description={
              searchQuery
                ? 'Try a different search, or clear it to see every preview.'
                : 'Previews of this type will appear here once generated.'
            }
            action={
              searchQuery
                ? { label: 'Clear search', onClick: clearSearch }
                : { label: 'Show all previews', onClick: () => setActiveFilter('All') }
            }
          />
        </Card>
      ) : (
        <>
          {/* Preview Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {visiblePreviews.map((preview) => {
                const displayData = getDisplayData(preview)
                const variants = previewVariants[preview.id] || []
                const hasVariants = variants.length > 0
                
                return (
                  <Card key={preview.id} className="p-0 overflow-hidden group relative hover:border-primary-500 hover:-translate-y-0.5 transition-all">
                    <div className={`aspect-video ${getPlaceholderSurface(preview.type)}`}>
                      {displayData.image_url ? (
                        <img
                          src={displayData.image_url}
                          alt={displayData.title}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = preview.image_url || ''
                          }}
                        />
                      ) : (
                        <div className="w-full h-full p-5 flex flex-col justify-between">
                          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-paper/60">
                            {preview.domain}
                          </span>
                          <span className="font-display text-xl font-semibold tracking-display-sm text-paper leading-tight line-clamp-2">
                            {displayData.title}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="p-4">
                      {/* Variant Tabs */}
                      {hasVariants && (
                        <div className="flex items-center space-x-1 mb-3 border-b border-secondary-200">
                          <button
                            onClick={() => setActiveVariants(prev => ({ ...prev, [preview.id]: 'main' }))}
                            className={`px-2 py-1 text-xs font-medium transition-colors ${
                              (activeVariants[preview.id] || 'main') === 'main'
                                ? 'text-primary-600 border-b-2 border-primary-500'
                                : 'text-secondary-500 hover:text-secondary-700'
                            }`}
                          >
                            Main
                          </button>
                          {variants.map((variant) => (
                            <button
                              key={variant.id}
                              onClick={() => setActiveVariants(prev => ({ ...prev, [preview.id]: variant.variant_key as 'a' | 'b' | 'c' }))}
                              className={`px-2 py-1 text-xs font-medium transition-colors ${
                                activeVariants[preview.id] === variant.variant_key
                                  ? 'text-primary-600 border-b-2 border-primary-500'
                                  : 'text-secondary-500 hover:text-secondary-700'
                              }`}
                              title={ANGLE_HELP[variant.angle ?? 'alternate']}
                            >
                              {/* The angle is what the tab is actually for — a
                                  bare "B" tells you nothing about what you are
                                  testing. Fall back to the key for older rows
                                  that predate angles. */}
                              {variant.angle && variant.angle !== 'main'
                                ? ANGLE_LABEL[variant.angle]
                                : variant.variant_key.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      )}
                      
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <h3 className="font-semibold text-secondary-900 truncate">{displayData.title}</h3>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          {/* Older backends omit generation_mode; those previews
                              all came from the AI lane, so absent reads as 'ai'
                              and only an explicit 'template' shows the badge. */}
                          {preview.generation_mode === 'template' && (
                            <span
                              className="pill bg-amber-50 text-amber-700"
                              title="Built from this page's metadata — your plan's monthly AI allowance is spent. Upgrade for an AI-designed card."
                            >
                              Template
                            </span>
                          )}
                          <span className="pill bg-secondary-100 text-secondary-600 capitalize">
                            {preview.type}
                          </span>
                        </div>
                      </div>
                      <p className="font-mono text-xs text-secondary-500 mb-2 truncate">{preview.url}</p>
                      {displayData.description && (
                        <p className="text-xs text-secondary-600 mb-2 line-clamp-2">{displayData.description}</p>
                      )}
                      {preview.keywords && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {preview.keywords.split(',').map((keyword, idx) => (
                            <span
                              key={idx}
                              className="font-mono text-[11px] px-2 py-0.5 bg-secondary-100 text-secondary-600 rounded-md"
                            >
                              {keyword.trim()}
                            </span>
                          ))}
                        </div>
                      )}
                      {!preview.keywords && (
                        <p className="text-xs text-secondary-400 italic mb-2">— no keywords detected —</p>
                      )}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <span className="text-xs text-secondary-500">{preview.monthly_clicks.toLocaleString()} clicks</span>
                          {preview.tone && (
                            <span className="text-xs text-secondary-400">• {preview.tone}</span>
                          )}
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => setDetailPreview(preview)}
                            className="text-primary-500 hover:text-accent-500 transition-colors p-1"
                            title="See how it looks on each platform"
                          >
                            <EyeIcon className="w-4 h-4" />
                          </button>
                          {/* Restyling only exists for cards that carry a render
                              spec. Older ones have to be regenerated once first,
                              so the control is hidden rather than shown broken. */}
                          {preview.can_rerender && (
                            <button
                              onClick={() =>
                                setOpenRestyleFor(openRestyleFor === preview.id ? null : preview.id)
                              }
                              disabled={!!restylingIds[preview.id]}
                              className={`transition-colors p-1 disabled:opacity-50 disabled:cursor-not-allowed ${
                                openRestyleFor === preview.id
                                  ? 'text-accent-500'
                                  : 'text-primary-500 hover:text-accent-500'
                              }`}
                              title="Restyle this card — free, no AI credit used"
                            >
                              <SwatchIcon className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => handleRegenerate(preview)}
                            disabled={!!regeneratingIds[preview.id]}
                            className="text-primary-500 hover:text-accent-500 transition-colors p-1 disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Regenerate from the page — uses one AI preview"
                          >
                            <ArrowPathIcon className={`w-4 h-4 ${regeneratingIds[preview.id] ? 'animate-spin' : ''}`} />
                          </button>
                          <button
                            onClick={() => handleOpenEditModal(preview, activeVariants[preview.id] || 'main')}
                            className="text-primary-500 hover:text-accent-500 transition-colors p-1"
                            title="Edit preview"
                          >
                            <PencilIcon className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(preview.id)}
                            className="text-error-600 hover:text-error-700 transition-colors p-1"
                            title="Delete preview"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {openRestyleFor === preview.id && (
                        <div className="mt-3 pt-3 border-t border-secondary-200 space-y-3">
                          <div>
                            <p className="text-[11px] font-mono uppercase tracking-wider text-secondary-500 mb-1.5">
                              Layout
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {LAYOUT_CHOICES.map((choice) => (
                                <button
                                  key={choice.value}
                                  onClick={() => handleRestyle(preview, { layout: choice.value })}
                                  disabled={!!restylingIds[preview.id]}
                                  title={choice.hint}
                                  className={`px-2 py-1 text-xs rounded-md border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                                    preview.layout === choice.value
                                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                                      : 'border-secondary-200 text-secondary-600 hover:border-primary-300'
                                  }`}
                                >
                                  {choice.label}
                                </button>
                              ))}
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] font-mono uppercase tracking-wider text-secondary-500 mb-1.5">
                              Panel
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {PANEL_CHOICES.map((choice) => (
                                <button
                                  key={choice.value}
                                  onClick={() => handleRestyle(preview, { panel: choice.value })}
                                  disabled={!!restylingIds[preview.id]}
                                  className="px-2 py-1 text-xs rounded-md border border-secondary-200 text-secondary-600 hover:border-primary-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  {choice.label}
                                </button>
                              ))}
                            </div>
                          </div>
                          <div>
                            <p className="text-[11px] font-mono uppercase tracking-wider text-secondary-500 mb-1.5">
                              Accent
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {ACCENT_CHOICES.map((choice) => (
                                <button
                                  key={choice.value}
                                  onClick={() => handleRestyle(preview, { accent: choice.value })}
                                  disabled={!!restylingIds[preview.id]}
                                  title={choice.hint}
                                  className="px-2 py-1 text-xs rounded-md border border-secondary-200 text-secondary-600 hover:border-primary-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  {choice.label}
                                </button>
                              ))}
                            </div>
                          </div>
                          <p className="text-[11px] text-secondary-500">
                            {restylingIds[preview.id]
                              ? 'Rendering…'
                              : 'Restyling re-renders the existing card. It never uses an AI preview from your plan.'}
                          </p>
                          {/* A layout the page cannot support (stat with no
                              number, split with no image) falls back rather than
                              failing, so say so instead of leaving the user to
                              wonder why nothing changed. */}
                          <p className="text-[11px] text-secondary-400">
                            Layouts that need something this page doesn&rsquo;t have fall back to Headline.
                          </p>
                        </div>
                      )}
                    </div>
                  </Card>
                )
              })}
            </div>
        </>
      )}

      <PreviewDetailModal
        preview={detailPreview}
        variant={
          detailPreview
            ? (previewVariants[detailPreview.id] || []).find(
                (v) => v.variant_key === (activeVariants[detailPreview.id] || 'main')
              ) || null
            : null
        }
        isOpen={detailPreview !== null}
        onClose={() => setDetailPreview(null)}
      />

      {/* Create/Edit Preview Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={editingPreview !== null 
          ? `Edit Preview${editingVariant && editingVariant !== 'main' ? ` - Variant ${editingVariant.toUpperCase()}` : ''}`
          : 'Create Preview'}
      >
        <div className="space-y-4">
          {formError && (
            <Alert variant="error">{formError}</Alert>
          )}

          <div>
            <label className="block text-sm font-medium text-secondary-700 mb-2">
              URL <span className="text-error-500">*</span>
            </label>
            <input
              type="url"
              placeholder="https://example.com/page"
              value={formData.url}
              onChange={(e) => {
                setFormData({ ...formData, url: e.target.value })
                setFormError(null)
              }}
              disabled={editingPreview !== null}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all ${
                formError && !formData.url ? 'border-error-300 bg-error-50/50' : 'border-secondary-300'
              } ${editingPreview !== null ? 'bg-secondary-50 cursor-not-allowed' : ''}`}
            />
            {editingPreview !== null && (
              <p className="text-xs text-secondary-500 mt-1">URL cannot be changed after creation</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-secondary-700 mb-2">
              Domain <span className="text-error-500">*</span>
            </label>
            {domains.length > 0 ? (
              <select
                value={formData.domain}
                onChange={(e) => {
                  setFormData({ ...formData, domain: e.target.value })
                  setFormError(null)
                }}
                disabled={editingPreview !== null}
                className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all ${
                  formError && !formData.domain ? 'border-error-300 bg-error-50/50' : 'border-secondary-300'
                } ${editingPreview !== null ? 'bg-secondary-50 cursor-not-allowed' : ''}`}
              >
                <option value="">Select a domain</option>
                {domains.map((domain) => (
                  <option key={domain.id} value={domain.name}>
                    {domain.name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                placeholder="example.com"
                value={formData.domain}
                onChange={(e) => {
                  setFormData({ ...formData, domain: e.target.value })
                  setFormError(null)
                }}
                disabled={editingPreview !== null}
                className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all ${
                  formError && !formData.domain ? 'border-error-300 bg-error-50/50' : 'border-secondary-300'
                } ${editingPreview !== null ? 'bg-secondary-50 cursor-not-allowed' : ''}`}
              />
            )}
            {domains.length === 0 && (
              <p className="text-xs text-secondary-500 mt-1">Add a domain first in the Domains page</p>
            )}
          </div>

          {/* Variant Switcher in Edit Mode */}
          {editingPreview !== null && previewVariants[editingPreview] && previewVariants[editingPreview].length > 0 && (
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Edit Variant
              </label>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleOpenEditModal(previews.find(p => p.id === editingPreview)!, 'main')}
                  className={`px-3 py-2 text-sm rounded-lg transition-colors ${
                    editingVariant === 'main'
                      ? 'bg-primary-500 text-paper'
                      : 'bg-secondary-100 text-secondary-700 hover:bg-secondary-200'
                  }`}
                >
                  Main
                </button>
                {previewVariants[editingPreview].map((variant) => (
                  <button
                    key={variant.id}
                    onClick={() => handleOpenEditModal(previews.find(p => p.id === editingPreview)!, variant.variant_key as 'a' | 'b' | 'c')}
                    className={`px-3 py-2 text-sm rounded-lg transition-colors ${
                      editingVariant === variant.variant_key
                        ? 'bg-primary-500 text-paper'
                        : 'bg-secondary-100 text-secondary-700 hover:bg-secondary-200'
                    }`}
                  >
                    {variant.variant_key.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-secondary-700 mb-2">
              Title <span className="text-error-500">*</span>
            </label>
            <input
              type="text"
              placeholder="Page Title"
              value={formData.title}
              onChange={(e) => {
                setFormData({ ...formData, title: e.target.value })
                setFormError(null)
              }}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all ${
                formError && !formData.title ? 'border-error-300 bg-error-50/50' : 'border-secondary-300'
              }`}
            />
          </div>
          
          {editingPreview !== null && editingVariant !== 'main' && (
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Description
              </label>
              <textarea
                placeholder="Preview description"
                value={formData.description || ''}
                onChange={(e) => {
                  setFormData({ ...formData, description: e.target.value || undefined })
                  setFormError(null)
                }}
                rows={3}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-secondary-700 mb-2">
              Type <span className="text-error-500">*</span>
            </label>
            <select
              value={formData.type}
              onChange={(e) => {
                setFormData({ ...formData, type: e.target.value })
                setFormError(null)
              }}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all"
            >
              <option value="product">Product</option>
              <option value="blog">Blog</option>
              <option value="landing">Landing Page</option>
            </select>
          </div>

          {/* Only show image URL for editing, not for new previews using AI */}
          {editingPreview !== null && (
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Image URL (optional)
              </label>
              <input
                type="url"
                placeholder="https://example.com/image.jpg"
                value={formData.image_url || ''}
                onChange={(e) => {
                  setFormData({ ...formData, image_url: e.target.value || null })
                  setFormError(null)
                }}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all"
              />
              <p className="text-xs text-secondary-500 mt-1">Override the AI-generated image with a custom URL.</p>
            </div>
          )}

          {/* What "Generate with AI" does — set expectations before the click */}
          {editingPreview === null && (
            <p className="text-xs text-secondary-500">
              Generation runs on our servers: we close this dialog as soon as the run starts, and
              it keeps going even if you close the tab. Watch it under “Generation activity”.
            </p>
          )}

          <div className="flex items-center justify-end space-x-3 pt-4">
            <Button variant="secondary" onClick={handleCloseModal} disabled={isSubmitting || isStartingGeneration}>
              Cancel
            </Button>
            {editingPreview !== null ? (
              <Button onClick={handleSubmit} disabled={isSubmitting || isStartingGeneration}>
                {isSubmitting ? 'Saving...' : 'Update Preview'}
              </Button>
            ) : (
              <>
                <Button
                  variant="secondary"
                  onClick={handleSubmit}
                  disabled={isSubmitting || isStartingGeneration}
                >
                  {isSubmitting ? 'Saving...' : 'Create Manually'}
                </Button>
                <Button
                  variant="accent"
                  onClick={handleGenerateWithAI}
                  disabled={isSubmitting || isStartingGeneration || !formData.url || !formData.domain}
                >
                  {isStartingGeneration ? (
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-paper border-t-transparent rounded-full animate-spin" />
                      <span>Starting…</span>
                    </div>
                  ) : (
                    <div className="flex items-center space-x-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span>Generate with AI</span>
                    </div>
                  )}
                </Button>
              </>
            )}
          </div>
        </div>
      </Modal>

      {/* Bulk generation modal */}
      <Modal isOpen={isBulkOpen} onClose={closeBulk} title="Generate previews in bulk">
        <div className="space-y-4">
          {bulkError && <Alert variant="error">{bulkError}</Alert>}

          {verifiedDomains.length === 0 ? (
            <Alert variant="warning">
              Add and verify a domain first on the Domains page, then you can generate previews for its pages in bulk.
            </Alert>
          ) : (
            <>
              <p className="text-[13px] text-secondary-600">
                Cover your whole site at once — load your URLs from the site's sitemap or paste them in,
                then generate an on-brand preview for each. The run happens on our servers, so you can
                close this dialog (and the tab) once it starts.
              </p>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-2">Domain</label>
                <select
                  value={bulkDomain}
                  onChange={(e) => setBulkDomain(e.target.value)}
                  disabled={bulkStarting}
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all disabled:bg-secondary-50"
                >
                  {verifiedDomains.map((d) => (
                    <option key={d.id} value={d.name}>{d.name}</option>
                  ))}
                </select>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="secondary"
                  onClick={handleLoadSitemap}
                  disabled={bulkLoadingSitemap || bulkStarting || !bulkDomain}
                >
                  {bulkLoadingSitemap ? (
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-secondary-400 border-t-transparent rounded-full animate-spin" />
                      <span>Reading sitemap…</span>
                    </div>
                  ) : (
                    'Load from sitemap'
                  )}
                </Button>
                {bulkSitemapNote && <span className="text-xs text-secondary-500">{bulkSitemapNote}</span>}
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-2">
                  URLs <span className="text-secondary-400 font-normal">(one per line)</span>
                </label>
                <textarea
                  value={bulkUrlText}
                  onChange={(e) => setBulkUrlText(e.target.value)}
                  disabled={bulkStarting}
                  rows={8}
                  placeholder={`https://${bulkDomain || 'example.com'}/\nhttps://${bulkDomain || 'example.com'}/pricing`}
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg font-mono text-xs focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500 outline-none transition-all disabled:bg-secondary-50"
                />
                <p className="text-xs text-secondary-500 mt-1">
                  {bulkUrls.length} URL{bulkUrls.length === 1 ? '' : 's'} · up to 50 per run
                </p>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-2">
                <Button variant="secondary" onClick={closeBulk} disabled={bulkStarting}>
                  Cancel
                </Button>
                <Button
                  variant="accent"
                  onClick={handleBulkGenerate}
                  disabled={bulkStarting || bulkUrls.length === 0}
                >
                  {bulkStarting ? (
                    <div className="flex items-center space-x-2">
                      <div className="w-4 h-4 border-2 border-paper border-t-transparent rounded-full animate-spin" />
                      <span>Starting…</span>
                    </div>
                  ) : (
                    `Generate ${bulkUrls.length || ''} preview${bulkUrls.length === 1 ? '' : 's'}`.replace('  ', ' ').trim()
                  )}
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  )
}

