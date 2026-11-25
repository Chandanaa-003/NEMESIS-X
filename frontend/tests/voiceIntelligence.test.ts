import assert from 'node:assert/strict'
import { afterEach, describe, it } from 'node:test'
import {
  announceLiveMonitoringEvent,
  buildEventAnnouncementTexts,
  classifyEventPriority,
  processDiscoveredEventsForVoice,
  resetVoiceAnnouncementSession,
} from '../src/services/eventAnnouncementService.ts'
import type { EventRecordInfo } from '../src/services/analysisService.ts'
import { DEFAULT_VOICE_SETTINGS } from '../src/services/settingsService.ts'
import {
  getVoiceCapabilities,
  isVoiceSpeaking,
  speakAnnouncement,
  stopSpeaking,
} from '../src/services/voiceService.ts'

interface SpokenCall {
  text: string
  lang: string
  volume: number
  voiceName: string | null
}

function installMockSpeechSynthesis(options: {
  voices: { name: string; lang: string }[]
  autoComplete?: boolean
  errorCode?: string | null
}) {
  const spoken: SpokenCall[] = []
  let cancelCount = 0
  let pendingFinishers: (() => void)[] = []

  class MockUtterance {
    text: string
    lang = ''
    voice: { name: string; lang: string } | null = null
    volume = 1
    rate = 1
    pitch = 1
    onend: (() => void) | null = null
    onerror: ((evt: { error: string }) => void) | null = null

    constructor(text: string) {
      this.text = text
    }
  }

  const mockSynth = {
    getVoices: () => options.voices,
    cancel: () => {
      cancelCount += 1
      for (const finish of pendingFinishers) {
        finish()
      }
      pendingFinishers = []
    },
    speak: (utterance: MockUtterance) => {
      spoken.push({
        text: utterance.text,
        lang: utterance.lang,
        volume: utterance.volume,
        voiceName: utterance.voice?.name ?? null,
      })

      const trigger = () => {
        if (options.errorCode) {
          utterance.onerror?.({ error: options.errorCode })
        } else {
          utterance.onend?.()
        }
      }

      if (options.autoComplete !== false) {
        queueMicrotask(trigger)
      } else {
        pendingFinishers.push(() => {
          utterance.onerror?.({ error: 'canceled' })
        })
      }
    },
    addEventListener: () => {},
  }

  ;(globalThis as Record<string, unknown>).window = {
    speechSynthesis: mockSynth,
  }
  ;(globalThis as Record<string, unknown>).SpeechSynthesisUtterance = MockUtterance

  return {
    spoken,
    getCancelCount: () => cancelCount,
  }
}

afterEach(() => {
  resetVoiceAnnouncementSession()
  delete (globalThis as Record<string, unknown>).window
  delete (globalThis as Record<string, unknown>).SpeechSynthesisUtterance
})

