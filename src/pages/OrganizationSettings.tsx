import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { BuildingOfficeIcon, CreditCardIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import { getOrganization, updateOrganization, type Organization } from '../api/client'
import { useOrganization } from '../hooks/useOrganization'

export default function OrganizationSettings() {
  const { orgId } = useParams<{ orgId: string }>()
  const { currentOrg, refreshOrganizations } = useOrganization()
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [orgName, setOrgName] = useState('')
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    if (orgId) {
      loadOrganization()
    } else if (currentOrg) {
      setOrganization(currentOrg)
      setLoading(false)
    }
  }, [orgId, currentOrg])

  const loadOrganization = async () => {
    if (!orgId) return

    try {
      setLoading(true)
      setError(null)
      const org = await getOrganization(parseInt(orgId))
      setOrganization(org)
      setOrgName(org.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load organization')
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateName = async () => {
    if (!orgId || !orgName.trim()) return

    try {
      setUpdating(true)
      setError(null)
      const updated = await updateOrganization(parseInt(orgId), { name: orgName.trim() })
      setOrganization(updated)
      await refreshOrganizations()
      setShowEditModal(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update organization')
    } finally {
      setUpdating(false)
    }
  }

  const org = organization || currentOrg
  if (!org) return null

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Organization Settings</h1>
        <p className="text-secondary-600">Manage your organization details and billing.</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Loading organization...</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Organization Details */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-secondary">Organization Details</h2>
              <Button variant="secondary" onClick={() => setShowEditModal(true)}>
                Edit Name
              </Button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">Name</label>
                <div className="flex items-center space-x-2">
                  <BuildingOfficeIcon className="w-5 h-5 text-secondary-500" />
                  <p className="text-secondary-900">{org.name}</p>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">Created</label>
                <p className="text-secondary-900">{new Date(org.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          </Card>

          {/* Billing Status */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-secondary">Billing</h2>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">Subscription Status</label>
                <div className="flex items-center space-x-2">
                  <CreditCardIcon className="w-5 h-5 text-secondary-500" />
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${
                      org.subscription_status === 'active'
                        ? 'bg-success-100 text-success-800'
                        : org.subscription_status === 'trialing'
                        ? 'bg-primary-100 text-primary-800'
                        : 'bg-secondary-100 text-secondary-800'
                    }`}
                  >
                    {org.subscription_status.charAt(0).toUpperCase() + org.subscription_status.slice(1)}
                  </span>
                </div>
              </div>
              {org.subscription_plan && (
                <div>
                  <label className="block text-sm font-medium text-secondary-700 mb-1">Plan</label>
                  <p className="text-secondary-900 capitalize">{org.subscription_plan}</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {showEditModal && (
        <Modal
          isOpen={showEditModal}
          onClose={() => {
            setShowEditModal(false)
            setOrgName(org.name)
            setError(null)
          }}
          title="Edit Organization Name"
        >
          <div className="space-y-4">
            <div>
              <label htmlFor="orgName" className="block text-sm font-medium text-secondary-700 mb-2">
                Organization Name
              </label>
              <input
                type="text"
                id="orgName"
                className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-primary focus:border-primary"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Organization Name"
                autoFocus
              />
            </div>
            <div className="flex justify-end space-x-3 pt-4">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowEditModal(false)
                  setOrgName(org.name)
                  setError(null)
                }}
                disabled={updating}
              >
                Cancel
              </Button>
              <Button onClick={handleUpdateName} disabled={updating || !orgName.trim()}>
                {updating ? 'Updating...' : 'Update'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

