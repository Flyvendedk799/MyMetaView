import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRightIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  GlobeAltIcon,
  PaintBrushIcon,
  Cog6ToothIcon,
  SparklesIcon,
  DocumentTextIcon,
  PlusIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { fetchDomains, createSite, type Domain, type PublishedSiteCreate } from '../../api/client'

type Step = 'domain' | 'template' | 'branding' | 'settings' | 'complete'

const TEMPLATES = [
  {
    id: 'default',
    name: 'Modern Blog',
    description: 'Clean and modern blog layout with responsive design, social sharing, and SEO optimization.',
    features: ['Responsive', 'SEO Ready', 'Social Sharing', 'Dark/Light Mode'],
    preview: '/templates/default-preview.png',
    category: 'Blog',
  },
]

const COLOR_PRESETS = [
  { name: 'Sunset', primary: '#f97316', secondary: '#1f2937', accent: '#fbbf24' },
  { name: 'Ocean', primary: '#0ea5e9', secondary: '#0f172a', accent: '#14b8a6' },
  { name: 'Forest', primary: '#22c55e', secondary: '#14532d', accent: '#a3e635' },
  { name: 'Berry', primary: '#8b5cf6', secondary: '#1e1b4b', accent: '#f472b6' },
  { name: 'Coral', primary: '#f43f5e', secondary: '#1f2937', accent: '#fb923c' },
  { name: 'Midnight', primary: '#6366f1', secondary: '#0f172a', accent: '#38bdf8' },
]

