import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { createDocument, createMergedDocument } from '@/entities/document'
import { bootstrapStyles, getStyles } from '@/entities/style'
import { queryKeys } from '@/shared/api/queryKeys'
import { cn } from '@/shared/lib/cn'

const MAX_DOCX_SIZE_BYTES = 50 * 1024 * 1024
type UploadMode = 'single' | 'merge'

export function UploadDocument() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<UploadMode>('single')
  const [mergeNotes, setMergeNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [styleVersionId, setStyleVersionId] = useState('')
  const [translationEnabled, setTranslationEnabled] = useState(false)
  const queryClient = useQueryClient()
  const styles = useQuery({ queryKey: queryKeys.styles(), queryFn: async () => { await bootstrapStyles(); return getStyles() } })

  const close = () => {
    if (!singleMutation.isPending && !mergeMutation.isPending) setOpen(false)
  }

  const singleMutation = useMutation({
    mutationFn: ({ title, file }: { title: string; file: File }) => createDocument(title, file, { styleVersionId: styleVersionId || undefined, targetLanguage: translationEnabled ? 'ru' : undefined, translationEnabled }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.documents() }); setOpen(false) },
    onError: () => setError('Не удалось загрузить документ.'),
  })
  const mergeMutation = useMutation({
    mutationFn: ({ title, files, notes }: { title: string; files: File[]; notes?: string }) => createMergedDocument(title, files, notes, { styleVersionId: styleVersionId || undefined, targetLanguage: translationEnabled ? 'ru' : undefined, translationEnabled }),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.documents() }); setOpen(false) },
    onError: () => setError('Не удалось запустить слияние документов.'),
  })
  const isPending = singleMutation.isPending || mergeMutation.isPending

  const handleChange = () => {
    const input = inputRef.current
    if (!input) return
    const files = Array.from(input.files ?? [])
    if (!files.length) return

    if (files.some((file) => !file.name.toLowerCase().endsWith('.docx'))) {
      input.value = ''
      setError('Выберите документы в формате DOCX.')
      return
    }
    if (files.some((file) => file.size > MAX_DOCX_SIZE_BYTES)) {
      input.value = ''
      setError('Размер каждого DOCX не должен превышать 50 МБ.')
      return
    }
    if (mode === 'merge' && files.length < 2) {
      input.value = ''
      setError('Для слияния выберите минимум два DOCX.')
      return
    }

    setError(null)
    if (mode === 'single') {
      const file = files[0]
      singleMutation.mutate({ title: file.name.replace(/\.docx$/i, ''), file })
      return
    }
    const title = files.map((file) => file.name.replace(/\.docx$/i, '')).slice(0, 3).join(' + ')
    mergeMutation.mutate({ title, files, notes: mergeNotes })
  }

  return (
    <div>
      <button className="flex min-h-10 w-full items-center justify-center gap-2 rounded-control border-0 bg-app-brand px-4 font-semibold text-white transition-colors hover:bg-app-brandHover disabled:cursor-not-allowed disabled:opacity-60" type="button" onClick={() => { setError(null); setOpen(true) }}>
        <span className="text-lg leading-none">+</span> Новый документ
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-[1000] grid place-items-center bg-[#171717]/30 p-5" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close() }}>
          <div className="relative z-[1001] max-h-[calc(100vh-40px)] w-full max-w-[500px] overflow-y-auto rounded-panel border border-app-border bg-app-panel p-6 shadow-[0_24px_70px_rgb(23_23_23_/_22%)]" role="dialog" aria-modal="true" aria-labelledby="new-document-title">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div><h2 id="new-document-title" className="m-0 text-xl font-bold tracking-[-0.02em]">Новый документ</h2><p className="m-0 mt-2 text-sm leading-relaxed text-app-muted">Загрузите DOCX и выберите параметры обработки.</p></div>
              <button className="grid h-8 w-8 shrink-0 place-items-center rounded-control border-0 bg-transparent text-xl leading-none text-app-muted hover:bg-app-subtle hover:text-app-text" type="button" onClick={close} aria-label="Закрыть">×</button>
            </div>

            <div className="grid min-h-[118px] place-items-center rounded-control border border-dashed border-[#c9c0b8] bg-app-bg p-5 text-center text-sm text-app-muted">
              <div><strong className="block mb-1 text-app-text">Перетащите файл сюда</strong><span>или выберите его на компьютере</span><button className="mt-3 block w-full text-sm font-semibold text-app-accent hover:underline" type="button" onClick={() => inputRef.current?.click()}>Выбрать DOCX</button></div>
            </div>

            <div className="mt-4 grid grid-cols-2 rounded-control border border-app-border bg-app-bg p-[3px]" aria-label="Режим загрузки документа">
              {([['single', 'Один DOCX'], ['merge', 'Слить DOCX']] as const).map(([value, label]) => (
                <label className={cn('flex min-h-9 cursor-pointer items-center justify-center rounded-control text-sm font-semibold text-app-muted', mode === value && 'bg-app-panel text-app-text shadow-control')} key={value}>
                  <input className="sr-only" type="radio" name="upload-mode" checked={mode === value} onChange={() => setMode(value)} />{label}
                </label>
              ))}
            </div>
            {mode === 'merge' && <input className="mt-3 min-h-10 w-full rounded-control border border-app-border bg-app-panel px-3 text-sm outline-none focus:border-app-accent" type="text" value={mergeNotes} placeholder="Комментарий для слияния, необязательно" onChange={(event) => setMergeNotes(event.target.value)} />}

            <label className="mt-4 grid gap-2 text-xs font-bold text-app-muted">Стилизация<select required className="min-h-10 rounded-control border border-app-border bg-app-panel px-3 text-sm font-normal text-app-text" value={styleVersionId} onChange={(event) => setStyleVersionId(event.target.value)}><option value="">Выберите опубликованную стилизацию</option>{styles.data?.flatMap((style) => style.current_version?.status === 'published' ? [{ id: style.current_version.id, label: `${style.name} · v${style.current_version.version}` }] : []).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label>
            <label className="mt-4 flex items-center gap-2 text-sm text-app-muted"><input className="h-4 w-4 accent-app-accent" type="checkbox" checked={translationEnabled} onChange={(event) => setTranslationEnabled(event.target.checked)} /> Перевести документ на русский</label>
            <input ref={inputRef} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple={mode === 'merge'} hidden onChange={handleChange} />
            {error && <p className="m-0 mt-3 text-sm text-app-danger" role="alert">{error}</p>}
            <div className="mt-5 flex justify-end gap-2"><button className="min-h-10 rounded-control border border-app-border bg-app-panel px-4 font-semibold text-app-muted hover:border-app-borderStrong hover:text-app-text" type="button" onClick={close}>Отмена</button><button className="min-h-10 rounded-control border-0 bg-app-brand px-4 font-semibold text-white hover:bg-app-brandHover disabled:cursor-not-allowed disabled:opacity-60" type="button" disabled={isPending || !styleVersionId} onClick={() => inputRef.current?.click()}>{isPending ? 'Загрузка…' : mode === 'merge' ? 'Выбрать DOCX для слияния' : 'Выбрать файл'}</button></div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
