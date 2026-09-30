import { DocumentList } from '@/widgets/document-list'
import { UploadDocument } from '@/features/upload-document'

import styles from './documents-page.module.css'

export function DocumentsPage() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Документы</h1>
          <p>Загрузка, обработка и публикация инструкций</p>
        </div>
        <UploadDocument />
      </header>
      <DocumentList />
    </main>
  )
}
