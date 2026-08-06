import { useState, useCallback, useRef } from 'react'
import { CloudArrowUpIcon, XMarkIcon } from '@heroicons/react/24/outline'

interface UploadZoneProps {
  onUpload: (files: File[]) => Promise<void>
  accept?: string
  multiple?: boolean
  maxSize?: number // in bytes
  disabled?: boolean
}

export default function UploadZone({
  onUpload,
  accept = 'image/*',
  multiple = true,
  maxSize = 10 * 1024 * 1024, // 10MB default
  disabled = false,
}: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) setIsDragging(true)
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const validateFiles = (files: File[]): File[] => {
    const validFiles: File[] = []
    const errors: string[] = []

    for (const file of files) {
      if (file.size > maxSize) {
        errors.push(`${file.name} is too large (max ${Math.round(maxSize / 1024 / 1024)}MB)`)
        continue
      }
      validFiles.push(file)
    }

    if (errors.length > 0) {
      setError(errors.join(', '))
    }

    return validFiles
  }

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0 || disabled) return

    setError(null)
    const fileArray = Array.from(files)
    const validFiles = validateFiles(fileArray)

    if (validFiles.length === 0) return

    setUploading(true)
    setUploadProgress(0)

    try {
      await onUpload(validFiles)
      setUploadProgress(100)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      setUploadProgress(0)
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    handleFiles(e.dataTransfer.files)
  }, [disabled])

  const handleClick = () => {
    if (!disabled) {
      inputRef.current?.click()
    }
  }

  return (
    <div className="w-full">
      <div
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
          ${isDragging ? 'border-primary bg-primary/5' : 'border-secondary-300 hover:border-primary/50'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
          ${uploading ? 'pointer-events-none' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
          disabled={disabled}
        />

        {uploading ? (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-secondary-600">Uploading...</p>
            {uploadProgress > 0 && (
              <div className="w-full max-w-xs mt-4 bg-secondary-200 rounded-full h-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            )}
          </div>
        ) : (
          <>
            <CloudArrowUpIcon className="w-12 h-12 text-secondary-400 mx-auto mb-4" />
            <p className="text-secondary-600 mb-2">
              <span className="text-primary font-medium">Click to upload</span> or drag and drop
            </p>
            <p className="text-sm text-secondary-500">
              {accept === 'image/*' ? 'PNG, JPG, GIF, WebP up to ' : 'Files up to '}
              {Math.round(maxSize / 1024 / 1024)}MB
            </p>
          </>
        )}
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 p-3 bg-error-50 border border-error-200 rounded-lg">
          <XMarkIcon 
            className="w-5 h-5 text-error-500 flex-shrink-0 cursor-pointer" 
            onClick={() => setError(null)} 
          />
          <p className="text-sm text-error-700">{error}</p>
        </div>
      )}
    </div>
  )
}

