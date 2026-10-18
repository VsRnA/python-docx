import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'

import { cancelJob, getDocument, getJob, renameDocument, translateDocument } from '@/entities/document'
import { createProcessingProfile } from '@/entities/style'
import type { SelectionContext } from '@/entities/document'
import { DocumentAssistant } from '@/features/document-assistant'
import { cn } from '@/shared/lib/cn'
import { queryKeys } from '@/shared/api/queryKeys'
import { DocumentEditor, type DocumentEditorHandle } from '@/widgets/document-editor'

const headerActionClass = cn(
  'inline-flex min-h-9 cursor-pointer items-center justify-center gap-[7px] rounded-[7px] border px-[13px] font-semibold',
  'disabled:cursor-default disabled:opacity-50',
)

const secondaryActionClass = cn(
  headerActionClass,
  'border-app-border bg-app-panel text-app-text hover:bg-app-subtle',
)

function processingStage(status: string, profileStatus?: string | null) {
  if (status === 'processing_failed') return 'Обработка остановлена'
  if (profileStatus === 'translating') return 'Переводим документ'
  if (status === 'queued' || status === 'uploaded') return 'Анализируем исходный документ'
  if (status === 'processing') return 'Анализируем документ и собираем HTML'
  return 'Документ готов'
}

function tocLinkLabel(link: HTMLAnchorElement, fallback: string) {
  const title = link.querySelector(
    '.toc__title, .toc-title, .manual-toc__title, [data-toc-title]',
  )
  if (title?.textContent?.trim()) return title.textContent.replace(/\s+/g, ' ').trim()

  const copy = link.cloneNode(true) as HTMLElement
  copy.querySelectorAll(
    '.toc__page, .toc-page, .manual-toc__page, .page-number, [data-toc-page], [data-page]',
  ).forEach((page) => page.remove())

  Array.from(copy.children).forEach((child) => {
    if (/^\s*\d{1,4}\s*$/.test(child.textContent ?? '')) child.remove()
  })

  return copy.textContent?.replace(/\s+/g, ' ').trim() || fallback
}

