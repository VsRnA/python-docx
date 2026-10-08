import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'

import { deleteDocument, getDocuments } from '@/entities/document'

const statusLabels = {
  uploaded: 'Загружен',
  queued: 'В очереди',
  processing: 'Обрабатывается',
  ready: 'Готов',
  processing_failed: 'Ошибка обработки',
  archived: 'Архив',
  deleted: 'Удалён',
} as const

interface DocumentListProps {
  limit?: number
  compact?: boolean
}

export function DocumentList({ limit, compact = false }: DocumentListProps) {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState<'updated' | 'created' | 'title'>('updated')
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['documents', search, statusFilter, sort],
    queryFn: () => getDocuments({ search, status: statusFilter, sort }),
    refetchInterval: ({ state }) =>
      state.data?.some((item) => ['uploaded', 'queued', 'processing'].includes(item.status))
        ? 3000
        : false,
  })
  const deletion = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })
  const filteredDocuments = useMemo(() => (query.data ?? []).filter((document) => {
    const matchesSearch = `${document.title} ${document.source_filename}`.toLowerCase().includes(search.trim().toLowerCase())
    return matchesSearch && (statusFilter === 'all' || document.status === statusFilter)
  }), [query.data, search, statusFilter])
  const documents = limit ? filteredDocuments.slice(0, limit) : filteredDocuments

  if (query.isLoading) return <div className="grid gap-3" aria-label="Загрузка документов"><div className="skeleton h-16 rounded-xl" /><div className="skeleton h-16 rounded-xl" /><div className="skeleton h-16 rounded-xl" /></div>
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
      {!compact && (
        <div className="mb-1 grid gap-2 min-[700px]:grid-cols-[minmax(0,1fr)_180px_180px]">
          <input className="min-h-10 rounded-control border border-app-border bg-white px-3 text-sm outline-none focus:border-app-accent" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по названию или файлу" aria-label="Поиск документов" />
          <select className="min-h-10 rounded-control border border-app-border bg-white px-3 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Фильтр по статусу">
            <option value="all">Все статусы</option><option value="ready">Готов</option><option value="processing">Обрабатывается</option><option value="processing_failed">Ошибка обработки</option><option value="archived">Архив</option>
          </select>
          <select className="min-h-10 rounded-control border border-app-border bg-white px-3 text-sm" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} aria-label="Сортировка документов">
            <option value="updated">Недавно изменённые</option><option value="created">Недавно загруженные</option><option value="title">По названию</option>
          </select>
        </div>
      )}
      {!documents.length && <p className="rounded-xl border border-dashed border-app-border bg-white p-8 text-center text-sm text-app-muted">По заданным условиям документы не найдены.</p>}
      {documents.map((document) => (
        <article
          className={`surface-reveal flex items-center justify-between rounded-xl border border-app-border bg-app-panel transition-colors hover:border-app-brand ${compact ? 'rounded-lg' : ''}`}
          key={document.id}
        >
          <Link
            className={`flex min-w-0 flex-1 items-center justify-between gap-4 text-inherit no-underline ${compact ? 'px-4 py-3.5' : 'px-6 py-5'}`}
            to={`/documents/${document.id}`}
          >
            <div>
              <h2 className={`m-0 mb-1 truncate font-bold text-app-text ${compact ? 'text-sm' : 'text-[17px]'}`}>{document.title}</h2>
              <p className="m-0 truncate text-sm text-app-muted">{document.source_filename}</p>
            </div>
            <span
              className="shrink-0 rounded-full border border-app-border bg-app-subtle px-3 py-1 text-xs font-bold uppercase tracking-wide text-app-muted"
              data-status={document.status}
            >
              {statusLabels[document.status]}
            </span>
          </Link>
          <button
            className="mr-3 min-h-11 shrink-0 rounded-control border-0 bg-transparent px-2.5 py-2 text-app-danger transition-colors hover:bg-app-dangerBg disabled:opacity-45"
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
