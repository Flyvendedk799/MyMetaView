import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeAntigravityLogin, completeClaudeLogin } from '../api/client'

/**
 * Finishes an AI provider redirect when the code comes back in the query.
 * The verifier stays in sessionStorage, which is what makes this work across
 * more than one API worker. Paste on the account page remains the fallback.
 */
export default function AiCallback() {
  const navigate = useNavigate()
  const [message, setMessage] = useState('Finishing the connection…')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const state = params.get('state')
    const raw = sessionStorage.getItem('mv_ai_oauth')
    if (!code || !state || !raw) {
      setMessage('Missing the login code. Paste it on the account page instead.')
      return
    }
    let saved: { provider: string; verifier: string; state: string; scope: 'user' | 'org'; orgId?: number }
    try {
      saved = JSON.parse(raw)
    } catch {
      setMessage('Could not read the saved login. Start again from account settings.')
      return
    }
    if (saved.state && saved.state !== state) {
      setMessage('This redirect does not match the login you started. Paste the URL on the account page.')
      return
    }
    const finish = saved.provider === 'antigravity' ? completeAntigravityLogin : completeClaudeLogin
    finish(code, state, saved.verifier, saved.scope, saved.orgId)
      .then(() => {
        sessionStorage.removeItem('mv_ai_oauth')
        navigate('/app/account', { replace: true })
      })
      .catch((err) => {
        setMessage(err instanceof Error ? err.message : 'Could not finish the connection')
      })
  }, [navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4">
      <p className="text-secondary-700">{message}</p>
    </div>
  )
}
