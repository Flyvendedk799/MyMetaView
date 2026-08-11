import { ReactNode } from 'react'

interface ProgressProps {
  value: number
  max?: number
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'gradient' | 'success' | 'warning' | 'error'
  showLabel?: boolean
  label?: string
  className?: string
}

export default function Progress({
  value,
  max = 100,
  size = 'md',
  variant = 'default',
  showLabel = false,
  label,
  className = '',
}: ProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))
  
  const sizeClasses = {
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  }
  
  const variantClasses = {
    default: 'bg-primary-500',
    gradient: 'bg-primary-500',
    success: 'bg-success-500',
    warning: 'bg-warning-500',
    error: 'bg-error-500',
  }
  
  return (
    <div className={className}>
      {(showLabel || label) && (
        <div className="flex justify-between mb-1.5 text-sm">
          {label && <span className="text-secondary-700 font-medium">{label}</span>}
          {showLabel && <span className="text-secondary-500">{Math.round(percentage)}%</span>}
        </div>
      )}
      
      <div className={`progress ${sizeClasses[size]}`}>
        <div 
          className={`${variantClasses[variant]} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        />
      </div>
    </div>
  )
}

// Circular Progress
interface CircularProgressProps {
  value: number
  max?: number
  size?: number
  strokeWidth?: number
  variant?: 'default' | 'gradient' | 'success' | 'warning' | 'error'
  showValue?: boolean
  label?: ReactNode
  className?: string
}

export function CircularProgress({
  value,
  max = 100,
  size = 80,
  strokeWidth = 6,
  variant = 'default',
  showValue = true,
  label,
  className = '',
}: CircularProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (percentage / 100) * circumference
  
  const colors = {
    default: 'stroke-primary-500',
    gradient: 'stroke-primary-500',
    success: 'stroke-success-500',
    warning: 'stroke-warning-500',
    error: 'stroke-error-500',
  }
  
  return (
    <div className={`relative inline-flex items-center justify-center ${className}`}>
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="none"
          className="text-secondary-100"
        />
        
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          className={colors[variant]}
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: offset,
            transition: 'stroke-dashoffset 0.5s ease-out',
          }}
        />
      </svg>
      
      {showValue && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-secondary-900">
            {Math.round(percentage)}%
          </span>
          {label && (
            <span className="text-xs text-secondary-500">{label}</span>
          )}
        </div>
      )}
    </div>
  )
}

// Loading Spinner
interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}

export function Spinner({ size = 'md', className = '' }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12',
  }
  
  return (
    <svg 
      className={`animate-spin ${sizeClasses[size]} ${className}`}
      xmlns="http://www.w3.org/2000/svg" 
      fill="none" 
      viewBox="0 0 24 24"
    >
      <circle 
        className="opacity-25" 
        cx="12" 
        cy="12" 
        r="10" 
        stroke="currentColor" 
        strokeWidth="4"
      />
      <path 
        className="opacity-75" 
        fill="currentColor" 
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

// Loading overlay
interface LoadingOverlayProps {
  isLoading: boolean
  message?: string
  blur?: boolean
  className?: string
}

export function LoadingOverlay({ 
  isLoading, 
  message = 'Loading...', 
  blur = true,
  className = '' 
}: LoadingOverlayProps) {
  if (!isLoading) return null
  
  return (
    <div className={`
      absolute inset-0 flex flex-col items-center justify-center z-10
      bg-white/80 ${blur ? 'backdrop-blur-sm' : ''}
      ${className}
    `}>
      <Spinner size="lg" className="text-primary-500" />
      {message && (
        <p className="mt-3 text-sm font-medium text-secondary-600">{message}</p>
      )}
    </div>
  )
}

