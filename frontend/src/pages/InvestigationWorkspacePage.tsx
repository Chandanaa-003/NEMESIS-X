import {
  AlertCircle,
  ArrowLeft,
  BriefcaseBusiness,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileImage,
  Film,
  GitBranch,
  ImageOff,
  Loader2,
  Plus,
  Radio,
  Search,
  Trash2,
  UserRound,
  X,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  type AnalysisListItem,
  listUserAnalyses,
} from '../services/analysisService'
import { getAuthErrorMessage } from '../services/authService'
import {
  addInvestigationNote,
  addInvestigationSource,
  createInvestigation,
  deleteInvestigation,
  deleteInvestigationNote,
  fetchInvestigationImageBlobUrl,
  getInvestigation,
  getInvestigationEvidence,
  getInvestigationGraph,
  getInvestigationTimeline,
  getInvestigationTrackDetail,
  linkInvestigationEvent,
  linkInvestigationTrack,
  listInvestigations,
  removeInvestigationSource,
  searchInvestigationTracks,
  unlinkInvestigationEvent,
  unlinkInvestigationTrack,
  updateInvestigation,
  updateInvestigationNote,
  type InvestigationDetail,
  type InvestigationEvidenceItem,
  type InvestigationGraph,
  type InvestigationGraphNode,
  type InvestigationNote,
  type InvestigationSource,
  type InvestigationSummary,
  type InvestigationTimeline,
  type InvestigationTimelineItem,
  type InvestigationTrack,
  type InvestigationTrackDetail,
} from '../services/investigationService'
import {
  listLiveMonitoringSessions,
  type LiveSessionStatusResponse,
} from '../services/liveService'
import { fetchVideoBlobUrl } from '../services/videoService'

type WorkspaceTab = 'timeline' | 'tracks' | 'graph' | 'evidence' | 'notes'

const TABS: Array<{ id: WorkspaceTab; label: string; icon: typeof Clock3 }> = [
  { id: 'timeline', label: 'Timeline', icon: Clock3 },
  { id: 'tracks', label: 'Tracks', icon: UserRound },
  { id: 'graph', label: 'Relationships', icon: GitBranch },
  { id: 'evidence', label: 'Evidence review', icon: FileImage },
  { id: 'notes', label: 'Investigator notes', icon: BriefcaseBusiness },
]

function formatTime(seconds: number): string {
  const safe = Math.max(0, seconds)
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const remainder = safe % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${remainder.toFixed(2).padStart(5, '0')}`
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString()
}

function statusStyle(status: InvestigationSummary['status']): string {
  if (status === 'closed') return 'border-slate-200 bg-slate-100 text-slate-600'
  if (status === 'reviewing') return 'border-violet-200 bg-violet-50 text-violet-700'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

function entityLabel(track: Pick<InvestigationTrack, 'entity_label' | 'track_label' | 'class_name'>) {
  return track.entity_label === 'Person'
    ? `Person ${track.track_label}`
    : `Object (${track.class_name}) ${track.track_label}`
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

export function InvestigationWorkspacePage() {
  const { investigationId } = useParams()
  return investigationId
    ? <InvestigationDetailWorkspace key={investigationId} investigationId={investigationId} />
    : <InvestigationListPage />
}

function InvestigationListPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState<InvestigationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    listInvestigations()
      .then((result) => {
        if (!active) return
        setRows(result)
        setError('')
      })
      .catch((reason) => {
        if (active) setError(getAuthErrorMessage(reason, 'Could not load investigations.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const filtered = useMemo(
    () => rows.filter((row) => `${row.title} ${row.description}`.toLowerCase().includes(search.toLowerCase())),
    [rows, search],
  )

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!title.trim()) return
    setSaving(true)
    setError('')
    try {
      const created = await createInvestigation({ title: title.trim(), description: description.trim() })
      navigate(`/dashboard/investigations/${created.id}`)
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not create the investigation.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (row: InvestigationSummary) => {
    if (!window.confirm(`Delete "${row.title}" and its investigation links and notes? Existing source evidence will not be deleted.`)) return
    try {
      await deleteInvestigation(row.id)
      setRows((current) => current.filter((item) => item.id !== row.id))
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not delete the investigation.'))
    }
  }

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              <BriefcaseBusiness className="h-3.5 w-3.5" />
              Investigation Workspace
            </div>
            <h1 className="mt-3 font-display text-3xl font-extrabold tracking-tight text-[#111827]">
              Investigations
            </h1>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[#64748B]">
              Organize real analyses, saved events, source-scoped tracks, evidence, and investigator-written notes.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate((current) => !current)}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-4 py-2.5 text-sm font-semibold text-white shadow-sm"
          >
            <Plus className="h-4 w-4" />
            New investigation
          </button>
        </div>
      </motion.section>

      {error && <ErrorBanner message={error} />}

      {showCreate && (
        <form onSubmit={submit} className="grid gap-4 rounded-2xl border border-blue-100 bg-white p-5 shadow-xs sm:grid-cols-2">
          <div>
            <label htmlFor="investigation-title" className="text-xs font-semibold text-[#111827]">Title</label>
            <input id="investigation-title" required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm outline-none focus:border-blue-400" placeholder="Investigation title" />
          </div>
          <div>
            <label htmlFor="investigation-description" className="text-xs font-semibold text-[#111827]">Description</label>
            <input id="investigation-description" maxLength={10000} value={description} onChange={(event) => setDescription(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm outline-none focus:border-blue-400" placeholder="Optional context" />
          </div>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <button type="button" onClick={() => setShowCreate(false)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">Cancel</button>
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Create workspace
            </button>
          </div>
        </form>
      )}

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-lg font-bold text-[#111827]">Your workspaces <span className="font-mono text-sm text-slate-400">({rows.length})</span></h2>
          <div className="relative w-full sm:w-72">
            <Search className="absolute top-2.5 left-3 h-4 w-4 text-slate-400" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search investigations" className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400" />
          </div>
        </div>
        {loading ? (
          <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-white py-12 text-sm text-slate-500"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading investigations…</div>
        ) : filtered.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
            <BriefcaseBusiness className="mx-auto h-8 w-8 text-blue-500" />
            <h3 className="mt-3 font-display text-lg font-bold text-slate-800">{rows.length ? 'No matching investigations' : 'Start an investigation'}</h3>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">{rows.length ? 'Try another title or description.' : 'Create a workspace, then link existing recorded analyses or stored live sessions. No sample events or media are added.'}</p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((row) => (
              <article key={row.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex items-start justify-between gap-2">
                  <Link to={`/dashboard/investigations/${row.id}`} className="min-w-0 flex-1">
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${statusStyle(row.status)}`}>{row.status}</span>
                    <h3 className="mt-3 truncate font-display text-lg font-bold text-slate-900">{row.title}</h3>
                  </Link>
                  <button type="button" onClick={() => void remove(row)} aria-label={`Delete ${row.title}`} className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button>
                </div>
                <p className="mt-1 line-clamp-2 min-h-10 text-sm text-slate-500">{row.description || 'No description provided.'}</p>
                <div className="mt-4 grid grid-cols-4 gap-2 border-t border-slate-100 pt-3 text-center">
                  {[
                    ['Sources', row.source_count],
                    ['Events', row.event_count],
                    ['Tracks', row.track_count],
                    ['Notes', row.note_count],
                  ].map(([label, count]) => <div key={label} className="rounded-lg bg-[#F5F8FC] py-2"><div className="font-mono text-sm font-bold text-slate-800">{count}</div><div className="text-[10px] text-slate-500">{label}</div></div>)}
                </div>
                <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{formatDate(row.updated_at)}</span>
                  <span className="font-mono">{row.id.slice(0, 8)}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

interface ReviewFrame {
  key: string
  eventTitle: string
  timestamp: number
  frameNumber: number
  original: string | null
  annotated: string | null
  explanation: string
  confidence: number | null
  trackLabels: string[]
}

