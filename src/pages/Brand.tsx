import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  PhotoIcon,
  ArrowPathIcon,
  TrashIcon,
  ArrowUpTrayIcon,
  LockClosedIcon,
  SparklesIcon,
  ArrowUturnLeftIcon,
} from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import {
  fetchBrandSettings,
  updateBrandSettings,
  uploadBrandLogo,
  renderBrandPreview,
  resetBrandSettings,
  detectBrandFromSite,
  getMyPlan,
} from '../api/client'
import type { BrandSettings, BrandSettingsUpdate, BrandSuggestion } from '../api/types'
import { useDomains } from '../hooks/useDomains'
import { FEATURES } from '../lib/plans'

// Must match FONT_CHOICES in backend/schemas/brand.py. These are the faces the
// renderer can actually draw; "auto" is the card's own type.
const FONT_OPTIONS: [string, string][] = [
  ['auto', 'Auto — MetaView display type (recommended)'],
  ['Bricolage Grotesque', 'Bricolage Grotesque'],
  ['IBM Plex Sans', 'IBM Plex Sans'],
  ['System', 'System UI'],
]
const HEX_RE = /^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/
const COLOR_FIELDS = ['primary_color', 'secondary_color', 'accent_color'] as const
// How long the form must sit still before the sample is redrawn.
const PREVIEW_DEBOUNCE_MS = 600

/** "Inter" was the stock value and never rendered as Inter; it means auto. */
function normalizeLoaded(s: BrandSettings): BrandSettings {
  const font = (s.font_family || '').toLowerCase()
  return font === 'inter' || font === '' ? { ...s, font_family: 'auto' } : s
}

/** The form as the API takes it. The white-label name only goes when the plan has it. */
function toPayload(form: BrandSettings, canWhiteLabel: boolean): BrandSettingsUpdate {
  const payload: BrandSettingsUpdate = {
    primary_color: form.primary_color,
    secondary_color: form.secondary_color,
    accent_color: form.accent_color,
    font_family: form.font_family,
    logo_url: form.logo_url ?? null,
    brand_name: form.brand_name ?? null,
    tagline: form.tagline ?? null,
    brand_description: form.brand_description ?? null,
    audience: form.audience ?? null,
    voice: form.voice,
    preview_layout: form.preview_layout,
    preview_panel: form.preview_panel,
    preview_accent: form.preview_accent,
    force_brand_colors: form.force_brand_colors,
    hide_watermark: form.hide_watermark,
  }
  if (canWhiteLabel) payload.white_label_name = form.white_label_name ?? null
  return payload
}

/** A sentence naming what "Fill from my site" applied. */
function describeSuggestion(found: BrandSuggestion): string {
  const parts: string[] = []
  if (found.brand_name) parts.push('name')
  if (found.tagline) parts.push('tagline')
  if (found.brand_description) parts.push('description')
  if (found.primary_color) parts.push('colours')
  if (found.logo_url) parts.push('logo')
  return parts.join(', ')
}
// Must match VOICE_CHOICES in backend/schemas/brand.py.
const VOICE_OPTIONS: [string, string][] = [
  ['auto', 'Auto — infer it from my brand'],
  ['professional', 'Professional — precise, trustworthy'],
  ['confident', 'Confident — direct, no hedging'],
  ['friendly', 'Friendly — warm, plain-spoken'],
  ['technical', 'Technical — specific, no fluff'],
  ['playful', 'Playful — energetic, a little wit'],
  ['luxury', 'Luxury — understated, premium'],
]
const LAYOUT_OPTIONS: [string, string][] = [
  ['auto', 'Auto — let the AI decide'],
  ['typographic', 'Headline (type only)'],
  ['split', 'Split (headline + hero image)'],
  ['stat', 'Stat (proof number as the hero)'],
  ['editorial', 'Editorial (kicker, rule, deck)'],
  ['product', 'Product (shot + price chip)'],
  ['profile', 'Profile (avatar + name)'],
]
const PANEL_OPTIONS: [string, string][] = [
  ['auto', 'Auto'],
  ['primary', 'Brand primary colour'],
  ['secondary', 'Secondary colour'],
  ['dark', 'Dark'],
  ['light', 'Light'],
]
const ACCENT_OPTIONS: [string, string][] = [
  ['auto', 'Auto'],
  ['bar', 'Bar'],
  ['dot', 'Dot'],
  ['shape', 'Shape'],
]

