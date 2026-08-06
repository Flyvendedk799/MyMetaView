/**
 * AdaptivePreview Component
 * 
 * Design DNA-aware preview component that adapts its appearance based on the
 * extracted design philosophy of the original website.
 * 
 * This component honors the original design's:
 * - Typography personality (authoritative, friendly, elegant, etc.)
 * - Color emotion (trust, energy, calm, sophistication, etc.)
 * - Spatial density (compact, balanced, spacious, ultra-minimal)
 * - Visual style (minimalist, maximalist, corporate, luxurious, etc.)
 * 
 * Unlike fixed templates, this component dynamically adjusts its styling
 * to match the brand's DNA, creating previews that feel like they belong
 * to the original design system.
 */

import { useMemo } from 'react'
import { DemoPreviewResponse, DesignDNA } from '../api/client'

interface AdaptivePreviewProps {
  preview: DemoPreviewResponse
  className?: string
}

// =============================================================================
// STYLE MAPPINGS
// =============================================================================

// Typography styles based on personality
const typographyStyles: Record<string, {
  headlineClass: string
  bodyClass: string
  letterSpacing: string
  fontWeight: string
}> = {
  authoritative: {
    headlineClass: 'font-black tracking-tight',
    bodyClass: 'font-medium',
    letterSpacing: '-0.02em',
    fontWeight: '900'
  },
  friendly: {
    headlineClass: 'font-bold tracking-normal',
    bodyClass: 'font-normal',
    letterSpacing: '0',
    fontWeight: '700'
  },
  elegant: {
    headlineClass: 'font-semibold tracking-wide',
    bodyClass: 'font-light',
    letterSpacing: '0.05em',
    fontWeight: '600'
  },
  technical: {
    headlineClass: 'font-bold tracking-tight font-mono',
    bodyClass: 'font-normal font-mono',
    letterSpacing: '-0.01em',
    fontWeight: '700'
  },
  bold: {
    headlineClass: 'font-black tracking-tighter',
    bodyClass: 'font-medium',
    letterSpacing: '-0.03em',
    fontWeight: '900'
  },
  subtle: {
    headlineClass: 'font-semibold tracking-normal',
    bodyClass: 'font-normal',
    letterSpacing: '0',
    fontWeight: '600'
  },
  expressive: {
    headlineClass: 'font-black tracking-tight uppercase',
    bodyClass: 'font-medium',
    letterSpacing: '-0.02em',
    fontWeight: '900'
  }
}

// Spacing styles based on density
const spacingStyles: Record<string, {
  padding: string
  gap: string
  margin: string
}> = {
  compact: {
    padding: 'p-4',
    gap: 'gap-2',
    margin: 'mb-2'
  },
  balanced: {
    padding: 'p-6',
    gap: 'gap-3',
    margin: 'mb-3'
  },
  spacious: {
    padding: 'p-8',
    gap: 'gap-4',
    margin: 'mb-4'
  },
  'ultra-minimal': {
    padding: 'p-12',
    gap: 'gap-6',
    margin: 'mb-6'
  }
}

// Background styles are handled inline in containerClasses for better Tailwind purging

