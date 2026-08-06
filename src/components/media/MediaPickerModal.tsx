import { useState, useEffect } from 'react'
import { XMarkIcon, CheckIcon, MagnifyingGlassIcon, PhotoIcon } from '@heroicons/react/24/outline'
import UploadZone from './UploadZone'
import { uploadSiteMedia, fetchSiteMedia, type SiteMedia } from '../../api/client'

interface MediaPickerModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (media: SiteMedia) => void
  siteId: number
  title?: string
}

export default function MediaPickerModal({
  isOpen,
  onClose,
  onSelect,
  siteId,
  title = 'Select Image',
}: MediaPickerModalProps) {
  const [activeTab, setActiveTab] = useState<'library' | 'upload'>('library')
  const [media, setMedia] = useState<SiteMedia[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedMedia, setSelectedMedia] = useState<SiteMedia | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadMedia()
    }
  }, [isOpen, siteId])

  async function loadMedia() {
    try {
      setLoading(true)
      const data = await fetchSiteMedia(siteId, { per_page: 50, search: search || undefined })
      setMedia(data)
    } catch (err) {
      console.error('Failed to load media:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(files: File[]) {
    for (const file of files) {
      try {
        const uploaded = await uploadSiteMedia(siteId, file)
        setMedia(prev => [uploaded, ...prev])
        // Auto-select the uploaded file
        setSelectedMedia(uploaded)
        setActiveTab('library')
      } catch (err) {
        console.error('Failed to upload:', err)
        throw err
      }
    }
  }

  function handleSelect() {
    if (selectedMedia) {
      onSelect(selectedMedia)
      onClose()
      setSelectedMedia(null)
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    loadMedia()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold text-secondary-900">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-secondary-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b">
          <button
            onClick={() => setActiveTab('library')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'library'
                ? 'text-primary border-b-2 border-primary'
                : 'text-secondary-500 hover:text-secondary-700'
            }`}
          >
            Media Library
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'upload'
                ? 'text-primary border-b-2 border-primary'
                : 'text-secondary-500 hover:text-secondary-700'
            }`}
          >
            Upload New
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'library' ? (
            <div className="h-full flex flex-col">
              {/* Search */}
              <form onSubmit={handleSearch} className="p-4 border-b">
                <div className="relative">
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

              {/* Grid */}
              <div className="flex-1 overflow-auto p-4">
                {loading ? (
                  <div className="flex items-center justify-center h-48">
                    <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : media.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-48 text-secondary-500">
                    <PhotoIcon className="w-12 h-12 mb-2" />
                    <p>No media found</p>
                    <button
                      onClick={() => setActiveTab('upload')}
                      className="mt-2 text-primary hover:underline"
                    >
                      Upload your first image
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-4 gap-4">
                    {media.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => setSelectedMedia(item)}
                        className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                          selectedMedia?.id === item.id
                            ? 'border-primary ring-2 ring-primary/30'
                            : 'border-transparent hover:border-secondary-300'
                        }`}
                      >
                        <img
                          src={item.file_path}
                          alt={item.alt_text || item.filename}
                          className="w-full h-full object-cover"
                        />
                        {selectedMedia?.id === item.id && (
                          <div className="absolute top-2 right-2 w-6 h-6 bg-primary rounded-full flex items-center justify-center">
                            <CheckIcon className="w-4 h-4 text-white" />
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6">
              <UploadZone onUpload={handleUpload} />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t bg-secondary-50">
          {selectedMedia ? (
            <div className="flex items-center gap-3">
              <img
                src={selectedMedia.file_path}
                alt=""
                className="w-10 h-10 object-cover rounded"
              />
              <div className="text-sm">
                <p className="font-medium text-secondary-900">{selectedMedia.filename}</p>
                <p className="text-secondary-500">
                  {selectedMedia.width && selectedMedia.height
                    ? `${selectedMedia.width} Ã— ${selectedMedia.height}`
                    : 'Unknown size'}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-secondary-500">Select an image from the library or upload a new one</p>
          )}
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-secondary-300 rounded-lg font-medium hover:bg-secondary-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSelect}
              disabled={!selectedMedia}
              className="px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Select
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

