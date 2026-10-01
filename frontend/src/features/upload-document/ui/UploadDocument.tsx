import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { createDocument, createMergedDocument } from '@/entities/document'
import { Button } from '@/shared/ui/button'

import styles from './upload-document.module.css'

const MAX_DOCX_SIZE_BYTES = 50 * 1024 * 1024
type UploadMode = 'single' | 'merge'

export function UploadDocument() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<UploadMode>('single')
  const [mergeNotes, setMergeNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const singleMutation = useMutation({
    mutationFn: ({ title, file }: { title: string; file: File }) => createDocument(title, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
    onError: () => setError('Не удалось загрузить документ.'),
  })
  const mergeMutation = useMutation({
    mutationFn: ({ title, files, notes }: { title: string; files: File[]; notes?: string }) =>
      createMergedDocument(title, files, notes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
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
    <div className={styles.root}>
      <div className={styles.modeToggle} aria-label="Режим загрузки документа">
        <label className={styles.modeOption} data-active={mode === 'single'}>
          <input
            type="radio"
            name="upload-mode"
            checked={mode === 'single'}
            onChange={() => setMode('single')}
          />
          <span>Один DOCX</span>
        </label>
        <label className={styles.modeOption} data-active={mode === 'merge'}>
          <input
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
          className={styles.notes}
          type="text"
          value={mergeNotes}
          placeholder="Комментарий для GPT Astra 6, необязательно"
          onChange={(event) => setMergeNotes(event.target.value)}
        />
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        multiple={mode === 'merge'}
        hidden
        onChange={handleChange}
      />
      <Button disabled={isPending} onClick={() => inputRef.current?.click()}>
        {isPending ? 'Загрузка…' : mode === 'merge' ? 'Выбрать DOCX для слияния' : 'Загрузить DOCX'}
      </Button>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
