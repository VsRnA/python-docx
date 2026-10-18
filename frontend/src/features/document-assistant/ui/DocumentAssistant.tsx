import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useEffect, useState } from 'react'

import { acceptDocumentAiEdit, getAiMessages, proposeDocumentAiEdit } from '@/entities/document'
import type { SelectionContext } from '@/entities/document'
import { ApiError } from '@/shared/api/client'
import { queryKeys } from '@/shared/api/queryKeys'
import { cn } from '@/shared/lib/cn'

const primaryButtonClass = cn(
  'min-h-9 cursor-pointer rounded-[7px] border border-app-accent bg-app-accent px-3 font-semibold text-white',
  'hover:bg-app-brandHover disabled:cursor-default disabled:opacity-50',
)
const secondaryButtonClass = 'min-h-8 cursor-pointer rounded-control border border-app-border bg-app-panel px-2.5 disabled:cursor-default disabled:opacity-50'
const contextCardClass = 'grid gap-[5px] rounded-[7px] border border-app-border bg-app-subtle px-2.5 py-[9px]'
const contextTextClass = 'm-0 line-clamp-3 max-h-[58px] overflow-hidden text-xs leading-[1.45] text-app-muted'

interface DocumentAssistantProps {
  documentId: string
  revision: number
  canMutate: boolean
  selectionContext: SelectionContext
  onRevisionChange: (revision: number) => void
  onBusyChange?: (busy: boolean) => void
  onClose?: () => void
  'data-panel'?: string
}

function aiErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Не удалось применить правку. Проверьте соединение и повторите запрос.'
  const detail = typeof error.details === 'object' && error.details && 'detail' in error.details
    ? (error.details as { detail?: unknown }).detail
    : error.details
  const code = typeof detail === 'object' && detail && 'code' in detail
    ? (detail as { code?: unknown }).code
    : undefined
  if (code === 'revision_conflict' || error.status === 409) return 'Документ изменился. Обновите страницу и повторите запрос.'
  if (code === 'selection_not_found') return 'Выбранная область больше не найдена. Выберите её заново.'
  if (code === 'outside_selected_area') return 'AI вышел за пределы выбранной области. Уточните команду.'
  if (code === 'invalid_change_set' || code === 'validation_failed') return 'AI вернул некорректную правку. Уточните команду и повторите.'
  return 'Не удалось применить правку. Запрос сохранен, можно повторить.'
}

function contextTitle(context: SelectionContext) {
  if (context.target.kind === 'image') return context.target.assetFormat ? `Изображение · ${context.target.assetFormat}` : 'Выбранное изображение'
  if (context.target.kind === 'text') return 'Выделенный текст'
  if (context.scope === 'document') return 'Весь документ'
  if (context.scope === 'current-block') return 'Выбранный блок'
  return 'Выделенный фрагмент'
}

function aiInstruction(instruction: string, context: SelectionContext) {
  const selectedText = context.selectedText.trim()
  if (!selectedText) return instruction
  return [
    instruction,
    '',
    'Ограничение: работай только с выделенным фрагментом внутри выбранного блока. Не меняй соседний текст без необходимости.',
    `Выделенный фрагмент: ${selectedText}`,
  ].join('\n')
}

function contextDescription(context: SelectionContext) {
  if (context.target.kind === 'image') {
    const block = context.blocks[0]
    if (context.target.svgIndex !== undefined) {
      return `${block ? `Блок: ${block.textPreview || block.blockType}` : 'Блок изображения'} · встроенный SVG выбран`
    }
    return `${block ? `Блок: ${block.textPreview || block.blockType}` : 'Блок изображения'}${context.target.assetId ? ' · файл подключён' : ' · файл не найден'}`
  }
  if (context.target.kind === 'text') return context.selectedText ? `Текст: ${context.selectedText}` : 'Выделенный текст'
  if (context.scope === 'document') return 'Сейчас команда затронет весь HTML-документ. Кликните по блоку, SVG или изображению, чтобы сузить область.'
  return context.blocks.map((block) => `${block.blockType} · ${block.textPreview || 'без текста'}`).join(' · ')
}

