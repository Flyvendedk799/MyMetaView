import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowDownTrayIcon,
  ArrowTopRightOnSquareIcon,
  ArrowPathIcon,
  BoltIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  GlobeAltIcon,
  InformationCircleIcon,
  SignalIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Alert from '../components/ui/Alert'
import CodeBlock from '../components/ui/CodeBlock'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonList } from '../components/ui/Skeleton'
import {
  downloadInstallArtifact,
  fetchInstallConfig,
  verifyInstall,
  type InstallArtifact,
  type InstallConfig,
  type InstallDomainStatus,
  type VerifyInstallResponse,
} from '../api/client'

// ---------------------------------------------------------------------------
// Platform catalogue
// ---------------------------------------------------------------------------

interface PlatformContext {
  tag: string
  snippetUrl: string
  domain: string
}

interface DeepLink {
  href: string
  label: string
}

interface Platform {
  id: string
  name: string
  icon: string
  tagline: string
  /** A download is genuinely one click; a copy is one click plus a paste. */
  kind: 'download' | 'copy'
  artifact?: InstallArtifact
  downloadLabel?: string
  recommended?: boolean
  steps: (ctx: PlatformContext) => string[]
  code?: (ctx: PlatformContext) => string
  codeLabel?: string
  deepLink?: (ctx: PlatformContext) => DeepLink | null
  note?: string
}

