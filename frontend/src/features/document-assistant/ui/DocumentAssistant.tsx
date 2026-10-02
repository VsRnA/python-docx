import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useEffect, useRef, useState } from 'react'

import {
  editDocumentWithAi,
  getAiMessages,
  getDocument,
  getDocumentVersions,
  restoreDocumentVersion,
  translateDocument,
} from '@/entities/document'
import type { SelectionContext } from '@/entities/document'
import { ApiError } from '@/shared/api/client'
import { cn } from '@/shared/lib/cn'

const tabClass = cn(
  'min-w-8 cursor-pointer rounded-[5px] border-0 bg-transparent px-2.5 text-app-muted',
  'aria-selected:bg-[#edf2f8] aria-selected:font-semibold aria-selected:text-[#1f252b]',
)

const primaryButtonClass = cn(
  'min-h-9 cursor-pointer rounded-[7px] border border-app-accent bg-app-accent px-3 font-semibold text-white',
  'hover:bg-[#1d55aa] disabled:cursor-default disabled:opacity-50',
)

const secondaryButtonClass = 'min-h-8 cursor-pointer rounded-control border border-[#bbc2ca] bg-white px-2.5 disabled:cursor-default disabled:opacity-50'

const contextCardClass = 'grid gap-[5px] rounded-[7px] border border-[#dce4ef] bg-[#f7f9fc] px-2.5 py-[9px]'
const contextTextClass = 'm-0 line-clamp-3 max-h-[58px] overflow-hidden text-xs leading-[1.45] text-[#4c5661]'

interface DocumentAssistantProps {
  documentId: string
  revision: number
  canMutate: boolean
  selectionContext: SelectionContext
  onRevisionChange: (revision: number) => void
  onAppliedBlocks?: (blockIds: string[]) => void
  onBusyChange?: (busy: boolean) => void
  onClose?: () => void
}

function aiErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Не удалось применить правку. Проверьте соединение и повторите запрос.'
  const detail = typeof error.details === 'object' && error.details && 'detail' in error.details
    ? (error.details as { detail?: unknown }).detail
    : error.details
  const code = typeof detail === 'object' && detail && 'code' in detail
    ? (detail as { code?: unknown }).code
    : undefined
  const message = typeof detail === 'object' && detail && 'message' in detail
    ? (detail as { message?: unknown }).message
    : typeof detail === 'string' ? detail : undefined

  if (code === 'revision_conflict') return 'Документ изменился после подготовки команды. Обновите документ и повторите запрос.'
  if (code === 'selection_not_found') return 'Выбранная область больше не найдена. Выберите текст заново и повторите запрос.'
  if (code === 'outside_selected_area') return 'AI попытался изменить текст вне выбранной области. Запрос сохранен, можно уточнить команду и повторить.'
  if (code === 'invalid_change_set') return 'AI вернул некорректную правку. Запрос сохранен, попробуйте повторить или сузить область.'
  if (code === 'validation_failed') return 'Правка нарушила структуру документа. Запрос сохранен, попробуйте более точную команду.'
  if (error.status === 409) return 'Документ изменился параллельно. Обновите документ и повторите запрос.'
  if (error.status === 422 && typeof message === 'string') return message
  return 'Не удалось применить правку. Запрос сохранен, можно повторить.'
}

