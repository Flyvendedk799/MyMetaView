/**
 * GenerationProgress Component
 * 
 * A premium, multi-stage progress indicator for AI preview generation.
 * Shows real-time status updates aligned with the AI workflow stages.
 * 
 * Design principles:
 * - Transparent: Users see exactly what's happening
 * - Trustworthy: Each stage has clear purpose
 * - Intentional: Animations and transitions feel designed
 * - Premium: Worthy of a high-ticket SaaS product
 */

import { useEffect, useState } from 'react'
import {
  CheckCircleIcon,
  CameraIcon,
  EyeIcon,
  SparklesIcon,
  AdjustmentsHorizontalIcon,
  DocumentCheckIcon,
  RocketLaunchIcon,
  TagIcon,
  PaintBrushIcon,
} from '@heroicons/react/24/outline'
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/react/24/solid'

export interface GenerationStage {
  id: string
  name: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  status: 'pending' | 'active' | 'completed'
  detail?: string
}

const DEFAULT_STAGES: GenerationStage[] = [
  {
    id: 'capture',
    name: 'Capturing Page',
    description: 'Taking a high-resolution screenshot',
    icon: CameraIcon,
    status: 'pending',
  },
  {
    id: 'classify',
    name: 'Page Classification',
    description: 'Identifying page type and structure',
    icon: TagIcon,
    status: 'pending',
  },
  {
    id: 'extract',
    name: 'Content Extraction',
    description: 'Extracting brand elements and content',
    icon: EyeIcon,
    status: 'pending',
  },
  {
    id: 'analyze',
    name: 'AI Analysis',
    description: 'Running multi-stage AI reasoning',
    icon: SparklesIcon,
    status: 'pending',
  },
  {
    id: 'normalize',
    name: 'Content Normalization',
    description: 'Standardizing extracted content',
    icon: AdjustmentsHorizontalIcon,
    status: 'pending',
  },
  {
    id: 'compose',
    name: 'Image Compositing',
    description: 'Generating preview image',
    icon: PaintBrushIcon,
    status: 'pending',
  },
  {
    id: 'quality',
    name: 'Quality Validation',
    description: 'Checking clarity, contrast, and fidelity',
    icon: DocumentCheckIcon,
    status: 'pending',
  },
  {
    id: 'finalize',
    name: 'Finalizing',
    description: 'Enriching result and caching',
    icon: RocketLaunchIcon,
    status: 'pending',
  },
]

/**
 * Failure reason codes from the backend (Phase 2 reason taxonomy).
 *
 * Keep this list in sync with
 * ``backend/services/preview/observability/reason_codes.py``.
 */
export type PreviewFailureReason =
  | 'capture_timeout'
  | 'capture_blocked'
  | 'capture_http_error'
  | 'capture_network_error'
  | 'extraction_low_confidence'
  | 'extraction_invalid_payload'
  | 'extraction_ai_rate_limit'
  | 'extraction_ai_auth'
  | 'extraction_ai_timeout'
  | 'render_font_fallback'
  | 'render_palette_fallback'
  | 'render_contrast_failed'
  | 'render_layout_overflow'
  | 'render_image_pipeline_error'
  | 'quality_gate_failed'
  | 'quality_budget_exceeded'
  | 'status_check_transient'
  | 'unknown'

/**
 * Frontend-facing reason copy. Mirrors the backend `user_message` map but
 * exposed at the component layer so designers can A/B test wording without
 * touching backend code.
 */
export const FAILURE_REASON_COPY: Record<PreviewFailureReason, string> = {
  capture_timeout:
    "The page took too long to load. We'll retry with a simpler capture.",
  capture_blocked:
    'The site blocked our preview crawler. Try a public URL or contact us.',
  capture_http_error:
    'The page responded with an error. Double-check the URL and try again.',
  capture_network_error:
    "We couldn't reach the page. Check the URL and try again.",
  extraction_low_confidence:
    "We couldn't read enough from the page to build a preview.",
  extraction_invalid_payload:
    "The page returned content we couldn't parse. We'll try a fallback.",
  extraction_ai_rate_limit:
    'Our AI provider rate-limited us. Please retry in a moment.',
  extraction_ai_auth:
    'Authentication issue with the AI provider — engineering is on it.',
  extraction_ai_timeout:
    "AI analysis timed out. We'll show a structured fallback.",
  render_font_fallback: 'We rendered the preview with a fallback font.',
  render_palette_fallback: 'We rendered the preview with a fallback palette.',
  render_contrast_failed: 'We adjusted text contrast to keep the preview readable.',
  render_layout_overflow: 'We trimmed text that would have overflowed the preview.',
  render_image_pipeline_error:
    "Image rendering hit an error — we used the screenshot as a fallback.",
  quality_gate_failed:
    "Quality didn't meet our bar so we shipped a safe fallback.",
  quality_budget_exceeded:
    'We hit our time budget and shipped the best result we had.',
  status_check_transient: 'Status check hiccup — refresh in a moment.',
  unknown: 'Something went wrong generating your preview.',
}