// Curated one-click looks. Each maps to the existing layout/panel/accent fields,
// so presets are just a friendly starting point over the fine-grained controls.
const CARD_PRESETS: { name: string; layout: string; panel: string; accent: string }[] = [
  { name: 'Auto', layout: 'auto', panel: 'auto', accent: 'auto' },
  { name: 'Bold', layout: 'split', panel: 'primary', accent: 'bar' },
  { name: 'Minimal', layout: 'typographic', panel: 'light', accent: 'dot' },
  { name: 'Dark', layout: 'typographic', panel: 'dark', accent: 'bar' },
  { name: 'Editorial', layout: 'split', panel: 'secondary', accent: 'shape' },
]

const inputClass =
  'w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all text-sm'

function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  hint?: string
  disabled?: boolean
}) {
  return (
    <div className={`flex items-start justify-between gap-4 ${disabled ? 'opacity-60' : ''}`}>
      <div>
        <span className="text-sm font-medium text-secondary-800">{label}</span>
        {hint && <p className="text-xs text-secondary-500 mt-0.5">{hint}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
          disabled ? 'cursor-not-allowed' : ''
        } ${checked && !disabled ? 'bg-primary-500' : 'bg-secondary-300'}`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-5' : 'translate-x-0.5'
          }`}
        />
      </button>
    </div>
  )
}

