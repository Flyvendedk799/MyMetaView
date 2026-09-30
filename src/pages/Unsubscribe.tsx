import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getApiBaseUrl } from '../api/client'

export default function Unsubscribe() {
  const [params] = useSearchParams()
  const [message, setMessage] = useState('Unsubscribing…')

  useEffect(() => {
    const token = params.get('token')
    if (!token) {
      setMessage('This unsubscribe link is missing its token.')
      return
    }
    const query = new URLSearchParams({ token })
    fetch(`${getApiBaseUrl()}/api/v1/newsletter/unsubscribe?${query}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}))
        setMessage(res.ok ? (body.message || 'You are unsubscribed.') : (body.detail || 'This link is not valid.'))
      })
      .catch(() => setMessage('Could not reach the server.'))
  }, [params])

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper px-4">
      <p className="text-secondary-800">{message}</p>
    </div>
  )
}
