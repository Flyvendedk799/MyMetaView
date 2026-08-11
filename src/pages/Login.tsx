import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { EnvelopeIcon, LockClosedIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { LogoMark } from '../components/ui/Logo'
import Seo from '../components/Seo'

export default function Login() {
  const { login, error: authError, loading } = useAuth()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || undefined
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!email || !password) {
      setError('Please fill in all fields')
      return
    }

    try {
      setIsSubmitting(true)
      await login(email, password, next)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-paper flex flex-col lg:flex-row">
      <Seo title="Sign in" description="Sign in to your MetaView account to manage domains, previews, and brand settings." path="/login" />
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-ink relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyek0zNiAzMHYySC0yNHYtMmgxMnoiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-30" />
        
        <div className="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full -mr-48 -mt-48 blur-3xl" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-accent-400/20 rounded-full -ml-40 -mb-40 blur-3xl" />
        
        <div className="relative z-10 flex flex-col justify-center px-12 xl:px-20 text-white">
          <div className="flex items-center gap-3 mb-10">
            <LogoMark size={48} surface="dark" />
            <span className="font-display text-3xl font-semibold tracking-display">MetaView</span>
          </div>

          <h1 className="font-display text-4xl xl:text-5xl font-semibold mb-5 leading-tight tracking-display-lg">
            Beautiful Link Previews<br />
            <span className="text-white/90">for Your Brand</span>
          </h1>
          
          <p className="text-lg xl:text-xl text-white/75 max-w-md mb-10 leading-relaxed">
            Create stunning, customized link previews that capture attention and drive engagement across all platforms.
          </p>
          
          <div className="flex items-center gap-6">
            <div className="flex -space-x-3" aria-hidden="true">
              {['#12523F', '#E8622C', '#1F7A5C', '#0B3B2E'].map((color, i) => (
                <div 
                  key={i}
                  className="w-10 h-10 rounded-full border-2 border-white/20 flex items-center justify-center text-white text-sm font-medium"
                  style={{ backgroundColor: color }}
                >
                  {String.fromCharCode(65 + i)}
                </div>
              ))}
            </div>
            <p className="text-sm text-white/75 font-medium">
              Branded link previews, served to every platform
            </p>
          </div>
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
              Welcome back
            </h1>
            <p className="text-base text-secondary-600 leading-relaxed">
              Sign in to your account to continue
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
                placeholder="••••••••"
                leftIcon={<LockClosedIcon className="w-5 h-5" aria-hidden="true" />}
                autoComplete="current-password"
              />

              <div className="flex items-center justify-end text-sm">
                <Link 
                  to="/forgot-password" 
                  className="text-primary-600 hover:text-primary-700 font-semibold transition-colors"
                >
                  Forgot password?
                </Link>
              </div>

              <Button 
                type="submit" 
                fullWidth
                size="lg"
                loading={isSubmitting || loading}
                className="btn-primary"
                aria-busy={isSubmitting || loading}
              >
                Sign in
              </Button>

            </form>
          </div>

          <p className="text-center text-sm text-secondary-600 mt-8 leading-relaxed">
            Don't have an account?{' '}
            <Link to={next ? `/signup?next=${encodeURIComponent(next)}` : '/signup'} className="text-primary-600 hover:text-primary-700 font-semibold transition-colors">
              Sign up for free
            </Link>
          </p>

          {/* Trust cue */}
          <p className="flex items-center justify-center gap-2 mt-8 text-xs text-secondary-500" aria-label="Secure login">
            <ShieldCheckIcon className="w-4 h-4 text-success-500 flex-shrink-0" aria-hidden="true" />
            <span>Secure login · Your data is protected</span>
          </p>
        </div>
      </div>
    </div>
  )
}
