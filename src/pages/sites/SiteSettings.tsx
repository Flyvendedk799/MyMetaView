import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { CheckIcon, PhotoIcon, XMarkIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import MediaPickerModal from '../../components/media/MediaPickerModal'
import {
  fetchSiteSettings,
  fetchSiteById,
  updateSiteSettings,
  updateSite,
  type SiteSettings,
  type SiteSettingsUpdate,
  type PublishedSite,
  type SiteMedia,
} from '../../api/client'

type SettingsTab = 'general' | 'seo' | 'analytics' | 'advanced'

export default function SiteSettings() {
  const { siteId } = useParams<{ siteId: string }>()
  const [site, setSite] = useState<PublishedSite | null>(null)
  const [settings, setSettings] = useState<SiteSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const [showSocialImageModal, setShowSocialImageModal] = useState(false)

  // Local form state
  const [siteName, setSiteName] = useState('')
  const [siteDescription, setSiteDescription] = useState('')
  const [metaTitle, setMetaTitle] = useState('')
  const [metaDescription, setMetaDescription] = useState('')
  const [metaKeywords, setMetaKeywords] = useState('')
  const [socialImage, setSocialImage] = useState('')
  const [twitterHandle, setTwitterHandle] = useState('')
  const [googleAnalyticsId, setGoogleAnalyticsId] = useState('')
  const [googleTagManagerId, setGoogleTagManagerId] = useState('')
  const [facebookPixelId, setFacebookPixelId] = useState('')
  const [customHeaderCode, setCustomHeaderCode] = useState('')
  const [customFooterCode, setCustomFooterCode] = useState('')
  const [customJs, setCustomJs] = useState('')
  const [enableSitemap, setEnableSitemap] = useState(true)
  const [enableRss, setEnableRss] = useState(true)
  const [noIndex, setNoIndex] = useState(false)
  const [language, setLanguage] = useState('en')
  const [timezone, setTimezone] = useState('UTC')

  useEffect(() => {
    if (siteId) {
      loadData()
    }
  }, [siteId])

  async function loadData() {
    if (!siteId) return
    try {
      setLoading(true)
      const [siteData, settingsData] = await Promise.all([
        fetchSiteById(parseInt(siteId)),
        fetchSiteSettings(parseInt(siteId)),
      ])
      
      setSite(siteData)
      setSettings(settingsData)
      
      // Populate form
      setSiteName(siteData.name || '')
      setSiteDescription(settingsData.site_description || '')
      // Meta fields come from site, not settings
      setMetaTitle(siteData.meta_title || '')
      setMetaDescription(siteData.meta_description || '')
      setMetaKeywords(siteData.meta_keywords || '')
      // Social fields from social_links
      setSocialImage(settingsData.social_links?.og_image || '')
      setTwitterHandle(settingsData.social_links?.twitter || '')
      setGoogleAnalyticsId(settingsData.google_analytics_id || '')
      setGoogleTagManagerId(settingsData.google_tag_manager_id || '')
      setFacebookPixelId(settingsData.facebook_pixel_id || '')
      setCustomHeaderCode(settingsData.header_code || '')
      setCustomFooterCode(settingsData.footer_code || '')
      setCustomJs('') // Not supported in backend
      setEnableSitemap(settingsData.sitemap_enabled !== false)
      setEnableRss(true) // Not supported in backend, default to true
      setNoIndex(false) // Site-wide noindex not supported, use per-page
      setLanguage(settingsData.language || 'en')
      setTimezone(settingsData.timezone || 'UTC')
    } catch (err) {
      console.error('Failed to load settings:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!siteId || !settings) return
    try {
      setSaving(true)

      // Update site (name and meta fields)
      if (site) {
        await updateSite(parseInt(siteId), {
          name: siteName,
          meta_title: metaTitle || null,
          meta_description: metaDescription || null,
          meta_keywords: metaKeywords || null,
        })
      }

      // Update settings with correct field names
      await updateSiteSettings(parseInt(siteId), {
        site_description: siteDescription || undefined,
        google_analytics_id: googleAnalyticsId || undefined,
        google_tag_manager_id: googleTagManagerId || undefined,
        facebook_pixel_id: facebookPixelId || undefined,
        header_code: customHeaderCode || undefined,
        footer_code: customFooterCode || undefined,
        sitemap_enabled: enableSitemap,
        language: language,
        timezone: timezone,
        social_links: {
          twitter: twitterHandle || undefined,
          og_image: socialImage || undefined,
        },
      } as SiteSettingsUpdate)

      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Failed to save settings:', err)
    } finally {
      setSaving(false)
    }
  }

  function handleSocialImageSelect(media: SiteMedia) {
    setSocialImage(media.file_path)
    setShowSocialImageModal(false)
  }

  const tabs: { id: SettingsTab; name: string }[] = [
    { id: 'general', name: 'General' },
    { id: 'seo', name: 'SEO' },
    { id: 'analytics', name: 'Analytics' },
    { id: 'advanced', name: 'Advanced' },
  ]

  if (loading) {
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
          <h1 className="text-2xl font-bold text-secondary">Settings</h1>
          <p className="text-muted">Configure your site settings</p>
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

      {/* Tabs */}
      <div className="flex border-b border-secondary-200 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-primary border-b-2 border-primary'
                : 'text-secondary-500 hover:text-secondary-700'
            }`}
          >
            {tab.name}
          </button>
        ))}
      </div>

      {/* General Settings */}
      {activeTab === 'general' && (
        <Card>
          <h3 className="font-semibold text-secondary-900 mb-6">General Settings</h3>
          <div className="space-y-6 max-w-2xl">
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Site Name
              </label>
              <input
                type="text"
                value={siteName}
                onChange={(e) => setSiteName(e.target.value)}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Site Description
              </label>
              <textarea
                value={siteDescription}
                onChange={(e) => setSiteDescription(e.target.value)}
                placeholder="A brief description of your site"
                rows={3}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="it">Italian</option>
                <option value="pt">Portuguese</option>
                <option value="nl">Dutch</option>
                <option value="ja">Japanese</option>
                <option value="zh">Chinese</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Timezone
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="UTC">UTC</option>
                <option value="America/New_York">Eastern Time</option>
                <option value="America/Chicago">Central Time</option>
                <option value="America/Denver">Mountain Time</option>
                <option value="America/Los_Angeles">Pacific Time</option>
                <option value="Europe/London">London</option>
                <option value="Europe/Paris">Paris</option>
                <option value="Europe/Berlin">Berlin</option>
                <option value="Asia/Tokyo">Tokyo</option>
                <option value="Asia/Shanghai">Shanghai</option>
              </select>
            </div>
          </div>
        </Card>
      )}

      {/* SEO Settings */}
      {activeTab === 'seo' && (
        <Card>
          <h3 className="font-semibold text-secondary-900 mb-6">SEO Settings</h3>
          <div className="space-y-6 max-w-2xl">
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Default Meta Title
                <span className="text-secondary-400 ml-2">({metaTitle.length}/70)</span>
              </label>
              <input
                type="text"
                value={metaTitle}
                onChange={(e) => setMetaTitle(e.target.value.slice(0, 70))}
                placeholder="Your Site | Tagline"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Default Meta Description
                <span className="text-secondary-400 ml-2">({metaDescription.length}/160)</span>
              </label>
              <textarea
                value={metaDescription}
                onChange={(e) => setMetaDescription(e.target.value.slice(0, 160))}
                placeholder="A brief description for search engines"
                rows={2}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Meta Keywords
              </label>
              <input
                type="text"
                value={metaKeywords}
                onChange={(e) => setMetaKeywords(e.target.value)}
                placeholder="keyword1, keyword2, keyword3"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Social Sharing Image
              </label>
              {socialImage ? (
                <div className="relative inline-block">
                  <img
                    src={socialImage}
                    alt="Social sharing"
                    className="w-64 h-32 object-cover rounded-lg border"
                  />
                  <button
                    onClick={() => setSocialImage('')}
                    className="absolute -top-2 -right-2 p-1 bg-error-500 text-white rounded-full"
                  >
                    <XMarkIcon className="w-3 h-3" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowSocialImageModal(true)}
                  className="w-64 h-32 border-2 border-dashed border-secondary-300 rounded-lg flex flex-col items-center justify-center text-secondary-400 hover:border-primary hover:text-primary transition-colors"
                >
                  <PhotoIcon className="w-8 h-8 mb-1" />
                  <span className="text-sm">1200 Ã— 630 recommended</span>
                </button>
              )}
              {socialImage && (
                <button
                  onClick={() => setShowSocialImageModal(true)}
                  className="mt-2 block text-sm text-primary hover:underline"
                >
                  Change Image
                </button>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Twitter Handle
              </label>
              <input
                type="text"
                value={twitterHandle}
                onChange={(e) => setTwitterHandle(e.target.value)}
                placeholder="@yourhandle"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="space-y-3 pt-4 border-t">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableSitemap}
                  onChange={(e) => setEnableSitemap(e.target.checked)}
                  className="w-4 h-4 text-primary border-secondary-300 rounded focus:ring-primary"
                />
                <span className="text-sm text-secondary-700">Enable XML Sitemap</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableRss}
                  onChange={(e) => setEnableRss(e.target.checked)}
                  className="w-4 h-4 text-primary border-secondary-300 rounded focus:ring-primary"
                />
                <span className="text-sm text-secondary-700">Enable RSS Feed</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={noIndex}
                  onChange={(e) => setNoIndex(e.target.checked)}
                  className="w-4 h-4 text-primary border-secondary-300 rounded focus:ring-primary"
                />
                <span className="text-sm text-secondary-700">
                  Discourage search engines from indexing this site
                </span>
              </label>
            </div>
          </div>
        </Card>
      )}

      {/* Analytics Settings */}
      {activeTab === 'analytics' && (
        <Card>
          <h3 className="font-semibold text-secondary-900 mb-6">Analytics & Tracking</h3>
          <div className="space-y-6 max-w-2xl">
            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Google Analytics ID
              </label>
              <input
                type="text"
                value={googleAnalyticsId}
                onChange={(e) => setGoogleAnalyticsId(e.target.value)}
                placeholder="G-XXXXXXXXXX or UA-XXXXXXXX-X"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-mono"
              />
              <p className="text-xs text-secondary-500 mt-1">
                Enter your Google Analytics 4 or Universal Analytics ID
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Google Tag Manager ID
              </label>
              <input
                type="text"
                value={googleTagManagerId}
                onChange={(e) => setGoogleTagManagerId(e.target.value)}
                placeholder="GTM-XXXXXXX"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-mono"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-secondary-700 mb-1">
                Facebook Pixel ID
              </label>
              <input
                type="text"
                value={facebookPixelId}
                onChange={(e) => setFacebookPixelId(e.target.value)}
                placeholder="XXXXXXXXXXXXXXXX"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-mono"
              />
            </div>
          </div>
        </Card>
      )}

      {/* Advanced Settings */}
      {activeTab === 'advanced' && (
        <div className="space-y-6">
          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Custom Header Code</h3>
            <textarea
              value={customHeaderCode}
              onChange={(e) => setCustomHeaderCode(e.target.value)}
              placeholder="<!-- Add custom HTML/scripts to <head> -->"
              rows={6}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            />
            <p className="text-xs text-secondary-500 mt-2">
              This code will be inserted before the closing &lt;/head&gt; tag
            </p>
          </Card>

          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Custom Footer Code</h3>
            <textarea
              value={customFooterCode}
              onChange={(e) => setCustomFooterCode(e.target.value)}
              placeholder="<!-- Add custom HTML/scripts before </body> -->"
              rows={6}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            />
            <p className="text-xs text-secondary-500 mt-2">
              This code will be inserted before the closing &lt;/body&gt; tag
            </p>
          </Card>

          <Card>
            <h3 className="font-semibold text-secondary-900 mb-4">Custom JavaScript</h3>
            <textarea
              value={customJs}
              onChange={(e) => setCustomJs(e.target.value)}
              placeholder="// Add custom JavaScript here"
              rows={6}
              className="w-full px-4 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            />
            <p className="text-xs text-secondary-500 mt-2">
              This JavaScript will be loaded after the page content
            </p>
          </Card>
        </div>
      )}

      {/* Social Image Modal */}
      {showSocialImageModal && siteId && (
        <MediaPickerModal
          isOpen={showSocialImageModal}
          onClose={() => setShowSocialImageModal(false)}
          onSelect={handleSocialImageSelect}
          siteId={parseInt(siteId)}
          title="Select Social Image"
        />
      )}
    </div>
  )
}
