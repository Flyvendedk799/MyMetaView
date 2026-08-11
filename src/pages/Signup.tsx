import { useState, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { CheckIcon, EnvelopeIcon, LockClosedIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { LogoMark } from '../components/ui/Logo'
import Seo from '../components/Seo'
import { getDemoContext } from '../lib/demoContext'

export default function Signup() {
  const { signup, error: authError, loading } = useAuth()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || undefined
  const demoContext = useMemo(() => getDemoContext(), [])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!email || !password || !confirmPassword) {
      setError('Please fill in all fields')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    try {
      setIsSubmitting(true)
      await signup(email, password, next)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  const features = [
    '14-day trial with Growth-plan limits',
    'Branded preview cards for your pages',
    'Impression, click & CTR analytics',
    'No credit card required',
  ]

  return (
    <div className="min-h-screen bg-paper flex flex-col lg:flex-row">
      <Seo title="Start free" description="Create a MetaView account and generate your first on-brand URL preview in minutes. Free 14-day trial, no credit card required." path="/signup" />
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-ink relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyek0zNiAzMHYySC0yNHYtMmgxMnoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-30" />
        
        <div className="absolute top-0 left-0 w-96 h-96 bg-white/10 rounded-full -ml-48 -mt-48 blur-3xl" />
        <div className="absolute bottom-0 right-0 w-80 h-80 bg-primary-400/20 rounded-full -mr-40 -mb-40 blur-3xl" />
        
        <div className="relative z-10 flex flex-col justify-center px-12 xl:px-20 text-white">
          <div className="flex items-center gap-3 mb-10">
            <LogoMark size={48} surface="dark" />
            <span className="font-display text-3xl font-semibold tracking-display">MetaView</span>
          </div>

          <h1 className="font-display text-4xl xl:text-5xl font-semibold mb-5 leading-tight tracking-display-lg">
            Start Creating<br />
            <span className="text-white/90">Amazing Previews</span>
          </h1>
          
          <p className="text-lg xl:text-xl text-white/75 max-w-md mb-10 leading-relaxed">
            {demoContext?.domain
              ? `Your demo preview for ${demoContext.domain} is ready to become the real thing.`
              : 'Turn every shared link into an on-brand preview that earns the click.'}
          </p>
          
          <ul className="space-y-4" aria-label="Included features">
            {features.map((feature, i) => (
              <li key={i} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                  <CheckIcon className="w-4 h-4 text-white" />
                </div>
                <span className="text-white/90 font-medium">{feature}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-10 xl:px-12 py-10 sm:py-12 lg:py-16">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-3 mb-10">
            <LogoMark size={44} />
            <span className="font-display text-2xl font-semibold text-secondary-900 tracking-display">MetaView</span>
          </div>

          <header className="text-center mb-10">
            <h1 className="font-display text-3xl sm:text-4xl font-semibold text-secondary-900 mb-3 tracking-display">
              Create your account
            </h1>
            <p className="text-base text-secondary-600 leading-relaxed">
              Start your free trial today — no credit card required
            </p>
          </header>

          <div className="card shadow-card p-6 sm:p-8">
            <form onSubmit={handleSubmit} className="space-y-6" noValidate>
              {(error || authError) && (
                <div 
                  className="alert alert-error animate-fade-in" 
                  role="alert" 
                  aria-live="assertive"
                >
                  <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <span>{error || authError}</span>
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

              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Create a strong password"
                leftIcon={<LockClosedIcon className="w-5 h-5" aria-hidden="true" />}
                helperText="Must be at least 6 characters"
                autoComplete="new-password"
              />

              <Input
                label="Confirm Password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                placeholder="Confirm your password"
                leftIcon={<LockClosedIcon className="w-5 h-5" aria-hidden="true" />}
                error={confirmPassword && password !== confirmPassword ? 'Passwords do not match' : undefined}
                autoComplete="new-password"
              />

              <Button 
                type="submit" 
                fullWidth
                size="lg"
                variant="gradient"
                loading={isSubmitting || loading}
                className="shadow-card"
                aria-busy={isSubmitting || loading}
              >
                Create Account
              </Button>

              <p className="text-center text-xs sm:text-sm text-secondary-600 leading-relaxed">
                By creating an account, you agree to our{' '}
                <Link to="/terms" className="text-primary-600 hover:text-primary-700 font-semibold hover:underline transition-colors">Terms of Service</Link>
                {' '}and{' '}
                <Link to="/privacy" className="text-primary-600 hover:text-primary-700 font-semibold hover:underline transition-colors">Privacy Policy</Link>
              </p>
            </form>
          </div>

          <p className="text-center text-sm text-secondary-600 mt-8 leading-relaxed">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-600 hover:text-primary-700 font-semibold transition-colors">
              Sign in
            </Link>
          </p>

          {/* Trust cue */}
          <p className="flex items-center justify-center gap-2 mt-8 text-xs text-secondary-500" aria-label="Secure signup">
            <ShieldCheckIcon className="w-4 h-4 text-success-500 flex-shrink-0" aria-hidden="true" />
            <span>Secure signup · Your data is protected</span>
          </p>
        </div>
      </div>
    </div>
  )
}
