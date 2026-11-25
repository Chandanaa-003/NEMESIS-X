import {
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileText,
  Layers,
  Loader2,
  Radio,
  Send,
  Sparkles,
  Target,
  Video,
  X,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import {
  downloadSessionPdfReport,
  fetchUnifiedSessionDetails,
  type UnifiedSessionDetailResponse,
} from '../../services/monitoringService.ts'

interface SessionDetailsModalProps {
  sessionId: string
  sessionType?: 'recorded' | 'live'
  onClose: () => void
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hrs > 0) {
    return `${hrs}h ${mins}m ${secs}s`
  }
  return `${mins}m ${secs}s`
}

function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatDateTime(dtStr: string | null | undefined): string {
  if (!dtStr) return '—'
  const d = new Date(dtStr)
  if (isNaN(d.getTime())) return dtStr
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatTrackCode(trackId: number): string {
  return `T${String(trackId).padStart(3, '0')}`
}

const SEVERITY_BADGES: Record<string, string> = {
  high: 'border-rose-200 bg-rose-50 text-rose-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  low: 'border-blue-200 bg-blue-50 text-blue-700',
}

const STATUS_BADGES: Record<string, string> = {
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  active: 'border-blue-200 bg-blue-50 text-blue-700 animate-pulse',
  stopped: 'border-slate-200 bg-slate-100 text-slate-700',
  processing: 'border-amber-200 bg-amber-50 text-amber-700',
  queued: 'border-slate-200 bg-slate-50 text-slate-600',
  failed: 'border-rose-200 bg-rose-50 text-rose-700',
}

export function SessionDetailsModal({
  sessionId,
  sessionType,
  onClose,
}: SessionDetailsModalProps) {
  const [session, setSession] = useState<UnifiedSessionDetailResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false)
  const [pdfSuccess, setPdfSuccess] = useState(false)

  // AI Explanation Assistant states
  const [activeTab, setActiveTab] = useState<'overview' | 'events' | 'tracks' | 'evidence' | 'ai'>('overview')
  const [aiQuery, setAiQuery] = useState('')
  const [aiChatLog, setAiChatLog] = useState<Array<{ role: 'assistant' | 'user'; text: string }>>([])

  useEffect(() => {
    let cancelled = false

    fetchUnifiedSessionDetails(sessionId, sessionType)
      .then((data) => {
        if (!cancelled) {
          setSession(data)
          // Seed AI explanation
          const highCount = data.events.filter((e) => e.severity === 'high').length
          const reviewCount = data.events.filter((e) => e.requires_human_review).length
          setAiChatLog([
            {
              role: 'assistant',
              text: `Hello! I am your NEMESIS-X AI Intelligence Assistant for session **${data.name}** (${data.session_type === 'live' ? 'Live Stream' : 'Recorded Video'}).\n\nI evaluated **${data.events.length} discovered events** across **${data.track_stats.total_tracks ?? 0} tracked trajectories**. There are **${highCount} high-priority alert(s)** and **${reviewCount} event(s) flagged for human verification**.\n\nAsk me about any event, involved track trajectory, or rule-based reasoning!`,
            },
          ])
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setErrorMessage(err.response?.data?.detail || 'Failed to load session details.')
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [sessionId, sessionType])

  // Handle PDF Download
  const handlePdfDownload = async () => {
    if (!session?.pdf_report_url) return
    setIsDownloadingPdf(true)
    setPdfSuccess(false)
    try {
      const fileName = `nemesis-x-${session.session_type}-report-${session.session_id.slice(0, 8)}.pdf`
      await downloadSessionPdfReport(session.pdf_report_url, fileName)
      setPdfSuccess(true)
      window.setTimeout(() => setPdfSuccess(false), 3000)
    } catch {
      alert('Unable to generate or download PDF report. Ensure analysis is completed.')
    } finally {
      setIsDownloadingPdf(false)
    }
  }

  // Handle AI Explanation query
  const handleSendAiQuery = (customPrompt?: string) => {
    const prompt = (customPrompt || aiQuery).trim()
    if (!prompt || !session) return

    const newLog = [...aiChatLog, { role: 'user' as const, text: prompt }]
    setAiQuery('')

    // Generate truthful factual response from session state
    let reply = ''
    const lower = prompt.toLowerCase()

    if (lower.includes('why') && (lower.includes('flagged') || lower.includes('alert') || lower.includes('high'))) {
      const highEvts = session.events.filter((e) => e.severity === 'high')
      if (highEvts.length > 0) {
        reply = `**High-Priority Event Analysis:**\n\n` +
          highEvts.map((e) => (
            `• **${e.title}** (${formatTimestamp(e.start_timestamp)} - ${formatTimestamp(e.end_timestamp)}):\n  - **Reason Flagged:** ${e.why_flagged || 'Exceeded threat tolerance'}\n  - **Involved Tracks:** ${e.involved_track_ids.map(formatTrackCode).join(', ') || 'N/A'}\n  - **Sequence:** ${e.observed_sequence.join(' → ') || 'Trajectory anomaly'}`
          )).join('\n\n')
      } else {
        reply = `No high-priority events were flagged during this session. All ${session.events.length} observed events remained within nominal or medium thresholds.`
      }
    } else if (lower.includes('track') || lower.includes('who') || lower.includes('object')) {
      const rawTracks = session.track_stats.tracks as Array<any> | undefined
      if (rawTracks && rawTracks.length > 0) {
        reply = `**Active Track Summary (${rawTracks.length} tracks):**\n\n` +
          rawTracks.slice(0, 5).map((t) => (
            `• **${formatTrackCode(t.track_id)}** (${t.class_name}): active for ${Math.round(t.duration_seconds)}s (frames ${formatTimestamp(t.first_seen_timestamp)} → ${formatTimestamp(t.last_seen_timestamp)}) with ${Math.round(t.avg_confidence * 100)}% detection confidence.`
          )).join('\n')
      } else {
        reply = `Tracks recorded: ${session.track_stats.total_tracks ?? 0} unique tracked trajectories across this session.`
      }
    } else if (lower.includes('review') || lower.includes('human')) {
      const reviewEvts = session.events.filter((e) => e.requires_human_review)
      if (reviewEvts.length > 0) {
        reply = `**Human Review Recommendations (${reviewEvts.length} events):**\n\n` +
          reviewEvts.map((e) => `• [${e.severity.toUpperCase()}] **${e.title}**: ${e.why_flagged}`).join('\n')
      } else {
        reply = `All discovered events have standard confidence metrics without mandatory manual review recommendations.`
      }
    } else {
      reply = `**Session Intelligence Assessment:**\n` +
        `• **Session:** ${session.name}\n` +
        `• **Duration:** ${formatDuration(session.duration_seconds)} (${session.frames_processed} frames analyzed)\n` +
        `• **Detected Objects:** ${session.detection_stats.total_detections ?? 0} detections across ${session.track_stats.total_tracks ?? 0} unique tracked objects\n` +
        `• **Discovered Events:** ${session.events.length} rule-validated events.\n\n` +
        `Is there a specific timestamp or tracking ID you would like me to dissect?`
    }

    setAiChatLog([...newLog, { role: 'assistant', text: reply }])
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-3 backdrop-blur-xs sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-modal-title"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96 }}
        className="relative flex h-full max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200/90 px-6 py-4 bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${
                session?.session_type === 'live'
                  ? 'bg-rose-100 text-rose-600'
                  : 'bg-blue-100 text-[#2563EB]'
              }`}
            >
              {session?.session_type === 'live' ? (
                <Radio className="h-5 w-5 animate-pulse" />
              ) : (
                <Video className="h-5 w-5" />
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                    session?.session_type === 'live'
                      ? 'border-rose-200 bg-rose-50 text-rose-700'
                      : 'border-blue-200 bg-blue-50 text-[#2563EB]'
                  }`}
                >
                  {session?.session_type === 'live' ? 'Live Webcam Stream' : 'Recorded Video Analysis'}
                </span>
                {session?.status && (
                  <span
                    className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                      STATUS_BADGES[session.status.toLowerCase()] || 'border-slate-200 bg-slate-100 text-slate-700'
                    }`}
                  >
                    {session.status}
                  </span>
                )}
              </div>

              <h3
                id="session-modal-title"
                className="mt-0.5 font-display text-lg font-bold text-[#111827] sm:text-xl truncate max-w-md sm:max-w-xl"
              >
                {session?.name || `Session ${sessionId.slice(0, 8)}`}
              </h3>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {session && (
              <button
                type="button"
                onClick={handlePdfDownload}
                disabled={isDownloadingPdf}
                className="cursor-pointer inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-2xs hover:bg-slate-50 hover:border-slate-300 disabled:opacity-60 transition-all"
                title="Download Intelligence PDF Report"
              >
                {isDownloadingPdf ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#2563EB]" />
                ) : pdfSuccess ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <Download className="h-3.5 w-3.5 text-[#2563EB]" />
                )}
                <span className="hidden sm:inline">
                  {isDownloadingPdf ? 'Generating...' : pdfSuccess ? 'Downloaded!' : 'PDF Report'}
                </span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="cursor-pointer rounded-xl border border-slate-200 p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
              aria-label="Close dialog"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 bg-white px-6">
          <div className="flex space-x-1 sm:space-x-4 overflow-x-auto py-2">
            {[
              { id: 'overview', label: 'Session Overview', icon: FileText },
              { id: 'events', label: `Discovered Events (${session?.events.length ?? 0})`, icon: Clock },
              { id: 'tracks', label: `Track Trajectories (${session?.track_stats.total_tracks ?? 0})`, icon: Target },
              { id: 'evidence', label: `Evidence Frames (${session?.evidence_count ?? 0})`, icon: Eye },
              { id: 'ai', label: 'AI Intelligence Assistant', icon: Sparkles },
            ].map((tab) => {
              const Icon = tab.icon
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`cursor-pointer inline-flex items-center gap-2 border-b-2 px-3 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
                    active
                      ? 'border-[#2563EB] text-[#2563EB]'
                      : 'border-transparent text-slate-500 hover:text-slate-900'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${active ? 'text-[#2563EB]' : 'text-slate-400'}`} />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Body content */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/50">
          {isLoading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-[#2563EB]" />
              <p className="text-xs font-semibold text-slate-500">Loading session metadata & intelligence...</p>
            </div>
          ) : errorMessage ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-700">
              <AlertCircle className="mx-auto h-8 w-8" />
              <p className="mt-2 text-sm font-bold">Failed to load session details</p>
              <p className="mt-1 text-xs">{errorMessage}</p>
            </div>
          ) : session ? (
            <div>
              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Top Stats Grid */}
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
                      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Duration</p>
                      <p className="mt-1 font-display text-2xl font-extrabold text-[#111827]">
                        {formatDuration(session.duration_seconds)}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-400 font-mono">
                        {session.frames_processed} frames analyzed
                      </p>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
                      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Total Detections</p>
                      <p className="mt-1 font-display text-2xl font-extrabold text-[#2563EB]">
                        {session.detection_stats.total_detections ?? 0}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-400">YOLOv8 detected objects</p>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
                      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Unique Tracks</p>
                      <p className="mt-1 font-display text-2xl font-extrabold text-[#7C3AED]">
                        {session.track_stats.total_tracks ?? 0}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-400">ByteTrack trajectories</p>
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
                      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Discovered Events</p>
                      <div className="mt-1 flex items-baseline gap-2">
                        <p className="font-display text-2xl font-extrabold text-[#111827]">
                          {session.events.length}
                        </p>
                        {session.events.filter((e) => e.severity === 'high').length > 0 && (
                          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                            {session.events.filter((e) => e.severity === 'high').length} High
                          </span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-400">Rule-based temporal events</p>
                    </div>
                  </div>

                  {/* Metadata & Specs */}
                  <div className="grid gap-6 md:grid-cols-2">
                    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs space-y-3">
                      <h4 className="font-display text-sm font-bold text-[#111827] flex items-center gap-2">
                        <FileText className="h-4 w-4 text-[#2563EB]" />
                        <span>Session Specifications</span>
                      </h4>
                      <dl className="space-y-2 text-xs">
                        <div className="flex justify-between py-1 border-b border-slate-100">
                          <dt className="text-slate-500">Session ID</dt>
                          <dd className="font-mono text-slate-800 select-all">{session.session_id}</dd>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100">
                          <dt className="text-slate-500">Monitoring Mode</dt>
                          <dd className="font-semibold text-slate-800 capitalize">{session.session_type}</dd>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100">
                          <dt className="text-slate-500">Started At</dt>
                          <dd className="text-slate-800">{formatDateTime(session.started_at)}</dd>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100">
                          <dt className="text-slate-500">Ended At</dt>
                          <dd className="text-slate-800">{formatDateTime(session.end_time)}</dd>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100">
                          <dt className="text-slate-500">Confidence Threshold</dt>
                          <dd className="font-mono text-slate-800">
                            {Math.round(session.confidence_threshold * 100)}%
                          </dd>
                        </div>
                        {session.frame_width && session.frame_height && (
                          <div className="flex justify-between py-1">
                            <dt className="text-slate-500">Resolution</dt>
                            <dd className="font-mono text-slate-800">
                              {session.frame_width} × {session.frame_height}
                            </dd>
                          </div>
                        )}
                      </dl>
                    </div>

                    {/* Detected Object Class Breakdown */}
                    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs space-y-3">
                      <h4 className="font-display text-sm font-bold text-[#111827] flex items-center gap-2">
                        <Layers className="h-4 w-4 text-[#7C3AED]" />
                        <span>Detected Object Classes</span>
                      </h4>
                      {session.detection_stats.class_counts &&
                      Object.keys(session.detection_stats.class_counts).length > 0 ? (
                        <div className="space-y-2">
                          {Object.entries(session.detection_stats.class_counts).map(([cls, cnt]) => (
                            <div key={cls} className="flex items-center justify-between text-xs">
                              <span className="font-medium text-slate-700 capitalize">{cls}</span>
                              <div className="flex items-center gap-2">
                                <div className="h-2 w-28 rounded-full bg-slate-100 overflow-hidden">
                                  <div
                                    className="h-full bg-[#2563EB] rounded-full"
                                    style={{
                                      width: `${Math.min(
                                        100,
                                        Math.round(((cnt as number) / (session.detection_stats.total_detections || 1)) * 100),
                                      )}%`,
                                    }}
                                  />
                                </div>
                                <span className="font-mono text-slate-500 text-[11px] w-8 text-right">
                                  {cnt as number}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-500 py-4 text-center">
                          Track classes logged in ByteTrack trajectories tab.
                        </p>
                      )}
                    </div>
                  </div>

                  {/* AI Quick Banner */}
                  <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <Sparkles className="h-5 w-5 text-[#2563EB] shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-bold text-blue-900">AI Intelligence Explanation Ready</p>
                        <p className="text-xs text-blue-700 mt-0.5">
                          Inspect rule triggers, trajectory memories, and why each threat or event was flagged.
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveTab('ai')}
                      className="cursor-pointer shrink-0 rounded-xl bg-[#2563EB] px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
                    >
                      Open AI Assistant
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 2: EVENTS TIMELINE */}
              {activeTab === 'events' && (
                <div className="space-y-4">
                  {session.events.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center">
                      <Clock className="mx-auto h-8 w-8 text-slate-400" />
                      <p className="mt-2 text-sm font-semibold text-slate-700">No events flagged</p>
                      <p className="mt-1 text-xs text-slate-500">
                        No temporal activity patterns exceeded alert thresholds during this monitoring run.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {session.events.map((evt) => (
                        <article
                          key={evt.id}
                          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs hover:shadow-md transition-shadow space-y-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span
                                  className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                                    SEVERITY_BADGES[evt.severity.toLowerCase()] || SEVERITY_BADGES.low
                                  }`}
                                >
                                  {evt.severity} severity
                                </span>
                                <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                                  {evt.category.replace('_', ' ')}
                                </span>
                                {evt.requires_human_review && (
                                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                                    <AlertTriangle className="h-3 w-3" />
                                    Review Recommended
                                  </span>
                                )}
                              </div>
                              <h4 className="font-display text-base font-bold text-[#111827]">
                                {evt.title}
                              </h4>
                            </div>

                            <div className="flex items-center gap-2 font-mono text-xs">
                              <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-700 font-semibold">
                                <Clock className="h-3.5 w-3.5 text-[#2563EB]" />
                                {formatTimestamp(evt.start_timestamp)} → {formatTimestamp(evt.end_timestamp)}
                              </span>
                              <span className="rounded-lg bg-blue-50 px-2 py-1 text-blue-700 font-semibold">
                                {Math.round(evt.confidence * 100)}% Conf
                              </span>
                            </div>
                          </div>

                          <p className="text-xs text-slate-600 leading-relaxed">{evt.description}</p>

                          {/* Involved Tracks */}
                          {evt.involved_track_ids.length > 0 && (
                            <div className="flex items-center gap-1.5 text-xs">
                              <span className="font-semibold text-slate-700">Involved Tracks:</span>
                              {evt.involved_track_ids.map((tid) => (
                                <span
                                  key={tid}
                                  className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-[11px] font-bold text-[#2563EB]"
                                >
                                  {formatTrackCode(tid)}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Sequence and Reason */}
                          <div className="grid gap-3 rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 text-xs sm:grid-cols-2">
                            <div>
                              <p className="font-semibold text-slate-800">Why Flagged</p>
                              <p className="mt-1 text-slate-600">{evt.why_flagged || 'Threshold condition satisfied.'}</p>
                            </div>
                            <div>
                              <p className="font-semibold text-slate-800">Observed Sequence</p>
                              <ul className="mt-1 space-y-1 text-slate-600">
                                {evt.observed_sequence.map((step, idx) => (
                                  <li key={idx} className="flex items-center gap-1.5">
                                    <span className="h-1.5 w-1.5 rounded-full bg-[#2563EB]" />
                                    <span>{step}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: TRACK TRAJECTORIES */}
              {activeTab === 'tracks' && (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
                    <h4 className="font-display text-sm font-bold text-[#111827] mb-3">
                      ByteTrack Trajectory Registry ({session.track_stats.total_tracks ?? 0} tracks)
                    </h4>
                    {Array.isArray(session.track_stats.tracks) && session.track_stats.tracks.length > 0 ? (
                      <div className="divide-y divide-slate-100">
                        {session.track_stats.tracks.map((t: any) => (
                          <div key={t.track_id} className="py-3 flex items-center justify-between text-xs">
                            <div className="flex items-center gap-3">
                              <span className="rounded-md bg-[#2563EB]/10 px-2 py-1 font-mono font-bold text-[#2563EB]">
                                {formatTrackCode(t.track_id)}
                              </span>
                              <div>
                                <p className="font-semibold text-slate-800 capitalize">{t.class_name}</p>
                                <p className="text-[11px] text-slate-400">
                                  Seen from {formatTimestamp(t.first_seen_timestamp)} to {formatTimestamp(t.last_seen_timestamp)}
                                </p>
                              </div>
                            </div>
                            <div className="text-right">
                              <p className="font-mono text-slate-700">{Math.round(t.duration_seconds)}s lifespan</p>
                              <p className="text-[11px] text-slate-400">{Math.round((t.avg_confidence || 0) * 100)}% avg conf</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 py-6 text-center">
                        Total {session.track_stats.total_tracks ?? 0} unique tracked objects recognized across frames.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 4: EVIDENCE FRAMES */}
              {activeTab === 'evidence' && (
                <div className="space-y-4">
                  {session.evidence_items.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center">
                      <Eye className="mx-auto h-8 w-8 text-slate-400" />
                      <p className="mt-2 text-sm font-semibold text-slate-700">No snapshot evidence captured</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Snapshots are automatically archived when high-confidence events or human-review triggers fire.
                      </p>
                    </div>
                  ) : (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      {session.evidence_items.map((ev) => (
                        <div
                          key={ev.id}
                          className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xs hover:shadow-md transition-shadow"
                        >
                          <div className="aspect-video bg-slate-900 relative overflow-hidden">
                            <img
                              src={ev.image_url}
                              alt={ev.description}
                              className="h-full w-full object-cover"
                              loading="lazy"
                            />
                            <span className="absolute bottom-2 left-2 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[10px] text-white">
                              {formatTimestamp(ev.timestamp_seconds)} · Frame {ev.frame_number}
                            </span>
                          </div>
                          <div className="p-3.5 space-y-1.5">
                            <p className="text-xs font-semibold text-slate-800 line-clamp-1">{ev.description}</p>
                            {ev.why_flagged && (
                              <p className="text-[11px] text-slate-500 line-clamp-2">{ev.why_flagged}</p>
                            )}
                            {ev.involved_track_ids.length > 0 && (
                              <div className="flex items-center gap-1 pt-1">
                                <span className="text-[10px] text-slate-400">Tracks:</span>
                                {ev.involved_track_ids.map((tid) => (
                                  <span key={tid} className="font-mono text-[10px] font-bold text-[#2563EB]">
                                    {formatTrackCode(tid)}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 5: AI INTELLIGENCE ASSISTANT */}
              {activeTab === 'ai' && (
                <div className="flex flex-col h-[520px] rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
                  <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/70 px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Bot className="h-4 w-4 text-[#2563EB]" />
                      <span className="font-display text-xs font-bold text-slate-800">
                        NEMESIS-X Session Reasoning Assistant
                      </span>
                    </div>
                    <span className="font-mono text-[10px] font-semibold text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                      Grounded in real YOLOv8 & ByteTrack telemetry
                    </span>
                  </div>

                  {/* Chat log */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {aiChatLog.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex gap-3 text-xs leading-relaxed ${
                          msg.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        {msg.role === 'assistant' && (
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-[#2563EB]">
                            <Sparkles className="h-4 w-4" />
                          </div>
                        )}
                        <div
                          className={`rounded-2xl px-4 py-2.5 max-w-xl whitespace-pre-line ${
                            msg.role === 'user'
                              ? 'bg-[#2563EB] text-white'
                              : 'border border-slate-200 bg-slate-50 text-slate-800'
                          }`}
                        >
                          {msg.text}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Quick suggestion prompt chips */}
                  <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-2 flex items-center gap-2 overflow-x-auto text-xs">
                    <span className="text-[11px] font-semibold text-slate-400 shrink-0">Ask:</span>
                    {[
                      'Why were high priority events flagged?',
                      'Summarize active track trajectories',
                      'Which events require human review?',
                      'Explain spatial-temporal reasoning',
                    ].map((promptText) => (
                      <button
                        key={promptText}
                        type="button"
                        onClick={() => handleSendAiQuery(promptText)}
                        className="cursor-pointer shrink-0 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:border-blue-300 hover:text-[#2563EB] transition-colors"
                      >
                        {promptText}
                      </button>
                    ))}
                  </div>

                  {/* Input form */}
                  <form
                    onSubmit={(e) => {
                      e.preventDefault()
                      handleSendAiQuery()
                    }}
                    className="border-t border-slate-200 bg-white p-3 flex items-center gap-2"
                  >
                    <input
                      type="text"
                      value={aiQuery}
                      onChange={(e) => setAiQuery(e.target.value)}
                      placeholder="Ask the AI explanation assistant about this session..."
                      className="flex-1 rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] focus:outline-none"
                    />
                    <button
                      type="submit"
                      disabled={!aiQuery.trim()}
                      className="cursor-pointer inline-flex items-center gap-1 rounded-xl bg-[#2563EB] px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      <Send className="h-3.5 w-3.5" />
                      <span>Send</span>
                    </button>
                  </form>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </motion.div>
    </div>
  )
}
