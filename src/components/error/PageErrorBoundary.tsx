import React, { Component, ErrorInfo, ReactNode } from 'react'
import Card from '../ui/Card'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class PageErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Page error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      
      return (
        <Card className="p-6">
          <h2 className="font-display text-xl font-semibold tracking-display-sm text-secondary-900 mb-2">Something went wrong</h2>
          <p className="text-secondary-600 mb-4">
            There was an error loading this page. Please try refreshing.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="text-sm font-semibold text-primary-500 hover:text-primary-600 transition-colors"
          >
            Try again
          </button>
        </Card>
      )
    }

    return this.props.children
  }
}