function EvidenceAsset({ path, alt, lazy = false }: { path: string | null; alt: string; lazy?: boolean }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [visible, setVisible] = useState(!lazy)
  const [state, setState] = useState<{ path: string; url: string | null; failed: boolean }>({ path: '', url: null, failed: false })
  const current = state.path === path
  useEffect(() => {
    if (!lazy || visible || !containerRef.current) return
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true)
        observer.disconnect()
      }
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [lazy, visible])
  useEffect(() => {
    if (!path || !visible) return
    let active = true
    let createdUrl: string | null = null
    fetchInvestigationImageBlobUrl(path)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setState({ path, url, failed: false })
      })
      .catch(() => {
        if (active) setState({ path, url: null, failed: true })
      })
    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [path, visible])
  if (!visible) return <div ref={containerRef} className="aspect-video animate-pulse bg-slate-100" />
  if (!path || (current && state.failed)) {
    return <div ref={containerRef} className="flex aspect-video items-center justify-center bg-slate-100 text-slate-400"><ImageOff className="h-5 w-5" /></div>
  }
  if (!current || !state.url) return <div ref={containerRef} className="aspect-video animate-pulse bg-slate-100" />
  return <img src={state.url} alt={alt} loading={lazy ? 'lazy' : 'eager'} className="aspect-video w-full bg-slate-950 object-contain" />
}

function toReviewFrames(items: InvestigationEvidenceItem[]): ReviewFrame[] {
  const groups = new Map<string, ReviewFrame>()
  for (const item of items) {
    const key = `${item.event_id}:${item.frame_number}:${item.timestamp_seconds}`
    const current = groups.get(key) ?? {
      key,
      eventTitle: item.event_title,
      timestamp: item.timestamp_seconds,
      frameNumber: item.frame_number,
      original: null,
      annotated: null,
      explanation: item.explanation,
      confidence: item.confidence,
      trackLabels: item.track_labels,
    }
    if (item.evidence_type === 'original_frame') current.original = item.image_url
    else current.annotated = item.image_url
    groups.set(key, current)
  }
  return [...groups.values()].sort((a, b) => a.timestamp - b.timestamp || a.frameNumber - b.frameNumber)
}

