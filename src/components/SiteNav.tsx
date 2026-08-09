import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bars3Icon, XMarkIcon } from '@heroicons/react/24/outline'
import Logo from './ui/Logo'

// Shared marketing header (dark ink identity). Used by Landing, Demo, and other
// public pages so the nav is identical everywhere. Section links point at the
// landing page (`/#…`) so they work from any route.
const navLinks = [
  { label: 'Product', href: '/#product' },
  { label: 'Features', href: '/#features' },
  { label: 'Pricing', href: '/#pricing' },
  { label: 'Docs', href: '/#docs' },
]

export default function SiteNav() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-ink/95 backdrop-blur-sm border-b border-paper/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-12">
        <div className="flex items-center justify-between h-16 sm:h-[72px]">
          <Link to="/" className="flex-shrink-0">
            <Logo size={30} surface="dark" />
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm text-paper/60 hover:text-paper transition-colors"
              >
                {link.label}
              </a>
            ))}
            <Link to="/blog" className="text-sm text-paper/60 hover:text-paper transition-colors">
              Blog
            </Link>
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link to="/login" className="text-sm font-medium text-paper/80 hover:text-paper transition-colors px-3 py-2">
              Sign in
            </Link>
            <Link
              to="/signup"
              className="text-sm font-semibold text-ink bg-paper hover:bg-brand-100 rounded-lg px-[18px] py-2.5 transition-colors"
            >
              Start free
            </Link>
          </div>

          {/* Mobile menu toggle */}
          <button
            className="md:hidden p-2 text-paper/70 hover:text-paper transition-colors"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileMenuOpen ? <XMarkIcon className="w-6 h-6" /> : <Bars3Icon className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden pb-4 border-t border-paper/10 animate-fade-in-down">
            <div className="flex flex-col gap-1 pt-3">
              {navLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2.5 text-sm text-paper/70 hover:text-paper hover:bg-paper/5 rounded-lg transition-colors"
                >
                  {link.label}
                </a>
              ))}
              <Link
                to="/blog"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 text-sm text-paper/70 hover:text-paper hover:bg-paper/5 rounded-lg transition-colors"
              >
                Blog
              </Link>
              <Link
                to="/demo"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2.5 text-sm text-paper/70 hover:text-paper hover:bg-paper/5 rounded-lg transition-colors"
              >
                Live demo
              </Link>
              <div className="flex items-center gap-3 px-3 pt-3">
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex-1 text-center text-sm font-medium text-paper/80 border border-paper/20 rounded-lg px-4 py-2.5 hover:border-paper/40 transition-colors"
                >
                  Sign in
                </Link>
                <Link
                  to="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex-1 text-center text-sm font-semibold text-ink bg-paper rounded-lg px-4 py-2.5 hover:bg-brand-100 transition-colors"
                >
                  Start free
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}
