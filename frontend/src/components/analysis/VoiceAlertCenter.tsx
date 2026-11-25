import {
  Bell,
  Clock,
  Play,
  Settings,
  Square,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getActiveVoiceSettings,
  replayVoiceAlert,
  stopAllVoiceAlerts,
  subscribeVoiceAlerts,
  type AlertPriority,
  type VoiceAlertRecord,
} from '../../services/eventAnnouncementService'
import { VOICE_LANGUAGE_LABELS } from '../../services/settingsService'
import {
  getVoiceCapabilities,
  isVoiceSpeaking,
  subscribeVoiceCapabilities,
  subscribeVoicePlayback,
  type VoiceCapabilities,
} from '../../services/voiceService'

function formatHms(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

const PRIORITY_BADGE: Record<AlertPriority, string> = {
  high: 'border-rose-200 bg-rose-50 text-rose-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  low: 'border-[#2563EB]/20 bg-[#EFF6FF] text-[#2563EB]',
}

export function VoiceAlertCenter({ currentAnalysisId }: { currentAnalysisId?: string }) {
  const [alerts, setAlerts] = useState<VoiceAlertRecord[]>([])
  const [speaking, setSpeaking] = useState<boolean>(() => isVoiceSpeaking())
  const [capabilities, setCapabilities] = useState<VoiceCapabilities>(() => getVoiceCapabilities())

  useEffect(() => {
    const unsubAlerts = subscribeVoiceAlerts((list) => {
      setAlerts(list)
    })
    const unsubSpeak = subscribeVoicePlayback(() => {
      setSpeaking(isVoiceSpeaking())
    })
    const unsubCaps = subscribeVoiceCapabilities(() => {
      setCapabilities(getVoiceCapabilities())
    })
    return () => {
      unsubAlerts()
      unsubSpeak()
      unsubCaps()
    }
  }, [])

  const settings = getActiveVoiceSettings()
  const visibleAlerts = currentAnalysisId
    ? alerts.filter((a) => a.analysisId === currentAnalysisId || a.source === 'live')
    : alerts

  return (
    <section
      aria-labelledby="voice-alert-center-heading"
      className="space-y-4 rounded-2xl border border-slate-200/90 bg-[#F5F8FC]/75 p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-[#7C3AED] shadow-2xs">
            {settings.voice_alerts_enabled ? (
              <Volume2 className="h-5 w-5" />
            ) : (
              <VolumeX className="h-5 w-5 text-[#64748B]" />
            )}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h4
                id="voice-alert-center-heading"
                className="font-display text-base font-bold text-[#111827]"
              >
                Voice Alert Center
              </h4>
              <span
                className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase ${
                  speaking
                    ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                    : settings.voice_alerts_enabled
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 bg-white text-[#64748B]'
                }`}
              >
                {speaking
                  ? 'Speaking...'
                  : settings.voice_alerts_enabled
                    ? `Active · ${VOICE_LANGUAGE_LABELS[settings.voice_language]}`
                    : 'Voice Disabled (Text Mode)'}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-[#64748B]">{capabilities.statusNote}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={stopAllVoiceAlerts}
            disabled={!speaking}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-[#111827] hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Square className="h-3.5 w-3.5" />
            <span>Stop</span>
          </button>

          <Link
            to="/dashboard/settings"
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-[#111827] hover:border-[#2563EB]/40 hover:text-[#2563EB]"
          >
            <Settings className="h-3.5 w-3.5" />
            <span>Voice Settings</span>
          </Link>
        </div>
      </div>

      {visibleAlerts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center">
          <Bell className="mx-auto h-6 w-6 text-[#64748B]" />
          <p className="mt-2 text-xs font-semibold text-[#111827]">No voice alerts triggered yet</p>
          <p className="mx-auto mt-1 max-w-md text-[11px] text-[#64748B]">
            Voice announcements are generated only from actual discovered events matching your
            configured priorities.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleAlerts.map((alert) => (
            <article
              key={alert.id}
              className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-2xs"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${PRIORITY_BADGE[alert.priority]}`}
                    >
                      {alert.priority} priority
                    </span>
                    <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-2 py-0.5 text-[10px] font-semibold text-[#64748B]">
                      {VOICE_LANGUAGE_LABELS[alert.language]}
                    </span>
                    <span className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-[#2563EB]">
                      <Clock className="h-3 w-3" />
                      {formatHms(alert.timestampSeconds)} ({alert.timestampSeconds.toFixed(1)}s)
                    </span>
                  </div>
                  <h5 className="font-display text-sm font-bold text-[#111827]">
                    {alert.eventTitle}
                  </h5>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void replayVoiceAlert(alert)}
                    className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-[#2563EB] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1D4ED8]"
                  >
                    <Play className="h-3 w-3" />
                    <span>Play</span>
                  </button>
                  <button
                    type="button"
                    onClick={stopAllVoiceAlerts}
                    disabled={!speaking}
                    className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-1.5 text-xs font-semibold text-[#111827] hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <Square className="h-3 w-3" />
                    <span>Stop</span>
                  </button>
                </div>
              </div>

              <div className="mt-3 space-y-1.5 rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3 text-xs text-[#111827]">
                {(alert.language === 'english' || alert.language === 'bilingual') && (
                  <p>
                    <span className="mr-1.5 font-mono text-[10px] font-bold text-[#2563EB] uppercase">
                      EN:
                    </span>
                    {alert.englishText}
                  </p>
                )}
                {(alert.language === 'kannada' || alert.language === 'bilingual') && (
                  <p>
                    <span className="mr-1.5 font-mono text-[10px] font-bold text-[#7C3AED] uppercase">
                      KN:
                    </span>
                    {alert.kannadaText}
                  </p>
                )}
              </div>

              <p className="mt-2 font-mono text-[10px] text-[#64748B]">
                Status: {alert.statusNote}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
