import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BuildingOfficeIcon, PlusIcon, ArrowRightIcon } from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import { fetchOrganizations, createOrganization, type Organization } from '../api/client'
import { useOrganization } from '../hooks/useOrganization'

export default function Organizations() {
  const navigate = useNavigate()
  const { currentOrg, refreshOrganizations } = useOrganization()
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newOrgName, setNewOrgName] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    loadOrganizations()
  }, [])

  const loadOrganizations = async () => {
    try {
      setLoading(true)
      setError(null)
      const orgs = await fetchOrganizations()
      setOrganizations(orgs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load organizations')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateOrganization = async () => {
    if (!newOrgName.trim()) {
      setError('Organization name is required')
      return
    }

    try {
      setCreating(true)
      setError(null)
      const newOrg = await createOrganization({ name: newOrgName.trim() })
      await refreshOrganizations()
      setShowCreateModal(false)
      setNewOrgName('')
      // Navigate to the new organization's settings
      navigate(`/app/organizations/${newOrg.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create organization')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-secondary mb-2">Organizations</h1>
          <p className="text-secondary-600">Manage your organizations and team members.</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <PlusIcon className="w-5 h-5 mr-2" />
          Create Organization
        </Button>
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
            <p className="text-secondary-500">Loading organizations...</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {organizations.length === 0 ? (
            <Card className="md:col-span-2 lg:col-span-3">
              <div className="text-center py-12">
                <BuildingOfficeIcon className="w-16 h-16 text-secondary-400 mx-auto mb-4" />
                <p className="text-secondary-500 mb-4">No organizations yet.</p>
                <Button onClick={() => setShowCreateModal(true)}>
                  Create Your First Organization
                </Button>
              </div>
            </Card>
          ) : (
            organizations.map((org) => (
              <div
                key={org.id}
                className={`cursor-pointer hover:shadow-lg transition-shadow ${
                  currentOrg?.id === org.id ? 'ring-2 ring-primary' : ''
                }`}
                onClick={() => {
                  navigate(`/app/organizations/${org.id}`)
                }}
              >
                <Card>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <BuildingOfficeIcon className="w-5 h-5 text-primary" />
                        <h3 className="text-lg font-semibold text-secondary">{org.name}</h3>
                      </div>
                      <p className="text-sm text-secondary-500 mb-4">
                        Subscription: <span className="font-medium">{org.subscription_status}</span>
                      </p>
                      {org.subscription_plan && (
                        <p className="text-sm text-secondary-500">
                          Plan: <span className="font-medium capitalize">{org.subscription_plan}</span>
                        </p>
                      )}
                    </div>
                    <ArrowRightIcon className="w-5 h-5 text-secondary-400" />
                  </div>
                  {currentOrg?.id === org.id && (
                    <div className="mt-4 pt-4 border-t border-secondary-200">
                      <span className="text-xs font-medium text-primary">Current Organization</span>
                    </div>
                  )}
                </Card>
              </div>
            ))
          )}
        </div>
      )}

      {showCreateModal && (
        <Modal
          isOpen={showCreateModal}
          onClose={() => {
            setShowCreateModal(false)
            setNewOrgName('')
            setError(null)
          }}
          title="Create Organization"
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
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="My Organization"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreateOrganization()
                  }
                }}
              />
            </div>
            <div className="flex justify-end space-x-3 pt-4">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowCreateModal(false)
                  setNewOrgName('')
                  setError(null)
                }}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button onClick={handleCreateOrganization} disabled={creating || !newOrgName.trim()}>
                {creating ? 'Creating...' : 'Create'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

