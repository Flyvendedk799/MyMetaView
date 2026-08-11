import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  UserIcon,
  GlobeAltIcon,
  PhotoIcon,
  CreditCardIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ClockIcon as ActivityIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonList } from '../components/ui/Skeleton'
import { fetchUserActivity, type ActivityLog } from '../api/client'

const ACTION_ICONS: Record<string, any> = {
  'user.login': UserIcon,
  'user.signup': UserIcon,
  'domain.created': GlobeAltIcon,
  'domain.deleted': GlobeAltIcon,
  'domain.verification.started': ClockIcon,
  'domain.verification.succeeded': CheckCircleIcon,
  'domain.verification.failed': XCircleIcon,
  'preview.created': PhotoIcon,
  'preview.updated': PhotoIcon,
  'preview.edited': PhotoIcon,
  'preview.deleted': PhotoIcon,
  'preview.ai_job.queued': ClockIcon,
  'preview.ai_job.completed': CheckCircleIcon,
  'preview.ai_job.failed': ExclamationTriangleIcon,
  'demo.preview.flow_step': SparklesIcon,
  'billing.subscription.created': CreditCardIcon,
  'billing.subscription.updated': CreditCardIcon,
  'billing.subscription.canceled': CreditCardIcon,
}

const ACTION_COLORS: Record<string, string> = {
  'user.login': 'text-primary-500',
  'user.signup': 'text-success-500',
  'domain.created': 'text-primary-500',
  'domain.deleted': 'text-error-500',
  'domain.verification.started': 'text-warning-500',
  'domain.verification.succeeded': 'text-success-500',
  'domain.verification.failed': 'text-error-500',
  'preview.created': 'text-primary',
  'preview.updated': 'text-primary',
  'preview.edited': 'text-primary',
  'preview.deleted': 'text-error-500',
  'preview.ai_job.queued': 'text-warning-500',
  'preview.ai_job.completed': 'text-success-500',
  'preview.ai_job.failed': 'text-error-500',
  'demo.preview.flow_step': 'text-primary-500',
  'billing.subscription.created': 'text-success-500',
  'billing.subscription.updated': 'text-primary-500',
  'billing.subscription.canceled': 'text-error-500',
}

function formatAction(action: string): string {
  // "preview.ai_job.completed" -> "Preview ai job completed", not the
  // machine-y "Preview Ai_job Completed".
  const words = action.split('.').join(' ').split('_').join(' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function getActionDescription(action: string, metadata: Record<string, any> | null): string {
  if (!metadata) {
    return formatAction(action)
  }
  if (action === 'user.login' || action === 'user.signup') {
    return `User ${action === 'user.login' ? 'logged in' : 'signed up'}`
  }
  if (action === 'domain.created') {
    return `Domain "${metadata.domain_name || 'Unknown'}" created`
  }
  if (action === 'domain.deleted') {
    return `Domain "${metadata.domain_name || 'Unknown'}" deleted`
  }
  if (action.startsWith('domain.verification')) {
    const domain = metadata.domain_name || 'Unknown'
    if (action.includes('succeeded')) return `Domain "${domain}" verified successfully`
    if (action.includes('failed')) return `Domain "${domain}" verification failed`
    return `Domain "${domain}" verification started (${metadata.method || 'unknown method'})`
  }
  if (action === 'preview.created') {
    return `Preview created for "${metadata.url || 'Unknown'}"`
  }
  if (action === 'preview.updated' || action === 'preview.edited') {
    return `Preview updated for "${metadata.url || 'Unknown'}"`
  }
  if (action === 'preview.deleted') {
    return `Preview "${metadata.title || metadata.url || 'Unknown'}" deleted`
  }
  if (action === 'preview.ai_job.queued') {
    return `AI preview generation queued for "${metadata.url || 'Unknown'}"`
  }
  if (action === 'preview.ai_job.completed') {
    return `AI preview generation completed for "${metadata.url || 'Unknown'}"`
  }
  if (action === 'preview.ai_job.failed') {
    return `AI preview generation failed for "${metadata.url || 'Unknown'}"`
  }
  if (action === 'demo.preview.flow_step') {
    const step = metadata.step ? String(metadata.step).replace(/_/g, ' ') : 'step'
    const status = metadata.status || 'updated'
    return `Demo preview flow ${status}: ${step} (${metadata.url || 'Unknown'})`
  }
  if (action.startsWith('billing.subscription')) {
    const plan = metadata.plan ? ` (${metadata.plan})` : ''
    if (action.includes('created')) return `Subscription created${plan}`
    if (action.includes('updated')) return `Subscription updated${plan}`
    if (action.includes('canceled')) return `Subscription canceled`
  }
  return formatAction(action)
}

export default function Activity() {
  const navigate = useNavigate()
  const [logs, setLogs] = useState<ActivityLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const limit = 50

  useEffect(() => {
    loadLogs()
  }, [page])

  const loadLogs = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchUserActivity(page * limit, limit)
      setLogs(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity logs')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Activity Log</h1>
        <p className="text-secondary-600">View your account activity and events</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <SkeletonList count={5} />
        </Card>
      ) : logs.length === 0 ? (
        <Card>
          <EmptyState
            icon={<ActivityIcon className="w-8 h-8" />}
            title="No activity yet"
            description="Your account activity and events will appear here as you use the platform. Start by adding a domain or generating your first preview."
            action={{
              label: 'Go to Dashboard',
              onClick: () => navigate('/app'),
            }}
          />
        </Card>
      ) : (
        <>
          <div className="space-y-4">
              {logs.map((log) => {
                const Icon = ACTION_ICONS[log.action] || ClockIcon
                const color = ACTION_COLORS[log.action] || 'text-secondary-500'
                return (
                  <Card key={log.id} className="p-4">
                    <div className="flex items-start space-x-4">
                      <div className={`flex-shrink-0 ${color}`}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <h3 className="font-semibold text-secondary-900">{formatAction(log.action)}</h3>
                          <span className="text-sm text-secondary-500">
                            {new Date(log.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-sm text-secondary-600">{getActionDescription(log.action, log.metadata)}</p>
                        {log.metadata && Object.keys(log.metadata).length > 0 && (
                          <details className="mt-2">
                            <summary className="text-xs text-secondary-500 cursor-pointer hover:text-secondary-700">
                              View metadata
                            </summary>
                            <pre className="mt-2 text-xs bg-secondary-50 p-2 rounded overflow-x-auto">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-6">
            <Button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              variant="secondary"
            >
              Previous
            </Button>
            <span className="text-secondary-600">Page {page + 1}</span>
            <Button
              onClick={() => setPage(page + 1)}
              disabled={logs.length < limit}
              variant="secondary"
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

