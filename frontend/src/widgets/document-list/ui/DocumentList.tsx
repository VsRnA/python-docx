import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { deleteDocument, getDocuments } from '@/entities/document'

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
      <section
        className="grid min-h-[360px] place-content-center rounded-2xl border border-app-border bg-app-panel p-12 text-center"
        aria-labelledby="documents-empty-title"
      >
        <h2 id="documents-empty-title" className="m-0 mb-2 text-xl font-bold text-app-text">
          Документов пока нет
        </h2>
        <p className="m-0 text-app-muted">Загрузите первый DOCX, чтобы начать обработку.</p>
      </section>
    )
  }

  return (
    <div className="grid gap-3">
      {query.data.map((document) => (
        <article
          className="flex items-center justify-between rounded-xl border border-app-border bg-app-panel transition-colors hover:border-app-brand"
          key={document.id}
        >
          <Link
            className="flex flex-1 items-center justify-between px-6 py-5 text-inherit no-underline"
            to={`/documents/${document.id}`}
          >
            <div>
              <h2 className="m-0 mb-1 text-[17px] font-bold text-app-text">{document.title}</h2>
              <p className="m-0 text-app-muted">{document.source_filename}</p>
            </div>
            <span
              className="rounded-full border border-app-border bg-app-subtle px-3 py-1 text-xs font-bold uppercase tracking-wide text-app-muted"
              data-status={document.status}
            >
              {document.status}
            </span>
          </Link>
          <button
            className="mr-4 rounded-control border-0 bg-transparent px-2.5 py-2 text-app-danger transition-colors hover:bg-app-dangerBg disabled:opacity-45"
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
