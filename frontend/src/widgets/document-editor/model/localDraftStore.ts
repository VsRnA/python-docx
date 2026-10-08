export interface LocalDraft {
  documentId: string
  baseRevision: number
  html: string
  updatedAt: number
}

const DATABASE_NAME = 'document-editor-local-drafts'
const STORE_NAME = 'drafts'

function openDraftDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'documentId' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Could not open local draft database'))
  })
}

export async function saveLocalDraft(draft: LocalDraft): Promise<void> {
  const database = await openDraftDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    transaction.objectStore(STORE_NAME).put({ ...draft, updatedAt: Date.now() })
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error ?? new Error('Could not save local draft'))
    transaction.onabort = () => reject(transaction.error ?? new Error('Local draft save was aborted'))
  })
  database.close()
}

export async function getLocalDraft(documentId: string): Promise<LocalDraft | null> {
  const database = await openDraftDatabase()
  const draft = await new Promise<LocalDraft | null>((resolve, reject) => {
    const request = database.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).get(documentId)
    request.onsuccess = () => resolve((request.result as LocalDraft | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Could not read local draft'))
  })
  database.close()
  return draft
}

export async function clearLocalDraft(documentId: string): Promise<void> {
  const database = await openDraftDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    transaction.objectStore(STORE_NAME).delete(documentId)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error ?? new Error('Could not clear local draft'))
    transaction.onabort = () => reject(transaction.error ?? new Error('Local draft clear was aborted'))
  })
  database.close()
}
