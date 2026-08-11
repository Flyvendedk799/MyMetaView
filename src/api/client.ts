/** API client for backend communication */
import type {
  Domain,
  DomainCreate,
  BrandSettings,
  BrandSettingsUpdate,
  Preview,
  PreviewCreate,
  PreviewUpdate,
  PreviewVariant,
  PreviewJobCreateResponse,
  SitemapDiscoverResponse,
  BulkJobCreateResponse,
  BulkJobStatus,
  RecentBulkJobs,
  AnalyticsSummary,
  User,
  Token,
  PublicPlan,
  MyPlan,
  PreviewRestyleRequest,
  PlatformCardsResponse,
  CardSize,
  AnalyticsOverview,
  DomainAnalyticsItem,
  PreviewAnalyticsItem,
  AdminAnalyticsOverview,
  AdminAnalyticsUserItem,
  WorkerHealth,
  ActivityLog,
  AdminActivityLog,
  Organization,
  OrganizationCreate,
  OrganizationUpdate,
  OrganizationMember,
  OrganizationInviteResponse,
  OrganizationJoinRequest,
  OrganizationRole,
  SystemOverview,
  AdminUserSummary,
  AdminUserDetail,
  AdminDomain,
  AdminPreview,
  PublishedSite,
  PublishedSiteCreate,
  PublishedSiteUpdate,
  SitePost,
  SitePostCreate,
  SitePostUpdate,
  SitePostListItem,
  PaginatedSitePosts,
  SiteCategory,
  SiteCategoryCreate,
  SiteCategoryUpdate,
  SitePage,
  SitePageCreate,
  SitePageUpdate,
  SiteMenu,
  SiteMenuCreate,
  SiteMenuUpdate,
  SiteMenuItem,
  SiteMenuItemCreate,
  SiteMenuItemUpdate,
  SiteMedia,
  SiteMediaCreate,
  SiteMediaUpdate,
  SiteBranding,
  SiteBrandingCreate,
  SiteBrandingUpdate,
  SiteSettings,
  SiteSettingsCreate,
  SiteSettingsUpdate,
  SiteStats,
} from './types'

// Re-export types for use in other files
export type {
  Domain,
  DomainCreate,
  BrandSettings,
  BrandSettingsUpdate,
  Preview,
  PreviewCreate,
  PreviewUpdate,
  PreviewVariant,
  PreviewJobCreateResponse,
  SitemapDiscoverResponse,
  BulkJobCreateResponse,
  BulkJobStatus,
  RecentBulkJobs,
  AnalyticsSummary,
  User,
  Token,
  PublicPlan,
  MyPlan,
  PreviewRestyleRequest,
  PlatformCardsResponse,
  CardSize,
  AnalyticsOverview,
  DomainAnalyticsItem,
  PreviewAnalyticsItem,
  AdminAnalyticsOverview,
  AdminAnalyticsUserItem,
  WorkerHealth,
  ActivityLog,
  AdminActivityLog,
  Organization,
  OrganizationMember,
  OrganizationInviteResponse,
  OrganizationRole,
  SystemOverview,
  AdminUserSummary,
  AdminUserDetail,
  AdminDomain,
  AdminPreview,
  // Site types
  PublishedSite,
  PublishedSiteCreate,
  PublishedSiteUpdate,
  SitePost,
  SitePostCreate,
  SitePostUpdate,
  SitePostListItem,
  PaginatedSitePosts,
  SiteCategory,
  SiteCategoryCreate,
  SiteCategoryUpdate,
  SitePage,
  SitePageCreate,
  SitePageUpdate,
  SiteMenu,
  SiteMenuCreate,
  SiteMenuUpdate,
  SiteMenuItem,
  SiteMenuItemCreate,
  SiteMenuItemUpdate,
  SiteMedia,
  SiteMediaCreate,
  SiteMediaUpdate,
  SiteBranding,
  SiteBrandingCreate,
  SiteBrandingUpdate,
  SiteSettings,
  SiteSettingsCreate,
  SiteSettingsUpdate,
  SiteStats,
}

/**
 * Get the base URL for API requests.
 * Reads from VITE_API_BASE_URL env var or defaults to localhost:8000
 */
/**
 * Get the API base URL from environment variables.
 * 
 * IMPORTANT: This should be just the base URL (e.g., https://backend.railway.app)
 * WITHOUT the /api/v1 suffix, as all endpoints already include /api/v1.
 * 
 * Examples:
 * - Development: http://localhost:8000
 * - Production: https://your-backend-service.railway.app
 */
export function getApiBaseUrl(): string {
  // If VITE_API_BASE_URL is set, use it (for direct backend access)
  // Otherwise, use empty string to make relative API calls (proxied through nginx)
  // In development, default to localhost:8000
  const url = import.meta.env.VITE_API_BASE_URL ||
              (import.meta.env.DEV ? 'http://localhost:8000' : '')
  // Remove trailing slash if present
  return url.replace(/\/$/, '')
}

/**
 * Get auth token from localStorage
 */
export function getAuthToken(): string | null {
  return localStorage.getItem('access_token')
}

/**
 * Set auth token in localStorage
 */
export function setAuthToken(token: string): void {
  localStorage.setItem('access_token', token)
}

/**
 * Remove auth token from localStorage
 */
export function removeAuthToken(): void {
  localStorage.removeItem('access_token')
}

/**
 * Extended fetch options with timeout support
 */
interface FetchApiOptions extends RequestInit {
  timeout?: number // Timeout in milliseconds
}

/**
 * Base fetch wrapper with error handling and auth token injection
 */