export default function CreateSite() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState<Step>('domain')
  const [domains, setDomains] = useState<Domain[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  
  // Form data
  const [selectedDomainId, setSelectedDomainId] = useState<number | null>(null)
  const [siteName, setSiteName] = useState('')
  const [siteDescription, setSiteDescription] = useState('')
  const [templateId, setTemplateId] = useState('default')
  const [selectedPreset, setSelectedPreset] = useState(COLOR_PRESETS[0])
  const [publishImmediately, setPublishImmediately] = useState(true) // Default to publishing immediately
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    loadDomains()
  }, [])

  async function loadDomains() {
    try {
      setLoading(true)
      const data = await fetchDomains()
      // Filter to only verified domains that aren't already in use
      const verified = data.filter(d => d.status === 'verified' && !d.site_id)
      setDomains(verified)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load domains')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit() {
    if (!selectedDomainId || !siteName.trim()) {
      setError('Please fill in all required fields')
      return
    }

    try {
      setIsSubmitting(true)
      setError('')
      
      const siteData: PublishedSiteCreate = {
        name: siteName.trim(),
        domain_id: selectedDomainId,
        template_id: templateId,
        status: publishImmediately ? 'published' : 'draft',
        is_active: true,
      }
      
      const site = await createSite(siteData)
      
      // If publishing immediately, the site will be accessible via the domain right away
      setCurrentStep('complete')
      
      // Redirect after 2 seconds
      setTimeout(() => {
        navigate(`/app/sites/${site.id}`)
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create site')
    } finally {
      setIsSubmitting(false)
    }
  }

  const steps = [
    { id: 'domain', name: 'Domain', icon: GlobeAltIcon },
    { id: 'template', name: 'Template', icon: DocumentTextIcon },
    { id: 'branding', name: 'Branding', icon: PaintBrushIcon },
    { id: 'settings', name: 'Confirm', icon: Cog6ToothIcon },
  ]

  const stepIndex = steps.findIndex(s => s.id === currentStep)

  const selectedDomain = domains.find(d => d.id === selectedDomainId)

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="heading-3 mb-2">Create New Site</h1>
        <p className="text-muted">Set up your white-label blog in minutes</p>
      </div>

      {/* Step Indicator */}
      <Card className="mb-6">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => {
            const StepIcon = step.icon
            const isActive = index === stepIndex
            const isCompleted = index < stepIndex
            
            return (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                    isCompleted ? 'bg-success-500 text-paper' :
                    isActive ? 'bg-primary-500 text-paper shadow-card' :
                    'bg-secondary-100 text-secondary-400'
                  }`}>
                    {isCompleted ? (
                      <CheckCircleIcon className="w-6 h-6" />
                    ) : (
                      <StepIcon className="w-6 h-6" />
                    )}
                  </div>
                  <span className={`text-sm mt-2 ${
                    isActive ? 'font-semibold text-primary-500' :
                    isCompleted ? 'font-medium text-success-600' :
                    'text-secondary-400'
                  }`}>
                    {step.name}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`h-1 flex-1 mx-4 rounded-full ${
                    isCompleted ? 'bg-success-500' : 'bg-secondary-200'
                  }`} />
                )}
              </div>
            )
          })}
        </div>
      </Card>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-100">
          <p className="text-error-600">{error}</p>
        </Card>
      )}

      {/* Step Content */}
      <Card className="min-h-[400px]">
        {currentStep === 'domain' && (
          <div className="space-y-6">
            <div>
              <h2 className="heading-4 mb-2">Select Your Domain</h2>
              <p className="text-muted">Choose a verified domain to host your site</p>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-16">
                <div className="w-10 h-10 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : domains.length === 0 ? (
              <div className="text-center py-12">
                <GlobeAltIcon className="w-16 h-16 text-secondary-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-secondary-900 mb-2">No Domains Available</h3>
                <p className="text-secondary-500 mb-6">You need a verified domain to create a site</p>
                <Button onClick={() => navigate('/app/domains')}>
                  Add & Verify Domain
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3">
                  {domains.map((domain) => (
                    <button
                      key={domain.id}
                      onClick={() => setSelectedDomainId(domain.id)}
                      className={`text-left p-4 border-2 rounded-xl transition-all ${
                        selectedDomainId === domain.id
                          ? 'border-primary-500 bg-brand-50 shadow-card'
                          : 'border-secondary-200 hover:border-primary-300 hover:bg-secondary-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                            selectedDomainId === domain.id ? 'bg-primary-500 text-paper' : 'bg-secondary-100 text-secondary-600'
                          }`}>
                            <GlobeAltIcon className="w-5 h-5" />
                          </div>
                          <div>
                            <p className="font-mono text-[13px] font-semibold text-secondary-900">{domain.name}</p>
                            <p className="text-sm text-muted">Verified and ready to use</p>
                          </div>
                        </div>
                        {selectedDomainId === domain.id && (
                          <CheckCircleIcon className="w-6 h-6 text-primary-500" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>
                
                {/* Add new domain button */}
                <div className="pt-4 border-t border-line">
                  <Button
                    variant="secondary"
                    onClick={() => navigate('/app/domains')}
                    className="w-full"
                  >
                    <PlusIcon className="w-4 h-4 mr-2" />
                    Add New Domain
                  </Button>
                </div>
              </div>
            )}

            <div className="flex justify-end pt-6 border-t border-line">
              <Button
                onClick={() => setCurrentStep('template')}
                disabled={!selectedDomainId}
              >
                Continue
                <ArrowRightIcon className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {currentStep === 'template' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-secondary mb-2">Choose a Template</h2>
              <p className="text-muted">Select the design that best fits your content</p>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  onClick={() => setTemplateId(template.id)}
                  className={`text-left border-2 rounded-xl overflow-hidden transition-all ${
                    templateId === template.id
                      ? 'border-primary shadow-lg shadow-primary/10'
                      : 'border-secondary-200 hover:border-primary/50'
                  }`}
                >
                  <div className="flex flex-col md:flex-row">
                    <div className="w-full md:w-48 h-32 bg-secondary-100 flex items-center justify-center">
                      <DocumentTextIcon className="w-12 h-12 text-secondary-400" />
                    </div>
                    <div className="flex-1 p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="font-semibold text-lg text-secondary">{template.name}</h3>
                          <p className="text-sm text-muted mt-1">{template.description}</p>
                        </div>
                        {templateId === template.id && (
                          <CheckCircleIcon className="w-6 h-6 text-primary flex-shrink-0" />
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2 mt-3">
                        {template.features.map((feature) => (
                          <span
                            key={feature}
                            className="px-2 py-1 bg-secondary-100 text-secondary-600 text-xs rounded-full"
                          >
                            {feature}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex justify-between pt-6 border-t border-line">
              <Button variant="secondary" onClick={() => setCurrentStep('domain')}>
                <ArrowLeftIcon className="w-4 h-4 mr-2" />
                Back
              </Button>
              <Button onClick={() => setCurrentStep('branding')}>
                Continue
                <ArrowRightIcon className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {currentStep === 'branding' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-secondary mb-2">Configure Your Brand</h2>
              <p className="text-muted">Give your site a name and choose your colors</p>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-2">
                  Site Name *
                </label>
                <input
                  type="text"
                  value={siteName}
                  onChange={(e) => setSiteName(e.target.value)}
                  placeholder="My Awesome Blog"
                  className="w-full px-4 py-3 text-lg border border-secondary-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-2">
                  Description
                </label>
                <textarea
                  value={siteDescription}
                  onChange={(e) => setSiteDescription(e.target.value)}
                  placeholder="A brief description of your site..."
                  rows={2}
                  className="w-full px-4 py-3 border border-secondary-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-3">
                  Color Scheme
                </label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {COLOR_PRESETS.map((preset) => (
                    <button
                      key={preset.name}
                      onClick={() => setSelectedPreset(preset)}
                      className={`p-4 border-2 rounded-xl transition-all ${
                        selectedPreset.name === preset.name
                          ? 'border-primary shadow-lg'
                          : 'border-secondary-200 hover:border-primary/50'
                      }`}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div className="flex gap-1">
                          <div
                            className="w-6 h-6 rounded-full"
                            style={{ backgroundColor: preset.primary }}
                          />
                          <div
                            className="w-6 h-6 rounded-full"
                            style={{ backgroundColor: preset.secondary }}
                          />
                          <div
                            className="w-6 h-6 rounded-full"
                            style={{ backgroundColor: preset.accent }}
                          />
                        </div>
                        {selectedPreset.name === preset.name && (
                          <CheckCircleIcon className="w-5 h-5 text-primary ml-auto" />
                        )}
                      </div>
                      <p className="text-sm font-medium text-secondary-900">{preset.name}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-between pt-6 border-t border-line">
              <Button variant="secondary" onClick={() => setCurrentStep('template')}>
                <ArrowLeftIcon className="w-4 h-4 mr-2" />
                Back
              </Button>
              <Button onClick={() => setCurrentStep('settings')} disabled={!siteName.trim()}>
                Continue
                <ArrowRightIcon className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {currentStep === 'settings' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-secondary mb-2">Review & Create</h2>
              <p className="text-muted">Everything looks good? Let's launch your site!</p>
            </div>

            <div className="bg-secondary-50 rounded-2xl p-6 space-y-4">
              <div className="flex items-center gap-4 pb-4 border-b border-secondary-200">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-white text-xl font-bold"
                  style={{ backgroundColor: selectedPreset.primary }}
                >
                  {siteName.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-secondary">{siteName || 'Your Site'}</h3>
                  <p className="text-sm text-muted">{selectedDomain?.name}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-secondary-500">Domain:</span>
                  <span className="ml-2 font-medium">{selectedDomain?.name}</span>
                </div>
                <div>
                  <span className="text-secondary-500">Template:</span>
                  <span className="ml-2 font-medium">
                    {TEMPLATES.find(t => t.id === templateId)?.name}
                  </span>
                </div>
                <div>
                  <span className="text-secondary-500">Color Scheme:</span>
                  <span className="ml-2 font-medium">{selectedPreset.name}</span>
                </div>
                <div>
                  <span className="text-secondary-500">Status:</span>
                  <span className="ml-2 font-medium">
                    {publishImmediately ? 'Published (live)' : 'Draft (unpublished)'}
                  </span>
                </div>
              </div>
            </div>

            {/* Publish immediately option */}
            <div className="bg-secondary-50 border border-secondary-200 rounded-xl p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={publishImmediately}
                  onChange={(e) => setPublishImmediately(e.target.checked)}
                  className="mt-1 w-5 h-5 text-primary border-secondary-300 rounded focus:ring-primary"
                />
                <div className="flex-1">
                  <p className="font-medium text-secondary">Publish immediately</p>
                  <p className="text-sm text-muted mt-1">
                    {publishImmediately ? (
                      <>
                        Your site will be live at <span className="font-mono font-semibold text-primary">{selectedDomain?.name}</span> as soon as it's created.
                        You can still edit it after publishing.
                      </>
                    ) : (
                      <>
                        Your site will be created as a draft. You can add posts, pages, and customize
                        everything before publishing it live.
                      </>
                    )}
                  </p>
                </div>
              </label>
            </div>

            {publishImmediately && (
              <div className="bg-success-50 border border-success-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <SparklesIcon className="w-5 h-5 text-success-600 mt-0.5" />
                  <div>
                    <p className="text-success-900 font-medium">Site will be live immediately!</p>
                    <p className="text-sm text-success-700 mt-1">
                      Once created, visitors to <span className="font-mono font-semibold">{selectedDomain?.name}</span> will see your site.
                      Make sure your domain DNS is pointing to our servers.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-between pt-6 border-t border-line">
              <Button variant="secondary" onClick={() => setCurrentStep('branding')}>
                <ArrowLeftIcon className="w-4 h-4 mr-2" />
                Back
              </Button>
              <Button onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                    Creating...
                  </>
                ) : (
                  <>
                    <SparklesIcon className="w-4 h-4 mr-2" />
                    Create Site
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {currentStep === 'complete' && (
          <div className="text-center py-12">
            <div className="w-20 h-20 bg-success-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircleIcon className="w-12 h-12 text-success-600" />
            </div>
            <h2 className="text-3xl font-bold text-secondary mb-2">Site Created!</h2>
            {publishImmediately ? (
              <>
                <p className="text-lg text-muted mb-2">Your site is now live!</p>
                <p className="text-sm text-primary font-mono mb-6">{selectedDomain?.name}</p>
                <div className="bg-success-50 border border-success-200 rounded-lg p-4 mb-6 max-w-md mx-auto">
                  <p className="text-sm text-success-800">
                    Visitors can now access your site at this domain. Make sure your DNS is configured correctly.
                  </p>
                </div>
              </>
            ) : (
              <p className="text-lg text-muted mb-6">Your new site is ready to customize</p>
            )}
            <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-secondary-500 mt-4">Redirecting to your dashboard...</p>
          </div>
        )}
      </Card>
    </div>
  )
}