export function DocumentAssistant({
  documentId,
  revision,
  canMutate,
  selectionContext,
  onRevisionChange,
  onBusyChange,
  onClose,
  'data-panel': dataPanel,
}: DocumentAssistantProps) {
  const queryClient = useQueryClient()
  const [instruction, setInstruction] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [messageTone, setMessageTone] = useState<'success' | 'error' | null>(null)
  const [reviewingInstruction, setReviewingInstruction] = useState(false)
  const conversation = useQuery({
    queryKey: queryKeys.aiMessages(documentId),
    queryFn: () => getAiMessages(documentId),
  })
  const refresh = async (nextRevision: number) => {
    onRevisionChange(nextRevision)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.document(documentId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.documentVersions(documentId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.aiMessages(documentId) }),
    ])
  }
  const acceptProposal = useMutation({
    mutationFn: (proposalId: string) => acceptDocumentAiEdit(documentId, proposalId),
    onSuccess: async (result) => {
      setInstruction('')
      setReviewingInstruction(false)
      setMessageTone('success')
      setMessage(result.summary || 'Изменения внесены')
      await refresh(result.revision)
    },
    onError: (error) => {
      setMessageTone('error')
      setMessage(aiErrorMessage(error))
    },
  })
  const aiProposal = useMutation({
    mutationFn: () => proposeDocumentAiEdit(documentId, revision, aiInstruction(instruction, selectionContext), selectionContext.blockIds, selectionContext.target),
    onSuccess: async (result) => {
      setMessage(null)
      setMessageTone(null)
      await acceptProposal.mutateAsync(result.proposal_id)
    },
    onError: (error) => {
      setMessageTone('error')
      setMessage(aiErrorMessage(error))
      void queryClient.invalidateQueries({ queryKey: queryKeys.aiMessages(documentId) })
    },
  })
  const busy = acceptProposal.isPending || aiProposal.isPending
  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])

  const startEdit = () => {
    if (!instruction.trim() || !canMutate || busy) return
    setMessage(null)
    setMessageTone(null)
    setReviewingInstruction(true)
    aiProposal.mutate()
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    startEdit()
  }

  return (
    <aside
      data-panel={dataPanel}
      className="workbench-assistant sticky top-16 grid h-[calc(100vh-64px)] w-[360px] grid-rows-[48px_minmax(0,1fr)] overflow-hidden border-l border-app-border bg-app-panel max-[1279px]:h-[calc(100vh-64px)] max-[1279px]:w-[min(400px,calc(100vw-80px))]"
      aria-label="Помощник по документу"
    >
      <header className="flex items-center justify-between gap-2 border-b border-app-border px-3.5 py-[7px]">
        <strong className="text-[15px]">AI-помощник</strong>
        <button className="min-w-8 cursor-pointer rounded-[5px] border-0 bg-transparent p-0 text-[21px] text-app-muted hover:bg-app-subtle" type="button" aria-label="Закрыть панель" title="Закрыть панель" onClick={onClose}>×</button>
      </header>

      <div className="grid min-h-0 grid-rows-[minmax(0,1fr)_auto]" role="region" aria-label="AI-правки">
        <div className="grid min-h-0 content-start gap-2.5 overflow-auto p-4" aria-live="polite">
          <div className="grid gap-1.5 rounded-[7px] border border-app-border bg-app-subtle px-3 py-2.5">
            <span className="text-[10px] font-bold uppercase tracking-[0.04em] text-app-accent">Область текущей правки</span>
            <strong className="text-[13px] text-app-text">{contextTitle(selectionContext)}</strong>
            {selectionContext.blocks.length ? (
              <div className="grid gap-1">
                {selectionContext.blocks.slice(0, 3).map((block) => (
                  <span className="truncate text-xs text-app-muted" key={block.blockId}>
                    {block.blockType} · {block.textPreview || 'изображение/блок без текста'}
                  </span>
                ))}
                {selectionContext.blocks.length > 3 && <span className="text-[11px] text-app-muted">Ещё блоков: {selectionContext.blocks.length - 3}</span>}
              </div>
            ) : (
              <span className="text-xs leading-normal text-app-muted">{contextDescription(selectionContext)}</span>
            )}
            {selectionContext.blocks.length > 0 && <span className="text-xs leading-normal text-app-muted">{contextDescription(selectionContext)}</span>}
          </div>

          {conversation.data?.length ? conversation.data.map((item) => (
            <article className={cn('rounded-[7px] px-3 py-2.5', item.role === 'user' ? 'ml-8 bg-app-accentSoft' : 'mr-8 bg-app-subtle')} key={item.id}>
              <span className="text-[10px] font-bold uppercase text-app-muted">{item.role === 'user' ? 'Вы' : 'AI'}</span>
              <p className="m-0 mt-1 whitespace-pre-wrap text-[13px] leading-[1.45]">{item.content}</p>
            </article>
          )) : (
            <div className="px-2.5 py-4 text-center">
              <h2 className="m-0 mb-2 text-base font-bold">Что изменить в документе?</h2>
              <p className="m-0 text-[13px] leading-normal text-app-muted">Клик по блоку, SVG или изображению ограничивает правку. Выделение текста ограничивает её ещё точнее.</p>
            </div>
          )}
        </div>

        <div className="border-t border-app-border bg-app-panel p-3.5">
          {reviewingInstruction ? (
            <section aria-labelledby="ai-review-title">
              <div className="mb-2 grid grid-cols-3 gap-1 text-[10px] font-semibold uppercase tracking-[0.03em] text-app-muted" aria-label="Этапы AI-правки">
                <span className="rounded bg-app-accentSoft px-1.5 py-1 text-app-accent">1 · Запрос</span>
                <span className={cn('rounded px-1.5 py-1', busy ? 'bg-app-accentSoft text-app-accent' : 'bg-app-subtle')}>2 · AI обрабатывает</span>
                <span className={cn('rounded px-1.5 py-1', !busy && messageTone === 'success' ? 'bg-app-accentSoft text-app-accent' : 'bg-app-subtle')}>3 · Готово</span>
              </div>
              <h2 className="m-0 mb-2 text-[15px] font-bold" id="ai-review-title">{busy ? 'AI обрабатывает команду' : 'Команда завершена'}</h2>
              <div className={cn(contextCardClass, 'mb-2.5')}>
                <strong className="text-xs text-app-text">AI изменит: {contextTitle(selectionContext)}</strong>
                <p className={contextTextClass}>{selectionContext.textPreview || 'Весь документ'}</p>
              </div>
              <p className="m-0 mb-2 rounded-control bg-app-bg p-2.5 text-[13px] leading-[1.45]"><span className="mb-1 block text-[10px] font-bold uppercase text-app-muted">Команда для AI</span>{instruction}</p>
              {busy && (
                <div className="mt-3 flex items-center gap-2 rounded-[7px] border border-app-border bg-app-subtle px-3 py-2.5 text-xs text-app-muted" role="status" aria-live="polite">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-app-border border-t-app-accent" aria-hidden="true" />
                  <span>{aiProposal.isPending ? 'AI думает над изменением…' : 'AI применяет изменение…'}</span>
                </div>
              )}
              {!busy && messageTone === 'error' && (
                <button className={cn(primaryButtonClass, 'mt-3 w-full')} type="button" disabled={!canMutate} onClick={() => aiProposal.mutate()}>Повторить правку</button>
              )}
              {busy && (
                <button className={secondaryButtonClass} type="button" disabled>Изменить команду</button>
              )}
              {!busy && messageTone === 'success' && (
                <button className={secondaryButtonClass} type="button" onClick={() => setReviewingInstruction(false)}>Новая команда</button>
              )}
            </section>
          ) : (
            <form className="grid gap-2.5" onSubmit={submit}>
              <div className="flex gap-1.5 overflow-x-auto pb-0.5" aria-label="Быстрые команды">
                {['Сократить текст', 'Исправить стиль', 'Упростить формулировки'].map((prompt) => <button className="min-h-7 flex-none cursor-pointer rounded-control border border-app-border bg-app-subtle px-[9px] text-[11px] text-app-muted" key={prompt} type="button" onClick={() => setInstruction(prompt)}>{prompt}</button>)}
              </div>
              <textarea className="min-h-[92px] resize-y rounded-[7px] border border-app-border px-[11px] py-2.5 leading-normal focus:border-app-accent focus:outline focus:outline-[3px] focus:outline-app-accent/15" aria-label="Команда для AI" value={instruction} onChange={(event) => setInstruction(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); startEdit() } }} placeholder="Напишите, что нужно изменить" rows={4} />
              <p className="m-0 text-xs leading-normal text-app-muted">
                {selectionContext.target.kind === 'image'
                  ? selectionContext.target.svgIndex !== undefined
                    ? 'Будет изменён только выбранный SVG внутри HTML. Остальные SVG, текст и блоки останутся без изменений.'
                    : `${selectionContext.target.assetFormat ? `${selectionContext.target.assetFormat}-изображение выбрано. ` : ''}Будет создан новый PNG-файл, исходная картинка останется в истории.`
                  : 'Выбранная область показана выше. Без выбора команда применится ко всему HTML-документу.'}
              </p>
              <button className={primaryButtonClass} type="submit" disabled={!canMutate || busy || !instruction.trim()}>Сформировать правку</button>
            </form>
          )}
          {!canMutate && <p className="m-0 mt-[9px] text-xs leading-normal text-app-muted">Команда станет доступна после сохранения документа.</p>}
          {message && <p className={cn('m-0 mt-[9px] rounded-control px-2.5 py-2 text-xs leading-normal', messageTone === 'error' ? 'bg-app-dangerBg text-app-danger' : 'bg-app-subtle text-app-success')}>{message}</p>}
        </div>
      </div>
    </aside>
  )
}
