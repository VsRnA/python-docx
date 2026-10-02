import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'

import { exportDocumentHtmlPreview, exportDocumentPdf, getDocument, publishDocument, renameDocument } from '@/entities/document'
import type { SelectionContext } from '@/entities/document'
import { DocumentAssistant } from '@/features/document-assistant'
import { cn } from '@/shared/lib/cn'
import { DocumentEditor } from '@/widgets/document-editor'

const headerActionClass = cn(
  'inline-flex min-h-9 cursor-pointer items-center justify-center gap-[7px] rounded-[7px] border px-[13px] font-semibold',
  'disabled:cursor-default disabled:opacity-50',
)

const secondaryActionClass = cn(
  headerActionClass,
  'border-[#bdc3ca] bg-white text-[#2b3036] hover:bg-[#f3f5f6]',
)

const primaryActionClass = cn(
  headerActionClass,
  'border-app-accent bg-app-accent text-white hover:bg-[#1d55aa]',
)

const modeTabClass = cn(
  'min-h-[30px] cursor-pointer rounded-[5px] border-0 bg-transparent px-[11px] text-[#4a5159]',
  'aria-selected:bg-white aria-selected:text-[#1f252b] aria-selected:shadow-control',
  'disabled:cursor-default disabled:opacity-50',
)

function saveStatusDotClass(saveState: 'saved' | 'changed' | 'saving' | 'error') {
  return cn(
    'h-[7px] w-[7px] rounded-full',
    saveState === 'saved' && 'bg-[#5f9d72]',
    saveState === 'changed' && 'bg-[#ca8b21]',
    saveState === 'saving' && 'bg-[#3775c9]',
    saveState === 'error' && 'bg-[#c84646]',
  )
}

