export const queryKeys = {
  documents: (search = '', status = 'all', sort = 'updated') => ['documents', search, status, sort] as const,
  document: (id: string | undefined) => ['document', id] as const,
  job: (id: string | undefined) => ['job', id] as const,
  styles: () => ['styles'] as const,
  style: (id: string | undefined) => ['style', id] as const,
  documentPreview: (id: string | undefined, revision: number) => ['document-html-preview', id, revision] as const,
  documentVersions: (id: string | undefined) => ['document-versions', id] as const,
  documentVersion: (id: string | undefined, revision: number | null) => ['document-version', id, revision] as const,
  publications: (id: string | undefined) => ['publications', id] as const,
  aiMessages: (id: string | undefined) => ['document-ai-messages', id] as const,
  snapshot: (id: string | undefined, revision: number) => ['document-snapshot', id, revision] as const,
} as const
