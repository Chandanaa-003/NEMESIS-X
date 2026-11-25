import { apiClient } from './api.ts'
import type { VoiceLanguageMode } from './settingsService.ts'

export type VoicePlaybackStatus =
  | 'spoken'
  | 'partial_text_fallback'
  | 'text_only_missing_voice'
  | 'disabled'
  | 'blocked_by_autoplay'
  | 'unavailable'
  | 'error'

export type TtsProviderKind =
  | 'browser_speech_synthesis'
  | 'backend_edge_tts'
  | 'hybrid_browser_and_backend'
  | 'text_fallback'
  | 'none'

export interface VoiceDiagnosticItem {
  name: string
  lang: string
}

export interface BackendKannadaTtsStatus {
  provider: string
  package_installed: boolean
  available: boolean
  internet_required: boolean
  kannada_voices: Array<{
    short_name: string
    friendly_name: string
    locale: string
    gender: string
  }>
  selected_voice: string | null
  error: string | null
}

export interface VoiceCapabilities {
  speechSupported: boolean
  voicesLoaded: boolean
  englishVoiceName: string | null
  englishVoiceLang: string | null
  kannadaVoiceName: string | null
  kannadaVoiceLang: string | null
  englishSupported: boolean
  kannadaSupported: boolean
  totalVoices: number
  availableEnglishVoices: VoiceDiagnosticItem[]
  availableKannadaVoices: VoiceDiagnosticItem[]
  selectedVoice: string | null
  lastSpeechError: string | null
  currentTtsProvider: TtsProviderKind
  statusNote: string
}

export interface SpeakRequest {
  language: VoiceLanguageMode
  volume: number
  englishText: string
  kannadaText: string
  enabled?: boolean
  userInitiated?: boolean
}

export interface SpeakResult {
  status: VoicePlaybackStatus
  spokenLanguages: ('english' | 'kannada')[]
  textFallbackUsed: boolean
  textNotifications: string[]
  providerUsed: TtsProviderKind
  message: string
}

type VoidListener = () => void

let currentToken = 0
let speakingNow = false
let activeAudioElement: HTMLAudioElement | null = null
let activeAudioBlobUrl: string | null = null
let lastSpeechError: string | null = null
let currentTtsProvider: TtsProviderKind = 'none'
const stateListeners = new Set<VoidListener>()
const voiceListeners = new Set<VoidListener>()
let voicesChangedBound = false

function notifyStateListeners(): void {
  for (const listener of stateListeners) {
    listener()
  }
}

function notifyVoiceListeners(): void {
  for (const listener of voiceListeners) {
    listener()
  }
}

function getSpeechSynthesisSafe(): SpeechSynthesis | null {
  if (typeof window === 'undefined') return null
  if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
    return null
  }
  return window.speechSynthesis
}

function bindVoicesChanged(): void {
  if (voicesChangedBound) return
  const synth = getSpeechSynthesisSafe()
  if (!synth) return
  voicesChangedBound = true
  try {
    synth.addEventListener?.('voiceschanged', () => {
      notifyVoiceListeners()
    })
  } catch {
    // Ignore browsers where addEventListener on speechSynthesis is unsupported
  }
}

function waitForVoicesLoaded(synth: SpeechSynthesis, timeoutMs = 1500): Promise<SpeechSynthesisVoice[]> {
  bindVoicesChanged()
  let existing: SpeechSynthesisVoice[] = []
  try {
    existing = synth.getVoices() || []
  } catch {
    existing = []
  }
  if (existing.length > 0) {
    return Promise.resolve(existing)
  }

  return new Promise((resolve) => {
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      try {
        synth.removeEventListener?.('voiceschanged', onChanged)
      } catch {
        // Ignore
      }
      let loaded: SpeechSynthesisVoice[] = []
      try {
        loaded = synth.getVoices() || []
      } catch {
        loaded = []
      }
      resolve(loaded)
    }

    const onChanged = () => {
      finish()
    }

    try {
      synth.addEventListener?.('voiceschanged', onChanged)
    } catch {
      // Ignore
    }

    window.setTimeout(finish, timeoutMs)
  })
}

function pickEnglishVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const enVoices = voices.filter((v) => v.lang.toLowerCase().startsWith('en'))
  if (enVoices.length === 0) return null

  const preferredOrder = ['en-in', 'en-us', 'en-gb']
  for (const prefix of preferredOrder) {
    const match = enVoices.find((v) => v.lang.toLowerCase().startsWith(prefix))
    if (match) return match
  }
  return enVoices[0]
}

function pickKannadaVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const knExact = voices.find((v) => v.lang.toLowerCase() === 'kn-in')
  if (knExact) return knExact
  const knPrefix = voices.find((v) => v.lang.toLowerCase().startsWith('kn'))
  if (knPrefix) return knPrefix
  const knByName = voices.find((v) => v.name.toLowerCase().includes('kannada'))
  return knByName ?? null
}

