/** TypeScript interfaces matching backend Pydantic schemas */

export interface Domain {
  id: number
  name: string
  environment: string
  status: string
  verification_method?: string | null
  verification_token?: string | null
  verified_at?: string | null
  created_at: string // ISO datetime
  monthly_clicks: number
  site_id?: number | null // ID of the published site using this domain
}

export interface DomainCreate {
  name: string
  environment?: string
  status?: string
}

export interface BrandSettings {
  id: number
  primary_color: string
  secondary_color: string
  accent_color: string
  font_family: string
  logo_url?: string | null
  // Preview-card controls ("auto" = let the AI decide)
  preview_layout: string
  preview_panel: string
  preview_accent: string
  force_brand_colors: boolean
  hide_watermark: boolean
}

export interface BrandSettingsUpdate {
  primary_color?: string
  secondary_color?: string
  accent_color?: string
  font_family?: string
  logo_url?: string | null
  preview_layout?: string
  preview_panel?: string
  preview_accent?: string
  force_brand_colors?: boolean
  hide_watermark?: boolean
}

export interface Preview {
  id: number
  url: string
  domain: string
  title: string
  type: string
  image_url: string
  highlight_image_url?: string | null
  description?: string | null
  keywords?: string | null
  tone?: string | null
  ai_reasoning?: string | null
  created_at: string // ISO datetime
  monthly_clicks: number
}

export interface PreviewVariant {
  id: number
  preview_id: number
  variant_key: 'a' | 'b' | 'c'
  title: string
  description?: string | null
  tone?: string | null
  keywords?: string | null
  image_url?: string | null
  created_at: string
}

export interface PreviewCreate {
  url: string
  domain: string
  title: string
  type: string
  image_url?: string | null
  description?: string | null
}

export interface PreviewUpdate {
  title?: string | null
  type?: string | null
  image_url?: string | null
}

export interface TopDomain {
  domain: string
  clicks: number
  ctr: number
}

export interface AnalyticsSummary {
  period: string
  total_clicks: number
  total_previews: number
  total_domains: number
  brand_score: number
  top_domains: TopDomain[]
}

export interface User {
  id: number
  email: string
  is_active: boolean
  is_admin?: boolean
  created_at: string
  stripe_customer_id?: string | null
  stripe_subscription_id?: string | null
  subscription_status: string
  subscription_plan?: string | null
  trial_ends_at?: string | null
}

export interface UserCreate {
  email: string
  password: string
}

export interface Token {
  access_token: string
  token_type: string
}

// Plans / billing tiers — shape mirrors backend/core/plans.py (the single
// source of truth). `null` on a numeric limit means "unlimited".
export interface PublicPlan {
  key: string
  name: string
  price: number
  domains: number | null
  previews_month: number | null
  team_seats: number | null
  features: string[]
}

export interface MyPlan {
  key: string
  name: string
  price: number
  status: string | null
  trial_ends_at: string | null
  limits: {
    domains: number | null
    previews_month: number | null
    team_seats: number | null
  }
  features: string[]
  usage: {
    domains: number
    previews_month: number
  }
}

// Admin types
export interface AdminUserSummary {
  id: number
  email: string
  is_active: boolean
  subscription_status: string
  subscription_plan?: string | null
  created_at: string
  domains_count: number
  previews_count: number
}

export interface AdminUserDetail {
  id: number
  email: string
  is_active: boolean
  is_admin: boolean
  subscription_status: string
  subscription_plan?: string | null
  trial_ends_at?: string | null
  created_at: string
  domains_count: number
  previews_count: number
  total_clicks: number
  stripe_customer_id?: string | null
}

export interface AdminDomain {
  id: number
  name: string
  environment: string
  status: string
  verification_method?: string | null
  verified_at?: string | null
  user_email: string
  user_id: number
  created_at: string
  monthly_clicks: number
}

export interface AdminPreview {
  id: number
  url: string
  domain: string
  title: string
  type: string
  user_email: string
  user_id: number
  created_at: string
  monthly_clicks: number
}

export interface SystemOverview {
  total_users: number
  active_subscribers: number
  total_domains: number
  verified_domains: number
  previews_generated_24h: number
  jobs_running: number
  errors_past_24h: number
  redis_queue_length: number
}

