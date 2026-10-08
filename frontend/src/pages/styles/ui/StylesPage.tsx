import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { createStyle, getStyles } from '@/entities/style'

const statusLabels = {
  active: 'Активна',
  archived: 'Архив',
} as const

export function StylesPage() {
  const queryClient = useQueryClient()
  const styles = useQuery({ queryKey: ['styles'], queryFn: getStyles })
  const creation = useMutation({
    mutationFn: () => createStyle({ name: 'Новая стилизация', description: 'Черновик визуального стандарта' }),
    onSuccess: (style) => {
      queryClient.invalidateQueries({ queryKey: ['styles'] })
      window.location.href = `/styles/${style.id}`
    },
  })

  return (
    <main className="min-h-screen bg-[#f6f7f9] text-app-text">
      <header className="workbench-header border-b border-app-border bg-white">
        <div className="mx-auto flex min-h-16 w-[min(1240px,calc(100%_-_64px))] items-center justify-between gap-6">
          <Link className="text-lg font-extrabold tracking-[-0.02em] text-app-text no-underline" to="/">Doc Studio</Link>
          <Link className="text-sm font-semibold text-app-muted no-underline hover:text-app-text" to="/">← Документы</Link>
        </div>
      </header>
      <div className="mx-auto w-[min(1120px,calc(100%_-_64px))] py-10 max-[640px]:w-[calc(100%_-_40px)] max-[640px]:py-8">
        <div className="mb-8 flex items-end justify-between gap-6">
          <div>
            <h1 className="m-0 mb-2 text-[32px] font-bold tracking-[-0.025em]">Стилизации</h1>
            <p className="m-0 text-app-muted">Управляйте версиями оформления, которые применяются при обработке документов.</p>
          </div>
          <button className="interactive-lift min-h-10 rounded-control bg-app-accent px-4 py-2.5 text-sm font-bold text-white hover:bg-[#1d55aa] disabled:opacity-50" type="button" disabled={creation.isPending} onClick={() => creation.mutate()}>
            {creation.isPending ? 'Создание…' : 'Создать стилизацию'}
          </button>
        </div>
        {styles.isLoading ? <p className="text-app-muted">Загрузка стилизаций…</p> : styles.isError ? <p role="alert" className="text-app-danger">Не удалось получить стилизации.</p> : !styles.data?.length ? (
          <section className="rounded-control border border-app-border bg-white p-10 text-center">
            <h2 className="m-0 mb-2 text-xl font-bold">Стилизаций пока нет</h2>
            <p className="m-0 text-app-muted">Создайте первый визуальный стандарт для документов.</p>
          </section>
        ) : (
          <div className="grid gap-4 min-[760px]:grid-cols-2">
            {styles.data.map((style, index) => (
              <Link className={`surface-reveal surface-reveal-delay-${Math.min(index + 1, 2)} interactive-lift rounded-control border border-app-border bg-white p-5 text-inherit no-underline transition-shadow hover:shadow-[0_8px_24px_rgb(25_33_42_/_8%)]`} to={`/styles/${style.id}`} key={style.id}>
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="m-0 mb-1 text-lg font-bold">{style.name}</h2>
                    <p className="m-0 text-sm text-app-muted">{style.description || 'Без описания'}</p>
                  </div>
                  <span className="rounded-full border border-app-border bg-app-subtle px-2.5 py-1 text-xs font-bold text-app-muted">{statusLabels[style.status]}</span>
                </div>
                <div className="flex items-center gap-6 text-sm text-app-muted">
                  <span>{style.current_version ? `Версия ${style.current_version.version}` : 'Нет версии'}</span>
                  <span>{style.documents_count} документов</span>
                  <span>{style.versions_count} версий</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
