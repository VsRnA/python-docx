import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'

import { DocumentsPage } from '@/pages/documents'
import { EditorPage } from '@/pages/editor'

const queryClient = new QueryClient()
const router = createBrowserRouter([
  {
    path: '/',
    element: <DocumentsPage />,
  },
  {
    path: '/documents/:documentId',
    element: <EditorPage />,
  },
])

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
