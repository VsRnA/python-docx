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

import styles from './document-assistant.module.css'

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
    <aside className={styles.panel} aria-label="Помощник по документу">
      <header className={styles.panelHeader}>
        <div className={styles.tabs} role="tablist" aria-label="Панель документа">
          <button type="button" role="tab" aria-selected={activeTab === 'ai'} onClick={() => setActiveTab('ai')}>AI</button>
          <button type="button" role="tab" aria-selected={activeTab === 'versions'} onClick={() => setActiveTab('versions')}>Версии</button>
        </div>
        <button className={styles.closeButton} type="button" aria-label="Закрыть панель" title="Закрыть панель" onClick={onClose}>×</button>
      </header>

      {activeTab === 'ai' ? (
        <div className={styles.tabContent} role="tabpanel">
          <div className={styles.conversation} aria-live="polite">
            {conversation.data?.length ? conversation.data.map((item) => (
              <article className={styles[item.role]} key={item.id}>
                <span>{item.role === 'user' ? 'Вы' : 'AI'}</span>
                <p>{item.content}</p>
              </article>
            )) : (
              <div className={styles.emptyState}>
                <h2>Помощник по документу</h2>
                <p>Опишите результат, который хотите получить. Перед изменением документа вы сможете проверить команду.</p>
              </div>
            )}
          </div>
          <div className={styles.composer}>
            {reviewingInstruction ? (
              <section className={styles.review} aria-labelledby="ai-review-title">
                <span>
                  Область: {contextTitle(selectionContext)}
                </span>
                <h2 id="ai-review-title">Проверьте команду</h2>
                <div className={styles.contextCard}>
                  <strong>{contextTitle(selectionContext)}</strong>
                  <p>{selectionContext.textPreview || 'Контекст не выбран. Команда будет применена ко всему документу.'}</p>
                  <small>
                    {selectionContext.blockIds.length
                      ? `${selectionContext.blockIds.length} блок(ов), ${selectionContext.characterCount} символов`
                      : 'Без выделения'}
                  </small>
                </div>
                <p>{instruction}</p>
                <small>
                  После подтверждения AI изменит текущую версию
                  {selectionContext.blockIds.length ? ' только в выбранной области' : ''}.
                  Результат можно будет отменить через историю версий.
                </small>
                <div>
                  <button type="button" disabled={aiEdit.isPending} onClick={() => setReviewingInstruction(false)}>Изменить</button>
                  <button className={styles.primaryButton} type="button" disabled={!canMutate || aiEdit.isPending} onClick={() => aiEdit.mutate()}>
                    {aiEdit.isPending ? 'Применение…' : 'Подтвердить правку'}
                  </button>
                </div>
              </section>
            ) : (
              <form onSubmit={submit}>
                <div className={styles.quickActions} aria-label="Быстрые команды">
                  {['Сократить текст', 'Исправить стиль', 'Упростить формулировки'].map((prompt) => (
                    <button key={prompt} type="button" onClick={() => setInstruction(prompt)}>{prompt}</button>
                  ))}
                </div>
                <textarea
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
                <div className={styles.contextCard}>
                  <strong>{contextTitle(selectionContext)}</strong>
                  <p>{selectionContext.textPreview || 'Выделите текст в документе, чтобы отправить AI конкретный фрагмент.'}</p>
                  <small>
                    {selectionContext.blockIds.length
                      ? `${selectionContext.blockIds.length} блок(ов), ${selectionContext.characterCount} символов`
                      : 'Сейчас команда применится ко всему документу'}
                  </small>
                </div>
                <p className={styles.scopeHint}>
                  {selectionContext.blockIds.length
                    ? 'AI применит команду к показанному выше контексту.'
                    : 'Без выделения команда применяется ко всему документу.'}
                </p>
                <button className={styles.primaryButton} type="submit" disabled={!canMutate || busy || !instruction.trim()}>
                  Сформировать правку
                </button>
              </form>
            )}
            {!canMutate && <p className={styles.hint}>Команда станет доступна после сохранения документа.</p>}
            {message && <p className={styles.message}>{message}</p>}
            {!reviewingInstruction && (
              <div className={styles.translationAction}>
                <span><strong>Перевод</strong><small>Создаст новую версию документа</small></span>
                <button type="button" disabled={!canMutate || busy} onClick={() => translation.mutate()}>
                  {translation.isPending ? 'Перевод…' : 'На русский'}
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <section className={styles.versionsPanel} role="tabpanel">
          <div className={styles.versionsHeading}>
            <h2>История версий</h2>
            <p>Восстановление создаст новую версию и сохранит историю.</p>
          </div>
          <ol className={styles.versions}>
            {versions.data?.map((version) => (
              <li key={version.revision} data-current={version.revision === revision}>
                <div>
                  <strong>Версия {version.revision}</strong>
                  <span>{version.reason}</span>
                  <time>{new Date(version.created_at).toLocaleString('ru')}</time>
                </div>
                {version.revision === revision ? (
                  <em>Текущая</em>
                ) : (
                  <button type="button" disabled={!canMutate || busy} onClick={() => restore.mutate(version.revision)}>
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
