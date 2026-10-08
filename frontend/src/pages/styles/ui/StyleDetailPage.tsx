import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'

import { archiveStyle, createStyleVersion, duplicateStyle, getStyle, previewStyleVersion, publishStyleVersion, updateStyleVersion, uploadStyleReference, validateStyleVersion } from '@/entities/style'

export function StyleDetailPage() {
  const { styleId } = useParams<{ styleId: string }>()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['style', styleId], queryFn: () => getStyle(styleId!), enabled: Boolean(styleId) })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['style', styleId] })
  const version = query.data?.versions[0]
  const [settings, setSettings] = useState<Record<string, unknown>>({ page: 'A4, portrait', font: 'Lato', accent: '#F67828', margins: '24 / 13 / 18 мм', renderer_theme_id: 'villartec-manual-a4', renderer_theme_version: '1.0' })
  useEffect(() => {
    if (version) {
      setSettings({ page: 'A4, portrait', font: 'Lato', accent: '#F67828', margins: '24 / 13 / 18 мм', renderer_theme_id: 'villartec-manual-a4', renderer_theme_version: '1.0', ...version.settings })
    }
  }, [version?.id, version?.settings])
  const createVersion = useMutation({ mutationFn: () => createStyleVersion(styleId!), onSuccess: refresh })
  const validate = useMutation({ mutationFn: () => validateStyleVersion(version!.id), onSuccess: refresh })
  const publish = useMutation({ mutationFn: () => publishStyleVersion(version!.id), onSuccess: refresh })
  const preview = useMutation({ mutationFn: () => previewStyleVersion(version!.id), onSuccess: ({ url }) => window.open(url, '_blank', 'noopener,noreferrer') })
  const saveSettings = useMutation({ mutationFn: () => updateStyleVersion(version!.id, settings), onSuccess: refresh })
  const uploadReference = useMutation({ mutationFn: (file: File) => uploadStyleReference(version!.id, file), onSuccess: refresh })
  const duplicate = useMutation({ mutationFn: () => duplicateStyle(styleId!), onSuccess: (style) => { window.location.href = `/styles/${style.id}` } })
  const archive = useMutation({ mutationFn: () => archiveStyle(styleId!), onSuccess: refresh })

  if (query.isLoading) return <main className="grid min-h-screen place-content-center text-app-muted">Загрузка стилизации…</main>
  if (query.isError || !query.data) return <main className="grid min-h-screen place-content-center text-app-danger">Не удалось открыть стилизацию.</main>

  return (
    <main className="min-h-screen bg-[#f6f7f9] text-app-text">
      <header className="workbench-header border-b border-app-border bg-white">
        <div className="mx-auto flex min-h-16 w-[min(1120px,calc(100%_-_64px))] items-center justify-between gap-6">
          <Link className="text-sm font-semibold text-app-muted no-underline hover:text-app-text" to="/styles">← Стилизации</Link>
          <span className="text-sm text-app-muted">Черновик пакета оформления</span>
        </div>
      </header>
      <div className="mx-auto w-[min(1120px,calc(100%_-_64px))] py-10">
        <div className="mb-8 flex items-start justify-between gap-6">
          <div>
            <p className="mb-2 text-sm font-bold uppercase tracking-[0.12em] text-app-accent">Настройка дизайна</p>
            <h1 className="m-0 mb-2 text-[34px] font-bold tracking-[-0.03em]">{query.data.name}</h1>
            <p className="m-0 max-w-[620px] text-app-muted">{query.data.description || 'Настройте страницу, типографику и компоненты документа.'}</p>
          </div>
          <div className="flex gap-2"><button className="rounded-control border border-app-border bg-white px-3.5 py-2 text-sm font-bold disabled:opacity-50" type="button" disabled={duplicate.isPending} onClick={() => duplicate.mutate()}>Дублировать</button><button className="rounded-control border border-app-border bg-white px-3.5 py-2 text-sm font-bold disabled:opacity-50" type="button" disabled={archive.isPending || query.data.status === 'archived'} onClick={() => archive.mutate()}>Архивировать</button><button className="rounded-control bg-app-accent px-3.5 py-2 text-sm font-bold text-white disabled:opacity-50" type="button" disabled={createVersion.isPending || query.data.status === 'archived'} onClick={() => createVersion.mutate()}>Создать версию</button></div>
        </div>
        <div className="grid gap-5 min-[900px]:grid-cols-[minmax(0,1fr)_320px]">
          <section className="rounded-2xl border border-app-border bg-white p-6">
            <div className="mb-6 flex items-center justify-between gap-4 border-b border-app-border pb-4">
              <div><h2 className="m-0 text-lg font-bold">Быстрая настройка</h2><p className="m-0 mt-1 text-sm text-app-muted">Безопасные параметры визуального стандарта.</p></div>
              <span className="rounded-full bg-[#f1f3f5] px-2.5 py-1 text-xs font-bold text-app-muted">{version ? `v${version.version}` : 'Нет версии'}</span>
            </div>
            <div className="grid gap-5 min-[680px]:grid-cols-2">
              <label className="grid min-w-0 gap-2 text-sm font-semibold">Формат страницы<select className="box-border min-h-10 w-full min-w-0 rounded-control border border-app-border bg-white px-3 font-normal" value={String(settings.page ?? 'A4, portrait')} onChange={(event) => { const page = event.target.value; const isA5 = page.startsWith('A5'); setSettings((current) => ({ ...current, page, renderer_theme_id: isA5 ? 'villartec-manual-a5' : 'villartec-manual-a4', renderer_theme_version: '1.0', margins: isA5 ? '19 / 12 / 15 мм' : '24 / 13 / 18 мм' })) }}><option>A4, portrait</option><option>A4, landscape</option><option>A5, portrait</option><option>A5, landscape</option><option>Letter, portrait</option><option>Letter, landscape</option></select></label>
              <label className="grid min-w-0 gap-2 text-sm font-semibold">Шрифт<select className="box-border min-h-10 w-full min-w-0 rounded-control border border-app-border bg-white px-3 font-normal" value={String(settings.font ?? 'Lato')} onChange={(event) => setSettings((current) => ({ ...current, font: event.target.value }))}><option>Lato</option><option>Arial</option><option>Helvetica</option><option>Inter</option></select></label>
              <label className="grid min-w-0 gap-2 text-sm font-semibold">Цвет акцента<input className="box-border min-h-10 w-full min-w-0 rounded-control border border-app-border bg-white p-1" type="color" value={String(settings.accent ?? '#F67828')} onChange={(event) => setSettings((current) => ({ ...current, accent: event.target.value }))} /></label>
              <label className="grid min-w-0 gap-2 text-sm font-semibold">Поля страницы<input className="box-border min-h-10 w-full min-w-0 rounded-control border border-app-border px-3 font-normal" value={String(settings.margins ?? '24 / 13 / 18 мм')} onChange={(event) => setSettings((current) => ({ ...current, margins: event.target.value }))} placeholder="24 / 13 / 18 мм" /><small className="font-normal text-app-muted">Верхнее / боковые / нижнее, от 8 до 40 мм</small></label>
              <label className="grid gap-2 text-sm font-semibold">Тема оформления<input className="box-border min-h-10 w-full rounded-control border border-app-border bg-[#f6f7f9] px-3 font-normal text-app-muted" value={`${String(settings.renderer_theme_id ?? 'villartec-manual-a4')} · ${String(settings.renderer_theme_version ?? '1.0')}`} readOnly /><small className="font-normal text-app-muted">Фиксируется в версии стилизации.</small></label>
            <button className="mt-5 min-h-10 rounded-control bg-app-accent px-4 text-sm font-bold text-white disabled:opacity-50" type="button" disabled={saveSettings.isPending || !version || version.status !== 'draft'} onClick={() => saveSettings.mutate()}>{saveSettings.isPending ? 'Сохранение…' : 'Сохранить настройки'}</button>
            </div>
            <div className="mt-6 grid gap-3 rounded-xl border border-dashed border-[#cbd2db] bg-[#fafbfc] p-5 text-sm text-app-muted"><strong className="text-app-text">PDF-референс</strong><p className="m-0">Эталон используется при следующей обработке документа, созданной с этой версией.</p><input type="file" accept="application/pdf,.pdf" disabled={!version || version.status !== 'draft' || uploadReference.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadReference.mutate(file); event.currentTarget.value = '' }} />{typeof version?.settings.reference_file === 'object' && version.settings.reference_file && 'filename' in version.settings.reference_file && <span>Прикреплён: {String(version.settings.reference_file.filename)}</span>}{uploadReference.isError && <span role="alert" className="text-app-danger">Не удалось загрузить PDF-референс.</span>}</div>
          </section>
          <aside className="h-fit rounded-2xl border border-app-border bg-white p-5">
            <h2 className="m-0 mb-2 text-base font-bold">Версия и публикация</h2>
            <p className="m-0 mb-5 text-sm leading-relaxed text-app-muted">Опубликованная версия фиксируется для новых запусков и не изменяет старые результаты.</p>
            {version ? <div className="grid gap-2 text-sm"><div className="flex justify-between"><span className="text-app-muted">Статус</span><strong>{version.status}</strong></div><div className="flex justify-between"><span className="text-app-muted">Документов</span><strong>{query.data.documents_count}</strong></div><div className="mt-4 grid gap-2"><button className="min-h-9 rounded-control border border-app-border bg-white font-semibold disabled:opacity-50" type="button" disabled={preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? 'Формирование…' : 'Открыть preview'}</button><button className="min-h-9 rounded-control border border-app-border bg-white font-semibold disabled:opacity-50" type="button" disabled={validate.isPending || version.status === 'published'} onClick={() => validate.mutate()}>{validate.isPending ? 'Проверка…' : 'Проверить пакет'}</button><button className="min-h-9 rounded-control bg-app-accent font-semibold text-white disabled:opacity-50" type="button" disabled={publish.isPending || version.status !== 'validating'} onClick={() => publish.mutate()}>{publish.isPending ? 'Публикация…' : 'Опубликовать версию'}</button></div></div> : <p className="text-sm text-app-muted">Создайте первую версию стилизации.</p>}
          </aside>
        </div>
      </div>
    </main>
  )
}
