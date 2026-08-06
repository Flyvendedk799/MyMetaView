import { useState, useEffect } from 'react'
import { PhotoIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useBrandSettings } from '../hooks/useBrandSettings'

export default function Brand() {
  const { settings, loading, error, updateSettings } = useBrandSettings()
  const [fontFamily, setFontFamily] = useState('Inter')
  const [accentColor, setAccentColor] = useState('#3FFFD3')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Update local state when settings load
  useEffect(() => {
    if (settings) {
      setFontFamily(settings.font_family)
      setAccentColor(settings.accent_color)
    }
  }, [settings])

  const handleSave = async () => {
    try {
      setIsSaving(true)
      setSaveError(null)
      setSaveSuccess(false)
      await updateSettings({
        font_family: fontFamily,
        accent_color: accentColor,
      })
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <p className="text-secondary-600">Customize how your URL previews appear across all platforms.</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {saveError && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {saveError}</p>
        </Card>
      )}

      {saveSuccess && (
        <Card className="mb-6 bg-success-50 border-success-200">
          <p className="text-success-800">Settings saved successfully!</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <p className="text-secondary-500">Loading brand settings...</p>
          </div>
        </Card>
      ) : settings ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Logo Upload */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary mb-4">Logo</h3>
              <div className="flex items-center space-x-6">
                <div className="w-24 h-24 bg-secondary-100 rounded-lg flex items-center justify-center border-2 border-dashed border-secondary-300">
                  {settings.logo_url ? (
                    <img src={settings.logo_url} alt="Logo" className="w-full h-full object-contain rounded-lg" />
                  ) : (
                    <PhotoIcon className="w-8 h-8 text-secondary-400" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-secondary-600 mb-2">
                    Upload your logo (PNG, SVG recommended)
                  </p>
                  <Button variant="secondary">Upload Logo</Button>
                </div>
              </div>
            </Card>

            {/* Brand Colors */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary mb-4">Brand Colors</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="w-full h-20 rounded-lg mb-2" style={{ backgroundColor: settings.primary_color }}></div>
                  <p className="text-sm font-medium text-secondary-700">Primary</p>
                  <p className="text-xs text-secondary-500">{settings.primary_color}</p>
                </div>
                <div>
                  <div className="w-full h-20 rounded-lg mb-2" style={{ backgroundColor: settings.secondary_color }}></div>
                  <p className="text-sm font-medium text-secondary-700">Secondary</p>
                  <p className="text-xs text-secondary-500">{settings.secondary_color}</p>
                </div>
                <div>
                  <div className="w-full h-20 rounded-lg mb-2" style={{ backgroundColor: settings.accent_color }}></div>
                  <p className="text-sm font-medium text-secondary-700">Accent</p>
                  <p className="text-xs text-secondary-500">{settings.accent_color}</p>
                </div>
                <div>
                  <div className="w-full h-20 bg-secondary-200 rounded-lg mb-2"></div>
                  <p className="text-sm font-medium text-secondary-700">Neutral</p>
                  <p className="text-xs text-secondary-500">#E5E7EB</p>
                </div>
              </div>
              <div className="mt-4">
                <label className="block text-sm font-medium text-secondary-700 mb-2">
                  Accent Color (Hex)
                </label>
                <input
                  type="text"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  placeholder="#3FFFD3"
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                />
              </div>
            </Card>

            {/* Font Selection */}
            <Card>
              <h3 className="text-lg font-semibold text-secondary mb-4">Typography</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-2">
                    Font Family
                  </label>
                  <select
                    value={fontFamily}
                    onChange={(e) => setFontFamily(e.target.value)}
                    className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                  >
                    <option value="Inter">Inter (Current)</option>
                    <option value="Roboto">Roboto</option>
                    <option value="Open Sans">Open Sans</option>
                    <option value="Lato">Lato</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-2">
                      Heading Size
                    </label>
                    <select className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all">
                      <option>Large</option>
                      <option>Medium</option>
                      <option>Small</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-secondary-700 mb-2">
                      Body Size
                    </label>
                    <select className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all">
                      <option>Medium</option>
                      <option>Large</option>
                      <option>Small</option>
                    </select>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Preview Card */}
          <div className="lg:col-span-1">
            <Card className="sticky top-24">
              <h3 className="text-lg font-semibold text-secondary mb-4">Preview</h3>
              <div className="border border-secondary-200 rounded-lg overflow-hidden bg-white">
                <div
                  className="aspect-video flex items-center justify-center"
                  style={{
                    background: `linear-gradient(to bottom right, ${settings.primary_color}33, ${settings.accent_color}33)`,
                  }}
                >
                  <div
                    className="w-16 h-16 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: settings.primary_color }}
                  >
                    <span className="text-white font-bold text-2xl">P</span>
                  </div>
                </div>
                <div className="p-4" style={{ fontFamily: settings.font_family }}>
                  <h4 className="font-semibold text-secondary-900 mb-1">Your Website Title</h4>
                  <p className="text-sm text-secondary-600 mb-2 line-clamp-2">
                    This is a preview of how your URL previews will appear on social media and messaging platforms.
                  </p>
                  <p className="text-xs text-secondary-500">example.com</p>
                </div>
              </div>
              <div className="mt-4">
                <Button className="w-full" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  )
}

