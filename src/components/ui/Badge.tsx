import { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
  icon?: ReactNode
  className?: string
}

export default function Badge({
  children,
  variant = 'secondary',
  size = 'md',
  dot = false,
  icon,
  className = '',
}: BadgeProps) {
  // AA-safe tint pairs from the identity spec
  const variantClasses = {
    primary: 'bg-brand-100 text-primary-500 border-transparent',
    secondary: 'bg-secondary-100 text-secondary-600 border-transparent',
    success: 'bg-success-50 text-success-500 border-transparent',
    warning: 'bg-warning-50 text-warning-700 border-transparent',
    error: 'bg-error-50 text-error-500 border-transparent',
    outline: 'bg-transparent border-secondary-300 text-secondary-600',
  }
  
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-2xs',
    md: 'px-2.5 py-1 text-xs',
    lg: 'px-3 py-1.5 text-sm',
  }
  
  const dotColors = {
    primary: 'bg-primary-500',
    secondary: 'bg-secondary-500',
    success: 'bg-success-500',
    warning: 'bg-warning-500',
    error: 'bg-error-500',
    outline: 'bg-secondary-400',
  }
  
  return (
    <span className={`
      inline-flex items-center gap-1.5 font-semibold rounded-md border
      ${variantClasses[variant]}
      ${sizeClasses[size]}
      ${className}
    `}>
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]}`} />
      )}
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </span>
  )
}

// Status Badge with predefined states
interface StatusBadgeProps {
  status: 'published' | 'draft' | 'scheduled' | 'archived' | 'active' | 'inactive' | 'pending'
  size?: 'sm' | 'md' | 'lg'
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const statusConfig = {
    published: { variant: 'success' as const, label: 'Published', dot: true },
    draft: { variant: 'secondary' as const, label: 'Draft', dot: true },
    scheduled: { variant: 'primary' as const, label: 'Scheduled', dot: true },
    archived: { variant: 'secondary' as const, label: 'Archived', dot: false },
    active: { variant: 'success' as const, label: 'Active', dot: true },
    inactive: { variant: 'secondary' as const, label: 'Inactive', dot: true },
    pending: { variant: 'warning' as const, label: 'Pending', dot: true },
  }
  
  const config = statusConfig[status]
  
  return (
    <Badge variant={config.variant} size={size} dot={config.dot}>
      {config.label}
    </Badge>
  )
}

// Count Badge (for notifications, etc.)
interface CountBadgeProps {
  count: number
  max?: number
  variant?: 'primary' | 'error'
  className?: string
}

export function CountBadge({ count, max = 99, variant = 'primary', className = '' }: CountBadgeProps) {
  const displayCount = count > max ? `${max}+` : count
  
  const variantClasses = {
    primary: 'bg-primary-500 text-white',
    error: 'bg-error-500 text-white',
  }
  
  if (count === 0) return null
  
  return (
    <span className={`
      inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5
      text-2xs font-bold rounded-full
      ${variantClasses[variant]}
      ${className}
    `}>
      {displayCount}
    </span>
  )
}

