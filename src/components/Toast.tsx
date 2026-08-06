import { useEffect } from 'react'
import { CheckCircleIcon, XMarkIcon } from '@heroicons/react/24/outline'

interface ToastProps {
  message: string
  type?: 'success' | 'error'
  onClose: () => void
  duration?: number
}

export default function Toast({ message, type = 'success', onClose, duration = 3000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose()
    }, duration)

    return () => clearTimeout(timer)
  }, [duration, onClose])

  return (
    <div className="fixed top-4 right-4 z-50 animate-slide-in-right">
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-xl shadow-overlay border ${
          type === 'success'
            ? 'bg-success-50 border-success-100 text-success-600'
            : 'bg-error-50 border-error-100 text-error-600'
        }`}
      >
        {type === 'success' && <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />}
        <span className="font-medium text-sm">{message}</span>
        <button
          onClick={onClose}
          className={`ml-2 p-1 rounded-lg transition-colors ${
            type === 'success' ? 'hover:bg-success-100' : 'hover:bg-error-100'
          }`}
          aria-label="Close"
        >
          <XMarkIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