function UpgradeNote({ feature }: { feature: string }) {
  return (
    <div className="mb-4 flex items-center gap-2 rounded-lg border border-accent-200 bg-accent-50 px-3 py-2 text-xs text-accent-800">
      <LockClosedIcon className="h-4 w-4 flex-shrink-0" />
      <span>
        {feature} is a <span className="font-semibold">Growth</span> feature.{' '}
        <Link to="/app/billing" className="font-semibold underline hover:no-underline">
          Upgrade to unlock
        </Link>
        .
      </span>
    </div>
  )
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  const safe = /^#[0-9a-fA-F]{6}$/.test(value) ? value : '#000000'
  const invalid = !HEX_RE.test(value.trim())
  return (
    <div>
      <label className="block text-sm font-medium text-secondary-700 mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={safe}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-12 flex-shrink-0 rounded border border-secondary-300 cursor-pointer bg-white p-0.5"
          aria-label={`${label} colour picker`}
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#000000"
          aria-invalid={invalid}
          className={`flex-1 px-3 py-2 border rounded-lg text-sm font-mono focus:ring-2 focus:ring-primary focus:border-transparent outline-none ${
            invalid ? 'border-error-500 bg-error-50' : 'border-secondary-300'
          }`}
        />
      </div>
      {invalid && <p className="text-xs text-error-700 mt-1">Use a hex colour like #1a2b3c.</p>}
    </div>
  )
}

function Select({
  label,
  value,
  options,
  onChange,
  hint,
  disabled,
}: {
  label: string
  value: string
  options: [string, string][]
  onChange: (v: string) => void
  hint?: string
  disabled?: boolean
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-secondary-700 mb-1.5">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`${inputClass} ${disabled ? 'opacity-60 cursor-not-allowed bg-secondary-50' : ''}`}
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
      {hint && <p className="text-xs text-secondary-500 mt-1">{hint}</p>}
    </div>
  )
}

export default function Brand() {
  // Each connected domain is its own site with its own brand. Until a domain is
  // connected there is nothing to scope to, so we edit the account-wide default
  // (domainId null) — which is exactly what this page did before.
  const { domains, loading: domainsLoading } = useDomains()
  const [domainId, setDomainId] = useState<number | null>(null)
  const [domainPicked, setDomainPicked] = useState(false)

  const [settings, setSettings] = useState<BrandSettings | null>(null)
  const [form, setForm] = useState<BrandSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [logoBusy, setLogoBusy] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [features, setFeatures] = useState<string[]>([])
  const [detecting, setDetecting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  // Each sample request gets a number; only the newest one may paint, so a
  // slow render for an older edit never overwrites a newer one.
  const previewSeq = useRef(0)

  const canCardControls = features.includes(FEATURES.CARD_CONTROLS)
  const canHideWatermark = features.includes(FEATURES.HIDE_WATERMARK)
  const canWhiteLabel = features.includes(FEATURES.WHITE_LABEL)

  const colorsValid = !!form && COLOR_FIELDS.every((k) => HEX_RE.test((form[k] || '').trim()))

  // Draws the sample from the form as it stands — saved or not — so every
  // control answers immediately instead of after a save.
  const refreshPreview = useCallback(
    async (draft?: BrandSettingsUpdate) => {
      const seq = ++previewSeq.current
      setPreviewLoading(true)
      setPreviewError(null)
      try {
        const { image_data_uri } = await renderBrandPreview(domainId, draft)
        if (seq === previewSeq.current) setPreviewUrl(image_data_uri)
      } catch (e) {
        if (seq === previewSeq.current) {
          setPreviewError(e instanceof Error ? e.message : 'Could not render preview')
        }
      } finally {
        if (seq === previewSeq.current) setPreviewLoading(false)
      }
    },
    [domainId]
  )

  const redrawNow = () => {
    if (form && colorsValid) refreshPreview(toPayload(form, canWhiteLabel))
  }

  const draftKey = form && colorsValid ? JSON.stringify(toPayload(form, canWhiteLabel)) : null
  useEffect(() => {
    if (!draftKey) return
    const timer = window.setTimeout(
      () => refreshPreview(JSON.parse(draftKey) as BrandSettingsUpdate),
      PREVIEW_DEBOUNCE_MS
    )
    return () => window.clearTimeout(timer)
  }, [draftKey, refreshPreview])

  // The API returns domains newest-first; sort by name so the picker order and
  // the default choice stay stable as domains are added.
  const sortedDomains = useMemo(
    () => [...domains].sort((a, b) => a.name.localeCompare(b.name)),
    [domains]
  )

  // Pick the site to edit once the domain list arrives, preferring a verified
  // one — those are the domains actually generating previews.
  useEffect(() => {
    if (domainsLoading || domainPicked) return
    const verified = sortedDomains.find((d) => d.status === 'verified')
    setDomainId((verified ?? sortedDomains[0])?.id ?? null)
    setDomainPicked(true)
  }, [sortedDomains, domainsLoading, domainPicked])

  // Which card features this plan is entitled to (drives the locks below).
  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const plan = await getMyPlan()
        if (active) setFeatures(plan.features || [])
      } catch {
        /* leave features empty → controls lock closed, which is the safe default */
      }
    })()
    return () => {
      active = false
    }
  }, [])

  // Load the selected site's brand. Waits for the domain choice so we don't
  // fetch the org default first and flash the wrong brand.
  useEffect(() => {
    if (!domainPicked) return
    let active = true
    ;(async () => {
      setLoading(true)
      setLoadError(null)
      setNotice(null)
      try {
        const s = normalizeLoaded(await fetchBrandSettings(domainId))
        if (!active) return
        setSettings(s)
        setForm(s)
      } catch (e) {
        if (active) setLoadError(e instanceof Error ? e.message : 'Failed to load brand settings')
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [domainId, domainPicked])

  const dirty = !!(settings && form && JSON.stringify(settings) !== JSON.stringify(form))
  const set = (patch: Partial<BrandSettings>) => setForm((f) => (f ? { ...f, ...patch } : f))
  const domainName = sortedDomains.find((d) => d.id === domainId)?.name ?? null
  const inherits = domainId !== null && !!settings?.inherits_default

  const handleSave = async () => {
    if (!form || !colorsValid) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const updated = normalizeLoaded(
        await updateBrandSettings(toPayload(form, canWhiteLabel), domainId)
      )
      setSettings(updated)
      setForm(updated)
      setNotice(null)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3500)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  // Uploading saves the logo immediately (it has to be stored somewhere), but
  // keeps whatever else the user has edited and not saved yet.
  const handleLogoFile = async (file: File | null | undefined) => {
    if (!file) return
    setLogoBusy(true)
    setSaveError(null)
    try {
      const updated = normalizeLoaded(await uploadBrandLogo(file, domainId))
      setSettings(updated)
      setForm((f) => (f ? { ...f, logo_url: updated.logo_url } : updated))
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Logo upload failed')
    } finally {
      setLogoBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  // Removing is just an edit: it shows on the sample now and lands on Save.
  const handleRemoveLogo = () => set({ logo_url: null })

  const handleDetect = async () => {
    if (domainId === null) return
    setDetecting(true)
    setSaveError(null)
    setNotice(null)
    try {
      const found = await detectBrandFromSite(domainId)
      const patch: Partial<BrandSettings> = {}
      if (found.brand_name) patch.brand_name = found.brand_name
      if (found.tagline) patch.tagline = found.tagline
      if (found.brand_description) patch.brand_description = found.brand_description
      if (found.primary_color) patch.primary_color = found.primary_color
      if (found.secondary_color) patch.secondary_color = found.secondary_color
      if (found.accent_color) patch.accent_color = found.accent_color
      if (found.logo_url) patch.logo_url = found.logo_url
      const what = describeSuggestion(found)
      if (!what) {
        setNotice(`We could read ${found.source_url} but found nothing usable to fill in.`)
        return
      }
      set(patch)
      setNotice(`Filled ${what} from ${found.source_url}. Check the sample, then save.`)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Could not read your site')
    } finally {
      setDetecting(false)
    }
  }

  const handleReset = async () => {
    if (domainId === null) return
    if (
      !window.confirm(
        `Put ${domainName ?? 'this site'} back on the account default brand? Its own settings will be removed.`
      )
    ) {
      return
    }
    setResetting(true)
    setSaveError(null)
    try {
      const updated = normalizeLoaded(await resetBrandSettings(domainId))
      setSettings(updated)
      setForm(updated)
      setNotice(`${domainName ?? 'This site'} now follows the account default.`)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Could not reset this site')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-secondary-900">My site — brand &amp; identity</h1>
        <p className="text-secondary-600 mt-1">
          Who your site is and how it looks. Everything here feeds preview generation for this
          domain: the identity shapes the words, the visuals shape the card.
        </p>
      </div>

      {sortedDomains.length > 0 && (
        <Card className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex-1 min-w-[240px]">
              <label
                htmlFor="brand-domain"
                className="block text-sm font-medium text-secondary-700 mb-1.5"
              >
                Site
              </label>
              <select
                id="brand-domain"
                value={domainId ?? ''}
                onChange={(e) => {
                  const next = e.target.value === '' ? null : Number(e.target.value)
                  if (
                    dirty &&
                    !window.confirm('You have unsaved changes. Switch site and discard them?')
                  ) {
                    return
                  }
                  setDomainId(next)
                }}
                className={`${inputClass} font-mono`}
              >
                {sortedDomains.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                    {d.status !== 'verified' ? ' (unverified)' : ''}
                  </option>
                ))}
                <option value="">All other sites (account default)</option>
              </select>
            </div>
            <p className="text-xs text-secondary-500 max-w-sm">
              {domainId === null
                ? 'These settings apply to every site that has not been given its own brand.'
                : inherits
                  ? 'This site follows the account default. Saving here gives it a brand of its own.'
                  : 'This site has its own brand. Changes here affect this site only.'}
            </p>
          </div>
          {domainId !== null && (
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-secondary-100 pt-4">
              <Button
                variant="secondary"
                size="sm"
                loading={detecting}
                disabled={loading}
                icon={<SparklesIcon className="w-4 h-4" />}
                onClick={handleDetect}
              >
                Fill from {domainName ?? 'my site'}
              </Button>
              {!inherits && settings?.id != null && (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={resetting}
                  icon={<ArrowUturnLeftIcon className="w-4 h-4" />}
                  onClick={handleReset}
                >
                  Use account default
                </Button>
              )}
              <p className="text-xs text-secondary-500">
                Reads your name, strapline, colours and logo off your home page. Nothing is saved
                until you save.
              </p>
            </div>
          )}
        </Card>
      )}

      {notice && (
        <Card className="mb-6 bg-accent-50 border-accent-200">
          <p className="text-accent-800 text-sm">{notice}</p>
        </Card>
      )}

      {loadError && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {loadError}</p>
        </Card>
      )}
      {saveError && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {saveError}</p>
        </Card>
      )}
      {saveSuccess && (
        <Card className="mb-6 bg-success-50 border-success-200">
          <p className="text-success-800">
            Saved. New previews{domainName && domainId !== null ? ` for ${domainName}` : ''} use these
            settings, and cached cards were cleared so regenerating picks them up.
          </p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <p className="text-secondary-500">Loading brand settings…</p>
          </div>
        </Card>
      ) : form ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls */}
          <div className="lg:col-span-2 space-y-6">
            {/* Site identity — the words previews are written from */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary-900 mb-1">Site identity</h3>
              <p className="text-sm text-secondary-600 mb-5">
                Tell us who you are in your own words. We use this when writing each preview's copy,
                and the name is what we print on the card. Leave anything blank and we'll keep
                inferring it from the page.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1.5">
                    Site / brand name
                  </label>
                  <input
                    type="text"
                    value={form.brand_name ?? ''}
                    onChange={(e) => set({ brand_name: e.target.value })}
                    placeholder="Acme Analytics"
                    maxLength={80}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1.5">
                    Tagline
                  </label>
                  <input
                    type="text"
                    value={form.tagline ?? ''}
                    onChange={(e) => set({ tagline: e.target.value })}
                    placeholder="Product analytics without the setup"
                    maxLength={120}
                    className={inputClass}
                  />
                </div>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-secondary-700 mb-1.5">
                  What you do
                </label>
                <textarea
                  value={form.brand_description ?? ''}
                  onChange={(e) => set({ brand_description: e.target.value })}
                  placeholder="We help SaaS teams see which features drive retention, without a data engineer."
                  rows={3}
                  maxLength={500}
                  className={inputClass}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1.5">
                    Who it's for
                  </label>
                  <input
                    type="text"
                    value={form.audience ?? ''}
                    onChange={(e) => set({ audience: e.target.value })}
                    placeholder="Product managers at B2B SaaS companies"
                    maxLength={200}
                    className={inputClass}
                  />
                </div>
                <Select
                  label="Tone of voice"
                  value={form.voice || 'auto'}
                  options={VOICE_OPTIONS}
                  onChange={(v) => set({ voice: v })}
                />
              </div>
            </Card>

            {/* Brand identity */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary-900 mb-4">Logo &amp; colours</h3>

              {/* Logo */}
              <div className="flex items-center gap-6 mb-6">
                <div className="w-24 h-24 bg-secondary-100 rounded-lg flex items-center justify-center border-2 border-dashed border-secondary-300 overflow-hidden flex-shrink-0">
                  {form.logo_url ? (
                    <img
                      src={form.logo_url}
                      alt="Brand logo"
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <PhotoIcon className="w-8 h-8 text-secondary-400" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-secondary-600 mb-2">
                    Upload your logo (PNG or SVG, transparent background, under 5&nbsp;MB).
                  </p>
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => handleLogoFile(e.target.files?.[0])}
                  />
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={logoBusy}
                      icon={<ArrowUpTrayIcon className="w-4 h-4" />}
                      onClick={() => fileRef.current?.click()}
                    >
                      {form.logo_url ? 'Replace logo' : 'Upload logo'}
                    </Button>
                    {form.logo_url && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={logoBusy}
                        icon={<TrashIcon className="w-4 h-4" />}
                        onClick={handleRemoveLogo}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Colours */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <ColorField
                  label="Primary"
                  value={form.primary_color}
                  onChange={(v) => set({ primary_color: v })}
                />
                <ColorField
                  label="Secondary"
                  value={form.secondary_color}
                  onChange={(v) => set({ secondary_color: v })}
                />
                <ColorField
                  label="Accent"
                  value={form.accent_color}
                  onChange={(v) => set({ accent_color: v })}
                />
              </div>

              {/* Font */}
              <div>
                <Select
                  label="Headline font"
                  value={form.font_family}
                  options={FONT_OPTIONS}
                  onChange={(v) => set({ font_family: v })}
                  hint="Auto draws headlines in the same display face as our showcase cards."
                />
              </div>
              <p className="text-xs text-secondary-500 mt-4">
                {form.force_brand_colors
                  ? 'Cards always use this palette.'
                  : 'Cards use the colours we find on each page, and fall back to this palette when a page has none of its own.'}
              </p>
            </Card>

            {/* Preview-card controls */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary-900 mb-1">Preview-card controls</h3>
              <p className="text-sm text-secondary-600 mb-5">
                “Auto” lets our art director choose per page. Override any of these to lock the look.
              </p>

              {!canCardControls && <UpgradeNote feature="Card layout & style controls" />}

              <div className="mb-5">
                <label className="block text-sm font-medium text-secondary-700 mb-2">Style presets</label>
                <div className="flex flex-wrap gap-2">
                  {CARD_PRESETS.map((p) => {
                    const active =
                      form.preview_layout === p.layout &&
                      form.preview_panel === p.panel &&
                      form.preview_accent === p.accent
                    return (
                      <button
                        key={p.name}
                        type="button"
                        disabled={!canCardControls}
                        onClick={() =>
                          set({ preview_layout: p.layout, preview_panel: p.panel, preview_accent: p.accent })
                        }
                        className={`px-3.5 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                          active
                            ? 'bg-primary-500 text-paper border-primary-500'
                            : 'bg-surface text-secondary-700 border-line hover:border-primary-500 hover:text-secondary-900'
                        } ${!canCardControls ? 'opacity-60 cursor-not-allowed' : ''}`}
                      >
                        {p.name}
                      </button>
                    )
                  })}
                </div>
                <p className="text-xs text-secondary-500 mt-2">
                  One-click starting points — fine-tune with the controls below, then Save.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <Select
                  label="Layout"
                  value={form.preview_layout}
                  options={LAYOUT_OPTIONS}
                  onChange={(v) => set({ preview_layout: v })}
                  disabled={!canCardControls}
                />
                <Select
                  label="Panel colour"
                  value={form.preview_panel}
                  options={PANEL_OPTIONS}
                  onChange={(v) => set({ preview_panel: v })}
                  disabled={!canCardControls}
                />
                <Select
                  label="Accent style"
                  value={form.preview_accent}
                  options={ACCENT_OPTIONS}
                  onChange={(v) => set({ preview_accent: v })}
                  disabled={!canCardControls}
                />
              </div>

              <div className="mt-6 space-y-4 border-t border-secondary-100 pt-5">
                <Toggle
                  label="Always use my brand colours"
                  hint="Ignore the colours we detect on the page and use the palette above."
                  checked={form.force_brand_colors}
                  onChange={(v) => set({ force_brand_colors: v })}
                />
                <Toggle
                  label="Hide the MetaView mark"
                  hint={
                    canHideWatermark
                      ? 'Remove the “metaview preview” footer from your cards.'
                      : 'Growth feature — remove the “metaview preview” footer.'
                  }
                  checked={form.hide_watermark && canHideWatermark}
                  onChange={(v) => set({ hide_watermark: v })}
                  disabled={!canHideWatermark}
                />
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">
                    Install product name
                  </label>
                  <input
                    type="text"
                    value={form.white_label_name || ''}
                    disabled={!canWhiteLabel}
                    placeholder={canWhiteLabel ? 'Shown on the Worker, plugin, and GTM container' : 'Agency feature'}
                    onChange={(e) => set({ white_label_name: e.target.value })}
                    className="w-full px-3 py-2 border border-secondary-300 rounded-lg disabled:bg-secondary-50"
                  />
                  <p className="text-xs text-secondary-500 mt-1">
                    {canWhiteLabel
                      ? 'Replaces “MyMetaView” on downloaded install files. Cards still follow the watermark toggle.'
                      : 'Agency feature — put your own name on downloaded install files.'}
                  </p>
                </div>
              </div>
            </Card>
          </div>

          {/* Live preview */}
          <div className="lg:col-span-1">
            <Card className="lg:sticky lg:top-24">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-secondary-900">Live preview</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={redrawNow}
                  disabled={previewLoading}
                  icon={<ArrowPathIcon className={`w-4 h-4 ${previewLoading ? 'animate-spin' : ''}`} />}
                >
                  Refresh
                </Button>
              </div>

              <div
                className="relative rounded-lg overflow-hidden border border-secondary-200 bg-secondary-100"
                style={{ aspectRatio: '1200 / 630' }}
              >
                {previewUrl && (
                  <img
                    src={previewUrl}
                    alt="Sample share card"
                    className={`w-full h-full object-contain transition-opacity ${
                      previewLoading ? 'opacity-40' : 'opacity-100'
                    }`}
                  />
                )}
                {!previewUrl && !previewError && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="animate-pulse text-sm text-secondary-500">Rendering…</div>
                  </div>
                )}
                {previewLoading && previewUrl && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <ArrowPathIcon className="w-6 h-6 text-secondary-500 animate-spin" />
                  </div>
                )}
                {previewError && !previewUrl && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center">
                    <p className="text-sm text-secondary-500">Couldn’t render the preview.</p>
                    <Button variant="secondary" size="sm" onClick={redrawNow}>
                      Try again
                    </Button>
                  </div>
                )}
              </div>

              <p className="text-xs text-secondary-500 mt-3">
                {dirty
                  ? 'Showing your unsaved changes — drawn the way real cards will be. Save to apply them.'
                  : 'A sample card drawn the way your real cards will be.'}
                {!canCardControls && ' Layout controls apply on Growth and above.'}
              </p>

              <div className="mt-4">
                <Button
                  fullWidth
                  onClick={handleSave}
                  loading={saving}
                  disabled={(!dirty && !saving) || !colorsValid}
                >
                  {!colorsValid ? 'Fix the colours to save' : dirty ? 'Save changes' : 'Saved'}
                </Button>
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  )
}