export function EditorPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [revision, setRevision] = useState(0)
  const [saveState, setSaveState] = useState<'saved' | 'changed' | 'saving' | 'error'>('saved')
  const [assistantBusy, setAssistantBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [viewMode, setViewMode] = useState<'final' | 'preview' | 'html-preview' | 'astra' | 'code'>('final')
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
  const htmlPreview = useQuery({
    queryKey: ['document-html-preview', documentId, revision],
    queryFn: () => exportDocumentHtmlPreview(documentId!),
    enabled: Boolean(documentId && revision > 0 && viewMode === 'html-preview'),
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

  if (query.isLoading) return <main className="grid min-h-[480px] place-content-center text-center">Загрузка документа…</main>
  if (query.isError || !query.data) {
    return <main className="grid min-h-[480px] place-content-center text-center">Не удалось открыть документ.</main>
  }

  const document = query.data
  const saveStatus = {
    saved: 'Все изменения сохранены',
    changed: 'Есть несохранённые изменения',
    saving: 'Сохранение…',
    error: 'Не удалось сохранить',
  }[saveState]

  return (
    <main className="min-h-screen bg-[#e7e9ed] text-app-text">
      <header className="sticky top-0 z-30 grid min-h-16 grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 border-b border-app-border bg-white px-5 py-2 max-[760px]:grid-cols-[36px_minmax(0,1fr)] max-[760px]:pr-3">
        <Link
          className="grid h-9 w-9 place-items-center rounded-control text-[22px] text-[#31363d] no-underline hover:bg-[#f0f2f4]"
          to="/"
          aria-label="К документам"
          title="К документам"
        >
          ←
        </Link>
        <div className="grid min-w-0 justify-items-start">
          <input
            className="w-[min(560px,100%)] overflow-hidden text-ellipsis rounded-[5px] border border-transparent bg-transparent px-1.5 py-[3px] text-base font-semibold leading-tight hover:border-[#b8bec6] hover:bg-white focus:border-[#b8bec6] focus:bg-white focus:outline-none focus-visible:shadow-[0_0_0_3px_rgb(44_105_206_/_16%)]"
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
            className={cn(
              'inline-flex min-h-[18px] items-center gap-1.5 pl-1.5 text-xs text-app-muted',
              saveState === 'error' && 'text-[#a93838]',
            )}
            aria-live="polite"
            title={saveError ?? undefined}
          >
            <span className={saveStatusDotClass(saveState)} aria-hidden="true" />
            {rename.isPending ? 'Сохранение названия…' : saveError ?? saveStatus}
          </span>
        </div>
        <div className="flex items-center gap-2 max-[760px]:col-span-full max-[760px]:justify-end">
          <button
            className={secondaryActionClass}
            type="button"
            disabled={exportPdf.isPending || saveState !== 'saved'}
            title={saveState === 'saved' ? 'Сформировать PDF текущей версии' : 'Дождитесь сохранения изменений'}
            onClick={() => exportPdf.mutate()}
          >
            <span aria-hidden="true">↓</span>
            {exportPdf.isPending ? 'Формирование…' : 'Экспорт PDF'}
          </button>
          <button
            className={primaryActionClass}
            type="button"
            disabled={publication.isPending || saveState !== 'saved'}
            onClick={() => setPublishConfirmationOpen(true)}
          >
            Опубликовать
          </button>
        </div>
      </header>
      {document.status === 'ready' && document.html ? (
        <div
          className={cn(
            'grid min-h-[calc(100vh-64px)] items-start max-[1279px]:grid-cols-[minmax(0,1fr)] max-[1279px]:[&_aside]:fixed max-[1279px]:[&_aside]:bottom-0 max-[1279px]:[&_aside]:right-0 max-[1279px]:[&_aside]:top-16 max-[1279px]:[&_aside]:z-40 max-[1279px]:[&_aside]:max-h-none max-[1279px]:[&_aside]:w-[min(400px,calc(100vw-80px))] max-[1279px]:[&_aside]:shadow-[-12px_0_40px_rgb(25_33_42_/_18%)]',
            viewMode === 'final' && assistantOpen
              ? 'grid-cols-[minmax(0,1fr)_360px]'
              : 'grid-cols-[minmax(0,1fr)]',
          )}
        >
          <section className="min-w-0">
            <nav
              className="sticky top-16 z-[80] flex min-h-11 items-center justify-between border-b border-app-border bg-white px-4 py-[5px] max-[760px]:top-[100px]"
              aria-label="Режим просмотра документа"
            >
              <div className="flex gap-0.5 rounded-[7px] bg-[#eef0f3] p-[3px]" role="tablist" aria-label="Режим документа">
                <button className={modeTabClass} role="tab" type="button" aria-selected={viewMode === 'final'} onClick={() => setViewMode('final')}>
                  Редактор
                </button>
                <button
                  className={modeTabClass}
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
              <div className="flex items-center gap-1.5">
                {viewMode === 'final' && !assistantOpen && (
                  <button
                    className="min-h-[30px] cursor-pointer rounded-[5px] border border-[#d0d5db] bg-transparent px-[11px] text-[#4a5159] hover:bg-[#f3f5f6]"
                    type="button"
                    onClick={() => setAssistantOpen(true)}
                  >
                    Открыть помощника
                  </button>
                )}
                <details className="relative z-[90]">
                  <summary
                    className="grid h-8 w-8 cursor-pointer list-none place-items-center rounded-control hover:bg-[#f0f2f4] [&::-webkit-details-marker]:hidden"
                    aria-label="Диагностические режимы"
                    title="Диагностические режимы"
                  >
                    ⋯
                  </summary>
                  <div className="absolute right-0 top-[calc(100%+6px)] z-[100] grid w-[210px] rounded-[7px] border border-[#d4d8dd] bg-white p-1.5 shadow-popover">
                    <button className="min-h-[34px] rounded-[5px] border-0 bg-transparent px-2.5 text-left hover:bg-[#f1f3f5] disabled:opacity-40" type="button" disabled={!document.astra_html} onClick={() => setViewMode('astra')}>
                      Отображение Astra
                    </button>
                    <button className="min-h-[34px] rounded-[5px] border-0 bg-transparent px-2.5 text-left hover:bg-[#f1f3f5] disabled:opacity-40" type="button" disabled={saveState !== 'saved'} onClick={() => setViewMode('html-preview')}>
                      HTML renderer
                    </button>
                    <button className="min-h-[34px] rounded-[5px] border-0 bg-transparent px-2.5 text-left hover:bg-[#f1f3f5] disabled:opacity-40" type="button" disabled={!document.astra_html} onClick={() => setViewMode('code')}>
                      Исходный HTML Astra
                    </button>
                  </div>
                </details>
              </div>
            </nav>
            {viewMode === 'preview' ? (
              <section className="min-h-[calc(100vh-108px)] overflow-hidden bg-[#34383d]" aria-label="Предпросмотр PDF">
                <div className="flex min-h-11 items-center gap-3 border-b border-[#4b5056] bg-[#25282c] px-4 py-1.5 text-[#eef0f3]">
                  <span className="mr-auto text-xs">Ревизия {revision}</span>
                  <button className="inline-flex min-h-[30px] items-center rounded-control border border-[#676d74] bg-[#34383d] px-2.5 text-[#eef0f3] disabled:opacity-55" type="button" disabled={pdfPreview.isFetching} onClick={() => pdfPreview.refetch()}>
                    {pdfPreview.isFetching ? 'Обновление…' : 'Обновить'}
                  </button>
                  {pdfPreview.data?.url && (
                    <a className="inline-flex min-h-[30px] items-center rounded-control border border-[#676d74] bg-[#34383d] px-2.5 text-[#eef0f3] no-underline" href={pdfPreview.data.url} target="_blank" rel="noreferrer">Открыть отдельно</a>
                  )}
                </div>
                {pdfPreview.isPending ? (
                  <div className="grid min-h-[720px] place-content-center text-white">Формируем точный печатный вид…</div>
                ) : pdfPreview.isError || !pdfPreview.data ? (
                  <div className="grid min-h-[720px] place-content-center text-white">Не удалось сформировать PDF-предпросмотр.</div>
                ) : (
                  <iframe
                    className="block h-[calc(100vh-152px)] min-h-[720px] w-full border-0"
                    src={pdfPreview.data.url}
                    title={`Предпросмотр PDF: ${document.title}`}
                    referrerPolicy="no-referrer"
                  />
                )}
              </section>
            ) : viewMode === 'html-preview' ? (
              <section className="min-h-[calc(100vh-108px)] overflow-hidden bg-[#34383d]" aria-label="HTML-предпросмотр renderer">
                <div className="flex min-h-11 items-center gap-3 border-b border-[#4b5056] bg-[#25282c] px-4 py-1.5 text-[#eef0f3]">
                  <span className="mr-auto text-xs">Renderer HTML · ревизия {revision}</span>
                  <button className="inline-flex min-h-[30px] items-center rounded-control border border-[#676d74] bg-[#34383d] px-2.5 text-[#eef0f3] disabled:opacity-55" type="button" disabled={htmlPreview.isFetching} onClick={() => htmlPreview.refetch()}>
                    {htmlPreview.isFetching ? 'Обновление…' : 'Обновить'}
                  </button>
                  {htmlPreview.data?.url && (
                    <a className="inline-flex min-h-[30px] items-center rounded-control border border-[#676d74] bg-[#34383d] px-2.5 text-[#eef0f3] no-underline" href={htmlPreview.data.url} target="_blank" rel="noreferrer">Открыть отдельно</a>
                  )}
                </div>
                {htmlPreview.isPending ? (
                  <div className="grid min-h-[720px] place-content-center text-white">Готовим HTML через renderer…</div>
                ) : htmlPreview.isError || !htmlPreview.data ? (
                  <div className="grid min-h-[720px] place-content-center text-white">Не удалось сформировать HTML-предпросмотр.</div>
                ) : (
                  <iframe
                    className="block h-[calc(100vh-152px)] min-h-[720px] w-full border-0 bg-white"
                    src={htmlPreview.data.url}
                    title={`HTML-предпросмотр renderer: ${document.title}`}
                    referrerPolicy="no-referrer"
                    sandbox="allow-same-origin"
                  />
                )}
              </section>
            ) : viewMode === 'code' ? (
              <pre className="m-0 max-h-[calc(100vh-108px)] overflow-auto bg-[#111827] p-5 font-mono text-xs leading-[1.55] text-[#d9e2ef] [overflow-wrap:anywhere] whitespace-pre-wrap">{document.astra_html}</pre>
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
        <section className="grid min-h-[480px] place-content-center text-center">
          <h2 className="m-0 mb-2 text-xl font-bold">Документ обрабатывается</h2>
          <p>Страница обновится автоматически после завершения GPT Astra 6.</p>
        </section>
      )}
      {notification && (
        <div className="fixed bottom-6 right-6 z-[100] flex max-w-[420px] items-center gap-4 rounded-[7px] bg-[#262c33] px-3.5 py-3 text-white shadow-[0_10px_32px_rgb(22_28_34_/_24%)]" role="status">
          <span>{notification}</span>
          <button className="cursor-pointer border-0 bg-transparent text-xl text-inherit" type="button" aria-label="Закрыть уведомление" onClick={() => setNotification(null)}>×</button>
        </div>
      )}
      {publishConfirmationOpen && (
        <div className="fixed inset-0 z-[110] grid place-items-center bg-[rgb(25_31_38_/_42%)] p-6" role="presentation" onMouseDown={() => setPublishConfirmationOpen(false)}>
          <section
            className="w-[min(440px,100%)] rounded-panel bg-white p-6 shadow-[0_20px_60px_rgb(20_27_35_/_25%)]"
            role="dialog"
            aria-modal="true"
            aria-labelledby="publish-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 className="m-0 mb-2 text-[19px] font-bold" id="publish-title">Опубликовать документ?</h2>
            <p className="m-0 mb-[22px] leading-normal text-[#5d6670]">Будет опубликована версия {revision} документа «{document.title}».</p>
            <div className="flex justify-end gap-2">
              <button className={secondaryActionClass} type="button" onClick={() => setPublishConfirmationOpen(false)}>Отмена</button>
              <button className={primaryActionClass} type="button" disabled={publication.isPending} onClick={() => publication.mutate()}>
                {publication.isPending ? 'Публикация…' : 'Опубликовать'}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  )
}
