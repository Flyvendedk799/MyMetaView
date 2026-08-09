import { XMarkIcon, CheckIcon, GlobeAltIcon } from '@heroicons/react/24/outline'
import GenerationProgress from './GenerationProgress'

interface DemoGeneratingProps {
  isGenerating: boolean
  currentStage: number
  progress: number
  statusMessage: string
  estimatedTimeRemaining: number
  url: string
  showCelebration: boolean
  onCancel: () => void
}

export default function DemoGenerating({
  isGenerating,
  currentStage,
  progress,
  statusMessage,
  estimatedTimeRemaining,
  url,
  showCelebration,
  onCancel,
}: DemoGeneratingProps) {
  if (!isGenerating) return null

  return (
    // overflow-y-auto + a min-h-full centering wrapper: the progress card (8
    // stages + header + footer) is taller than a laptop viewport, so a plain
    // `items-center` overlay clipped the top/bottom stages. Now it centers when
    // it fits and scrolls when it doesn't — every stage is reachable.
    <div className="fixed inset-0 z-40 overflow-y-auto bg-ink/95 animate-fade-in">
      {/* Cancel button — pinned to the viewport so it stays reachable while scrolling */}
      <button
        onClick={onCancel}
        className="fixed top-4 right-4 z-10 p-3 text-paper/70 hover:text-paper hover:bg-paper/10 rounded-xl transition-colors"
        aria-label="Cancel preview generation"
      >
        <XMarkIcon className="w-6 h-6" />
      </button>

      <div className="min-h-full flex items-center justify-center p-4 py-12">
        {showCelebration ? (
          <div className="relative text-center animate-scale-in">
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
              {[...Array(20)].map((_, i) => (
                <div
                  key={i}
                  className="absolute w-3 h-3 rounded-full animate-float-up"
                  style={{
                    left: `${(i * 53) % 100}%`,
                    backgroundColor: ['#E8622C', '#12523F', '#34d399', '#0B3B2E', '#F2A98C'][i % 5],
                    animationDelay: `${(i % 5) * 0.1}s`,
                    animationDuration: `${1 + (i % 3) * 0.3}s`,
                  }}
                />
              ))}
            </div>

            <div className="relative">
              <div className="w-24 h-24 bg-success-500 rounded-full flex items-center justify-center mx-auto animate-bounce">
                <CheckIcon className="w-12 h-12 text-white" />
              </div>
              <div className="absolute inset-0 rounded-full bg-success-400 animate-ping opacity-30" />
            </div>

            <h2 className="mt-6 font-display font-semibold text-3xl text-paper">Preview Ready!</h2>
            <p className="mt-2 text-paper/70">AI analysis complete</p>
          </div>
        ) : (
          <div className="w-full max-w-xl">
            <GenerationProgress
              isGenerating={isGenerating}
              currentStage={currentStage}
              overallProgress={progress}
              statusMessage={statusMessage}
              estimatedTimeRemaining={estimatedTimeRemaining}
            />

            <div className="mt-6 text-center">
              <p className="text-paper/60 text-sm mb-2">Analyzing:</p>
              <div className="bg-paper/10 rounded-lg px-4 py-2 inline-flex items-center gap-2 max-w-full">
                <GlobeAltIcon className="w-4 h-4 text-accent-400 flex-shrink-0" />
                <span className="text-paper/90 font-mono text-sm truncate">{url}</span>
              </div>
            </div>

            <p className="mt-8 text-center text-paper/40 text-xs">
              Our AI is analyzing your page using multi-stage reasoning...
            </p>
            <p className="mt-4 text-center text-paper/30 text-xs">
              Press Escape or click X to cancel
            </p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes float-up {
          0% { transform: translateY(100vh) rotate(0deg); opacity: 1; }
          100% { transform: translateY(-100vh) rotate(720deg); opacity: 0; }
        }
        .animate-float-up {
          animation: float-up var(--duration, 1.5s) ease-out forwards;
        }
        @keyframes scale-in {
          0% { transform: scale(0.5); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }
        .animate-scale-in {
          animation: scale-in 0.5s ease-out forwards;
        }
      `}</style>
    </div>
  )
}
