import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { deleteDocument, getDocuments } from '@/entities/document'

import styles from './document-list.module.css'

export function DocumentList() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
    refetchInterval: ({ state }) =>
      state.data?.some((item) => ['uploaded', 'queued', 'processing'].includes(item.status))
        ? 3000
        : false,
  })
  const deletion = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })

  if (query.isLoading) return <p>Загрузка документов…</p>
  if (query.isError) return <p role="alert">Не удалось получить документы.</p>
  if (!query.data?.length) {
    return (
      <section className={styles.empty} aria-labelledby="documents-empty-title">
        <h2 id="documents-empty-title">Документов пока нет</h2>
        <p>Загрузите первый DOCX, чтобы начать обработку.</p>
      </section>
    )
  }

  return (
    <div className={styles.list}>
      {query.data.map((document) => (
        <article className={styles.card} key={document.id}>
          <Link className={styles.cardLink} to={`/documents/${document.id}`}>
            <div>
              <h2>{document.title}</h2>
              <p>{document.source_filename}</p>
            </div>
            <span data-status={document.status}>{document.status}</span>
          </Link>
          <button
            className={styles.deleteButton}
            type="button"
            disabled={deletion.isPending || ['queued', 'processing'].includes(document.status)}
            onClick={() => {
              if (window.confirm(`Удалить документ «${document.title}»?`)) deletion.mutate(document.id)
            }}
          >
            Удалить
          </button>
        </article>
      ))}
    </div>
  )
}
