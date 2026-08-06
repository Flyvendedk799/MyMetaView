interface LogoMarkProps {
  size?: number
  /** 'light' renders the mark for light surfaces (brand-800 tile);
      'dark' renders it for dark surfaces (brand-700 tile). */
  surface?: 'light' | 'dark'
  className?: string
}

/** The MetaView mark: a preview card with a generated image.
    Min size 24px. Clear space = 1× corner radius. */
export function LogoMark({ size = 28, surface = 'light', className = '' }: LogoMarkProps) {
  const tile = surface === 'dark' ? '#12523F' : '#0B3B2E'
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 44 44"
      fill="none"
      aria-label="MetaView mark"
      className={className}
    >
      <rect width="44" height="44" rx="12" fill={tile} />
      <rect x="9" y="13" width="26" height="18" rx="4" fill="#FBFBF9" />
      <rect x="9" y="13" width="26" height="7" rx="4" fill="#DDE9E3" />
      <circle cx="29.5" cy="26" r="4" fill="#E8622C" />
    </svg>
  )
}

interface LogoProps {
  size?: number
  surface?: 'light' | 'dark'
  showWordmark?: boolean
  className?: string
}

/** Mark + wordmark lockup. */
export default function Logo({ size = 28, surface = 'light', showWordmark = true, className = '' }: LogoProps) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} surface={surface} />
      {showWordmark && (
        <span
          className={`font-display font-semibold tracking-display ${
            surface === 'dark' ? 'text-paper' : 'text-secondary-900'
          }`}
          style={{ fontSize: Math.round(size * 0.68) }}
        >
          MetaView
        </span>
      )}
    </span>
  )
}