function InvestigationDetailWorkspace({ investigationId }: { investigationId: string }) {
  const navigate = useNavigate()
  const [detail, setDetail] = useState<InvestigationDetail | null>(null)
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [liveSessions, setLiveSessions] = useState<LiveSessionStatusResponse[]>([])
  const [timeline, setTimeline] = useState<InvestigationTimeline | null>(null)
  const [graph, setGraph] = useState<InvestigationGraph | null>(null)
  const [tracks, setTracks] = useState<InvestigationTrack[]>([])
  const [trackDetail, setTrackDetail] = useState<InvestigationTrackDetail | null>(null)
  const [reviewFrames, setReviewFrames] = useState<ReviewFrame[]>([])
  const [reviewIndex, setReviewIndex] = useState(0)
  const [selectedTimeline, setSelectedTimeline] = useState<InvestigationTimelineItem | null>(null)
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('timeline')
  const [loading, setLoading] = useState(true)
  const [timelineLoading, setTimelineLoading] = useState(false)
  const [graphLoading, setGraphLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [titleDraft, setTitleDraft] = useState('')
  const [descriptionDraft, setDescriptionDraft] = useState('')
  const [sourceChoice, setSourceChoice] = useState('')
  const [trackSourceId, setTrackSourceId] = useState('')
  const [trackQuery, setTrackQuery] = useState('')
  const [entityFilter, setEntityFilter] = useState<'all' | 'person' | 'object'>('all')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [trackFilter, setTrackFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [timelineOffset, setTimelineOffset] = useState(0)
  const [noteContent, setNoteContent] = useState('')
  const [noteSourceId, setNoteSourceId] = useState('')
  const [noteEventLinkId, setNoteEventLinkId] = useState('')
  const [noteTimestamp, setNoteTimestamp] = useState('')
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [editingNoteContent, setEditingNoteContent] = useState('')
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [videoSourceId, setVideoSourceId] = useState<string | null>(null)
  const [videoLoading, setVideoLoading] = useState(false)
  const [videoProgress, setVideoProgress] = useState(0)
  const [videoPreparationMessage, setVideoPreparationMessage] = useState('')
  const [videoPlaybackError, setVideoPlaybackError] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const loadDetail = useCallback(async () => {
    const result = await getInvestigation(investigationId)
    setTimelineLoading(true)
    setGraphLoading(true)
    setDetail(result)
    setTitleDraft(result.title)
    setDescriptionDraft(result.description)
    setTrackSourceId((current) => current || result.sources[0]?.id || '')
  }, [investigationId])

  useEffect(() => {
    let active = true
    Promise.all([getInvestigation(investigationId), listUserAnalyses(), listLiveMonitoringSessions()])
      .then(([investigation, analysisRows, sessions]) => {
        if (!active) return
        setTimelineLoading(true)
        setGraphLoading(true)
        setDetail(investigation)
        setTitleDraft(investigation.title)
        setDescriptionDraft(investigation.description)
        setTrackSourceId(investigation.sources[0]?.id ?? '')
        setAnalyses(analysisRows.filter((item) => item.status === 'completed'))
        setLiveSessions(sessions)
        setError('')
      })
      .catch((reason) => {
        if (active) setError(getAuthErrorMessage(reason, 'Could not load this investigation.'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [investigationId])

  useEffect(() => {
    if (!detail) return
    let active = true
    const [selectedTrackSource, selectedTrackId] = trackFilter ? trackFilter.split(':') : []
    const params = {
      event_category: categoryFilter || undefined,
      source_id: selectedTrackSource || sourceFilter || undefined,
      severity: severityFilter || undefined,
      track_id: selectedTrackId ? Number(selectedTrackId) : undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      limit: 100,
      offset: timelineOffset,
    }
    getInvestigationTimeline(investigationId, params)
      .then((result) => {
        if (!active) return
        setTimeline((current) => timelineOffset > 0 && current
          ? { ...result, items: [...current.items, ...result.items] }
          : result)
      })
      .catch((reason) => {
        if (active) setError(getAuthErrorMessage(reason, 'Could not load the investigation timeline.'))
      })
      .finally(() => {
        if (active) setTimelineLoading(false)
      })
    return () => {
      active = false
    }
  }, [categoryFilter, detail, endDate, investigationId, severityFilter, sourceFilter, startDate, timelineOffset, trackFilter])

  useEffect(() => {
    if (!detail) return
    let active = true
    getInvestigationGraph(investigationId)
      .then((result) => {
        if (active) setGraph(result)
      })
      .catch((reason) => {
        if (active) setError(getAuthErrorMessage(reason, 'Could not generate the relationship graph.'))
      })
      .finally(() => {
        if (active) setGraphLoading(false)
      })
    return () => {
      active = false
    }
  }, [detail, investigationId])

  useEffect(() => {
    if (!detail || !trackSourceId) {
      return
    }
    let active = true
    const timeout = window.setTimeout(() => {
      searchInvestigationTracks(investigationId, {
        q: trackQuery || undefined,
        entity: entityFilter === 'all' ? undefined : entityFilter,
        source_id: trackSourceId,
        limit: 250,
      })
        .then((result) => {
          if (active) setTracks(result)
        })
        .catch((reason) => {
          if (active) setError(getAuthErrorMessage(reason, 'Could not search tracks in this source.'))
        })
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timeout)
    }
  }, [detail, entityFilter, investigationId, trackQuery, trackSourceId])

  useEffect(() => {
    if (!videoUrl || !selectedTimeline || selectedTimeline.source_type !== 'analysis') return
    const video = videoRef.current
    if (video && video.readyState >= 1) video.currentTime = selectedTimeline.timestamp_seconds
  }, [selectedTimeline, videoUrl])

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl)
  }, [videoUrl])

  const refresh = async () => {
    try {
      await loadDetail()
      setNotice('')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not refresh the investigation.'))
    }
  }

  const linkedAnalysisIds = new Set(
    (detail?.sources ?? []).flatMap((source) => source.analysis_id ? [source.analysis_id] : []),
  )
  const linkedLiveSessionIds = new Set(
    (detail?.sources ?? []).flatMap((source) => source.live_session_id ? [source.live_session_id] : []),
  )
  const sourceChoiceOptions = [
    ...analyses.filter((analysis) => !linkedAnalysisIds.has(analysis.analysis_id)).map((analysis) => ({
      value: `analysis:${analysis.analysis_id}`,
      label: `${analysis.video_filename} · Analysis ${analysis.analysis_id.slice(0, 8)}`,
    })),
    ...liveSessions.filter((session) => session.status === 'stopped' && !linkedLiveSessionIds.has(session.session_id)).map((session) => ({
      value: `live:${session.session_id}`,
      label: `Live ${session.status} · ${new Date(session.started_at).toLocaleString()} · ${session.session_id.slice(0, 8)}`,
    })),
  ]

  const setFilters = () => {
    setTimelineLoading(true)
    setTimelineOffset(0)
  }

  const handleAddSource = async () => {
    if (!sourceChoice) return
    const [kind, id] = sourceChoice.split(':', 2)
    try {
      await addInvestigationSource(
        investigationId,
        kind === 'analysis' ? { analysis_id: id } : { live_session_id: id },
      )
      setSourceChoice('')
      await refresh()
      setNotice('Source linked. Track IDs remain scoped to this source.')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not link that source.'))
    }
  }

  const handleRemoveSource = async (source: InvestigationSource) => {
    if (!window.confirm(`Remove ${source.source_label} from this investigation? Existing source records and evidence will remain unchanged.`)) return
    try {
      await removeInvestigationSource(investigationId, source.id)
      if (trackSourceId === source.id) setTrackSourceId('')
      await refresh()
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not remove this source.'))
    }
  }

  const handleSaveDetails = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!detail) return
    try {
      await updateInvestigation(investigationId, {
        title: titleDraft.trim(),
        description: descriptionDraft.trim(),
      })
      await refresh()
      setNotice('Investigation details saved.')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not save investigation details.'))
    }
  }

  const handleStatusChange = async (status: InvestigationDetail['status']) => {
    try {
      await updateInvestigation(investigationId, { status })
      await refresh()
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not update investigation status.'))
    }
  }

  const handleDeleteInvestigation = async () => {
    if (!window.confirm('Delete this investigation and its private notes and links? Source videos, events and evidence are not deleted.')) return
    try {
      await deleteInvestigation(investigationId)
      navigate('/dashboard/investigations')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not delete this investigation.'))
    }
  }

  const handleToggleTrack = async (track: InvestigationTrack) => {
    try {
      if (track.linked) {
        const link = detail?.linked_tracks.find((item) => item.source_id === track.source_id && item.track_id === track.track_id)
        if (link) await unlinkInvestigationTrack(investigationId, link.id)
      } else {
        await linkInvestigationTrack(investigationId, { source_id: track.source_id, track_id: track.track_id })
      }
      await refresh()
      setNotice(track.linked ? 'Track unlinked.' : 'Track linked with its source scope.')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not update the linked track.'))
    }
  }

  const handleOpenTrack = async (track: InvestigationTrack) => {
    setError('')
    setTrackDetail(null)
    try {
      const result = await getInvestigationTrackDetail(investigationId, track.source_id, track.track_id)
      setTrackDetail(result)
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not load track history.'))
    }
  }

  const handleOpenTimelineTrack = async (item: InvestigationTimelineItem) => {
    const trackId = item.track_ids[0]
    if (trackId === undefined) return
    const knownTrack = tracks.find(
      (track) => track.source_id === item.source_id && track.track_id === trackId,
    )
    setTrackSourceId(item.source_id)
    setActiveTab('tracks')
    if (knownTrack) {
      await handleOpenTrack(knownTrack)
      return
    }
    try {
      setTrackDetail(await getInvestigationTrackDetail(investigationId, item.source_id, trackId))
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not load the source-scoped track.'))
    }
  }

  const handleToggleEvent = async (item: InvestigationTimelineItem) => {
    if (!item.event_id) return
    const link = detail?.linked_events.find(
      (candidate) => candidate.source_id === item.source_id
        && (candidate.event_id === item.event_id || candidate.live_event_id === item.event_id),
    )
    try {
      if (link) {
        await unlinkInvestigationEvent(investigationId, link.id)
      } else {
        await linkInvestigationEvent(
          investigationId,
          item.source_type === 'analysis'
            ? { source_id: item.source_id, event_id: item.event_id }
            : { source_id: item.source_id, live_event_id: item.event_id },
        )
      }
      await refresh()
      setNotice(link ? 'Event unlinked.' : 'Event linked to investigation.')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not update the linked event.'))
    }
  }

  const openEvidence = async (item: InvestigationTimelineItem) => {
    setSelectedTimeline(item)
    setTrackDetail(null)
    setActiveTab('evidence')
    setReviewFrames([])
    setReviewIndex(0)
    try {
      if (item.event_id) {
        const evidence = await getInvestigationEvidence(investigationId, {
          source_id: item.source_id,
          event_id: item.event_id,
        })
        setReviewFrames(toReviewFrames(evidence))
      } else {
        const frames: ReviewFrame[] = item.evidence.map((entry) => ({
          key: entry.id,
          eventTitle: item.title,
          timestamp: entry.timestamp_seconds,
          frameNumber: Number(entry.id.split(':').pop() ?? 0),
          original: entry.evidence_type === 'original_frame' ? entry.image_url : null,
          annotated: entry.evidence_type !== 'original_frame' ? entry.image_url : null,
          explanation: item.explanation,
          confidence: item.confidence,
          trackLabels: item.track_labels,
        }))
        setReviewFrames(frames)
      }
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Evidence could not be loaded.'))
    }
  }

  const browseAllEvidence = async () => {
    setSelectedTimeline(null)
    setTrackDetail(null)
    setReviewFrames([])
    setReviewIndex(0)
    try {
      setReviewFrames(toReviewFrames(await getInvestigationEvidence(investigationId)))
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not load saved investigation evidence.'))
    }
  }

  const loadSelectedVideo = async () => {
    const source = detail?.sources.find((item) => item.id === selectedTimeline?.source_id)
    if (!source?.video_id || videoLoading) return
    setVideoLoading(true)
    setVideoPlaybackError(null)
    setVideoProgress(0)
    try {
      const url = await fetchVideoBlobUrl(source.video_id, (progress, message) => {
        setVideoProgress(progress)
        setVideoPreparationMessage(message)
      })
      setVideoUrl(url)
      setVideoSourceId(source.video_id)
    } catch (reason) {
      setVideoPlaybackError(
        reason instanceof Error
          ? reason.message
          : getAuthErrorMessage(reason, 'Could not prepare browser-compatible video playback.'),
      )
    } finally {
      setVideoLoading(false)
    }
  }

  const submitNote = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!noteContent.trim()) return
    if (noteTimestamp && !noteSourceId && !noteEventLinkId) {
      setError('Choose a source before attaching a timestamp to a note.')
      return
    }
    try {
      await addInvestigationNote(investigationId, {
        content: noteContent.trim(),
        source_id: noteSourceId || undefined,
        investigation_event_id: noteEventLinkId || undefined,
        timestamp_seconds: noteTimestamp ? Number(noteTimestamp) : undefined,
      })
      setNoteContent('')
      setNoteTimestamp('')
      setNoteEventLinkId('')
      await refresh()
      setNotice('Investigator note saved.')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not save investigator note.'))
    }
  }

  const saveEditedNote = async (note: InvestigationNote) => {
    try {
      await updateInvestigationNote(investigationId, note.id, {
        content: editingNoteContent,
        source_id: note.source_id,
        investigation_event_id: note.investigation_event_id,
        timestamp_seconds: note.timestamp_seconds,
      })
      setEditingNoteId(null)
      await refresh()
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not update investigator note.'))
    }
  }

  const removeNote = async (note: InvestigationNote) => {
    if (!window.confirm('Delete this investigator-written note?')) return
    try {
      await deleteInvestigationNote(investigationId, note.id)
      await refresh()
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not delete investigator note.'))
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center rounded-3xl border border-slate-200 bg-white py-20 text-sm text-slate-500"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading investigation workspace…</div>
  }
  if (!detail) {
    return <div className="space-y-4"><ErrorBanner message={error || 'Investigation not found.'} /><Link to="/dashboard/investigations" className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600"><ArrowLeft className="h-4 w-4" />All investigations</Link></div>
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/dashboard/investigations" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-blue-600"><ArrowLeft className="h-4 w-4" />All investigations</Link>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-500">Status</span>
          <select aria-label="Investigation status" value={detail.status} onChange={(event) => void handleStatusChange(event.target.value as InvestigationDetail['status'])} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold capitalize outline-none focus:border-blue-400">
            <option value="open">Open</option><option value="reviewing">Reviewing</option><option value="closed">Closed</option>
          </select>
          <button type="button" onClick={() => void handleDeleteInvestigation()} className="rounded-xl border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-600 hover:bg-rose-50">Delete</button>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {notice && <div role="status" className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-700"><Check className="h-4 w-4" />{notice}<button type="button" className="ml-auto" onClick={() => setNotice('')} aria-label="Dismiss"><X className="h-4 w-4" /></button></div>}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <form onSubmit={handleSaveDetails} className="rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${statusStyle(detail.status)}`}>{detail.status}</span>
            <span className="font-mono text-[11px] text-slate-400">Investigation ID · {detail.id}</span>
          </div>
          <input value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} maxLength={200} aria-label="Investigation title" className="mt-3 w-full border-0 bg-transparent p-0 font-display text-2xl font-extrabold tracking-tight text-slate-900 outline-none focus:ring-0" />
          <textarea value={descriptionDraft} onChange={(event) => setDescriptionDraft(event.target.value)} maxLength={10000} aria-label="Investigation description" rows={2} placeholder="Add investigation context…" className="mt-2 w-full resize-y rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-sm text-slate-600 outline-none focus:border-blue-400" />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-slate-400">Updated {formatDate(detail.updated_at)}</span>
            <button type="submit" className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white hover:bg-blue-700">Save details</button>
          </div>
        </form>
        <div className="rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs sm:p-6">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-lg font-bold text-slate-900">Linked sources</h2>
              <p className="text-xs text-slate-500">Each track ID stays inside its own analysis or live session.</p>
            </div>
            <span className="rounded-lg bg-blue-50 px-2 py-1 font-mono text-xs font-bold text-blue-700">{detail.sources.length}</span>
          </div>
          <div className="mt-3 flex gap-2">
            <select aria-label="Choose source to link" value={sourceChoice} onChange={(event) => setSourceChoice(event.target.value)} className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-[#F5F8FC] px-2.5 py-2 text-xs outline-none focus:border-blue-400">
              <option value="">Select an existing source…</option>
              {sourceChoiceOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <button type="button" disabled={!sourceChoice} onClick={() => void handleAddSource()} className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"><Plus className="h-3.5 w-3.5" />Link</button>
          </div>
          <div className="mt-3 max-h-52 space-y-2 overflow-y-auto">
            {detail.sources.length === 0 ? <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">No source linked yet. Choose an existing analysis or live session above.</p> : detail.sources.map((source) => (
              <div key={source.id} className="rounded-xl border border-slate-200 bg-[#F8FAFC] p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                      {source.source_type === 'analysis' ? <Film className="h-3.5 w-3.5 text-blue-600" /> : <Radio className="h-3.5 w-3.5 text-violet-600" />}
                      <span className="truncate">{source.source_label}</span>
                    </div>
                    <p className="mt-1 font-mono text-[10px] text-slate-500">Source ID · {source.source_id}</p>
                  </div>
                  <button type="button" onClick={() => void handleRemoveSource(source)} aria-label={`Remove ${source.source_label}`} className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><X className="h-4 w-4" /></button>
                </div>
                <p className="mt-2 text-[10px] leading-relaxed text-slate-500">{source.data_availability}</p>
                <div className="mt-1 flex gap-3 font-mono text-[10px] text-slate-400"><span>{source.track_count} tracks</span><span>{source.event_count} events</span><span className="capitalize">{source.status}</span></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="flex gap-1 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xs">
        {TABS.map((tab) => {
          const Icon = tab.icon
          return <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`inline-flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs font-semibold transition ${activeTab === tab.id ? 'bg-[#EFF6FF] text-blue-700 shadow-xs' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'}`}><Icon className="h-4 w-4" />{tab.label}{tab.id === 'notes' && <span className="rounded-full bg-slate-100 px-1.5 font-mono text-[10px]">{detail.notes.length}</span>}</button>
        })}
      </div>

      {activeTab === 'timeline' && (
        <TimelinePanel
          detail={detail}
          timeline={timeline}
          loading={timelineLoading}
          categoryFilter={categoryFilter}
          severityFilter={severityFilter}
          trackFilter={trackFilter}
          sourceFilter={sourceFilter}
          startDate={startDate}
          endDate={endDate}
          onCategory={(value) => { setCategoryFilter(value); setFilters() }}
          onSeverity={(value) => { setSeverityFilter(value); setFilters() }}
          onTrack={(value) => { setTrackFilter(value); setFilters() }}
          onSourceFilter={(value) => { setSourceFilter(value); setFilters() }}
          onStartDate={(value) => { setStartDate(value); setFilters() }}
          onEndDate={(value) => { setEndDate(value); setFilters() }}
          onSelectEvidence={openEvidence}
          onToggleEvent={(item) => void handleToggleEvent(item)}
          onOpenTrack={(item) => void handleOpenTimelineTrack(item)}
          onLoadMore={() => {
            setTimelineLoading(true)
            setTimelineOffset((current) => current + (timeline?.items.length ?? 0))
          }}
        />
      )}

      {activeTab === 'tracks' && (
        <TrackPanel
          sources={detail.sources}
          selectedSourceId={trackSourceId}
          onSourceChange={(value) => { setTracks([]); setTrackSourceId(value) }}
          query={trackQuery}
          onQuery={setTrackQuery}
          entityFilter={entityFilter}
          onEntityFilter={setEntityFilter}
          tracks={tracks}
          detail={trackDetail}
          onOpenTrack={handleOpenTrack}
          onToggleTrack={(track) => void handleToggleTrack(track)}
          onEvidence={(track) => {
            setTrackDetail(track)
            const frames = (track.frames ?? []).map((frame) => ({
              key: `track:${frame.frame_index}`,
              eventTitle: `${track.entity_label ?? 'Track'} ${track.track_label ?? ''}`,
              timestamp: frame.timestamp_seconds,
              frameNumber: frame.frame_index,
              original: frame.frame_available ? frame.frame_url : null,
              annotated: null,
              explanation: track.temporary_id_notice ?? '',
              confidence: frame.selected_detection.confidence,
              trackLabels: [track.track_label ?? ''],
            }))
            const liveFrames = (track.related_events ?? [])
              .filter((event) => event.snapshot_url)
              .map((event) => ({
                key: event.id,
                eventTitle: event.title ?? event.event_type,
                timestamp: event.start_timestamp ?? event.timestamp_seconds ?? 0,
                frameNumber: 0,
                original: null,
                annotated: event.snapshot_url ?? null,
                explanation: event.description ?? '',
                confidence: event.confidence,
                trackLabels: [track.track_label ?? ''],
              }))
            setReviewFrames(frames.length ? frames : liveFrames)
            setReviewIndex(0)
            setSelectedTimeline(null)
            setActiveTab('evidence')
          }}
        />
      )}

      {activeTab === 'graph' && <RelationshipGraph graph={graph} loading={graphLoading} />}

      {activeTab === 'evidence' && (
        <EvidenceReview
          frames={reviewFrames}
          index={reviewIndex}
          onIndex={setReviewIndex}
          selected={reviewFrames[reviewIndex] ?? null}
          selectedTimeline={selectedTimeline}
          source={detail.sources.find((source) => source.id === selectedTimeline?.source_id) ?? null}
          videoUrl={videoSourceId === detail.sources.find((source) => source.id === selectedTimeline?.source_id)?.video_id ? videoUrl : null}
          videoRef={videoRef}
          videoLoading={videoLoading}
          videoProgress={videoProgress}
          videoPreparationMessage={videoPreparationMessage}
          videoPlaybackError={videoPlaybackError}
          onVideoError={(message) => setVideoPlaybackError(message)}
          onLoadVideo={() => void loadSelectedVideo()}
          onBrowseAll={browseAllEvidence}
        />
      )}

      {activeTab === 'notes' && (
        <NotesPanel
          detail={detail}
          content={noteContent}
          onContent={setNoteContent}
          sourceId={noteSourceId}
          onSourceId={setNoteSourceId}
          eventLinkId={noteEventLinkId}
          onEventLinkId={setNoteEventLinkId}
          timestamp={noteTimestamp}
          onTimestamp={setNoteTimestamp}
          editingNoteId={editingNoteId}
          editingContent={editingNoteContent}
          onEditingContent={setEditingNoteContent}
          onSubmit={submitNote}
          onEdit={(note) => { setEditingNoteId(note.id); setEditingNoteContent(note.content) }}
          onSaveEdit={(note) => void saveEditedNote(note)}
          onCancelEdit={() => setEditingNoteId(null)}
          onDelete={(note) => void removeNote(note)}
        />
      )}
    </div>
  )
}

