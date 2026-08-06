/**
 * Error Boundary Component
 * 
 * Catches React errors in component tree and displays a user-friendly error UI.
 * Prevents the entire app from crashing when errors occur.
 */
import React, { Component, ErrorInfo, ReactNode } from 'react'
import { ExclamationTriangleIcon, ArrowPathIcon } from '@heroicons/react/24/outline'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console in development
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught an error:', error, errorInfo)
    }

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    this.setState({
      error,
      errorInfo,
    })
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
  }

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-paper px-4">
          <div className="max-w-md w-full bg-surface rounded-2xl shadow-overlay border border-line p-6">
            <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-error-50 rounded-full">
              <ExclamationTriangleIcon className="w-6 h-6 text-error-500" aria-hidden="true" />
            </div>

            <h2 className="font-display text-xl font-semibold tracking-display-sm text-secondary-900 text-center mb-2">
              Something went wrong
            </h2>

            <p className="text-secondary-600 text-center mb-6">
              We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
            </p>

            {import.meta.env.DEV && this.state.error && (
              <details className="mb-4 p-3 bg-secondary-50 rounded-lg border border-secondary-200">
                <summary className="text-sm font-semibold text-secondary-700 cursor-pointer mb-2">
                  Error Details (Development Only)
                </summary>
                <pre className="font-mono text-xs text-secondary-600 overflow-auto max-h-40">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <div className="flex gap-3">
              <button
                onClick={this.handleReset}
                className="btn-primary flex-1"
                aria-label="Try again"
              >
                <ArrowPathIcon className="w-5 h-5" aria-hidden="true" />
                Try Again
              </button>
              
              <button
                onClick={() => window.location.reload()}
                className="btn-secondary flex-1"
                aria-label="Reload page"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

