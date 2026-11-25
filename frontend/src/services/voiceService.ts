import type { VoiceLanguageMode } from './settingsService.ts'

export type VoicePlaybackStatus =
  | 'spoken'
  | 'partial_text_fallback'
  | 'text_only_missing_voice'
  | 'disabled'
  | 'blocked_by_autoplay'
  | 'unavailable'
  | 'error'

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
  message: string
}

type VoidListener = () => void

let currentToken = 0
let speakingNow = false
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
      statusNote:
        'Web Speech API (speechSynthesis) is not supported in this browser. Text notifications will be shown instead.',
    }
  }

  let voices: SpeechSynthesisVoice[] = []
  try {
    voices = synth.getVoices() || []
  } catch {
    voices = []
  }

  const enVoice = pickEnglishVoice(voices)
  const knVoice = pickKannadaVoice(voices)

  let statusNote = ''
  if (voices.length === 0) {
    statusNote =
      'No browser speech voices are loaded yet. If speech is unavailable on this device, alerts appear as text notifications.'
  } else if (enVoice && knVoice) {
    statusNote = `Both English (${enVoice.lang}) and Kannada (${knVoice.lang}) voices are available on this browser.`
  } else if (enVoice && !knVoice) {
    statusNote =
      'English speech is available, but no Kannada (kn-IN) voice is installed on this browser/OS. Kannada announcements will appear as text notifications.'
  } else if (!enVoice && knVoice) {
    statusNote = `Kannada (${knVoice.lang}) voice is available, but no English voice was found.`
  } else {
    statusNote =
      'No English or Kannada speech voices were found in this browser. Text notifications will be used.'
  }

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
  voice: SpeechSynthesisVoice | null,
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
      utterance.lang = voice?.lang || lang
      if (voice) {
        utterance.voice = voice
      }
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
          finish('not_allowed')
        } else {
          finish('error')
        }
      }

      synth.speak(utterance)
    } catch {
      resolve('error')
    }
  })
}

export async function speakAnnouncement(req: SpeakRequest): Promise<SpeakResult> {
  const textNotifications = buildTextNotifications(req)

  if (req.enabled === false) {
    return {
      status: 'disabled',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      message: 'Voice alerts are disabled in Settings. Displayed as text notification.',
    }
  }

  const synth = getSpeechSynthesisSafe()
  if (!synth) {
    return {
      status: 'unavailable',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      message: 'Web Speech API is unavailable in this browser. Showing text alert.',
    }
  }

  let voices: SpeechSynthesisVoice[] = []
  try {
    voices = synth.getVoices() || []
  } catch {
    voices = []
  }

  const enVoice = pickEnglishVoice(voices)
  const knVoice = pickKannadaVoice(voices)

  const queue: { langKey: 'english' | 'kannada'; text: string; langTag: string; voice: SpeechSynthesisVoice }[] = []
  let missingKannada = false
  let missingEnglish = false

  if (req.language === 'english' || req.language === 'bilingual') {
    if (enVoice && req.englishText.trim()) {
      queue.push({
        langKey: 'english',
        text: req.englishText,
        langTag: enVoice.lang || 'en-US',
        voice: enVoice,
      })
    } else if (req.englishText.trim()) {
      missingEnglish = true
    }
  }

  if (req.language === 'kannada' || req.language === 'bilingual') {
    if (knVoice && req.kannadaText.trim()) {
      queue.push({
        langKey: 'kannada',
        text: req.kannadaText,
        langTag: knVoice.lang || 'kn-IN',
        voice: knVoice,
      })
    } else if (req.kannadaText.trim()) {
      missingKannada = true
    }
  }

  if (queue.length === 0) {
    return {
      status: 'text_only_missing_voice',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      message: missingKannada
        ? 'Kannada (kn-IN) voice is not available on this browser. Displayed Kannada text notification instead.'
        : 'No compatible browser speech voice was detected. Displayed text notification instead.',
    }
  }

  // Cancel any in-progress speech so announcements never overlap
  currentToken += 1
  const token = currentToken
  try {
    synth.cancel()
  } catch {
    // Ignore cancel exceptions
  }

  speakingNow = true
  notifyStateListeners()

  const spokenLanguages: ('english' | 'kannada')[] = []
  let blockedAutoplay = false
  let hadError = false

  for (const item of queue) {
    if (token !== currentToken) break
    const outcome = await speakUtteranceItem(
      synth,
      item.text,
      item.langTag,
      item.voice,
      req.volume,
      token,
    )
    if (outcome === 'ok') {
      spokenLanguages.push(item.langKey)
    } else if (outcome === 'not_allowed') {
      blockedAutoplay = true
      break
    } else if (outcome === 'error') {
      hadError = true
    } else if (outcome === 'cancelled') {
      break
    }
  }

  if (token === currentToken) {
    speakingNow = false
    notifyStateListeners()
  }

  if (blockedAutoplay) {
    return {
      status: 'blocked_by_autoplay',
      spokenLanguages,
      textFallbackUsed: true,
      textNotifications,
      message:
        'Browser blocked automatic audio playback prior to user interaction. Click Play in the Voice Alert Center to hear it.',
    }
  }

  if (spokenLanguages.length === 0 && hadError) {
    return {
      status: 'error',
      spokenLanguages: [],
      textFallbackUsed: true,
      textNotifications,
      message: 'Speech synthesis failed on this device. Showing text notification.',
    }
  }

  if (missingKannada || missingEnglish) {
    return {
      status: 'partial_text_fallback',
      spokenLanguages,
      textFallbackUsed: true,
      textNotifications,
      message: missingKannada
        ? 'Spoke English announcement; Kannada (kn-IN) voice unavailable, shown as text notification.'
        : 'Spoke Kannada announcement; English voice unavailable, shown as text notification.',
    }
  }

  return {
    status: 'spoken',
    spokenLanguages,
    textFallbackUsed: false,
    textNotifications,
    message:
      spokenLanguages.length === 2
        ? 'Announced in English and Kannada.'
        : `Announced in ${spokenLanguages[0] === 'kannada' ? 'Kannada' : 'English'}.`,
  }
}
