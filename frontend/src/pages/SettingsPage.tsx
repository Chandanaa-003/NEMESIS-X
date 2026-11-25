import {
  AlertCircle,
  Bell,
  CheckCircle2,
  Languages,
  Loader2,
  Play,
  Save,
  Settings,
  ShieldAlert,
  Square,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState, type FormEvent } from 'react'
import { VoiceDiagnosticsPanel } from '../components/analysis/VoiceDiagnosticsPanel'
import { setActiveVoiceSettings } from '../services/eventAnnouncementService'
import { getAuthErrorMessage } from '../services/authService'
import {
  DEFAULT_VOICE_SETTINGS,
  fetchUserVoiceSettings,
  updateUserVoiceSettings,
  type UserVoiceSettings,
  type VoiceLanguageMode,
} from '../services/settingsService'
import {
  getVoiceCapabilities,
  isVoiceSpeaking,
  speakAnnouncement,
  stopSpeaking,
  subscribeVoiceCapabilities,
  subscribeVoicePlayback,
  type SpeakResult,
  type VoiceCapabilities,
} from '../services/voiceService'

const LANGUAGE_OPTIONS: {
  value: VoiceLanguageMode
  title: string
  subtitle: string
}[] = [
  {
    value: 'english',
    title: 'English',
    subtitle: 'Spoken and text alerts in English only.',
  },
  {
    value: 'kannada',
    title: 'Kannada (ಕನ್ನಡ)',
    subtitle: 'Spoken in kn-IN when supported, with Kannada text notifications.',
  },
  {
    value: 'bilingual',
    title: 'English + Kannada',
    subtitle: 'Sequential bilingual alerts in English followed by Kannada.',
  },
]

const TEST_ENGLISH_PHRASE =
  'Attention. NEMESIS-X voice alerts are active. A person entered the camera view at 10 seconds.'
const TEST_KANNADA_PHRASE =
  'ಗಮನಿಸಿ. ನೆಮೆಸಿಸ್-ಎಕ್ಸ್ ಧ್ವನಿ ಎಚ್ಚರಿಕೆಗಳು ಸಕ್ರಿಯವಾಗಿವೆ. ಕ್ಯಾಮೆರಾ ದೃಶ್ಯದಲ್ಲಿ ಒಬ್ಬ ವ್ಯಕ್ತಿ ಕಾಣಿಸಿಕೊಂಡಿದ್ದಾರೆ.'

