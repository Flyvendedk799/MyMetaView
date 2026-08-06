import { useState } from 'react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { exportUserData, deleteUserAccount } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import { ExclamationTriangleIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline'

export default function AccountSettings() {
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleExportData = async () => {
    try {
      setExporting(true)
      setError(null)
      
      const data = await exportUserData()
      
      // Download as JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `preview-data-export-${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export data')
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (deleteConfirm !== 'DELETE') {
      setError('Please type "DELETE" to confirm account deletion')
      return
    }

    if (!window.confirm('Are you absolutely sure? This action cannot be undone. Your account and all associated data will be permanently deleted.')) {
      return
    }

    try {
      setDeleting(true)
      setError(null)
      
      await deleteUserAccount()
      
      // Logout and redirect to landing
      logout()
      navigate('/')
      alert('Your account has been deleted. We\'re sorry to see you go.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete account')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Account Settings</h1>
        <p className="text-secondary-600">Manage your account data and privacy</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {/* Data Export */}
      <Card className="mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold text-secondary mb-2">Export Your Data</h2>
            <p className="text-secondary-600 text-sm">
              Download all your data in JSON format. This includes your profile, organizations, domains, previews, and activity logs.
            </p>
          </div>
        </div>
        <Button
          onClick={handleExportData}
          disabled={exporting}
          variant="secondary"
        >
          {exporting ? (
            <span className="flex items-center space-x-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              <span>Exporting...</span>
            </span>
          ) : (
            <span className="flex items-center space-x-2">
              <ArrowDownTrayIcon className="w-5 h-5" />
              <span>Export My Data</span>
            </span>
          )}
        </Button>
      </Card>

      {/* Account Deletion */}
      <Card className="mb-6 border-error-200">
        <div className="flex items-start space-x-3 mb-4">
          <ExclamationTriangleIcon className="w-6 h-6 text-error-500 flex-shrink-0 mt-1" />
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-error-700 mb-2">Delete Account</h2>
            <p className="text-secondary-600 text-sm mb-4">
              Permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-secondary-700 mb-2">
                Type "DELETE" to confirm:
              </label>
              <input
                type="text"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-error-500 focus:border-error-500"
                placeholder="DELETE"
              />
            </div>
            <Button
              onClick={handleDeleteAccount}
              disabled={deleting || deleteConfirm !== 'DELETE'}
              className="bg-error-600 hover:bg-error-700 text-white"
            >
              {deleting ? (
                <span className="flex items-center space-x-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Deleting...</span>
                </span>
              ) : (
                'Delete My Account'
              )}
            </Button>
          </div>
        </div>
      </Card>

      {/* Legal Links */}
      <Card>
        <h2 className="text-xl font-semibold text-secondary mb-4">Legal</h2>
        <div className="space-y-2 text-sm">
          <a href="/privacy" className="text-primary hover:text-primary/80 block">
            Privacy Policy
          </a>
          <a href="/terms" className="text-primary hover:text-primary/80 block">
            Terms of Service
          </a>
          <p className="text-secondary-500 mt-4">
            For questions about data processing or deletion, please contact support.
          </p>
        </div>
      </Card>
    </div>
  )
}

