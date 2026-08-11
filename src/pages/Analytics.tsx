import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChartBarIcon, InformationCircleIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Alert from '../components/ui/Alert'
import EmptyState from '../components/ui/EmptyState'
import {
  fetchAnalyticsOverview,
  fetchDomainAnalytics,
  fetchPreviewAnalytics,
} from '../api/client'
import type {
  AnalyticsOverview,
  DomainAnalyticsItem,
  PreviewAnalyticsItem,
  TimeseriesPoint,
} from '../api/types'

type Days = 7 | 30 | 90

// Series colors: validated for CVD separation and contrast on the light
// surface (dataviz palette checks) — data colors, distinct from UI accents.
const IMPRESSIONS_COLOR = '#2563EB'
const CLICKS_COLOR = '#D97706'

/**
 * Two-series time chart: impressions + clicks per day, one shared y-axis
 * (both are event counts). Inline SVG — crosshair hover with a tooltip,
 * legend chips, quiet gridlines.
 */
function EngagementChart({
  impressions,
  clicks,
}: {
  impressions: TimeseriesPoint[]
  clicks: TimeseriesPoint[]
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const W = 720
  const H = 240
  const PAD = { top: 12, right: 12, bottom: 26, left: 40 }
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom

  const n = impressions.length
  const maxValue = Math.max(
    1,
    ...impressions.map((p) => p.value),
    ...clicks.map((p) => p.value)
  )
  // Headroom so the peak doesn't kiss the top edge.
  const yMax = Math.ceil(maxValue * 1.15)

  const x = (i: number) => PAD.left + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW)
  const y = (v: number) => PAD.top + plotH - (v / yMax) * plotH

  const linePath = (points: TimeseriesPoint[]) =>
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')

  const gridValues = [0, Math.round(yMax / 2), yMax]
  const tickEvery = Math.max(1, Math.floor(n / 6))

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const i = Math.round(((px - PAD.left) / plotW) * (n - 1))
    setHoverIndex(Math.max(0, Math.min(n - 1, i)))
  }

  const fmtDate = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

  const hover = hoverIndex !== null && impressions[hoverIndex]
    ? {
        date: fmtDate(impressions[hoverIndex].date),
        impressions: impressions[hoverIndex].value,
        clicks: clicks[hoverIndex]?.value ?? 0,
        cx: x(hoverIndex),
      }
    : null

  return (
    <div>
      <div className="flex items-center gap-4 mb-3">
        <span className="inline-flex items-center gap-1.5 text-[13px] text-secondary-700">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: IMPRESSIONS_COLOR }} />
          Impressions
        </span>
        <span className="inline-flex items-center gap-1.5 text-[13px] text-secondary-700">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: CLICKS_COLOR }} />
          Clicks
        </span>
        {hover && (
          <span className="ml-auto text-[13px] text-secondary-600 tabular-nums">
            {hover.date} · <span style={{ color: IMPRESSIONS_COLOR }}>{hover.impressions.toLocaleString()}</span>
            {' / '}
            <span style={{ color: CLICKS_COLOR }}>{hover.clicks.toLocaleString()}</span>
          </span>
        )}
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto select-none"
        role="img"
        aria-label="Daily impressions and clicks"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* Gridlines + y labels */}
        {gridValues.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(v)}
              y2={y(v)}
              stroke="#E7E5E0"
              strokeWidth="1"
            />
            <text x={PAD.left - 6} y={y(v) + 3.5} textAnchor="end" fontSize="10" fill="#8A857C">
              {v.toLocaleString()}
            </text>
          </g>
        ))}

        {/* X tick labels */}
        {impressions.map((p, i) =>
          i % tickEvery === 0 ? (
            <text key={p.date} x={x(i)} y={H - 8} textAnchor="middle" fontSize="10" fill="#8A857C">
              {fmtDate(p.date)}
            </text>
          ) : null
        )}

        {/* Series */}
        <path d={linePath(impressions)} fill="none" stroke={IMPRESSIONS_COLOR} strokeWidth="2" strokeLinejoin="round" />
        <path d={linePath(clicks)} fill="none" stroke={CLICKS_COLOR} strokeWidth="2" strokeLinejoin="round" />

        {/* Crosshair + hover markers */}
        {hover && (
          <g>
            <line x1={hover.cx} x2={hover.cx} y1={PAD.top} y2={PAD.top + plotH} stroke="#B8B3A9" strokeWidth="1" strokeDasharray="3 3" />
            <circle cx={hover.cx} cy={y(hover.impressions)} r="4" fill={IMPRESSIONS_COLOR} stroke="#FFFFFF" strokeWidth="2" />
            <circle cx={hover.cx} cy={y(hover.clicks)} r="4" fill={CLICKS_COLOR} stroke="#FFFFFF" strokeWidth="2" />
          </g>
        )}
      </svg>
    </div>
  )
}

