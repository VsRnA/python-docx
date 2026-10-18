import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { deleteStyle, getStyle, getStyleReference, updateStyle, uploadStyleReference } from '@/entities/style'
import { queryKeys } from '@/shared/api/queryKeys'

export function StyleDetailPage() {
  const { styleId } = useParams<{ styleId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: queryKeys.style(styleId), queryFn: () => getStyle(styleId!), enabled: Boolean(styleId) })
  const version = query.data?.versions[0]
  const storedPrompt = typeof version?.settings.style_prompt === 'string' ? version.settings.style_prompt : ''
  const reference = version?.settings.reference_file && typeof version.settings.reference_file === 'object'
    ? version.settings.reference_file as { filename?: string; size_bytes?: number }
    : null
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')

  useEffect(() => {
    if (!query.data) return
    setName(query.data.name)
    setDescription(query.data.description ?? '')
    setPrompt(storedPrompt)
  }, [query.data, storedPrompt])

  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.style(styleId) })
  const hasChanges = query.data !== undefined && (
    name !== query.data.name || description !== (query.data.description ?? '') || prompt !== storedPrompt
  )
  const save = useMutation({
    mutationFn: () => updateStyle(styleId!, {
      name: name.trim(),
      description: description.trim(),
      ...(prompt.trim() && prompt !== storedPrompt ? { prompt: prompt.trim() } : {}),
    }),
    onSuccess: refresh,
  })
  const uploadReference = useMutation({ mutationFn: (file: File) => uploadStyleReference(styleId!, file), onSuccess: refresh })
  const openReference = useMutation({ mutationFn: () => getStyleReference(styleId!), onSuccess: ({ url }) => window.open(url, '_blank', 'noopener,noreferrer') })
  const remove = useMutation({
    mutationFn: () => deleteStyle(styleId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.styles() })
      navigate('/styles')
    },
  })

  if (query.isLoading) return <main className="grid min-h-screen place-content-center text-app-muted">Загрузка стилизации…</main>
  if (query.isError || !query.data) return <main className="grid min-h-screen place-content-center text-app-danger">Не удалось открыть стилизацию.</main>

  return (
    <main className="min-h-screen bg-[#f6f7f9] text-app-text">
      <header className="workbench-header border-b border-app-border bg-white">
        <div className="mx-auto flex min-h-16 w-[min(1120px,calc(100%_-_64px))] items-center justify-between gap-6">
          <Link className="text-sm font-semibold text-app-muted no-underline hover:text-app-text" to="/styles">← Стилизации</Link>
          <button className="rounded-control border border-[#e7b7b7] bg-white px-3.5 py-2 text-sm font-bold text-[#a34040] disabled:opacity-50" type="button" disabled={remove.isPending} onClick={() => { if (window.confirm('Удалить стилизацию? Уже созданные документы сохранят свои результаты.')) remove.mutate() }}>{remove.isPending ? 'Удаление…' : 'Удалить'}</button>
        </div>
      </header>
      <div className="mx-auto w-[min(1120px,calc(100%_-_64px))] py-10">
        <div className="mb-8">
          <p className="mb-2 text-sm font-bold uppercase tracking-[0.12em] text-app-accent">Настройка дизайна</p>
          <h1 className="m-0 mb-2 text-[34px] font-bold tracking-[-0.03em]">{query.data.name}</h1>
          <p className="m-0 max-w-[720px] text-app-muted">Настройте материалы, которые будут использоваться при обработке новых документов.</p>
        </div>
        <section className="rounded-2xl border border-app-border bg-white p-6">
          <div className="mb-6 border-b border-app-border pb-4">
            <h2 className="m-0 text-lg font-bold">Материалы стилизации</h2>
            <p className="m-0 mt-1 text-sm text-app-muted">Изменения применяются к новым запускам обработки.</p>
          </div>
          <div className="grid gap-5 text-sm">
            <div className="grid gap-4 min-[760px]:grid-cols-2">
              <label className="grid gap-2"><span className="font-bold">Название</span><input className="min-h-10 rounded-xl border border-app-border bg-[#fafbfc] px-3 outline-none focus:border-app-accent" value={name} onChange={(event) => setName(event.target.value)} maxLength={255} /></label>
              <label className="grid gap-2"><span className="font-bold">Описание</span><input className="min-h-10 rounded-xl border border-app-border bg-[#fafbfc] px-3 outline-none focus:border-app-accent" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} /></label>
            </div>
            <label className="grid gap-2"><span className="font-bold">Prompt профиля</span><textarea className="min-h-[360px] w-full resize-y rounded-xl border border-app-border bg-[#fafbfc] p-4 font-mono text-[13px] leading-relaxed outline-none focus:border-app-accent" value={prompt} onChange={(event) => setPrompt(event.target.value)} /><span className="text-xs text-app-muted">Текст сохраняется в базе данных и используется при следующей обработке документа.</span></label>
            <div className="flex items-center gap-3"><button className="min-h-9 rounded-control bg-app-accent px-4 font-semibold text-white disabled:opacity-50" type="button" disabled={!name.trim() || !hasChanges || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Сохранение…' : 'Сохранить изменения'}</button>{save.isError && <span role="alert" className="text-app-danger">Не удалось сохранить изменения.</span>}{remove.isError && <span role="alert" className="text-app-danger">Не удалось удалить стилизацию.</span>}</div>
            <div className="rounded-xl border border-app-border bg-[#fafbfc] p-4"><div className="flex items-start justify-between gap-4"><div><strong>PDF-образец</strong><p className="m-0 mt-1 text-app-muted">Файл используется как визуальный образец оформления.</p>{reference?.filename && <p className="m-0 mt-2 text-xs text-app-muted">{reference.filename}{reference.size_bytes ? ` · ${(reference.size_bytes / 1024 / 1024).toFixed(1)} МБ` : ''}</p>}</div>{reference && <button className="min-h-9 rounded-control border border-app-border bg-white px-3 font-semibold disabled:opacity-50" type="button" disabled={openReference.isPending} onClick={() => openReference.mutate()}>{openReference.isPending ? 'Открытие…' : 'Открыть PDF'}</button>}</div><div className="mt-4 flex flex-wrap items-center gap-3"><label className="cursor-pointer rounded-control border border-app-border bg-white px-3 py-2 font-semibold">{reference ? 'Заменить PDF' : 'Прикрепить PDF'}<input className="sr-only" type="file" accept="application/pdf,.pdf" disabled={uploadReference.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadReference.mutate(file); event.currentTarget.value = '' }} /></label>{uploadReference.isPending && <span className="text-app-muted">Загрузка…</span>}{uploadReference.isError && <span role="alert" className="text-app-danger">Не удалось загрузить PDF.</span>}{openReference.isError && <span role="alert" className="text-app-danger">Не удалось открыть PDF.</span>}</div></div>
          </div>
        </section>
      </div>
    </main>
  )
}
