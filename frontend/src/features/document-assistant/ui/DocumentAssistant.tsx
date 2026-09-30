import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FormEvent, useEffect, useState } from 'react'

import {
  editDocumentWithAi,
  getAiMessages,
  getDocumentVersions,
  restoreDocumentVersion,
  translateDocument,
} from '@/entities/document'

import styles from './document-assistant.module.css'

interface DocumentAssistantProps {
  documentId: string
  revision: number
  canMutate: boolean
  selectedBlockIds: string[]
  onRevisionChange: (revision: number) => void
  onBusyChange?: (busy: boolean) => void
  onClose?: () => void
}

export function DocumentAssistant({
  documentId,
  revision,
  canMutate,
  selectedBlockIds,
  onRevisionChange,
  onBusyChange,
  onClose,
}: DocumentAssistantProps) {
  const queryClient = useQueryClient()
  const [instruction, setInstruction] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'ai' | 'versions'>('ai')
  const [reviewingInstruction, setReviewingInstruction] = useState(false)
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
    mutationFn: () => editDocumentWithAi(documentId, revision, instruction, selectedBlockIds),
    onSuccess: async (result) => {
      setInstruction('')
      setReviewingInstruction(false)
      setMessage(result.summary || 'Изменения внесены')
      await refresh(result.revision)
    },
    onError: () => setMessage('Не удалось применить правку. Обновите документ и повторите запрос.'),
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
                  Область: {selectedBlockIds.length ? `${selectedBlockIds.length} выдел. блок(ов)` : 'весь документ'}
                </span>
                <h2 id="ai-review-title">Проверьте команду</h2>
                <p>{instruction}</p>
                <small>
                  После подтверждения AI изменит текущую версию
                  {selectedBlockIds.length ? ' только в выбранной области' : ''}.
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
                <p className={styles.scopeHint}>
                  {selectedBlockIds.length
                    ? `AI применит команду к выделению: ${selectedBlockIds.length} блок(ов).`
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