export default function Analytics() {
  const navigate = useNavigate()
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [domains, setDomains] = useState<DomainAnalyticsItem[]>([])
  const [previews, setPreviews] = useState<PreviewAnalyticsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState<Days>(30)

  const loadAnalytics = useCallback(async (window: Days) => {
    try {
      setLoading(true)
      setError(null)
      const [overviewData, domainsData, previewsData] = await Promise.all([
        fetchAnalyticsOverview(window),
        fetchDomainAnalytics(),
        fetchPreviewAnalytics(10),
      ])
      setOverview(overviewData)
      setDomains(domainsData)
      setPreviews(previewsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAnalytics(days)
  }, [days, loadAnalytics])

  const hasData = overview && (overview.total_impressions > 0 || overview.total_clicks > 0)

  const sortedDomains = useMemo(
    () => [...domains].sort((a, b) => b.impressions_30d - a.impressions_30d).slice(0, 5),
    [domains]
  )

  return (
    <div>
      <div className="mb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Analytics</h1>
          <p className="text-[15px] text-secondary-600">
            Impressions are crawler fetches of your previews; clicks are visitors arriving from social links.
          </p>
        </div>
        {/* Period switcher */}
        <div className="inline-flex rounded-lg border border-line overflow-hidden self-start">
          {([7, 30, 90] as Days[]).map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-4 py-2 text-[13px] font-medium transition-colors ${
                days === d
                  ? 'bg-secondary-900 text-paper'
                  : 'bg-surface text-secondary-600 hover:text-secondary-900'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mb-6">
          <Alert variant="error" title="Analytics failed to load">{error}</Alert>
        </div>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4"></div>
            <p className="text-secondary-500">Loading analytics...</p>
          </div>
        </Card>
      ) : !hasData ? (
        <Card>
          <EmptyState
            icon={<ChartBarIcon className="w-8 h-8" />}
            title="No engagement recorded yet"
            description="Data appears here once your previews are being served: an impression is counted when a social platform fetches a preview, and a click when a visitor arrives at your site from a social link. Both require a verified domain with the install completed."
            action={{
              label: 'Open the install guide',
              onClick: () => navigate('/app/install'),
            }}
          />
          <div className="mt-4 mx-auto max-w-lg flex items-start gap-2 text-[13px] text-secondary-500">
            <InformationCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              Quick test: share a preview-covered page in a private Slack channel or run it
              through a platform's link debugger — the crawler fetch shows up here as an impression.
            </p>
          </div>
        </Card>
      ) : overview ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <Card padding="sm" className="!p-5">
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Impressions</span>
              <p className="font-display text-[32px] leading-tight font-semibold tracking-display text-secondary-900 tabular-nums mt-1">
                {overview.total_impressions.toLocaleString()}
              </p>
              <p className="text-[13px] text-secondary-600 mt-1">Preview fetches by platforms · last {days} days</p>
            </Card>
            <Card padding="sm" className="!p-5">
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Clicks</span>
              <p className="font-display text-[32px] leading-tight font-semibold tracking-display text-secondary-900 tabular-nums mt-1">
                {overview.total_clicks.toLocaleString()}
              </p>
              <p className="text-[13px] text-secondary-600 mt-1">Visitors from social links · last {days} days</p>
            </Card>
            <Card padding="sm" className="!p-5">
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Click-through rate</span>
              <p className="font-display text-[32px] leading-tight font-semibold tracking-display text-secondary-900 tabular-nums mt-1">
                {overview.ctr.toFixed(1)}%
              </p>
              <p className="text-[13px] text-secondary-600 mt-1">Clicks ÷ impressions</p>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Engagement over time */}
            <Card className="lg:col-span-2">
              <h3 className="text-[17px] font-semibold text-secondary-900 mb-4">Engagement over time</h3>
              <EngagementChart
                impressions={overview.impressions_timeseries}
                clicks={overview.clicks_timeseries}
              />
            </Card>

            {/* Top domains */}
            <Card>
              <h3 className="text-[17px] font-semibold text-secondary-900 mb-4">Top domains</h3>
              <div className="space-y-4">
                {sortedDomains.length === 0 ? (
                  <p className="text-sm text-secondary-500">No domain data yet.</p>
                ) : (
                  sortedDomains.map((item) => (
                    <div key={item.domain_id} className="flex items-center justify-between pb-4 border-b border-secondary-100 last:border-0 last:pb-0">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-secondary-900 truncate">{item.domain_name}</p>
                        <p className="text-xs text-secondary-500">
                          {item.impressions_30d.toLocaleString()} impression{item.impressions_30d === 1 ? '' : 's'} · {item.clicks_30d.toLocaleString()} click{item.clicks_30d === 1 ? '' : 's'}
                        </p>
                      </div>
                      <div className="text-right ml-3">
                        <p className="text-sm font-semibold text-secondary-900 tabular-nums">{item.ctr_30d.toFixed(1)}%</p>
                        <p className="text-xs text-secondary-500">CTR</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>

          {/* Top previews */}
          <Card>
            <h3 className="text-[17px] font-semibold text-secondary-900 mb-4">Top previews · last 30 days</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-secondary-200">
                    <th className="text-left py-3 px-4 text-[13px] font-semibold text-secondary-700">Preview</th>
                    <th className="text-left py-3 px-4 text-[13px] font-semibold text-secondary-700">Domain</th>
                    <th className="text-right py-3 px-4 text-[13px] font-semibold text-secondary-700">Impressions</th>
                    <th className="text-right py-3 px-4 text-[13px] font-semibold text-secondary-700">Clicks</th>
                    <th className="text-right py-3 px-4 text-[13px] font-semibold text-secondary-700">CTR</th>
                  </tr>
                </thead>
                <tbody>
                  {previews.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="text-center py-8 text-secondary-500">
                        No per-preview data yet.
                      </td>
                    </tr>
                  ) : (
                    previews.map((item) => (
                      <tr key={item.preview_id} className="border-b border-secondary-100 hover:bg-secondary-50">
                        <td className="py-3 px-4">
                          <p className="text-sm font-medium text-secondary-900">{item.title}</p>
                          <p className="font-mono text-xs text-secondary-500 line-clamp-1">{item.url}</p>
                        </td>
                        <td className="py-3 px-4 text-sm text-secondary-600">{item.domain}</td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900 tabular-nums">
                          {item.impressions_30d.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-sm text-secondary-900 tabular-nums">
                          {item.clicks_30d.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-sm font-semibold text-secondary-900 tabular-nums">
                          {item.ctr_30d.toFixed(1)}%
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  )
}
