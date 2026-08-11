import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Alert from '../components/ui/Alert'
import Input from '../components/ui/Input'
import { ConfirmDialog } from '../components/ui/Modal'
import { exportUserData, deleteUserAccount, changePassword } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { ExclamationTriangleIcon, ArrowDownTrayIcon, KeyIcon } from '@heroicons/react/24/outline'

export default function AccountSettings() {
  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Change password
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmNewPassword, setConfirmNewPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSuccess, setPasswordSuccess] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordError(null)
    setPasswordSuccess(false)
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmNewPassword) {
      setPasswordError('New passwords do not match.')
      return
    }
    try {
      setChangingPassword(true)
      await changePassword(currentPassword, newPassword)
      setPasswordSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmNewPassword('')
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : 'Could not change password.')
    } finally {
      setChangingPassword(false)
    }
  }

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
    try {
      setDeleting(true)
      setError(null)
      await deleteUserAccount()
      logout()
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete account')
      setShowDeleteDialog(false)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Account</h1>
        <p className="text-[15px] text-secondary-600">Your sign-in details, data, and privacy</p>
      </div>

      {error && (
        <div className="mb-6">
          <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>
        </div>
      )}

      {/* Profile */}
      <Card className="mb-6">
        <h2 className="text-xl font-semibold text-secondary-900 mb-1">Profile</h2>
        <p className="text-secondary-600 text-sm mb-4">
          Signed in as <span className="font-medium text-secondary-900">{user?.email}</span>
        </p>
        <p className="text-[13px] text-secondary-500">
          Your email address is your account identity and can't be changed here — write to{' '}
          <a href="mailto:hello@mymetaview.com" className="text-primary-600 hover:text-primary-700">hello@mymetaview.com</a>{' '}
          if you need it moved.
        </p>
      </Card>

      {/* Change password */}
      <Card className="mb-6">
        <div className="flex items-start gap-3 mb-4">
          <KeyIcon className="w-6 h-6 text-secondary-400 flex-shrink-0 mt-1" />
          <div>
            <h2 className="text-xl font-semibold text-secondary-900 mb-1">Change password</h2>
            <p className="text-secondary-600 text-sm">At least 8 characters.</p>
          </div>
        </div>
        <form onSubmit={handleChangePassword} className="max-w-md space-y-4">
          {passwordError && <Alert variant="error">{passwordError}</Alert>}
          {passwordSuccess && <Alert variant="success">Password updated.</Alert>}
          <Input
            label="Current password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          <Input
            label="New password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
          <Input
            label="Confirm new password"
            type="password"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
          <Button type="submit" loading={changingPassword}>
            Update password
          </Button>
        </form>
      </Card>

      {/* Data Export */}
      <Card className="mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold text-secondary-900 mb-2">Export your data</h2>
            <p className="text-secondary-600 text-sm">
              Download all your data in JSON format. This includes your profile, organizations, domains, previews, and activity logs.
            </p>
          </div>
        </div>
        <Button onClick={handleExportData} loading={exporting} variant="secondary">
          <span className="flex items-center space-x-2">
            <ArrowDownTrayIcon className="w-5 h-5" />
            <span>Export my data</span>
          </span>
        </Button>
      </Card>

      {/* Account Deletion */}
      <Card className="mb-6 border-error-200">
        <div className="flex items-start space-x-3 mb-4">
          <ExclamationTriangleIcon className="w-6 h-6 text-error-500 flex-shrink-0 mt-1" />
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-error-700 mb-2">Delete account</h2>
            <p className="text-secondary-600 text-sm mb-4">
              Permanently delete your account and all associated data. This action cannot be undone.
            </p>
            <div className="mb-4 max-w-xs">
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
              onClick={() => setShowDeleteDialog(true)}
              disabled={deleting || deleteConfirm !== 'DELETE'}
              className="bg-error-600 hover:bg-error-700 text-white"
            >
              Delete my account
            </Button>
          </div>
        </div>
      </Card>

      <ConfirmDialog
        isOpen={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        onConfirm={handleDeleteAccount}
        title="Delete your account?"
        message="Your domains, previews, brand settings, and analytics will be permanently removed. This cannot be undone."
        confirmText="Delete everything"
        loading={deleting}
        variant="danger"
      />

      {/* Legal Links */}
      <Card>
        <h2 className="text-xl font-semibold text-secondary-900 mb-4">Legal</h2>
        <div className="space-y-2 text-sm">
          <Link to="/privacy" className="text-primary-600 hover:text-primary-700 block">
            Privacy Policy
          </Link>
          <Link to="/terms" className="text-primary-600 hover:text-primary-700 block">
            Terms of Service
          </Link>
          <p className="text-secondary-500 mt-4">
            For questions about data processing or deletion, write to{' '}
            <a href="mailto:hello@mymetaview.com" className="text-primary-600 hover:text-primary-700">hello@mymetaview.com</a>.
          </p>
        </div>
      </Card>
    </div>
  )
}
