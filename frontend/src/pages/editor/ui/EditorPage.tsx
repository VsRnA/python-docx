import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'

import { exportDocumentPdf, getDocument, publishDocument, renameDocument } from '@/entities/document'
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
    onSuccess: ({ url }) => window.open(url, '_blank', 'noopener,noreferrer'),
  })
  const pdfPreview = useQuery({
    queryKey: ['document-pdf-preview', documentId, revision],
    queryFn: () => exportDocumentPdf(documentId!),
    enabled: Boolean(documentId && revision > 0 && viewMode === 'preview'),
    staleTime: 10 * 60 * 1000,
  })
  const publication = useMutation({
    mutationFn: () => publishDocument(documentId!),
    onSuccess: ({ url }) => window.open(url, '_blank', 'noopener,noreferrer'),
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
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link to="/" aria-label="Вернуться к документам">←</Link>
        <div>
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
          <span>{document.status}</span>
        </div>
        <div className={styles.actions}>
          <button type="button" disabled={exportPdf.isPending} onClick={() => exportPdf.mutate()}>
            {exportPdf.isPending ? 'Формирование…' : 'Экспорт PDF'}
          </button>
          <button type="button" disabled={publication.isPending} onClick={() => publication.mutate()}>
            {publication.isPending ? 'Публикация…' : 'Опубликовать'}
          </button>
        </div>
      </header>
      {document.status === 'ready' && document.html ? (
        <div className={`${styles.editorLayout} ${viewMode !== 'final' ? styles.debugLayout : ''}`}>
          <section className={styles.documentColumn}>
            <nav className={styles.viewSwitcher} aria-label="Режим просмотра документа">
              <button
                type="button"
                aria-pressed={viewMode === 'final'}
                onClick={() => setViewMode('final')}
              >
                Редактор
              </button>
              <button
                type="button"
                aria-pressed={viewMode === 'preview'}
                disabled={saveState !== 'saved'}
                title={saveState === 'saved' ? 'Точный вид экспортируемого PDF' : 'Дождитесь сохранения изменений'}
                onClick={() => setViewMode('preview')}
              >
                Предпросмотр PDF
              </button>
              <button
                type="button"
                aria-pressed={viewMode === 'astra'}
                disabled={!document.astra_html}
                title={document.astra_html ? undefined : 'Доступно для документов, обработанных после обновления'}
                onClick={() => setViewMode('astra')}
              >
                Отображение Astra
              </button>
              <button
                type="button"
                aria-pressed={viewMode === 'code'}
                disabled={!document.astra_html}
                title={document.astra_html ? undefined : 'Доступно для документов, обработанных после обновления'}
                onClick={() => setViewMode('code')}
              >
                HTML Astra
              </button>
              {viewMode === 'preview' && (
                <span>Точный печатный вид — совпадает с экспортом PDF</span>
              )}
              {(viewMode === 'astra' || viewMode === 'code') && (
                <span>Диагностический режим — редактирование и автосохранение отключены</span>
              )}
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
              />
            )}
          </section>
          {viewMode === 'final' && (
            <DocumentAssistant
              documentId={document.id}
              revision={revision}
              canMutate={saveState === 'saved'}
              onRevisionChange={setRevision}
              onBusyChange={setAssistantBusy}
            />
          )}
        </div>
      ) : (
        <section className={styles.processing}>
          <h2>Документ обрабатывается</h2>
          <p>Страница обновится автоматически после завершения GPT Astra 6.</p>
        </section>
      )}
    </main>
  )
}
