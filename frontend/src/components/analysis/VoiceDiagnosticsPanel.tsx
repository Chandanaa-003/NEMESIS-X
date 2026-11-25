import { Activity, AlertTriangle, CheckCircle2, RefreshCw, Server, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  fetchBackendKannadaTtsStatus,
  getVoiceCapabilities,
  subscribeVoiceCapabilities,
  type BackendKannadaTtsStatus,
  type VoiceCapabilities,
} from '../../services/voiceService.ts'

export function VoiceDiagnosticsPanel() {
  const [caps, setCaps] = useState<VoiceCapabilities>(() => getVoiceCapabilities())
  const [backendStatus, setBackendStatus] = useState<BackendKannadaTtsStatus | null>(null)
  const [isCheckingBackend, setIsCheckingBackend] = useState(false)

  const refreshDiagnostics = useCallback(() => {
    setCaps(getVoiceCapabilities())
    setIsCheckingBackend(true)
    fetchBackendKannadaTtsStatus()
      .then((res) => setBackendStatus(res))
      .finally(() => setIsCheckingBackend(false))
  }, [])

  useEffect(() => {
    const unsub = subscribeVoiceCapabilities(() => {
      setCaps(getVoiceCapabilities())
    })
    fetchBackendKannadaTtsStatus().then((res) => setBackendStatus(res))
    return () => {
      unsub()
    }
  }, [])

  return (
    <section className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#EFF6FF] text-[#2563EB]">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-display text-base font-bold text-[#111827]">
              Voice & Kannada TTS Diagnostics
            </h3>
            <p className="text-xs text-[#64748B]">
              Live inspection of browser SpeechSynthesis voices and backend edge-tts Kannada fallback.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={refreshDiagnostics}
          disabled={isCheckingBackend}
          className="cursor-pointer inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-1.5 text-xs font-semibold text-[#111827] hover:bg-slate-100 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isCheckingBackend ? 'animate-spin text-[#2563EB]' : ''}`} />
          <span>Refresh Voices</span>
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-xs">
        {/* 1. Browser Speech Support */}
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5 space-y-1">
          <p className="font-semibold text-[#64748B]">Browser Speech Support</p>
          <p className="font-bold text-[#111827] flex items-center gap-1.5">
            {caps.speechSupported ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>Supported ({caps.totalVoices} voices loaded)</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-4 w-4 text-rose-600" />
                <span>Unsupported in this browser</span>
              </>
            )}
          </p>
        </div>

        {/* 2. Available English Voices */}
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5 space-y-1">
          <p className="font-semibold text-[#64748B]">Available English Voices</p>
          <p className="font-bold text-[#111827]">
            {caps.availableEnglishVoices.length > 0
              ? `${caps.availableEnglishVoices.length} found (${caps.englishVoiceName})`
              : 'None detected'}
          </p>
          {caps.availableEnglishVoices.length > 0 && (
            <p className="text-[11px] text-[#64748B] truncate">
              {caps.availableEnglishVoices.slice(0, 3).map((v) => `${v.name} [${v.lang}]`).join(', ')}
            </p>
          )}
        </div>

        {/* 3. Available Kannada Voices */}
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5 space-y-1">
          <p className="font-semibold text-[#64748B]">Available Browser Kannada Voices</p>
          <p className="font-bold text-[#111827] flex items-center gap-1.5">
            {caps.availableKannadaVoices.length > 0 ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>{caps.availableKannadaVoices.length} found ({caps.kannadaVoiceName})</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <span>0 browser kn-IN voices installed</span>
              </>
            )}
          </p>
        </div>

        {/* 4. Selected Voice */}
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5 space-y-1">
          <p className="font-semibold text-[#64748B]">Selected Browser Voice</p>
          <p className="font-mono text-[11px] font-bold text-[#111827] truncate">
            {caps.selectedVoice || 'None'}
          </p>
        </div>

        {/* 5. Current TTS Provider */}
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5 space-y-1">
          <p className="font-semibold text-[#64748B]">Current TTS Provider</p>
          <p className="font-mono text-[11px] font-bold text-[#2563EB] flex items-center gap-1.5">
            <Volume2 className="h-3.5 w-3.5" />
            <span>{caps.currentTtsProvider}</span>
          </p>
        </div>

        {/* 6. Speech Synthesis Errors */}
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5 space-y-1">
          <p className="font-semibold text-[#64748B]">Speech Synthesis Errors</p>
          <p className={`text-[11px] font-semibold ${caps.lastSpeechError ? 'text-rose-700' : 'text-emerald-700'}`}>
            {caps.lastSpeechError || 'No errors reported'}
          </p>
        </div>
      </div>

      {/* Backend edge-tts Fallback Status */}
      <div className="rounded-2xl border border-slate-200/90 bg-slate-50/70 p-4 text-xs space-y-1.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 font-bold text-[#111827]">
            <Server className="h-4 w-4 text-[#7C3AED]" />
            <span>Backend Kannada Fallback (edge-tts)</span>
          </div>
          <span
            className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase ${
              backendStatus?.available
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-amber-200 bg-amber-50 text-amber-800'
            }`}
          >
            {backendStatus === null
              ? 'Checking...'
              : backendStatus.available
                ? `Ready · ${backendStatus.selected_voice}`
                : 'Unavailable / Offline'}
          </span>
        </div>
        <p className="text-[#64748B]">
          {backendStatus?.available
            ? `Discovered ${backendStatus.kannada_voices.length} Kannada voice(s) dynamically (selected: ${backendStatus.selected_voice}). Requires internet access.`
            : backendStatus?.error || 'Backend TTS requires edge-tts package and internet access; text notifications will be shown if offline.'}
        </p>
      </div>
    </section>
  )
}
