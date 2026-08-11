import { ReactNode } from 'react'
import Button from './Button'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
    icon?: ReactNode
  }
  secondaryAction?: {
    label: string
    onClick: () => void
  }
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  className = '',
  size = 'md',
}: EmptyStateProps) {
  const sizeClasses = {
    sm: 'py-8',
    md: 'py-16',
    lg: 'py-24',
  }
  
  const iconSizes = {
    sm: 'w-12 h-12',
    md: 'w-16 h-16',
    lg: 'w-20 h-20',
  }
  
  return (
    <div className={`empty-state ${sizeClasses[size]} ${className}`}>
      {icon && (
        <div className={`
          ${iconSizes[size]} rounded-2xl 
          bg-secondary-100 
          flex items-center justify-center mb-6 
          text-secondary-400
        `}>
          {icon}
        </div>
      )}
      
      <h3 className="heading-5 mb-2">{title}</h3>
      <p className="text-body max-w-sm mb-6">{description}</p>
      
      {(action || secondaryAction) && (
        <div className="flex items-center justify-center gap-3">
          {action && (
            <Button 
              onClick={action.onClick}
              icon={action.icon}
            >
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button variant="ghost" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

// Illustration-based empty states
interface IllustratedEmptyStateProps extends Omit<EmptyStateProps, 'icon'> {
  illustration: 'posts' | 'sites' | 'media' | 'search' | 'error' | 'success'
}

export function IllustratedEmptyState({ illustration, ...props }: IllustratedEmptyStateProps) {
  const illustrations = {
    posts: (
      <svg className="w-full h-full" viewBox="0 0 120 120" fill="none">
        <rect x="20" y="20" width="80" height="80" rx="8" className="fill-secondary-100" />
        <rect x="30" y="35" width="40" height="6" rx="3" className="fill-secondary-300" />
        <rect x="30" y="50" width="60" height="4" rx="2" className="fill-secondary-200" />
        <rect x="30" y="60" width="55" height="4" rx="2" className="fill-secondary-200" />
        <rect x="30" y="70" width="45" height="4" rx="2" className="fill-secondary-200" />
        <rect x="30" y="85" width="20" height="8" rx="4" className="fill-primary-200" />
      </svg>
    ),
    sites: (
      <svg className="w-full h-full" viewBox="0 0 120 120" fill="none">
        <circle cx="60" cy="60" r="45" className="fill-secondary-100" />
        <path d="M60 15 L60 105 M15 60 L105 60" className="stroke-secondary-200" strokeWidth="2" />
        <ellipse cx="60" cy="60" rx="45" ry="20" className="stroke-secondary-300" strokeWidth="2" fill="none" />
        <circle cx="60" cy="60" r="45" className="stroke-primary-300" strokeWidth="2" fill="none" />
      </svg>
    ),
    media: (
      <svg className="w-full h-full" viewBox="0 0 120 120" fill="none">
        <rect x="20" y="30" width="80" height="60" rx="8" className="fill-secondary-100" />
        <circle cx="45" cy="55" r="12" className="fill-secondary-200" />
        <path d="M35 80 L55 60 L75 75 L95 55" className="stroke-primary-300" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    search: (
      <svg className="w-full h-full" viewBox="0 0 120 120" fill="none">
        <circle cx="55" cy="55" r="30" className="stroke-secondary-300" strokeWidth="4" fill="none" />
        <line x1="78" y1="78" x2="100" y2="100" className="stroke-secondary-300" strokeWidth="4" strokeLinecap="round" />
        <path d="M55 40 Q65 50 55 60 Q45 70 55 70" className="stroke-secondary-200" strokeWidth="3" strokeLinecap="round" fill="none" />
      </svg>
    ),
    error: (
      <svg className="w-full h-full" viewBox="0 0 120 120" fill="none">
        <circle cx="60" cy="60" r="45" className="fill-error-50" />
        <circle cx="60" cy="60" r="35" className="stroke-error-200" strokeWidth="3" fill="none" />
        <path d="M60 40 L60 65" className="stroke-error-400" strokeWidth="4" strokeLinecap="round" />
        <circle cx="60" cy="78" r="3" className="fill-error-400" />
      </svg>
    ),
    success: (
      <svg className="w-full h-full" viewBox="0 0 120 120" fill="none">
        <circle cx="60" cy="60" r="45" className="fill-success-50" />
        <circle cx="60" cy="60" r="35" className="stroke-success-200" strokeWidth="3" fill="none" />
        <path d="M42 60 L55 73 L78 50" className="stroke-success-500" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
    ),
  }
  
  return (
    <EmptyState
      icon={<div className="w-24 h-24">{illustrations[illustration]}</div>}
      {...props}
    />
  )
}
