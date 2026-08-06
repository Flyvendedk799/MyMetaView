import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  MagnifyingGlassIcon,
  TrashIcon,
  ClipboardIcon,
  CheckIcon,
  PhotoIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'
import Card from '../../components/ui/Card'
import UploadZone from '../../components/media/UploadZone'
import { fetchSiteMedia, uploadSiteMedia, deleteSiteMedia, type SiteMedia } from '../../api/client'

export default function SiteMedia() {
  const { siteId } = useParams<{ siteId: string }>()
  const [media, setMedia] = useState<SiteMedia[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [selectedMedia, setSelectedMedia] = useState<SiteMedia | null>(null)

  useEffect(() => {
    if (siteId) loadMedia()
  }, [siteId])

  async function loadMedia() {
    if (!siteId) return
    try {
      setLoading(true)
      const data = await fetchSiteMedia(parseInt(siteId), { per_page: 100, search: search || undefined })
      setMedia(data)
    } catch (err) {
      console.error('Failed to load media:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(files: File[]) {
    if (!siteId) return
    for (const file of files) {
      try {
        const uploaded = await uploadSiteMedia(parseInt(siteId), file)
        setMedia(prev => [uploaded, ...prev])
      } catch (err) {
        console.error('Failed to upload:', err)
        throw err
      }
    }
  }

  async function handleDelete(mediaId: number) {
    if (!siteId) return
    try {
      await deleteSiteMedia(parseInt(siteId), mediaId)
      setMedia(media.filter(m => m.id !== mediaId))
      setDeleteConfirm(null)
      if (selectedMedia?.id === mediaId) {
        setSelectedMedia(null)
      }
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  function copyUrl(url: string, id: number) {
    navigator.clipboard.writeText(url)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    loadMedia()
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-secondary mb-2">Media Library</h1>
        <p className="text-muted">Upload and manage images for your site</p>
      </div>

      {/* Upload Zone */}
      <Card className="mb-6">
        <UploadZone onUpload={handleUpload} />
      </Card>

      {/* Search */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative max-w-md">
          <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-secondary-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search media..."
            className="w-full pl-10 pr-4 py-2 border border-secondary-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </form>

      {/* Media Grid */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : media.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-secondary-500">
            <PhotoIcon className="w-12 h-12 mb-2" />
            <p className="font-medium">No media found</p>
            <p className="text-sm">Upload your first image using the upload zone above</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {media.map((item) => (
              <div
                key={item.id}
                className="group relative aspect-square rounded-lg overflow-hidden bg-secondary-100 border border-secondary-200 hover:border-primary transition-colors"
              >
                <img
                  src={item.file_path}
                  alt={item.alt_text || item.filename}
                  className="w-full h-full object-cover"
                />
                
                {/* Overlay */}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedMedia(item)}
                      className="p-2 bg-white rounded-lg hover:bg-secondary-100 transition-colors"
                      title="View details"
                    >
                      <EyeIcon className="w-4 h-4 text-secondary-700" />
                    </button>
                    <button
                      onClick={() => copyUrl(item.file_path, item.id)}
                      className="p-2 bg-white rounded-lg hover:bg-secondary-100 transition-colors"
                      title="Copy URL"
                    >
                      {copiedId === item.id ? (
                        <CheckIcon className="w-4 h-4 text-success-600" />
                      ) : (
                        <ClipboardIcon className="w-4 h-4 text-secondary-700" />
                      )}
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(item.id)}
                      className="p-2 bg-white rounded-lg hover:bg-error-50 transition-colors"
                      title="Delete"
                    >
                      <TrashIcon className="w-4 h-4 text-error-600" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Media Details Modal */}
      {selectedMedia && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden">
            <div className="aspect-video bg-secondary-100 flex items-center justify-center">
              <img
                src={selectedMedia.file_path}
                alt={selectedMedia.alt_text || selectedMedia.filename}
                className="max-w-full max-h-full object-contain"
              />
            </div>
            <div className="p-6">
              <h3 className="font-semibold text-lg text-secondary-900 mb-4">{selectedMedia.filename}</h3>
              <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                <div>
                  <span className="text-secondary-500">Size:</span>
                  <span className="ml-2 font-medium">{formatFileSize(selectedMedia.file_size)}</span>
                </div>
                {selectedMedia.width && selectedMedia.height && (
                  <div>
                    <span className="text-secondary-500">Dimensions:</span>
                    <span className="ml-2 font-medium">{selectedMedia.width} Ã— {selectedMedia.height}</span>
                  </div>
                )}
                <div>
                  <span className="text-secondary-500">Type:</span>
                  <span className="ml-2 font-medium">{selectedMedia.mime_type}</span>
                </div>
                <div>
                  <span className="text-secondary-500">Uploaded:</span>
                  <span className="ml-2 font-medium">
                    {new Date(selectedMedia.uploaded_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <div className="mb-4">
                <label className="block text-sm text-secondary-500 mb-1">URL</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={selectedMedia.file_path}
                    readOnly
                    className="flex-1 px-3 py-2 bg-secondary-50 border border-secondary-300 rounded-lg text-sm font-mono"
                  />
                  <button
                    onClick={() => copyUrl(selectedMedia.file_path, selectedMedia.id)}
                    className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                  >
                    {copiedId === selectedMedia.id ? 'Copied!' : 'Copy'}
                  </button>
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setDeleteConfirm(selectedMedia.id)}
                  className="px-4 py-2 text-error-600 border border-error-300 rounded-lg hover:bg-error-50 transition-colors"
                >
                  Delete
                </button>
                <button
                  onClick={() => setSelectedMedia(null)}
                  className="px-4 py-2 bg-secondary-100 rounded-lg hover:bg-secondary-200 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="text-lg font-bold text-secondary-900 mb-2">Delete Media?</h3>
            <p className="text-secondary-500 text-sm mb-6">
              This action cannot be undone. The file will be permanently deleted.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 px-4 py-2 border border-secondary-200 rounded-lg font-medium hover:bg-secondary-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="flex-1 px-4 py-2 bg-error-500 text-white rounded-lg font-medium hover:bg-error-600 transition-colors"
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