function contextTitle(context: SelectionContext) {
  if (context.scope === 'document') return 'Весь документ'
  if (context.scope === 'current-block') return 'Текущий блок'
  return 'Выделенный текст'
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

function isRevisionConflict(error: unknown) {
  if (!(error instanceof ApiError)) return false
  const detail = typeof error.details === 'object' && error.details && 'detail' in error.details
    ? (error.details as { detail?: unknown }).detail
    : error.details
  const code = typeof detail === 'object' && detail && 'code' in detail
    ? (detail as { code?: unknown }).code
    : undefined
  return error.status === 409 || code === 'revision_conflict'
}

export function DocumentAssistant({
  documentId,
  revision,
  canMutate,
  selectionContext,
  onRevisionChange,
  onAppliedBlocks,
  onBusyChange,
  onClose,
}: DocumentAssistantProps) {
  const queryClient = useQueryClient()
  const [instruction, setInstruction] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'ai' | 'versions'>('ai')
  const [reviewingInstruction, setReviewingInstruction] = useState(false)
  const pendingBlockIdsRef = useRef<string[]>([])
  const retryingConflictRef = useRef(false)
  const versions = useQuery({
    queryKey: ['document-versions', documentId, revision],
    queryFn: () => getDocumentVersions(documentId),
  })
  const conversation = useQuery({
    queryKey: ['document-ai-messages', documentId, revision],
    queryFn: () => getAiMessages(documentId),
  })
  const refresh = async (nextRevision: number) => {
    onRevisionChange(nextRevision)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['document', documentId] }),
      queryClient.invalidateQueries({ queryKey: ['document-versions', documentId] }),
      queryClient.invalidateQueries({ queryKey: ['document-ai-messages', documentId] }),
    ])
  }
  const aiEdit = useMutation({
    mutationFn: async () => {
      pendingBlockIdsRef.current = selectionContext.blockIds
      const requestInstruction = aiInstruction(instruction, selectionContext)
      try {
        retryingConflictRef.current = false
        return await editDocumentWithAi(documentId, revision, requestInstruction, pendingBlockIdsRef.current)
      } catch (error) {
        if (!isRevisionConflict(error)) throw error
        retryingConflictRef.current = true
        const latest = await queryClient.fetchQuery({
          queryKey: ['document', documentId],
          queryFn: () => getDocument(documentId),
          staleTime: 0,
        })
        onRevisionChange(latest.current_revision)
        return editDocumentWithAi(documentId, latest.current_revision, requestInstruction, pendingBlockIdsRef.current)
      }
    },
    onSuccess: async (result) => {
      setInstruction('')
      setReviewingInstruction(false)
      setMessage(retryingConflictRef.current
        ? result.summary || 'Изменения внесены после обновления версии документа'
        : result.summary || 'Изменения внесены')
      onAppliedBlocks?.(pendingBlockIdsRef.current)
      await refresh(result.revision)
    },
    onError: (error) => setMessage(aiErrorMessage(error)),
  })
  const translation = useMutation({
    mutationFn: () => translateDocument(documentId, revision, 'auto', 'ru'),
    onSuccess: async (result) => {
      setMessage('Перевод добавлен как новая версия')
      await refresh(result.revision)
    },
    onError: () => setMessage('Не удалось перевести документ.'),
  })
  const restore = useMutation({
    mutationFn: (sourceRevision: number) => restoreDocumentVersion(documentId, revision, sourceRevision),
    onSuccess: async (result) => {
      setMessage('Версия восстановлена')
      await refresh(result.revision)
    },
    onError: () => setMessage('Не удалось восстановить версию.'),
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (instruction.trim() && canMutate) setReviewingInstruction(true)
  }

  const busy = aiEdit.isPending || translation.isPending || restore.isPending
  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])
  return (
    <aside
      className="sticky top-16 grid h-[calc(100vh-64px)] w-[360px] grid-rows-[48px_minmax(0,1fr)] overflow-hidden border-l border-[#d6dae0] bg-white max-[1279px]:h-[calc(100vh-64px)] max-[1279px]:w-[min(400px,calc(100vw-80px))]"
      aria-label="Помощник по документу"
    >
      <header className="flex items-center justify-between gap-2 border-b border-[#e0e3e7] py-[7px] pl-3.5 pr-2.5">
        <div className="flex h-[34px] gap-0.5" role="tablist" aria-label="Панель документа">
          <button className={tabClass} type="button" role="tab" aria-selected={activeTab === 'ai'} onClick={() => setActiveTab('ai')}>AI</button>
          <button className={tabClass} type="button" role="tab" aria-selected={activeTab === 'versions'} onClick={() => setActiveTab('versions')}>Версии</button>
        </div>
        <button className="min-w-8 cursor-pointer rounded-[5px] border-0 bg-transparent p-0 text-[21px] text-app-muted hover:bg-[#f0f2f4]" type="button" aria-label="Закрыть панель" title="Закрыть панель" onClick={onClose}>×</button>
      </header>

      {activeTab === 'ai' ? (
        <div className="grid min-h-0 grid-rows-[minmax(0,1fr)_auto]" role="tabpanel">
          <div className="grid min-h-0 content-start gap-2.5 overflow-auto p-4" aria-live="polite">
            {conversation.data?.length ? conversation.data.map((item) => (
              <article
                className={cn(
                  'rounded-[7px] px-3 py-2.5',
                  item.role === 'user' ? 'ml-8 bg-[#eaf2ff]' : 'mr-8 bg-[#f0f2f4]',
                )}
                key={item.id}
              >
                <span className="text-[10px] font-bold uppercase text-[#69727c]">{item.role === 'user' ? 'Вы' : 'AI'}</span>
                <p className="m-0 mt-1 whitespace-pre-wrap text-[13px] leading-[1.45]">{item.content}</p>
              </article>
            )) : (
              <div className="px-2.5 py-6 text-center">
                <h2 className="m-0 mb-2 text-base font-bold">Помощник по документу</h2>
                <p className="m-0 text-[13px] leading-normal text-app-muted">Опишите результат, который хотите получить. Перед изменением документа вы сможете проверить команду.</p>
              </div>
            )}
          </div>
          <div className="border-t border-[#e0e3e7] bg-white p-3.5">
            {reviewingInstruction ? (
              <section aria-labelledby="ai-review-title">
                <span className="mb-2 inline-flex rounded px-[7px] py-1 text-[11px] text-[#48515a] bg-[#edf0f3]">
                  Область: {contextTitle(selectionContext)}
                </span>
                <h2 className="m-0 mb-2 text-[15px] font-bold" id="ai-review-title">Проверьте команду</h2>
                <div className={cn(contextCardClass, 'mb-2.5')}>
                  <strong className="text-xs text-[#313941]">{contextTitle(selectionContext)}</strong>
                  <p className={contextTextClass}>{selectionContext.textPreview || 'Контекст не выбран. Команда будет применена ко всему документу.'}</p>
                  <small className="text-[11px] text-[#747d86]">
                    {selectionContext.blockIds.length
                      ? `${selectionContext.blockIds.length} блок(ов), ${selectionContext.characterCount} символов`
                      : 'Без выделения'}
                  </small>
                </div>
                <p className="m-0 mb-2 rounded-control bg-[#f5f6f7] p-2.5 text-[13px] leading-[1.45]">{instruction}</p>
                <small className="block leading-normal text-[#69727b]">
                  После подтверждения AI изменит текущую версию
                  {selectionContext.blockIds.length ? ' только в выбранной области' : ''}.
                  Результат можно будет отменить через историю версий.
                </small>
                <div className="mt-3.5 flex justify-end gap-2">
                  <button className={secondaryButtonClass} type="button" disabled={aiEdit.isPending} onClick={() => setReviewingInstruction(false)}>Изменить</button>
                  <button className={primaryButtonClass} type="button" disabled={!canMutate || aiEdit.isPending} onClick={() => aiEdit.mutate()}>
                    {aiEdit.isPending ? 'Применение…' : 'Подтвердить правку'}
                  </button>
                </div>
              </section>
            ) : (
              <form className="grid gap-2.5" onSubmit={submit}>
                <div className="flex gap-1.5 overflow-x-auto pb-0.5" aria-label="Быстрые команды">
                  {['Сократить текст', 'Исправить стиль', 'Упростить формулировки'].map((prompt) => (
                    <button className="min-h-7 flex-none cursor-pointer rounded-control border border-[#e0e3e7] bg-[#f4f5f6] px-[9px] text-[11px] text-[#505962]" key={prompt} type="button" onClick={() => setInstruction(prompt)}>{prompt}</button>
                  ))}
                </div>
                <textarea
                  className="min-h-[92px] resize-y rounded-[7px] border border-[#bbc2ca] px-[11px] py-2.5 leading-normal focus:border-[#3470c5] focus:outline focus:outline-[3px] focus:outline-[#3470c5]/15"
                  aria-label="Команда для AI"
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  onKeyDown={(event) => {
                    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter' && instruction.trim() && canMutate) {
                      event.preventDefault()
                      setReviewingInstruction(true)
                    }
                  }}
                  placeholder="Напишите, что нужно изменить"
                  rows={4}
                />
                <div className={contextCardClass}>
                  <strong className="text-xs text-[#313941]">{contextTitle(selectionContext)}</strong>
                  <p className={contextTextClass}>{selectionContext.textPreview || 'Выделите текст в документе, чтобы отправить AI конкретный фрагмент.'}</p>
                  <small className="text-[11px] text-[#747d86]">
                    {selectionContext.blockIds.length
                      ? `${selectionContext.blockIds.length} блок(ов), ${selectionContext.characterCount} символов`
                      : 'Сейчас команда применится ко всему документу'}
                  </small>
                </div>
                <p className="m-0 mt-[-2px] text-xs leading-normal text-app-muted">
                  {selectionContext.blockIds.length
                    ? 'AI применит команду к показанному выше контексту.'
                    : 'Без выделения команда применяется ко всему документу.'}
                </p>
                <button className={primaryButtonClass} type="submit" disabled={!canMutate || busy || !instruction.trim()}>
                  Сформировать правку
                </button>
              </form>
            )}
            {!canMutate && <p className="m-0 mt-[9px] text-xs leading-normal text-app-muted">Команда станет доступна после сохранения документа.</p>}
            {message && <p className="m-0 mt-[9px] rounded-control bg-[#f0f6ed] px-2.5 py-2 text-xs leading-normal text-app-muted">{message}</p>}
            {!reviewingInstruction && (
              <div className="mt-3 flex items-center justify-between gap-2 border-t border-[#e5e7ea] pt-3">
                <span className="grid gap-0.5 text-xs"><strong>Перевод</strong><small className="text-[#747d86]">Создаст новую версию документа</small></span>
                <button className={secondaryButtonClass} type="button" disabled={!canMutate || busy} onClick={() => translation.mutate()}>
                  {translation.isPending ? 'Перевод…' : 'На русский'}
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <section className="min-h-0 overflow-auto px-4 pb-5" role="tabpanel">
          <div className="sticky top-0 z-20 bg-white pb-3 pt-[18px]">
            <h2 className="m-0 mb-[5px] text-[15px] font-bold">История версий</h2>
            <p className="m-0 text-xs leading-normal text-[#6c747d]">Восстановление создаст новую версию и сохранит историю.</p>
          </div>
          <ol className="m-0 grid list-none gap-0 p-0">
            {versions.data?.map((version) => (
              <li
                className="flex items-center justify-between gap-2.5 border-b border-[#e8eaed] py-[13px] data-[current=true]:bg-[#f4f7fb] data-[current=true]:px-[9px]"
                key={version.revision}
                data-current={version.revision === revision}
              >
                <div className="grid min-w-0 gap-0.5">
                  <strong className="text-[13px]">Версия {version.revision}</strong>
                  <span className="overflow-hidden text-ellipsis whitespace-nowrap text-[11px] text-[#747d86]">{version.reason}</span>
                  <time className="overflow-hidden text-ellipsis whitespace-nowrap text-[11px] text-[#747d86]">{new Date(version.created_at).toLocaleString('ru')}</time>
                </div>
                {version.revision === revision ? (
                  <em className="text-[11px] font-semibold not-italic text-[#28643b]">Текущая</em>
                ) : (
                  <button className={secondaryButtonClass} type="button" disabled={!canMutate || busy} onClick={() => restore.mutate(version.revision)}>
                    Восстановить
                  </button>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}
    </aside>
  )
}
