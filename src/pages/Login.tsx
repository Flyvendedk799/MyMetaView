import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { EnvelopeIcon, LockClosedIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { LogoMark } from '../components/ui/Logo'
import Seo from '../components/Seo'

export default function Login() {
  const { login, error: authError, loading } = useAuth()
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
      await login(email, password)
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
              <span className="font-extrabold text-white">2,500+</span> teams trust MetaView
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

          <div className="card shadow-soft-lg p-6 sm:p-8">
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

              <div className="flex items-center justify-between text-sm gap-4">
                <label className="flex items-center gap-2.5 cursor-pointer select-none">
                  <input 
                    type="checkbox" 
                    className="w-4 h-4 text-primary-500 border-secondary-300 rounded focus:ring-primary-500 focus:ring-offset-0" 
                    aria-describedby="remember-desc"
                  />
                  <span id="remember-desc" className="text-secondary-600 font-medium">Remember me</span>
                </label>
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

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-secondary-200" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-white text-secondary-500 font-medium">or continue with</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  className="btn btn-secondary justify-center py-3 font-medium"
                  aria-label="Sign in with Google"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  <span>Google</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary justify-center py-3 font-medium"
                  aria-label="Sign in with GitHub"
                >
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                  <span>GitHub</span>
                </button>
              </div>
            </form>
          </div>

          <p className="text-center text-sm text-secondary-600 mt-8 leading-relaxed">
            Don't have an account?{' '}
            <Link to="/signup" className="text-primary-600 hover:text-primary-700 font-semibold transition-colors">
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
