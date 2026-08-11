import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { AppErrorBoundary } from './components/error/AppErrorBoundary'
import { getApiBaseUrl } from './api/client'

// Log API configuration on startup
console.log('[App Startup] API Base URL:', getApiBaseUrl())
console.log('[App Startup] Environment:', import.meta.env.MODE)
if (!import.meta.env.VITE_API_BASE_URL) {
  console.warn('[App Startup] WARNING: VITE_API_BASE_URL is not set. Using default:', getApiBaseUrl())
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </React.StrictMode>,
)

