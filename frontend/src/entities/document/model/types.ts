export type DocumentStatus =
  | 'uploaded'
  | 'queued'
  | 'processing'
  | 'ready'
  | 'processing_failed'
  | 'archived'
  | 'deleted'

export interface DocumentListItem {
  id: string
  title: string
  source_filename: string
  source_size_bytes: number
  status: DocumentStatus
  current_revision: number
  created_at: string
  updated_at: string
}

export interface DocumentDetails {
  id: string
  title: string
  source_filename: string
  source_size_bytes: number
  status: DocumentStatus
  current_revision: number
  html: string | null
  astra_html: string | null
  theme_id: string | null
  theme_version: string | null
  asset_urls: Record<string, string>
}

export interface CreateDocumentResult {
  document_id: string
  job_id: string
}

export interface DocumentVersion {
  revision: number
  reason: string
  created_by: string | null
  created_at: string
}

export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  revision: number
  created_at: string
}

export interface SelectionContextBlock {
  blockId: string
  blockType: string
  textPreview: string
}

export interface SelectionContext {
  scope: 'selection' | 'current-block' | 'document'
  blockIds: string[]
  blocks: SelectionContextBlock[]
  selectedText: string
  textPreview: string
  characterCount: number
}
