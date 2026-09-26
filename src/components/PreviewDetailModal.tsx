/**
 * Preview detail: how one preview actually looks where it matters.
 *
 * Platform-accurate mockups (Facebook, X, LinkedIn, Slack), the exact meta
 * tags being served, per-size card exports, and the actions you reach for
 * with a finished card: copy, download, open.
 */
import { useEffect, useMemo, useState } from 'react'
import Modal from './ui/Modal'
import SpatialPreviewStudio from './SpatialPreviewStudio'
import type { Preview, PreviewVariant } from '../api/types'

interface PreviewDetailModalProps {
  preview: Preview | null
  variant: PreviewVariant | null
  isOpen: boolean
  onClose: () => void
}

export default function PreviewDetailModal({ preview, variant, isOpen, onClose }: PreviewDetailModalProps) {
  if (!preview) return null

  // Create a combined preview object for the studio
  const studioPreview = {
    ...preview,
    title: variant?.title || preview.title,
    description: variant?.description || preview.description,
    composited_preview_image_url: variant?.image_url || preview.image_url || preview.highlight_image_url,
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Spatial Preview Studio" size="xl">
      <div className="h-[85vh] -mx-6 -mb-6 overflow-hidden bg-[#09090b]">
        <SpatialPreviewStudio preview={studioPreview} />
      </div>
    </Modal>
  )
}

