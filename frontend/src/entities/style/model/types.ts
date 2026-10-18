export type StyleStatus = 'active' | 'archived'
export type StyleVersionStatus = 'draft' | 'validating' | 'published' | 'archived'

export interface StyleVersionSummary {
  id: string
  version: number
  status: StyleVersionStatus
  manifest_sha256: string
  settings: Record<string, unknown>
  validation_report: Record<string, unknown> | null
  created_at: string
  published_at: string | null
}

export interface DocumentStyle {
  id: string
  name: string
  description: string | null
  status: StyleStatus
  current_version: StyleVersionSummary | null
  versions_count: number
  created_at: string
  updated_at: string
}

export interface DocumentStyleDetails extends DocumentStyle {
  versions: StyleVersionSummary[]
}

export interface CreateStylePayload {
  name: string
  description?: string
  settings?: Record<string, unknown>
}

export interface UpdateStylePayload {
  name?: string
  description?: string
  prompt?: string
}

export interface ProcessingProfile {
  id: string
  document_id: string
  style_version_id: string
  source_language: string | null
  target_language: string | null
  translation_enabled: boolean
  status: string
  created_at: string
}
