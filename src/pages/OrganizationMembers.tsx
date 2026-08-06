import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  UserGroupIcon,
  UserIcon,
  TrashIcon,
  ShieldCheckIcon,
  PencilIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Modal from '../components/ui/Modal'
import {
  fetchOrganizationMembers,
  updateMemberRole,
  removeMember,
  createInviteLink,
  type OrganizationMember,
  type OrganizationInviteResponse,
  type OrganizationRole,
} from '../api/client'
import { useOrganization } from '../hooks/useOrganization'
import { useAuth } from '../hooks/useAuth'

const roleLabels: Record<OrganizationRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  editor: 'Editor',
  viewer: 'Viewer',
}

const roleIcons: Record<OrganizationRole, typeof UserIcon> = {
  owner: ShieldCheckIcon,
  admin: ShieldCheckIcon,
  editor: PencilIcon,
  viewer: EyeIcon,
}

export default function OrganizationMembers() {
  const { orgId } = useParams<{ orgId: string }>()
  const navigate = useNavigate()
  const { currentOrg } = useOrganization()
  const [members, setMembers] = useState<OrganizationMember[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [inviteLink, setInviteLink] = useState<string | null>(null)
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [inviteRole, setInviteRole] = useState<OrganizationRole>('viewer')
  const [creatingInvite, setCreatingInvite] = useState(false)

  useEffect(() => {
    if (orgId) {
      loadMembers()
    }
  }, [orgId])

  const loadMembers = async () => {
    if (!orgId) return

    try {
      setLoading(true)
      setError(null)
      const memberList = await fetchOrganizationMembers(parseInt(orgId))
      setMembers(memberList)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load members')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateInvite = async () => {
    if (!orgId) return

    try {
      setCreatingInvite(true)
      setError(null)
      const response = await createInviteLink(parseInt(orgId), inviteRole, 7)
      setInviteLink(response.invite_url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create invite link')
    } finally {
      setCreatingInvite(false)
    }
  }

  const handleUpdateRole = async (memberId: number, newRole: OrganizationRole) => {
    if (!orgId) return

    try {
      await updateMemberRole(parseInt(orgId), memberId, newRole)
      await loadMembers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role')
    }
  }

  const handleRemoveMember = async (memberId: number) => {
    if (!orgId) return

    if (!confirm('Are you sure you want to remove this member?')) {
      return
    }

    try {
      await removeMember(parseInt(orgId), memberId)
      await loadMembers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove member')
    }
  }

  const { user } = useAuth()
  const currentUserMember = members.find((m) => m.user_id === user?.id)
  const currentUserRole = currentUserMember?.role || (currentOrg?.owner_user_id === user?.id ? 'owner' : 'viewer')
  const canManageMembers = currentUserRole === 'owner' || currentUserRole === 'admin'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-secondary mb-2">Team Members</h1>
          <p className="text-secondary-600">Manage team members and their roles.</p>
        </div>
        {canManageMembers && (
          <Button onClick={() => setShowInviteModal(true)}>
            <UserGroupIcon className="w-5 h-5 mr-2" />
            Invite Member
          </Button>
        )}
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
            <p className="text-secondary-500">Loading members...</p>
          </div>
        </Card>
      ) : (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-secondary-200">
              <thead className="bg-secondary-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">
                    Member
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">
                    Role
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-secondary-500 uppercase">
                    Joined
                  </th>
                  {canManageMembers && (
                    <th scope="col" className="relative px-6 py-3">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-secondary-200">
                {members.map((member) => {
                  const Icon = roleIcons[member.role]
                  const canEdit = canManageMembers && member.role !== 'owner'
                  const canRemove = canManageMembers && member.role !== 'owner'

                  return (
                    <tr key={member.id} className="hover:bg-secondary-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
                            <span className="text-primary font-medium text-sm">
                              {member.user_email?.charAt(0).toUpperCase() || '?'}
                            </span>
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-secondary-900">
                              {member.user_email || `User ID: ${member.user_id}`}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <Icon className="w-5 h-5 mr-2 text-secondary-500" />
                          <span className="text-sm text-secondary-900">{roleLabels[member.role]}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-500">
                        {new Date(member.created_at).toLocaleDateString()}
                      </td>
                      {canManageMembers && (
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <div className="flex items-center justify-end space-x-2">
                            {canEdit && (
                              <select
                                value={member.role}
                                onChange={(e) =>
                                  handleUpdateRole(member.id, e.target.value as OrganizationRole)
                                }
                                className="text-sm border border-secondary-300 rounded-lg px-2 py-1"
                              >
                                <option value="viewer">Viewer</option>
                                <option value="editor">Editor</option>
                                {currentUserRole === 'owner' && <option value="admin">Admin</option>}
                              </select>
                            )}
                            {canRemove && (
                              <button
                                onClick={() => handleRemoveMember(member.id)}
                                className="text-error-600 hover:text-error-800"
                              >
                                <TrashIcon className="w-5 h-5" />
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {showInviteModal && (
        <Modal
          isOpen={showInviteModal}
          onClose={() => {
            setShowInviteModal(false)
            setInviteLink(null)
            setInviteRole('viewer')
          }}
          title="Invite Team Member"
        >
          <div className="space-y-4">
            {inviteLink ? (
              <div>
                <p className="text-sm text-secondary-600 mb-2">Invite link created:</p>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    readOnly
                    value={inviteLink}
                    className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg bg-secondary-50 text-sm"
                  />
                  <Button
                    variant="secondary"
                    onClick={() => {
                      navigator.clipboard.writeText(inviteLink)
                      alert('Invite link copied to clipboard!')
                    }}
                  >
                    Copy
                  </Button>
                </div>
                <p className="text-xs text-secondary-500 mt-2">
                  Share this link with the person you want to invite. They can join by clicking the link.
                </p>
              </div>
            ) : (
              <>
                <div>
                  <label htmlFor="inviteRole" className="block text-sm font-medium text-secondary-700 mb-2">
                    Role
                  </label>
                  <select
                    id="inviteRole"
                    className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:ring-primary focus:border-primary"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as OrganizationRole)}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="editor">Editor</option>
                    {currentUserRole === 'owner' && <option value="admin">Admin</option>}
                  </select>
                  <p className="text-xs text-secondary-500 mt-1">
                    {inviteRole === 'viewer' && 'Can view organization data'}
                    {inviteRole === 'editor' && 'Can create and edit previews'}
                    {inviteRole === 'admin' && 'Can manage members and settings'}
                  </p>
                </div>
                <div className="flex justify-end space-x-3 pt-4">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setShowInviteModal(false)
                      setInviteLink(null)
                    }}
                    disabled={creatingInvite}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleCreateInvite} disabled={creatingInvite}>
                    {creatingInvite ? 'Creating...' : 'Create Invite Link'}
                  </Button>
                </div>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}

