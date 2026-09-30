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
  onRevisionChange: (revision: number) => void
  onBusyChange?: (busy: boolean) => void
}

export function DocumentAssistant({
  documentId,
  revision,
  canMutate,
  onRevisionChange,
  onBusyChange,
}: DocumentAssistantProps) {
  const queryClient = useQueryClient()
  const [instruction, setInstruction] = useState('')
  const [message, setMessage] = useState<string | null>(null)
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
    mutationFn: () => editDocumentWithAi(documentId, revision, instruction),
    onSuccess: async (result) => {
      setInstruction('')
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
    if (instruction.trim() && canMutate) aiEdit.mutate()
  }

  const busy = aiEdit.isPending || translation.isPending || restore.isPending
  useEffect(() => onBusyChange?.(busy), [busy, onBusyChange])
  return (
    <aside className={styles.panel} aria-label="Помощник по документу">
      <section>
        <h2>AI-помощник</h2>
        {conversation.data?.length ? (
          <div className={styles.conversation} aria-live="polite">
            {conversation.data.map((item) => (
              <div className={styles[item.role]} key={item.id}>
                <span>{item.role === 'user' ? 'Вы' : 'AI'}</span>
                <p>{item.content}</p>
              </div>
            ))}
          </div>
        ) : null}
        <form onSubmit={submit}>
          <textarea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="Например: сократи введение и сохрани технические термины"
            rows={6}
          />
          <button type="submit" disabled={!canMutate || busy || !instruction.trim()}>
            {aiEdit.isPending ? 'Вношу изменения…' : 'Применить правку'}
          </button>
        </form>
        {!canMutate && <p className={styles.hint}>Дождитесь сохранения текущих изменений.</p>}
        {message && <p className={styles.message}>{message}</p>}
      </section>

      <section>
        <div className={styles.sectionTitle}>
          <h2>Перевод</h2>
          <button type="button" disabled={!canMutate || busy} onClick={() => translation.mutate()}>
            Перевести на русский
          </button>
        </div>
      </section>

      <section>
        <h2>История версий</h2>
        <ol className={styles.versions}>
          {versions.data?.map((version) => (
            <li key={version.revision}>
              <div>
                <strong>Версия {version.revision}</strong>
                <span>{new Date(version.created_at).toLocaleString('ru')}</span>
              </div>
              {version.revision !== revision && (
                <button
                  type="button"
                  disabled={!canMutate || busy}
                  onClick={() => restore.mutate(version.revision)}
                >
                  Восстановить
                </button>
              )}
            </li>
          ))}
        </ol>
      </section>
    </aside>
  )
}
