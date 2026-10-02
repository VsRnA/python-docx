import { DocumentList } from '@/widgets/document-list'
import { UploadDocument } from '@/features/upload-document'

export function DocumentsPage() {
  return (
    <main className="mx-auto w-[min(1200px,calc(100%_-_64px))] py-10">
      <header className="mb-8 flex items-center justify-between gap-6">
        <div>
          <h1 className="m-0 mb-2 text-[32px] font-bold leading-tight text-app-text">Документы</h1>
          <p className="m-0 text-app-muted">Загрузка, обработка и публикация инструкций</p>
        </div>
        <UploadDocument />
      </header>
      <DocumentList />
    </main>
  )
}
