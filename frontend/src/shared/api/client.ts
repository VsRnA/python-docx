import { env } from '@/shared/config/env'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message)
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  const accessToken = window.localStorage.getItem('access_token')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  else headers.set('X-User-ID', env.devUserId)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${env.apiUrl}${path}`, { ...init, headers })
  if (!response.ok) {
    let details: unknown
    try {
      details = await response.json()
    } catch {
      details = await response.text()
    }
    throw new ApiError('Ошибка запроса к серверу', response.status, details)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