describe('Voice Intelligence & Event Announcement Tests', () => {
  it('1. English speech selects English voice and speaks text', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [{ name: 'Microsoft Aria', lang: 'en-US' }],
    })

    const res = await speakAnnouncement({
      language: 'english',
      volume: 0.75,
      englishText: 'Attention. A person entered the camera view at 10 seconds.',
      kannadaText: 'ಗಮನಿಸಿ.',
      enabled: true,
      userInitiated: true,
    })

    assert.equal(res.status, 'spoken')
    assert.deepEqual(res.spokenLanguages, ['english'])
    assert.equal(mock.spoken.length, 1)
    assert.equal(mock.spoken[0].voiceName, 'Microsoft Aria')
    assert.equal(mock.spoken[0].volume, 0.75)
  })

  it('2. Kannada speech uses kn-IN when supported', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [
        { name: 'English US', lang: 'en-US' },
        { name: 'Kannada India', lang: 'kn-IN' },
      ],
    })

    const caps = getVoiceCapabilities()
    assert.equal(caps.kannadaSupported, true)
    assert.equal(caps.kannadaVoiceLang, 'kn-IN')

    const res = await speakAnnouncement({
      language: 'kannada',
      volume: 0.9,
      englishText: 'Attention.',
      kannadaText: 'ಗಮನಿಸಿ. ಕ್ಯಾಮೆರಾ ದೃಶ್ಯದಲ್ಲಿ ಒಬ್ಬ ವ್ಯಕ್ತಿ ಕಾಣಿಸಿಕೊಂಡಿದ್ದಾರೆ.',
      enabled: true,
      userInitiated: true,
    })

    assert.equal(res.status, 'spoken')
    assert.deepEqual(res.spokenLanguages, ['kannada'])
    assert.equal(mock.spoken[0].voiceName, 'Kannada India')
    assert.equal(mock.spoken[0].lang, 'kn-IN')
  })

  it('3. Bilingual announcement speaks English then Kannada sequentially', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [
        { name: 'English India', lang: 'en-IN' },
        { name: 'Kannada India', lang: 'kn-IN' },
      ],
    })

    const res = await speakAnnouncement({
      language: 'bilingual',
      volume: 0.85,
      englishText: 'Attention. A person entered the camera view at 10 seconds.',
      kannadaText: 'ಗಮನಿಸಿ. 10 ಸೆಕೆಂಡುಗಳಲ್ಲಿ ಕ್ಯಾಮೆರಾ ದೃಶ್ಯದಲ್ಲಿ ಒಬ್ಬ ವ್ಯಕ್ತಿ ಕಾಣಿಸಿಕೊಂಡಿದ್ದಾರೆ.',
      enabled: true,
      userInitiated: true,
    })

    assert.equal(res.status, 'spoken')
    assert.deepEqual(res.spokenLanguages, ['english', 'kannada'])
    assert.equal(mock.spoken.length, 2)
    assert.equal(mock.spoken[0].lang, 'en-IN')
    assert.equal(mock.spoken[1].lang, 'kn-IN')
  })

  it('4. Voice disabled setting suppresses speech and preserves text fallback', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [{ name: 'English US', lang: 'en-US' }],
    })

    const res = await speakAnnouncement({
      language: 'english',
      volume: 0.8,
      englishText: 'Attention. Voice alert text.',
      kannadaText: 'ಗಮನಿಸಿ.',
      enabled: false,
    })

    assert.equal(res.status, 'disabled')
    assert.equal(res.textFallbackUsed, true)
    assert.deepEqual(res.textNotifications, ['Attention. Voice alert text.'])
    assert.equal(mock.spoken.length, 0)
  })

  it('5. Stop speech cancels active utterance and resets speaking state', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [{ name: 'English US', lang: 'en-US' }],
      autoComplete: false,
    })

    const speakPromise = speakAnnouncement({
      language: 'english',
      volume: 0.8,
      englishText: 'Long running announcement.',
      kannadaText: 'ಗಮನಿಸಿ.',
      enabled: true,
      userInitiated: true,
    })

    assert.equal(isVoiceSpeaking(), true)
    stopSpeaking()
    assert.equal(isVoiceSpeaking(), false)
    assert.ok(mock.getCancelCount() >= 2)
    await speakPromise
  })

  it('6. Missing Kannada voice falls back gracefully to text notification', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [{ name: 'English US', lang: 'en-US' }],
    })

    const caps = getVoiceCapabilities()
    assert.equal(caps.kannadaSupported, false)

    const knOnly = await speakAnnouncement({
      language: 'kannada',
      volume: 0.85,
      englishText: 'Attention.',
      kannadaText: 'ಗಮನಿಸಿ.',
      enabled: true,
    })
    assert.equal(knOnly.status, 'text_only_missing_voice')
    assert.equal(mock.spoken.length, 0)

    const bilingual = await speakAnnouncement({
      language: 'bilingual',
      volume: 0.85,
      englishText: 'Attention.',
      kannadaText: 'ಗಮನಿಸಿ.',
      enabled: true,
    })
    assert.equal(bilingual.status, 'partial_text_fallback')
    assert.deepEqual(bilingual.spokenLanguages, ['english'])
    assert.equal(mock.spoken.length, 1)
  })

  it('7. Duplicate event prevention & priority classification work on actual discovered events', async () => {
    const mock = installMockSpeechSynthesis({
      voices: [{ name: 'English US', lang: 'en-US' }],
    })

    const realEvent: EventRecordInfo = {
      id: 'evt-real-101',
      analysis_id: 'ana-real-101',
      event_type: 'person_entering',
      category: 'people_movement',
      title: 'Person T004 entered camera view',
      description: 'Observed tracked person T004 appearing at 00:00:07.',
      start_timestamp: 6.982,
      end_timestamp: 6.982,
      involved_track_ids: [4],
      confidence: 0.824,
      severity: 'low',
      evidence_frame_ids: [7],
      evidence_frames: [],
      explanation: {
        observed_sequence: ['Person T004 first appears at 00:00:07.'],
        why_flagged: 'Track appearance rule triggered.',
        evidence_timestamps: [6.982],
        confidence_note: 'Visual inference only.',
        requires_human_review: false,
      },
      created_at: '2026-11-25T11:28:20Z',
    }

    assert.equal(
      classifyEventPriority({
        category: realEvent.category,
        severity: realEvent.severity,
        requiresHumanReview: realEvent.explanation.requires_human_review,
      }),
      'low',
    )

    const texts = buildEventAnnouncementTexts({
      eventType: realEvent.event_type,
      timestampSeconds: realEvent.start_timestamp,
    })
    assert.match(texts.englishText, /7 seconds/)
    assert.match(texts.kannadaText, /7 ಸೆಕೆಂಡುಗಳಲ್ಲಿ/)

    const firstPass = await processDiscoveredEventsForVoice({
      analysisId: realEvent.analysis_id,
      events: [realEvent],
      settings: { ...DEFAULT_VOICE_SETTINGS, voice_language: 'english' },
      userInitiated: true,
    })
    assert.equal(firstPass.length, 1)
    assert.equal(mock.spoken.length, 1)

    // Re-processing identical event in same session must not re-announce
    const secondPass = await processDiscoveredEventsForVoice({
      analysisId: realEvent.analysis_id,
      events: [realEvent],
      settings: { ...DEFAULT_VOICE_SETTINGS, voice_language: 'english' },
      userInitiated: false,
    })
    assert.equal(secondPass.length, 0)
    assert.equal(mock.spoken.length, 1)

    // Live monitoring adapter accepts real future live events cleanly (High priority bypasses cooldown)
    const liveAlert = await announceLiveMonitoringEvent(
      {
        id: 'live-evt-1',
        streamId: 'cam-1',
        eventType: 'possible_unattended_object',
        category: 'possible_unattended_objects',
        title: 'Possible unattended object',
        timestampSeconds: 25,
        severity: 'high',
        requiresHumanReview: true,
      },
      { ...DEFAULT_VOICE_SETTINGS, voice_language: 'english' },
    )
    assert.ok(liveAlert)
    assert.equal(liveAlert.priority, 'high')
    assert.equal(mock.spoken.length, 2)

    // Cooldown suppresses rapid automatic low-priority live event right after prior speech
    const cooledDown = await announceLiveMonitoringEvent(
      {
        id: 'live-evt-2',
        streamId: 'cam-1',
        eventType: 'person_entering',
        category: 'people_movement',
        title: 'Another person entered view',
        timestampSeconds: 27,
        severity: 'low',
        requiresHumanReview: false,
      },
      { ...DEFAULT_VOICE_SETTINGS, voice_language: 'english', cooldown_seconds: 30 },
    )
    assert.equal(cooledDown, null)
    assert.equal(mock.spoken.length, 2)
  })
})
