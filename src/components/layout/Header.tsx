import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bars3Icon,
  BellIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  ChevronDownIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '../../hooks/useAuth'
import { CountBadge } from '../ui/Badge'

interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const userMenuRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  
  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])
  
  // Focus search input when opened
  useEffect(() => {
    if (showSearch && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [showSearch])
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      // The preview gallery owns search — it filters by URL/title/domain.
      navigate(`/app/previews?q=${encodeURIComponent(searchQuery.trim())}`)
      setShowSearch(false)
      setSearchQuery('')
    }
  }
  
  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-30 bg-surface border-b border-line">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
        {/* Left side */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 -ml-2 text-secondary-500 hover:text-secondary-700 hover:bg-secondary-100 rounded-lg transition-colors"
            aria-label="Open menu"
          >
            <Bars3Icon className="w-6 h-6" />
          </button>
          
          {/* Search bar - desktop */}
          <div className="hidden md:block relative">
            <form onSubmit={handleSearch}>
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
              <input
                type="search"
                placeholder="Search URLs, domains…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-64 lg:w-80 pl-10 pr-4 py-2 font-mono text-[13px] bg-secondary-50 border border-line rounded-lg
                         placeholder-secondary-500 text-secondary-900
                         focus:bg-surface focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 focus:outline-none
                         transition-all duration-200"
                aria-label="Search URLs, domains"
              />
            </form>
          </div>
        </div>
        
        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* Search button - mobile */}
          <button
            onClick={() => setShowSearch(!showSearch)}
            className="md:hidden p-2 text-secondary-500 hover:text-secondary-700 hover:bg-secondary-100 rounded-lg transition-colors"
          >
            <MagnifyingGlassIcon className="w-5 h-5" />
          </button>
          
          {/* Quick create button */}
          <button
            onClick={() => navigate('/app/previews?new=1')}
            className="hidden sm:flex items-center gap-2 px-3 py-2 text-sm font-semibold text-primary-500
                     hover:bg-brand-50 rounded-lg transition-colors"
          >
            <PlusIcon className="w-5 h-5" />
            <span>New Preview</span>
          </button>
          
          {/* Notifications */}
          <button className="relative p-2 text-secondary-500 hover:text-secondary-700 hover:bg-secondary-100 rounded-lg transition-colors">
            <BellIcon className="w-5 h-5" />
            <CountBadge count={3} className="absolute -top-0.5 -right-0.5" />
          </button>
          
          {/* Divider */}
          <div className="w-px h-8 bg-secondary-200 mx-2 hidden sm:block" />
          
          {/* User menu */}
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-1.5 pr-3 hover:bg-secondary-100 rounded-xl transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-primary-500 font-semibold text-sm">
                {user?.email?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span className="hidden sm:block text-sm font-medium text-secondary-700 max-w-[120px] truncate">
                {user?.email?.split('@')[0] || 'User'}
              </span>
              <ChevronDownIcon className={`hidden sm:block w-4 h-4 text-secondary-400 transition-transform duration-200 ${showUserMenu ? 'rotate-180' : ''}`} />
            </button>
            
            {/* Dropdown menu */}
            {showUserMenu && (
              <div className="dropdown absolute right-0 w-56">
                <div className="px-4 py-3 border-b border-secondary-100">
                  <p className="text-sm font-medium text-secondary-900 truncate">{user?.email}</p>
                  <p className="text-xs text-secondary-500 mt-0.5">
                    {user?.is_admin ? 'Administrator' : 'Member'}
                  </p>
                </div>
                
                <div className="py-2">
                  <Link
                    to="/app/account"
                    onClick={() => setShowUserMenu(false)}
                    className="dropdown-item"
                  >
                    <UserCircleIcon className="w-5 h-5 text-secondary-400" />
                    Your Profile
                  </Link>
                  <Link
                    to="/app/organizations"
                    onClick={() => setShowUserMenu(false)}
                    className="dropdown-item"
                  >
                    <Cog6ToothIcon className="w-5 h-5 text-secondary-400" />
                    Settings
                  </Link>
                </div>
                
                <div className="dropdown-divider" />
                
                <div className="py-2">
                  <button
                    onClick={handleLogout}
                    className="dropdown-item w-full text-error-600 hover:bg-error-50"
                  >
                    <ArrowRightOnRectangleIcon className="w-5 h-5" />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Mobile search bar */}
      {showSearch && (
        <div className="md:hidden px-4 pb-4 animate-fade-in-down">
          <form onSubmit={handleSearch}>
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
              <input
                ref={searchInputRef}
                type="search"
                placeholder="Search URLs, domains…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 font-mono text-[13px] bg-secondary-50 border border-line rounded-lg
                         placeholder-secondary-500 text-secondary-900
                         focus:bg-surface focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 focus:outline-none"
              />
            </div>
          </form>
        </div>
      )}
    </header>
  )
}