export async function fetchApi<T>(
  endpoint: string,
  options?: FetchApiOptions,
  requireAuth: boolean = true
): Promise<T> {
  const baseUrl = getApiBaseUrl()
  const url = `${baseUrl}${endpoint}`

  // Log API calls in development
  if (import.meta.env.DEV) {
    console.log(`[API] ${options?.method || 'GET'} ${url}`)
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  }

  // Add auth token if available and auth is required
  if (requireAuth) {
    const token = getAuthToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    // Add organization ID header if available
    const selectedOrgId = localStorage.getItem('selected_org_id')
    if (selectedOrgId) {
      headers['X-Organization-ID'] = selectedOrgId
    }
  }

  try {
    // Create AbortController for timeout (default 120 seconds)
    const timeoutMs = options?.timeout || 120000 // 120 seconds default
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
    
    // Remove timeout from options before passing to fetch
    const { timeout, ...fetchOptions } = options || {}
    
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    })
    
    clearTimeout(timeoutId)

    if (!response.ok) {
      // Try to parse JSON error response
      let errorMessage = `Server error (${response.status})`
      try {
        const errorData = await response.json().catch(() => null)
        if (errorData?.detail) {
          // FastAPI validation errors can be:
          // 1. A string: { detail: "Error message" }
          // 2. An array: { detail: [{ loc: [...], msg: "...", type: "..." }] }
          if (Array.isArray(errorData.detail)) {
            // Format validation errors nicely
            const errors = errorData.detail.map((err: any) => {
              const field = err.loc?.slice(1).join('.') || 'unknown'
              return `${field}: ${err.msg || 'Invalid value'}`
            })
            errorMessage = `Validation errors:\n${errors.join('\n')}`
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          } else {
            errorMessage = JSON.stringify(errorData.detail)
          }
        } else if (typeof errorData === 'string') {
          errorMessage = errorData
        } else if (errorData && typeof errorData === 'object') {
          // Try to extract message from common error formats
          errorMessage = errorData.message || errorData.error || JSON.stringify(errorData)
        } else {
          const errorText = await response.text().catch(() => 'Unknown error')
          errorMessage = errorText || `Server error (${response.status})`
        }
      } catch {
        // If JSON parsing fails, try text
        const errorText = await response.text().catch(() => 'Unknown error')
        errorMessage = errorText || `Server error (${response.status})`
      }
      
      console.error(`[API Error] ${url}:`, {
        status: response.status,
        statusText: response.statusText,
        error: errorMessage
      })
      throw new Error(errorMessage)
    }

    return response.json()
  } catch (error) {
    // Handle timeout errors
    if (error instanceof Error && error.name === 'AbortError') {
      // Check if this is likely a Railway load balancer timeout (60s) vs our timeout (300s)
      const errorMessage = 'Request timed out. Preview generation can take 30-90 seconds. Railway\'s load balancer has a 60-second limit. Please try again - the request may still be processing on the backend.'
      console.error(`[API Timeout] ${url}:`, errorMessage)
      throw new Error(errorMessage)
    }
    
    // Handle network errors (connection refused, etc.)
    if (error instanceof TypeError && error.message.includes('fetch')) {
      const errorMessage = `Failed to connect to API at ${url}. Please check that the backend is running and VITE_API_BASE_URL is set correctly.`
      console.error(`[API Connection Error] ${url}:`, errorMessage)
      console.error(`[API Config] Base URL: ${baseUrl}, Endpoint: ${endpoint}`)
      throw new Error(errorMessage)
    }
    throw error
  }
}

// Auth endpoints
export async function login(email: string, password: string): Promise<Token> {
  const baseUrl = getApiBaseUrl()
  const formData = new URLSearchParams()
  formData.append('username', email) // OAuth2PasswordRequestForm uses 'username'
  formData.append('password', password)

  const url = `${baseUrl}/api/v1/auth/login`
  
  // Log API calls in development
  if (import.meta.env.DEV) {
    console.log(`[API] POST ${url}`)
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData,
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error')
    const errorMessage = `Login failed: ${response.status} ${response.statusText} - ${errorText}`
    console.error(`[API Error] ${url}:`, errorMessage)
    throw new Error(errorMessage)
  }

  return response.json()
}

export async function signup(email: string, password: string): Promise<User> {
  return fetchApi<User>(
    '/api/v1/auth/signup',
    {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    },
    false // Don't require auth for signup
  )
}

export async function fetchCurrentUser(): Promise<User> {
  return fetchApi<User>('/api/v1/auth/me')
}

export async function requestPasswordReset(email: string): Promise<{ status: string; message: string }> {
  return fetchApi(
    '/api/v1/auth/forgot-password',
    { method: 'POST', body: JSON.stringify({ email }) },
    false
  )
}

