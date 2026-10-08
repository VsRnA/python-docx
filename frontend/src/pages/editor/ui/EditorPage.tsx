import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

import { cancelJob, exportDocumentPdf, getDocument, getDocumentPublications, getDocumentVersion, getDocumentVersions, publishDocument, renameDocument, revokeDocumentPublication } from '@/entities/document'
import { createProcessingProfile } from '@/entities/style'
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
  'min-h-[34px] cursor-pointer rounded-none border-0 border-b-2 border-transparent bg-transparent px-[11px] text-[#5b6570]',
  'aria-selected:border-app-accent aria-selected:bg-transparent aria-selected:text-[#1f252b] aria-selected:shadow-none',
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
  const [viewMode, setViewMode] = useState<'final' | 'preview'>('final')
  const [assistantOpen, setAssistantOpen] = useState(() => (
    typeof window !== 'undefined' && window.matchMedia('(min-width: 1280px)').matches
  ))
  const [notification, setNotification] = useState<string | null>(null)
  const [publishConfirmationOpen, setPublishConfirmationOpen] = useState(false)
  const [compareRevision, setCompareRevision] = useState<number | null>(null)
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
    refetchInterval: ({ state }) => {
      if (!state.data) return false
      const profileInProgress = ['created', 'processing', 'translating'].includes(
        state.data.processing_profile?.status ?? '',
      )
      return ['uploaded', 'queued', 'processing'].includes(state.data.status) || profileInProgress
        ? 3000
        : false
    },
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
  const versions = useQuery({
    queryKey: ['document-versions', documentId],
    queryFn: () => getDocumentVersions(documentId!),
    enabled: Boolean(documentId),
  })
  const comparison = useQuery({
    queryKey: ['document-version', documentId, compareRevision],
    queryFn: () => getDocumentVersion(documentId!, compareRevision!),
    enabled: Boolean(documentId && compareRevision !== null),
  })
  const publications = useQuery({ queryKey: ['publications', documentId], queryFn: () => getDocumentPublications(documentId!), enabled: Boolean(documentId) })
  const revokePublication = useMutation({
    mutationFn: (publicationId: string) => revokeDocumentPublication(documentId!, publicationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['publications', documentId] }),
    onError: () => setNotification('Не удалось отозвать публикацию.'),
  })
  const cancellation = useMutation({
    mutationFn: (jobId: string) => cancelJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['document', documentId] }),
    onError: () => setNotification('Не удалось отменить обработку. Обновите страницу и повторите попытку.'),
  })
  const retryProcessing = useMutation({
    mutationFn: () => createProcessingProfile(documentId!, {
      style_version_id: query.data!.style_version_id!,
      source_language: query.data?.processing_profile?.source_language ?? undefined,
      target_language: query.data?.processing_profile?.target_language ?? undefined,
      translation_enabled: query.data?.processing_profile?.translation_enabled ?? false,
      glossary_version_id: query.data?.processing_profile?.glossary_version_id ?? undefined,
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['document', documentId] }),
    onError: () => setNotification('Не удалось повторить обработку. Проверьте, что версия стилизации ещё опубликована.'),
  })

  useEffect(() => {
    if (query.data) {
      setRevision(query.data.current_revision)
      setTitle(query.data.title)
    }
  }, [query.data])

  const outline = useMemo(() => {
    if (!query.data?.html || typeof DOMParser === 'undefined') return []
    const parsed = new DOMParser().parseFromString(query.data.html, 'text/html')
    return Array.from(parsed.querySelectorAll('h1.manual-heading--h1, h2.manual-heading--h2, h3.manual-heading--h3'))
      .filter((heading) => !heading.closest('.manual-warning, .manual-note, .manual-header, .manual-cover, .manual-toc'))
      .filter((heading) => !/^(?:warning|caution|danger|note|important|notice|внимание|предупреждение)\s*[:!]?$/i.test(heading.textContent?.trim() ?? ''))
      .slice(0, 40)
      .map((heading, index) => ({
        id: heading.getAttribute('data-block-id') || `outline-${index}`,
        level: Number(heading.tagName.slice(1)),
        label: heading.textContent?.trim() || `Раздел ${index + 1}`,
      }))
  }, [query.data?.html])

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
    <main className="workbench-shell min-h-screen bg-[#e9edf1] text-app-text">
      <header className="workbench-header sticky top-0 z-30 grid min-h-16 grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 border-b border-app-border bg-white px-5 py-2 max-[760px]:grid-cols-[36px_minmax(0,1fr)] max-[760px]:pr-3">
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
            <span className={cn(saveStatusDotClass(saveState), saveState === 'saving' && 'status-pulse')} aria-hidden="true" />
            {rename.isPending ? 'Сохранение названия…' : saveError ?? saveStatus}
          </span>
        </div>
        <div className="flex items-center gap-2 max-[760px]:col-span-full max-[760px]:w-full max-[760px]:flex-wrap max-[760px]:justify-end">
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
          <button className={secondaryActionClass} type="button" onClick={() => setCompareRevision(revision > 1 ? revision - 1 : null)} disabled={revision < 2}>Сравнить версии</button>
          <details className="relative"><summary className={cn(secondaryActionClass, 'cursor-pointer list-none')}>Публикации</summary><div className="absolute right-0 top-[calc(100%+6px)] z-50 grid max-h-[60vh] w-[min(420px,90vw)] gap-2 overflow-auto rounded-panel border border-app-border bg-white p-3 shadow-popover">{publications.isPending ? <p className="m-0 text-sm">Загрузка…</p> : publications.data?.length ? publications.data.map((item) => <div className="flex items-center justify-between gap-3 rounded-control border border-app-border p-2.5 text-sm" key={item.id}><div><strong>Редакция v{item.revision}</strong><div className="text-xs text-app-muted">{item.revoked_at ? 'Отозвана' : new Date(item.created_at).toLocaleString()}</div></div>{item.revoked_at ? <span className="text-xs text-app-muted">Недоступна</span> : <div className="flex gap-2"><a className="text-app-accent" href={item.url} target="_blank" rel="noreferrer">Открыть</a><button className="text-app-danger" type="button" disabled={revokePublication.isPending} onClick={() => revokePublication.mutate(item.id)}>Отозвать</button></div>}</div>) : <p className="m-0 text-sm text-app-muted">Публикаций пока нет.</p>}</div></details>
        </div>
      </header>
      {document.status === 'ready' && document.html ? (
        <div
          className={cn(
            'grid min-h-[calc(100vh-64px)] items-start max-[1279px]:grid-cols-[minmax(0,1fr)] max-[1279px]:[&_aside[data-panel=assistant]]:fixed max-[1279px]:[&_aside[data-panel=assistant]]:bottom-0 max-[1279px]:[&_aside[data-panel=assistant]]:right-0 max-[1279px]:[&_aside[data-panel=assistant]]:top-16 max-[1279px]:[&_aside[data-panel=assistant]]:z-40 max-[1279px]:[&_aside[data-panel=assistant]]:max-h-none max-[1279px]:[&_aside[data-panel=assistant]]:w-[min(400px,calc(100vw-80px))] max-[1279px]:[&_aside[data-panel=assistant]]:shadow-[-12px_0_40px_rgb(25_33_42_/_18%)] max-[760px]:[&_aside[data-panel=assistant]]:top-auto max-[760px]:[&_aside[data-panel=assistant]]:bottom-0 max-[760px]:[&_aside[data-panel=assistant]]:left-0 max-[760px]:[&_aside[data-panel=assistant]]:h-[min(72vh,640px)] max-[760px]:[&_aside[data-panel=assistant]]:max-h-[72vh] max-[760px]:[&_aside[data-panel=assistant]]:w-full max-[760px]:[&_aside[data-panel=assistant]]:border-l-0 max-[760px]:[&_aside[data-panel=assistant]]:border-t max-[760px]:[&_aside[data-panel=assistant]]:shadow-[0_-12px_40px_rgb(25_33_42_/_18%)]',
            viewMode === 'final' && assistantOpen
              ? 'grid-cols-[220px_minmax(0,1fr)_360px]'
              : 'grid-cols-[220px_minmax(0,1fr)]',
          )}
        >
          {viewMode === 'final' && (
            <aside className="workbench-sidebar sticky top-16 hidden h-[calc(100vh-64px)] overflow-auto border-r border-app-border bg-white p-4 min-[1280px]:block" aria-label="Структура документа">
              <h2 className="m-0 mb-3 text-xs font-bold uppercase tracking-[0.08em] text-app-muted">Структура документа</h2>
              {outline.length ? (
                <nav className="grid gap-1">
                  {outline.map((item) => (
                    <button className={cn('min-h-8 truncate rounded-control border-0 bg-transparent px-2 text-left text-sm text-[#4b5662] hover:bg-[#f1f3f5] hover:text-app-text', item.level === 1 && 'font-bold', item.level === 2 && 'pl-4', item.level === 3 && 'pl-6')} key={item.id} type="button" onClick={() => {
                      const target = window.document.querySelector(`[data-block-id="${CSS.escape(item.id)}"]`)
                      target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    }}>{item.label}</button>
                  ))}
                </nav>
              ) : <p className="m-0 text-sm leading-relaxed text-app-muted">Заголовки документа появятся здесь.</p>}
            </aside>
          )}
          <section className="min-w-0">
            <nav
              className="workbench-modebar sticky top-16 z-[80] flex min-h-11 items-center justify-between border-b border-app-border bg-white px-4 py-[5px] max-[760px]:top-[100px]"
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
            ) : (
              <DocumentEditor
                documentId={document.id}
                revision={document.current_revision}
                html={document.html}
                assetUrls={document.asset_urls}
                styleSettings={document.style_settings ?? {}}
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
              data-panel="assistant"
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
          <h2 className="m-0 mb-2 text-xl font-bold">{document.status === 'processing_failed' ? 'Обработка остановлена' : 'Документ обрабатывается'}</h2>
          <p>{document.status === 'processing_failed' ? 'Можно запустить обработку повторно с опубликованной стилизацией.' : 'Страница обновится автоматически после завершения обработки.'}</p>
          {document.status === 'processing_failed' && document.style_version_id && <button className={secondaryActionClass} type="button" disabled={retryProcessing.isPending} onClick={() => retryProcessing.mutate()}>{retryProcessing.isPending ? 'Запуск…' : 'Повторить обработку'}</button>}
          {['queued', 'processing'].includes(document.status) && document.processing_job_id && <button className={secondaryActionClass} type="button" disabled={cancellation.isPending} onClick={() => cancellation.mutate(document.processing_job_id!)}>{cancellation.isPending ? 'Отмена…' : 'Отменить обработку'}</button>}
        </section>
      )}
      {notification && (
        <div className="fixed bottom-6 right-6 z-[100] flex max-w-[420px] items-center gap-4 rounded-[7px] bg-[#262c33] px-3.5 py-3 text-white shadow-[0_10px_32px_rgb(22_28_34_/_24%)]" role="status">
          <span>{notification}</span>
          <button className="cursor-pointer border-0 bg-transparent text-xl text-inherit" type="button" aria-label="Закрыть уведомление" onClick={() => setNotification(null)}>×</button>
        </div>
      )}
      {compareRevision !== null && (
        <div className="fixed inset-0 z-[105] grid place-items-center bg-[rgb(25_31_38_/_42%)] p-4" role="presentation" onMouseDown={() => setCompareRevision(null)}>
          <section className="grid max-h-[90vh] w-[min(1100px,100%)] gap-4 overflow-auto rounded-panel bg-white p-5 shadow-popover" role="dialog" aria-modal="true" aria-labelledby="compare-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="m-0 text-xl font-bold" id="compare-title">Сравнение редакций</h2><div className="flex items-center gap-2"><label className="text-sm">Редакция для сравнения <select className="ml-2 min-h-9 rounded-control border border-app-border bg-white px-2" value={compareRevision} onChange={(event) => setCompareRevision(Number(event.target.value))}>{(versions.data ?? []).filter((item) => item.revision !== revision).map((item) => <option key={item.revision} value={item.revision}>v{item.revision} · {item.reason}</option>)}</select></label><span className="text-sm text-app-muted">Текущая v{revision}</span><button className={secondaryActionClass} type="button" onClick={() => setCompareRevision(null)}>Закрыть</button></div></div>
            {comparison.isPending ? <p>Загружаем редакцию…</p> : comparison.isError || !comparison.data ? <p role="alert">Не удалось загрузить выбранную редакцию.</p> : <div className="grid gap-4 min-[760px]:grid-cols-2"><article className="min-w-0 rounded-xl border border-app-border p-4"><h3 className="m-0 mb-3 text-base font-bold">Редакция v{compareRevision}</h3><pre className="m-0 max-h-[65vh] overflow-auto whitespace-pre-wrap text-sm">{(() => { const parsed = new DOMParser().parseFromString(comparison.data.html, 'text/html'); return parsed.body.textContent?.replace(/\s+/g, ' ').trim() ?? '' })()}</pre></article><article className="min-w-0 rounded-xl border border-app-border p-4"><h3 className="m-0 mb-3 text-base font-bold">Текущая v{revision}</h3><pre className="m-0 max-h-[65vh] overflow-auto whitespace-pre-wrap text-sm">{(() => { const parsed = new DOMParser().parseFromString(document.html ?? '', 'text/html'); return parsed.body.textContent?.replace(/\s+/g, ' ').trim() ?? '' })()}</pre></article></div>}
          </section>
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