export async function fetchBackendKannadaTtsStatus(): Promise<BackendKannadaTtsStatus | null> {
  try {
    const res = await apiClient.get<BackendKannadaTtsStatus>('/tts/kannada/status', {
      timeout: 5000,
    })
    return res.data
  } catch {
    return null
  }
}

export function getVoiceCapabilities(): VoiceCapabilities {
  bindVoicesChanged()
  const synth = getSpeechSynthesisSafe()
  if (!synth) {
    return {
      speechSupported: false,
      voicesLoaded: false,
      englishVoiceName: null,
      englishVoiceLang: null,
      kannadaVoiceName: null,
      kannadaVoiceLang: null,
      englishSupported: false,
      kannadaSupported: false,
      totalVoices: 0,
      availableEnglishVoices: [],
      availableKannadaVoices: [],
      selectedVoice: null,
      lastSpeechError,
      currentTtsProvider,
      statusNote:
        'Web Speech API (speechSynthesis) is not supported in this browser. Backend Kannada fallback or text notifications will be used.',
    }
  }

  let voices: SpeechSynthesisVoice[] = []
  try {
    voices = synth.getVoices() || []
  } catch {
    voices = []
  }

  const enVoices = voices
    .filter((v) => v.lang.toLowerCase().startsWith('en'))
    .map((v) => ({ name: v.name, lang: v.lang }))
  const knVoices = voices
    .filter(
      (v) =>
        v.lang.toLowerCase().startsWith('kn') ||
        v.name.toLowerCase().includes('kannada'),
    )
    .map((v) => ({ name: v.name, lang: v.lang }))

  const enVoice = pickEnglishVoice(voices)
  const knVoice = pickKannadaVoice(voices)

  let statusNote = ''
  if (voices.length === 0) {
    statusNote =
      'Waiting for browser speech voices to load. Backend Kannada TTS fallback or text notifications remain available.'
  } else if (enVoice && knVoice) {
    statusNote = `Both English (${enVoice.lang}) and Kannada (${knVoice.lang}) browser voices are available.`
  } else if (enVoice && !knVoice) {
    statusNote =
      'English browser voice is active; no browser Kannada (kn-IN) voice installed. Kannada will use backend edge-tts fallback (requires internet) or text notification.'
  } else if (!enVoice && knVoice) {
    statusNote = `Kannada (${knVoice.lang}) voice is available, but no English voice was found.`
  } else {
    statusNote =
      'No English or Kannada browser voices were found. Backend fallback or text notifications will be used.'
  }

  const selectedVoice = knVoice
    ? `${knVoice.name} (${knVoice.lang})`
    : enVoice
      ? `${enVoice.name} (${enVoice.lang})`
      : null

  return {
    speechSupported: true,
    voicesLoaded: voices.length > 0,
    englishVoiceName: enVoice?.name ?? null,
    englishVoiceLang: enVoice?.lang ?? null,
    kannadaVoiceName: knVoice?.name ?? null,
    kannadaVoiceLang: knVoice?.lang ?? null,
    englishSupported: Boolean(enVoice),
    kannadaSupported: Boolean(knVoice),
    totalVoices: voices.length,
    availableEnglishVoices: enVoices,
    availableKannadaVoices: knVoices,
    selectedVoice,
    lastSpeechError,
    currentTtsProvider,
    statusNote,
  }
}

export function isVoiceSpeaking(): boolean {
  return speakingNow
}

export function subscribeVoicePlayback(listener: VoidListener): () => void {
  stateListeners.add(listener)
  return () => {
    stateListeners.delete(listener)
  }
}

export function subscribeVoiceCapabilities(listener: VoidListener): () => void {
  bindVoicesChanged()
  voiceListeners.add(listener)
  return () => {
    voiceListeners.delete(listener)
  }
}

function cleanupActiveAudio(): void {
  if (activeAudioElement) {
    try {
      activeAudioElement.pause()
      activeAudioElement.currentTime = 0
      activeAudioElement.src = ''
    } catch {
      // Ignore audio cleanup errors
    }
    activeAudioElement = null
  }
  if (activeAudioBlobUrl) {
    try {
      URL.revokeObjectURL(activeAudioBlobUrl)
    } catch {
      // Ignore revoke errors
    }
    activeAudioBlobUrl = null
  }
}

export function stopSpeaking(): void {
  currentToken += 1
  const synth = getSpeechSynthesisSafe()
  if (synth) {
    try {
      synth.cancel()
    } catch {
      // Ignore browser cancel errors
    }
  }
  cleanupActiveAudio()
  if (speakingNow) {
    speakingNow = false
    notifyStateListeners()
  }
}

