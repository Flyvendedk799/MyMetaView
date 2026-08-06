import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'

interface PaidRouteProps {
  children: React.ReactNode
}

/**
 * Protected route that requires an active paid subscription.
 * Shows upgrade prompt if user doesn't have active subscription.
 */
export default function PaidRoute({ children }: PaidRouteProps) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
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

  // Check if user has active subscription or is within trial period
  const hasActiveSubscription = user.subscription_status === 'active' || user.subscription_status === 'trialing'
  
  // Check if user is within trial period
  const isWithinTrial = user.trial_ends_at && new Date(user.trial_ends_at) > new Date()

  if (!hasActiveSubscription && !isWithinTrial) {
    // Show upgrade prompt
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-secondary mb-2">Upgrade Required</h2>
            <p className="text-secondary-600 mb-6">
              This feature requires an active subscription. Please upgrade your plan to continue.
            </p>
            <div className="space-y-3">
              <Button
                onClick={() => window.location.href = '/app/billing'}
                className="w-full"
              >
                View Plans & Upgrade
              </Button>
              <Button
                onClick={() => window.history.back()}
                variant="secondary"
                className="w-full"
              >
                Go Back
              </Button>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}

