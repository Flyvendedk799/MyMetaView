import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Card from '../components/ui/Card'

interface AdminRouteProps {
  children: React.ReactNode
}

/**
 * Protected route that requires admin access.
 * Redirects to /app if user is not an admin.
 */
export default function AdminRoute({ children }: AdminRouteProps) {
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

  if (!user.is_admin) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-secondary mb-2">Access Denied</h2>
            <p className="text-secondary-600 mb-6">
              You do not have permission to access this page. Admin access required.
            </p>
            <button
              onClick={() => window.location.href = '/app'}
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}

