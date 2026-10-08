import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { createDocument, createMergedDocument } from '@/entities/document'
import { getStyles } from '@/entities/style'
import { cn } from '@/shared/lib/cn'
import { Button } from '@/shared/ui/button'

const MAX_DOCX_SIZE_BYTES = 50 * 1024 * 1024
type UploadMode = 'single' | 'merge'

export function UploadDocument() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<UploadMode>('single')
  const [mergeNotes, setMergeNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [styleVersionId, setStyleVersionId] = useState('')
  const [translationEnabled, setTranslationEnabled] = useState(false)
  const [targetLanguage, setTargetLanguage] = useState('ru')
  const [glossaryVersionId, setGlossaryVersionId] = useState('')
  const queryClient = useQueryClient()
  const styles = useQuery({ queryKey: ['styles'], queryFn: getStyles })
  const singleMutation = useMutation({
    mutationFn: ({ title, file }: { title: string; file: File }) => createDocument(title, file, { styleVersionId: styleVersionId || undefined, targetLanguage: translationEnabled ? targetLanguage : undefined, translationEnabled, glossaryVersionId: glossaryVersionId.trim() || undefined }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: () => setError('Не удалось загрузить документ.'),
  })
  const mergeMutation = useMutation({
    mutationFn: ({ title, files, notes }: { title: string; files: File[]; notes?: string }) =>
      createMergedDocument(title, files, notes, { styleVersionId: styleVersionId || undefined, targetLanguage: translationEnabled ? targetLanguage : undefined, translationEnabled, glossaryVersionId: glossaryVersionId.trim() || undefined }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
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
    const title = files
      .map((file) => file.name.replace(/\.docx$/i, ''))
      .slice(0, 3)
      .join(' + ')
    mergeMutation.mutate({ title, files, notes: mergeNotes })
  }

  return (
    <div className="flex w-full min-w-0 flex-col items-stretch gap-2.5">
      <div
        className="grid w-full grid-cols-2 rounded-panel border border-app-border bg-app-bg p-[3px]"
        aria-label="Режим загрузки документа"
      >
        <label
          className={cn(
            'flex min-h-[34px] cursor-pointer items-center justify-center rounded-control text-sm font-bold text-[#4f5661]',
            mode === 'single' && 'bg-app-panel text-app-text shadow-control',
          )}
          data-active={mode === 'single'}
        >
          <input
            className="pointer-events-none absolute h-px w-px opacity-0"
            type="radio"
            name="upload-mode"
            checked={mode === 'single'}
            onChange={() => setMode('single')}
          />
          <span>Один DOCX</span>
        </label>
        <label
          className={cn(
            'flex min-h-[34px] cursor-pointer items-center justify-center rounded-control text-sm font-bold text-[#4f5661]',
            mode === 'merge' && 'bg-app-panel text-app-text shadow-control',
          )}
          data-active={mode === 'merge'}
        >
          <input
            className="pointer-events-none absolute h-px w-px opacity-0"
            type="radio"
            name="upload-mode"
            checked={mode === 'merge'}
            onChange={() => setMode('merge')}
          />
          <span>Слить DOCX</span>
        </label>
      </div>
      {mode === 'merge' && (
        <input
          className="surface-reveal box-border min-h-[38px] w-full min-w-0 rounded-panel border border-app-border px-3"
          type="text"
          value={mergeNotes}
          placeholder="Комментарий для GPT Astra 6, необязательно"
          onChange={(event) => setMergeNotes(event.target.value)}
        />
      )}
      <label className="grid w-full gap-1.5 text-left text-sm font-semibold text-app-text">
        Стилизация
        <select required className="box-border min-h-[38px] w-full min-w-0 rounded-panel border border-app-border bg-white px-3 font-normal" value={styleVersionId} onChange={(event) => setStyleVersionId(event.target.value)}>
          <option value="">Выберите опубликованную стилизацию</option>
          {styles.data?.flatMap((style) => style.current_version?.status === 'published' ? [{ id: style.current_version.id, label: `${style.name} · v${style.current_version.version}` }] : []).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
        </select>
      </label>
      <label className="flex w-full items-center gap-2 text-sm text-app-muted"><input type="checkbox" checked={translationEnabled} onChange={(event) => setTranslationEnabled(event.target.checked)} /> Перевести документ</label>
      {translationEnabled && <label className="surface-reveal grid w-full min-w-0 gap-1.5 text-left text-sm font-semibold text-app-text">Язык перевода<select className="box-border min-h-[38px] w-full min-w-0 rounded-panel border border-app-border bg-white px-3 font-normal" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}><option value="ru">Русский</option><option value="en">Английский</option><option value="zh">Китайский</option><option value="de">Немецкий</option><option value="fr">Французский</option></select></label>}
      {translationEnabled && <label className="surface-reveal grid w-full min-w-0 gap-1.5 text-left text-sm font-semibold text-app-text">Версия глоссария (необязательно)<input className="box-border min-h-[38px] w-full min-w-0 rounded-panel border border-app-border px-3 font-normal" value={glossaryVersionId} onChange={(event) => setGlossaryVersionId(event.target.value)} placeholder="например, ru-tech-v2" /></label>}
      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        multiple={mode === 'merge'}
        hidden
        onChange={handleChange}
      />
      <Button disabled={isPending || !styleVersionId} onClick={() => inputRef.current?.click()}>
        {isPending ? 'Загрузка…' : mode === 'merge' ? 'Выбрать DOCX для слияния' : 'Загрузить DOCX'}
      </Button>
      {error && (
        <p className="m-0 max-w-[360px] text-right text-sm text-app-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
