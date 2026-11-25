import {
  ArrowRight,
  CheckCircle2,
  Film,
  Info,
  Radio,
  Sparkles,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  AnalysisConfigForm,
  type AnalysisConfigState,
} from '../components/analysis/AnalysisConfigForm'
import { VideoUploadDropzone } from '../components/analysis/VideoUploadDropzone'

export function NewAnalysisPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [config, setConfig] = useState<AnalysisConfigState>({
    profile: 'General',
    sensitivity: 'Balanced',
    alertLanguage: 'Both',
    voiceAlerts: true,
  })
  const [submittedNotice, setSubmittedNotice] = useState<string | null>(null)

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file)
    setSubmittedNotice(null)
  }

  const handleConfigChange = (nextConfig: AnalysisConfigState) => {
    setConfig(nextConfig)
    setSubmittedNotice(null)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedFile) return

    setSubmittedNotice(
      `Ready for "${selectedFile.name}" (${config.profile} profile, ${config.sensitivity} sensitivity, ${config.alertLanguage} alerts, voice ${
        config.voiceAlerts ? 'on' : 'off'
      }). Backend upload and AI video analysis will be connected in the next development stage.`,
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#2563EB]">
          <Sparkles className="h-3.5 w-3.5 text-[#7C3AED]" />
          <span>Analysis Setup</span>
        </span>
        <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827] sm:text-3xl">
          Start New Analysis
        </h2>
        <p className="mt-1.5 text-sm text-[#64748B] sm:text-base">
          Discover meaningful events hidden inside your videos.
        </p>

        {/* Two Source Selection Cards */}
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {/* Card 1: Recorded Video Analysis (Active) */}
          <div className="relative flex items-start justify-between gap-4 rounded-2xl border-2 border-[#2563EB] bg-[#EFF6FF]/60 p-5 shadow-2xs">
            <div className="flex items-start gap-3.5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#2563EB] text-white">
                <Film className="h-5 w-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-display text-base font-bold text-[#111827]">
                    Recorded Video Analysis
                  </h3>
                  <span className="rounded-full bg-[#2563EB]/12 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB]">
                    SELECTED
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-[#64748B]">
                  Upload an MP4, MOV, or AVI clip and configure detection, sensitivity, and alert
                  preferences below.
                </p>
              </div>
            </div>
            <CheckCircle2 className="h-5 w-5 shrink-0 text-[#2563EB]" />
          </div>

          {/* Card 2: Live Webcam Monitoring (Navigates to Coming Soon placeholder) */}
          <Link
            to="/dashboard/live"
            className="group flex items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 transition-all hover:border-[#7C3AED]/40 hover:bg-[#F5F8FC] hover:shadow-xs"
          >
            <div className="flex items-start gap-3.5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#7C3AED]/10 text-[#7C3AED] transition-colors group-hover:bg-[#7C3AED] group-hover:text-white">
                <Radio className="h-5 w-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-display text-base font-bold text-[#111827]">
                    Live Webcam Monitoring
                  </h3>
                  <span className="rounded-full border border-[#7C3AED]/20 bg-[#F5F3FF] px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#7C3AED]">
                    COMING SOON
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-[#64748B]">
                  Stream live camera feeds for real-time object tracking and instant bilingual
                  notifications.
                </p>
              </div>
            </div>
            <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-[#64748B] transition-transform group-hover:translate-x-0.5 group-hover:text-[#7C3AED]" />
          </Link>
        </div>
      </motion.section>

      {/* Main Upload + Configuration Form */}
      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-12">
        {/* Left: Video Upload Section */}
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06, ease: 'easeOut' }}
          className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs lg:col-span-7"
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="font-display text-base font-bold text-[#111827]">1. Upload Video</h3>
              <p className="text-xs text-[#64748B]">
                Choose a recorded video file from your computer to preview and configure.
              </p>
            </div>
            <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#64748B]">
              MAX 500 MB
            </span>
          </div>

          <VideoUploadDropzone selectedFile={selectedFile} onFileSelect={handleFileSelect} />
        </motion.section>

        {/* Right: Analysis Configuration + Start Button */}
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.12, ease: 'easeOut' }}
          className="flex flex-col justify-between rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs lg:col-span-5"
        >
          <div>
            <div className="mb-5">
              <h3 className="font-display text-base font-bold text-[#111827]">
                2. Analysis Configuration
              </h3>
              <p className="text-xs text-[#64748B]">
                Tailor detection and alert output before running analysis.
              </p>
            </div>

            <AnalysisConfigForm config={config} onChange={handleConfigChange} />
          </div>

          <div className="mt-7 border-t border-slate-200/80 pt-5">
            {submittedNotice && (
              <div
                role="status"
                className="mb-4 flex items-start gap-2.5 rounded-xl border border-[#2563EB]/25 bg-[#EFF6FF]/70 px-3.5 py-3 text-xs leading-relaxed text-[#111827]"
              >
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#2563EB]" />
                <span>{submittedNotice}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={!selectedFile}
              className={`flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3.5 text-sm font-semibold transition-all ${
                selectedFile
                  ? 'cursor-pointer bg-gradient-to-r from-[#2563EB] to-[#7C3AED] text-white shadow-md shadow-[#2563EB]/20 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-[#2563EB]/25'
                  : 'cursor-not-allowed border border-slate-200 bg-slate-100 text-slate-400'
              }`}
            >
              <span>Start Analysis</span>
              <ArrowRight className="h-4 w-4" />
            </button>

            {!selectedFile && (
              <p className="mt-2 text-center text-[11px] text-[#64748B]">
                Select a valid MP4, MOV, or AVI video above to enable Start Analysis.
              </p>
            )}
          </div>
        </motion.section>
      </form>
    </div>
  )
}
