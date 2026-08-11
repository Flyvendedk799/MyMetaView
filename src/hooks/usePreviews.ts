import { useState, useEffect, useCallback } from 'react'
import { fetchPreviews, createOrUpdatePreview, updatePreview, deletePreview } from '../api/client'
import type { Preview, PreviewCreate, PreviewUpdate } from '../api/types'

/**
 * CRUD over the org's previews.
 *
 * AI generation is deliberately absent: it runs as a background job on the server
 * (see `createPreviewJob` + the generation-activity list on the Previews page), so
 * nothing here waits on it. Call `refetch` when a run reports finished.
 */
interface UsePreviewsReturn {
  previews: Preview[]
  loading: boolean
  error: string | null
  createOrUpdatePreview: (input: PreviewCreate) => Promise<Preview>
  updatePreview: (id: number, input: PreviewUpdate) => Promise<void>
  deletePreview: (id: number) => Promise<void>
  /**
   * Swap one already-updated preview into local state. For endpoints that
   * return the full updated row (restyle), which makes a refetch pure waste.
   */
  replacePreview: (preview: Preview) => void
  refetch: (type?: string) => Promise<void>
}

export function usePreviews(type?: string): UsePreviewsReturn {
  const [previews, setPreviews] = useState<Preview[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadPreviews = useCallback(
    async (filterType?: string) => {
      try {
        setLoading(true)
        setError(null)
        const data = await fetchPreviews(filterType)
        setPreviews(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load previews')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    loadPreviews(type)
  }, [loadPreviews, type])

  const handleCreateOrUpdate = useCallback(
    async (input: PreviewCreate): Promise<Preview> => {
      try {
        setError(null)
        const newPreview = await createOrUpdatePreview(input)
        await loadPreviews(type)
        return newPreview
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create/update preview')
        throw err
      }
    },
    [loadPreviews, type]
  )

  const handleUpdate = useCallback(
    async (id: number, input: PreviewUpdate): Promise<void> => {
      try {
        setError(null)
        await updatePreview(id, input)
        await loadPreviews(type)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update preview')
        throw err
      }
    },
    [loadPreviews, type]
  )

  const handleDelete = useCallback(
    async (id: number): Promise<void> => {
      try {
        setError(null)
        await deletePreview(id)
        setPreviews((prev) => prev.filter((p) => p.id !== id))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete preview')
        throw err
      }
    },
    []
  )

  const replacePreview = useCallback((updated: Preview) => {
    setPreviews((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }, [])

  return {
    previews,
    loading,
    error,
    createOrUpdatePreview: handleCreateOrUpdate,
    updatePreview: handleUpdate,
    deletePreview: handleDelete,
    replacePreview,
    refetch: loadPreviews,
  }
}

