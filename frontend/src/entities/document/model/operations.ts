export type DocumentBlockType = 'paragraph' | 'heading' | 'list' | 'table' | 'image' | 'callout' | 'page_break'

export interface DocumentInline {
  text: string
  marks?: Array<'bold' | 'italic' | 'underline' | 'link'>
}

export interface DocumentBlock {
  id: string
  type: DocumentBlockType
  content: DocumentInline[] | Record<string, unknown>
  attrs: Record<string, unknown>
}

export interface DocumentSnapshot {
  document_id: string
  revision: number
  metadata: {
    title: string
    language: string | null
    style_version_id: string | null
  }
  blocks: DocumentBlock[]
  layout: Record<string, unknown>
  comments: DocumentComment[]
}

export interface DocumentComment {
  id: string
  block_id: string | null
  text: string
  status: 'open' | 'resolved'
  created_at: string
}
