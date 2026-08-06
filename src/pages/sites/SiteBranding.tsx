import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { PhotoIcon, XMarkIcon, CheckIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import MediaPickerModal from '../../components/media/MediaPickerModal'
import {
  fetchSiteBranding,
  updateSiteBranding,
  type SiteBranding,
  type SiteBrandingUpdate,
  type SiteMedia,
} from '../../api/client'

const GOOGLE_FONTS = [
  'Inter',
  'Roboto',
  'Open Sans',
  'Lato',
  'Montserrat',
  'Poppins',
  'Source Sans Pro',
  'Nunito',
  'Raleway',
  'Merriweather',
  'Playfair Display',
  'PT Sans',
  'Oswald',
  'Work Sans',
  'DM Sans',
  'Space Grotesk',
  'Outfit',
  'Sora',
]

const COLOR_PRESETS = [
  { name: 'Orange', primary: '#f97316', secondary: '#1f2937', accent: '#fbbf24' },
  { name: 'Blue', primary: '#3b82f6', secondary: '#1e293b', accent: '#06b6d4' },
  { name: 'Green', primary: '#22c55e', secondary: '#14532d', accent: '#a3e635' },
  { name: 'Purple', primary: '#8b5cf6', secondary: '#1e1b4b', accent: '#f472b6' },
  { name: 'Red', primary: '#ef4444', secondary: '#1f2937', accent: '#fbbf24' },
  { name: 'Teal', primary: '#14b8a6', secondary: '#134e4a', accent: '#06b6d4' },
]

export default function SiteBranding() {
  const { siteId } = useParams<{ siteId: string }>()
  const [branding, setBranding] = useState<SiteBranding | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [showLogoModal, setShowLogoModal] = useState(false)
  const [showFaviconModal, setShowFaviconModal] = useState(false)

  useEffect(() => {
    if (siteId) loadBranding()
  }, [siteId])

  async function loadBranding() {
    if (!siteId) return
    try {
      setLoading(true)
      const data = await fetchSiteBranding(parseInt(siteId))
      setBranding(data)
    } catch (err) {
      console.error('Failed to load branding:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!siteId || !branding) return
    try {
      setSaving(true)
      await updateSiteBranding(parseInt(siteId), branding as SiteBrandingUpdate)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Failed to save branding:', err)
    } finally {
      setSaving(false)
    }
  }

  function updateBranding(updates: Partial<SiteBranding>) {
    if (!branding) return
    setBranding({ ...branding, ...updates })
  }

  function handleLogoSelect(media: SiteMedia) {
    updateBranding({ logo_url: media.file_path })
    setShowLogoModal(false)
  }

  function handleFaviconSelect(media: SiteMedia) {
    updateBranding({ favicon_url: media.file_path })
    setShowFaviconModal(false)
  }

  function applyPreset(preset: typeof COLOR_PRESETS[0]) {
    if (!branding) return
    setBranding({
      ...branding,
      primary_color: preset.primary,
      secondary_color: preset.secondary,
      accent_color: preset.accent,
    })
  }

  if (loading || !branding) {
    return (
      <Card>
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </Card>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-secondary">Branding</h1>
          <p className="text-muted">Customize the look and feel of your site</p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saved ? (
            <>
              <CheckIcon className="w-5 h-5 mr-2" />
              Saved!
            </>
          ) : saving ? (
            'Saving...'
          ) : (
            'Save Changes'
          )}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Colors */}
        <Card>
          <h3 className="font-semibold text-secondary-900 mb-4">Colors</h3>
          
          {/* Presets */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-secondary-700 mb-2">
              Quick Presets
            </label>
            <div className="flex flex-wrap gap-2">
              {COLOR_PRESETS.map((preset) => (
                <button
                  key={preset.name}
                  onClick={() => applyPreset(preset)}
                  className="flex items-center gap-2 px-3 py-2 border border-secondary-200 rounded-lg hover:border-primary transition-colors"
                >
                  <div className="flex gap-0.5">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: preset.primary }}
                    />
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: preset.secondary }}
                    />
                  </div>
                  <span className="text-sm">{preset.name}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Primary Color
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={branding.primary_color || '#f97316'}
                  onChange={(e) => updateBranding({ primary_color: e.target.value })}
                  className="w-12 h-10 border border-secondary-300 rounded cursor-pointer"
                />
                <input
                  type="text"
                  value={branding.primary_color || '#f97316'}
                  onChange={(e) => updateBranding({ primary_color: e.target.value })}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Secondary Color
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={branding.secondary_color || '#1f2937'}
                  onChange={(e) => updateBranding({ secondary_color: e.target.value })}
                  className="w-12 h-10 border border-secondary-300 rounded cursor-pointer"
                />
                <input
                  type="text"
                  value={branding.secondary_color || '#1f2937'}
                  onChange={(e) => updateBranding({ secondary_color: e.target.value })}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Accent Color
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={branding.accent_color || '#fbbf24'}
                  onChange={(e) => updateBranding({ accent_color: e.target.value })}
                  className="w-12 h-10 border border-secondary-300 rounded cursor-pointer"
                />
                <input
                  type="text"
                  value={branding.accent_color || '#fbbf24'}
                  onChange={(e) => updateBranding({ accent_color: e.target.value })}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Background Color
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={branding.background_color || '#ffffff'}
                  onChange={(e) => updateBranding({ background_color: e.target.value })}
                  className="w-12 h-10 border border-secondary-300 rounded cursor-pointer"
                />
                <input
                  type="text"
                  value={branding.background_color || '#ffffff'}
                  onChange={(e) => updateBranding({ background_color: e.target.value })}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Text Color
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={branding.text_color || '#1f2937'}
                  onChange={(e) => updateBranding({ text_color: e.target.value })}
                  className="w-12 h-10 border border-secondary-300 rounded cursor-pointer"
                />
                <input
                  type="text"
                  value={branding.text_color || '#1f2937'}
                  onChange={(e) => updateBranding({ text_color: e.target.value })}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Typography & Images */}
        <div className="space-y-6">
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Typography</h3>
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Font Family
              </label>
              <select
                value={branding.font_family || 'Inter'}
                onChange={(e) => updateBranding({ font_family: e.target.value })}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                style={{ fontFamily: branding.font_family || 'Inter' }}
              >
                {GOOGLE_FONTS.map((font) => (
                  <option key={font} value={font} style={{ fontFamily: font }}>
                    {font}
                  </option>
                ))}
              </select>
              <p className="text-xs text-secondary-500 mt-2">
                Preview: <span style={{ fontFamily: branding.font_family || 'Inter' }}>
                  The quick brown fox jumps over the lazy dog
                </span>
              </p>
            </div>
          </Card>

          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Logo</h3>
            {branding.logo_url ? (
              <div className="relative inline-block">
                <img
                  src={branding.logo_url}
                  alt="Site logo"
                  className="h-16 object-contain"
                />
                <button
                  onClick={() => updateBranding({ logo_url: '' })}
                  className="absolute -top-2 -right-2 p-1 bg-error-500 text-white rounded-full"
                >
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowLogoModal(true)}
                className="w-full h-24 border-2 border-dashed border-secondary-300 rounded-lg flex flex-col items-center justify-center text-secondary-400 hover:border-primary hover:text-primary transition-colors"
              >
                <PhotoIcon className="w-8 h-8 mb-1" />
                <span className="text-sm">Upload Logo</span>
              </button>
            )}
            {branding.logo_url && (
              <button
                onClick={() => setShowLogoModal(true)}
                className="mt-2 text-sm text-primary hover:underline"
              >
                Change Logo
              </button>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Favicon</h3>
            {branding.favicon_url ? (
              <div className="relative inline-block">
                <img
                  src={branding.favicon_url}
                  alt="Favicon"
                  className="w-16 h-16 object-contain"
                />
                <button
                  onClick={() => updateBranding({ favicon_url: '' })}
                  className="absolute -top-2 -right-2 p-1 bg-error-500 text-white rounded-full"
                >
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowFaviconModal(true)}
                className="w-16 h-16 border-2 border-dashed border-secondary-300 rounded-lg flex items-center justify-center text-secondary-400 hover:border-primary hover:text-primary transition-colors"
              >
                <PhotoIcon className="w-6 h-6" />
              </button>
            )}
            {branding.favicon_url && (
              <button
                onClick={() => setShowFaviconModal(true)}
                className="mt-2 text-sm text-primary hover:underline"
              >
                Change Favicon
              </button>
            )}
            <p className="text-xs text-secondary-500 mt-2">
              Recommended: 32x32 or 64x64 PNG
            </p>
          </Card>

          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Custom CSS</h3>
            <textarea
              value={branding.custom_css || ''}
              onChange={(e) => updateBranding({ custom_css: e.target.value })}
              placeholder="/* Add custom CSS here */"
              rows={6}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            />
            <p className="text-xs text-secondary-500 mt-2">
              Add custom CSS to override template styles
            </p>
          </Card>
        </div>
      </div>

      {/* Color Preview */}
      <Card className="mt-6">
        <h3 className="font-semibold text-secondary-900 mb-4">Preview</h3>
        <div
          className="p-6 rounded-lg"
          style={{
            backgroundColor: branding.background_color || '#ffffff',
            fontFamily: branding.font_family || 'Inter',
          }}
        >
          <div className="flex items-center gap-4 mb-4">
            {branding.logo_url ? (
              <img src={branding.logo_url} alt="" className="h-8" />
            ) : (
              <div
                className="text-xl font-bold"
                style={{ color: branding.primary_color || '#f97316' }}
              >
                Your Site
              </div>
            )}
            <nav className="flex gap-4 ml-auto">
              <span style={{ color: branding.text_color || '#1f2937' }}>Home</span>
              <span style={{ color: branding.text_color || '#1f2937' }}>About</span>
              <span style={{ color: branding.primary_color || '#f97316' }}>Contact</span>
            </nav>
          </div>
          <h1
            className="text-2xl font-bold mb-2"
            style={{ color: branding.secondary_color || '#1f2937' }}
          >
            Sample Heading
          </h1>
          <p style={{ color: branding.text_color || '#1f2937' }}>
            This is how your text will look on the site. The colors and fonts you choose
            will be applied consistently across all pages.
          </p>
          <button
            className="mt-4 px-4 py-2 rounded-lg text-white"
            style={{ backgroundColor: branding.primary_color || '#f97316' }}
          >
            Sample Button
          </button>
          <span
            className="ml-3 px-3 py-1 rounded-full text-sm"
            style={{
              backgroundColor: branding.accent_color || '#fbbf24',
              color: branding.secondary_color || '#1f2937',
            }}
          >
            Accent Badge
          </span>
        </div>
      </Card>

      {/* Media Modals */}
      {showLogoModal && siteId && (
        <MediaPickerModal
          isOpen={showLogoModal}
          onClose={() => setShowLogoModal(false)}
          onSelect={handleLogoSelect}
          siteId={parseInt(siteId)}
          title="Select Logo"
        />
      )}

      {showFaviconModal && siteId && (
        <MediaPickerModal
          isOpen={showFaviconModal}
          onClose={() => setShowFaviconModal(false)}
          onSelect={handleFaviconSelect}
          siteId={parseInt(siteId)}
          title="Select Favicon"
        />
      )}
    </div>
  )
}
