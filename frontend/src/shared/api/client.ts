import { env } from '@/shared/config/env'
import { clearBasicAuthCredentials, getAuthorizationHeader, notifyAuthRequired } from './auth'

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
  const authorization = getAuthorizationHeader()
  if (authorization) headers.set('Authorization', authorization)
  else headers.set('X-User-ID', env.devUserId)
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  return headers
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = buildHeaders(init)
  const response = await fetch(`${env.apiUrl}${path}`, { ...init, headers })
  if (response.status === 401) {
    clearBasicAuthCredentials()
    notifyAuthRequired()
  }
  if (!response.ok) {
    const responseText = await response.text()
    let details: unknown = responseText || undefined
    if (responseText) {
      try {
        details = JSON.parse(responseText)
      } catch {}
    }
    const errorPayload = typeof details === 'object' && details !== null && 'error' in details
      ? (details as { error?: { message?: unknown } }).error
      : undefined
    const message = typeof errorPayload?.message === 'string'
      ? errorPayload.message
      : typeof details === 'object' && details !== null && 'detail' in details
        ? String(details.detail)
        : responseText || `HTTP ${response.status}`
    throw new ApiError(message, response.status, details)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export { clearBasicAuthCredentials, setBasicAuthCredentials } from './auth'
