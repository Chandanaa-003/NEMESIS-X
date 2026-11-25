import axios from 'axios'

export const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

export const ACCESS_TOKEN_STORAGE_KEY = 'nemesis_x_access_token'

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
}

export function clearStoredToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