export function EditorPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [revision, setRevision] = useState(0)
  const [assistantBusy, setAssistantBusy] = useState(false)
  const [title, setTitle] = useState('')
  const [assistantOpen, setAssistantOpen] = useState(() => (
    typeof window !== 'undefined' && window.matchMedia('(min-width: 1280px)').matches
  ))
  const [notification, setNotification] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [translationSource, setTranslationSource] = useState('auto')
  const [translationTarget, setTranslationTarget] = useState('ru')
  const [selectionContext, setSelectionContext] = useState<SelectionContext>({
    scope: 'document',
    blockIds: [],
    blocks: [],
    selectedText: '',
    textPreview: '',
    characterCount: 0,
    target: { kind: 'document' },
  })
  const documentEditorRef = useRef<DocumentEditorHandle>(null)
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.document(documentId),
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
  const jobQuery = useQuery({
    queryKey: queryKeys.job(query.data?.processing_job_id ?? undefined),
    queryFn: () => getJob(query.data!.processing_job_id!),
    enabled: Boolean(query.data?.processing_job_id && ['queued', 'processing'].includes(query.data.status)),
    refetchInterval: 2000,
  })
  const rename = useMutation({
    mutationFn: (nextTitle: string) => renameDocument(documentId!, nextTitle),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.document(documentId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.documents() })
    },
  })
  const translation = useMutation({
    mutationFn: () => translateDocument(documentId!, revision, translationSource, translationTarget),
    onSuccess: async (result) => {
      setRevision(result.revision)
      setMenuOpen(false)
      setNotification('Перевод добавлен как новая версия')
      await queryClient.invalidateQueries({ queryKey: queryKeys.document(documentId) })
    },
    onError: () => setNotification('Не удалось перевести документ. Проверьте настройки перевода.'),
  })
  const cancellation = useMutation({
    mutationFn: (jobId: string) => cancelJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.document(documentId) }),
    onError: () => setNotification('Не удалось отменить обработку. Обновите страницу и повторите попытку.'),
  })
  const retryProcessing = useMutation({
    mutationFn: () => createProcessingProfile(documentId!, {
      style_version_id: query.data!.style_version_id!,
      source_language: query.data?.processing_profile?.source_language ?? undefined,
      target_language: query.data?.processing_profile?.target_language ?? undefined,
      translation_enabled: query.data?.processing_profile?.translation_enabled ?? false,
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.document(documentId) }),
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
    const headingSelector = 'h1, h2, h3, h4, .block.h, .block.sub'
    const candidates = Array.from(parsed.querySelectorAll(headingSelector)).filter((heading) => {
      if (heading.closest('.manual-warning, .manual-toc, script, style')) return false
      return Boolean(heading.textContent?.replace(/\s+/g, ' ').trim())
    })

    const toc = parsed.querySelector(
      '#contents nav.toc, #contents nav[aria-label="Содержание руководства"], '
      + '#contents .manual-toc, .manual-toc',
    )
    const seen = new Set<string>()
    const fromToc = Array.from(toc?.querySelectorAll<HTMLAnchorElement>('a[href^="#"]') ?? [])
      .map((link, index) => {
        const targetId = decodeURIComponent(link.getAttribute('href')?.slice(1) || '')
        const target = parsed.getElementById(targetId)
          || parsed.querySelector(`[data-block-id="${CSS.escape(targetId)}"], [data-b="${CSS.escape(targetId)}"]`)
        const heading = target?.matches(headingSelector)
          ? target
          : target?.querySelector(headingSelector)
        const id = heading?.getAttribute('data-block-id') || heading?.getAttribute('data-b') || heading?.getAttribute('id') || target?.getAttribute('data-block-id') || target?.getAttribute('data-b') || target?.getAttribute('id') || targetId
        const label = tocLinkLabel(link, heading?.textContent?.replace(/\s+/g, ' ').trim() || `Раздел ${index + 1}`)
        return { id: id || null, headingIndex: heading ? Math.max(0, candidates.findIndex((item) => item === heading)) : 0, level: heading?.matches('.block.sub, h2, h3, h4') ? 2 : 1, label }
      })
      .filter((item) => item.id && !seen.has(item.id) && Boolean(seen.add(item.id)))

    if (toc) return fromToc.slice(0, 40)

    return candidates.slice(0, 40).map((heading, index) => ({
      id: heading.getAttribute('data-block-id') || heading.getAttribute('data-b') || heading.getAttribute('id'),
      headingIndex: index,
      level: heading.matches('.block.sub, h2, h3, h4') ? 2 : 1,
      label: heading.textContent?.replace(/\s+/g, ' ').trim() || `Раздел ${index + 1}`,
    }))
  }, [query.data?.html])

  if (query.isLoading) return <main className="grid min-h-[480px] place-content-center text-center">Загрузка документа…</main>
  if (query.isError || !query.data) {
    return <main className="grid min-h-[480px] place-content-center text-center">Не удалось открыть документ.</main>
  }

  const document = query.data

  return (
    <main className="workbench-shell min-h-screen bg-app-shell text-app-text">
      <header className="workbench-header sticky top-0 z-30 grid min-h-16 grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 border-b border-app-border bg-app-panel px-5 py-2 max-[760px]:grid-cols-[36px_minmax(0,1fr)] max-[760px]:pr-3">
        <Link
          className="grid h-9 w-9 place-items-center rounded-control text-[22px] text-app-text no-underline hover:bg-app-subtle"
          to="/"
          aria-label="К документам"
          title="К документам"
        >
          ←
        </Link>
        <div className="grid min-w-0 justify-items-start">
          <input
            className="w-[min(560px,100%)] overflow-hidden text-ellipsis rounded-[5px] border border-transparent bg-transparent px-1.5 py-[3px] text-base font-semibold leading-tight hover:border-app-accent hover:bg-app-panel focus:border-app-accent focus:bg-app-panel focus:outline-none focus-visible:shadow-[0_0_0_3px_rgb(243_111_33_/_16%)]"
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
            'text-app-success',
            )}
            aria-live="polite"
            title="HTML сохраняется как версия после применения AI-правки"
          >
            <span className="h-[7px] w-[7px] rounded-full bg-app-success" aria-hidden="true" />
            {rename.isPending ? 'Сохранение названия…' : 'Готово'}
          </span>
        </div>
        <div className="flex items-center gap-2 max-[760px]:col-span-full max-[760px]:w-full max-[760px]:flex-wrap max-[760px]:justify-end">
          {!assistantOpen && <button className={secondaryActionClass} type="button" onClick={() => setAssistantOpen(true)}>Открыть AI</button>}
          <details className="relative" open={menuOpen} onToggle={(event) => setMenuOpen(event.currentTarget.open)}>
            <summary className={cn(secondaryActionClass, 'cursor-pointer list-none px-3 text-lg leading-none')} aria-label="Меню документа" title="Меню документа">☰</summary>
            <div className="absolute right-0 top-[calc(100%+6px)] z-50 grid w-[min(320px,90vw)] gap-3 rounded-panel border border-app-border bg-white p-3 shadow-popover">
              <button className={secondaryActionClass} type="button" onClick={() => { setMenuOpen(false); setNotification('Выгрузка HTML будет доступна в следующей версии.') }}>Выгрузить HTML</button>
              <div className="grid gap-2 border-t border-app-border pt-3">
                <strong className="text-sm">Перевод документа</strong>
                <label className="grid gap-1 text-xs font-semibold text-app-muted">Исходный язык<select className="min-h-8 rounded-control border border-app-border bg-white px-2 text-sm font-normal" value={translationSource} onChange={(event) => setTranslationSource(event.target.value)}><option value="auto">Определить автоматически</option><option value="ru">Русский</option><option value="en">Английский</option><option value="zh">Китайский</option><option value="de">Немецкий</option></select></label>
                <label className="grid gap-1 text-xs font-semibold text-app-muted">Язык перевода<select className="min-h-8 rounded-control border border-app-border bg-white px-2 text-sm font-normal" value={translationTarget} onChange={(event) => setTranslationTarget(event.target.value)}><option value="ru">Русский</option><option value="en">Английский</option><option value="zh">Китайский</option><option value="de">Немецкий</option><option value="fr">Французский</option></select></label>
                <button className={secondaryActionClass} type="button" disabled={translation.isPending || assistantBusy} onClick={() => translation.mutate()}>{translation.isPending ? 'Перевод…' : 'Запустить перевод'}</button>
              </div>
            </div>
          </details>
        </div>
      </header>
      {document.status === 'ready' && document.html ? (
        <div
          className={cn(
            'grid min-h-[calc(100vh-64px)] items-start max-[1279px]:grid-cols-[minmax(0,1fr)] max-[1279px]:[&_aside[data-panel=assistant]]:fixed max-[1279px]:[&_aside[data-panel=assistant]]:bottom-0 max-[1279px]:[&_aside[data-panel=assistant]]:right-0 max-[1279px]:[&_aside[data-panel=assistant]]:top-16 max-[1279px]:[&_aside[data-panel=assistant]]:z-40 max-[1279px]:[&_aside[data-panel=assistant]]:max-h-none max-[1279px]:[&_aside[data-panel=assistant]]:w-[min(400px,calc(100vw-80px))] max-[1279px]:[&_aside[data-panel=assistant]]:shadow-[-12px_0_40px_rgb(25_33_42_/_18%)] max-[760px]:[&_aside[data-panel=assistant]]:top-auto max-[760px]:[&_aside[data-panel=assistant]]:bottom-0 max-[760px]:[&_aside[data-panel=assistant]]:left-0 max-[760px]:[&_aside[data-panel=assistant]]:h-[min(72vh,640px)] max-[760px]:[&_aside[data-panel=assistant]]:max-h-[72vh] max-[760px]:[&_aside[data-panel=assistant]]:w-full max-[760px]:[&_aside[data-panel=assistant]]:border-l-0 max-[760px]:[&_aside[data-panel=assistant]]:border-t max-[760px]:[&_aside[data-panel=assistant]]:shadow-[0_-12px_40px_rgb(25_33_42_/_18%)]',
            assistantOpen
              ? 'grid-cols-[220px_minmax(0,1fr)_360px]'
              : 'grid-cols-[220px_minmax(0,1fr)]',
          )}
        >
          <aside className="workbench-sidebar sticky top-16 hidden h-[calc(100vh-64px)] overflow-auto border-r border-app-border bg-app-panel p-4 min-[1280px]:block" aria-label="Структура документа">
              <h2 className="m-0 mb-3 text-xs font-bold uppercase tracking-[0.08em] text-app-muted">Структура документа</h2>
              {outline.length ? (
                <nav className="grid gap-1">
                  {outline.map((item) => (
                    <button className={cn('min-h-8 truncate rounded-control border-0 bg-transparent px-2 text-left text-sm text-app-muted hover:bg-app-subtle hover:text-app-text', item.level === 1 && 'font-bold', item.level === 2 && 'pl-4', item.level === 3 && 'pl-6')} key={`${item.id ?? 'heading'}-${item.headingIndex}`} type="button" onClick={() => {
                    documentEditorRef.current?.scrollToHeading(item.id, item.headingIndex, item.label)
                  }}>{item.label}</button>
                  ))}
                </nav>
              ) : <p className="m-0 text-sm leading-relaxed text-app-muted">Заголовки документа появятся здесь.</p>}
          </aside>
          <section className="min-w-0">
            <DocumentEditor
              ref={documentEditorRef}
              html={document.html}
              assetUrls={document.asset_urls}
              onSelectionChange={setSelectionContext}
            />
          </section>
          {assistantOpen && (
            <DocumentAssistant
              data-panel="assistant"
              documentId={document.id}
              revision={revision}
              canMutate={!assistantBusy}
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
          <p className="mx-auto max-w-[520px]">{processingStage(document.status, document.processing_profile?.status)}. {jobQuery.data?.stage ? `Этап: ${jobQuery.data.stage} (${jobQuery.data.progress}%). ` : ''}{document.status === 'processing_failed' ? 'Можно запустить обработку повторно с опубликованной стилизацией.' : 'Страница обновится автоматически после завершения обработки.'}</p>
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
    </main>
  )
}