function buildTextNotifications(req: SpeakRequest): string[] {
  if (req.language === 'english') {
    return req.englishText ? [req.englishText] : []
  }
  if (req.language === 'kannada') {
    return req.kannadaText ? [req.kannadaText] : []
  }
  return [req.englishText, req.kannadaText].filter(Boolean)
}

function speakUtteranceItem(
  synth: SpeechSynthesis,
  text: string,
  lang: string,
  voice: SpeechSynthesisVoice,
  volume: number,
  token: number,
): Promise<'ok' | 'cancelled' | 'not_allowed' | 'error'> {
  return new Promise((resolve) => {
    if (token !== currentToken) {
      resolve('cancelled')
      return
    }

    try {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = voice.lang || lang
      utterance.voice = voice
      utterance.volume = Math.min(1, Math.max(0, volume))
      utterance.rate = 0.98
      utterance.pitch = 1.0

      let settled = false
      const finish = (outcome: 'ok' | 'cancelled' | 'not_allowed' | 'error') => {
        if (settled) return
        settled = true
        resolve(outcome)
      }

      utterance.onend = () => {
        finish(token === currentToken ? 'ok' : 'cancelled')
      }
      utterance.onerror = (event) => {
        const errCode = (event as SpeechSynthesisErrorEvent | undefined)?.error || ''
        if (errCode === 'canceled' || errCode === 'interrupted' || token !== currentToken) {
          finish('cancelled')
        } else if (errCode === 'not-allowed') {
          lastSpeechError = 'Browser blocked automatic speech synthesis (not-allowed).'
          finish('not_allowed')
        } else {
          lastSpeechError = `Browser speech synthesis error: ${errCode || 'unknown'}`
          finish('error')
        }
      }

      synth.speak(utterance)
    } catch (err) {
      lastSpeechError = err instanceof Error ? err.message : 'SpeechSynthesisUtterance failed.'
      resolve('error')
    }
  })
}

