import type { EventRecordInfo } from './analysisService.ts'
import { DEFAULT_VOICE_SETTINGS, type UserVoiceSettings, type VoiceLanguageMode } from './settingsService.ts'
import {
  speakAnnouncement,
  stopSpeaking,
  type VoicePlaybackStatus,
} from './voiceService.ts'

export type AlertPriority = 'high' | 'medium' | 'low'

export interface VoiceAlertRecord {
  id: string
  eventId: string
  analysisId: string
  source: 'analysis' | 'live'
  eventType: string
  eventTitle: string
  timestampSeconds: number
  priority: AlertPriority
  language: VoiceLanguageMode
  englishText: string
  kannadaText: string
  speechStatus: VoicePlaybackStatus | 'queued'
  statusNote: string
  createdAt: string
}

export interface LiveMonitoringEventInput {
  id: string
  streamId: string
  eventType: string
  category: string
  title: string
  timestampSeconds: number
  severity: 'low' | 'medium' | 'high'
  requiresHumanReview?: boolean
}

const PRIORITY_RANK: Record<AlertPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
}

type AlertListener = (alerts: VoiceAlertRecord[]) => void

let activeSettings: UserVoiceSettings = { ...DEFAULT_VOICE_SETTINGS }
let alertLog: VoiceAlertRecord[] = []
const announcedSessionKeys = new Set<string>()
let lastAutoSpokenAtMs = 0
const alertListeners = new Set<AlertListener>()

function notifyAlertListeners(): void {
  const snapshot = [...alertLog]
  for (const listener of alertListeners) {
    listener(snapshot)
  }
}

export function subscribeVoiceAlerts(listener: AlertListener): () => void {
  alertListeners.add(listener)
  listener([...alertLog])
  return () => {
    alertListeners.delete(listener)
  }
}

export function getVoiceAlertHistory(): VoiceAlertRecord[] {
  return [...alertLog]
}

export function setActiveVoiceSettings(settings: UserVoiceSettings): void {
  activeSettings = { ...settings }
}

export function getActiveVoiceSettings(): UserVoiceSettings {
  return { ...activeSettings }
}

export function resetVoiceAnnouncementSession(): void {
  announcedSessionKeys.clear()
  lastAutoSpokenAtMs = 0
  alertLog = []
  stopSpeaking()
  notifyAlertListeners()
}

export function classifyEventPriority(event: {
  category: string
  severity: string
  requiresHumanReview?: boolean
}): AlertPriority {
  if (
    event.requiresHumanReview ||
    event.severity === 'high' ||
    event.category === 'possible_unattended_objects'
  ) {
    return 'high'
  }
  if (event.category === 'object_interactions' || event.severity === 'medium') {
    return 'medium'
  }
  return 'low'
}

function isPriorityAllowed(priority: AlertPriority, settings: UserVoiceSettings): boolean {
  if (priority === 'high') return settings.announce_high_priority
  if (priority === 'medium') return settings.announce_medium_priority
  return settings.announce_low_priority
}

function formatSpokenTimestampEn(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds))
  if (rounded < 60) {
    return `${rounded} ${rounded === 1 ? 'second' : 'seconds'}`
  }
  const mins = Math.floor(rounded / 60)
  const secs = rounded % 60
  if (secs === 0) {
    return `${mins} ${mins === 1 ? 'minute' : 'minutes'}`
  }
  return `${mins} ${mins === 1 ? 'minute' : 'minutes'} and ${secs} ${secs === 1 ? 'second' : 'seconds'}`
}

function formatSpokenTimestampKn(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds))
  if (rounded < 60) {
    return `${rounded} ಸೆಕೆಂಡುಗಳಲ್ಲಿ`
  }
  const mins = Math.floor(rounded / 60)
  const secs = rounded % 60
  if (secs === 0) {
    return `${mins} ನಿಮಿಷಗಳಲ್ಲಿ`
  }
  return `${mins} ನಿಮಿಷ ${secs} ಸೆಕೆಂಡುಗಳಲ್ಲಿ`
}