// Activity log types
export interface ActivityLog {
  id: number
  action: string
  metadata: Record<string, any> | null
  created_at: string
}

export interface AdminActivityLog extends ActivityLog {
  user_id?: number | null
  organization_id?: number | null
  ip_address?: string | null
  user_agent?: string | null
}

// Analytics types
export interface TimeseriesPoint {
  date: string
  value: number
}

export interface AnalyticsOverview {
  total_impressions: number
  total_clicks: number
  ctr: number
  impressions_timeseries: TimeseriesPoint[]
  clicks_timeseries: TimeseriesPoint[]
}

export interface DomainAnalyticsItem {
  domain_id: number
  domain_name: string
  impressions_7d: number
  impressions_30d: number
  clicks_7d: number
  clicks_30d: number
  ctr_30d: number
}

export interface PreviewAnalyticsItem {
  preview_id: number
  url: string
  title: string
  domain: string
  impressions_30d: number
  clicks_30d: number
  ctr_30d: number
}

export interface AdminAnalyticsOverview {
  total_users: number
  active_subscribers: number
  total_domains: number
  total_previews: number
  total_impressions_24h: number
  total_clicks_24h: number
  total_impressions_30d: number
  total_clicks_30d: number
}

export interface AdminAnalyticsUserItem {
  user_id: number
  email: string
  impressions_30d: number
  clicks_30d: number
  active_domains: number
  active_previews: number
}

export interface WorkerHealth {
  main_queue_length: number
  dlq_length: number
  recent_failures_count: number
  last_successful_job_at: string | null
  last_failure_at: string | null
}

// Organization types
export type OrganizationRole = 'owner' | 'admin' | 'editor' | 'viewer'

export interface Organization {
  id: number
  name: string
  owner_user_id: number
  created_at: string
  subscription_status: string
  subscription_plan?: string | null
}

export interface OrganizationCreate {
  name: string
}

export interface OrganizationUpdate {
  name?: string
}

export interface OrganizationMember {
  id: number
  organization_id: number
  user_id: number
  role: OrganizationRole
  created_at: string
  user_email?: string | null
}

export interface OrganizationInviteResponse {
  invite_token: string
  invite_url: string
  expires_at: string
}

export interface OrganizationJoinRequest {
  invite_token: string
}

// Site types
export interface PublishedSite {
  id: number
  name: string
  slug: string
  domain_id: number
  organization_id: number
  template_id: string
  status: 'draft' | 'published' | 'archived'
  is_active: boolean
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  created_at: string
  updated_at: string
  published_at?: string | null
  domain?: Domain
}

export interface PublishedSiteCreate {
  name: string
  slug?: string
  domain_id: number
  template_id?: string
  status?: 'draft' | 'published' | 'archived'
  is_active?: boolean
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
}

export interface PublishedSiteUpdate {
  name?: string
  slug?: string
  template_id?: string
  status?: 'draft' | 'published' | 'archived'
  is_active?: boolean
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
}

export interface SitePost {
  id: number
  site_id: number
  title: string
  slug: string
  excerpt?: string | null
  content: string
  featured_image?: string | null
  featured_image_alt?: string | null
  og_image?: string | null
  author_id: number
  author_name?: string | null
  author_bio?: string | null
  author_avatar?: string | null
  category_id?: number | null
  tags?: string | null
  status: 'draft' | 'published' | 'scheduled' | 'archived'
  is_featured: boolean
  is_pinned: boolean
  read_time_minutes?: number | null
  views_count: number
  created_at: string
  updated_at: string
  published_at?: string | null
  scheduled_at?: string | null
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  canonical_url?: string | null
  no_index: boolean
  schema_type: string
  twitter_title?: string | null
  twitter_description?: string | null
  twitter_image?: string | null
}

export interface SitePostCreate {
  title: string
  slug?: string
  excerpt?: string | null
  content: string
  featured_image?: string | null
  featured_image_alt?: string | null
  og_image?: string | null
  author_name?: string | null
  author_bio?: string | null
  author_avatar?: string | null
  category_id?: number | null
  tags?: string | null
  status?: 'draft' | 'published' | 'scheduled' | 'archived'
  is_featured?: boolean
  is_pinned?: boolean
  scheduled_at?: string | null
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  canonical_url?: string | null
  no_index?: boolean
  schema_type?: string
  twitter_title?: string | null
  twitter_description?: string | null
  twitter_image?: string | null
}

