import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Alert from '../components/ui/Alert'
import Input, { Textarea } from '../components/ui/Input'
import { updateCurrentUser } from '../api/client'

export default function Profile() {
  const { user, refreshUser } = useAuth()

  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [bio, setBio] = useState(user?.bio || '')
  
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  
  // Unsaved changes tracking
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  // Sync state if user updates from context
  useEffect(() => {
    if (user && !hasUnsavedChanges) {
      setDisplayName(user.display_name || '')
      setBio(user.bio || '')
    }
  }, [user, hasUnsavedChanges])

  const handleFieldChange = () => {
    if (!hasUnsavedChanges) {
      setHasUnsavedChanges(true)
      setSuccess(false)
      setError(null)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Basic validation
    if (displayName.length > 50) {
      setError('Display name is too long (max 50 characters).')
      return
    }
    if (bio.length > 200) {
      setError('Bio is too long (max 200 characters).')
      return
    }

    try {
      setIsSaving(true)
      setError(null)
      
      await updateCurrentUser({
        display_name: displayName.trim() || null,
        bio: bio.trim() || null
      })
      
      // Update global user state
      if (refreshUser) {
        await refreshUser()
      }
      
      setSuccess(true)
      setHasUnsavedChanges(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update profile')
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setDisplayName(user?.display_name || '')
    setBio(user?.bio || '')
    setHasUnsavedChanges(false)
    setError(null)
    setSuccess(false)
  }

  // Handle reload block if unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  const getInitials = (nameOrEmail: string) => {
    if (!nameOrEmail) return '?'
    const parts = nameOrEmail.split(/[ @.]/)
    if (parts.length > 1 && parts[0] && parts[1]) {
      return (parts[0][0] + parts[1][0]).toUpperCase()
    }
    return nameOrEmail.substring(0, 2).toUpperCase()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-display text-secondary-900 mb-1.5">Profile</h1>
          <p className="text-[15px] text-secondary-600">Manage your public identity on MyMetaView</p>
        </div>
        <div>
          <Link to="/app/account" className="text-sm font-medium text-primary-600 hover:text-primary-700 bg-primary-50 px-3 py-2 rounded-lg transition-colors">
            Account Settings &rarr;
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-6">
          <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>
        </div>
      )}
      
      {success && (
        <div className="mb-6">
          <Alert variant="success" onDismiss={() => setSuccess(false)}>Profile updated successfully.</Alert>
        </div>
      )}

      <Card>
        <form onSubmit={handleSave} className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-6">
            <div className="flex-shrink-0 flex flex-col items-center">
              <div className="w-24 h-24 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 text-3xl font-semibold border-2 border-primary-200">
                {getInitials(displayName || user?.email || '')}
              </div>
              <p className="text-xs text-secondary-500 mt-3 text-center w-full max-w-[120px]">
                Initials avatar automatically generated.
              </p>
            </div>
            
            <div className="flex-1 space-y-5">
              <div>
                <Input
                  label="Email address"
                  value={user?.email || ''}
                  disabled
                  helperText="Your email address cannot be changed here."
                />
              </div>
              
              <div>
                <Input
                  label="Display name"
                  placeholder="e.g. Jane Doe"
                  value={displayName}
                  onChange={(e) => {
                    setDisplayName(e.target.value)
                    handleFieldChange()
                  }}
                  maxLength={50}
                />
              </div>
              
              <div>
                <Textarea
                  label="Short bio"
                  placeholder="Tell us a bit about yourself..."
                  value={bio}
                  onChange={(e) => {
                    setBio(e.target.value)
                    handleFieldChange()
                  }}
                  rows={4}
                  maxLength={200}
                  showCount
                />
              </div>
            </div>
          </div>
          
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-secondary-200">
            {hasUnsavedChanges && (
              <Button type="button" variant="secondary" onClick={handleCancel} disabled={isSaving}>
                Cancel
              </Button>
            )}
            <Button type="submit" loading={isSaving} disabled={!hasUnsavedChanges}>
              Save Changes
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