async function speakKannadaViaBackend(
  text: string,
  volume: number,
  token: number,
): Promise<{ outcome: 'ok' | 'cancelled' | 'not_allowed' | 'error'; voiceName?: string; errorDetail?: string }> {
  if (token !== currentToken) {
    return { outcome: 'cancelled' }
  }

  try {
    const response = await apiClient.post<Blob>(
      '/tts/kannada',
      { text },
      { responseType: 'blob', timeout: 10000 },
    )
    if (token !== currentToken) {
      return { outcome: 'cancelled' }
    }

    const voiceName = response.headers?.['x-tts-voice'] || 'edge-tts-kn'
    const blobUrl = URL.createObjectURL(response.data)
    activeAudioBlobUrl = blobUrl

    const audio = new Audio(blobUrl)
    audio.volume = Math.min(1, Math.max(0, volume))
    activeAudioElement = audio

    return await new Promise((resolve) => {
      let settled = false
      const finish = (outcome: 'ok' | 'cancelled' | 'not_allowed' | 'error', errMsg?: string) => {
        if (settled) return
        settled = true
        cleanupActiveAudio()
        if (errMsg) {
          lastSpeechError = errMsg
        }
        resolve({ outcome, voiceName, errorDetail: errMsg })
      }

      audio.onended = () => {
        finish(token === currentToken ? 'ok' : 'cancelled')
      }
      audio.onerror = () => {
        finish('error', 'Failed to decode backend Kannada audio stream.')
      }

      audio.play().catch((playErr) => {
        const msg = playErr instanceof Error ? playErr.message : String(playErr)
        if (msg.toLowerCase().includes('notallowed') || msg.toLowerCase().includes('interact')) {
          finish('not_allowed', 'Browser blocked automatic audio playback prior to user interaction.')
        } else {
          finish('error', `Audio playback error: ${msg}`)
        }
      })
    })
  } catch (err: unknown) {
    const detail =
      (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data
        ?.detail ||
      (err as { message?: string })?.message ||
      'Backend Kannada TTS is unreachable.'
    lastSpeechError = detail
    return { outcome: 'error', errorDetail: detail }
  }
}

export async function speakAnnouncement(req: SpeakRequest): Promise<SpeakResult> {
  const textNotifications = buildTextNotifications(req)

  if (req.enabled === false) {
    currentTtsProvider = 'text_fallback'
    notifyVoiceListeners()
    return {
      status: 'disabled',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      providerUsed: 'text_fallback',
      message: 'Voice alerts are disabled in Settings. Displayed as text notification.',
    }
  }

  // Cancel any in-progress speech or audio so announcements never overlap
  currentToken += 1
  const token = currentToken
  const synth = getSpeechSynthesisSafe()
  if (synth) {
    try {
      synth.cancel()
    } catch {
      // Ignore cancel exceptions
    }
  }
  cleanupActiveAudio()

  let voices: SpeechSynthesisVoice[] = []
  if (synth) {
    voices = await waitForVoicesLoaded(synth, 1500)
  }
  if (token !== currentToken) {
    return {
      status: 'unavailable',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      providerUsed: currentTtsProvider,
      message: 'Announcement superseded by a newer alert.',
    }
  }

  const enVoice = pickEnglishVoice(voices)
  const knVoice = pickKannadaVoice(voices)

  const wantsEnglish = (req.language === 'english' || req.language === 'bilingual') && Boolean(req.englishText.trim())
  const wantsKannada = (req.language === 'kannada' || req.language === 'bilingual') && Boolean(req.kannadaText.trim())

  speakingNow = true
  lastSpeechError = null
  notifyStateListeners()

  const spokenLanguages: ('english' | 'kannada')[] = []
  let usedBrowser = false
  let usedBackend = false
  let blockedAutoplay = false
  let hadError = false
  let missingEnglish = false
  let missingKannada = false

  // 1. English announcement via browser SpeechSynthesis
  if (wantsEnglish) {
    if (synth && enVoice) {
      const outcome = await speakUtteranceItem(
        synth,
        req.englishText,
        enVoice.lang || 'en-US',
        enVoice,
        req.volume,
        token,
      )
      if (outcome === 'ok') {
        spokenLanguages.push('english')
        usedBrowser = true
      } else if (outcome === 'not_allowed') {
        blockedAutoplay = true
      } else if (outcome === 'error') {
        hadError = true
      }
    } else {
      missingEnglish = true
    }
  }

  // 2. Kannada announcement: prefer verified browser kn-IN voice; NEVER use an English voice; fallback to backend edge-tts
  if (wantsKannada && !blockedAutoplay && token === currentToken) {
    if (synth && knVoice) {
      const outcome = await speakUtteranceItem(
        synth,
        req.kannadaText,
        knVoice.lang || 'kn-IN',
        knVoice,
        req.volume,
        token,
      )
      if (outcome === 'ok') {
        spokenLanguages.push('kannada')
        usedBrowser = true
      } else if (outcome === 'not_allowed') {
        blockedAutoplay = true
      } else if (outcome === 'error') {
        hadError = true
      }
    } else {
      // Browser Kannada voice missing -> try backend edge-tts fallback
      const backendRes = await speakKannadaViaBackend(req.kannadaText, req.volume, token)
      if (backendRes.outcome === 'ok') {
        spokenLanguages.push('kannada')
        usedBackend = true
      } else if (backendRes.outcome === 'not_allowed') {
        blockedAutoplay = true
      } else if (backendRes.outcome === 'error') {
        missingKannada = true
        hadError = true
      }
    }
  }

  if (token === currentToken) {
    speakingNow = false
    notifyStateListeners()
  }

  const providerUsed: TtsProviderKind =
    usedBrowser && usedBackend
      ? 'hybrid_browser_and_backend'
      : usedBrowser
        ? 'browser_speech_synthesis'
        : usedBackend
          ? 'backend_edge_tts'
          : 'text_fallback'

  currentTtsProvider = providerUsed
  notifyVoiceListeners()

  if (blockedAutoplay) {
    return {
      status: 'blocked_by_autoplay',
      spokenLanguages,
      textFallbackUsed: true,
      textNotifications,
      providerUsed,
      message:
        'Browser blocked automatic audio playback prior to user interaction. Click Play in the Voice Alert Center to hear it.',
    }
  }

  if (spokenLanguages.length === 0) {
    return {
      status: hadError ? 'error' : 'text_only_missing_voice',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      providerUsed: 'text_fallback',
      message: missingKannada
        ? `Kannada voice unavailable in browser and backend TTS failed (${lastSpeechError || 'offline'}). Displayed Kannada text notification.`
        : lastSpeechError || 'No compatible speech provider available. Displayed text notification.',
    }
  }

  if (missingKannada || missingEnglish) {
    return {
      status: 'partial_text_fallback',
      spokenLanguages,
      textFallbackUsed: true,
      textNotifications,
      providerUsed,
      message: missingKannada
        ? `Spoke English announcement; Kannada voice unavailable (${lastSpeechError || 'offline'}), shown as text notification.`
        : 'Spoke Kannada announcement; English voice unavailable, shown as text notification.',
    }
  }

  return {
    status: 'spoken',
    spokenLanguages,
    textFallbackUsed: false,
    textNotifications,
    providerUsed,
    message:
      spokenLanguages.length === 2
        ? usedBackend
          ? 'Announced in English (Browser) and Kannada (Backend edge-tts).'
          : 'Announced in English and Kannada.'
        : spokenLanguages[0] === 'kannada'
          ? usedBackend
            ? 'Announced in Kannada via backend edge-tts fallback.'
            : 'Announced in Kannada via browser voice.'
          : 'Announced in English via browser voice.',
  }
}