interface GenerationProgressProps {
  isGenerating: boolean
  currentStage?: number
  stages?: GenerationStage[]
  overallProgress?: number
  statusMessage?: string
  estimatedTimeRemaining?: number
  /**
   * Phase 5 — explicit finalization state.
   * When the backend has crossed the 95% threshold but is still running
   * post-processing (palette enforcement, visual quality fix-ups, cache
   * write), pass `isFinalizing` so the UI shows a labelled "Finalizing…"
   * stripe instead of plateauing at 95%.
   */
  isFinalizing?: boolean
  /**
   * Phase 5 — backend reason code for non-success terminal status. When set,
   * the component shows the matching copy from `FAILURE_REASON_COPY` and a
   * retry button that fires `onRetry`.
   */
  failureReason?: PreviewFailureReason
  failureDetail?: string
  onRetry?: () => void
}

export default function GenerationProgress({
  isGenerating,
  currentStage = 0,
  stages: customStages,
  overallProgress = 0,
  statusMessage,
  estimatedTimeRemaining,
  isFinalizing = false,
  failureReason,
  failureDetail,
  onRetry,
}: GenerationProgressProps) {
  const [stages, setStages] = useState<GenerationStage[]>(customStages || DEFAULT_STAGES)
  const [pulseStage, setPulseStage] = useState<string | null>(null)
  const [showDetail, setShowDetail] = useState<string | null>(null)

  // Update stage statuses based on currentStage
  useEffect(() => {
    if (!isGenerating) {
      setStages(prev => prev.map(s => ({ ...s, status: 'pending' as const })))
      return
    }

    setStages(prev => prev.map((stage, index) => ({
      ...stage,
      status: index < currentStage 
        ? 'completed' as const
        : index === currentStage 
          ? 'active' as const
          : 'pending' as const
    })))

    // Pulse animation for active stage
    const activeStage = stages[currentStage]
    if (activeStage) {
      setPulseStage(activeStage.id)
    }
  }, [currentStage, isGenerating])

  if (!isGenerating && !failureReason) return null

  const completedCount = stages.filter(s => s.status === 'completed').length
  const baseProgress = Math.max(overallProgress, (completedCount / stages.length) * 100)
  // Phase 5 — Trust UX. While we are in the explicit finalizing state,
  // animate progress between 95 and 99 instead of plateauing at 95.
  const progressPercent = isFinalizing
    ? Math.max(baseProgress, 95) + Math.min(4, (Date.now() % 4000) / 1000)
    : baseProgress

  if (failureReason) {
    return (
      <div className="w-full max-w-lg mx-auto">
        <div className="rounded-2xl border border-error-200 bg-error-50/70 p-5 text-error-900">
          <h3 className="text-base font-semibold mb-1">
            We couldn't finish your preview
          </h3>
          <p className="text-sm">{FAILURE_REASON_COPY[failureReason]}</p>
          {failureDetail ? (
            <p className="text-xs text-error-700/80 mt-2 break-words">
              {failureDetail}
            </p>
          ) : null}
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center px-3 py-1.5 rounded-lg bg-error-600 text-white text-sm font-medium hover:bg-error-700"
            >
              Try again
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Main Progress Card */}
      <div className="bg-white rounded-2xl shadow-2xl border border-secondary-200/80 overflow-hidden">
        {/* Header */}
        <div className="bg-primary-500 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="relative">
                <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                  <SparklesIcon className="w-6 h-6 text-white animate-pulse" />
                </div>
                {/* Spinning ring */}
                <div className="absolute inset-0 rounded-xl border-2 border-white/30 border-t-white animate-spin" style={{ animationDuration: '2s' }} />
              </div>
              <div>
                <h3 className="text-white font-bold text-lg">AI Working</h3>
                <p className="text-white/80 text-sm">{statusMessage || 'Analyzing your page...'}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-white font-bold text-2xl">{Math.round(progressPercent)}%</div>
              {isFinalizing ? (
                <div className="text-white/85 text-xs font-semibold">Finalizing…</div>
              ) : estimatedTimeRemaining && estimatedTimeRemaining > 0 && progressPercent < 92 ? (
                <div className="text-white/70 text-xs">~{Math.ceil(estimatedTimeRemaining)}s left</div>
              ) : progressPercent >= 92 && progressPercent < 100 ? (
                <div className="text-white/70 text-xs">Finalizing…</div>
              ) : null}
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className="mt-4 h-2 bg-white/20 rounded-full overflow-hidden">
            <div 
              className="h-full bg-white rounded-full transition-all duration-500 ease-out relative overflow-hidden"
              style={{ width: `${progressPercent}%` }}
            >
              {/* Shimmer effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
            </div>
          </div>
        </div>

        {/* Stages List */}
        <div className="p-4 space-y-1">
          {stages.map((stage, index) => {
            const StageIcon = stage.icon
            const isActive = stage.status === 'active'
            const isCompleted = stage.status === 'completed'
            const isPending = stage.status === 'pending'
            
            return (
              <div
                key={stage.id}
                className={`
                  relative flex items-center space-x-3 p-3 rounded-xl transition-all duration-300
                  ${isActive ? 'bg-accent-50 border border-accent-200' : ''}
                  ${isCompleted ? 'opacity-60' : ''}
                  ${isPending ? 'opacity-40' : ''}
                `}
                onMouseEnter={() => setShowDetail(stage.id)}
                onMouseLeave={() => setShowDetail(null)}
              >
                {/* Stage Number / Icon */}
                <div className={`
                  relative w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0
                  transition-all duration-300
                  ${isCompleted ? 'bg-success-500' : ''}
                  ${isActive ? 'bg-accent-500' : ''}
                  ${isPending ? 'bg-secondary-200' : ''}
                `}>
                  {isCompleted ? (
                    <CheckCircleSolidIcon className="w-6 h-6 text-white" />
                  ) : isActive ? (
                    <>
                      <StageIcon className="w-5 h-5 text-white" />
                      {/* Pulse ring for active */}
                      <div className="absolute inset-0 rounded-full bg-accent-500 animate-ping opacity-30" />
                    </>
                  ) : (
                    <span className="text-secondary-500 font-semibold text-sm">{index + 1}</span>
                  )}
                </div>

                {/* Stage Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className={`font-semibold text-sm ${isActive ? 'text-accent-700' : isCompleted ? 'text-secondary-600' : 'text-secondary-500'}`}>
                      {stage.name}
                    </span>
                    {isActive && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-accent-100 text-accent-700">
                        In Progress
                      </span>
                    )}
                    {isCompleted && (
                      <CheckCircleIcon className="w-4 h-4 text-success-500" />
                    )}
                  </div>
                  <p className={`text-xs mt-0.5 ${isActive ? 'text-accent-600' : 'text-secondary-400'}`}>
                    {stage.description}
                  </p>
                </div>

                {/* Connecting Line */}
                {index < stages.length - 1 && (
                  <div className={`
                    absolute left-7 top-14 w-0.5 h-4 -mt-1
                    ${isCompleted ? 'bg-success-300' : 'bg-secondary-200'}
                  `} />
                )}
              </div>
            )
          })}
        </div>

        {/* Footer Tips */}
        <div className="px-4 pb-4">
          <div className="bg-secondary-50 rounded-xl p-3 border border-secondary-100">
            <div className="flex items-start space-x-2">
              <SparklesIcon className="w-4 h-4 text-warning-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-secondary-600">
                  <span className="font-semibold text-secondary-700">AI Insight:</span>
                  {' '}Our multi-stage reasoning framework analyzes your page like a senior designer, identifying what matters most for social sharing.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Custom Animations */}
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        .animate-shimmer {
          animation: shimmer 1.5s infinite;
        }
      `}</style>
    </div>
  )
}

/**
 * Hook for managing generation progress state
 */
export function useGenerationProgress() {
  const [isGenerating, setIsGenerating] = useState(false)
  const [currentStage, setCurrentStage] = useState(0)
  const [overallProgress, setOverallProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [estimatedTime, setEstimatedTime] = useState(0)

  const startGeneration = () => {
    setIsGenerating(true)
    setCurrentStage(0)
    setOverallProgress(0)
    setStatusMessage('Initializing...')
    setEstimatedTime(30)
  }

  const advanceStage = (stageName?: string) => {
    setCurrentStage(prev => Math.min(prev + 1, 5))
    if (stageName) {
      setStatusMessage(stageName)
    }
  }

  const updateProgress = (progress: number, message?: string) => {
    setOverallProgress(progress)
    if (message) {
      setStatusMessage(message)
    }
    // Update estimated time based on progress
    const remaining = ((100 - progress) / 100) * 30
    setEstimatedTime(Math.max(0, remaining))
  }

  const completeGeneration = () => {
    setCurrentStage(6)
    setOverallProgress(100)
    setStatusMessage('Complete!')
    setTimeout(() => {
      setIsGenerating(false)
    }, 500)
  }

  const resetGeneration = () => {
    setIsGenerating(false)
    setCurrentStage(0)
    setOverallProgress(0)
    setStatusMessage('')
    setEstimatedTime(0)
  }

  return {
    isGenerating,
    currentStage,
    overallProgress,
    statusMessage,
    estimatedTime,
    startGeneration,
    advanceStage,
    updateProgress,
    completeGeneration,
    resetGeneration,
  }
}

