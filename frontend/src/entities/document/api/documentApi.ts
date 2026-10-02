import { apiRequest } from '@/shared/api/client'

import type {
  AiMessage,
  CreateDocumentResult,
  CreateMergedDocumentResult,
  DocumentDetails,
  DocumentListItem,
  DocumentVersion,
} from '../model/types'

export function getDocuments() {
  return apiRequest<DocumentListItem[]>('/documents')
}

export function getDocument(id: string) {
  return apiRequest<DocumentDetails>(`/documents/${id}`)
}

export function createDocument(title: string, file: File) {
  const body = new FormData()
  body.set('title', title)
  body.set('file', file)
  return apiRequest<CreateDocumentResult>('/documents', { method: 'POST', body })
}

export function createMergedDocument(title: string, files: File[], mergeNotes?: string) {
  const body = new FormData()
  body.set('title', title)
  files.forEach((file) => body.append('files', file))
  if (mergeNotes?.trim()) body.set('merge_notes', mergeNotes.trim())
  return apiRequest<CreateMergedDocumentResult>('/documents/merge', { method: 'POST', body })
}

export function saveDocument(id: string, baseRevision: number, html: string) {
  return apiRequest<{ revision: number }>(`/documents/${id}/content`, {
    method: 'PUT',
    body: JSON.stringify({ base_revision: baseRevision, html }),
  })
}

export function exportDocumentPdf(id: string) {
  return apiRequest<{ url: string; expires_in: number }>(`/documents/${id}/exports/pdf`, {
    method: 'POST',
  })
}

export function exportDocumentHtmlPreview(id: string) {
  return apiRequest<{ url: string; expires_in: number }>(`/documents/${id}/previews/html`, {
    method: 'POST',
  })
}

export function getDocumentVersions(id: string) {
  return apiRequest<DocumentVersion[]>(`/documents/${id}/versions`)
}

export function restoreDocumentVersion(id: string, baseRevision: number, sourceRevision: number) {
  return apiRequest<{ revision: number }>(`/documents/${id}/versions/restore`, {
    method: 'POST',
    body: JSON.stringify({ base_revision: baseRevision, source_revision: sourceRevision }),
  })
}

export function editDocumentWithAi(
  id: string,
  baseRevision: number,
  instruction: string,
  targetBlockIds: string[] = [],
) {
  return apiRequest<{ revision: number; summary: string }>(`/documents/${id}/ai-edits`, {
    method: 'POST',
    body: JSON.stringify({
      base_revision: baseRevision,
      instruction,
      target_block_ids: targetBlockIds,
    }),
  })
}

export function getAiMessages(id: string) {
  return apiRequest<AiMessage[]>(`/documents/${id}/ai-messages`)
}

export function translateDocument(
  id: string,
  baseRevision: number,
  sourceLanguage: string,
  targetLanguage: string,
) {
  return apiRequest<{ revision: number }>(`/documents/${id}/translations`, {
    method: 'POST',
    body: JSON.stringify({
      base_revision: baseRevision,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    }),
  })
}

export function publishDocument(id: string) {
  return apiRequest<{ id: string; url: string; revision: number; expires_in: number | null }>(
    `/documents/${id}/publications`,
    { method: 'POST' },
  )
}

export function renameDocument(id: string, title: string) {
  return apiRequest<void>(`/documents/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export function deleteDocument(id: string) {
  return apiRequest<void>(`/documents/${id}`, { method: 'DELETE' })
}