export interface SitePostUpdate {
  title?: string
  slug?: string
  excerpt?: string | null
  content?: string
  featured_image?: string | null
  featured_image_alt?: string | null
  og_image?: string | null
  author_name?: string | null
  author_bio?: string | null
  author_avatar?: string | null
  category_id?: number | null
  tags?: string | null
  status?: 'draft' | 'published' | 'scheduled' | 'archived'
  is_featured?: boolean
  is_pinned?: boolean
  scheduled_at?: string | null
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  canonical_url?: string | null
  no_index?: boolean
  schema_type?: string
  twitter_title?: string | null
  twitter_description?: string | null
  twitter_image?: string | null
}

export interface SitePostListItem {
  id: number
  title: string
  slug: string
  excerpt?: string | null
  featured_image?: string | null
  author_name?: string | null
  category_id?: number | null
  status: string
  is_featured: boolean
  is_pinned: boolean
  read_time_minutes?: number | null
  views_count: number
  published_at?: string | null
  created_at: string
}

export interface PaginatedSitePosts {
  items: SitePostListItem[]
  total: number
  page: number
  per_page: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface SiteCategory {
  id: number
  site_id: number
  name: string
  slug: string
  description?: string | null
  color: string
  icon?: string | null
  is_active: boolean
  sort_order: number
  meta_title?: string | null
  meta_description?: string | null
  created_at: string
  updated_at: string
  post_count?: number
}

export interface SiteCategoryCreate {
  name: string
  slug?: string
  description?: string | null
  color?: string
  icon?: string | null
  is_active?: boolean
  sort_order?: number
  meta_title?: string | null
  meta_description?: string | null
}

export interface SiteCategoryUpdate {
  name?: string
  slug?: string
  description?: string | null
  color?: string
  icon?: string | null
  is_active?: boolean
  sort_order?: number
  meta_title?: string | null
  meta_description?: string | null
}

export interface SitePage {
  id: number
  site_id: number
  title: string
  slug: string
  content: string
  status: 'draft' | 'published'
  is_homepage: boolean
  sort_order: number
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  no_index: boolean
  created_at: string
  updated_at: string
  published_at?: string | null
}

export interface SitePageCreate {
  title: string
  slug?: string
  content: string
  status?: 'draft' | 'published'
  is_homepage?: boolean
  sort_order?: number
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  no_index?: boolean
}

export interface SitePageUpdate {
  title?: string
  slug?: string
  content?: string
  status?: 'draft' | 'published'
  is_homepage?: boolean
  sort_order?: number
  meta_title?: string | null
  meta_description?: string | null
  meta_keywords?: string | null
  no_index?: boolean
}

export interface SiteMenu {
  id: number
  site_id: number
  name: string
  location: 'header' | 'footer' | 'sidebar'
  is_active: boolean
  created_at: string
  updated_at: string
  items: SiteMenuItem[]
}

export interface SiteMenuItem {
  id: number
  menu_id: number
  parent_id?: number | null
  label: string
  url?: string | null
  type: 'link' | 'post' | 'page' | 'category'
  target_id?: number | null
  icon?: string | null
  css_class?: string | null
  sort_order: number
  is_active: boolean
  open_in_new_tab?: boolean
  created_at: string
  updated_at: string
  children?: SiteMenuItem[]
}

export interface SiteMenuItemCreate {
  label: string
  url?: string | null
  type?: 'link' | 'post' | 'page' | 'category'
  target_id?: number | null
  parent_id?: number | null
  icon?: string | null
  css_class?: string | null
  sort_order?: number
  is_active?: boolean
  open_in_new_tab?: boolean
}

export interface SiteMenuItemUpdate {
  label?: string
  url?: string | null
  type?: 'link' | 'post' | 'page' | 'category'
  target_id?: number | null
  parent_id?: number | null
  icon?: string | null
  css_class?: string | null
  sort_order?: number
  is_active?: boolean
  open_in_new_tab?: boolean
}

export interface SiteMenuCreate {
  name: string
  location: 'header' | 'footer' | 'sidebar'
  is_active?: boolean
  items?: SiteMenuItemCreate[]
}

export interface SiteMenuUpdate {
  name?: string
  location?: 'header' | 'footer' | 'sidebar'
  is_active?: boolean
}

export interface SiteMedia {
  id: number
  site_id: number
  filename: string
  original_filename: string
  file_path: string
  file_size: number
  mime_type: string
  width?: number | null
  height?: number | null
  alt_text?: string | null
  title?: string | null
  description?: string | null
  caption?: string | null
  uploaded_at: string
  uploaded_by_id: number
}

export interface SiteMediaCreate {
  filename: string
  original_filename: string
  file_path: string
  file_size: number
  mime_type: string
  width?: number | null
  height?: number | null
  alt_text?: string | null
  title?: string | null
  description?: string | null
  caption?: string | null
}

export interface SiteMediaUpdate {
  alt_text?: string | null
  title?: string | null
  description?: string | null
  caption?: string | null
}

export interface SiteBranding {
  id: number
  site_id: number
  logo_url?: string | null
  logo_alt?: string | null
  favicon_url?: string | null
  primary_color: string
  secondary_color?: string | null
  accent_color?: string | null
  background_color: string
  text_color: string
  font_family?: string | null
  heading_font?: string | null
  body_font?: string | null
  custom_css?: string | null
  theme_config?: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface SiteBrandingCreate {
  logo_url?: string | null
  logo_alt?: string | null
  favicon_url?: string | null
  primary_color?: string
  secondary_color?: string | null
  accent_color?: string | null
  background_color?: string
  text_color?: string
  font_family?: string | null
  heading_font?: string | null
  body_font?: string | null
  custom_css?: string | null
  theme_config?: Record<string, any> | null
}

export interface SiteBrandingUpdate {
  logo_url?: string | null
  logo_alt?: string | null
  favicon_url?: string | null
  primary_color?: string
  secondary_color?: string | null
  accent_color?: string | null
  background_color?: string
  text_color?: string
  font_family?: string | null
  heading_font?: string | null
  body_font?: string | null
  custom_css?: string | null
  theme_config?: Record<string, any> | null
}

export interface SiteSettings {
  id: number
  site_id: number
  site_description?: string | null
  language: string
  timezone: string
  contact_email?: string | null
  contact_phone?: string | null
  address?: string | null
  social_links?: Record<string, string> | null
  google_analytics_id?: string | null
  google_tag_manager_id?: string | null
  facebook_pixel_id?: string | null
  robots_txt?: string | null
  sitemap_enabled: boolean
  comments_enabled: boolean
  newsletter_enabled: boolean
  search_enabled: boolean
  header_code?: string | null
  footer_code?: string | null
  created_at: string
  updated_at: string
}

export interface SiteSettingsCreate {
  site_description?: string | null
  language?: string
  timezone?: string
  contact_email?: string | null
  contact_phone?: string | null
  address?: string | null
  social_links?: Record<string, string> | null
  google_analytics_id?: string | null
  google_tag_manager_id?: string | null
  facebook_pixel_id?: string | null
  robots_txt?: string | null
  sitemap_enabled?: boolean
  comments_enabled?: boolean
  newsletter_enabled?: boolean
  search_enabled?: boolean
  header_code?: string | null
  footer_code?: string | null
}

export interface SiteSettingsUpdate {
  site_description?: string | null
  language?: string
  timezone?: string
  contact_email?: string | null
  contact_phone?: string | null
  address?: string | null
  social_links?: Record<string, string> | null
  google_analytics_id?: string | null
  google_tag_manager_id?: string | null
  facebook_pixel_id?: string | null
  robots_txt?: string | null
  sitemap_enabled?: boolean
  comments_enabled?: boolean
  newsletter_enabled?: boolean
  search_enabled?: boolean
  header_code?: string | null
  footer_code?: string | null
}

export interface SiteStats {
  total_posts: number
  published_posts: number
  draft_posts: number
  categories: number
  pages: number
  total_views: number
}

