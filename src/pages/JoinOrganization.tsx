import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { joinOrganization } from '../api/client'
import { useOrganization } from '../hooks/useOrganization'
import Seo from '../components/Seo'

export default function JoinOrganization() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { refreshOrganizations } = useOrganization()
  const token = searchParams.get('token')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (token) {
      handleJoin()
    } else {
      setError('No invite token provided')
    }
  }, [token])

  const handleJoin = async () => {
    if (!token) return

    try {
      setLoading(true)
      setError(null)
      const org = await joinOrganization({ invite_token: token })
      await refreshOrganizations()
      setSuccess(true)
      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        navigate('/app')
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to join organization')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 px-4">
      <Seo title="Join organization" noindex />
      <Card className="max-w-md w-full">
        {loading && (
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Joining organization...</p>
          </div>
        )}

        {success && (
          <div className="text-center py-12">
            <CheckCircleIcon className="w-16 h-16 text-success-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-secondary mb-2">Success!</h2>
            <p className="text-secondary-600 mb-4">You've successfully joined the organization.</p>
            <p className="text-sm text-secondary-500">Redirecting to dashboard...</p>
          </div>
        )}

        {error && (
          <div className="text-center py-12">
            <XCircleIcon className="w-16 h-16 text-error-500 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-secondary mb-2">Error</h2>
            <p className="text-secondary-600 mb-4">{error}</p>
            <Button onClick={() => navigate('/app')}>Go to Dashboard</Button>
          </div>
        )}
      </Card>
    </div>
  )
}