export function buildEventAnnouncementTexts(params: {
  eventType: string
  timestampSeconds: number
}): { englishText: string; kannadaText: string } {
  const enTs = formatSpokenTimestampEn(params.timestampSeconds)
  const knTs = formatSpokenTimestampKn(params.timestampSeconds)

  switch (params.eventType) {
    case 'person_entering':
      return {
        englishText: `Attention. A person entered the camera view at ${enTs}.`,
        kannadaText: `ಗಮನಿಸಿ. ${knTs} ಕ್ಯಾಮೆರಾ ದೃಶ್ಯದಲ್ಲಿ ಒಬ್ಬ ವ್ಯಕ್ತಿ ಕಾಣಿಸಿಕೊಂಡಿದ್ದಾರೆ.`,
      }
    case 'person_leaving':
      return {
        englishText: `Notice. A person left the camera view at ${enTs}.`,
        kannadaText: `ಸೂಚನೆ. ${knTs} ಒಬ್ಬ ವ್ಯಕ್ತಿ ಕ್ಯಾಮೆರಾ ದೃಶ್ಯದಿಂದ ಹೊರಹೋಗಿದ್ದಾರೆ.`,
      }
    case 'person_approaching_object':
      return {
        englishText: `A possible object interaction was detected at ${enTs}. A person approached an object. Please review the evidence.`,
        kannadaText: `ಒಂದು ವಸ್ತುವಿನ ಚಲನೆ ಪತ್ತೆಯಾಗಿದೆ. ${knTs} ಒಬ್ಬ ವ್ಯಕ್ತಿ ವಸ್ತುವಿನ ಹತ್ತಿರ ಬಂದಿದ್ದಾರೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ.`,
      }
    case 'person_moving_away_from_object':
      return {
        englishText: `A possible object interaction was detected at ${enTs}. A person moved away from an object. Please review the evidence.`,
        kannadaText: `ಒಂದು ವಸ್ತುವಿನ ಚಲನೆ ಪತ್ತೆಯಾಗಿದೆ. ${knTs} ಒಬ್ಬ ವ್ಯಕ್ತಿ ವಸ್ತುವಿನಿಂದ ದೂರ ಸರಿದಿದ್ದಾರೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ.`,
      }
    case 'possible_unattended_object':
      return {
        englishText: `Attention. A possible unattended object was observed at ${enTs}. Please review the evidence.`,
        kannadaText: `ಗಮನಿಸಿ. ${knTs} ಗಮನಿಸದ ವಸ್ತು ಕಂಡುಬಂದಿದೆ. ದಯವಿಟ್ಟು ಸಾಕ್ಷ್ಯವನ್ನು ಪರಿಶೀಲಿಸಿ.`,
      }
    case 'object_disappearing':
      return {
        englishText: `Attention. A tracked object disappeared from view at ${enTs}. Please review the evidence.`,
        kannadaText: `ಗಮನಿಸಿ. ${knTs} ಗುರುತಿಸಿದ ವಸ್ತು ದೃಶ್ಯದಿಂದ ಕಣ್ಮರೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ.`,
      }
    case 'stationary_object_extended':
      return {
        englishText: `Notice. A stationary object remained in view at ${enTs}.`,
        kannadaText: `ಸೂಚನೆ. ${knTs} ಒಂದು ವಸ್ತು ಒಂದೇ ಸ್ಥಳದಲ್ಲಿ ನಿಂತಿರುವುದು ಕಂಡುಬಂದಿದೆ.`,
      }
    case 'repeated_movement_near_object':
      return {
        englishText: `Attention. Repeated movement near an object was detected at ${enTs}. Please review the evidence.`,
        kannadaText: `ಗಮನಿಸಿ. ${knTs} ವಸ್ತುವಿನ ಸಮೀಪ ಪದೇ ಪದೇ ಚಲನೆ ಪತ್ತೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ.`,
      }
    case 'multiple_people_interacting':
      return {
        englishText: `Notice. Multiple people were observed in the same area at ${enTs}.`,
        kannadaText: `ಸೂಚನೆ. ${knTs} ಒಂದೇ ಪ್ರದೇಶದಲ್ಲಿ ಹಲವರು ಕಂಡುಬಂದಿದ್ದಾರೆ.`,
      }
    default:
      return {
        englishText: `Event alert detected at ${enTs}. Please review the timeline.`,
        kannadaText: `ಗಮನಿಸಿ. ${knTs} ಚಟುವಟಿಕೆ ಪತ್ತೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ.`,
      }
  }
}

