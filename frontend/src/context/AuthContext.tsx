import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { clearStoredToken, getStoredToken, setStoredToken } from '../services/api'
import {
  fetchCurrentUser,
  loginUser,
  registerUser,
  type AuthUser,
  type LoginPayload,
  type RegisterPayload,
} from '../services/authService'
import { AuthContext } from './authContextStore'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken())
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isInitializing, setIsInitializing] = useState<boolean>(() => Boolean(getStoredToken()))

  useEffect(() => {
    const initialToken = getStoredToken()
    if (!initialToken) {
      return
    }

    let cancelled = false

    fetchCurrentUser()
      .then((profile) => {
        if (cancelled) return
        setUser(profile)
      })
      .catch(() => {
        if (cancelled) return
        clearStoredToken()
        setToken(null)
        setUser(null)
      })
      .finally(() => {
        if (!cancelled) {
          setIsInitializing(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload): Promise<AuthUser> => {
    const data = await loginUser(payload)
    setStoredToken(data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (payload: RegisterPayload): Promise<AuthUser> => {
    const data = await registerUser(payload)
    setStoredToken(data.access_token)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(() => {
    clearStoredToken()
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(user && token),
      isInitializing,
      login,
      register,
      logout,
    }),
    [user, token, isInitializing, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
