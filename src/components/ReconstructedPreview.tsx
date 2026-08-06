/**
 * ReconstructedPreview Component
 *
 * Displays the AI-generated composited OG preview image from the backend.
 * When the composited image is unavailable or fails to load, falls back to
 * AdaptivePreview which renders a brand-aware, Design DNA-styled preview
 * directly from the extracted content — ensuring there is always something
 * beautiful to show.
 */

import { useState } from 'react'
import { DemoPreviewResponse } from '../api/client'
import AdaptivePreview from './AdaptivePreview'

interface ReconstructedPreviewProps {
  preview: DemoPreviewResponse
  className?: string
}

// Quality badge shown on hover
const QualityBadge = ({ quality, score }: { quality: string; score: number }) => {
  const colors: Record<string, string> = {
    excellent: 'bg-success-100 text-success-700 border-success-200',
    good: 'bg-primary-100 text-primary-700 border-primary-200',
    fair: 'bg-warning-100 text-warning-700 border-warning-200',
    poor: 'bg-secondary-100 text-secondary-600 border-secondary-200',
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors[quality] || colors.good}`}
    >
      {Math.round(score * 100)}% {quality}
    </span>
  )
}

export default function ReconstructedPreview({ preview, className = '' }: ReconstructedPreviewProps) {
  const { blueprint, composited_preview_image_url } = preview
  const [imageError, setImageError] = useState(false)

  return (
    <div className={`relative group ${className}`}>
      {/* Ambient glow effect on hover */}
      <div
        className="absolute -inset-1 rounded-3xl opacity-0 group-hover:opacity-30 blur-xl transition-opacity duration-500"
        style={{
          background: `linear-gradient(135deg, ${blueprint.primary_color}, ${blueprint.accent_color || blueprint.secondary_color})`,
        }}
      />

      {/* Preview content */}
      <div className="relative">
        {composited_preview_image_url && !imageError ? (
          // Primary: show the backend-composited OG image
          <div className="relative overflow-hidden rounded-2xl bg-white shadow-xl">
            <img
              src={composited_preview_image_url}
              alt={preview.title}
              className="w-full h-auto"
              onError={() => setImageError(true)}
            />
          </div>
        ) : (
          // Fallback: brand-aware Design DNA rendering when composited image is unavailable
          <AdaptivePreview preview={preview} />
        )}
      </div>

      {/* Quality indicators (revealed on hover) */}
      <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col gap-1 items-end">
        <QualityBadge quality={blueprint.overall_quality} score={blueprint.coherence_score} />
        {preview.design_fidelity_score !== undefined && preview.design_fidelity_score > 0 && (
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
              preview.design_fidelity_score >= 0.8
                ? 'bg-primary-100 text-primary-700 border-primary-200'
                : preview.design_fidelity_score >= 0.6
                ? 'bg-primary-100 text-primary-700 border-primary-200'
                : 'bg-secondary-100 text-secondary-600 border-secondary-200'
            }`}
          >
            🧬 {Math.round(preview.design_fidelity_score * 100)}% fidelity
          </span>
        )}
      </div>
    </div>
  )
}
