import {
  AlertCircle,
  ArrowRight,
  Calendar,
  Clock,
  FileDown,
  Film,
  ImageOff,
  Loader2,
  Maximize2,
  Radio,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PdfDownloadButton } from '../components/analysis/PdfDownloadButton'
import {
  discoverAnalysisEvents,
  fetchEvidenceImageBlobUrl,
  getAnalysisEvidence,
  listUserAnalyses,
  type AnalysisListItem,
  type EvidenceItemInfo,
  type EvidenceType,
} from '../services/analysisService'
import { getAuthErrorMessage } from '../services/authService'
import {
  downloadLiveSessionPdfReport,
  fetchLiveEventSnapshotBlobUrl,
  getLiveSessionEvidence,
  listLiveMonitoringSessions,
  type LiveSessionStatusResponse,
} from '../services/liveService'

type CategoryFilter =
  | 'all'
  | 'people_movement'
  | 'object_interactions'
  | 'possible_unattended_objects'

const CATEGORY_FILTERS: { value: CategoryFilter; label: string }[] = [
  { value: 'all', label: 'All evidence' },
  { value: 'people_movement', label: 'People movement' },
  { value: 'object_interactions', label: 'Object interactions' },
  { value: 'possible_unattended_objects', label: 'Possible unattended objects' },
]

const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  original_frame: 'Original Frame',
  annotated_detection: 'Annotated Detection',
  annotated_tracking: 'Annotated Tracking',
}

function formatHms(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatTrackCode(trackId: number): string {
  return `T${String(trackId).padStart(3, '0')}`
}

interface EvidenceGroup {
  key: string
  event_id: string
  analysis_id: string
  frame_number: number
  timestamp_seconds: number
  event_title: string
  event_category: string
  event_severity: string
  event_confidence: number
  why_flagged: string
  involved_track_ids: number[]
  detection_count: number
  detection_summary: string[]
  created_at: string
  artifacts: Partial<Record<EvidenceType, EvidenceItemInfo>>
}

function AuthenticatedEvidenceImg({
  evidenceId,
  liveSessionId,
  eventId,
  alt,
  className,
}: {
  evidenceId: string
  liveSessionId?: string
  eventId?: string
  alt: string
  className: string
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    let createdUrl: string | null = null

    const loader =
      liveSessionId && eventId
        ? fetchLiveEventSnapshotBlobUrl(liveSessionId, eventId)
        : fetchEvidenceImageBlobUrl(evidenceId)

    loader
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setBlobUrl(url)
      })
      .catch(() => {
        if (active) setFailed(true)
      })

    return () => {
      active = false
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl)
      }
    }
  }, [evidenceId, liveSessionId, eventId])

  if (failed) {
    return (
      <div className="flex aspect-video w-full items-center justify-center bg-[#F5F8FC] text-[#64748B]">
        <ImageOff className="h-5 w-5" />
      </div>
    )
  }

  if (!blobUrl) {
    return <div className="aspect-video w-full animate-pulse bg-slate-100" />
  }

  return <img src={blobUrl} alt={alt} className={className} />
}

