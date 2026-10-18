import { useState } from 'react'

import { UploadDocument } from '@/features/upload-document'
import { DocumentList, type DocumentListFilters } from '@/widgets/document-list'
import { WorkspaceSidebar } from '@/widgets/workspace-sidebar'

const defaultFilters: DocumentListFilters = {
  search: '',
  status: 'all',
  sort: 'updated',
  date: 'all',
}

function FilterIcon() {
  return <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24"><path d="M4 6h16M7 12h10M10 18h4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" /></svg>
}

export function DocumentsPage() {
  const [filters, setFilters] = useState<DocumentListFilters>(defaultFilters)

  const updateFilters = (patch: Partial<DocumentListFilters>) => setFilters((current) => ({ ...current, ...patch }))

  return (
    <main className="min-h-screen bg-app-bg text-app-text">
      <div className="flex min-h-screen max-[720px]:block">
        <WorkspaceSidebar />
        <section className="min-w-0 flex-1 px-12 py-11 max-[940px]:px-6 max-[940px]:py-8 max-[720px]:px-4 max-[720px]:py-7">
          <div className="mx-auto max-w-[1280px]">
            <h1 className="mb-6 text-[28px] font-bold leading-tight tracking-[-0.045em]">Документы</h1>
            <div className="grid items-start gap-7 min-[940px]:grid-cols-[240px_minmax(0,1fr)]">
              <aside className="sticky top-6 rounded-panel border border-app-border bg-app-panel p-4 shadow-[0_10px_30px_rgb(23_23_23_/_4%)] max-[940px]:static max-[720px]:mb-1" aria-label="Фильтры документов">
                <div className="mb-5 flex items-center justify-between">
                  <h2 className="m-0 text-sm font-bold">Фильтры документов</h2>
                  <span className="text-app-muted"><FilterIcon /></span>
                </div>
                <div className="grid gap-4">
                  <label className="grid gap-2 text-[11px] font-bold text-app-muted">
                    Поиск по названию
                    <input className="min-h-9 rounded-control border border-app-border bg-app-bg px-3 text-sm font-normal text-app-text outline-none placeholder:text-[#a39d96] focus:border-app-accent" value={filters.search} onChange={(event) => updateFilters({ search: event.target.value })} placeholder="Например, договор" />
                  </label>
                  <label className="grid gap-2 border-t border-app-border pt-4 text-[11px] font-bold text-app-muted">
                    Статус
                    <select className="min-h-9 rounded-control border border-app-border bg-app-bg px-3 text-sm font-normal text-app-text" value={filters.status} onChange={(event) => updateFilters({ status: event.target.value })}>
                      <option value="all">Все статусы</option>
                      <option value="ready">Готов</option>
                      <option value="processing">Обрабатывается</option>
                      <option value="processing_failed">Ошибка обработки</option>
                      <option value="archived">Архив</option>
                    </select>
                  </label>
                  <div className="border-t border-app-border pt-4">
                    <span className="mb-2 block text-[11px] font-bold text-app-muted">Дата добавления</span>
                    <div className="flex flex-wrap gap-1.5">
                      {([['all', 'Все даты'], ['today', 'Сегодня'], ['week', 'Неделя'], ['month', 'Месяц']] as const).map(([value, label]) => (
                        <button className={`rounded-[5px] border px-2 py-1.5 text-[11px] ${filters.date === value ? 'border-[#f6bf9b] bg-app-accentSoft text-app-accent' : 'border-app-border bg-white text-app-muted hover:border-app-accent/50'}`} key={value} type="button" onClick={() => updateFilters({ date: value })}>{label}</button>
                      ))}
                    </div>
                  </div>
                  <label className="grid gap-2 border-t border-app-border pt-4 text-[11px] font-bold text-app-muted">
                    Сортировка
                    <select className="min-h-9 rounded-control border border-app-border bg-app-bg px-3 text-sm font-normal text-app-text" value={filters.sort} onChange={(event) => updateFilters({ sort: event.target.value as DocumentListFilters['sort'] })}>
                      <option value="updated">Сначала новые</option>
                      <option value="created">Сначала загруженные</option>
                      <option value="title">По названию</option>
                    </select>
                  </label>
                  <button className="justify-self-start border-0 bg-transparent p-0 text-xs font-semibold text-app-accent hover:underline" type="button" onClick={() => setFilters(defaultFilters)}>Сбросить фильтры</button>
                </div>
                <div className="mt-5 border-t border-app-border pt-5">
                  <UploadDocument />
                </div>
              </aside>
              <section className="min-w-0" aria-label="Список документов">
                <DocumentList filters={filters} />
              </section>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