// Mood modifiers
const moodModifiers: Record<string, string> = {
  calm: 'transition-all duration-500 ease-out',
  balanced: 'transition-all duration-300',
  dynamic: 'transition-all duration-200 hover:scale-[1.01]',
  dramatic: 'transition-all duration-150 hover:shadow-2xl'
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

const StarIcon = ({ filled = false }: { filled?: boolean }) => (
  <svg className={`w-4 h-4 ${filled ? 'text-amber-400 fill-current' : 'text-gray-300'}`} viewBox="0 0 20 20">
    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
  </svg>
)

const DesignBadge = ({ dna }: { dna: DesignDNA }) => (
  <div className="flex items-center gap-2 text-xs">
    <span className="px-2 py-0.5 rounded-full bg-brand-100 text-primary-500 font-medium">
      {dna.style}
    </span>
    <span className="px-2 py-0.5 rounded-full bg-brand-100 text-primary-500 font-medium">
      {dna.typography_personality}
    </span>
  </div>
)

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export default function AdaptivePreview({ preview, className = '' }: AdaptivePreviewProps) {
  const { 
    blueprint, 
    design_dna, 
    title, 
    subtitle, 
    description, 
    tags, 
    context_items, 
    credibility_items,
    primary_image_base64,
    screenshot_url
  } = preview

  // Compute styles based on Design DNA
  const styles = useMemo(() => {
    const dna = design_dna || {
      style: 'corporate',
      mood: 'balanced',
      formality: 0.5,
      typography_personality: 'bold',
      color_emotion: 'trust',
      spacing_feel: 'balanced',
      brand_adjectives: ['professional', 'modern'],
      design_reasoning: ''
    }

    const typography = typographyStyles[dna.typography_personality] || typographyStyles.bold
    const spacing = spacingStyles[dna.spacing_feel] || spacingStyles.balanced
    const mood = moodModifiers[dna.mood] || moodModifiers.balanced

    // Determine if dark theme based on style
    const isDark = ['luxurious', 'technical'].includes(dna.style)

    return {
      typography,
      spacing,
      mood,
      isDark,
      style: dna.style,
      formality: dna.formality,
      brandAdjectives: dna.brand_adjectives || []
    }
  }, [design_dna])

  // Get image URL
  const imageUrl = primary_image_base64
    ? `data:image/png;base64,${primary_image_base64}`
    : screenshot_url

  // Determine container classes based on design style
  const containerClasses = useMemo(() => {
    const base = 'relative overflow-hidden rounded-2xl shadow-xl'
    
    switch (styles.style) {
      case 'minimalist':
        return `${base} bg-white border border-gray-100`
      case 'luxurious':
        return `${base} bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900`
      case 'playful':
        return `${base} bg-gradient-to-br from-pink-50 via-white to-blue-50`
      case 'technical':
        return `${base} bg-slate-900 border border-slate-700`
      case 'editorial':
        return `${base} bg-stone-50`
      case 'brutalist':
        return `${base} bg-white border-4 border-black`
      case 'organic':
        return `${base} bg-gradient-to-b from-emerald-50/50 to-white`
      case 'maximalist':
        return `${base} bg-gradient-to-br from-violet-600 via-fuchsia-500 to-pink-500`
      default:
        return `${base} bg-white`
    }
  }, [styles.style])

  // Text color based on theme
  const textColors = styles.isDark 
    ? { primary: 'text-white', secondary: 'text-gray-300', muted: 'text-gray-400' }
    : { primary: 'text-gray-900', secondary: 'text-gray-600', muted: 'text-gray-500' }

  return (
    <div className={`${containerClasses} ${styles.mood} ${className}`}>
      {/* Accent bar - style varies by design type */}
      {styles.style !== 'brutalist' && (
        <div 
          className={`h-1.5 ${styles.style === 'minimalist' ? 'h-1' : ''}`}
          style={{ backgroundColor: blueprint.accent_color }}
        />
      )}

      {/* Main content area */}
      <div className={`${styles.spacing.padding} ${styles.spacing.gap} flex flex-col`}>
        
        {/* Header with optional image */}
        <div className={`flex ${styles.spacing.gap} items-start`}>
          {/* Image/Avatar */}
          {imageUrl && (
            <div className={`flex-shrink-0 ${
              styles.style === 'minimalist' ? 'w-12 h-12 rounded-lg' :
              styles.style === 'playful' ? 'w-16 h-16 rounded-2xl rotate-3' :
              styles.style === 'brutalist' ? 'w-14 h-14 rounded-none border-2 border-black' :
              'w-14 h-14 rounded-xl'
            } overflow-hidden shadow-lg`}>
              <img 
                src={imageUrl} 
                alt="" 
                className="w-full h-full object-cover"
              />
            </div>
          )}

          {/* Title and subtitle */}
          <div className="flex-1 min-w-0">
            <h2 className={`${styles.typography.headlineClass} ${textColors.primary} text-xl leading-tight ${styles.spacing.margin}`}
                style={{ letterSpacing: styles.typography.letterSpacing }}>
              {title}
            </h2>
            {subtitle && (
              <p className={`${styles.typography.bodyClass} ${textColors.secondary} text-sm leading-relaxed`}>
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Description */}
        {description && (
          <p className={`${textColors.muted} text-sm leading-relaxed ${
            styles.formality > 0.7 ? 'font-light' : ''
          }`}>
            {description}
          </p>
        )}

        {/* Tags */}
        {tags.length > 0 && (
          <div className={`flex flex-wrap ${styles.spacing.gap}`}>
            {tags.slice(0, 4).map((tag, i) => (
              <span
                key={i}
                className={`px-2.5 py-1 text-xs font-medium ${
                  styles.style === 'minimalist' ? 'bg-gray-100 text-gray-700 rounded-md' :
                  styles.style === 'playful' ? 'bg-gradient-to-r from-pink-100 to-blue-100 text-gray-700 rounded-full' :
                  styles.style === 'brutalist' ? 'bg-black text-white' :
                  styles.isDark ? 'bg-white/10 text-white/90 rounded-md' :
                  'bg-gray-100 text-gray-700 rounded-md'
                }`}
                style={styles.style === 'corporate' ? { 
                  backgroundColor: `${blueprint.primary_color}15`,
                  color: blueprint.primary_color
                } : undefined}
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Context items */}
        {context_items.length > 0 && (
          <div className={`flex flex-wrap ${styles.spacing.gap} text-sm ${textColors.muted}`}>
            {context_items.map((item, i) => (
              <div key={i} className="flex items-center gap-1">
                <span className="w-4 h-4 opacity-70">
                  {item.icon === 'location' ? '📍' : 'ℹ️'}
                </span>
                <span>{item.text}</span>
              </div>
            ))}
          </div>
        )}

        {/* Credibility items */}
        {credibility_items.length > 0 && (
          <div className={`flex flex-wrap items-center ${styles.spacing.gap}`}>
            {credibility_items.map((item, i) => (
              <div key={i} className={`flex items-center gap-1 ${
                styles.style === 'luxurious' ? 'text-amber-400' :
                styles.isDark ? 'text-emerald-400' : 'text-emerald-600'
              }`}>
                {item.type === 'rating' ? (
                  <>
                    <StarIcon filled />
                    <span className="text-sm font-semibold">{item.value}</span>
                  </>
                ) : (
                  <span className="text-sm font-medium">{item.value}</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Brand adjectives (if DNA available) */}
        {styles.brandAdjectives.length > 0 && (
          <div className="pt-2 mt-auto border-t border-gray-100 dark:border-gray-800">
            <div className={`flex flex-wrap gap-1 text-[10px] ${textColors.muted}`}>
              {styles.brandAdjectives.slice(0, 3).map((adj, i) => (
                <span key={i} className="opacity-60">
                  {i > 0 ? '·' : ''} {adj}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Design fidelity indicator (development only) */}
      {preview.design_fidelity_score !== undefined && (
        <div className="absolute top-2 right-2 opacity-50 hover:opacity-100 transition-opacity">
          <div className={`px-2 py-0.5 rounded text-[10px] font-mono ${
            preview.design_fidelity_score >= 0.8 ? 'bg-emerald-100 text-emerald-700' :
            preview.design_fidelity_score >= 0.6 ? 'bg-brand-100 text-primary-500' :
            'bg-amber-100 text-amber-700'
          }`}>
            DNA {Math.round(preview.design_fidelity_score * 100)}%
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// SPECIALIZED TEMPLATES (DNA-aware variants)
// =============================================================================

/**
 * Minimalist template - clean, spacious, refined
 */
export function MinimalistPreview({ preview, className = '' }: AdaptivePreviewProps) {
  const { blueprint, title, subtitle, description, tags, primary_image_base64 } = preview

  return (
    <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden ${className}`}>
      <div className="h-0.5" style={{ backgroundColor: blueprint.accent_color }} />
      <div className="p-10">
        {primary_image_base64 && (
          <img 
            src={`data:image/png;base64,${primary_image_base64}`}
            alt=""
            className="w-12 h-12 rounded-lg mb-6 object-cover"
          />
        )}
        <h2 className="text-2xl font-semibold text-gray-900 tracking-tight mb-2">
          {title}
        </h2>
        {subtitle && (
          <p className="text-gray-500 mb-4 font-light">{subtitle}</p>
        )}
        {description && (
          <p className="text-gray-400 text-sm leading-relaxed mb-6">{description}</p>
        )}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tags.slice(0, 3).map((tag, i) => (
              <span key={i} className="px-3 py-1 bg-gray-50 text-gray-600 text-xs rounded-md">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Bold template - high contrast, impactful typography
 */
export function BoldPreview({ preview, className = '' }: AdaptivePreviewProps) {
  const { blueprint, title, subtitle, credibility_items, primary_image_base64 } = preview

  return (
    <div 
      className={`rounded-2xl shadow-2xl overflow-hidden ${className}`}
      style={{ 
        background: `linear-gradient(135deg, ${blueprint.primary_color}, ${blueprint.secondary_color})`
      }}
    >
      <div className="p-8">
        {primary_image_base64 && (
          <img 
            src={`data:image/png;base64,${primary_image_base64}`}
            alt=""
            className="w-16 h-16 rounded-xl mb-6 object-cover shadow-lg"
          />
        )}
        <h2 className="text-3xl font-black text-white tracking-tighter mb-3 leading-none">
          {title}
        </h2>
        {subtitle && (
          <p className="text-white/80 text-lg mb-4">{subtitle}</p>
        )}
        {credibility_items.length > 0 && (
          <div className="flex items-center gap-3 mt-6">
            {credibility_items.slice(0, 2).map((item, i) => (
              <span key={i} className="px-3 py-1 bg-white/20 text-white text-sm font-semibold rounded-full">
                {item.value}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Elegant template - refined, luxurious, sophisticated
 */
export function ElegantPreview({ preview, className = '' }: AdaptivePreviewProps) {
  const { blueprint, title, subtitle, description, primary_image_base64 } = preview

  return (
    <div className={`bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl shadow-2xl overflow-hidden ${className}`}>
      <div className="p-10 text-center">
        {primary_image_base64 && (
          <div className="flex justify-center mb-6">
            <img 
              src={`data:image/png;base64,${primary_image_base64}`}
              alt=""
              className="w-20 h-20 rounded-full object-cover ring-2 ring-amber-400/30"
            />
          </div>
        )}
        <h2 className="text-2xl font-light text-white tracking-widest uppercase mb-3">
          {title}
        </h2>
        <div className="w-12 h-px mx-auto mb-4" style={{ backgroundColor: blueprint.accent_color }} />
        {subtitle && (
          <p className="text-gray-400 text-sm tracking-wide">{subtitle}</p>
        )}
        {description && (
          <p className="text-gray-500 text-xs mt-4 max-w-xs mx-auto leading-relaxed">
            {description}
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * Playful template - fun, colorful, energetic
 */
export function PlayfulPreview({ preview, className = '' }: AdaptivePreviewProps) {
  const { blueprint, title, subtitle, tags, credibility_items, primary_image_base64 } = preview

  return (
    <div className={`bg-gradient-to-br from-pink-100 via-white to-blue-100 rounded-3xl shadow-xl overflow-hidden ${className}`}>
      <div className="p-6">
        <div className="flex items-start gap-4">
          {primary_image_base64 && (
            <img 
              src={`data:image/png;base64,${primary_image_base64}`}
              alt=""
              className="w-16 h-16 rounded-2xl object-cover rotate-3 shadow-lg ring-4 ring-white"
            />
          )}
          <div>
            <h2 className="text-xl font-bold text-gray-800 mb-1">
              {title} ✨
            </h2>
            {subtitle && (
              <p className="text-gray-600 text-sm">{subtitle}</p>
            )}
          </div>
        </div>
        
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {tags.slice(0, 4).map((tag, i) => (
              <span 
                key={i} 
                className="px-3 py-1 bg-gradient-to-r from-violet-200 to-pink-200 text-gray-700 text-xs font-medium rounded-full"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {credibility_items.length > 0 && (
          <div className="flex items-center gap-2 mt-4 text-sm">
            {credibility_items.slice(0, 1).map((item, i) => (
              <span key={i} className="flex items-center gap-1 text-amber-500 font-semibold">
                ⭐ {item.value}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

