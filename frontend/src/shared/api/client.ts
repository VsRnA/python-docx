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

function buildHeaders(init?: RequestInit) {
  const headers = new Headers(init?.headers)
  const basicCredentials = window.localStorage.getItem('basic_auth')
  const accessToken = window.localStorage.getItem('access_token')
  if (basicCredentials) headers.set('Authorization', `Basic ${basicCredentials}`)
  else if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  else headers.set('X-User-ID', env.devUserId)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  return headers
}

async function requestBasicCredentials() {
  const username = window.prompt('Логин')
  if (!username) return false
  const password = window.prompt('Пароль') ?? ''
  setBasicAuthCredentials(username, password)
  return true
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let headers = buildHeaders(init)
  let response = await fetch(`${env.apiUrl}${path}`, { ...init, headers })
  if (response.status === 401) {
    clearBasicAuthCredentials()
    if (await requestBasicCredentials()) {
      headers = buildHeaders(init)
      response = await fetch(`${env.apiUrl}${path}`, { ...init, headers })
    }
  }
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

export function setBasicAuthCredentials(username: string, password: string) {
  window.localStorage.setItem('basic_auth', window.btoa(`${username}:${password}`))
}

export function clearBasicAuthCredentials() {
  window.localStorage.removeItem('basic_auth')
}
