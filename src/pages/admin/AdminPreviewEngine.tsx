import { useState, useEffect, useCallback } from 'react'
import { ArrowPathIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import {
  fetchRecentDiagnoses,
  fetchPreviewCosts,
  fetchPreviewDiagnosis,
  type PreviewDiagnosis,
  type CostDashboard,
} from '../../api/client'

/**
 * The engine's "why" view.
 *
 * The question this page exists to answer is not "did the job fail?" — the
 * activity log already says that — but "why did this card come out generic
 * when the job says it finished?". Answering it used to mean tailing worker
 * logs. Every generation now carries an ordered trail of the fallbacks it took,
 * and this renders that trail as sentences, next to where the time and money
 * went.
 */

const VERDICT_STYLES: Record<string, string> = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  degraded: 'bg-amber-50 text-amber-700 border-amber-200',
  fallback: 'bg-orange-50 text-orange-700 border-orange-200',
  fail: 'bg-red-50 text-red-700 border-red-200',
  unknown: 'bg-gray-50 text-gray-600 border-gray-200',
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const style = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.unknown
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${style}`}>
      {verdict}
    </span>
  )
}

function ms(value: number | null | undefined): string {
  if (value == null) return '—'
  return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${Math.round(value)}ms`
}

function usd(value: number | null | undefined): string {
  if (!value) return '$0'
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(3)}`
}

/** The trail, rendered as the story it is: each step, what it means, what happened. */
function DegradationTrail({ diagnosis }: { diagnosis: PreviewDiagnosis }) {
  if (!diagnosis.degradations?.length) {
    return <p className="text-muted text-sm">No trace recorded for this generation.</p>
  }

  return (
    <ol className="space-y-2">
      {diagnosis.degradations.map((step, index) => {
        const explained = diagnosis.explanation?.find((e) => e.code === step.code)
        return (
          <li key={`${step.code}-${index}`} className="flex gap-3 text-sm">
            <span
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                step.healthy ? 'bg-emerald-400' : 'bg-amber-500'
              }`}
              aria-hidden
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-2">
                <code className="text-xs text-gray-500">{step.stage}</code>
                <span className={step.healthy ? 'text-gray-600' : 'font-medium text-gray-900'}>
                  {explained?.says ?? step.code.replace(/_/g, ' ')}
                </span>
              </div>
              {step.detail && (
                <p className="text-muted mt-0.5 break-words text-xs">{step.detail}</p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/** Where the time and the money went, per stage. */
function StageBreakdown({ diagnosis }: { diagnosis: PreviewDiagnosis }) {
  const stages = Object.entries(diagnosis.stage_ms ?? {})
  if (!stages.length) return null
  const slowest = Math.max(...stages.map(([, value]) => value), 1)

  return (
    <div className="space-y-1.5">
      {stages.map(([name, duration]) => {
        const cost = diagnosis.stage_costs?.[name]
        const overBudget = diagnosis.over_budget_stages?.includes(name)
        return (
          <div key={name} className="flex items-center gap-3 text-xs">
            <span className="w-24 shrink-0 text-gray-600">{name}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full rounded-full ${overBudget ? 'bg-amber-500' : 'bg-gray-400'}`}
                style={{ width: `${Math.max(2, (duration / slowest) * 100)}%` }}
              />
            </div>
            <span className="w-14 shrink-0 text-right tabular-nums text-gray-600">{ms(duration)}</span>
            <span className="w-16 shrink-0 text-right tabular-nums text-gray-500">
              {cost?.usd ? usd(cost.usd) : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function AdminPreviewEngine() {
  const [jobs, setJobs] = useState<PreviewDiagnosis[]>([])
  const [costs, setCosts] = useState<CostDashboard | null>(null)
  const [selected, setSelected] = useState<PreviewDiagnosis | null>(null)
  const [degradedOnly, setDegradedOnly] = useState(false)
  const [jobIdQuery, setJobIdQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [recent, cost] = await Promise.all([
        fetchRecentDiagnoses(50, degradedOnly),
        fetchPreviewCosts(100),
      ])
      setJobs(recent.jobs)
      setCosts(cost)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load engine diagnostics')
    } finally {
      setLoading(false)
    }
  }, [degradedOnly])

  useEffect(() => { load() }, [load])

  const lookUpJob = async () => {
    const jobId = jobIdQuery.trim()
    if (!jobId) return
    try {
      setError(null)
      setSelected(await fetchPreviewDiagnosis(jobId))
    } catch {
      setError(`No trace found for job ${jobId}. Traces are kept for 48 hours.`)
    }
  }

  const degradedCount = jobs.filter((job) => job.unhealthy_degradations?.length).length

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="heading-3 mb-2">Admin / Preview engine</h1>
          <p className="text-muted">
            Every generation records the fallbacks it took. This is where you find out
            why a card came out the way it did.
          </p>
        </div>
        <Button variant="secondary" onClick={load} disabled={loading}>
          <ArrowPathIcon className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {error && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <p className="text-sm text-red-700">{error}</p>
        </Card>
      )}

      {/* Cost + latency, over the recent window */}
      {costs && costs.samples > 0 && (
        <Card className="mb-6">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="font-medium">Cost and latency</h2>
            <span className="text-muted text-xs">last {costs.samples} generations</span>
          </div>
          <div className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <div className="text-2xl font-semibold tabular-nums">
                {usd(costs.cost_per_preview_usd)}
              </div>
              <div className="text-muted text-xs">per preview</div>
            </div>
            {Object.entries(costs.lanes).map(([lane, stats]) => (
              <div key={lane}>
                <div className="text-2xl font-semibold tabular-nums">{ms(stats.avg_ms)}</div>
                <div className="text-muted text-xs">{lane} lane · {stats.count} runs</div>
              </div>
            ))}
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted border-b text-left">
                <th className="pb-2 font-normal">Stage</th>
                <th className="pb-2 text-right font-normal">p50</th>
                <th className="pb-2 text-right font-normal">p95</th>
                <th className="pb-2 text-right font-normal">max</th>
                <th className="pb-2 text-right font-normal">AI cost</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(costs.stages)
                .sort(([, a], [, b]) => b.p95_ms - a.p95_ms)
                .map(([name, stats]) => (
                  <tr key={name} className="border-b last:border-0">
                    <td className="py-1.5">{name}</td>
                    <td className="py-1.5 text-right tabular-nums">{ms(stats.p50_ms)}</td>
                    <td className="py-1.5 text-right tabular-nums font-medium">{ms(stats.p95_ms)}</td>
                    <td className="text-muted py-1.5 text-right tabular-nums">{ms(stats.max_ms)}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {stats.cost_usd ? usd(stats.cost_usd) : '—'}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Look up one job by the id the activity log records */}
      <Card className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <MagnifyingGlassIcon className="h-4 w-4 shrink-0 text-gray-400" />
          <input
            className="input flex-1"
            placeholder="Job trace id (from the activity log's job_trace_id)"
            value={jobIdQuery}
            onChange={(event) => setJobIdQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') lookUpJob() }}
          />
          <Button onClick={lookUpJob} disabled={!jobIdQuery.trim()}>Look up</Button>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent generations */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-medium">Recent generations</h2>
            <label className="text-muted flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={degradedOnly}
                onChange={(event) => setDegradedOnly(event.target.checked)}
              />
              Degraded only
              {!degradedOnly && degradedCount > 0 && (
                <span className="text-amber-600">({degradedCount})</span>
              )}
            </label>
          </div>

          {loading ? (
            <p className="text-muted text-sm">Loading…</p>
          ) : jobs.length === 0 ? (
            <p className="text-muted text-sm">
              No traces yet. They appear here as previews are generated, and are kept
              for 48 hours.
            </p>
          ) : (
            <ul className="divide-y">
              {jobs.map((job) => (
                <li key={job.job_id ?? job.url ?? Math.random()}>
                  <button
                    type="button"
                    onClick={() => setSelected(job)}
                    className={`w-full py-2.5 text-left transition-colors hover:bg-gray-50 ${
                      selected?.job_id === job.job_id ? 'bg-gray-50' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-sm">{job.url ?? '(no url)'}</span>
                      <VerdictBadge verdict={job.verdict} />
                    </div>
                    <div className="text-muted mt-1 flex flex-wrap items-center gap-x-3 text-xs">
                      <span>{ms(job.total_ms)}</span>
                      {job.ai_cost_usd > 0 && <span>{usd(job.ai_cost_usd)}</span>}
                      {job.template && <span>{job.template}</span>}
                      {job.unhealthy_degradations?.length > 0 && (
                        <span className="text-amber-600">
                          {job.unhealthy_degradations.length} fallback
                          {job.unhealthy_degradations.length === 1 ? '' : 's'}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* The selected generation, explained */}
        <Card>
          {!selected ? (
            <p className="text-muted text-sm">
              Pick a generation to see the fallbacks it took and where its time went.
            </p>
          ) : (
            <div className="space-y-5">
              <div>
                <div className="mb-1 flex items-start justify-between gap-3">
                  <h2 className="min-w-0 break-all font-medium">{selected.url}</h2>
                  <VerdictBadge verdict={selected.verdict} />
                </div>
                <p className="text-muted font-mono text-xs">{selected.job_id}</p>
              </div>

              {selected.failure_reason && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3">
                  <p className="text-sm font-medium text-red-800">{selected.failure_reason}</p>
                  {selected.failure_detail && (
                    <p className="mt-1 break-words text-xs text-red-700">{selected.failure_detail}</p>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div>
                  <div className="text-muted text-xs">Total</div>
                  <div className="tabular-nums">{ms(selected.total_ms)}</div>
                </div>
                <div>
                  <div className="text-muted text-xs">AI cost</div>
                  <div className="tabular-nums">{usd(selected.ai_cost_usd)}</div>
                </div>
                <div>
                  <div className="text-muted text-xs">Layout</div>
                  <div>{selected.template ?? '—'}</div>
                </div>
                <div>
                  <div className="text-muted text-xs">Retries</div>
                  <div className="tabular-nums">{selected.retry_count}</div>
                </div>
              </div>

              <div>
                <h3 className="mb-2 text-sm font-medium">What happened</h3>
                <DegradationTrail diagnosis={selected} />
              </div>

              <div>
                <h3 className="mb-2 text-sm font-medium">Where the time went</h3>
                <StageBreakdown diagnosis={selected} />
                {selected.over_budget_stages?.length > 0 && (
                  <p className="mt-2 text-xs text-amber-600">
                    Over budget: {selected.over_budget_stages.join(', ')}
                  </p>
                )}
              </div>

              {selected.bottleneck_stage && (
                <p className="text-muted text-xs">
                  Slowest stage: <strong>{selected.bottleneck_stage.name}</strong>{' '}
                  ({ms(selected.bottleneck_stage.duration_ms)})
                </p>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
