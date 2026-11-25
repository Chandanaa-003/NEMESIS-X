import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Film,
  Loader2,
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
import { getAuthErrorMessage } from '../services/authService'
import { uploadVideoFile, type VideoRecord } from '../services/videoService'

export function NewAnalysisPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [config, setConfig] = useState<AnalysisConfigState>({
    profile: 'General',
    sensitivity: 'Balanced',
    alertLanguage: 'Both',
    voiceAlerts: true,
  })
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadedVideo, setUploadedVideo] = useState<VideoRecord | null>(null)

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file)
    setUploadError(null)
    setUploadedVideo(null)
    setUploadProgress(0)
  }

  const handleConfigChange = (nextConfig: AnalysisConfigState) => {
    setConfig(nextConfig)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedFile || isUploading) return

    setIsUploading(true)
    setUploadProgress(0)
    setUploadError(null)
    setUploadedVideo(null)

    try {
      const record = await uploadVideoFile(selectedFile, (percent) => {
        setUploadProgress(percent)
      })
      setUploadedVideo(record)
    } catch (error) {
      setUploadError(
        getAuthErrorMessage(error, 'Failed to upload video. Please check the file and try again.'),
      )
    } finally {
      setIsUploading(false)
    }
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
                Choose a recorded video file from your computer to preview and upload.
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
                Tailor detection and alert output before uploading.
              </p>
            </div>

            <AnalysisConfigForm config={config} onChange={handleConfigChange} />
          </div>

          <div className="mt-7 border-t border-slate-200/80 pt-5">
            {isUploading && (
              <div className="mb-4 rounded-xl border border-slate-200 bg-[#F5F8FC] p-3">
                <div className="flex items-center justify-between text-xs font-semibold text-[#111827]">
                  <span>Uploading video to storage...</span>
                  <span className="font-mono text-[#2563EB]">{uploadProgress}%</span>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    style={{ width: `${uploadProgress}%` }}
                    className="h-full rounded-full bg-gradient-to-r from-[#2563EB] to-[#7C3AED] transition-all duration-150"
                  />
                </div>
              </div>
            )}

            {uploadError && (
              <div
                role="alert"
                className="mb-4 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-xs leading-relaxed font-medium text-rose-700"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadedVideo && (
              <div
                role="status"
                className="mb-4 space-y-1.5 rounded-xl border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-xs text-emerald-950"
              >
                <div className="flex items-center gap-2 font-semibold text-emerald-800">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>Video Uploaded Successfully</span>
                </div>
                <p className="font-mono text-[11px] text-emerald-900">
                  ID: {uploadedVideo.id} · Status: {uploadedVideo.status}
                </p>
                <p className="text-[11px] leading-relaxed text-emerald-800">
                  Saved to <code className="font-mono">{uploadedVideo.file_path}</code> with{' '}
                  {config.profile} profile ({config.sensitivity} sensitivity, {config.alertLanguage}{' '}
                  alerts). AI processing pipeline will run in the next development stage.
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={!selectedFile || isUploading}
              className={`flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3.5 text-sm font-semibold transition-all ${
                selectedFile && !isUploading
                  ? 'cursor-pointer bg-gradient-to-r from-[#2563EB] to-[#7C3AED] text-white shadow-md shadow-[#2563EB]/20 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-[#2563EB]/25'
                  : 'cursor-not-allowed border border-slate-200 bg-slate-100 text-slate-400'
              }`}
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Uploading Video ({uploadProgress}%)</span>
                </>
              ) : (
                <>
                  <span>Start Analysis</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
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
