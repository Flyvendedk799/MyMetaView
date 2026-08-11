import { Link } from 'react-router-dom'
import Logo from '../components/ui/Logo'
import Seo from '../components/Seo'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-paper flex flex-col items-center justify-center px-4 text-center">
      <Seo title="Page not found" description="This page doesn't exist." path="/404" />
      <div className="mb-8">
        <Logo />
      </div>
      <p className="font-mono text-sm uppercase tracking-[0.2em] text-secondary-500 mb-3">404</p>
      <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-display text-secondary-900 mb-3">
        This page doesn't exist
      </h1>
      <p className="text-secondary-600 max-w-md mb-8">
        The link may be outdated, or the page may have moved.
      </p>
      <div className="flex items-center gap-4">
        <Link to="/" className="btn btn-primary">Go to homepage</Link>
        <Link to="/app" className="btn btn-secondary">Open dashboard</Link>
      </div>
    </div>
  )
}
