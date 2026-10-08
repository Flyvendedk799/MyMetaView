import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Alert from '../components/ui/Alert'
import Input from '../components/ui/Input'
import { ConfirmDialog } from '../components/ui/Modal'
import { exportUserData, deleteUserAccount, changePassword, listApiKeys, createApiKey, revokeApiKey, getMyPlan, type ApiKeyRecord } from '../api/client'
import { FEATURES } from '../lib/plans'
import { useAuth } from '../hooks/useAuth'
import { ExclamationTriangleIcon, ArrowDownTrayIcon, KeyIcon } from '@heroicons/react/24/outline'
import AIAuthSettings from '../components/settings/AIAuthSettings'

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
  const [apiAccess, setApiAccess] = useState(false)
  const [apiKeys, setApiKeys] = useState<ApiKeyRecord[]>([])
  const [newKeyName, setNewKeyName] = useState('')
  const [freshToken, setFreshToken] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getMyPlan()
      .then(async (plan) => {
        const allowed = (plan.features || []).includes(FEATURES.API)
        if (!active) return
        setApiAccess(allowed)
        if (allowed) setApiKeys(await listApiKeys())
      })
      .catch(() => {
        if (active) setApiAccess(false)
      })
    return () => {
      active = false
    }
  }, [])

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
        <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Account Settings</h1>
        <p className="text-[15px] text-secondary-600">Your sign-in details, data, and privacy</p>
      </div>

      {error && (
        <div className="mb-6">
          <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>
        </div>
      )}

      {/* Profile Link */}
      <Card className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-secondary-900 mb-1">Profile</h2>
            <p className="text-secondary-600 text-sm">
              Manage your display name, bio, and public identity.
            </p>
          </div>
          <Link to="/app/profile" className="text-sm font-medium text-primary-600 hover:text-primary-700 bg-primary-50 px-4 py-2 rounded-lg transition-colors">
            Go to Profile
          </Link>
        </div>
      </Card>

      {/* AI Credentials */}
      <Card className="mb-6">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-secondary-900 mb-1">AI Credentials</h2>
          <p className="text-secondary-600 text-sm">
            Connect your personal AI subscriptions or API keys. These override your organization's credentials when set.
          </p>
        </div>
        <AIAuthSettings scope="user" />
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

      {apiAccess && (
        <Card className="mb-6">
          <h2 className="text-xl font-semibold text-secondary-900 mb-2">API keys</h2>
          <p className="text-sm text-secondary-600 mb-4">
            Send <code className="font-mono text-xs">Authorization: Bearer mv_…</code> to create preview jobs, read previews, and render platform cards.
          </p>
          <div className="flex gap-2 mb-4">
            <Input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name"
            />
            <Button
              onClick={async () => {
                if (!newKeyName.trim()) return
                const created = await createApiKey(newKeyName.trim())
                setFreshToken(created.token)
                setNewKeyName('')
                setApiKeys(await listApiKeys())
              }}
            >
              Create
            </Button>
          </div>
          {freshToken && (
            <Alert variant="success">
              Copy this key now. It will not be shown again: {freshToken}
            </Alert>
          )}
          <ul className="mt-3 space-y-2">
            {apiKeys.map((key) => (
              <li key={key.id} className="flex items-center justify-between text-sm">
                <span>{key.name} · <span className="font-mono">{key.prefix}…</span></span>
                <button
                  className="text-error-600"
                  onClick={async () => {
                    await revokeApiKey(key.id)
                    setApiKeys(await listApiKeys())
                  }}
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Account Deletion */}
      <Card className="mb-6 border-error-200">
        <div className="flex items-start space-x-3 mb-4">
          <ExclamationTriangleIcon className="w-6 h-6 text-error-500 flex-shrink-0 mt-1" />
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-error-700 mb-2">Delete account</h2>
            <p className="text-secondary-600 text-sm mb-4">
              Your account is anonymized. If another admin is in an organization you own, they become the owner. If you are the only member, that organization is deleted with the account.
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
        message="If another admin is in an organization you own, ownership transfers to the longest-tenured admin. If you are the only member, that organization is deleted."
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
