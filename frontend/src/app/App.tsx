import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { DocumentsPage } from '@/pages/documents'
import { EditorPage } from '@/pages/editor'
import { StyleDetailPage, StylesPage } from '@/pages/styles'
import { AUTH_REQUIRED_EVENT, setBasicAuthCredentials } from '@/shared/api/auth'

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
  const [authOpen, setAuthOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  useEffect(() => {
    const handleAuthRequired = () => {
      setAuthOpen(true)
    }
    window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired)
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired)
  }, [])

  const submitAuth = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!username.trim() || !password) return
    setBasicAuthCredentials(username.trim(), password)
    setPassword('')
    setAuthOpen(false)
    window.location.reload()
  }

  return (
    <>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
      {authOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" role="presentation">
          <form
            className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl"
            onSubmit={submitAuth}
            aria-labelledby="auth-title"
          >
            <h2 id="auth-title" className="text-xl font-semibold text-slate-900">Вход в сервис</h2>
            <p className="mt-2 text-sm text-slate-600">Введите логин и пароль один раз.</p>
            <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="auth-username">
              Логин
            </label>
            <input
              id="auth-username"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              autoFocus
            />
            <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="auth-password">
              Пароль
            </label>
            <input
              id="auth-password"
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
                onClick={() => setAuthOpen(false)}
              >
                Отмена
              </button>
              <button
                type="submit"
                className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white hover:bg-orange-600 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!username.trim() || !password}
              >
                Войти
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}
