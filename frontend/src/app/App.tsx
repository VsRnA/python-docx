import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'

import { DocumentsPage } from '@/pages/documents'
import { EditorPage } from '@/pages/editor'
import { StyleDetailPage, StylesPage } from '@/pages/styles'

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
  {
    path: '/styles',
    element: <StylesPage />,
  },
  {
    path: '/styles/:styleId',
    element: <StyleDetailPage />,
  },
])

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