function upsertAlertRecord(record: VoiceAlertRecord): void {
  const existingIdx = alertLog.findIndex((item) => item.id === record.id)
  if (existingIdx >= 0) {
    const copy = [...alertLog]
    copy[existingIdx] = record
    alertLog = copy
  } else {
    alertLog = [record, ...alertLog].slice(0, 30)
  }
  notifyAlertListeners()
}

async function dispatchAnnouncement(params: {
  dedupKey: string
  eventId: string
  analysisId: string
  source: 'analysis' | 'live'
  eventType: string
  eventTitle: string
  timestampSeconds: number
  priority: AlertPriority
  settings: UserVoiceSettings
  userInitiated: boolean
}): Promise<VoiceAlertRecord | null> {
  if (!isPriorityAllowed(params.priority, params.settings)) {
    return null
  }

  if (!params.userInitiated) {
    if (announcedSessionKeys.has(params.dedupKey)) {
      return null
    }
    const cooldownMs = Math.max(0, params.settings.cooldown_seconds) * 1000
    if (
      cooldownMs > 0 &&
      lastAutoSpokenAtMs > 0 &&
      Date.now() - lastAutoSpokenAtMs < cooldownMs &&
      params.priority !== 'high'
    ) {
      return null
    }
  }

  announcedSessionKeys.add(params.dedupKey)
  if (!params.userInitiated && params.settings.voice_alerts_enabled) {
    lastAutoSpokenAtMs = Date.now()
  }

  const { englishText, kannadaText } = buildEventAnnouncementTexts({
    eventType: params.eventType,
    timestampSeconds: params.timestampSeconds,
  })

  const alertId = `va-${params.dedupKey}`
  const pendingRecord: VoiceAlertRecord = {
    id: alertId,
    eventId: params.eventId,
    analysisId: params.analysisId,
    source: params.source,
    eventType: params.eventType,
    eventTitle: params.eventTitle,
    timestampSeconds: params.timestampSeconds,
    priority: params.priority,
    language: params.settings.voice_language,
    englishText,
    kannadaText,
    speechStatus: 'queued',
    statusNote: params.settings.voice_alerts_enabled
      ? 'Preparing voice announcement...'
      : 'Voice alerts disabled; recorded as text alert.',
    createdAt: new Date().toISOString(),
  }
  upsertAlertRecord(pendingRecord)

  const result = await speakAnnouncement({
    language: params.settings.voice_language,
    volume: params.settings.alert_volume,
    englishText,
    kannadaText,
    enabled: params.settings.voice_alerts_enabled,
    userInitiated: params.userInitiated,
  })

  const finalized: VoiceAlertRecord = {
    ...pendingRecord,
    speechStatus: result.status,
    statusNote: result.message,
  }
  upsertAlertRecord(finalized)
  return finalized
}

/**
 * Process real backend discovered events from an analysis and announce the highest-priority
 * unannounced event without overlapping or repeating events already announced this session.
 */
