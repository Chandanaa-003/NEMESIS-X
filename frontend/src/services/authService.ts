import axios from 'axios'
import { apiClient } from './api'

export interface AuthUser {
  id: number
  full_name: string
  email: string
  is_active: boolean
  created_at: string
}

export interface AuthTokenResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface RegisterPayload {
  full_name: string
  email: string
  password: string
  confirm_password: string
}

export interface LoginPayload {
  email: string
  password: string
}

interface ValidationDetailItem {
  msg?: string
}

interface FastApiErrorPayload {
  detail?: string | ValidationDetailItem[]
}

export async function registerUser(payload: RegisterPayload): Promise<AuthTokenResponse> {
  const response = await apiClient.post<AuthTokenResponse>('/auth/register', payload)
  return response.data
}

export async function loginUser(payload: LoginPayload): Promise<AuthTokenResponse> {
  const response = await apiClient.post<AuthTokenResponse>('/auth/login', payload)
  return response.data
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const response = await apiClient.get<AuthUser>('/auth/me')
  return response.data
}

export function getAuthErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<FastApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const firstMessage = detail[0]?.msg
      if (typeof firstMessage === 'string' && firstMessage.trim()) {
        return firstMessage.replace(/^Value error,\s*/i, '')
      }
    }
    if (!error.response) {
      return 'Unable to reach the NEMESIS-X backend server. Make sure the FastAPI server is running.'
    }
  }
  return fallback
}
