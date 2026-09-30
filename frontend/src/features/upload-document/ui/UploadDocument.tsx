import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { createDocument } from '@/entities/document'
import { Button } from '@/shared/ui/button'

const MAX_DOCX_SIZE_BYTES = 50 * 1024 * 1024

export function UploadDocument() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: ({ title, file }: { title: string; file: File }) => createDocument(title, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
    onError: () => setError('Не удалось загрузить документ.'),
  })

  const handleChange = () => {
    const input = inputRef.current
    const file = input?.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.docx')) {
      input.value = ''
      setError('Выберите документ в формате DOCX.')
      return
    }

    if (file.size > MAX_DOCX_SIZE_BYTES) {
      input.value = ''
      setError('Размер DOCX не должен превышать 50 МБ.')
      return
    }

    setError(null)
    mutation.mutate({ title: file.name.replace(/\.docx$/i, ''), file })
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        hidden
        onChange={handleChange}
      />
      <Button disabled={mutation.isPending} onClick={() => inputRef.current?.click()}>
        {mutation.isPending ? 'Загрузка…' : 'Загрузить DOCX'}
      </Button>
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
