import { useQuery } from '@tanstack/react-query'
import { DocumentList } from '@/widgets/document-list'
import { UploadDocument } from '@/features/upload-document'
import { getStyles } from '@/entities/style'

export function DocumentsPage() {
  const styles = useQuery({ queryKey: ['styles'], queryFn: getStyles })
  return (
    <main className="min-h-screen bg-[#f6f7f9] text-app-text">
      <header className="workbench-header border-b border-app-border bg-white">
        <div className="mx-auto flex min-h-16 w-[min(1240px,calc(100%_-_64px))] items-center justify-between gap-6">
          <a className="text-lg font-extrabold tracking-[-0.02em] text-app-text no-underline" href="/">Doc Studio</a>
          <nav className="flex items-center gap-5 text-sm text-app-muted" aria-label="Основная навигация">
            <a className="font-semibold text-app-text no-underline" href="/">Документы</a>
            <button className="border-0 bg-transparent p-0 text-app-muted" type="button">Помощь</button>
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[#e8edf4] text-xs font-bold text-[#385579]" aria-label="Профиль пользователя">РВ</span>
          </nav>
        </div>
      </header>

      <div className="mx-auto w-[min(1240px,calc(100%_-_64px))] py-10 max-[640px]:w-[calc(100%_-_40px)] max-[640px]:py-8">
        <section className="surface-reveal mb-8">
          <h1 className="m-0 mb-2 text-[32px] font-bold leading-tight tracking-[-0.025em]">Документы</h1>
          <p className="m-0 max-w-[620px] text-base text-app-muted">Подготовьте документ к обработке, настройте оформление и откройте готовый результат.</p>
        </section>

        <section className="mb-10 grid gap-4 min-[900px]:grid-cols-2" aria-label="Рабочие разделы">
          <article className="surface-reveal surface-reveal-delay-1 interactive-lift group rounded-control border border-app-border bg-white p-5 transition-shadow hover:shadow-[0_8px_24px_rgb(25_33_42_/_8%)]">
            <h2 className="m-0 mb-2 text-xl font-bold">Настройка дизайна</h2>
            <p className="m-0 mb-6 max-w-[420px] text-sm leading-relaxed text-app-muted">Создайте визуальный стандарт, который будет применяться к документам при обработке и экспорте в PDF.</p>
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-semibold text-app-muted">{styles.data?.filter((style) => style.current_version?.status === 'published').length ?? '—'} опубликованных стилей</span>
              <a className="rounded-control border border-app-border bg-white px-3.5 py-2 text-sm font-bold text-app-accent no-underline hover:bg-app-subtle" href="/styles">Открыть настройки</a>
          </div>
          </article>
          <article className="surface-reveal surface-reveal-delay-2 interactive-lift group rounded-control border border-app-border bg-white p-5 transition-shadow hover:shadow-[0_8px_24px_rgb(25_33_42_/_8%)]">
            <h2 className="m-0 mb-2 text-xl font-bold">Работа с документами</h2>
            <p className="m-0 mb-6 max-w-[420px] text-sm leading-relaxed text-app-muted">Загрузите DOCX, запустите обработку или продолжите работу с уже готовым документом.</p>
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-semibold text-app-muted">Открыть список файлов</span>
              <a className="rounded-control bg-app-accent px-3.5 py-2 text-sm font-bold text-white no-underline hover:bg-[#1d55aa]" href="#documents">Перейти к документам</a>
            </div>
          </article>
        </section>

        <section id="documents" className="grid gap-5 min-[1000px]:grid-cols-[minmax(0,1fr)_360px]">
          <div>
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 className="m-0 mb-1 text-xl font-bold">Последние документы</h2>
                <p className="m-0 text-sm text-app-muted">Откройте документ, чтобы продолжить работу.</p>
              </div>
              <a className="text-sm font-bold text-app-accent no-underline" href="#documents">Все документы →</a>
            </div>
            <DocumentList limit={5} compact />
          </div>
          <aside className="h-fit rounded-control border border-app-border bg-white p-5">
            <h2 className="m-0 mb-2 text-base font-bold">Быстрые действия</h2>
            <p className="m-0 mb-5 text-sm leading-relaxed text-app-muted">Начните новый рабочий процесс с загрузки исходного файла.</p>
            <UploadDocument />
          </aside>
        </section>
      </div>
    </main>
  )
}
