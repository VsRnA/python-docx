import { apiRequest } from '@/shared/api/client'

import type { CreateStylePayload, DocumentStyle, DocumentStyleDetails, ProcessingProfile, UpdateStylePayload } from '../model/types'

export function getStyles() {
  return apiRequest<DocumentStyle[]>('/styles')
}

export function bootstrapStyles() {
  return apiRequest<DocumentStyle>('/styles/bootstrap', { method: 'POST' })
}

export function getStyle(id: string) {
  return apiRequest<DocumentStyleDetails>(`/styles/${id}`)
}

export function createStyle(payload: CreateStylePayload) {
  return apiRequest<DocumentStyle>('/styles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateStyle(styleId: string, payload: UpdateStylePayload) {
  return apiRequest<DocumentStyleDetails>(`/styles/${styleId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteStyle(styleId: string) {
  return apiRequest<void>(`/styles/${styleId}`, { method: 'DELETE' })
}

export function uploadStyleReference(styleId: string, file: File) {
  const body = new FormData()
  body.set('file', file)
  return apiRequest<{ filename: string; sha256: string; size_bytes: number }>(
    `/styles/${styleId}/reference`,
    { method: 'POST', body },
  )
}

export function getStyleReference(styleId: string) {
  return apiRequest<{ url: string; expires_in: number; filename: string | null }>(`/styles/${styleId}/reference`)
}

export function createProcessingProfile(documentId: string, payload: {
  style_version_id: string
  source_language?: string
  target_language?: string
  translation_enabled: boolean
}) {
  return apiRequest<ProcessingProfile>(`/documents/${documentId}/processing-profiles`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
