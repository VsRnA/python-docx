import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'

import { exportDocumentPdf, getDocument, publishDocument, renameDocument } from '@/entities/document'
import type { SelectionContext } from '@/entities/document'
import { DocumentAssistant } from '@/features/document-assistant'
import { DocumentEditor } from '@/widgets/document-editor'

import styles from './editor-page.module.css'

export function EditorPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [revision, setRevision] = useState(0)
  const [saveState, setSaveState] = useState<'saved' | 'changed' | 'saving' | 'error'>('saved')
  const [assistantBusy, setAssistantBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [viewMode, setViewMode] = useState<'final' | 'preview' | 'astra' | 'code'>('final')
  const [assistantOpen, setAssistantOpen] = useState(true)
  const [notification, setNotification] = useState<string | null>(null)
  const [publishConfirmationOpen, setPublishConfirmationOpen] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [selectionContext, setSelectionContext] = useState<SelectionContext>({
    scope: 'document',
    blockIds: [],
    blocks: [],
    selectedText: '',
    textPreview: '',
    characterCount: 0,
  })
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId!),
    enabled: Boolean(documentId),
    refetchInterval: ({ state }) =>
      state.data && ['uploaded', 'queued', 'processing'].includes(state.data.status) ? 3000 : false,
  })
  const exportPdf = useMutation({
    mutationFn: () => exportDocumentPdf(documentId!),
    onSuccess: ({ url }) => {
      setNotification('PDF сформирован и открыт в новой вкладке')
      window.open(url, '_blank', 'noopener,noreferrer')
    },
    onError: () => setNotification('Не удалось сформировать PDF. Повторите попытку.'),
  })
  const pdfPreview = useQuery({
    queryKey: ['document-pdf-preview', documentId, revision],
    queryFn: () => exportDocumentPdf(documentId!),
    enabled: Boolean(documentId && revision > 0 && viewMode === 'preview'),
    staleTime: 10 * 60 * 1000,
  })
  const publication = useMutation({
    mutationFn: () => publishDocument(documentId!),
    onSuccess: ({ url }) => {
      setPublishConfirmationOpen(false)
      setNotification('Документ опубликован')
      window.open(url, '_blank', 'noopener,noreferrer')
    },
    onError: () => setNotification('Не удалось опубликовать документ. Повторите попытку.'),
  })
  const rename = useMutation({
    mutationFn: (nextTitle: string) => renameDocument(documentId!, nextTitle),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  useEffect(() => {
    if (query.data) {
      setRevision(query.data.current_revision)
      setTitle(query.data.title)
    }
  }, [query.data])

  if (query.isLoading) return <main className={styles.state}>Загрузка документа…</main>
  if (query.isError || !query.data) {
    return <main className={styles.state}>Не удалось открыть документ.</main>
  }

  const document = query.data
  const saveStatus = {
    saved: 'Все изменения сохранены',
    changed: 'Есть несохранённые изменения',
    saving: 'Сохранение…',
    error: 'Не удалось сохранить',
  }[saveState]

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link className={styles.backButton} to="/" aria-label="К документам" title="К документам">←</Link>
        <div className={styles.documentIdentity}>
          <input
            className={styles.titleInput}
            aria-label="Название документа"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onBlur={() => {
              const nextTitle = title.trim()
              if (nextTitle && nextTitle !== document.title) rename.mutate(nextTitle)
              else setTitle(document.title)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.currentTarget.blur()
            }}
          />
          <span
            className={`${styles.saveStatus} ${styles[saveState]}`}
            aria-live="polite"
            title={saveError ?? undefined}
          >
            <span aria-hidden="true" />
            {rename.isPending ? 'Сохранение названия…' : saveError ?? saveStatus}
          </span>
        </div>
        <div className={styles.actions}>
          <button
            className={styles.secondaryAction}
            type="button"
            disabled={exportPdf.isPending || saveState !== 'saved'}
            title={saveState === 'saved' ? 'Сформировать PDF текущей версии' : 'Дождитесь сохранения изменений'}
            onClick={() => exportPdf.mutate()}
          >
            <span aria-hidden="true">↓</span>
            {exportPdf.isPending ? 'Формирование…' : 'Экспорт PDF'}
          </button>
          <button
            className={styles.primaryAction}
            type="button"
            disabled={publication.isPending || saveState !== 'saved'}
            onClick={() => setPublishConfirmationOpen(true)}
          >
            Опубликовать
          </button>
        </div>
      </header>
      {document.status === 'ready' && document.html ? (
        <div className={`${styles.editorLayout} ${viewMode !== 'final' || !assistantOpen ? styles.panelClosed : ''}`}>
          <section className={styles.documentColumn}>
            <nav className={styles.viewSwitcher} aria-label="Режим просмотра документа">
              <div className={styles.modeTabs} role="tablist" aria-label="Режим документа">
                <button role="tab" type="button" aria-selected={viewMode === 'final'} onClick={() => setViewMode('final')}>
                  Редактор
                </button>
                <button
                  role="tab"
                  type="button"
                  aria-selected={viewMode === 'preview'}
                  disabled={saveState !== 'saved'}
                  title={saveState === 'saved' ? 'Точный вид экспортируемого PDF' : 'Предпросмотр станет доступен после сохранения'}
                  onClick={() => setViewMode('preview')}
                >
                  Предпросмотр PDF
                </button>
              </div>
              <div className={styles.viewActions}>
                {viewMode === 'final' && !assistantOpen && (
                  <button type="button" onClick={() => setAssistantOpen(true)}>Открыть помощника</button>
                )}
                <details className={styles.diagnostics}>
                  <summary aria-label="Диагностические режимы" title="Диагностические режимы">⋯</summary>
                  <div>
                    <button type="button" disabled={!document.astra_html} onClick={() => setViewMode('astra')}>
                      Отображение Astra
                    </button>
                    <button type="button" disabled={!document.astra_html} onClick={() => setViewMode('code')}>
                      Исходный HTML Astra
                    </button>
                  </div>
                </details>
              </div>
            </nav>
            {viewMode === 'preview' ? (
              <section className={styles.pdfPreview} aria-label="Предпросмотр PDF">
                <div className={styles.pdfPreviewActions}>
                  <span>Ревизия {revision}</span>
                  <button type="button" disabled={pdfPreview.isFetching} onClick={() => pdfPreview.refetch()}>
                    {pdfPreview.isFetching ? 'Обновление…' : 'Обновить'}
                  </button>
                  {pdfPreview.data?.url && (
                    <a href={pdfPreview.data.url} target="_blank" rel="noreferrer">Открыть отдельно</a>
                  )}
                </div>
                {pdfPreview.isPending ? (
                  <div className={styles.pdfPreviewState}>Формируем точный печатный вид…</div>
                ) : pdfPreview.isError || !pdfPreview.data ? (
                  <div className={styles.pdfPreviewState}>Не удалось сформировать PDF-предпросмотр.</div>
                ) : (
                  <iframe
                    className={styles.pdfFrame}
                    src={pdfPreview.data.url}
                    title={`Предпросмотр PDF: ${document.title}`}
                    referrerPolicy="no-referrer"
                  />
                )}
              </section>
            ) : viewMode === 'code' ? (
              <pre className={styles.htmlSource}>{document.astra_html}</pre>
            ) : (
              <DocumentEditor
                key={viewMode}
                documentId={document.id}
                revision={document.current_revision}
                html={viewMode === 'astra' ? document.astra_html ?? document.html : document.html}
                assetUrls={document.asset_urls}
                editable={viewMode === 'final' && !assistantBusy}
                onRevisionChange={viewMode === 'final' ? setRevision : undefined}
                onSaveStateChange={viewMode === 'final' ? setSaveState : undefined}
                onSaveError={viewMode === 'final' ? setSaveError : undefined}
                selectionBlockIds={[]}
                highlightBlockIds={[]}
                onSelectionChange={viewMode === 'final' ? setSelectionContext : undefined}
              />
            )}
          </section>
          {viewMode === 'final' && assistantOpen && (
            <DocumentAssistant
              documentId={document.id}
              revision={revision}
              canMutate={saveState === 'saved'}
              selectionContext={selectionContext}
              onRevisionChange={setRevision}
              onBusyChange={setAssistantBusy}
              onClose={() => setAssistantOpen(false)}
            />
          )}
        </div>
      ) : (
        <section className={styles.processing}>
          <h2>Документ обрабатывается</h2>
          <p>Страница обновится автоматически после завершения GPT Astra 6.</p>
        </section>
      )}
      {notification && (
        <div className={styles.notification} role="status">
          <span>{notification}</span>
          <button type="button" aria-label="Закрыть уведомление" onClick={() => setNotification(null)}>×</button>
        </div>
      )}
      {publishConfirmationOpen && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={() => setPublishConfirmationOpen(false)}>
          <section
            className={styles.modal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="publish-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="publish-title">Опубликовать документ?</h2>
            <p>Будет опубликована версия {revision} документа «{document.title}».</p>
            <div>
              <button type="button" onClick={() => setPublishConfirmationOpen(false)}>Отмена</button>
              <button className={styles.primaryAction} type="button" disabled={publication.isPending} onClick={() => publication.mutate()}>
                {publication.isPending ? 'Публикация…' : 'Опубликовать'}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
