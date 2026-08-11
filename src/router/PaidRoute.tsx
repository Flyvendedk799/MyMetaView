import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'

interface PaidRouteProps {
  children: React.ReactNode
}

/**
 * Protected route that requires an active paid subscription (or trial).
 * Shows an upgrade prompt if the subscription has lapsed.
 *
 * Renders inside the app shell — no min-h-screen wrapper, which used to
 * produce double chrome and a second scrollbar.
 */
export default function PaidRoute({ children }: PaidRouteProps) {
  const { user, loading, hasActiveSubscription } = useAuth()
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-secondary-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (!hasActiveSubscription()) {
    return (
      <div className="flex items-center justify-center py-24 px-4">
        <Card className="max-w-md w-full">
          <div className="text-center">
            <h2 className="font-display text-2xl font-semibold tracking-display-sm text-secondary-900 mb-2">
              Your trial has ended
            </h2>
            <p className="text-secondary-600 mb-6">
              Pick a plan to keep generating previews and tracking results. Your
              domains, brand settings, and existing previews are all safe.
            </p>
            <div className="space-y-3">
              <Button onClick={() => navigate('/app/billing')} className="w-full">
                View plans & upgrade
              </Button>
              <Button onClick={() => navigate('/app')} variant="secondary" className="w-full">
                Back to dashboard
              </Button>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
