const BASIC_AUTH_KEY = 'basic_auth'
const ACCESS_TOKEN_KEY = 'access_token'
export const AUTH_REQUIRED_EVENT = 'document-service:auth-required'

export function getAuthorizationHeader(): string | null {
  const basicCredentials = window.sessionStorage.getItem(BASIC_AUTH_KEY)
  const accessToken = window.sessionStorage.getItem(ACCESS_TOKEN_KEY)
  if (basicCredentials) return `Basic ${basicCredentials}`
  if (accessToken) return `Bearer ${accessToken}`
  return null
}

export function setBasicAuthCredentials(username: string, password: string) {
  window.sessionStorage.setItem(BASIC_AUTH_KEY, window.btoa(`${username}:${password}`))
}

export function clearBasicAuthCredentials() {
  window.sessionStorage.removeItem(BASIC_AUTH_KEY)
}

export function notifyAuthRequired() {
  window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT))
}
