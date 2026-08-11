import { Link, useLocation, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import {
  HomeIcon,
  GlobeAltIcon,
  PaintBrushIcon,
  PhotoIcon,
  ChartBarIcon,
  CreditCardIcon,
  XMarkIcon,
  ShieldCheckIcon,
  UserGroupIcon,
  ServerIcon,
  ClockIcon,
  BuildingOfficeIcon,
  ExclamationTriangleIcon,
  UserCircleIcon,
  DocumentTextIcon,
  EnvelopeIcon,
  NewspaperIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  Bars3Icon,
  DocumentIcon,
  FolderIcon,
  ArrowLeftIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '../../hooks/useAuth'
import { CountBadge } from '../ui/Badge'
import Logo from '../ui/Logo'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

interface NavItem {
  name: string
  href: string
  icon: any
  badge?: number
}

const mainNavigation: NavItem[] = [
  { name: 'Dashboard', href: '/app', icon: HomeIcon },
  { name: 'My Sites', href: '/app/sites', icon: NewspaperIcon },
  { name: 'Domains', href: '/app/domains', icon: GlobeAltIcon },
  { name: 'Install', href: '/app/install', icon: CodeBracketIcon },
  { name: 'Preview Gallery', href: '/app/previews', icon: PhotoIcon },
]

const settingsNavigation: NavItem[] = [
  { name: 'Brand Settings', href: '/app/brand', icon: PaintBrushIcon },
  { name: 'Analytics', href: '/app/analytics', icon: ChartBarIcon },
  { name: 'Billing', href: '/app/billing', icon: CreditCardIcon },
  { name: 'Activity', href: '/app/activity', icon: ClockIcon },
  { name: 'Organizations', href: '/app/organizations', icon: BuildingOfficeIcon },
  { name: 'Account', href: '/app/account', icon: UserCircleIcon },
]

const adminNavigation: NavItem[] = [
  { name: 'Overview', href: '/app/admin', icon: ShieldCheckIcon },
  { name: 'Users', href: '/app/admin/users', icon: UserGroupIcon },
  { name: 'Domains', href: '/app/admin/domains', icon: GlobeAltIcon },
  { name: 'Previews', href: '/app/admin/previews', icon: PhotoIcon },
  { name: 'Blog', href: '/app/admin/blog', icon: DocumentTextIcon },
  { name: 'Newsletter', href: '/app/admin/newsletter', icon: EnvelopeIcon },
  { name: 'Analytics', href: '/app/admin/analytics', icon: ChartBarIcon },
  { name: 'Activity', href: '/app/admin/activity', icon: ClockIcon },
  { name: 'System', href: '/app/admin/system', icon: ServerIcon },
  { name: 'Errors', href: '/app/admin/errors', icon: ExclamationTriangleIcon },
]

// Site-specific navigation when inside a site
const getSiteNavigation = (siteId: string): NavItem[] => [
  { name: 'Dashboard', href: `/app/sites/${siteId}`, icon: HomeIcon },
  { name: 'Posts', href: `/app/sites/${siteId}/posts`, icon: DocumentTextIcon },
  { name: 'Pages', href: `/app/sites/${siteId}/pages`, icon: DocumentIcon },
  { name: 'Categories', href: `/app/sites/${siteId}/categories`, icon: FolderIcon },
  { name: 'Media', href: `/app/sites/${siteId}/media`, icon: PhotoIcon },
  { name: 'Menus', href: `/app/sites/${siteId}/menus`, icon: Bars3Icon },
  { name: 'Branding', href: `/app/sites/${siteId}/branding`, icon: PaintBrushIcon },
  { name: 'Settings', href: `/app/sites/${siteId}/settings`, icon: Cog6ToothIcon },
]

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const location = useLocation()
  const params = useParams()
  const { user } = useAuth()
  const [settingsExpanded, setSettingsExpanded] = useState(false)
  const [adminExpanded, setAdminExpanded] = useState(false)

  // Check if we're in a site context
  const siteId = params.siteId
  const isInSiteContext = Boolean(siteId) && location.pathname.includes('/app/sites/')

  // Auto-expand sections based on current path
  useEffect(() => {
    if (settingsNavigation.some(item => location.pathname === item.href)) {
      setSettingsExpanded(true)
    }
    if (adminNavigation.some(item => location.pathname.startsWith(item.href))) {
      setAdminExpanded(true)
    }
  }, [location.pathname])

  const isActive = (href: string) => {
    if (href === '/app') return location.pathname === href
    return location.pathname.startsWith(href)
  }

  const NavLink = ({ item }: { item: NavItem }) => {
    const active = isActive(item.href)
    const Icon = item.icon

    return (
      <Link
        to={item.href}
        onClick={() => window.innerWidth < 1024 && onClose()}
        className={`
          group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm
          transition-colors duration-150
          ${active
            ? 'bg-paper/10 text-paper font-semibold'
            : 'text-paper/60 hover:bg-paper/5 hover:text-paper'
          }
        `}
      >
        <Icon className={`w-5 h-5 flex-shrink-0 transition-colors ${
          active ? 'text-paper' : 'text-paper/40 group-hover:text-paper/70'
        }`} />
        <span className="flex-1">{item.name}</span>
        {item.badge !== undefined && item.badge > 0 && (
          <CountBadge count={item.badge} variant="error" />
        )}
      </Link>
    )
  }

  const CollapsibleSection = ({
    title,
    items,
    expanded,
    onToggle,
    variant = 'default'
  }: {
    title: string
    items: NavItem[]
    expanded: boolean
    onToggle: () => void
    variant?: 'default' | 'admin'
  }) => (
    <div className="mt-6">
      <button
        onClick={onToggle}
        className={`
          w-full flex items-center justify-between px-3 py-2 font-mono text-[10px] uppercase tracking-label
          ${variant === 'admin' ? 'text-accent-400' : 'text-paper/35'}
          hover:text-paper/70 transition-colors
        `}
      >
        {title}
        <ChevronDownIcon className={`w-4 h-4 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
      </button>

      <div className={`
        mt-1 space-y-0.5 overflow-hidden transition-all duration-200
        ${expanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'}
      `}>
        {items.map((item) => (
          <NavLink key={item.name} item={item} />
        ))}
      </div>
    </div>
  )

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-ink/70 backdrop-blur-sm z-40 lg:hidden animate-fade-in"
          onClick={onClose}
        />
      )}

      {/* Sidebar — the dark evergreen surface is the only carry-over from marketing */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-full w-64
          bg-ink
          transform transition-transform duration-300 ease-out
          flex flex-col
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-5 flex-shrink-0">
          <Link to="/app" className="flex items-center group">
            <Logo size={28} surface="dark" />
          </Link>
          <button
            onClick={onClose}
            className="lg:hidden p-2 -mr-2 text-paper/50 hover:text-paper hover:bg-paper/10 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto scrollbar-hide">
          {/* Site Context Navigation */}
          {isInSiteContext ? (
            <>
              {/* Back to Sites Link */}
              <Link
                to="/app/sites"
                className="flex items-center gap-2 px-3 py-2 mb-4 text-sm text-paper/50 hover:text-paper transition-colors"
              >
                <ArrowLeftIcon className="w-4 h-4" />
                Back to Sites
              </Link>

              <div className="space-y-0.5">
                {getSiteNavigation(siteId!).map((item) => (
                  <NavLink key={item.name} item={item} />
                ))}
              </div>
            </>
          ) : (
            <>
              {/* Main Navigation */}
              <span className="block px-3 pb-2 font-mono text-[10px] uppercase tracking-label text-paper/35">
                Workspace
              </span>
              <div className="space-y-0.5">
                {mainNavigation.map((item) => (
                  <NavLink key={item.name} item={item} />
                ))}
              </div>

              {/* Settings Section */}
              <CollapsibleSection
                title="Account"
                items={settingsNavigation}
                expanded={settingsExpanded}
                onToggle={() => setSettingsExpanded(!settingsExpanded)}
              />

              {/* Admin Section */}
              {user?.is_admin && (
                <CollapsibleSection
                  title="Admin"
                  items={adminNavigation}
                  expanded={adminExpanded}
                  onToggle={() => setAdminExpanded(!adminExpanded)}
                  variant="admin"
                />
              )}
            </>
          )}
        </nav>

        {/* User Section */}
        <div className="p-3 flex-shrink-0">
          <Link
            to="/app/account"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-paper/5 hover:bg-paper/10 transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-primary-500 font-semibold text-sm flex-shrink-0">
              {user?.email?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-paper truncate">
                {user?.email || 'User'}
              </p>
              <p className="text-xs text-paper/50">
                {user?.is_admin ? 'Administrator' : 'Member'}
              </p>
            </div>
          </Link>
        </div>
      </aside>
    </>
  )
}
