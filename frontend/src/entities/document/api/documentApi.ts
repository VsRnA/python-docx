import { apiRequest } from '@/shared/api/client'

import type {
  AiMessage,
  CreateDocumentResult,
  CreateMergedDocumentResult,
  DocumentDetails,
  DocumentListItem,
  DocumentVersion,
} from '../model/types'
import type { DocumentComment, DocumentOperation, DocumentSnapshot } from '../model/operations'

export function getDocuments(params?: { search?: string; status?: string; sort?: 'updated' | 'created' | 'title' }) {
  const query = new URLSearchParams()
  if (params?.search) query.set('search', params.search)
  if (params?.status && params.status !== 'all') query.set('status', params.status)
  if (params?.sort) query.set('sort', params.sort)
  return apiRequest<DocumentListItem[]>(`/documents${query.size ? `?${query}` : ''}`)
}

export function getDocument(id: string) {
  return apiRequest<DocumentDetails>(`/documents/${id}`)
}

export function cancelJob(jobId: string) {
  return apiRequest<{ id: string; status: string }>(`/jobs/${jobId}/cancel`, { method: 'POST' })
}

export function getDocumentSnapshot(id: string) {
  return apiRequest<DocumentSnapshot>(`/documents/${id}/snapshot`)
}

export function applyDocumentOperations(id: string, baseRevision: number, operations: DocumentOperation[]) {
  return apiRequest<{ revision: number; accepted_operations: string[] }>(`/documents/${id}/operations`, {
    method: 'POST',
    body: JSON.stringify({
      base_revision: baseRevision,
      operations: operations.map((operation) => ({
        ...operation,
        operation_id: operation.operation_id ?? crypto.randomUUID(),
      })),
    }),
  })
}

export function getDocumentOperations(id: string, after: number) {
  return apiRequest<{ revision: number; operations: DocumentOperation[] }>(`/documents/${id}/operations?after=${after}`)
}

export function createDocumentComment(id: string, blockId: string | null, text: string) {
  return apiRequest<DocumentComment>(`/documents/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify({ block_id: blockId, text }),
  })
}

export function updateDocumentComment(commentId: string, payload: { text?: string; status?: 'open' | 'resolved' }) {
  return apiRequest<DocumentComment>(`/documents/comments/${commentId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function createDocument(title: string, file: File, processing?: {
  styleVersionId?: string
  targetLanguage?: string
  translationEnabled?: boolean
  glossaryVersionId?: string
}) {
  const body = new FormData()
  body.set('title', title)
  body.set('file', file)
  if (processing?.styleVersionId) body.set('style_version_id', processing.styleVersionId)
  if (processing?.targetLanguage) body.set('target_language', processing.targetLanguage)
  body.set('translation_enabled', String(Boolean(processing?.translationEnabled)))
  if (processing?.glossaryVersionId) body.set('glossary_version_id', processing.glossaryVersionId)
  return apiRequest<CreateDocumentResult>('/documents', { method: 'POST', body })
}

export function uploadDocumentAsset(documentId: string, file: File) {
  const body = new FormData()
  body.set('file', file)
  return apiRequest<{ id: string; src: string; url: string; filename: string; alt: string }>(
    `/documents/${documentId}/assets`,
    { method: 'POST', body },
  )
}

export function createMergedDocument(title: string, files: File[], mergeNotes?: string, processing?: {
  styleVersionId?: string
  targetLanguage?: string
  translationEnabled?: boolean
  glossaryVersionId?: string
}) {
  const body = new FormData()
  body.set('title', title)
  files.forEach((file) => body.append('files', file))
  if (mergeNotes?.trim()) body.set('merge_notes', mergeNotes.trim())
  if (processing?.styleVersionId) body.set('style_version_id', processing.styleVersionId)
  if (processing?.targetLanguage) body.set('target_language', processing.targetLanguage)
  body.set('translation_enabled', String(Boolean(processing?.translationEnabled)))
  if (processing?.glossaryVersionId) body.set('glossary_version_id', processing.glossaryVersionId)
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

export function getDocumentVersion(id: string, revision: number) {
  return apiRequest<{ revision: number; html: string; reason: string; created_at: string }>(
    `/documents/${id}/versions/${revision}`,
  )
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

export function proposeDocumentAiEdit(id: string, baseRevision: number, instruction: string, targetBlockIds: string[] = []) {
  return apiRequest<{ base_revision: number; summary: string; before_html: string; after_html: string; operations: Array<{ operation: string; block_id: string; html?: string }> }>(`/documents/${id}/ai-edit-proposals`, {
    method: 'POST',
    body: JSON.stringify({ base_revision: baseRevision, instruction, target_block_ids: targetBlockIds }),
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
  glossaryVersion?: string,
) {
  return apiRequest<{ revision: number }>(`/documents/${id}/translations`, {
    method: 'POST',
    body: JSON.stringify({
      base_revision: baseRevision,
      source_language: sourceLanguage,
      target_language: targetLanguage,
      glossary_version: glossaryVersion || null,
    }),
  })
}

export function publishDocument(id: string) {
  return apiRequest<{ id: string; url: string; revision: number; expires_in: number | null }>(
    `/documents/${id}/publications`,
    { method: 'POST' },
  )
}

export function getDocumentPublications(id: string) {
  return apiRequest<import('../model/types').DocumentPublication[]>(`/documents/${id}/publications`)
}

export function revokeDocumentPublication(documentId: string, publicationId: string) {
  return apiRequest<void>(`/documents/${documentId}/publications/${publicationId}`, { method: 'DELETE' })
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
