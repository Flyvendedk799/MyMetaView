import { ReactNode, forwardRef, HTMLAttributes } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  variant?: 'default' | 'hover' | 'interactive' | 'gradient' | 'glass'
  padding?: 'none' | 'sm' | 'md' | 'lg'
  noBorder?: boolean
}

const Card = forwardRef<HTMLDivElement, CardProps>(({ 
  children, 
  variant = 'default',
  padding = 'md',
  noBorder = false,
  className = '', 
  onClick,
  ...props 
}, ref) => {
  // One card recipe: line border + the single card shadow.
  // Legacy gradient/glass variants collapse into the default card.
  const variantClasses = {
    default: 'card',
    hover: 'card-hover',
    interactive: 'card-interactive',
    gradient: 'card',
    glass: 'card',
  }
  
  const paddingClasses = {
    none: 'p-0',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }
  
  return (
    <div 
      ref={ref}
      className={`
        ${variantClasses[variant]} 
        ${paddingClasses[padding]}
        ${noBorder ? 'border-0' : ''}
        ${className}
      `}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick(e as any) : undefined}
      {...props}
    >
      {children}
    </div>
  )
})

Card.displayName = 'Card'

export default Card

// Card Header component
interface CardHeaderProps {
  children: ReactNode
  action?: ReactNode
  className?: string
}

export function CardHeader({ children, action, className = '' }: CardHeaderProps) {
  return (
    <div className={`flex items-center justify-between mb-4 ${className}`}>
      <div className="flex-1">{children}</div>
      {action && <div className="flex-shrink-0 ml-4">{action}</div>}
    </div>
  )
}

// Card Title component
interface CardTitleProps {
  children: ReactNode
  subtitle?: string
  className?: string
}

export function CardTitle({ children, subtitle, className = '' }: CardTitleProps) {
  return (
    <div className={className}>
      <h3 className="heading-5">{children}</h3>
      {subtitle && <p className="text-sm text-secondary-500 mt-0.5">{subtitle}</p>}
    </div>
  )
}

// Card Content component
interface CardContentProps {
  children: ReactNode
  className?: string
}

export function CardContent({ children, className = '' }: CardContentProps) {
  return <div className={className}>{children}</div>
}

// Card Footer component
interface CardFooterProps {
  children: ReactNode
  className?: string
}

export function CardFooter({ children, className = '' }: CardFooterProps) {
  return (
    <div className={`mt-4 pt-4 border-t border-secondary-100 ${className}`}>
      {children}
    </div>
  )
}
