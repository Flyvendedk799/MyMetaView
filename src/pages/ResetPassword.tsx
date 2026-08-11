import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { LockClosedIcon } from '@heroicons/react/24/outline'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { LogoMark } from '../components/ui/Logo'
import Seo from '../components/Seo'
import { resetPassword } from '../api/client'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    try {
      setSubmitting(true)
      await resetPassword(token, password)
      navigate('/login?reset=success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed. The link may have expired.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-4 py-12">
      <Seo title="Choose a new password" description="Set a new password for your MetaView account." path="/reset-password" />
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-10">
          <LogoMark size={44} />
          <span className="font-display text-2xl font-semibold text-secondary-900 tracking-display">MetaView</span>
        </div>

        <div className="card shadow-card p-6 sm:p-8">
          {!token ? (
            <div className="text-center">
              <h1 className="font-display text-2xl font-semibold text-secondary-900 mb-2 tracking-display-sm">
                This link is incomplete
              </h1>
              <p className="text-secondary-600 mb-6">
                Open the reset link from your email again, or request a new one.
              </p>
              <Link to="/forgot-password" className="text-primary-600 hover:text-primary-700 font-semibold text-sm">
                Request a new link
              </Link>
            </div>
          ) : (
            <>
              <header className="text-center mb-8">
                <h1 className="font-display text-2xl sm:text-3xl font-semibold text-secondary-900 mb-2 tracking-display-sm">
                  Choose a new password
                </h1>
                <p className="text-secondary-600">At least 8 characters.</p>
              </header>

              <form onSubmit={handleSubmit} className="space-y-6" noValidate>
                {error && (
                  <div className="alert alert-error" role="alert">
                    <span>{error}</span>
                  </div>
                )}
                <Input
                  label="New password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  leftIcon={<LockClosedIcon className="w-5 h-5" aria-hidden="true" />}
                  autoComplete="new-password"
                />
                <Input
                  label="Confirm new password"
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  placeholder="••••••••"
                  leftIcon={<LockClosedIcon className="w-5 h-5" aria-hidden="true" />}
                  autoComplete="new-password"
                />
                <Button type="submit" fullWidth size="lg" loading={submitting}>
                  Update password
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
