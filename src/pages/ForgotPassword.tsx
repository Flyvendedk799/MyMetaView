import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EnvelopeIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { LogoMark } from '../components/ui/Logo'
import Seo from '../components/Seo'
import { requestPasswordReset } from '../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!email) {
      setError('Enter the email you signed up with.')
      return
    }
    try {
      setSubmitting(true)
      await requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-4 py-12">
      <Seo title="Reset your password" description="Request a password reset link for your MetaView account." path="/forgot-password" />
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-3 mb-10">
          <LogoMark size={44} />
          <span className="font-display text-2xl font-semibold text-secondary-900 tracking-display">MetaView</span>
        </div>

        <div className="card shadow-card p-6 sm:p-8">
          {sent ? (
            <div className="text-center">
              <CheckCircleIcon className="w-12 h-12 text-success-500 mx-auto mb-4" />
              <h1 className="font-display text-2xl font-semibold text-secondary-900 mb-2 tracking-display-sm">
                Check your inbox
              </h1>
              <p className="text-secondary-600 mb-6">
                If <span className="font-medium text-secondary-900">{email}</span> has
                an account, a reset link is on its way. The link is valid for 30 minutes.
              </p>
              <Link to="/login" className="text-primary-600 hover:text-primary-700 font-semibold text-sm">
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <header className="text-center mb-8">
                <h1 className="font-display text-2xl sm:text-3xl font-semibold text-secondary-900 mb-2 tracking-display-sm">
                  Forgot your password?
                </h1>
                <p className="text-secondary-600">
                  Enter your email and we'll send you a link to choose a new one.
                </p>
              </header>

              <form onSubmit={handleSubmit} className="space-y-6" noValidate>
                {error && (
                  <div className="alert alert-error" role="alert">
                    <span>{error}</span>
                  </div>
                )}
                <Input
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                  leftIcon={<EnvelopeIcon className="w-5 h-5" aria-hidden="true" />}
                  autoComplete="email"
                />
                <Button type="submit" fullWidth size="lg" loading={submitting}>
                  Send reset link
                </Button>
              </form>

              <p className="text-center text-sm text-secondary-600 mt-6">
                Remembered it?{' '}
                <Link to="/login" className="text-primary-600 hover:text-primary-700 font-semibold">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