export function SettingsPage() {
  const [formState, setFormState] = useState<UserVoiceSettings>(DEFAULT_VOICE_SETTINGS)
  const [loadedFromApi, setLoadedFromApi] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const [capabilities, setCapabilities] = useState<VoiceCapabilities>(() => getVoiceCapabilities())
  const [speaking, setSpeaking] = useState<boolean>(() => isVoiceSpeaking())
  const [testResult, setTestResult] = useState<SpeakResult | null>(null)

  useEffect(() => {
    let cancelled = false

    fetchUserVoiceSettings()
      .then((saved) => {
        if (cancelled) return
        setFormState(saved)
        setActiveVoiceSettings(saved)
        setLoadError(null)
        setLoadedFromApi(true)
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(getAuthErrorMessage(error, 'Failed to load saved workspace settings.'))
          setLoadedFromApi(true)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const unsubCaps = subscribeVoiceCapabilities(() => {
      setCapabilities(getVoiceCapabilities())
    })
    const unsubSpeak = subscribeVoicePlayback(() => {
      setSpeaking(isVoiceSpeaking())
    })
    return () => {
      unsubCaps()
      unsubSpeak()
    }
  }, [])

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSaving) return
    setIsSaving(true)
    setSaveMessage(null)
    setSaveError(null)

    try {
      const saved = await updateUserVoiceSettings({
        voice_language: formState.voice_language,
        voice_alerts_enabled: formState.voice_alerts_enabled,
        alert_volume: formState.alert_volume,
        announce_high_priority: formState.announce_high_priority,
        announce_medium_priority: formState.announce_medium_priority,
        announce_low_priority: formState.announce_low_priority,
        cooldown_seconds: formState.cooldown_seconds,
      })
      setFormState(saved)
      setActiveVoiceSettings(saved)
      setSaveMessage('Voice and alert settings saved to your account.')
    } catch (error) {
      setSaveError(getAuthErrorMessage(error, 'Failed to save workspace settings.'))
    } finally {
      setIsSaving(false)
    }
  }

  const handleTestVoice = async () => {
    setCapabilities(getVoiceCapabilities())
    const result = await speakAnnouncement({
      language: formState.voice_language,
      volume: formState.alert_volume,
      englishText: TEST_ENGLISH_PHRASE,
      kannadaText: TEST_KANNADA_PHRASE,
      enabled: formState.voice_alerts_enabled,
      userInitiated: true,
    })
    setTestResult(result)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#2563EB]">
              <Settings className="h-3.5 w-3.5 text-[#7C3AED]" />
              <span>Workspace &amp; Voice Intelligence</span>
            </span>
            <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827]">
              Voice Alert Settings
            </h2>
            <p className="mt-1 text-sm text-[#64748B]">
              Configure English and Kannada speech announcements, alert volume, and priority filters
              for discovered events.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 font-mono text-[11px] font-semibold ${
                formState.voice_alerts_enabled
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 bg-[#F5F8FC] text-[#64748B]'
              }`}
            >
              {formState.voice_alerts_enabled ? 'VOICE ALERTS ENABLED' : 'VOICE ALERTS DISABLED'}
            </span>
          </div>
        </div>
      </motion.section>

      {loadError && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{loadError}</span>
        </div>
      )}

      {!loadedFromApi ? (
        <div className="flex items-center gap-2.5 rounded-3xl border border-slate-200 bg-white p-8 text-xs font-medium text-[#64748B]">
          <Loader2 className="h-4 w-4 animate-spin text-[#2563EB]" />
          <span>Loading your saved voice preferences...</span>
        </div>
      ) : (
        <form onSubmit={handleSave} className="grid gap-6 lg:grid-cols-12">
          {/* Left column: Language, Toggle, Volume & Priorities */}
          <div className="space-y-6 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs lg:col-span-7">
            {/* Enable/Disable toggle */}
            <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200/90 bg-[#F5F8FC] p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-[#2563EB] shadow-2xs">
                  {formState.voice_alerts_enabled ? (
                    <Volume2 className="h-5 w-5" />
                  ) : (
                    <VolumeX className="h-5 w-5 text-[#64748B]" />
                  )}
                </div>
                <div>
                  <h3 className="font-display text-sm font-bold text-[#111827]">
                    Enable Voice Announcements
                  </h3>
                  <p className="text-xs text-[#64748B]">
                    When disabled, discovered events appear as silent text alerts only.
                  </p>
                </div>
              </div>

              <button
                type="button"
                role="switch"
                aria-checked={formState.voice_alerts_enabled}
                aria-label="Enable voice announcements"
                onClick={() =>
                  setFormState((prev) => ({
                    ...prev,
                    voice_alerts_enabled: !prev.voice_alerts_enabled,
                  }))
                }
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
                  formState.voice_alerts_enabled ? 'bg-[#2563EB]' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`inline-block h-4.5 w-4.5 transform rounded-full bg-white shadow-xs transition-transform ${
                    formState.voice_alerts_enabled ? 'translate-x-5.5' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Language Selector */}
            <div>
              <div className="flex items-center gap-2 text-xs font-bold tracking-wide text-[#111827]">
                <Languages className="h-4 w-4 text-[#7C3AED]" />
                <span>Voice Announcement Language</span>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                {LANGUAGE_OPTIONS.map((opt) => {
                  const selected = formState.voice_language === opt.value
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() =>
                        setFormState((prev) => ({ ...prev, voice_language: opt.value }))
                      }
                      aria-pressed={selected}
                      className={`cursor-pointer rounded-2xl border p-3.5 text-left transition-all ${
                        selected
                          ? 'border-[#2563EB] bg-[#EFF6FF] ring-2 ring-[#2563EB]/15'
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-[#F5F8FC]'
                      }`}
                    >
                      <p className="font-display text-xs font-bold text-[#111827]">{opt.title}</p>
                      <p className="mt-1 text-[11px] leading-relaxed text-[#64748B]">
                        {opt.subtitle}
                      </p>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Alert Volume */}
            <div>
              <div className="flex items-center justify-between text-xs font-bold text-[#111827]">
                <label htmlFor="voice-alert-volume" className="flex items-center gap-2">
                  <Volume2 className="h-4 w-4 text-[#2563EB]" />
                  <span>Alert Volume</span>
                </label>
                <span className="rounded-md bg-[#F5F8FC] px-2 py-0.5 font-mono text-[#2563EB]">
                  {Math.round(formState.alert_volume * 100)}%
                </span>
              </div>
              <input
                id="voice-alert-volume"
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={formState.alert_volume}
                onChange={(e) =>
                  setFormState((prev) => ({
                    ...prev,
                    alert_volume: Number(e.target.value),
                  }))
                }
                className="mt-3 w-full accent-[#2563EB]"
              />
            </div>

            {/* Alert Priorities & Cooldown */}
            <div className="space-y-3 border-t border-slate-200/80 pt-5">
              <div className="flex items-center gap-2 text-xs font-bold text-[#111827]">
                <Bell className="h-4 w-4 text-[#7C3AED]" />
                <span>Event Priority Filters &amp; Cooldown</span>
              </div>

              <div className="grid gap-2.5 sm:grid-cols-3">
                <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 bg-[#F5F8FC] p-3">
                  <input
                    type="checkbox"
                    checked={formState.announce_high_priority}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        announce_high_priority: e.target.checked,
                      }))
                    }
                    className="mt-0.5 accent-[#2563EB]"
                  />
                  <span>
                    <span className="block text-xs font-bold text-rose-700">High Priority</span>
                    <span className="text-[11px] text-[#64748B]">
                      Events requiring human review
                    </span>
                  </span>
                </label>

                <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 bg-[#F5F8FC] p-3">
                  <input
                    type="checkbox"
                    checked={formState.announce_medium_priority}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        announce_medium_priority: e.target.checked,
                      }))
                    }
                    className="mt-0.5 accent-[#2563EB]"
                  />
                  <span>
                    <span className="block text-xs font-bold text-amber-700">Medium Priority</span>
                    <span className="text-[11px] text-[#64748B]">Possible object interactions</span>
                  </span>
                </label>

                <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 bg-[#F5F8FC] p-3">
                  <input
                    type="checkbox"
                    checked={formState.announce_low_priority}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        announce_low_priority: e.target.checked,
                      }))
                    }
                    className="mt-0.5 accent-[#2563EB]"
                  />
                  <span>
                    <span className="block text-xs font-bold text-[#2563EB]">Low Priority</span>
                    <span className="text-[11px] text-[#64748B]">
                      General movement notifications
                    </span>
                  </span>
                </label>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-[#F5F8FC] px-4 py-3">
                <div>
                  <label
                    htmlFor="voice-cooldown-seconds"
                    className="block text-xs font-semibold text-[#111827]"
                  >
                    Announcement Cooldown (seconds)
                  </label>
                  <p className="text-[11px] text-[#64748B]">
                    Prevents repeated spoken alerts in rapid succession.
                  </p>
                </div>
                <input
                  id="voice-cooldown-seconds"
                  type="number"
                  min={0}
                  max={600}
                  value={formState.cooldown_seconds}
                  onChange={(e) =>
                    setFormState((prev) => ({
                      ...prev,
                      cooldown_seconds: Math.max(0, Math.min(600, Number(e.target.value) || 0)),
                    }))
                  }
                  className="w-24 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-center font-mono text-xs font-bold text-[#111827]"
                />
              </div>
            </div>

            {/* Save feedback + button */}
            {saveMessage && (
              <div
                role="status"
                className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-xs font-semibold text-emerald-800"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{saveMessage}</span>
              </div>
            )}

            {saveError && (
              <div
                role="alert"
                className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs font-semibold text-rose-700"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{saveError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-xs font-semibold text-white shadow-sm shadow-[#2563EB]/20 transition-all hover:opacity-95 disabled:opacity-65"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Saving Settings...</span>
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  <span>Save Voice Settings</span>
                </>
              )}
            </button>
          </div>

          {/* Right column: Browser Voice Diagnostics & Test Voice */}
          <div className="space-y-5 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs lg:col-span-5">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-[#2563EB]" />
              <h3 className="font-display text-base font-bold text-[#111827]">
                Browser Voice Capabilities &amp; Test
              </h3>
            </div>

            <div className="space-y-2.5 rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[#64748B]">Web Speech API</span>
                <span
                  className={`font-mono font-bold ${
                    capabilities.speechSupported ? 'text-emerald-700' : 'text-rose-700'
                  }`}
                >
                  {capabilities.speechSupported ? 'AVAILABLE' : 'UNAVAILABLE'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[#64748B]">English Voice</span>
                <span className="truncate font-mono font-semibold text-[#111827]">
                  {capabilities.englishSupported
                    ? `${capabilities.englishVoiceName} (${capabilities.englishVoiceLang})`
                    : 'Not detected'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[#64748B]">Kannada Voice (kn-IN)</span>
                <span
                  className={`truncate font-mono font-semibold ${
                    capabilities.kannadaSupported ? 'text-emerald-700' : 'text-amber-700'
                  }`}
                >
                  {capabilities.kannadaSupported
                    ? `${capabilities.kannadaVoiceName} (${capabilities.kannadaVoiceLang})`
                    : 'Not installed on browser/OS'}
                </span>
              </div>
              <p className="border-t border-slate-200 pt-2.5 leading-relaxed text-[#64748B]">
                {capabilities.statusNote}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <button
                type="button"
                onClick={() => void handleTestVoice()}
                className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-[#2563EB] px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-[#1D4ED8]"
              >
                <Play className="h-3.5 w-3.5" />
                <span>Test Voice</span>
              </button>

              <button
                type="button"
                onClick={stopSpeaking}
                disabled={!speaking}
                className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-[#111827] hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Square className="h-3.5 w-3.5" />
                <span>Stop Speech</span>
              </button>
            </div>

            {/* Text notification fallback & sample phrases */}
            <div className="space-y-2.5 rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
              <p className="text-xs font-bold text-[#111827]">
                Accessible Text Equivalents (Always Available)
              </p>
              {(formState.voice_language === 'english' ||
                formState.voice_language === 'bilingual') && (
                <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-[#111827]">
                  <span className="mb-1 block font-mono text-[10px] font-bold text-[#2563EB] uppercase">
                    English
                  </span>
                  {TEST_ENGLISH_PHRASE}
                </div>
              )}
              {(formState.voice_language === 'kannada' ||
                formState.voice_language === 'bilingual') && (
                <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-[#111827]">
                  <span className="mb-1 block font-mono text-[10px] font-bold text-[#7C3AED] uppercase">
                    Kannada (ಕನ್ನಡ)
                  </span>
                  {TEST_KANNADA_PHRASE}
                </div>
              )}

              {testResult && (
                <div
                  role="status"
                  className="rounded-xl border border-[#2563EB]/25 bg-[#EFF6FF] px-3 py-2.5 text-[11px] font-medium text-[#111827]"
                >
                  <span className="font-mono font-bold text-[#2563EB] uppercase">
                    {testResult.status}:{' '}
                  </span>
                  {testResult.message}
                </div>
              )}
            </div>
          </div>
        </form>
      )}

      <VoiceDiagnosticsPanel />
    </div>
  )
}
