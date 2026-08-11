import { useState, useEffect } from 'react'
import { CheckCircleIcon, XCircleIcon, EyeIcon } from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import {
  fetchAdminUsers,
  fetchAdminUserById,
  toggleUserActive,
  type AdminUserSummary,
  type AdminUserDetail,
} from '../../api/client'

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUserSummary[]>([])
  const [selectedUser, setSelectedUser] = useState<AdminUserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [isDetailOpen, setIsDetailOpen] = useState(false)

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchAdminUsers()
      setUsers(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleActive = async (userId: number) => {
    if (!window.confirm('Are you sure you want to toggle this user\'s active status?')) {
      return
    }

    try {
      await toggleUserActive(userId)
      await loadUsers()
      if (selectedUser && selectedUser.id === userId) {
        const updated = await fetchAdminUserById(userId)
        setSelectedUser(updated)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle user status')
    }
  }

  const handleViewDetail = async (userId: number) => {
    try {
      const userDetail = await fetchAdminUserById(userId)
      setSelectedUser(userDetail)
      setIsDetailOpen(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load user details')
    }
  }

  const filteredUsers = users.filter((user) => {
    if (filter === 'all') return true
    if (filter === 'active') return user.is_active
    if (filter === 'inactive') return !user.is_active
    return user.subscription_status === filter
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-secondary mb-2">Admin / Users</h1>
        <p className="text-secondary-600">Manage all users in the system</p>
      </div>

      {error && (
        <Card className="mb-6 bg-error-50 border-error-200">
          <p className="text-error-800">Error: {error}</p>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-6">
        {['all', 'active', 'inactive', 'trialing', 'past_due', 'canceled'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg font-medium transition-all capitalize ${
              filter === f
                ? 'bg-primary text-white shadow-md'
                : 'bg-white text-secondary-700 border border-secondary-200 hover:border-primary hover:text-primary'
            }`}
          >
            {f.replace('_', ' ')}
          </button>
        ))}
      </div>

      {loading ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-secondary-500">Loading users...</p>
          </div>
        </Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-secondary-200">
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Email</th>
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Status</th>
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Plan</th>
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Domains</th>
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Previews</th>
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Created</th>
                <th className="text-left py-3 px-4 font-semibold text-secondary-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-secondary-500">
                    No users found
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr key={user.id} className="border-b border-secondary-100 hover:bg-secondary-50">
                    <td className="py-3 px-4">{user.email}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {user.is_active ? (
                          <CheckCircleIcon className="w-5 h-5 text-success-500" />
                        ) : (
                          <XCircleIcon className="w-5 h-5 text-error-500" />
                        )}
                        <span className="capitalize">{user.subscription_status}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 capitalize">{user.subscription_plan || 'Free'}</td>
                    <td className="py-3 px-4">{user.domains_count}</td>
                    <td className="py-3 px-4">{user.previews_count}</td>
                    <td className="py-3 px-4 text-sm text-secondary-500">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleViewDetail(user.id)}
                          className="text-primary hover:text-primary/80 transition-colors p-1"
                          title="View details"
                        >
                          <EyeIcon className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleToggleActive(user.id)}
                          className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                            user.is_active
                              ? 'bg-error-100 text-error-700 hover:bg-error-200'
                              : 'bg-success-100 text-success-700 hover:bg-success-200'
                          }`}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      )}

      {/* User Detail Drawer */}
      {isDetailOpen && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-secondary">User Details</h2>
              <button
                onClick={() => setIsDetailOpen(false)}
                className="text-secondary-500 hover:text-secondary-700"
              >
                ✕
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-secondary-600">Email</p>
                <p className="font-semibold">{selectedUser.email}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-secondary-600">Status</p>
                  <p className="font-semibold capitalize">{selectedUser.subscription_status}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Plan</p>
                  <p className="font-semibold capitalize">{selectedUser.subscription_plan || 'Free'}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Active</p>
                  <p className="font-semibold">{selectedUser.is_active ? 'Yes' : 'No'}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Admin</p>
                  <p className="font-semibold">{selectedUser.is_admin ? 'Yes' : 'No'}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Domains</p>
                  <p className="font-semibold">{selectedUser.domains_count}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Previews</p>
                  <p className="font-semibold">{selectedUser.previews_count}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Total Clicks</p>
                  <p className="font-semibold">{selectedUser.total_clicks.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-sm text-secondary-600">Created</p>
                  <p className="font-semibold">{new Date(selectedUser.created_at).toLocaleString()}</p>
                </div>
              </div>
              {selectedUser.trial_ends_at && (
                <div>
                  <p className="text-sm text-secondary-600">Trial Ends</p>
                  <p className="font-semibold">{new Date(selectedUser.trial_ends_at).toLocaleString()}</p>
                </div>
              )}
              <div className="pt-4 border-t">
                <Button
                  onClick={() => handleToggleActive(selectedUser.id)}
                  variant={selectedUser.is_active ? 'secondary' : 'primary'}
                >
                  {selectedUser.is_active ? 'Deactivate User' : 'Activate User'}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