const PLATFORMS: Platform[] = [
  {
    id: 'wordpress',
    name: 'WordPress',
    icon: '🟦',
    tagline: 'One-click plugin',
    kind: 'download',
    artifact: 'wordpress-plugin',
    downloadLabel: 'Download plugin (.zip)',
    steps: () => [
      'Download the plugin — it already knows your domain, so there is nothing to configure.',
      'In WordPress, go to Plugins → Add New → Upload Plugin and pick the file.',
      'Click Install Now, then Activate.',
    ],
    deepLink: ({ domain }) =>
      domain
        ? {
            href: `https://${domain}/wp-admin/plugin-install.php?tab=upload`,
            label: 'Open your WordPress upload page',
          }
        : null,
  },
  {
    id: 'gtm',
    name: 'Google Tag Manager',
    icon: '🏷️',
    tagline: 'One-click container import',
    kind: 'download',
    artifact: 'gtm-container',
    downloadLabel: 'Download container (.json)',
    steps: () => [
      'Download the container file below.',
      'In Tag Manager, go to Admin → Import Container and select it.',
      'Choose "Merge" so your existing tags are kept, then publish.',
    ],
    deepLink: () => ({ href: 'https://tagmanager.google.com/', label: 'Open Tag Manager' }),
    note: 'The container adds a single Custom HTML tag firing on All Pages.',
  },
  {
    id: 'cloudflare',
    name: 'Cloudflare',
    icon: '⚡',
    tagline: 'Edge injection — most reliable',
    kind: 'download',
    artifact: 'cloudflare-worker',
    downloadLabel: 'Download worker (.js)',
    recommended: true,
    steps: () => [
      'Download the worker below.',
      'In Cloudflare, go to Workers & Pages → Create → Worker, paste the file, and Deploy.',
      'Add a route pointing at your site so the worker sits in front of it.',
    ],
    deepLink: () => ({ href: 'https://dash.cloudflare.com/', label: 'Open Cloudflare dashboard' }),
    note:
      'This one adds the tags server-side, so crawlers that never run JavaScript still see them. If you are on Cloudflare, prefer it over the script.',
  },
  {
    id: 'shopify',
    name: 'Shopify',
    icon: '🛍️',
    tagline: 'Paste into your theme',
    kind: 'copy',
    steps: () => [
      'In Shopify admin, go to Online Store → Themes → ⋯ → Edit code.',
      'Open layout/theme.liquid.',
      'Paste the tag just before the closing </head> tag, then Save.',
    ],
    deepLink: () => ({ href: 'https://admin.shopify.com/', label: 'Open Shopify admin' }),
  },
  {
    id: 'webflow',
    name: 'Webflow',
    icon: '🌊',
    tagline: 'Paste into custom code',
    kind: 'copy',
    steps: () => [
      'Open Site settings → Custom code.',
      'Paste the tag into the "Head code" field.',
      'Save, then publish your site.',
    ],
    deepLink: () => ({ href: 'https://webflow.com/dashboard', label: 'Open Webflow dashboard' }),
  },
  {
    id: 'squarespace',
    name: 'Squarespace',
    icon: '⬛',
    tagline: 'Paste into code injection',
    kind: 'copy',
    steps: () => [
      'Open Settings → Developer Tools → Code Injection.',
      'Paste the tag into the "Header" field.',
      'Save.',
    ],
    deepLink: () => ({ href: 'https://account.squarespace.com/', label: 'Open Squarespace' }),
  },
  {
    id: 'wix',
    name: 'Wix',
    icon: '🟨',
    tagline: 'Paste into custom code',
    kind: 'copy',
    steps: () => [
      'Open Settings → Custom Code → Add Custom Code.',
      'Paste the tag, set it to load in the Head, and apply it to all pages.',
      'Apply, then publish.',
    ],
    deepLink: () => ({ href: 'https://manage.wix.com/', label: 'Open Wix dashboard' }),
  },
  {
    id: 'framer',
    name: 'Framer',
    icon: '🖼️',
    tagline: 'Paste into custom code',
    kind: 'copy',
    steps: () => [
      'Open Site Settings → General → Custom Code.',
      'Paste the tag into "Start of <head> tag".',
      'Save, then publish.',
    ],
    deepLink: () => ({ href: 'https://framer.com/projects/', label: 'Open Framer projects' }),
  },
  {
    id: 'nextjs',
    name: 'Next.js',
    icon: '▲',
    tagline: 'Add the Script component',
    kind: 'copy',
    codeLabel: 'app/layout.tsx',
    code: ({ snippetUrl, domain }) => `import Script from 'next/script'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Script
          src="${snippetUrl}"
          data-site="${domain}"
          strategy="afterInteractive"
        />
      </body>
    </html>
  )
}`,
    steps: () => [
      'Add the Script component to your root layout.',
      'Deploy.',
    ],
  },
  {
    id: 'nuxt',
    name: 'Nuxt',
    icon: '💚',
    tagline: 'Add it to your config',
    kind: 'copy',
    codeLabel: 'nuxt.config.ts',
    code: ({ snippetUrl, domain }) => `export default defineNuxtConfig({
  app: {
    head: {
      script: [
        { src: '${snippetUrl}', 'data-site': '${domain}', defer: true },
      ],
    },
  },
})`,
    steps: () => ['Add the script entry to your Nuxt config.', 'Deploy.'],
  },
  {
    id: 'html',
    name: 'Plain HTML',
    icon: '📄',
    tagline: 'Paste into <head>',
    kind: 'copy',
    steps: () => [
      'Paste the tag into the <head> of every page you want previews for.',
      'If your site uses a shared header or template, adding it there covers the whole site.',
    ],
  },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelative(iso: string | null): string {
  if (!iso) return 'never'
  // Timestamps come from the API as naive UTC.
  const stamp = /[Z+]|-\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`
  const then = new Date(stamp).getTime()
  if (Number.isNaN(then)) return 'unknown'

  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

function buildTag(snippetUrl: string, domain: string): string {
  const site = domain ? ` data-site="${domain}"` : ''
  return `<script src="${snippetUrl}"${site} defer></script>`
}

function InstallBadge({ domain }: { domain: InstallDomainStatus | undefined }) {
  if (!domain) return null
  if (domain.snippet_live) {
    return (
      <Badge variant="success" icon={<SignalIcon className="w-3.5 h-3.5" />}>
        Installed
      </Badge>
    )
  }
  return <Badge variant="secondary">Not detected yet</Badge>
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Install() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<InstallConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [selectedDomainId, setSelectedDomainId] = useState<number | null>(null)
  const [platformId, setPlatformId] = useState<string>(PLATFORMS[0].id)

  const [downloading, setDownloading] = useState<InstallArtifact | null>(null)
  const [downloadError, setDownloadError] = useState('')

  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<VerifyInstallResponse | null>(null)
  const [verifyError, setVerifyError] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await fetchInstallConfig()
      setConfig(data)
      setSelectedDomainId((current) => {
        if (current !== null && data.domains.some((d) => d.id === current)) return current
        // Default to a domain that still needs the snippet — that is the one
        // the visitor is most likely here for.
        const pending = data.domains.find((d) => !d.snippet_live)
        return (pending ?? data.domains[0])?.id ?? null
      })
      setLoadError('')
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load install details')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const domains = useMemo(() => config?.domains ?? [], [config])
  const selectedDomain = useMemo(
    () => domains.find((d) => d.id === selectedDomainId),
    [domains, selectedDomainId]
  )
  const platform = useMemo(
    () => PLATFORMS.find((p) => p.id === platformId) ?? PLATFORMS[0],
    [platformId]
  )

  const ctx: PlatformContext = useMemo(
    () => ({
      snippetUrl: config?.snippet_url ?? '',
      domain: selectedDomain?.name ?? '',
      tag: buildTag(config?.snippet_url ?? '', selectedDomain?.name ?? ''),
    }),
    [config, selectedDomain]
  )

  const handleDownload = async (artifact: InstallArtifact) => {
    setDownloading(artifact)
    setDownloadError('')
    try {
      await downloadInstallArtifact(artifact, selectedDomainId ?? undefined)
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloading(null)
    }
  }

  const handleVerify = async () => {
    if (selectedDomainId === null) return
    setVerifying(true)
    setVerifyError('')
    setVerifyResult(null)
    try {
      const result = await verifyInstall({ domain_id: selectedDomainId })
      setVerifyResult(result)
      // A successful check may have been driven by a heartbeat that landed
      // after the page loaded, so refresh the badges too.
      load()
    } catch (err) {
      setVerifyError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <Card>
        <SkeletonList count={4} />
      </Card>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Install</h1>
        <p className="text-muted">
          Add MyMetaView to your site, then confirm it is working. Most platforms take about a minute.
        </p>
      </div>

      {loadError && (
        <Card className="mb-6" padding="md">
          <Alert variant="error">{loadError}</Alert>
        </Card>
      )}

      {domains.length === 0 ? (
        <Card>
          <EmptyState
            icon={<GlobeAltIcon className="w-12 h-12" />}
            title="Connect a domain first"
            description="The snippet is tied to a domain, so add one before installing. It only takes a couple of minutes."
            action={{
              label: 'Go to Domains',
              onClick: () => {
                navigate('/app/domains')
              },
            }}
          />
        </Card>
      ) : (
        <>
          {/* Domain picker + live status */}
          <Card className="mb-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex-1 min-w-[240px]">
                <label
                  htmlFor="install-domain"
                  className="block text-sm font-semibold text-secondary mb-2"
                >
                  Installing on
                </label>
                {domains.length === 1 ? (
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-secondary">{domains[0].name}</span>
                    <InstallBadge domain={domains[0]} />
                  </div>
                ) : (
                  <div className="flex items-center gap-3 flex-wrap">
                    <select
                      id="install-domain"
                      value={selectedDomainId ?? ''}
                      onChange={(e) => {
                        setSelectedDomainId(Number(e.target.value))
                        setVerifyResult(null)
                        setVerifyError('')
                      }}
                      className="px-3 py-2 border border-secondary-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      {domains.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                        </option>
                      ))}
                    </select>
                    <InstallBadge domain={selectedDomain} />
                  </div>
                )}
                {selectedDomain?.snippet_last_seen_at && (
                  <p className="text-xs text-secondary-500 mt-2">
                    Last seen {formatRelative(selectedDomain.snippet_last_seen_at)}
                    {selectedDomain.snippet_version && ` · snippet v${selectedDomain.snippet_version}`}
                  </p>
                )}
              </div>

              <Button
                onClick={handleVerify}
                loading={verifying}
                disabled={selectedDomainId === null}
                variant="secondary"
                icon={<ArrowPathIcon className="w-4 h-4" />}
              >
                Check installation
              </Button>
            </div>

            {selectedDomain && !selectedDomain.verified && (
              <div className="mt-4">
                <Alert variant="warning">
                  <span>
                    {selectedDomain.name} is not verified yet, so previews will fall back to
                    placeholders even once the snippet is in place.{' '}
                    <Link to="/app/domains" className="underline font-medium">
                      Verify the domain
                    </Link>
                    .
                  </span>
                </Alert>
              </div>
            )}

            {selectedDomain?.snippet_outdated && (
              <div className="mt-4">
                <Alert variant="info">
                  This domain is running snippet v{selectedDomain.snippet_version}. The current
                  version is v{config?.snippet_version}. If you pasted the tag by hand, no action is
                  needed — it updates itself. Bundled copies should be refreshed.
                </Alert>
              </div>
            )}

            {verifyError && (
              <div className="mt-4">
                <Alert variant="error">{verifyError}</Alert>
              </div>
            )}

            {verifyResult && (
              <div className="mt-4">
                <Alert variant={verifyResult.ok ? 'success' : 'warning'}>
                  <div>
                    <p className="font-medium">{verifyResult.message}</p>
                    {verifyResult.hint && (
                      <p className="text-sm mt-1 opacity-90">{verifyResult.hint}</p>
                    )}
                    <ul className="text-sm mt-2 space-y-0.5 opacity-90">
                      <li className="flex items-center gap-1.5">
                        {verifyResult.snippet_found ? (
                          <CheckCircleIcon className="w-4 h-4 flex-shrink-0" />
                        ) : (
                          <XCircleIcon className="w-4 h-4 flex-shrink-0" />
                        )}
                        Tag found in the page source
                      </li>
                      <li className="flex items-center gap-1.5">
                        {verifyResult.heartbeat_seen ? (
                          <CheckCircleIcon className="w-4 h-4 flex-shrink-0" />
                        ) : (
                          <XCircleIcon className="w-4 h-4 flex-shrink-0" />
                        )}
                        Snippet reported in from a real page view
                        {verifyResult.heartbeat_at && ` (${formatRelative(verifyResult.heartbeat_at)})`}
                      </li>
                    </ul>
                    <p className="text-xs mt-2 opacity-75 break-all">
                      Checked {verifyResult.checked_url}
                    </p>
                  </div>
                </Alert>
              </div>
            )}
          </Card>

          {/* Platform picker */}
          <Card className="mb-6">
            <h2 className="text-lg font-semibold text-secondary mb-1">Choose your platform</h2>
            <p className="text-sm text-secondary-600 mb-4">
              We will generate the exact file or snippet for it.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {PLATFORMS.map((p) => {
                const active = p.id === platform.id
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setPlatformId(p.id)
                      setDownloadError('')
                    }}
                    aria-pressed={active}
                    className={`relative text-left p-3 rounded-lg border-2 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1 ${
                      active
                        ? 'border-primary bg-brand-50'
                        : 'border-secondary-200 hover:border-secondary-300 bg-white'
                    }`}
                  >
                    <div className="text-xl mb-1" aria-hidden="true">
                      {p.icon}
                    </div>
                    <div className="text-sm font-semibold text-secondary leading-tight">
                      {p.name}
                    </div>
                    <div className="text-2xs text-secondary-500 mt-0.5 leading-tight">
                      {p.tagline}
                    </div>
                    {p.recommended && (
                      <span className="absolute top-2 right-2">
                        <BoltIcon className="w-4 h-4 text-warning-700" aria-label="Recommended" />
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </Card>

          {/* Selected platform */}
          <Card className="mb-6">
            <div className="flex items-start gap-3 mb-5">
              <span className="text-2xl leading-none" aria-hidden="true">
                {platform.icon}
              </span>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-secondary">
                  Install on {platform.name}
                </h2>
                {platform.kind === 'download' && (
                  <p className="text-sm text-secondary-600 mt-0.5">
                    Generated for {ctx.domain} — nothing to configure.
                  </p>
                )}
              </div>
              {platform.recommended && <Badge variant="warning">Most reliable</Badge>}
            </div>

            <ol className="space-y-3 mb-5">
              {platform.steps(ctx).map((step, index) => (
                <li key={index} className="flex gap-3">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-brand-100 text-primary-500 text-xs font-semibold flex items-center justify-center">
                    {index + 1}
                  </span>
                  <span className="text-sm text-secondary-700 pt-0.5">{step}</span>
                </li>
              ))}
            </ol>

            {platform.kind === 'download' && platform.artifact && (
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <Button
                  onClick={() => handleDownload(platform.artifact!)}
                  loading={downloading === platform.artifact}
                  icon={<ArrowDownTrayIcon className="w-4 h-4" />}
                >
                  {platform.downloadLabel}
                </Button>
                {platform.deepLink?.(ctx) && (
                  <a
                    href={platform.deepLink(ctx)!.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
                  >
                    {platform.deepLink(ctx)!.label}
                    <ArrowTopRightOnSquareIcon className="w-4 h-4" />
                  </a>
                )}
              </div>
            )}

            {platform.kind === 'copy' && (
              <>
                <CodeBlock
                  code={platform.code ? platform.code(ctx) : ctx.tag}
                  label={platform.codeLabel}
                  copyLabel={platform.code ? 'Copy code' : 'Copy tag'}
                  wrap={!platform.code}
                  className="mb-4"
                />
                {platform.deepLink?.(ctx) && (
                  <a
                    href={platform.deepLink(ctx)!.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline mb-4"
                  >
                    {platform.deepLink(ctx)!.label}
                    <ArrowTopRightOnSquareIcon className="w-4 h-4" />
                  </a>
                )}
              </>
            )}

            {downloadError && (
              <Alert variant="error" className="mb-4">
                {downloadError}
              </Alert>
            )}

            {platform.note && (
              <p className="text-xs text-secondary-500 flex items-start gap-1.5">
                <InformationCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{platform.note}</span>
              </p>
            )}

            {platform.kind === 'copy' && (
              <p className="text-xs text-secondary-500 flex items-start gap-1.5 mt-2">
                <ExclamationTriangleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>
                  The script fills in tags in the browser. Some crawlers never run JavaScript, so
                  for the widest coverage put the tags in your HTML server-side — the Cloudflare
                  option above does exactly that.
                </span>
              </p>
            )}
          </Card>

          {/* Reference */}
          <Card>
            <h2 className="text-lg font-semibold text-secondary mb-1">Snippet reference</h2>
            <p className="text-sm text-secondary-600 mb-4">
              The tag works as-is. These options are here when you need them.
            </p>

            <CodeBlock code={ctx.tag} label="The tag" wrap className="mb-5" />

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-secondary-200">
                    <th className="text-left py-2 pr-4 font-semibold text-secondary-600">
                      Attribute
                    </th>
                    <th className="text-left py-2 pr-4 font-semibold text-secondary-600">
                      Default
                    </th>
                    <th className="text-left py-2 font-semibold text-secondary-600">What it does</th>
                  </tr>
                </thead>
                <tbody className="text-secondary-700">
                  {[
                    ['data-site', 'page hostname', 'Resolve previews against a different registered domain, e.g. a subdomain using the apex domain’s previews.'],
                    ['data-mode', 'fill', '"fill" only adds tags you are missing. "replace" overwrites the ones already on the page.'],
                    ['data-spa', 'on', 'Re-run on client-side route changes. Turn off for classic multi-page sites.'],
                    ['data-cache', '600', 'Seconds to reuse a response within a tab. 0 disables it.'],
                    ['data-timeout', '4000', 'Milliseconds before the request is abandoned.'],
                    ['data-debug', 'off', 'Log what the snippet did. Adding ?mmv_debug=1 to any URL does the same thing.'],
                  ].map(([attr, def, desc]) => (
                    <tr key={attr} className="border-b border-secondary-100 last:border-0">
                      <td className="py-2.5 pr-4 align-top">
                        <code className="font-mono text-xs bg-secondary-100 px-1.5 py-0.5 rounded whitespace-nowrap">
                          {attr}
                        </code>
                      </td>
                      <td className="py-2.5 pr-4 align-top">
                        <code className="font-mono text-xs text-secondary-500">{def}</code>
                      </td>
                      <td className="py-2.5 align-top">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-secondary-500 mt-4 flex items-start gap-1.5">
              <InformationCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>
                The snippet never overwrites tags your site already sets, never blocks rendering,
                and fails silently if our API is unreachable.
              </span>
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
