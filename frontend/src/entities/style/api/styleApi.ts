import { apiRequest } from '@/shared/api/client'

import type {
  CreateStylePayload,
  DocumentStyle,
  DocumentStyleDetails,
  ProcessingProfile,
  StyleVersionSummary,
} from '../model/types'

export function getStyles() {
  return apiRequest<DocumentStyle[]>('/styles')
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

export function createStyleVersion(styleId: string) {
  return apiRequest<StyleVersionSummary>(`/styles/${styleId}/versions`, { method: 'POST' })
}

export function duplicateStyle(styleId: string) {
  return apiRequest<DocumentStyle>(`/styles/${styleId}/duplicate`, { method: 'POST' })
}

export function archiveStyle(styleId: string) {
  return apiRequest<DocumentStyle>(`/styles/${styleId}/archive`, { method: 'POST' })
}

export function updateStyleVersion(versionId: string, settings: Record<string, unknown>) {
  return apiRequest<StyleVersionSummary>(`/style-versions/${versionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ settings }),
  })
}

export function validateStyleVersion(versionId: string) {
  return apiRequest<StyleVersionSummary>(`/style-versions/${versionId}/validate`, { method: 'POST' })
}

export function publishStyleVersion(versionId: string) {
  return apiRequest<StyleVersionSummary>(`/style-versions/${versionId}/publish`, { method: 'POST' })
}

export function previewStyleVersion(versionId: string) {
  return apiRequest<{ url: string; expires_in: number }>(`/style-versions/${versionId}/preview`, { method: 'POST' })
}

export function uploadStyleReference(versionId: string, file: File) {
  const body = new FormData()
  body.set('file', file)
  return apiRequest<{ filename: string; sha256: string; size_bytes: number }>(
    `/style-versions/${versionId}/reference`,
    { method: 'POST', body },
  )
}

export function createProcessingProfile(documentId: string, payload: {
  style_version_id: string
  source_language?: string
  target_language?: string
  translation_enabled: boolean
  glossary_version_id?: string
}) {
  return apiRequest<ProcessingProfile>(`/documents/${documentId}/processing-profiles`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