function TimelinePanel(props: {
  detail: InvestigationDetail
  timeline: InvestigationTimeline | null
  loading: boolean
  categoryFilter: string
  severityFilter: string
  trackFilter: string
  sourceFilter: string
  startDate: string
  endDate: string
  onCategory: (value: string) => void
  onSeverity: (value: string) => void
  onTrack: (value: string) => void
  onSourceFilter: (value: string) => void
  onStartDate: (value: string) => void
  onEndDate: (value: string) => void
  onSelectEvidence: (item: InvestigationTimelineItem) => void
  onToggleEvent: (item: InvestigationTimelineItem) => void
  onOpenTrack: (item: InvestigationTimelineItem) => void
  onLoadMore: () => void
}) {
  const [filterTracks, setFilterTracks] = useState<InvestigationTrack[]>([])
  const [filterSourceId, setFilterSourceId] = useState(props.detail.sources[0]?.id ?? '')
  const activeFilterSourceId = props.detail.sources.some((source) => source.id === filterSourceId)
    ? filterSourceId
    : props.detail.sources[0]?.id ?? ''
  const visibleFilterTracks = filterTracks.filter((track) => track.source_id === activeFilterSourceId)
  useEffect(() => {
    if (!activeFilterSourceId) return
    let active = true
    searchInvestigationTracks(props.detail.id, { source_id: activeFilterSourceId, limit: 250 })
      .then((result) => { if (active) setFilterTracks(result) })
      .catch(() => { if (active) setFilterTracks([]) })
    return () => { active = false }
  }, [activeFilterSourceId, props.detail.id])

  const getEventLink = (item: InvestigationTimelineItem) => props.detail.linked_events.find(
    (event) => event.source_id === item.source_id
      && (event.event_id === item.event_id || event.live_event_id === item.event_id),
  )
  const getTrack = (item: InvestigationTimelineItem) => filterTracks.find(
    (track) => track.source_id === item.source_id && track.track_id === item.track_ids[0],
  )

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="font-display text-lg font-bold text-slate-900">Unified source timeline</h2><p className="text-xs text-slate-500">Source-local timestamps; different recordings and live sessions are not time-synchronized.</p></div>
          <span className="rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-xs font-bold text-slate-600">{props.timeline?.total ?? 0} records</span>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
          <select aria-label="Event category filter" value={props.categoryFilter} onChange={(event) => props.onCategory(event.target.value)} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs">
            <option value="">All categories</option><option value="detection">Detection observations</option><option value="tracking">Track milestones</option><option value="people_movement">People movement</option><option value="object_interactions">Object interactions</option><option value="possible_unattended_objects">Possible unattended objects</option><option value="other_activities">Other activities</option>
          </select>
          <select aria-label="Timeline source filter" value={props.sourceFilter} onChange={(event) => props.onSourceFilter(event.target.value)} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs">
            <option value="">All linked sources</option>{props.detail.sources.map((source) => <option key={source.id} value={source.id}>{source.source_label}</option>)}
          </select>
          <select aria-label="Track source filter" value={activeFilterSourceId} onChange={(event) => { setFilterSourceId(event.target.value); props.onTrack('') }} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs">
            <option value="">Select a track source</option>{props.detail.sources.map((source) => <option key={source.id} value={source.id}>{source.source_label}</option>)}
          </select>
          <select aria-label="Track filter" value={props.trackFilter} onChange={(event) => props.onTrack(event.target.value)} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs">
            <option value="">All tracks in source</option>{visibleFilterTracks.map((track) => <option key={`${track.source_id}:${track.track_id}`} value={`${track.source_id}:${track.track_id}`}>Track {track.track_label} · {track.entity_label}</option>)}
          </select>
          <select aria-label="Severity filter" value={props.severityFilter} onChange={(event) => props.onSeverity(event.target.value)} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs">
            <option value="">All severities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select>
          <input aria-label="Timeline start date" type="date" value={props.startDate} onChange={(event) => props.onStartDate(event.target.value)} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs" />
          <input aria-label="Timeline end date" type="date" value={props.endDate} onChange={(event) => props.onEndDate(event.target.value)} className="rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs" />
        </div>
        <p className="mt-2 text-[10px] text-slate-400">Date filters use the source record creation date. Track filters are source-scoped even when two sessions reuse the same numeric ID.</p>
      </div>

      {props.loading && !props.timeline ? <div className="rounded-2xl border border-slate-200 bg-white py-12 text-center text-sm text-slate-500"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Loading event and detection records…</div> : null}
      {!props.loading && !props.timeline?.items.length ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-12 text-center"><CircleHelp className="mx-auto h-7 w-7 text-slate-400" /><h3 className="mt-2 font-semibold text-slate-800">No timeline records</h3><p className="mt-1 text-xs text-slate-500">Link a source with saved detections or events, or adjust the filters.</p></div> : null}
      {props.timeline?.items.length ? (
        <div className="relative space-y-3">
          <div className="absolute top-5 bottom-5 left-[17px] w-px bg-slate-200" />
          {props.timeline.items.map((item) => {
            const linkedEvent = getEventLink(item)
            const track = getTrack(item)
            return (
              <article key={item.id} className="relative ml-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
                <span className={`absolute top-5 -left-[25px] h-3 w-3 rounded-full border-2 border-white ${item.record_type === 'anomaly' ? 'bg-rose-500' : item.record_type === 'detection' ? 'bg-violet-500' : item.record_type === 'track_observation' ? 'bg-amber-500' : 'bg-blue-500'}`} />
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <button type="button" onClick={() => void props.onSelectEvidence(item)} className="min-w-0 flex-1 text-left">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-blue-50 px-2 py-1 font-mono text-[10px] font-bold uppercase text-blue-700">{item.record_type.replace('_', ' ')}</span>
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">{item.event_category.replaceAll('_', ' ')}</span>
                      {item.severity && <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${item.severity === 'high' ? 'bg-rose-50 text-rose-700' : item.severity === 'medium' ? 'bg-amber-50 text-amber-700' : 'bg-blue-50 text-blue-700'}`}>{item.severity}</span>}
                    </div>
                    <h3 className="mt-2 font-display text-sm font-bold text-slate-900">{item.title}</h3>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">{item.explanation}</p>
                  </button>
                  <div className="flex shrink-0 flex-col items-end gap-1 text-right">
                    <span className="rounded-lg border border-slate-200 bg-[#F8FAFC] px-2.5 py-1 font-mono text-xs font-semibold text-slate-800"><Clock3 className="mr-1 inline h-3.5 w-3.5 text-blue-600" />{formatTime(item.timestamp_seconds)}</span>
                    {item.confidence !== null && <span className="font-mono text-[10px] text-slate-500">{Math.round(item.confidence * 100)}% confidence</span>}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] text-slate-600">{item.source_label}</span>
                  {item.event_id && <span className="font-mono text-[10px] text-slate-400">Event ID · {item.event_id.slice(0, 8)}</span>}
                  {item.track_labels.map((label, index) => <button key={`${label}:${index}`} type="button" onClick={() => props.onOpenTrack(item)} className="rounded-md bg-violet-50 px-2 py-1 font-mono text-[10px] font-semibold text-violet-700">{label}</button>)}
                </div>
                {item.evidence[0] && (
                  <button type="button" onClick={() => void props.onSelectEvidence(item)} className="mt-3 flex w-fit items-center gap-3 rounded-xl border border-slate-200 bg-[#F8FAFC] p-2 text-left hover:border-blue-200">
                    <span className="block w-32 overflow-hidden rounded-lg border border-slate-200"><EvidenceAsset path={item.evidence[0].image_url} alt={`Evidence thumbnail for ${item.title}`} lazy /></span>
                    <span><span className="block text-[10px] font-semibold text-slate-700">Evidence preview</span><span className="mt-1 block font-mono text-[10px] text-slate-500">{item.evidence[0].evidence_type.replaceAll('_', ' ')} · {formatTime(item.evidence[0].timestamp_seconds)}</span></span>
                  </button>
                )}
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
                  <span className="text-[10px] text-slate-400">{item.evidence.length ? `${item.evidence.length} evidence reference(s)` : 'No saved frame for this record'}</span>
                  <div className="flex gap-2">
                    {track && <button type="button" onClick={() => props.onOpenTrack(item)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-[10px] font-semibold text-slate-600 hover:bg-slate-50">Inspect {entityLabel(track)}</button>}
                    {item.event_id && <button type="button" onClick={() => props.onToggleEvent(item)} className={`rounded-lg px-2.5 py-1.5 text-[10px] font-semibold ${linkedEvent ? 'border border-blue-200 bg-blue-50 text-blue-700' : 'border border-slate-200 text-slate-600 hover:bg-slate-50'}`}>{linkedEvent ? 'Unlink event' : 'Link event'}</button>}
                    <button type="button" onClick={() => void props.onSelectEvidence(item)} className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1.5 text-[10px] font-semibold text-white"><FileImage className="h-3 w-3" />Review evidence</button>
                  </div>
                </div>
              </article>
            )
          })}
          {props.timeline.has_more && <div className="pt-2 text-center"><button type="button" disabled={props.loading} onClick={props.onLoadMore} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 disabled:opacity-50">{props.loading ? 'Loading…' : `Load more (${props.timeline.total - props.timeline.items.length} remaining)`}</button></div>}
        </div>
      ) : null}
    </section>
  )
}

function TrackPanel(props: {
  sources: InvestigationSource[]
  selectedSourceId: string
  onSourceChange: (value: string) => void
  query: string
  onQuery: (value: string) => void
  entityFilter: 'all' | 'person' | 'object'
  onEntityFilter: (value: 'all' | 'person' | 'object') => void
  tracks: InvestigationTrack[]
  detail: InvestigationTrackDetail | null
  onOpenTrack: (track: InvestigationTrack) => void
  onToggleTrack: (track: InvestigationTrack) => void
  onEvidence: (detail: InvestigationTrackDetail) => void
}) {
  const [detailLoading, setDetailLoading] = useState(false)
  const handleOpen = async (track: InvestigationTrack) => {
    setDetailLoading(true)
    try { await props.onOpenTrack(track) } finally { setDetailLoading(false) }
  }
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.28fr)]">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex items-center justify-between"><div><h2 className="font-display text-lg font-bold text-slate-900">Track search</h2><p className="text-xs text-slate-500">IDs are temporary and source-specific.</p></div><Search className="h-4 w-4 text-blue-600" /></div>
        <label className="mt-4 block text-[11px] font-semibold text-slate-600">Source</label>
        <select value={props.selectedSourceId} onChange={(event) => props.onSourceChange(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2.5 text-xs">
          <option value="">Select a linked source</option>{props.sources.map((source) => <option key={source.id} value={source.id}>{source.source_label} · {source.source_id.slice(0, 8)}</option>)}
        </select>
        <div className="mt-3 flex gap-2">
          <input value={props.query} onChange={(event) => props.onQuery(event.target.value)} placeholder="Track ID, class or label" className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-xs outline-none focus:border-blue-400" />
          <select aria-label="Track entity filter" value={props.entityFilter} onChange={(event) => props.onEntityFilter(event.target.value as 'all' | 'person' | 'object')} className="rounded-xl border border-slate-200 bg-white px-2 text-xs"><option value="all">All</option><option value="person">Persons</option><option value="object">Objects</option></select>
        </div>
        <div className="mt-3 max-h-[34rem] space-y-2 overflow-y-auto">
          {props.tracks.length === 0 ? <div className="rounded-xl border border-dashed border-slate-200 px-3 py-8 text-center text-xs text-slate-500">{props.selectedSourceId ? 'No matching persisted tracks in this source.' : 'Link a source to search its actual tracks.'}</div> : props.tracks.map((track) => (
            <article key={`${track.source_id}:${track.track_id}`} className="rounded-xl border border-slate-200 bg-[#F8FAFC] p-3">
              <div className="flex items-start justify-between gap-2">
                <button type="button" onClick={() => void handleOpen(track)} className="min-w-0 flex-1 text-left">
                  <span className={`inline-flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10px] font-bold ${track.entity_label === 'Person' ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'}`}><span>{track.entity_label}</span><span>{track.track_label}</span></span>
                  <h3 className="mt-1.5 text-sm font-bold capitalize text-slate-800">{track.class_name}</h3>
                  <p className="mt-1 truncate text-[10px] text-slate-500">{props.sources.find((item) => item.id === track.source_id)?.source_label}</p>
                </button>
                <button type="button" onClick={() => props.onToggleTrack(track)} className={`shrink-0 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold ${track.linked ? 'border border-blue-200 bg-blue-50 text-blue-700' : 'bg-slate-900 text-white'}`}>{track.linked ? 'Linked' : 'Add track'}</button>
              </div>
              <div className="mt-2 flex justify-between text-[10px] text-slate-500"><span>{formatTime(track.first_seen_timestamp)} – {formatTime(track.last_seen_timestamp)}</span><span>{track.detection_count} saved observations</span></div>
            </article>
          ))}
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs sm:p-5">
        {!props.detail ? (
          <div className="flex min-h-64 flex-col items-center justify-center text-center"><UserRound className="h-8 w-8 text-blue-500" /><h3 className="mt-3 font-semibold text-slate-800">Select a source-scoped track</h3><p className="mt-1 max-w-sm text-xs text-slate-500">Inspect its actual detection history, movement samples, related persisted events, and available frames.</p></div>
        ) : (
          <div>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><span className="rounded-md bg-violet-50 px-2 py-1 font-mono text-xs font-bold text-violet-700">{props.detail.entity_label} · {props.detail.track_label}</span><h3 className="mt-2 font-display text-xl font-bold capitalize text-slate-900">{props.detail.class_name}</h3><p className="mt-1 text-xs text-slate-500">{props.detail.source_label}</p></div>
              <button type="button" onClick={() => props.onEvidence(props.detail!)} className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700">Review available frames</button>
            </div>
            <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-800">{props.detail.temporary_id_notice}</p>
            <p className="mt-2 text-[11px] text-slate-500">{props.detail.history_availability}</p>
            <div className="mt-4 grid grid-cols-3 gap-2">
              <Metric label="First observed" value={formatTime(props.detail.first_seen_timestamp ?? props.detail.track?.first_seen_timestamp ?? 0)} />
              <Metric label="Last observed" value={formatTime(props.detail.last_seen_timestamp ?? props.detail.track?.last_seen_timestamp ?? 0)} />
              <Metric label="Saved samples" value={String(props.detail.detection_count ?? props.detail.track?.frame_count ?? props.detail.detection_history?.length ?? 0)} />
            </div>
            <h4 className="mt-5 text-xs font-bold uppercase tracking-wide text-slate-500">Detection and movement history</h4>
            <div className="mt-2 max-h-52 overflow-auto rounded-xl border border-slate-200">
              {(props.detail.track?.timeline_points ?? props.detail.detection_history ?? []).length === 0 ? <p className="p-4 text-xs text-slate-500">No stored detection points are available for this track.</p> : (
                <table className="w-full text-left text-[11px]"><thead className="sticky top-0 bg-[#F8FAFC] text-slate-500"><tr><th className="p-2">Time</th><th className="p-2">Image position</th><th className="p-2">Confidence</th></tr></thead><tbody>
                  {(props.detail.track?.timeline_points ?? props.detail.detection_history ?? []).map((point, index) => <tr key={`${point.frame_index}:${index}`} className="border-t border-slate-100"><td className="p-2 font-mono">{formatTime(point.timestamp_seconds)}</td><td className="p-2">{Math.round(point.center_x)}, {Math.round(point.center_y)}</td><td className="p-2">{Math.round(point.confidence * 100)}%</td></tr>)}
                </tbody></table>
              )}
            </div>
            <h4 className="mt-5 text-xs font-bold uppercase tracking-wide text-slate-500">Related saved events</h4>
            <div className="mt-2 space-y-2">
              {(props.detail.related_events ?? []).length === 0 ? <p className="rounded-xl bg-[#F8FAFC] p-3 text-xs text-slate-500">No persisted events are associated with this source-scoped track.</p> : props.detail.related_events?.map((event) => <div key={event.id} className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 p-3"><div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-800">{event.title ?? event.event_type}</p><p className="font-mono text-[10px] text-slate-500">{formatTime(event.start_timestamp ?? event.timestamp_seconds ?? 0)} · {event.severity} · {Math.round(event.confidence * 100)}%</p></div>{event.snapshot_url && <span className="rounded-md bg-blue-50 px-2 py-1 text-[10px] text-blue-700">Snapshot saved</span>}</div>)}
            </div>
          </div>
        )}
        {detailLoading && <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/10"><div className="rounded-xl bg-white px-4 py-3 text-sm shadow-lg"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Loading track…</div></div>}
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-200 bg-[#F8FAFC] p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 font-mono text-xs font-bold text-slate-800">{value}</p></div>
}

function RelationshipGraph({ graph, loading }: { graph: InvestigationGraph | null; loading: boolean }) {
  if (loading && !graph) return <div className="rounded-2xl border border-slate-200 bg-white py-16 text-center text-sm text-slate-500"><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Building graph from stored events…</div>
  if (!graph || graph.nodes.length === 0) return <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-14 text-center"><GitBranch className="mx-auto h-8 w-8 text-violet-500" /><h3 className="mt-2 font-semibold text-slate-800">No stored relationships yet</h3><p className="mt-1 text-xs text-slate-500">Link a source with recorded events to build a graph. Tracks with no event relationship remain unconnected.</p></div>

  const maxEdges = 100
  const visibleEdges = graph.edges.slice(0, maxEdges)
  const visibleIds = new Set(visibleEdges.flatMap((edge) => [edge.source, edge.target]))
  if (visibleEdges.length === 0) graph.nodes.slice(0, 80).forEach((node) => visibleIds.add(node.id))
  const nodes = graph.nodes.filter((node) => visibleIds.has(node.id)).slice(0, 200)
  const buckets: Record<InvestigationGraphNode['node_type'], InvestigationGraphNode[]> = { person: [], object: [], unknown_track: [], event: [] }
  for (const node of nodes) buckets[node.node_type].push(node)
  const width = 1180
  const height = Math.max(430, Math.max(buckets.person.length, buckets.object.length, buckets.unknown_track.length, buckets.event.length) * 92 + 60)
  const x: Record<InvestigationGraphNode['node_type'], number> = { person: 150, object: 390, unknown_track: 620, event: 910 }
  const coordinates = new Map<string, { x: number; y: number }>()
  for (const [kind, bucket] of Object.entries(buckets) as Array<[InvestigationGraphNode['node_type'], InvestigationGraphNode[]]>) {
    bucket.forEach((node, index) => coordinates.set(node.id, { x: x[kind], y: 50 + index * 92 }))
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
        <div><h2 className="font-display text-lg font-bold text-slate-900">Event relationship graph</h2><p className="text-xs text-slate-500">Edges mean only “track involved in this stored event”; no identity matching across sources.</p></div>
        <span className="font-mono text-[10px] text-slate-500">{nodes.length} nodes · {visibleEdges.length} actual event links</span>
      </div>
      {graph.edges.length > maxEdges && <p className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-800">Showing the first {maxEdges} stored event relationships. Use the timeline filters to inspect individual records.</p>}
      <div className="overflow-auto bg-[#F8FAFC] p-3">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Investigation event relationship graph" className="min-w-[760px] rounded-xl bg-white">
          <defs><marker id="investigation-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L8,3 z" fill="#94A3B8" /></marker></defs>
          {visibleEdges.map((edge) => {
            const from = coordinates.get(edge.source)
            const to = coordinates.get(edge.target)
            if (!from || !to) return null
            const midX = (from.x + to.x) / 2
            const midY = (from.y + to.y) / 2
            return <g key={edge.id}><line x1={from.x + 82} y1={from.y + 26} x2={to.x - 78} y2={to.y + 26} stroke="#94A3B8" strokeWidth="1.5" markerEnd="url(#investigation-arrow)" /><title>{`${edge.label} at ${formatTime(edge.timestamp_seconds)}${edge.uncertainty ? ` · ${edge.uncertainty}` : ''}`}</title><text x={midX} y={midY - 5} textAnchor="middle" className="fill-slate-500" fontSize="10">{edge.label}</text><text x={midX} y={midY + 9} textAnchor="middle" className="fill-slate-400" fontSize="9">{formatTime(edge.timestamp_seconds)}</text></g>
          })}
          {nodes.map((node) => {
            const point = coordinates.get(node.id)
            if (!point) return null
            const color = node.node_type === 'person' ? '#2563EB' : node.node_type === 'object' ? '#D97706' : node.node_type === 'unknown_track' ? '#64748B' : '#7C3AED'
            return <g key={node.id}><title>{`${node.source_label} · ${node.label}${node.timestamp_seconds === null ? '' : ` · ${formatTime(node.timestamp_seconds)}`}`}</title><rect x={point.x - 78} y={point.y} width="160" height="52" rx="12" fill="white" stroke={color} strokeWidth="1.5" /><circle cx={point.x - 62} cy={point.y + 18} r="4" fill={color} /><text x={point.x - 52} y={point.y + 21} fontSize="10" fontWeight="700" fill="#0F172A">{node.node_type.toUpperCase()}</text><text x={point.x - 64} y={point.y + 39} fontSize="10" fill="#334155">{node.label.length > 23 ? `${node.label.slice(0, 22)}…` : node.label}</text></g>
          })}
        </svg>
      </div>
      <div className="flex flex-wrap gap-3 border-t border-slate-100 px-4 py-3 text-[10px] text-slate-500"><span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-600" />Person track</span><span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-600" />Object track</span><span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-slate-500" />Track role unknown</span><span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-violet-600" />Stored event</span></div>
    </section>
  )
}

function EvidenceReview(props: {
  frames: ReviewFrame[]
  index: number
  onIndex: (index: number) => void
  selected: ReviewFrame | null
  selectedTimeline: InvestigationTimelineItem | null
  source: InvestigationSource | null
  videoUrl: string | null
  videoRef: React.RefObject<HTMLVideoElement | null>
  videoLoading: boolean
  videoProgress: number
  videoPreparationMessage: string
  videoPlaybackError: string | null
  onVideoError: (message: string) => void
  onLoadVideo: () => void
  onBrowseAll: () => void
}) {
  const frame = props.selected
  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-xs">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
        <div><h2 className="font-display text-lg font-bold text-slate-900">Evidence review</h2><p className="text-xs text-slate-500">Original evidence files are read-only. Missing artifacts are shown as unavailable.</p></div>
        {frame && <div className="flex items-center gap-2"><button type="button" disabled={props.index <= 0} onClick={() => props.onIndex(props.index - 1)} aria-label="Previous evidence frame" className="rounded-lg border border-slate-200 p-2 text-slate-600 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button><span className="font-mono text-xs text-slate-600">{props.index + 1} / {props.frames.length}</span><button type="button" disabled={props.index >= props.frames.length - 1} onClick={() => props.onIndex(props.index + 1)} aria-label="Next evidence frame" className="rounded-lg border border-slate-200 p-2 text-slate-600 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button></div>}
      </div>
      {!frame ? (
        props.selectedTimeline ? (
          <div className="space-y-4 p-4 sm:p-5">
            <div className="rounded-xl bg-[#F8FAFC] p-3">
              <h3 className="text-sm font-bold text-slate-900">{props.selectedTimeline.title}</h3>
              <p className="mt-1 flex items-center gap-1 font-mono text-xs text-blue-700"><Clock3 className="h-3.5 w-3.5" />{formatTime(props.selectedTimeline.timestamp_seconds)} · {props.selectedTimeline.source_label}</p>
              <p className="mt-2 text-xs leading-relaxed text-slate-600">{props.selectedTimeline.explanation}</p>
              <p className="mt-2 text-[11px] text-slate-500">No saved evidence frame is available for this record. The selected timestamp is source-local.</p>
            </div>
            {props.selectedTimeline.source_type === 'analysis' && props.source?.video_id ? (
              <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-3">
                {props.videoLoading && <div className="mb-3 space-y-1.5"><p className="text-[11px] text-blue-800">{props.videoPreparationMessage || 'Preparing video playback...'}</p><progress value={props.videoProgress} max={100} className="h-1.5 w-full accent-blue-600" /></div>}
                {props.videoPlaybackError && <p role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-2 text-[11px] text-rose-800">{props.videoPlaybackError} Annotated frames remain available below.</p>}
                {!props.videoUrl && <button type="button" disabled={props.videoLoading} onClick={props.onLoadVideo} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60">{props.videoLoading ? 'Loading video…' : 'Load original video and seek to event'}</button>}
                {props.videoUrl && <video ref={props.videoRef} src={props.videoUrl} controls preload="metadata" onLoadedMetadata={(event) => { if (props.selectedTimeline) event.currentTarget.currentTime = props.selectedTimeline.timestamp_seconds }} onError={(event) => { const code = event.currentTarget.error?.code; props.onVideoError(code === 4 ? 'The browser does not support this prepared video source.' : `Video playback failed${code ? ` (media error ${code})` : ''}.`) }} className="max-h-[420px] w-full rounded-lg bg-black" />}
              </div>
            ) : <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">No continuous video is archived for this live session. Timeline navigation is limited to stored event snapshots and track samples.</p>}
            <button type="button" onClick={props.onBrowseAll} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">Browse all saved investigation evidence</button>
          </div>
        ) : (
          <div className="px-5 py-14 text-center"><FileImage className="mx-auto h-8 w-8 text-blue-500" /><h3 className="mt-2 font-semibold text-slate-800">Choose an event from the timeline</h3><p className="mx-auto mt-1 max-w-md text-xs text-slate-500">Available saved frames, track evidence, timestamps, confidence, and event explanations appear here.</p><button type="button" onClick={props.onBrowseAll} className="mt-4 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">Browse all saved evidence</button></div>
        )
      ) : (
        <div className="space-y-4 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#F8FAFC] p-3">
            <div><h3 className="text-sm font-bold text-slate-900">{frame.eventTitle}</h3><p className="mt-1 flex items-center gap-1 font-mono text-xs text-blue-700"><Clock3 className="h-3.5 w-3.5" />{formatTime(frame.timestamp)} · Frame {frame.frameNumber}</p></div>
            {props.selectedTimeline?.event_id && <span className="font-mono text-[10px] text-slate-500">Event ID · {props.selectedTimeline.event_id}</span>}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="overflow-hidden rounded-xl border border-slate-200"><div className="border-b border-slate-100 bg-white px-3 py-2 text-xs font-semibold text-slate-700">Original frame</div><EvidenceAsset path={frame.original} alt="Original investigation evidence frame" /></div>
            <div className="overflow-hidden rounded-xl border border-slate-200"><div className="border-b border-slate-100 bg-white px-3 py-2 text-xs font-semibold text-slate-700">Annotated frame / event snapshot</div><EvidenceAsset path={frame.annotated} alt="Annotated investigation evidence frame" /></div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Explanation</p><p className="mt-1 text-xs leading-relaxed text-slate-700">{frame.explanation || 'No stored explanation is available.'}</p></div>
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Related track IDs</p><div className="mt-1 flex flex-wrap gap-1.5">{frame.trackLabels.length ? frame.trackLabels.map((label, index) => <span key={`${label}:${index}`} className="rounded-md bg-violet-50 px-2 py-1 font-mono text-[10px] font-semibold text-violet-700">{label}</span>) : <span className="text-xs text-slate-500">None recorded</span>}</div>{frame.confidence !== null && <p className="mt-2 font-mono text-[10px] text-slate-500">Stored confidence · {Math.round(frame.confidence * 100)}%</p>}</div>
          </div>
          {props.selectedTimeline?.source_type === 'analysis' && props.source?.video_id ? (
            <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-semibold text-blue-900">Uploaded video playback</p><p className="text-[10px] text-blue-700">Fetched only on request and positioned at the stored source timestamp. The original upload remains unchanged.</p></div>{!props.videoUrl && <button type="button" disabled={props.videoLoading} onClick={props.onLoadVideo} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60">{props.videoLoading ? 'Preparing video…' : 'Load and seek to event'}</button>}</div>
              {props.videoLoading && <div className="mt-3 space-y-1.5"><p className="text-[11px] text-blue-800">{props.videoPreparationMessage || 'Preparing video playback...'}</p><progress value={props.videoProgress} max={100} className="h-1.5 w-full accent-blue-600" /></div>}
              {props.videoPlaybackError && <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-2 text-[11px] text-rose-800">{props.videoPlaybackError} The saved evidence frames above remain available.</p>}
              {props.videoUrl && <video ref={props.videoRef} src={props.videoUrl} controls preload="metadata" onLoadedMetadata={(event) => { if (props.selectedTimeline) event.currentTarget.currentTime = props.selectedTimeline.timestamp_seconds }} onError={(event) => { const code = event.currentTarget.error?.code; props.onVideoError(code === 4 ? 'The browser does not support this prepared video source.' : `Video playback failed${code ? ` (media error ${code})` : ''}.`) }} className="mt-3 max-h-[420px] w-full rounded-lg bg-black" />}
            </div>
          ) : props.selectedTimeline?.source_type === 'live_session' ? <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">This live session has no archived continuous video. Only saved event snapshots and retained track samples are available.</p> : null}
        </div>
      )}
    </section>
  )
}

function NotesPanel(props: {
  detail: InvestigationDetail
  content: string
  onContent: (value: string) => void
  sourceId: string
  onSourceId: (value: string) => void
  eventLinkId: string
  onEventLinkId: (value: string) => void
  timestamp: string
  onTimestamp: (value: string) => void
  editingNoteId: string | null
  editingContent: string
  onEditingContent: (value: string) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onEdit: (note: InvestigationNote) => void
  onSaveEdit: (note: InvestigationNote) => void
  onCancelEdit: () => void
  onDelete: (note: InvestigationNote) => void
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(280px,0.7fr)_minmax(0,1.3fr)]">
      <form onSubmit={props.onSubmit} className="h-fit rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <h2 className="font-display text-lg font-bold text-slate-900">Private investigator note</h2>
        <p className="mt-1 text-xs text-slate-500">User-written and distinct from system-generated event explanations.</p>
        <textarea required maxLength={20000} value={props.content} onChange={(event) => props.onContent(event.target.value)} rows={6} placeholder="Record your observation or follow-up…" className="mt-3 w-full resize-y rounded-xl border border-slate-200 bg-[#F8FAFC] p-3 text-sm outline-none focus:border-blue-400" />
        <label className="mt-3 block text-[11px] font-semibold text-slate-600">Source (optional)</label>
        <select value={props.sourceId} onChange={(event) => { props.onSourceId(event.target.value); props.onEventLinkId('') }} className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"><option value="">No source link</option>{props.detail.sources.map((source) => <option key={source.id} value={source.id}>{source.source_label}</option>)}</select>
        <label className="mt-3 block text-[11px] font-semibold text-slate-600">Linked event (optional)</label>
        <select value={props.eventLinkId} onChange={(event) => { props.onEventLinkId(event.target.value); const linked = props.detail.linked_events.find((item) => item.id === event.target.value); if (linked) props.onSourceId(linked.source_id) }} className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"><option value="">No event link</option>{props.detail.linked_events.map((event) => <option key={event.id} value={event.id}>{event.title} · {event.track_labels.join(', ') || event.event_type}</option>)}</select>
        <label className="mt-3 block text-[11px] font-semibold text-slate-600">Source timestamp in seconds (optional)</label>
        <input type="number" min="0" step="0.01" value={props.timestamp} onChange={(event) => props.onTimestamp(event.target.value)} placeholder="e.g. 12.50" className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs" />
        <button type="submit" className="mt-4 w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">Add private note</button>
      </form>
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex items-center justify-between"><div><h2 className="font-display text-lg font-bold text-slate-900">Investigation notes</h2><p className="text-xs text-slate-500">Only the investigation owner can read or edit these notes.</p></div><span className="font-mono text-xs text-slate-400">{props.detail.notes.length} notes</span></div>
        <div className="mt-4 space-y-3">
          {props.detail.notes.length === 0 ? <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-500">No investigator-written notes yet.</div> : props.detail.notes.map((note) => (
            <article key={note.id} className="rounded-xl border border-slate-200 bg-[#F8FAFC] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><span className="rounded-full bg-blue-100 px-2 py-1 text-[9px] font-bold uppercase text-blue-700">Investigator note · User-written</span>{note.timestamp_seconds !== null && <span className="font-mono text-[10px] text-violet-700">{formatTime(note.timestamp_seconds)}</span>}</div><span className="text-[10px] text-slate-400">Edited {formatDate(note.updated_at)}</span></div>
              {props.editingNoteId === note.id ? <textarea value={props.editingContent} onChange={(event) => props.onEditingContent(event.target.value)} rows={4} className="mt-3 w-full rounded-lg border border-slate-200 bg-white p-3 text-sm" /> : <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{note.content}</p>}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-2"><div className="text-[10px] text-slate-500">{props.detail.sources.find((source) => source.id === note.source_id)?.source_label ?? 'No source linked'}{note.investigation_event_id ? ` · Event link ${note.investigation_event_id.slice(0, 8)}` : ''}</div><div className="flex gap-2">{props.editingNoteId === note.id ? <><button type="button" onClick={() => props.onSaveEdit(note)} className="text-[10px] font-semibold text-blue-700">Save</button><button type="button" onClick={props.onCancelEdit} className="text-[10px] font-semibold text-slate-500">Cancel</button></> : <button type="button" onClick={() => props.onEdit(note)} className="text-[10px] font-semibold text-blue-700">Edit</button>}<button type="button" onClick={() => props.onDelete(note)} className="text-[10px] font-semibold text-rose-600">Delete</button></div></div>
            </article>
          ))}
        </div>
        <p className="mt-3 flex items-start gap-1.5 text-[10px] text-slate-400"><CalendarDays className="mt-0.5 h-3 w-3 shrink-0" />Revision history is not available in the existing application; creation and last-edit times are stored.</p>
      </div>
    </section>
  )
}