export async function processDiscoveredEventsForVoice(params: {
  analysisId: string
  events: EventRecordInfo[]
  settings?: UserVoiceSettings
  userInitiated?: boolean
}): Promise<VoiceAlertRecord[]> {
  const settings = params.settings ?? activeSettings
  if (!params.events || params.events.length === 0) {
    return []
  }

  const ordered = [...params.events].sort((a, b) => {
    const pA = PRIORITY_RANK[
      classifyEventPriority({
        category: a.category,
        severity: a.severity,
        requiresHumanReview: a.explanation.requires_human_review,
      })
    ]
    const pB = PRIORITY_RANK[
      classifyEventPriority({
        category: b.category,
        severity: b.severity,
        requiresHumanReview: b.explanation.requires_human_review,
      })
    ]
    if (pA !== pB) return pA - pB
    return a.start_timestamp - b.start_timestamp
  })

  const created: VoiceAlertRecord[] = []

  // Log all newly eligible events into the alert feed, while only speaking the top unannounced alert
  let spokePrimary = false
  for (const evt of ordered) {
    const priority = classifyEventPriority({
      category: evt.category,
      severity: evt.severity,
      requiresHumanReview: evt.explanation.requires_human_review,
    })
    if (!isPriorityAllowed(priority, settings)) continue

    const dedupKey = `${params.analysisId}:${evt.id}`
    if (announcedSessionKeys.has(dedupKey)) continue

    if (!spokePrimary) {
      spokePrimary = true
      const rec = await dispatchAnnouncement({
        dedupKey,
        eventId: evt.id,
        analysisId: params.analysisId,
        source: 'analysis',
        eventType: evt.event_type,
        eventTitle: evt.title,
        timestampSeconds: evt.start_timestamp,
        priority,
        settings,
        userInitiated: Boolean(params.userInitiated),
      })
      if (rec) created.push(rec)
    } else {
      // Record remaining distinct events as text alerts ready for manual replay without voice overlap
      announcedSessionKeys.add(dedupKey)
      const { englishText, kannadaText } = buildEventAnnouncementTexts({
        eventType: evt.event_type,
        timestampSeconds: evt.start_timestamp,
      })
      const queuedCard: VoiceAlertRecord = {
        id: `va-${dedupKey}`,
        eventId: evt.id,
        analysisId: params.analysisId,
        source: 'analysis',
        eventType: evt.event_type,
        eventTitle: evt.title,
        timestampSeconds: evt.start_timestamp,
        priority,
        language: settings.voice_language,
        englishText,
        kannadaText,
        speechStatus: settings.voice_alerts_enabled ? 'partial_text_fallback' : 'disabled',
        statusNote: settings.voice_alerts_enabled
          ? 'Queued in Voice Alert Center to prevent overlapping speech. Click Play to hear.'
          : 'Voice alerts are disabled in Settings. Displayed as text alert.',
        createdAt: new Date().toISOString(),
      }
      upsertAlertRecord(queuedCard)
      created.push(queuedCard)
    }
  }

  return created
}

/**
 * Entry point prepared for upcoming Live Monitoring module: consumes real backend live events
 * using the same priority, cooldown, and deduplication safeguards.
 */
export async function announceLiveMonitoringEvent(
  liveEvent: LiveMonitoringEventInput,
  settings: UserVoiceSettings = activeSettings,
): Promise<VoiceAlertRecord | null> {
  const priority = classifyEventPriority({
    category: liveEvent.category,
    severity: liveEvent.severity,
    requiresHumanReview: liveEvent.requiresHumanReview,
  })
  const dedupKey = `live:${liveEvent.streamId}:${liveEvent.id}`

  return dispatchAnnouncement({
    dedupKey,
    eventId: liveEvent.id,
    analysisId: liveEvent.streamId,
    source: 'live',
    eventType: liveEvent.eventType,
    eventTitle: liveEvent.title,
    timestampSeconds: liveEvent.timestampSeconds,
    priority,
    settings,
    userInitiated: false,
  })
}

export async function replayVoiceAlert(
  alert: VoiceAlertRecord,
  overrideSettings?: UserVoiceSettings,
): Promise<VoiceAlertRecord> {
  const settings = overrideSettings ?? activeSettings
  const result = await speakAnnouncement({
    language: settings.voice_language,
    volume: settings.alert_volume,
    englishText: alert.englishText,
    kannadaText: alert.kannadaText,
    enabled: settings.voice_alerts_enabled,
    userInitiated: true,
  })

  const updated: VoiceAlertRecord = {
    ...alert,
    language: settings.voice_language,
    speechStatus: result.status,
    statusNote: result.message,
  }
  upsertAlertRecord(updated)
  return updated
}

export function stopAllVoiceAlerts(): void {
  stopSpeaking()
}
