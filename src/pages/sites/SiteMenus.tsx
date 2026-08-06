import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  PlusIcon,
  TrashIcon,
  XMarkIcon,
  Bars3Icon,
  ChevronUpIcon,
  ChevronDownIcon,
  PencilSquareIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import {
  fetchSiteMenus,
  createSiteMenu,
  updateSiteMenu,
  deleteSiteMenu,
  createSiteMenuItem,
  updateSiteMenuItem,
  deleteSiteMenuItem,
  type SiteMenu,
  type SiteMenuItem,
  type SiteMenuCreate,
  type SiteMenuItemCreate,
  type SiteMenuItemUpdate,
} from '../../api/client'

const MENU_LOCATIONS = [
  { id: 'header', name: 'Header Navigation' },
  { id: 'footer', name: 'Footer Navigation' },
  { id: 'sidebar', name: 'Sidebar' },
]

export default function SiteMenus() {
  const { siteId } = useParams<{ siteId: string }>()
  const [menus, setMenus] = useState<SiteMenu[]>([])
  const [loading, setLoading] = useState(true)
  const [activeMenuId, setActiveMenuId] = useState<number | null>(null)
  const [showCreateMenu, setShowCreateMenu] = useState(false)
  const [showAddItem, setShowAddItem] = useState(false)
  const [editingItem, setEditingItem] = useState<SiteMenuItem | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'menu' | 'item'; id: number } | null>(null)
  const [saving, setSaving] = useState(false)

  // Form states
  const [newMenuName, setNewMenuName] = useState('')
  const [newMenuLocation, setNewMenuLocation] = useState('header')
  const [itemLabel, setItemLabel] = useState('')
  const [itemUrl, setItemUrl] = useState('')
  const [itemNewTab, setItemNewTab] = useState(false)

  useEffect(() => {
    if (siteId) loadMenus()
  }, [siteId])

  async function loadMenus() {
    if (!siteId) return
    try {
      setLoading(true)
      const data = await fetchSiteMenus(parseInt(siteId))
      setMenus(data)
      if (data.length > 0 && !activeMenuId) {
        setActiveMenuId(data[0].id)
      }
    } catch (err) {
      console.error('Failed to load menus:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateMenu(e: React.FormEvent) {
    e.preventDefault()
    if (!siteId || !newMenuName.trim()) return

    try {
      setSaving(true)
      const menu = await createSiteMenu(parseInt(siteId), {
        name: newMenuName.trim(),
        location: newMenuLocation,
        is_active: true,
      } as SiteMenuCreate)
      setMenus([...menus, menu])
      setActiveMenuId(menu.id)
      setShowCreateMenu(false)
      setNewMenuName('')
    } catch (err) {
      console.error('Failed to create menu:', err)
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteMenu(menuId: number) {
    if (!siteId) return
    try {
      await deleteSiteMenu(parseInt(siteId), menuId)
      const remaining = menus.filter(m => m.id !== menuId)
      setMenus(remaining)
      if (activeMenuId === menuId) {
        setActiveMenuId(remaining.length > 0 ? remaining[0].id : null)
      }
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete menu:', err)
    }
  }

  async function handleAddItem(e: React.FormEvent) {
    e.preventDefault()
    if (!siteId || !activeMenuId || !itemLabel.trim() || !itemUrl.trim()) return

    try {
      setSaving(true)
      const menu = menus.find(m => m.id === activeMenuId)
      const sortOrder = (menu?.items?.length || 0) + 1

      const item = await createSiteMenuItem(parseInt(siteId), activeMenuId, {
        label: itemLabel.trim(),
        url: itemUrl.trim(),
        open_in_new_tab: itemNewTab,
        sort_order: sortOrder,
        is_active: true,
      } as SiteMenuItemCreate)

      setMenus(menus.map(m => {
        if (m.id === activeMenuId) {
          return { ...m, items: [...(m.items || []), item] }
        }
        return m
      }))
      
      setShowAddItem(false)
      setItemLabel('')
      setItemUrl('')
      setItemNewTab(false)
    } catch (err) {
      console.error('Failed to add item:', err)
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdateItem(e: React.FormEvent) {
    e.preventDefault()
    if (!siteId || !activeMenuId || !editingItem) return

    try {
      setSaving(true)
      const updated = await updateSiteMenuItem(parseInt(siteId), activeMenuId, editingItem.id, {
        label: itemLabel.trim(),
        url: itemUrl.trim(),
        open_in_new_tab: itemNewTab,
      } as SiteMenuItemUpdate)

      setMenus(menus.map(m => {
        if (m.id === activeMenuId) {
          return {
            ...m,
            items: (m.items || []).map(i => i.id === editingItem.id ? updated : i)
          }
        }
        return m
      }))
      
      setEditingItem(null)
      setItemLabel('')
      setItemUrl('')
      setItemNewTab(false)
    } catch (err) {
      console.error('Failed to update item:', err)
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteItem(itemId: number) {
    if (!siteId || !activeMenuId) return
    try {
      await deleteSiteMenuItem(parseInt(siteId), activeMenuId, itemId)
      setMenus(menus.map(m => {
        if (m.id === activeMenuId) {
          return { ...m, items: (m.items || []).filter(i => i.id !== itemId) }
        }
        return m
      }))
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete item:', err)
    }
  }

  async function moveItem(itemId: number, direction: 'up' | 'down') {
    if (!activeMenuId) return
    const menu = menus.find(m => m.id === activeMenuId)
    if (!menu?.items) return

    const items = [...menu.items]
    const index = items.findIndex(i => i.id === itemId)
    if (index === -1) return
    if (direction === 'up' && index === 0) return
    if (direction === 'down' && index === items.length - 1) return

    const newIndex = direction === 'up' ? index - 1 : index + 1
    const [item] = items.splice(index, 1)
    items.splice(newIndex, 0, item)

    // Update sort orders
    const updatedItems = items.map((item, idx) => ({ ...item, sort_order: idx + 1 }))
    
    setMenus(menus.map(m => {
      if (m.id === activeMenuId) {
        return { ...m, items: updatedItems }
      }
      return m
    }))

    // Update on server
    if (siteId) {
      try {
        await updateSiteMenuItem(parseInt(siteId), activeMenuId, itemId, {
          sort_order: newIndex + 1
        } as SiteMenuItemUpdate)
      } catch (err) {
        console.error('Failed to reorder item:', err)
      }
    }
  }

  function startEditItem(item: SiteMenuItem) {
    setEditingItem(item)
    setItemLabel(item.label)
    setItemUrl(item.url || '')
    setItemNewTab(item.open_in_new_tab || false)
  }

  const activeMenu = menus.find(m => m.id === activeMenuId)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-secondary">Menus</h1>
          <p className="text-muted">Manage navigation menus for your site</p>
        </div>
        <Button onClick={() => setShowCreateMenu(true)}>
          <PlusIcon className="w-5 h-5 mr-2" />
          New Menu
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Menu List */}
        <Card className="lg:col-span-1">
          <h3 className="font-semibold text-secondary-900 mb-4">Menus</h3>
          {loading ? (
            <div className="flex items-center justify-center h-24">
              <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : menus.length === 0 ? (
            <p className="text-sm text-secondary-500">No menus yet</p>
          ) : (
            <div className="space-y-2">
              {menus.map((menu) => (
                <button
                  key={menu.id}
                  onClick={() => setActiveMenuId(menu.id)}
                  className={`w-full text-left p-3 rounded-lg transition-colors ${
                    activeMenuId === menu.id
                      ? 'bg-primary text-white'
                      : 'hover:bg-secondary-100'
                  }`}
                >
                  <p className="font-medium">{menu.name}</p>
                  <p className={`text-xs ${activeMenuId === menu.id ? 'text-white/70' : 'text-secondary-500'}`}>
                    {menu.location}
                  </p>
                </button>
              ))}
            </div>
          )}
        </Card>

        {/* Menu Editor */}
        <Card className="lg:col-span-3">
          {!activeMenu ? (
            <div className="flex flex-col items-center justify-center h-48 text-secondary-500">
              <Bars3Icon className="w-12 h-12 mb-2" />
              <p className="font-medium">Select or create a menu</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold text-secondary-900">{activeMenu.name}</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowAddItem(true)}
                    className="px-3 py-1.5 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                  >
                    Add Item
                  </button>
                  <button
                    onClick={() => setDeleteConfirm({ type: 'menu', id: activeMenu.id })}
                    className="p-2 text-error-600 hover:bg-error-50 rounded-lg transition-colors"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {!activeMenu.items?.length ? (
                <div className="text-center py-8 text-secondary-500">
                  <p className="mb-2">No items in this menu</p>
                  <button
                    onClick={() => setShowAddItem(true)}
                    className="text-primary hover:underline"
                  >
                    Add your first menu item
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  {activeMenu.items
                    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
                    .map((item, index) => (
                    <div
                      key={item.id}
                      className="flex items-center gap-3 p-3 bg-secondary-50 rounded-lg"
                    >
                      <div className="flex flex-col">
                        <button
                          onClick={() => moveItem(item.id, 'up')}
                          disabled={index === 0}
                          className="p-1 hover:bg-secondary-200 rounded disabled:opacity-30"
                        >
                          <ChevronUpIcon className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => moveItem(item.id, 'down')}
                          disabled={index === (activeMenu.items?.length || 0) - 1}
                          className="p-1 hover:bg-secondary-200 rounded disabled:opacity-30"
                        >
                          <ChevronDownIcon className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-secondary-900">{item.label}</p>
                        <p className="text-sm text-secondary-500">{item.url}</p>
                      </div>
                      {item.open_in_new_tab && (
                        <span className="text-xs text-secondary-400">Opens in new tab</span>
                      )}
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => startEditItem(item)}
                          className="p-2 hover:bg-secondary-200 rounded-lg transition-colors"
                        >
                          <PencilSquareIcon className="w-4 h-4 text-secondary-600" />
                        </button>
                        <button
                          onClick={() => setDeleteConfirm({ type: 'item', id: item.id })}
                          className="p-2 hover:bg-error-50 rounded-lg transition-colors"
                        >
                          <TrashIcon className="w-4 h-4 text-error-600" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      {/* Create Menu Modal */}
      {showCreateMenu && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-xl font-semibold text-secondary-900">New Menu</h2>
              <button
                onClick={() => setShowCreateMenu(false)}
                className="p-2 hover:bg-secondary-100 rounded-lg"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateMenu} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">Name</label>
                <input
                  type="text"
                  value={newMenuName}
                  onChange={(e) => setNewMenuName(e.target.value)}
                  placeholder="Menu name"
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">Location</label>
                <select
                  value={newMenuLocation}
                  onChange={(e) => setNewMenuLocation(e.target.value)}
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  {MENU_LOCATIONS.map((loc) => (
                    <option key={loc.id} value={loc.id}>{loc.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateMenu(false)}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-medium hover:bg-secondary-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50"
                >
                  {saving ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add/Edit Item Modal */}
      {(showAddItem || editingItem) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-xl font-semibold text-secondary-900">
                {editingItem ? 'Edit Menu Item' : 'Add Menu Item'}
              </h2>
              <button
                onClick={() => { setShowAddItem(false); setEditingItem(null); setItemLabel(''); setItemUrl(''); setItemNewTab(false); }}
                className="p-2 hover:bg-secondary-100 rounded-lg"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={editingItem ? handleUpdateItem : handleAddItem} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">Label</label>
                <input
                  type="text"
                  value={itemLabel}
                  onChange={(e) => setItemLabel(e.target.value)}
                  placeholder="Home"
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-secondary-700 mb-1">URL</label>
                <input
                  type="text"
                  value={itemUrl}
                  onChange={(e) => setItemUrl(e.target.value)}
                  placeholder="/about or https://..."
                  className="w-full px-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={itemNewTab}
                  onChange={(e) => setItemNewTab(e.target.checked)}
                  className="w-4 h-4 text-primary border-secondary-300 rounded focus:ring-primary"
                />
                <span className="text-sm text-secondary-700">Open in new tab</span>
              </label>
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowAddItem(false); setEditingItem(null); setItemLabel(''); setItemUrl(''); setItemNewTab(false); }}
                  className="flex-1 px-4 py-2 border border-secondary-300 rounded-lg font-medium hover:bg-secondary-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : editingItem ? 'Update' : 'Add'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="text-lg font-bold text-secondary-900 mb-2">
              Delete {deleteConfirm.type === 'menu' ? 'Menu' : 'Item'}?
            </h3>
            <p className="text-secondary-500 text-sm mb-6">
              {deleteConfirm.type === 'menu'
                ? 'This will delete the menu and all its items.'
                : 'This item will be removed from the menu.'}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 px-4 py-2 border border-secondary-200 rounded-lg font-medium hover:bg-secondary-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (deleteConfirm.type === 'menu') handleDeleteMenu(deleteConfirm.id)
                  else handleDeleteItem(deleteConfirm.id)
                }}
                className="flex-1 px-4 py-2 bg-error-500 text-white rounded-lg font-medium hover:bg-error-600"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
