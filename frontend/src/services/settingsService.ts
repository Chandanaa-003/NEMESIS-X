import { apiClient } from './api.ts'

export type VoiceLanguageMode = 'english' | 'kannada' | 'bilingual'

export interface UserVoiceSettings {
  voice_language: VoiceLanguageMode
  voice_alerts_enabled: boolean
  alert_volume: number
  announce_high_priority: boolean
  announce_medium_priority: boolean
  announce_low_priority: boolean
  cooldown_seconds: number
  updated_at?: string
}

export const DEFAULT_VOICE_SETTINGS: UserVoiceSettings = {
  voice_language: 'english',
  voice_alerts_enabled: true,
  alert_volume: 0.85,
  announce_high_priority: true,
  announce_medium_priority: true,
  announce_low_priority: true,
  cooldown_seconds: 30,
}

export const VOICE_LANGUAGE_LABELS: Record<VoiceLanguageMode, string> = {
  english: 'English',
  kannada: 'Kannada (ಕನ್ನಡ)',
  bilingual: 'English + Kannada',
}

export async function fetchUserVoiceSettings(): Promise<UserVoiceSettings> {
  const response = await apiClient.get<UserVoiceSettings>('/settings')
  return response.data
}

export async function updateUserVoiceSettings(
  payload: Omit<UserVoiceSettings, 'updated_at'>,
): Promise<UserVoiceSettings> {
  const response = await apiClient.put<UserVoiceSettings>('/settings', payload)
  return response.data
}