function EvidenceGroupCard({
  group,
  isLiveMode,
  onOpenPreview,
}: {
  group: EvidenceGroup
  isLiveMode: boolean
  onOpenPreview: (group: EvidenceGroup, initialType: EvidenceType) => void
}) {
  const annotated =
    group.artifacts.annotated_tracking ?? group.artifacts.annotated_detection ?? null
  const original = group.artifacts.original_frame ?? null
  const defaultPreviewType: EvidenceType = annotated
    ? annotated.evidence_type
    : 'original_frame'

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-xs transition-shadow hover:shadow-md hover:shadow-slate-200/60">
      {/* Side-by-side Original vs Annotated comparison */}
      <div className="grid grid-cols-2 gap-px bg-slate-200">
        <div className="bg-[#F5F8FC]">
          {original ? (
            <button
              type="button"
              onClick={() => onOpenPreview(group, 'original_frame')}
              className="group relative block w-full cursor-pointer text-left"
            >
              <AuthenticatedEvidenceImg
                evidenceId={original.id}
                alt={`Original frame #${group.frame_number}`}
                className="aspect-video w-full object-cover"
              />
              <span className="absolute bottom-1.5 left-1.5 rounded bg-white/90 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#111827] shadow-2xs">
                Original
              </span>
            </button>
          ) : (
            <div className="flex aspect-video items-center justify-center text-xs text-[#64748B]">
              No original copy
            </div>
          )}
        </div>

        <div className="bg-[#F5F8FC]">
          {annotated ? (
            <button
              type="button"
              onClick={() => onOpenPreview(group, annotated.evidence_type)}
              className="group relative block w-full cursor-pointer text-left"
            >
              <AuthenticatedEvidenceImg
                evidenceId={annotated.id}
                liveSessionId={isLiveMode ? group.analysis_id : undefined}
                eventId={isLiveMode ? group.event_id : undefined}
                alt={`Annotated frame #${group.frame_number}`}
                className="aspect-video w-full object-cover"
              />
              <span className="absolute bottom-1.5 left-1.5 rounded bg-[#2563EB]/90 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white shadow-2xs">
                {EVIDENCE_TYPE_LABELS[annotated.evidence_type]}
              </span>
            </button>
          ) : (
            <div className="flex aspect-video items-center justify-center text-xs text-[#64748B]">
              No annotation
            </div>
          )}
        </div>
      </div>

      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1 rounded-md bg-[#EFF6FF] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#2563EB]">
            <Clock className="h-3 w-3" />
            {formatHms(group.timestamp_seconds)} ({group.timestamp_seconds.toFixed(2)}s)
          </span>
          <span className="rounded-md border border-slate-200 bg-[#F5F8FC] px-2 py-0.5 font-mono text-[10px] font-semibold text-[#7C3AED]">
            {Math.round(group.event_confidence * 100)}% conf
          </span>
        </div>

        <h3 className="font-display text-sm font-bold text-[#111827]">{group.event_title}</h3>

        {group.why_flagged && (
          <p className="text-xs leading-relaxed text-[#64748B]">{group.why_flagged}</p>
        )}

        {group.involved_track_ids.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[11px] font-semibold text-[#111827]">Tracks:</span>
            {group.involved_track_ids.map((tid) => (
              <span
                key={tid}
                className="rounded bg-[#2563EB]/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB]"
              >
                {formatTrackCode(tid)}
              </span>
            ))}
          </div>
        )}

        {group.detection_summary.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {group.detection_summary.slice(0, 3).map((det, idx) => (
              <span
                key={idx}
                className="rounded border border-slate-200 bg-[#F5F8FC] px-1.5 py-0.5 font-mono text-[10px] text-[#111827]"
              >
                {det}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-100 pt-2.5">
          <span className="inline-flex items-center gap-1 font-mono text-[10px] text-[#64748B]">
            <Calendar className="h-3 w-3" />
            {new Date(group.created_at).toLocaleDateString()}
          </span>

          <button
            type="button"
            onClick={() => onOpenPreview(group, defaultPreviewType)}
            className="inline-flex cursor-pointer items-center gap-1 text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8]"
          >
            <Maximize2 className="h-3.5 w-3.5" />
            <span>Larger Preview</span>
          </button>
        </div>
      </div>
    </article>
  )
}

export function EvidenceCenterPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedId = searchParams.get('analysisId')
  const requestedLiveId = searchParams.get('liveSessionId')

  const [sourceMode, setSourceMode] = useState<'video' | 'live'>(() =>
    requestedLiveId ? 'live' : 'video',
  )
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [liveSessions, setLiveSessions] = useState<LiveSessionStatusResponse[]>([])
  const [selectedId, setSelectedId] = useState<string>(requestedId || '')
  const [selectedLiveId, setSelectedLiveId] = useState<string>(requestedLiveId || '')
  const [analysesLoaded, setAnalysesLoaded] = useState(false)
  const [isDownloadingLivePdf, setIsDownloadingLivePdf] = useState(false)

  const [evidenceItems, setEvidenceItems] = useState<EvidenceItemInfo[]>([])
  const [loadedEvidenceFor, setLoadedEvidenceFor] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [isGeneratingEvidence, setIsGeneratingEvidence] = useState(false)

  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
  const [timeQuery, setTimeQuery] = useState('')
  const [dateFilter, setDateFilter] = useState('')

  const [previewState, setPreviewState] = useState<{
    group: EvidenceGroup
    activeType: EvidenceType
  } | null>(null)

  useEffect(() => {
    let cancelled = false

    Promise.all([listUserAnalyses(), listLiveMonitoringSessions().catch(() => [])])
      .then(([items, liveList]) => {
        if (cancelled) return
        const completed = items.filter((item) => item.status === 'completed')
        setAnalyses(completed)
        setLiveSessions(liveList)

        if (requestedId && completed.some((c) => c.analysis_id === requestedId)) {
          setSelectedId(requestedId)
        } else if (completed.length > 0) {
          setSelectedId(completed[0].analysis_id)
        }

        if (requestedLiveId && liveList.some((s) => s.session_id === requestedLiveId)) {
          setSelectedLiveId(requestedLiveId)
          setSourceMode('live')
        } else if (liveList.length > 0) {
          setSelectedLiveId(liveList[0].session_id)
        }

        setAnalysesLoaded(true)
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMsg(getAuthErrorMessage(error, 'Failed to load completed analyses.'))
          setAnalysesLoaded(true)
        }
      })

    return () => {
      cancelled = true
    }
  }, [requestedId, requestedLiveId])

  const activeTargetKey =
    sourceMode === 'live'
      ? selectedLiveId
        ? `live:${selectedLiveId}`
        : ''
      : selectedId
        ? `video:${selectedId}`
        : ''

  useEffect(() => {
    if (!activeTargetKey) return
    let cancelled = false

    const loader =
      sourceMode === 'live'
        ? getLiveSessionEvidence(selectedLiveId)
        : getAnalysisEvidence(selectedId)

    loader
      .then((data) => {
        if (!cancelled) {
          setEvidenceItems(data.evidence)
          setErrorMsg(null)
          setLoadedEvidenceFor(activeTargetKey)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMsg(getAuthErrorMessage(error, 'Failed to load evidence artifacts.'))
          setLoadedEvidenceFor(activeTargetKey)
        }
      })

    return () => {
      cancelled = true
    }
  }, [activeTargetKey, sourceMode, selectedId, selectedLiveId])

  const handleSelectAnalysis = (nextId: string) => {
    setSelectedId(nextId)
    setSearchParams({ analysisId: nextId })
  }

  const handleSelectLiveSession = (nextId: string) => {
    setSelectedLiveId(nextId)
    setSearchParams({ liveSessionId: nextId })
  }

  const handleSwitchMode = (nextMode: 'video' | 'live') => {
    setSourceMode(nextMode)
    setEvidenceItems([])
    if (nextMode === 'live' && selectedLiveId) {
      setSearchParams({ liveSessionId: selectedLiveId })
    } else if (nextMode === 'video' && selectedId) {
      setSearchParams({ analysisId: selectedId })
    }
  }

  const handleDownloadLivePdf = async () => {
    if (!selectedLiveId || isDownloadingLivePdf) return
    setIsDownloadingLivePdf(true)
    try {
      await downloadLiveSessionPdfReport(selectedLiveId)
    } catch (error) {
      setErrorMsg(getAuthErrorMessage(error, 'Failed to download live session PDF report.'))
    } finally {
      setIsDownloadingLivePdf(false)
    }
  }

  const handleRunDiscoveryAndEvidence = async () => {
    if (sourceMode === 'live' || !selectedId || isGeneratingEvidence) return
    setIsGeneratingEvidence(true)
    setErrorMsg(null)
    try {
      await discoverAnalysisEvents(selectedId)
      const data = await getAnalysisEvidence(selectedId)
      setEvidenceItems(data.evidence)
      setLoadedEvidenceFor(selectedId)
    } catch (error) {
      setErrorMsg(getAuthErrorMessage(error, 'Failed to collect event evidence.'))
    } finally {
      setIsGeneratingEvidence(false)
    }
  }

  const groupedEvidence = useMemo(() => {
    const map = new Map<string, EvidenceGroup>()
    for (const item of evidenceItems) {
      const key = `${item.event_id}-${item.frame_number}`
      let group = map.get(key)
      if (!group) {
        group = {
          key,
          event_id: item.event_id,
          analysis_id: item.analysis_id,
          frame_number: item.frame_number,
          timestamp_seconds: item.timestamp_seconds,
          event_title: item.event_title,
          event_category: item.event_category,
          event_severity: item.event_severity,
          event_confidence: item.event_confidence,
          why_flagged: item.why_flagged,
          involved_track_ids: item.involved_track_ids,
          detection_count: item.detection_count,
          detection_summary: item.detection_summary,
          created_at: item.created_at,
          artifacts: {},
        }
        map.set(key, group)
      }
      group.artifacts[item.evidence_type] = item
    }
    return Array.from(map.values())
  }, [evidenceItems])

  const filteredGroups = useMemo(() => {
    const q = timeQuery.trim().toLowerCase()
    return groupedEvidence.filter((group) => {
      if (categoryFilter !== 'all' && group.event_category !== categoryFilter) {
        return false
      }
      if (dateFilter) {
        const itemDate = new Date(group.created_at).toISOString().slice(0, 10)
        if (itemDate !== dateFilter) return false
      }
      if (q) {
        const hms = formatHms(group.timestamp_seconds).toLowerCase()
        const secStr = group.timestamp_seconds.toFixed(2)
        const title = group.event_title.toLowerCase()
        if (!hms.includes(q) && !secStr.includes(q) && !title.includes(q)) {
          return false
        }
      }
      return true
    })
  }, [groupedEvidence, categoryFilter, dateFilter, timeQuery])

  const isLoadingEvidence = Boolean(activeTargetKey) && loadedEvidenceFor !== activeTargetKey

  return (
    <div className="space-y-6">
      {/* Header & Analysis / Live Session Selector */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#2563EB]">
              <ShieldCheck className="h-3.5 w-3.5 text-[#7C3AED]" />
              <span>Evidence Center</span>
            </span>
            <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827]">
              Visual Evidence &amp; Reports
            </h2>
            <p className="mt-1 text-sm text-[#64748B]">
              Inspect saved event evidence frames and intelligence reports from uploaded video
              analyses and live webcam monitoring sessions.
            </p>

            {/* Source Switcher */}
            <div className="mt-4 inline-flex rounded-xl border border-slate-200 bg-[#F5F8FC] p-1">
              <button
                type="button"
                onClick={() => handleSwitchMode('video')}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  sourceMode === 'video'
                    ? 'bg-white text-[#2563EB] shadow-2xs'
                    : 'text-[#64748B] hover:text-[#111827]'
                }`}
              >
                <Film className="h-3.5 w-3.5" />
                <span>Video Analyses ({analyses.length})</span>
              </button>
              <button
                type="button"
                onClick={() => handleSwitchMode('live')}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  sourceMode === 'live'
                    ? 'bg-white text-[#7C3AED] shadow-2xs'
                    : 'text-[#64748B] hover:text-[#111827]'
                }`}
              >
                <Radio className="h-3.5 w-3.5" />
                <span>Live Sessions ({liveSessions.length})</span>
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            {sourceMode === 'video' && analyses.length > 0 && (
              <>
                <div className="w-full sm:w-72">
                  <label
                    htmlFor="evidence-analysis-select"
                    className="block text-xs font-semibold text-[#111827]"
                  >
                    Select Analyzed Video
                  </label>
                  <select
                    id="evidence-analysis-select"
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

                {selectedId && <PdfDownloadButton analysisId={selectedId} />}
              </>
            )}

            {sourceMode === 'live' && liveSessions.length > 0 && (
              <>
                <div className="w-full sm:w-72">
                  <label
                    htmlFor="evidence-live-select"
                    className="block text-xs font-semibold text-[#111827]"
                  >
                    Select Live Monitoring Session
                  </label>
                  <select
                    id="evidence-live-select"
                    value={selectedLiveId}
                    onChange={(e) => handleSelectLiveSession(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3.5 py-2.5 text-xs font-semibold text-[#111827] focus:border-[#7C3AED] focus:bg-white focus:ring-2 focus:ring-[#7C3AED]/20 focus:outline-none"
                  >
                    {liveSessions.map((sess) => (
                      <option key={sess.session_id} value={sess.session_id}>
                        {new Date(sess.started_at).toLocaleString()} · {sess.events_discovered_count}{' '}
                        event(s) ({sess.status})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedLiveId && (
                  <button
                    type="button"
                    onClick={() => void handleDownloadLivePdf()}
                    disabled={isDownloadingLivePdf}
                    className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-[#111827] transition-colors hover:border-[#7C3AED]/40 hover:bg-[#F5F8FC] hover:text-[#7C3AED] disabled:opacity-60"
                  >
                    {isDownloadingLivePdf ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <FileDown className="h-3.5 w-3.5" />
                    )}
                    <span>Download Live PDF Report</span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </motion.section>

      {errorMsg && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {!analysesLoaded ? (
        <div className="flex items-center justify-center rounded-3xl border border-slate-200 bg-white py-14">
          <Loader2 className="mr-2.5 h-5 w-5 animate-spin text-[#2563EB]" />
          <span className="text-sm font-medium text-[#64748B]">Loading evidence sources...</span>
        </div>
      ) : sourceMode === 'video' && analyses.length === 0 ? (
        <div className="rounded-3xl border border-slate-200/90 bg-white p-10 text-center shadow-xs">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#EFF6FF] text-[#2563EB]">
            <Film className="h-6 w-6" />
          </div>
          <h3 className="mt-4 font-display text-lg font-bold text-[#111827]">
            No Completed Analyses Available
          </h3>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-[#64748B]">
            Upload and process a video first to generate timestamped evidence frames and PDF
            reports.
          </p>
          <Link
            to="/analysis/new"
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-sm font-semibold text-white shadow-sm"
          >
            <span>Start New Analysis</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : sourceMode === 'live' && liveSessions.length === 0 ? (
        <div className="rounded-3xl border border-slate-200/90 bg-white p-10 text-center shadow-xs">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#F5F3FF] text-[#7C3AED]">
            <Radio className="h-6 w-6" />
          </div>
          <h3 className="mt-4 font-display text-lg font-bold text-[#111827]">
            No Live Monitoring Sessions Recorded Yet
          </h3>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-[#64748B]">
            Start a Live Webcam Monitoring session to capture evidence snapshots when events are
            discovered.
          </p>
          <Link
            to="/dashboard/live"
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-sm font-semibold text-white shadow-sm"
          >
            <span>Open Live Monitoring</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        <>
          {/* Filters Bar */}
          <section className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                {CATEGORY_FILTERS.map((f) => {
                  const active = categoryFilter === f.value
                  return (
                    <button
                      key={f.value}
                      type="button"
                      onClick={() => setCategoryFilter(f.value)}
                      className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all ${
                        active
                          ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                          : 'border-slate-200 bg-white text-[#64748B] hover:bg-[#F5F8FC] hover:text-[#111827]'
                      }`}
                    >
                      {f.label}
                    </button>
                  )
                })}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="date"
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                  aria-label="Filter by date"
                  className="rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-1.5 text-xs text-[#111827] focus:border-[#2563EB] focus:bg-white focus:outline-none"
                />
                <input
                  type="search"
                  value={timeQuery}
                  onChange={(e) => setTimeQuery(e.target.value)}
                  placeholder="Timestamp (e.g. 00:00:05) or title..."
                  aria-label="Filter by timestamp or title"
                  className="w-56 rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-1.5 text-xs text-[#111827] placeholder:text-slate-400 focus:border-[#2563EB] focus:bg-white focus:outline-none"
                />
              </div>
            </div>
          </section>

          {isLoadingEvidence ? (
            <div className="flex items-center justify-center rounded-3xl border border-slate-200 bg-white py-14">
              <Loader2 className="mr-2.5 h-5 w-5 animate-spin text-[#2563EB]" />
              <span className="text-sm font-medium text-[#64748B]">
                Loading evidence artifacts...
              </span>
            </div>
          ) : filteredGroups.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
              <ShieldCheck className="mx-auto h-8 w-8 text-[#64748B]" />
              <h3 className="mt-3 font-display text-base font-bold text-[#111827]">
                {groupedEvidence.length === 0
                  ? 'No Visual Evidence Collected Yet'
                  : 'No Evidence Matches Your Filters'}
              </h3>
              <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-[#64748B]">
                {groupedEvidence.length === 0
                  ? 'Run event discovery on this completed analysis to generate annotated detection and tracking evidence frames.'
                  : 'Clear the date, timestamp, or category filter to view all evidence items.'}
              </p>

              {groupedEvidence.length === 0 && sourceMode === 'video' && (
                <button
                  type="button"
                  onClick={handleRunDiscoveryAndEvidence}
                  disabled={isGeneratingEvidence}
                  className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-2.5 text-xs font-semibold text-white shadow-sm disabled:opacity-65"
                >
                  {isGeneratingEvidence ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Discovering &amp; Collecting Evidence...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      <span>Discover Events &amp; Collect Evidence</span>
                    </>
                  )}
                </button>
              )}
            </div>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {filteredGroups.map((group) => (
                <EvidenceGroupCard
                  key={group.key}
                  group={group}
                  isLiveMode={sourceMode === 'live'}
                  onOpenPreview={(grp, type) => setPreviewState({ group: grp, activeType: type })}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Larger Preview Modal */}
      <AnimatePresence>
        {previewState && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs"
            onClick={() => setPreviewState(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-4xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-slate-200 bg-[#F5F8FC] px-5 py-3.5">
                <div>
                  <h3 className="font-display text-base font-bold text-[#111827]">
                    {previewState.group.event_title}
                  </h3>
                  <p className="font-mono text-xs text-[#64748B]">
                    Frame #{previewState.group.frame_number} ·{' '}
                    {formatHms(previewState.group.timestamp_seconds)} (
                    {previewState.group.timestamp_seconds.toFixed(2)}s)
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPreviewState(null)}
                  aria-label="Close evidence preview"
                  className="cursor-pointer rounded-xl p-2 text-[#64748B] hover:bg-white hover:text-[#111827]"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="p-5">
                {/* Frame Variant Switcher */}
                <div className="mb-4 flex flex-wrap gap-2">
                  {(['original_frame', 'annotated_detection', 'annotated_tracking'] as EvidenceType[]).map(
                    (typeKey) => {
                      const item = previewState.group.artifacts[typeKey]
                      if (!item) return null
                      const isActive = previewState.activeType === typeKey
                      return (
                        <button
                          key={typeKey}
                          type="button"
                          onClick={() =>
                            setPreviewState({ group: previewState.group, activeType: typeKey })
                          }
                          className={`cursor-pointer rounded-xl border px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                            isActive
                              ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                              : 'border-slate-200 bg-white text-[#64748B] hover:bg-[#F5F8FC]'
                          }`}
                        >
                          {EVIDENCE_TYPE_LABELS[typeKey]}
                        </button>
                      )
                    },
                  )}
                </div>

                {previewState.group.artifacts[previewState.activeType] && (
                  <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
                    <AuthenticatedEvidenceImg
                      evidenceId={previewState.group.artifacts[previewState.activeType]!.id}
                      liveSessionId={
                        sourceMode === 'live' ? previewState.group.analysis_id : undefined
                      }
                      eventId={
                        sourceMode === 'live' ? previewState.group.event_id : undefined
                      }
                      alt={previewState.group.event_title}
                      className="max-h-[60vh] w-full object-contain"
                    />
                  </div>
                )}

                <div className="mt-4 rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4 text-xs text-[#64748B]">
                  <p className="font-semibold text-[#111827]">Why Flagged</p>
                  <p className="mt-1 leading-relaxed">{previewState.group.why_flagged}</p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
