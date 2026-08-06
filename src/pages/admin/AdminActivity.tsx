import { useState, useEffect, useCallback } from 'react'
import { ClipboardDocumentIcon, CheckIcon, FunnelIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { fetchAdminActivity, fetchAdminUsers, type AdminActivityLog } from '../../api/client'
import type { AdminUserSummary } from '../../api/types'

export default function AdminActivity() {
  const [logs, setLogs] = useState<AdminActivityLog[]>([])
  const [users, setUsers] = useState<AdminUserSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [filterUserId, setFilterUserId] = useState<number | undefined>(undefined)
  const [filterAction, setFilterAction] = useState<string>('')
  const [filterUrl, setFilterUrl] = useState<string>('')
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [copiedFullId, setCopiedFullId] = useState<number | null>(null)
  const [copiedSupportId, setCopiedSupportId] = useState<number | null>(null)
  const limit = 50

  useEffect(() => { loadUsers() }, [])
  useEffect(() => { loadLogs() }, [page, filterUserId, filterAction, filterUrl])

  const loadUsers = async () => {
    try {
      const data = await fetchAdminUsers()
      setUsers(data)
    } catch (err) {
      console.error('Failed to load users:', err)
    }
  }

  const loadLogs = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchAdminActivity(
        page * limit,
        limit,
        filterUserId,
        filterAction || undefined,
        filterUrl || undefined
      )
      setLogs(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity logs')
    } finally {
      setLoading(false)
    }
  }

  type LogWithMeta = AdminActivityLog & { extra_metadata?: Record<string, unknown> }

  /** Build a debug-friendly object for copying - always includes metadata explicitly */
  const buildCopyPayload = useCallback((log: LogWithMeta) => {
    const user = users.find((u) => u.id === log.user_id)
    const meta = log.metadata ?? log.extra_metadata ?? {}
    return {
      id: log.id,
      action: log.action,
      user: user?.email ?? log.user_id ?? 'system',
      ip: log.ip_address ?? null,
      time: log.created_at,
      metadata: meta,
    }
  }, [users])

  /** Build full debug object for copy - includes all fields */
  const buildFullPayload = useCallback((log: LogWithMeta) => {
    const meta = log.metadata ?? log.extra_metadata ?? {}
    return {
      id: log.id,
      action: log.action,
      user_id: log.user_id,
      organization_id: log.organization_id,
      ip_address: log.ip_address,
      user_agent: log.user_agent,
      created_at: log.created_at,
      metadata: meta,
    }
  }, [])

  const copyLogLine = useCallback(async (log: AdminActivityLog) => {
    const payload = buildCopyPayload(log)
    await navigator.clipboard.writeText(JSON.stringify(payload))
    setCopiedId(log.id)
    setTimeout(() => setCopiedId(null), 1500)
  }, [buildCopyPayload])

  /** Copy full log as pretty JSON - everything the API returned, for debugging */
  const copyLogFull = useCallback(async (log: LogWithMeta) => {
    const full = buildFullPayload(log)
    await navigator.clipboard.writeText(JSON.stringify(full, null, 2))
    setCopiedFullId(log.id)
    setTimeout(() => setCopiedFullId(null), 1500)
  }, [buildFullPayload])

  /** Copy human-readable support format + full JSON for pasting into tickets */
  const copyLogForSupport = useCallback(async (log: LogWithMeta) => {
    const user = users.find((u) => u.id === log.user_id)
    const meta = log.metadata ?? log.extra_metadata ?? {}
    const timeStr = new Date(log.created_at).toISOString()
    const lines: string[] = [
      '--- Activity Log (Debug) ---',
      `ID: ${log.id}`,
      `Action: ${log.action}`,
      `Time: ${timeStr}`,
      `User: ${user?.email ?? log.user_id ?? 'system'}`,
      `IP: ${log.ip_address ?? 'n/a'}`,
      `User-Agent: ${(log.user_agent || 'n/a').slice(0, 80)}`,
      '',
      '--- Metadata ---',
      ...Object.entries(meta).map(([k, v]) => {
        const val = typeof v === 'object' ? JSON.stringify(v) : String(v)
        return `${k}: ${val.slice(0, 200)}${val.length > 200 ? '...' : ''}`
      }),
      '',
      '--- Full JSON ---',
      JSON.stringify(buildFullPayload(log), null, 2),
    ]
    await navigator.clipboard.writeText(lines.join('\n'))
    setCopiedSupportId(log.id)
    setTimeout(() => setCopiedSupportId(null), 1500)
  }, [users, buildFullPayload])

  const copyAllVisible = useCallback(async () => {
    const lines = logs.map((log) => JSON.stringify(buildCopyPayload(log)))
    await navigator.clipboard.writeText(lines.join('\n'))
    setCopiedId(-1)
    setTimeout(() => setCopiedId(null), 1500)
  }, [logs, buildCopyPayload])

  const actionTypes = Array.from(new Set(logs.map((log) => log.action)))

  /** Format metadata into a concise single-line summary for the table */
  const summarizeMetadata = (log: LogWithMeta): string => {
    const m = log.metadata ?? log.extra_metadata
    if (!m || typeof m !== 'object') return ''

    const parts: string[] = []

    // URL is the most important field
    if (m.url) parts.push(m.url)

    // Outcome / status / source
    if (m.outcome) parts.push(`outcome=${m.outcome}`)
    if (m.status) parts.push(`status=${m.status}`)
    if (m.source) parts.push(`source=${m.source}`)

    // Job ID (for correlating with RQ)
    if (m.job_id) parts.push(`job=${String(m.job_id).slice(0, 12)}`)

    // Preview result fields
    if (m.title) parts.push(`"${String(m.title).slice(0, 50)}"`)
    if (m.template_type) parts.push(`template=${m.template_type}`)
    if (m.processing_time_ms != null) parts.push(`${m.processing_time_ms}ms`)
    if (m.confidence !== undefined) parts.push(`conf=${Number(m.confidence).toFixed(2)}`)
    if (m.overall_quality) parts.push(`quality=${m.overall_quality}`)
    if (m.design_fidelity != null) parts.push(`fidelity=${m.design_fidelity}`)
    if (m.coherence != null) parts.push(`coherence=${m.coherence}`)

    // Error / exception (critical for debugging)
    if (m.error) parts.push(`err="${String(m.error).slice(0, 60)}"`)
    if (m.exception_type) parts.push(`ex=${m.exception_type}`)

    // Warnings
    if (m.warnings && Array.isArray(m.warnings) && m.warnings.length > 0) {
      parts.push(`warnings=[${m.warnings.slice(0, 2).join(', ')}]`)
    }

    // Image flags
    if (m.image_url) parts.push(`img=yes`)
    if (m.has_composited_image !== undefined) parts.push(`composited=${m.has_composited_image}`)

    // Generic fallback: show first few keys
    if (parts.length === 0) {
      const keys = Object.keys(m).slice(0, 5)
      for (const k of keys) {
        const v = m[k]
        const vs = typeof v === 'object' ? JSON.stringify(v) : String(v)
        parts.push(`${k}=${vs.slice(0, 40)}`)
      }
    }

    return parts.join(' | ')
  }

  const getActionBadgeColor = (action: string) => {
    if (action.includes('completed')) return 'bg-success-50 text-success-500'
    if (action.includes('failed')) return 'bg-error-50 text-error-500'
    if (action.includes('job_created')) return 'bg-brand-100 text-primary-500'
    if (action.includes('admin')) return 'bg-secondary-100 text-secondary-700'
    return 'bg-secondary-100 text-secondary-600'
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="heading-3 mb-1">Activity</h1>
          <p className="text-secondary-500 text-sm">Each row is one event. Copy = one-line JSON. Full = pretty JSON. Support = human-readable + JSON for tickets.</p>
        </div>
        <Button
          onClick={copyAllVisible}
          variant="secondary"
          className="text-sm flex items-center gap-1.5"
        >
          {copiedId === -1 ? <CheckIcon className="w-4 h-4 text-success-500" /> : <ClipboardDocumentIcon className="w-4 h-4" />}
          {copiedId === -1 ? 'Copied!' : 'Copy all visible'}
        </Button>
      </div>

      {error && (
        <Card className="mb-4 bg-error-50 border-error-100">
          <p className="text-error-600 text-sm">Error: {error}</p>
        </Card>
      )}

      {/* Filters */}
      <Card className="mb-4 p-3">
        <div className="flex items-center gap-2 text-sm">
          <FunnelIcon className="w-4 h-4 text-secondary-400 shrink-0" />
          <select
            value={filterUserId || ''}
            onChange={(e) => { setFilterUserId(e.target.value ? parseInt(e.target.value) : undefined); setPage(0) }}
            className="px-2 py-1.5 bg-surface border border-secondary-300 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none"
          >
            <option value="">All Users</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>{user.email}</option>
            ))}
          </select>
          <select
            value={filterAction}
            onChange={(e) => { setFilterAction(e.target.value); setPage(0) }}
            className="px-2 py-1.5 bg-surface border border-secondary-300 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none"
          >
            <option value="">All Actions</option>
            {actionTypes.map((action) => (
              <option key={action} value={action}>{action}</option>
            ))}
          </select>
          <input
            type="text"
            value={filterUrl}
            onChange={(e) => setFilterUrl(e.target.value)}
            placeholder="Filter by URL..."
            className="flex-1 px-2 py-1.5 bg-surface border border-secondary-300 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none min-w-0"
          />
        </div>
      </Card>

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
            <p className="text-secondary-500 text-sm">Loading...</p>
          </div>
        </Card>
      ) : logs.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <p className="text-secondary-500 text-sm">No activity logs found.</p>
          </div>
        </Card>
      ) : (
        <>
          <div className="space-y-1">
            {logs.map((log) => {
              const user = users.find((u) => u.id === log.user_id)
              const isCopied = copiedId === log.id
              const isCopiedFull = copiedFullId === log.id
              const isCopiedSupport = copiedSupportId === log.id
              return (
                <div
                  key={log.id}
                  className="group flex items-start gap-2 px-3 py-2 bg-white border border-secondary-100 rounded-md hover:border-secondary-200 hover:bg-secondary-50/50 transition-colors font-mono text-xs leading-relaxed"
                >
                  {/* Copy one-line */}
                  <button
                    onClick={() => copyLogLine(log)}
                    className="shrink-0 mt-0.5 p-0.5 rounded hover:bg-secondary-200 transition-colors"
                    title="Copy one-line JSON (id, action, metadata)"
                  >
                    {isCopied
                      ? <CheckIcon className="w-3.5 h-3.5 text-success-600" />
                      : <ClipboardDocumentIcon className="w-3.5 h-3.5 text-secondary-400 group-hover:text-secondary-600" />
                    }
                  </button>
                  {/* Copy full */}
                  <button
                    onClick={() => copyLogFull(log)}
                    className="shrink-0 mt-0.5 px-1 py-0.5 rounded hover:bg-secondary-200 transition-colors text-[10px] text-secondary-400 group-hover:text-secondary-600"
                    title="Copy full log as pretty JSON"
                  >
                    {isCopiedFull ? 'âœ“' : 'full'}
                  </button>
                  {/* Copy for support */}
                  <button
                    onClick={() => copyLogForSupport(log)}
                    className="shrink-0 mt-0.5 px-1 py-0.5 rounded hover:bg-secondary-200 transition-colors text-[10px] text-secondary-400 group-hover:text-secondary-600"
                    title="Copy human-readable + JSON for support tickets"
                  >
                    {isCopiedSupport ? 'âœ“' : 'support'}
                  </button>

                  {/* Timestamp */}
                  <span className="shrink-0 text-secondary-400 tabular-nums">
                    {new Date(log.created_at).toLocaleString('en-US', {
                      month: '2-digit', day: '2-digit',
                      hour: '2-digit', minute: '2-digit', second: '2-digit',
                      hour12: false,
                    })}
                  </span>

                  {/* Action badge */}
                  <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${getActionBadgeColor(log.action)}`}>
                    {log.action}
                  </span>

                  {/* User */}
                  {(user || log.user_id) && (
                    <span className="shrink-0 text-secondary-500">
                      {user ? user.email.split('@')[0] : `#${log.user_id}`}
                    </span>
                  )}

                  {/* Metadata summary - the key debugging info */}
                  <span className="text-secondary-700 truncate min-w-0">
                    {summarizeMetadata(log)}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <Button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              variant="secondary"
              className="text-sm"
            >
              Previous
            </Button>
            <span className="text-secondary-500 text-sm">Page {page + 1}</span>
            <Button
              onClick={() => setPage(page + 1)}
              disabled={logs.length < limit}
              variant="secondary"
              className="text-sm"
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
