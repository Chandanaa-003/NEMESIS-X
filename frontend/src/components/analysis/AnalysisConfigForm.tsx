import { Languages, Sliders, Volume2 } from 'lucide-react'

export type AnalysisProfile = 'General' | 'Traffic' | 'Classroom' | 'Retail' | 'Industrial'
export type DetectionSensitivity = 'Low' | 'Balanced' | 'High'
export type AlertLanguage = 'English' | 'Kannada' | 'Both'

export interface AnalysisConfigState {
  profile: AnalysisProfile
  sensitivity: DetectionSensitivity
  alertLanguage: AlertLanguage
  voiceAlerts: boolean
}

const ANALYSIS_PROFILES: { value: AnalysisProfile; label: string }[] = [
  { value: 'General', label: 'General' },
  { value: 'Traffic', label: 'Traffic' },
  { value: 'Classroom', label: 'Classroom' },
  { value: 'Retail', label: 'Retail' },
  { value: 'Industrial', label: 'Industrial' },
]

const SENSITIVITY_OPTIONS: DetectionSensitivity[] = ['Low', 'Balanced', 'High']
const ALERT_LANGUAGE_OPTIONS: AlertLanguage[] = ['English', 'Kannada', 'Both']

interface AnalysisConfigFormProps {
  config: AnalysisConfigState
  onChange: (next: AnalysisConfigState) => void
}

export function AnalysisConfigForm({ config, onChange }: AnalysisConfigFormProps) {
  return (
    <div className="space-y-6">
      {/* Analysis Profile */}
      <div>
        <label
          htmlFor="analysis-profile"
          className="flex items-center gap-2 text-xs font-semibold tracking-wide text-[#111827]"
        >
          <Sliders className="h-3.5 w-3.5 text-[#2563EB]" />
          <span>Analysis Profile</span>
        </label>
        <select
          id="analysis-profile"
          value={config.profile}
          onChange={(e) =>
            onChange({ ...config, profile: e.target.value as AnalysisProfile })
          }
          className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-medium text-[#111827] transition-colors focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 focus:outline-none"
        >
          {ANALYSIS_PROFILES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <p className="mt-1.5 text-xs leading-relaxed text-[#64748B]">
          Select the environment that matches your footage so event discovery focuses on relevant
          objects and scene behaviors.
        </p>
      </div>

      {/* Detection Sensitivity */}
      <div>
        <span className="block text-xs font-semibold tracking-wide text-[#111827]">
          Detection Sensitivity
        </span>
        <div className="mt-2 grid grid-cols-3 gap-2">
          {SENSITIVITY_OPTIONS.map((option) => {
            const active = config.sensitivity === option
            return (
              <button
                key={option}
                type="button"
                onClick={() => onChange({ ...config, sensitivity: option })}
                aria-pressed={active}
                className={`cursor-pointer rounded-xl border px-3 py-2.5 text-xs font-semibold transition-all ${
                  active
                    ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB] shadow-2xs'
                    : 'border-slate-200 bg-white text-[#64748B] hover:border-slate-300 hover:bg-[#F5F8FC] hover:text-[#111827]'
                }`}
              >
                {option}
              </button>
            )
          })}
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-[#64748B]">
          Controls how easily unusual activity is flagged. Balanced fits most clips, while High
          surfaces subtle motion or brief events.
        </p>
      </div>

      {/* Alert Language */}
      <div>
        <span className="flex items-center gap-2 text-xs font-semibold tracking-wide text-[#111827]">
          <Languages className="h-3.5 w-3.5 text-[#7C3AED]" />
          <span>Alert Language</span>
        </span>
        <div className="mt-2 grid grid-cols-3 gap-2">
          {ALERT_LANGUAGE_OPTIONS.map((option) => {
            const active = config.alertLanguage === option
            return (
              <button
                key={option}
                type="button"
                onClick={() => onChange({ ...config, alertLanguage: option })}
                aria-pressed={active}
                className={`cursor-pointer rounded-xl border px-3 py-2.5 text-xs font-semibold transition-all ${
                  active
                    ? 'border-[#7C3AED] bg-[#F5F3FF] text-[#7C3AED] shadow-2xs'
                    : 'border-slate-200 bg-white text-[#64748B] hover:border-slate-300 hover:bg-[#F5F8FC] hover:text-[#111827]'
                }`}
              >
                {option}
              </button>
            )
          })}
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-[#64748B]">
          Choose whether generated incident alerts and summaries appear in English, Kannada, or
          both languages together.
        </p>
      </div>

      {/* Voice Alerts Toggle */}
      <div className="rounded-2xl border border-slate-200/90 bg-[#F5F8FC] p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-[#2563EB] shadow-2xs">
              <Volume2 className="h-4.5 w-4.5" />
            </div>
            <div>
              <span className="block text-xs font-semibold text-[#111827]">Voice Alerts</span>
              <span className="text-[11px] text-[#64748B]">
                {config.voiceAlerts ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={config.voiceAlerts}
            aria-label="Toggle voice alerts"
            onClick={() => onChange({ ...config, voiceAlerts: !config.voiceAlerts })}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]/40 ${
              config.voiceAlerts ? 'bg-[#2563EB]' : 'bg-slate-300'
            }`}
          >
            <span
              className={`inline-block h-4.5 w-4.5 transform rounded-full bg-white shadow-xs transition-transform ${
                config.voiceAlerts ? 'translate-x-5.5' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        <p className="mt-2.5 text-xs leading-relaxed text-[#64748B]">
          When turned on, future real-time alerts can be read aloud in your chosen alert language
          whenever a notable event is detected.
        </p>
      </div>
    </div>
  )
}
