import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'

import { createStyle, getStyles } from '@/entities/style'
import type { DocumentStyle } from '@/entities/style'
import { queryKeys } from '@/shared/api/queryKeys'
import { WorkspaceSidebar } from '@/widgets/workspace-sidebar'

function promptPreview(style: DocumentStyle) {
  const value = style.current_version?.settings.style_prompt
  if (typeof value !== 'string' || !value.trim()) return 'Промпт пока не задан'
  const compact = value.replace(/\s+/g, ' ').trim()
  return compact.length > 220 ? `${compact.slice(0, 220)}…` : compact
}

function referenceName(style: DocumentStyle) {
  const value = style.current_version?.settings.reference_file
  if (!value || typeof value !== 'object' || !('filename' in value) || typeof value.filename !== 'string') return 'PDF-образец не прикреплён'
  return value.filename
}

export function StylesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const styles = useQuery({ queryKey: queryKeys.styles(), queryFn: getStyles })
  const createMutation = useMutation({
    mutationFn: () => createStyle({ name: name.trim(), description: description.trim() || undefined }),
    onSuccess: (style) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.styles() })
      navigate(`/styles/${style.id}`)
    },
  })

  return (
    <main className="min-h-screen bg-app-bg text-app-text">
      <div className="flex min-h-screen max-[720px]:block">
        <WorkspaceSidebar />
        <section className="min-w-0 flex-1 px-12 py-11 max-[940px]:px-6 max-[940px]:py-8 max-[720px]:px-4 max-[720px]:py-7">
          <div className="mx-auto max-w-[1280px]">
            <div className="mb-6 flex items-center justify-between gap-4">
              <h1 className="m-0 text-[28px] font-bold leading-tight tracking-[-0.045em]">Стили</h1>
              <button className="min-h-10 rounded-control bg-app-accent px-4 text-sm font-bold text-white hover:bg-app-accentHover disabled:opacity-50" type="button" onClick={() => setCreateOpen((value) => !value)}>{createOpen ? 'Отмена' : 'Создать стилизацию'}</button>
            </div>
            {createOpen && <form className="mb-6 grid gap-3 rounded-panel border border-app-border bg-app-panel p-5" onSubmit={(event) => { event.preventDefault(); createMutation.mutate() }}>
              <h2 className="m-0 text-base font-bold">Новая стилизация</h2>
              <label className="grid gap-1 text-sm font-semibold">Название<input className="min-h-10 rounded-control border border-app-border bg-app-bg px-3 font-normal outline-none focus:border-app-accent" value={name} onChange={(event) => setName(event.target.value)} placeholder="Например, Инструкция Villartec A5" required maxLength={255} /></label>
              <label className="grid gap-1 text-sm font-semibold">Описание<span className="text-xs font-normal text-app-muted">Необязательно</span><textarea className="min-h-20 rounded-control border border-app-border bg-app-bg p-3 font-normal outline-none focus:border-app-accent" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} /></label>
              <div className="flex items-center gap-3"><button className="min-h-10 rounded-control bg-app-accent px-4 text-sm font-bold text-white disabled:opacity-50" type="submit" disabled={!name.trim() || createMutation.isPending}>{createMutation.isPending ? 'Создание…' : 'Создать'}</button>{createMutation.isError && <span role="alert" className="text-sm text-app-danger">Не удалось создать стилизацию.</span>}</div>
            </form>}
            {styles.isLoading ? <p className="text-app-muted">Загрузка стилизаций…</p> : styles.isError ? <p role="alert" className="text-app-danger">Не удалось получить стилизации.</p> : !styles.data?.length ? (
              <section className="rounded-panel border border-app-border bg-app-panel p-10 text-center">
                <h2 className="m-0 mb-2 text-lg font-bold">Стилизованных шаблонов пока нет</h2>
                <p className="m-0 text-app-muted">Здесь будут промпты и PDF-образцы для обработки документов.</p>
              </section>
            ) : (
              <div className="grid gap-3 min-[760px]:grid-cols-2">
                {styles.data.map((style) => (
                  <Link className="rounded-panel border border-app-border bg-app-panel p-5 text-inherit no-underline transition-shadow hover:border-app-accent hover:shadow-[0_10px_30px_rgb(23_23_23_/_5%)]" to={`/styles/${style.id}`} key={style.id}>
                    <h2 className="m-0 text-base font-bold">{style.name}</h2>
                    <span className="mb-2 mt-5 block text-[10px] font-bold uppercase tracking-[0.08em] text-app-muted">Промпт</span>
                    <p className="m-0 min-h-[72px] rounded-control border border-app-border bg-app-bg p-3 text-xs leading-relaxed text-app-muted">{promptPreview(style)}</p>
                    <span className="mb-2 mt-5 block text-[10px] font-bold uppercase tracking-[0.08em] text-app-muted">PDF-образец</span>
                    <div className="flex items-center gap-2.5 rounded-control border border-app-border px-3 py-2.5 text-xs text-app-muted"><span className="grid h-7 w-6 place-items-center rounded border border-[#e1c5c5] bg-[#fdf7f7] text-[9px] font-extrabold text-[#b65353]">PDF</span><span className="truncate">{referenceName(style)}</span></div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  )
}