export async function resetPassword(token: string, newPassword: string): Promise<{ status: string; message: string }> {
  return fetchApi(
    '/api/v1/auth/reset-password',
    { method: 'POST', body: JSON.stringify({ token, new_password: newPassword }) },
    false
  )
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{ status: string; message: string }> {
  return fetchApi(
    '/api/v1/account/change-password',
    { method: 'POST', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }
  )
}

// Domain endpoints
export async function fetchDomains(): Promise<Domain[]> {
  return fetchApi<Domain[]>('/api/v1/domains')
}

export async function createDomain(payload: DomainCreate): Promise<Domain> {
  return fetchApi<Domain>('/api/v1/domains', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchDomainById(id: number): Promise<Domain> {
  return fetchApi<Domain>(`/api/v1/domains/${id}`)
}

export async function deleteDomain(id: number): Promise<void> {
  await fetchApi<{ success: boolean }>(`/api/v1/domains/${id}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Snippet install
// ============================================================================

export interface InstallDomainStatus {
  id: number
  name: string
  status: string
  verified: boolean
  snippet_installed_at: string | null
  snippet_last_seen_at: string | null
  snippet_version: string | null
  snippet_live: boolean
  snippet_outdated: boolean
}

export interface InstallConfig {
  snippet_url: string
  snippet_tag: string
  snippet_version: string
  api_origin: string
  domains: InstallDomainStatus[]
}

export type InstallVerifyStatus = 'installed' | 'not_found' | 'unreachable' | 'blocked'

export interface VerifyInstallResponse {
  ok: boolean
  checked_url: string
  snippet_found: boolean
  snippet_version: string | null
  heartbeat_seen: boolean
  heartbeat_at: string | null
  og_title: string | null
  og_image: string | null
  has_own_og_tags: boolean
  status: InstallVerifyStatus
  message: string
  hint: string | null
}

export async function fetchInstallConfig(): Promise<InstallConfig> {
  return fetchApi<InstallConfig>('/api/v1/install/config')
}

export async function verifyInstall(payload: {
  domain_id?: number
  url?: string
}): Promise<VerifyInstallResponse> {
  return fetchApi<VerifyInstallResponse>('/api/v1/install/verify', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeout: 30000, // The backend fetches a third-party page; allow for a slow origin.
  })
}

export type InstallArtifact = 'wordpress-plugin' | 'gtm-container' | 'cloudflare-worker'

const INSTALL_ARTIFACT_FILENAMES: Record<InstallArtifact, string> = {
  'wordpress-plugin': 'mymetaview-previews.zip',
  'gtm-container': 'mymetaview-gtm-container.json',
  'cloudflare-worker': 'mymetaview-worker.js',
}

/**
 * Download a generated install file and hand it to the browser.
 *
 * These endpoints need an auth header, so a plain <a href> will not do — we
 * fetch the bytes and drive the download from an object URL.
 */
export async function downloadInstallArtifact(
  artifact: InstallArtifact,
  domainId?: number
): Promise<void> {
  const query = domainId !== undefined ? `?domain_id=${domainId}` : ''
  const url = `${getApiBaseUrl()}/api/v1/install/downloads/${artifact}${query}`

  const headers: Record<string, string> = {}
  const token = getAuthToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const selectedOrgId = localStorage.getItem('selected_org_id')
  if (selectedOrgId) headers['X-Organization-ID'] = selectedOrgId

  const response = await fetch(url, { method: 'GET', headers })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail || `Download failed (${response.status})`)
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = INSTALL_ARTIFACT_FILENAMES[artifact]
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

// Brand settings endpoints
//
// Brands are scoped per domain: each connected site has its own identity.
// Passing no domainId targets the organization-wide default.
function brandQuery(domainId?: number | null): string {
  return domainId != null ? `?domain_id=${domainId}` : ''
}

export async function fetchBrandSettings(domainId?: number | null): Promise<BrandSettings> {
  return fetchApi<BrandSettings>(`/api/v1/brand${brandQuery(domainId)}`)
}

export async function updateBrandSettings(
  payload: BrandSettingsUpdate,
  domainId?: number | null
): Promise<BrandSettings> {
  return fetchApi<BrandSettings>(`/api/v1/brand${brandQuery(domainId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

/**
 * Upload a brand logo (multipart). We use a raw fetch here so the browser sets
 * the multipart Content-Type + boundary itself (fetchApi forces application/json).
 */
export async function uploadBrandLogo(file: File, domainId?: number | null): Promise<BrandSettings> {
  const baseUrl = getApiBaseUrl()
  const form = new FormData()
  form.append('file', file)

  const headers: Record<string, string> = {}
  const token = getAuthToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const selectedOrgId = localStorage.getItem('selected_org_id')
  if (selectedOrgId) headers['X-Organization-ID'] = selectedOrgId

  const response = await fetch(`${baseUrl}/api/v1/brand/logo${brandQuery(domainId)}`, {
    method: 'POST',
    headers, // deliberately no Content-Type — the browser adds the boundary
    body: form,
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : `Logo upload failed (${response.status})`)
  }
  return response.json() as Promise<BrandSettings>
}

/** Render a live SAMPLE share-card from a domain's currently-saved brand settings. */
export async function renderBrandPreview(domainId?: number | null): Promise<{ image_url: string }> {
  return fetchApi<{ image_url: string }>(`/api/v1/brand/preview${brandQuery(domainId)}`, {
    method: 'POST',
    timeout: 30000,
  })
}

// Preview endpoints
export async function fetchPreviews(type?: string): Promise<Preview[]> {
  const queryParam = type ? `?type=${encodeURIComponent(type)}` : ''
  return fetchApi<Preview[]>(`/api/v1/previews${queryParam}`)
}

export async function createOrUpdatePreview(
  payload: PreviewCreate
): Promise<Preview> {
  return fetchApi<Preview>('/api/v1/previews', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updatePreview(
  previewId: number,
  payload: PreviewUpdate
): Promise<Preview> {
  return fetchApi<Preview>(`/api/v1/previews/${previewId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deletePreview(previewId: number): Promise<void> {
  await fetchApi<{ success: boolean }>(`/api/v1/previews/${previewId}`, {
    method: 'DELETE',
  })
}

export async function generatePreviewWithAI(payload: { url: string; domain: string }): Promise<Preview> {
  return fetchApi<Preview>('/api/v1/previews/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * Re-render a card with a different layout, panel colour or accent.
 *
 * A pure render off the stored spec — no page capture, no model call — so it
 * does not spend an AI generation. The copy stays as it is; changing the hook
 * needs a full regeneration.
 */
export async function restylePreview(
  previewId: number,
  direction: PreviewRestyleRequest
): Promise<Preview> {
  return fetchApi<Preview>(`/api/v1/previews/${previewId}/restyle`, {
    method: 'POST',
    body: JSON.stringify(direction),
  })
}

/** Render this card at each aspect ratio. Also free of AI cost. */
export async function buildPlatformCards(
  previewId: number,
  sizes?: CardSize[]
): Promise<PlatformCardsResponse> {
  const query = sizes?.length
    ? '?' + sizes.map((s) => `sizes=${encodeURIComponent(s)}`).join('&')
    : ''
  return fetchApi<PlatformCardsResponse>(
    `/api/v1/previews/${previewId}/platform-cards${query}`,
    { method: 'POST' }
  )
}

// Job queue endpoints
export interface JobStatus {
  status: 'queued' | 'started' | 'finished' | 'failed'
  result: Preview | null
  error: string | null
}

export async function createPreviewJob(
  payload: { url: string; domain: string; force?: boolean }
): Promise<PreviewJobCreateResponse> {
  return fetchApi<PreviewJobCreateResponse>('/api/v1/jobs/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return fetchApi<JobStatus>(`/api/v1/jobs/${jobId}/status`)
}

// Bulk / whole-site generation + sitemap discovery
export async function discoverSitemapUrls(domain: string): Promise<SitemapDiscoverResponse> {
  return fetchApi<SitemapDiscoverResponse>('/api/v1/jobs/preview/discover', {
    method: 'POST',
    body: JSON.stringify({ domain }),
    timeout: 45000, // reading a site's sitemap can take a moment
  })
}

export async function createBulkPreviewJob(
  domain: string,
  urls: string[],
  force = false
): Promise<BulkJobCreateResponse> {
  return fetchApi<BulkJobCreateResponse>('/api/v1/jobs/preview/bulk', {
    method: 'POST',
    body: JSON.stringify({ domain, urls, force }),
  })
}

export async function getBulkJobStatus(batchId: string): Promise<BulkJobStatus> {
  return fetchApi<BulkJobStatus>(`/api/v1/jobs/bulk/${batchId}/status`)
}

export async function getRecentBulkJobs(): Promise<RecentBulkJobs> {
  return fetchApi<RecentBulkJobs>('/api/v1/jobs/bulk/recent')
}

// Analytics endpoints
export async function fetchAnalyticsSummary(
  period: '7d' | '30d' = '7d'
): Promise<AnalyticsSummary> {
  return fetchApi<AnalyticsSummary>(`/api/v1/analytics/summary?period=${period}`)
}

// Domain Verification
export async function startDomainVerification(domainId: number, method: 'dns' | 'html' | 'meta'): Promise<{
  domain_id: number
  method: string
  token: string
  instructions: Record<string, string>
}> {
  return fetchApi(`/api/v1/domains/${domainId}/verification/start`, {
    method: 'POST',
    body: JSON.stringify({ method }),
  })
}

export async function checkDomainVerification(domainId: number): Promise<Domain> {
  return fetchApi<Domain>(`/api/v1/domains/${domainId}/verification/check`)
}

export async function debugDomainVerification(domainId: number): Promise<{
  domain: string
  expected_value: string
  found_records: string[]
  is_verified: boolean
  error: string | null
}> {
  return fetchApi(`/api/v1/domains/${domainId}/verification/debug`)
}

// Billing endpoints
export async function createCheckoutSession(priceId: string): Promise<{ checkout_url: string }> {
  return fetchApi<{ checkout_url: string }>('/api/v1/billing/checkout', {
    method: 'POST',
    body: JSON.stringify({ price_id: priceId }),
  })
}

export async function createBillingPortal(): Promise<{ portal_url: string }> {
  return fetchApi<{ portal_url: string }>('/api/v1/billing/portal', {
    method: 'POST',
  })
}

export async function getBillingStatus(): Promise<{
  subscription_status: string
  subscription_plan?: string | null
  trial_ends_at?: string | null
}> {
  return fetchApi('/api/v1/billing/status')
}

export async function changeSubscriptionPlan(priceId: string): Promise<{
  subscription_status: string
  subscription_plan?: string | null
  trial_ends_at?: string | null
}> {
  return fetchApi('/api/v1/billing/change-plan', {
    method: 'POST',
    body: JSON.stringify({ price_id: priceId }),
  })
}

// Plans (single source of truth: backend/core/plans.py)
export async function getPlans(): Promise<PublicPlan[]> {
  const res = await fetchApi<{ plans: PublicPlan[] }>('/api/v1/plans')
  return res.plans
}

export async function getMyPlan(): Promise<MyPlan> {
  return fetchApi<MyPlan>('/api/v1/plans/me')
}

// Admin endpoints

export async function fetchAdminUsers(): Promise<AdminUserSummary[]> {
  return fetchApi<AdminUserSummary[]>('/api/v1/admin/users')
}

export async function fetchAdminUserById(userId: number): Promise<AdminUserDetail> {
  return fetchApi<AdminUserDetail>(`/api/v1/admin/users/${userId}`)
}

export async function toggleUserActive(userId: number): Promise<{
  id: number
  email: string
  is_active: boolean
  message: string
}> {
  return fetchApi(`/api/v1/admin/users/${userId}/toggle-active`, {
    method: 'POST',
  })
}

export async function fetchAdminDomains(): Promise<AdminDomain[]> {
  return fetchApi<AdminDomain[]>('/api/v1/admin/domains')
}

export async function deleteAdminDomain(domainId: number): Promise<{ message: string }> {
  return fetchApi(`/api/v1/admin/domains/${domainId}`, {
    method: 'DELETE',
  })
}

export async function fetchAdminPreviews(skip = 0, limit = 50): Promise<AdminPreview[]> {
  return fetchApi<AdminPreview[]>(`/api/v1/admin/previews?skip=${skip}&limit=${limit}`)
}

export async function deleteAdminPreview(previewId: number): Promise<{ message: string }> {
  return fetchApi(`/api/v1/admin/previews/${previewId}`, {
    method: 'DELETE',
  })
}

export async function fetchAdminPreviewVariants(previewId: number): Promise<PreviewVariant[]> {
  return fetchApi<PreviewVariant[]>(`/api/v1/admin/previews/${previewId}/variants`)
}

export async function deleteAdminPreviewVariant(variantId: number): Promise<{ message: string }> {
  return fetchApi(`/api/v1/admin/preview-variants/${variantId}`, {
    method: 'DELETE',
  })
}

export async function fetchAdminSystemOverview(): Promise<SystemOverview> {
  return fetchApi<SystemOverview>('/api/v1/admin/system/overview')
}

export async function fetchAdminWorkerHealth(): Promise<WorkerHealth> {
  return fetchApi<WorkerHealth>('/api/v1/admin/system/worker-health')
}

// Admin settings endpoints

export interface DemoCacheDisabledResponse {
  disabled: boolean
}

export async function getDemoCacheDisabled(): Promise<boolean> {
  const response = await fetchApi<DemoCacheDisabledResponse>('/api/v1/admin/settings/demo-cache-disabled')
  return response.disabled
}

export async function setDemoCacheDisabled(disabled: boolean): Promise<boolean> {
  const response = await fetchApi<DemoCacheDisabledResponse>('/api/v1/admin/settings/demo-cache-disabled', {
    method: 'POST',
    body: JSON.stringify({ disabled }),
  })
  return response.disabled
}

export interface DeploymentResponse {
  success: boolean
  message: string
  output?: string
  branch_merged?: string
}

export async function triggerDeployment(): Promise<DeploymentResponse> {
  return fetchApi<DeploymentResponse>('/api/v1/admin/deploy/merge-claude-branch', {
    method: 'POST',
  })
}

export async function exportUserData(): Promise<any> {
  return fetchApi('/api/v1/account/export')
}

export async function deleteUserAccount(): Promise<{ success: boolean; message: string }> {
  return fetchApi('/api/v1/account', {
    method: 'DELETE',
  })
}

export async function deleteOrganization(orgId: number): Promise<{ success: boolean; message: string }> {
  return fetchApi(`/api/v1/account/organizations/${orgId}`, {
    method: 'DELETE',
  })
}

// Activity endpoints

export async function fetchUserActivity(skip = 0, limit = 50): Promise<ActivityLog[]> {
  return fetchApi<ActivityLog[]>(`/api/v1/activity?skip=${skip}&limit=${limit}`)
}

export async function fetchAdminActivity(
  skip = 0,
  limit = 50,
  userId?: number,
  action?: string,
  url?: string
): Promise<AdminActivityLog[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  })
  if (userId !== undefined) params.append('user_id', userId.toString())
  if (action) params.append('action', action)
  if (url) params.append('url', url)
  return fetchApi<AdminActivityLog[]>(`/api/v1/activity/admin?${params.toString()}`)
}

// Analytics endpoints
export async function fetchAnalyticsOverview(): Promise<AnalyticsOverview> {
  return fetchApi<AnalyticsOverview>('/api/v1/analytics/overview')
}

export async function fetchDomainAnalytics(): Promise<DomainAnalyticsItem[]> {
  return fetchApi<DomainAnalyticsItem[]>('/api/v1/analytics/domains')
}

export async function fetchPreviewAnalytics(limit = 20): Promise<PreviewAnalyticsItem[]> {
  return fetchApi<PreviewAnalyticsItem[]>(`/api/v1/analytics/previews?limit=${limit}`)
}

export async function fetchAdminAnalyticsOverview(): Promise<AdminAnalyticsOverview> {
  return fetchApi<AdminAnalyticsOverview>('/api/v1/admin/analytics/overview')
}

export async function fetchAdminAnalyticsUsers(limit = 20): Promise<AdminAnalyticsUserItem[]> {
  return fetchApi<AdminAnalyticsUserItem[]>(`/api/v1/admin/analytics/users?limit=${limit}`)
}

// Organization endpoints

export async function fetchOrganizations(): Promise<Organization[]> {
  return fetchApi<Organization[]>('/api/v1/organizations')
}

export async function createOrganization(data: OrganizationCreate): Promise<Organization> {
  return fetchApi<Organization>('/api/v1/organizations', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getOrganization(orgId: number): Promise<Organization> {
  return fetchApi<Organization>(`/api/v1/organizations/${orgId}`)
}

export async function updateOrganization(orgId: number, data: OrganizationUpdate): Promise<Organization> {
  return fetchApi<Organization>(`/api/v1/organizations/${orgId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function fetchOrganizationMembers(orgId: number): Promise<OrganizationMember[]> {
  return fetchApi<OrganizationMember[]>(`/api/v1/organizations/${orgId}/members`)
}

export async function updateMemberRole(
  orgId: number,
  memberId: number,
  role: string
): Promise<OrganizationMember> {
  return fetchApi<OrganizationMember>(`/api/v1/organizations/${orgId}/members/${memberId}/role?new_role=${role}`, {
    method: 'PUT',
  })
}

export async function removeMember(orgId: number, memberId: number): Promise<{ success: boolean }> {
  return fetchApi<{ success: boolean }>(`/api/v1/organizations/${orgId}/members/${memberId}`, {
    method: 'DELETE',
  })
}

export async function createInviteLink(
  orgId: number,
  role: string = 'viewer',
  expiresInDays: number = 7
): Promise<OrganizationInviteResponse> {
  return fetchApi<OrganizationInviteResponse>(`/api/v1/organizations/${orgId}/invite`, {
    method: 'POST',
    body: JSON.stringify({ role, expires_in_days: expiresInDays }),
  })
}

export async function joinOrganization(data: OrganizationJoinRequest): Promise<Organization> {
  return fetchApi<Organization>('/api/v1/organizations/join', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Preview Variant endpoints
export async function fetchPreviewVariants(previewId: number): Promise<PreviewVariant[]> {
  return fetchApi<PreviewVariant[]>(`/api/v1/preview-variants/preview/${previewId}`)
}

export async function getPreviewVariant(variantId: number): Promise<PreviewVariant> {
  return fetchApi<PreviewVariant>(`/api/v1/preview-variants/${variantId}`)
}

export async function updatePreviewVariant(
  variantId: number,
  data: { title?: string; description?: string; tone?: string; keywords?: string; image_url?: string }
): Promise<PreviewVariant> {
  return fetchApi<PreviewVariant>(`/api/v1/preview-variants/${variantId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deletePreviewVariant(variantId: number): Promise<void> {
  await fetchApi(`/api/v1/preview-variants/${variantId}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Blog Types
// ============================================================================

export interface BlogCategory {
  id: number
  name: string
  slug: string
  description?: string
  color: string
  icon?: string
  is_active: boolean
  sort_order: number
  meta_title?: string
  meta_description?: string
  created_at: string
  updated_at: string
  post_count?: number
}

export interface BlogPostListItem {
  id: number
  title: string
  slug: string
  excerpt?: string
  featured_image?: string
  author_name?: string
  author_avatar?: string
  category?: BlogCategory
  tags?: string
  status: string
  is_featured: boolean
  is_pinned: boolean
  read_time_minutes?: number
  views_count: number
  published_at?: string
  created_at: string
}

export interface BlogPost extends BlogPostListItem {
  content: string
  featured_image_alt?: string
  og_image?: string
  author_id: number
  author_bio?: string
  category_id?: number
  scheduled_at?: string
  updated_at: string
  meta_title?: string
  meta_description?: string
  meta_keywords?: string
  canonical_url?: string
  no_index: boolean
  schema_type: string
  twitter_title?: string
  twitter_description?: string
  twitter_image?: string
  related_post_ids?: string
}

export interface PaginatedBlogPosts {
  items: BlogPostListItem[]
  total: number
  page: number
  per_page: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface BlogPostCreate {
  title: string
  slug?: string
  excerpt?: string
  content: string
  featured_image?: string
  featured_image_alt?: string
  og_image?: string
  author_name?: string
  author_bio?: string
  author_avatar?: string
  category_id?: number
  tags?: string
  status?: 'draft' | 'published' | 'scheduled' | 'archived'
  is_featured?: boolean
  is_pinned?: boolean
  scheduled_at?: string
  meta_title?: string
  meta_description?: string
  meta_keywords?: string
  canonical_url?: string
  no_index?: boolean
  schema_type?: string
  twitter_title?: string
  twitter_description?: string
  twitter_image?: string
  related_post_ids?: string
}

export interface BlogPostUpdate extends Partial<BlogPostCreate> {}

export interface BlogCategoryCreate {
  name: string
  slug?: string
  description?: string
  color?: string
  icon?: string
  is_active?: boolean
  sort_order?: number
  meta_title?: string
  meta_description?: string
}

export interface BlogCategoryUpdate extends Partial<BlogCategoryCreate> {}

// ============================================================================
// Blog Endpoints (Public)
// ============================================================================

export async function fetchBlogPosts(options?: {
  page?: number
  per_page?: number
  category?: string
  tag?: string
  search?: string
  featured?: boolean
}): Promise<PaginatedBlogPosts> {
  const params = new URLSearchParams()
  if (options?.page) params.append('page', options.page.toString())
  if (options?.per_page) params.append('per_page', options.per_page.toString())
  if (options?.category) params.append('category', options.category)
  if (options?.tag) params.append('tag', options.tag)
  if (options?.search) params.append('search', options.search)
  if (options?.featured !== undefined) params.append('featured', options.featured.toString())
  
  const query = params.toString() ? `?${params.toString()}` : ''
  return fetchApi<PaginatedBlogPosts>(`/api/v1/blog/posts${query}`, undefined, false)
}

export async function fetchFeaturedBlogPosts(limit: number = 3): Promise<BlogPostListItem[]> {
  return fetchApi<BlogPostListItem[]>(`/api/v1/blog/posts/featured?limit=${limit}`, undefined, false)
}

export async function fetchRecentBlogPosts(limit: number = 5, excludeId?: number): Promise<BlogPostListItem[]> {
  const params = new URLSearchParams({ limit: limit.toString() })
  if (excludeId) params.append('exclude_id', excludeId.toString())
  return fetchApi<BlogPostListItem[]>(`/api/v1/blog/posts/recent?${params.toString()}`, undefined, false)
}

export async function fetchBlogPostBySlug(slug: string): Promise<BlogPost> {
  return fetchApi<BlogPost>(`/api/v1/blog/posts/${slug}`, undefined, false)
}

export async function fetchBlogCategories(includeEmpty: boolean = false): Promise<BlogCategory[]> {
  return fetchApi<BlogCategory[]>(`/api/v1/blog/categories?include_empty=${includeEmpty}`, undefined, false)
}

export async function fetchBlogCategoryBySlug(slug: string): Promise<BlogCategory> {
  return fetchApi<BlogCategory>(`/api/v1/blog/categories/${slug}`, undefined, false)
}

// ============================================================================
// Blog Endpoints (Admin)
// ============================================================================

export async function adminFetchBlogPosts(options?: {
  page?: number
  per_page?: number
  status?: string
  category_id?: number
  search?: string
}): Promise<PaginatedBlogPosts> {
  const params = new URLSearchParams()
  if (options?.page) params.append('page', options.page.toString())
  if (options?.per_page) params.append('per_page', options.per_page.toString())
  if (options?.status) params.append('status', options.status)
  if (options?.category_id) params.append('category_id', options.category_id.toString())
  if (options?.search) params.append('search', options.search)
  
  const query = params.toString() ? `?${params.toString()}` : ''
  return fetchApi<PaginatedBlogPosts>(`/api/v1/blog/admin/posts${query}`)
}

export async function adminFetchBlogPost(postId: number): Promise<BlogPost> {
  return fetchApi<BlogPost>(`/api/v1/blog/admin/posts/${postId}`)
}

export async function adminCreateBlogPost(data: BlogPostCreate): Promise<BlogPost> {
  return fetchApi<BlogPost>('/api/v1/blog/admin/posts', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function adminUpdateBlogPost(postId: number, data: BlogPostUpdate): Promise<BlogPost> {
  return fetchApi<BlogPost>(`/api/v1/blog/admin/posts/${postId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function adminDeleteBlogPost(postId: number): Promise<void> {
  await fetchApi(`/api/v1/blog/admin/posts/${postId}`, {
    method: 'DELETE',
  })
}

export async function adminPublishBlogPost(postId: number): Promise<BlogPost> {
  return fetchApi<BlogPost>(`/api/v1/blog/admin/posts/${postId}/publish`, {
    method: 'POST',
  })
}

export async function adminUnpublishBlogPost(postId: number): Promise<BlogPost> {
  return fetchApi<BlogPost>(`/api/v1/blog/admin/posts/${postId}/unpublish`, {
    method: 'POST',
  })
}

export async function adminFetchBlogCategories(includeInactive: boolean = true): Promise<BlogCategory[]> {
  return fetchApi<BlogCategory[]>(`/api/v1/blog/admin/categories?include_inactive=${includeInactive}`)
}

export async function adminCreateBlogCategory(data: BlogCategoryCreate): Promise<BlogCategory> {
  return fetchApi<BlogCategory>('/api/v1/blog/admin/categories', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function adminUpdateBlogCategory(categoryId: number, data: BlogCategoryUpdate): Promise<BlogCategory> {
  return fetchApi<BlogCategory>(`/api/v1/blog/admin/categories/${categoryId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function adminDeleteBlogCategory(categoryId: number): Promise<void> {
  await fetchApi(`/api/v1/blog/admin/categories/${categoryId}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Newsletter Endpoints
// ============================================================================

export interface NewsletterSubscribeRequest {
  email: string
  source?: string
  consent_given?: boolean
}

export interface NewsletterSubscriber {
  id: number
  email: string
  source: string
  subscribed_at: string
  is_active: boolean
  consent_given: boolean
  ip_address?: string | null
  user_agent?: string | null
}

export interface NewsletterSubscriberList {
  items: NewsletterSubscriber[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export async function subscribeToNewsletter(data: NewsletterSubscribeRequest): Promise<NewsletterSubscriber> {
  return fetchApi<NewsletterSubscriber>('/api/v1/newsletter/subscribe', {
    method: 'POST',
    body: JSON.stringify(data),
  }, false) // No auth required
}

export async function fetchNewsletterSubscribers(options?: {
  page?: number
  per_page?: number
  search?: string
  source?: string
}): Promise<NewsletterSubscriberList> {
  const params = new URLSearchParams()
  if (options?.page) params.append('page', options.page.toString())
  if (options?.per_page) params.append('per_page', options.per_page.toString())
  if (options?.search) params.append('search', options.search)
  if (options?.source) params.append('source', options.source)
  
  const query = params.toString() ? `?${params.toString()}` : ''
  return fetchApi<NewsletterSubscriberList>(`/api/v1/newsletter/subscribers${query}`)
}

export async function exportNewsletterSubscribers(format: 'csv' | 'xlsx' = 'csv', source?: string): Promise<Blob> {
  const params = new URLSearchParams()
  params.append('format', format)
  if (source) params.append('source', source)
  
  const baseUrl = getApiBaseUrl()
  const url = `${baseUrl}/api/v1/newsletter/subscribers/export?${params.toString()}`
  const token = getAuthToken()
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  const response = await fetch(url, {
    method: 'GET',
    headers,
  })
  
  if (!response.ok) {
    throw new Error(`Export failed: ${response.statusText}`)
  }
  
  return response.blob()
}

// ============================================================================
// Demo Preview Endpoints - Multi-Stage Reasoned Preview
// ============================================================================

export interface DemoPreviewRequest {
  url: string
}

export interface ContextItem {
  icon: string  // 'location', 'info', etc.
  text: string
}

export interface CredibilityItem {
  type: string   // 'rating', 'review', etc.
  value: string  // '4.5 (10 reviews)'
}

// Design DNA - extracted design philosophy for intelligent rendering
export interface DesignDNA {
  style: 'minimalist' | 'maximalist' | 'corporate' | 'luxurious' | 'playful' | 'technical' | 'editorial' | 'brutalist' | 'organic' | string
  mood: 'calm' | 'balanced' | 'dynamic' | 'dramatic' | string
  formality: number  // 0-1, where 0=casual, 1=formal
  typography_personality: 'authoritative' | 'friendly' | 'elegant' | 'technical' | 'bold' | 'subtle' | 'expressive' | string
  color_emotion: 'trust' | 'energy' | 'calm' | 'sophistication' | 'warmth' | 'innovation' | 'playfulness' | string
  spacing_feel: 'compact' | 'balanced' | 'spacious' | 'ultra-minimal' | string
  brand_adjectives: string[]
  design_reasoning: string
}

export interface LayoutBlueprint {
  template_type: string  // profile, product, landing, article, service
  primary_color: string
  secondary_color: string
  accent_color: string
  
  // Quality scores from coherence check
  coherence_score: number  // 0-1
  balance_score: number    // 0-1
  clarity_score: number    // 0-1
  design_fidelity_score?: number  // 0-1, how well preview honors original design
  overall_quality: 'excellent' | 'good' | 'fair' | 'poor'
  
  // Reasoning chain
  layout_reasoning: string
  composition_notes: string
}

export interface DemoPreviewResponse {
  // Source URL
  url: string
  
  // ===== RENDERED CONTENT =====
  title: string
  subtitle: string | null
  description: string | null
  tags: string[]
  context_items: ContextItem[]
  credibility_items: CredibilityItem[]
  cta_text: string | null
  
  // ===== IMAGES =====
  primary_image_base64: string | null
  screenshot_url: string | null
  composited_preview_image_url: string | null  // Final og:image with all elements composited
  
  // ===== LAYOUT BLUEPRINT =====
  blueprint: LayoutBlueprint
  
  // ===== DESIGN DNA (NEW) =====
  design_dna?: DesignDNA | null  // Design intelligence for adaptive rendering
  
  // ===== QUALITY METRICS =====
  reasoning_confidence: number  // 0-1
  design_fidelity_score?: number  // 0-1, how well preview honors original design
  processing_time_ms: number
  quality_scores?: Record<string, any> | null  // Quality scores from backend
  is_fallback?: boolean  // True if this is a fallback preview
  
  // ===== DEMO METADATA =====
  is_demo: boolean
  message: string
}

/**
 * @deprecated Use createDemoJob + getDemoJobStatus instead. The /api/v1/demo/preview
 * endpoint is deprecated; demo-v2 job flow avoids Railway's 60s timeout and provides
 * progress feedback. Will be removed in a future release.
 */
export async function generateDemoPreview(url: string): Promise<DemoPreviewResponse> {
  const token = getAuthToken()
  return fetchApi<DemoPreviewResponse>('/api/v1/demo/preview', {
    method: 'POST',
    body: JSON.stringify({ url }),
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  }, false) // Public endpoint; attach auth when available for user-scoped activity logs
}

// ============================================================================
// Demo Preview V2 - Enhanced with Brand Extraction
// ============================================================================

export interface BrandElements {
  brand_name?: string | null
  logo_base64?: string | null
  hero_image_base64?: string | null
  favicon_url?: string | null
}

export interface DemoPreviewResponseV2 extends DemoPreviewResponse {
  brand?: BrandElements | null
}

/**
 * Generate demo preview using sync V2 endpoint.
 *
 * @deprecated Prefer createDemoJob + getDemoJobStatus for production. Sync endpoint
 * can hit Railway's 60s load balancer timeout. Job flow provides progress and avoids
 * timeouts. Sync endpoint kept for quick tests only.
 *
 * @param url - URL to generate preview for
 * @returns Enhanced preview response with brand elements
 */
export async function generateDemoPreviewV2(url: string): Promise<DemoPreviewResponseV2> {
  const token = getAuthToken()
  return fetchApi<DemoPreviewResponseV2>('/api/v1/demo-v2/preview', {
    method: 'POST',
    body: JSON.stringify({ url }),
    timeout: 300000, // 5 minutes for preview generation (can take 30-90s, with buffer for slow pages)
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  }, false) // Public endpoint; attach auth when available for user-scoped activity logs
}

// Async demo job endpoints (work around Railway's 60-second load balancer timeout)
export interface DemoJobResponse {
  job_id: string
  status: string
  message: string
}

export interface DemoJobStatusResponse {
  job_id: string
  status: 'queued' | 'started' | 'finished' | 'failed'
  result: DemoPreviewResponseV2 | null
  error: string | null
  progress: number | null // 0.0 to 1.0
  message?: string | null // Human-readable status message
}

export async function createDemoJob(url: string): Promise<DemoJobResponse> {
  const token = getAuthToken()
  return fetchApi<DemoJobResponse>('/api/v1/demo-v2/jobs', {
    method: 'POST',
    body: JSON.stringify({ url, quality_mode: 'ultra' }),
    timeout: 30000, // 30 seconds for job creation (should be instant)
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  }, false) // Public endpoint; attach auth when available for user-scoped activity logs
}

export async function getDemoJobStatus(jobId: string): Promise<DemoJobStatusResponse> {
  const token = getAuthToken()
  return fetchApi<DemoJobStatusResponse>(`/api/v1/demo-v2/jobs/${jobId}/status`, {
    method: 'GET',
    timeout: 10000, // 10 seconds for status check
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  }, false) // Public endpoint; attach auth when available for user-scoped activity logs
}

// Sites Management
export async function fetchSites(): Promise<PublishedSite[]> {
  return fetchApi<PublishedSite[]>('/api/v1/sites', {
    method: 'GET',
  })
}

export async function createSite(payload: PublishedSiteCreate): Promise<PublishedSite> {
  return fetchApi<PublishedSite>('/api/v1/sites', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchSiteById(siteId: number): Promise<PublishedSite> {
  return fetchApi<PublishedSite>(`/api/v1/sites/${siteId}`, {
    method: 'GET',
  })
}

export async function updateSite(siteId: number, payload: PublishedSiteUpdate): Promise<PublishedSite> {
  return fetchApi<PublishedSite>(`/api/v1/sites/${siteId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSite(siteId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}`, {
    method: 'DELETE',
  })
}

export async function publishSite(siteId: number): Promise<PublishedSite> {
  return fetchApi<PublishedSite>(`/api/v1/sites/${siteId}/publish`, {
    method: 'POST',
  })
}

export async function unpublishSite(siteId: number): Promise<PublishedSite> {
  return fetchApi<PublishedSite>(`/api/v1/sites/${siteId}/unpublish`, {
    method: 'POST',
  })
}

export async function fetchSiteStats(siteId: number): Promise<SiteStats> {
  return fetchApi<SiteStats>(`/api/v1/sites/${siteId}/stats`, {
    method: 'GET',
  })
}

// Site Posts
export async function fetchSitePosts(
  siteId: number,
  params?: { page?: number; per_page?: number; status?: string; category_id?: number; search?: string }
): Promise<PaginatedSitePosts> {
  const queryParams = new URLSearchParams()
  if (params?.page) queryParams.append('page', params.page.toString())
  if (params?.per_page) queryParams.append('per_page', params.per_page.toString())
  if (params?.status) queryParams.append('status', params.status)
  if (params?.category_id) queryParams.append('category_id', params.category_id.toString())
  if (params?.search) queryParams.append('search', params.search)
  
  const query = queryParams.toString()
  return fetchApi<PaginatedSitePosts>(`/api/v1/sites/${siteId}/posts${query ? `?${query}` : ''}`, {
    method: 'GET',
  })
}

export async function createSitePost(siteId: number, payload: SitePostCreate): Promise<SitePost> {
  return fetchApi<SitePost>(`/api/v1/sites/${siteId}/posts`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchSitePost(siteId: number, postId: number): Promise<SitePost> {
  return fetchApi<SitePost>(`/api/v1/sites/${siteId}/posts/${postId}`, {
    method: 'GET',
  })
}

export async function updateSitePost(siteId: number, postId: number, payload: SitePostUpdate): Promise<SitePost> {
  return fetchApi<SitePost>(`/api/v1/sites/${siteId}/posts/${postId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSitePost(siteId: number, postId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}/posts/${postId}`, {
    method: 'DELETE',
  })
}

// Site Categories
export async function fetchSiteCategories(siteId: number): Promise<SiteCategory[]> {
  return fetchApi<SiteCategory[]>(`/api/v1/sites/${siteId}/categories`, {
    method: 'GET',
  })
}

export async function createSiteCategory(siteId: number, payload: SiteCategoryCreate): Promise<SiteCategory> {
  return fetchApi<SiteCategory>(`/api/v1/sites/${siteId}/categories`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateSiteCategory(siteId: number, categoryId: number, payload: SiteCategoryUpdate): Promise<SiteCategory> {
  return fetchApi<SiteCategory>(`/api/v1/sites/${siteId}/categories/${categoryId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteCategory(siteId: number, categoryId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}/categories/${categoryId}`, {
    method: 'DELETE',
  })
}

// Site Pages
export async function fetchSitePages(siteId: number): Promise<SitePage[]> {
  return fetchApi<SitePage[]>(`/api/v1/sites/${siteId}/pages`, {
    method: 'GET',
  })
}

export async function createSitePage(siteId: number, payload: SitePageCreate): Promise<SitePage> {
  return fetchApi<SitePage>(`/api/v1/sites/${siteId}/pages`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchSitePage(siteId: number, pageId: number): Promise<SitePage> {
  return fetchApi<SitePage>(`/api/v1/sites/${siteId}/pages/${pageId}`, {
    method: 'GET',
  })
}

export async function updateSitePage(siteId: number, pageId: number, payload: SitePageUpdate): Promise<SitePage> {
  return fetchApi<SitePage>(`/api/v1/sites/${siteId}/pages/${pageId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSitePage(siteId: number, pageId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}/pages/${pageId}`, {
    method: 'DELETE',
  })
}

// Site Menus
export async function fetchSiteMenus(siteId: number): Promise<SiteMenu[]> {
  return fetchApi<SiteMenu[]>(`/api/v1/sites/${siteId}/menus`, {
    method: 'GET',
  })
}

export async function createSiteMenu(siteId: number, payload: SiteMenuCreate): Promise<SiteMenu> {
  return fetchApi<SiteMenu>(`/api/v1/sites/${siteId}/menus`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchSiteMenu(siteId: number, menuId: number): Promise<SiteMenu> {
  return fetchApi<SiteMenu>(`/api/v1/sites/${siteId}/menus/${menuId}`, {
    method: 'GET',
  })
}

export async function updateSiteMenu(siteId: number, menuId: number, payload: SiteMenuUpdate): Promise<SiteMenu> {
  return fetchApi<SiteMenu>(`/api/v1/sites/${siteId}/menus/${menuId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteMenu(siteId: number, menuId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}/menus/${menuId}`, {
    method: 'DELETE',
  })
}

// Site Menu Items
export async function createSiteMenuItem(siteId: number, menuId: number, payload: SiteMenuItemCreate): Promise<SiteMenuItem> {
  return fetchApi<SiteMenuItem>(`/api/v1/sites/${siteId}/menus/${menuId}/items`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateSiteMenuItem(siteId: number, menuId: number, itemId: number, payload: SiteMenuItemUpdate): Promise<SiteMenuItem> {
  return fetchApi<SiteMenuItem>(`/api/v1/sites/${siteId}/menus/${menuId}/items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteMenuItem(siteId: number, menuId: number, itemId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}/menus/${menuId}/items/${itemId}`, {
    method: 'DELETE',
  })
}

// Site Media
export async function fetchSiteMedia(siteId: number, params?: { page?: number; per_page?: number; search?: string }): Promise<SiteMedia[]> {
  const queryParams = new URLSearchParams()
  if (params?.page) queryParams.append('page', params.page.toString())
  if (params?.per_page) queryParams.append('per_page', params.per_page.toString())
  if (params?.search) queryParams.append('search', params.search)
  
  const query = queryParams.toString()
  return fetchApi<SiteMedia[]>(`/api/v1/sites/${siteId}/media${query ? `?${query}` : ''}`, {
    method: 'GET',
  })
}

export async function uploadSiteMedia(siteId: number, file: File, altText?: string): Promise<SiteMedia> {
  const formData = new FormData()
  formData.append('file', file)
  if (altText) formData.append('alt_text', altText)
  
  const token = localStorage.getItem('token')
  const response = await fetch(`/api/v1/sites/${siteId}/media/upload`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || 'Upload failed')
  }
  
  return response.json()
}

export async function createSiteMedia(siteId: number, payload: SiteMediaCreate): Promise<SiteMedia> {
  return fetchApi<SiteMedia>(`/api/v1/sites/${siteId}/media`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateSiteMedia(siteId: number, mediaId: number, payload: SiteMediaUpdate): Promise<SiteMedia> {
  return fetchApi<SiteMedia>(`/api/v1/sites/${siteId}/media/${mediaId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteMedia(siteId: number, mediaId: number): Promise<void> {
  return fetchApi<void>(`/api/v1/sites/${siteId}/media/${mediaId}`, {
    method: 'DELETE',
  })
}

// Site Branding
export async function fetchSiteBranding(siteId: number): Promise<SiteBranding> {
  return fetchApi<SiteBranding>(`/api/v1/sites/${siteId}/branding`, {
    method: 'GET',
  })
}

export async function updateSiteBranding(siteId: number, payload: SiteBrandingUpdate): Promise<SiteBranding> {
  return fetchApi<SiteBranding>(`/api/v1/sites/${siteId}/branding`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

// Site Settings
export async function fetchSiteSettings(siteId: number): Promise<SiteSettings> {
  return fetchApi<SiteSettings>(`/api/v1/sites/${siteId}/settings`, {
    method: 'GET',
  })
}

export async function updateSiteSettings(siteId: number, payload: SiteSettingsUpdate): Promise<SiteSettings> {
  return fetchApi<SiteSettings>(`/api/v1/sites/${siteId}/settings`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}






