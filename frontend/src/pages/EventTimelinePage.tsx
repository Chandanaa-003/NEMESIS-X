import { ArrowRight, Clock, Film, Loader2 } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EventDiscoverySection } from '../components/analysis/EventDiscoverySection'
import { listUserAnalyses, type AnalysisListItem } from '../services/analysisService'
import { getAuthErrorMessage } from '../services/authService'

export function EventTimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedId = searchParams.get('analysisId')

  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [selectedId, setSelectedId] = useState<string>(requestedId || '')
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    listUserAnalyses()
      .then((items) => {
        if (cancelled) return
        const completed = items.filter((item) => item.status === 'completed')
        setAnalyses(completed)

        if (requestedId && completed.some((c) => c.analysis_id === requestedId)) {
          setSelectedId(requestedId)
        } else if (completed.length > 0) {
          setSelectedId(completed[0].analysis_id)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(getAuthErrorMessage(error, 'Failed to load completed analyses.'))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [requestedId])

  const handleSelectAnalysis = (nextId: string) => {
    setSelectedId(nextId)
    setSearchParams({ analysisId: nextId })
  }

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#7C3AED]">
              <Clock className="h-3.5 w-3.5" />
              <span>Temporal Event Timeline</span>
            </span>
            <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827]">
              Discovered Event Timeline
            </h2>
            <p className="mt-1 text-sm text-[#64748B]">
              Inspect factual event sequences, involved tracks, and visual evidence frames.
            </p>
          </div>

          {analyses.length > 0 && (
            <div className="w-full sm:w-80">
              <label
                htmlFor="timeline-analysis-select"
                className="block text-xs font-semibold text-[#111827]"
              >
                Select Analyzed Video
              </label>
              <select
                id="timeline-analysis-select"
                value={selectedId}
                onChange={(e) => handleSelectAnalysis(e.target.value)}
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3.5 py-2.5 text-xs font-semibold text-[#111827] focus:border-[#2563EB] focus:bg-white focus:ring-2 focus:ring-[#2563EB]/20 focus:outline-none"
              >
                {analyses.map((item) => (
                  <option key={item.analysis_id} value={item.analysis_id}>
                    {item.video_filename} ({item.extracted_frames} frames)
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </motion.section>

      {isLoading ? (
        <div className="flex items-center justify-center rounded-3xl border border-slate-200 bg-white py-14">
          <Loader2 className="mr-2.5 h-5 w-5 animate-spin text-[#2563EB]" />
          <span className="text-sm font-medium text-[#64748B]">Loading your analyses...</span>
        </div>
      ) : loadError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-medium text-rose-700">
          {loadError}
        </div>
      ) : analyses.length === 0 ? (
        <div className="rounded-3xl border border-slate-200/90 bg-white p-10 text-center shadow-xs">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#EFF6FF] text-[#2563EB]">
            <Film className="h-6 w-6" />
          </div>
          <h3 className="mt-4 font-display text-lg font-bold text-[#111827]">
            No Completed Video Analyses Yet
          </h3>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-[#64748B]">
            Upload and process a video first so NEMESIS-X has real object detections and tracking
            histories to analyze.
          </p>
          <Link
            to="/analysis/new"
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-sm font-semibold text-white shadow-sm"
          >
            <span>Start New Analysis</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        selectedId && <EventDiscoverySection analysisId={selectedId} />
      )}
    </div>
  )
}
