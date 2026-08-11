import { Link } from 'react-router-dom'

interface FooterProps {
  /** 'dark' for the public marketing shell, 'light' for app-adjacent pages. */
  tone?: 'dark' | 'light'
}

export default function Footer({ tone = 'dark' }: FooterProps) {
  const text = tone === 'dark' ? 'text-white/50' : 'text-secondary-600'
  const link = tone === 'dark' ? 'text-white/60 hover:text-white' : 'text-secondary-600 hover:text-primary-500'
  const border = tone === 'dark' ? 'border-white/10' : 'border-line'

  return (
    <footer className={`border-t ${border} mt-12 py-6`}>
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
          <div className={`text-sm ${text}`}>
            © {new Date().getFullYear()} MetaView. All rights reserved.
          </div>
          <div className="flex space-x-6 text-sm">
            <Link to="/privacy" className={`${link} transition-colors`}>
              Privacy Policy
            </Link>
            <Link to="/terms" className={`${link} transition-colors`}>
              Terms of Service
            </Link>
            <a href="mailto:hello@mymetaview.com" className={`${link} transition-colors`}>
              Contact
            </a>
          </div>
        </div>
      </div>
    </footer>
  )
}
