import {
  AlertCircle,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Loader2,
  MapPinned,
  Pencil,
  Plus,
  Radio,
  Save,
  Shield,
  Trash2,
  Video,
  X,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  discoverAnalysisEvents,
  fetchExtractedFrameBlobUrl,
  getAnalysisResults,
  listUserAnalyses,
  type AnalysisListItem,
  type AnalysisResultsResponse,
} from '../services/analysisService'
import { getAuthErrorMessage } from '../services/authService'
import {
  fetchLiveLatestFrameBlobUrl,
  getAnalysisZoneActivity,
  getAnalysisZoneEvents,
  getLiveZoneActivity,
  getLiveZoneEvents,
  listZones,
  createZone,
  deleteZone,
  updateZone,
  DEFAULT_ZONE_SETTINGS,
  type ZoneActivitySummary,
  type ZoneEventRecord,
  type ZoneRecord,
  type ZoneSettings,
  type ZoneType,
} from '../services/zoneService'
import {
  fetchLiveEventSnapshotBlobUrl,
  listLiveMonitoringSessions,
  type LiveSessionStatusResponse,
} from '../services/liveService'

type SourceKind = 'video' | 'live'
type Point = [number, number]
type ZoneDraft = {
  name: string
  zone_type: ZoneType
  color: string
  polygon: Point[]
  settings: ZoneSettings
}

const ZONE_TYPES: { value: ZoneType; label: string; tone: string }[] = [
  { value: 'restricted', label: 'Restricted', tone: '#E11D48' },
  { value: 'safe', label: 'Safe', tone: '#059669' },
  { value: 'monitoring', label: 'Monitoring', tone: '#2563EB' },
  { value: 'entry', label: 'Entry', tone: '#7C3AED' },
  { value: 'exit', label: 'Exit', tone: '#D97706' },
]

function frameTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function EventEvidencePreview({
  analysisId,
  sessionId,
  event,
  frameName,
}: {
  analysisId?: string
  sessionId?: string
  event: ZoneEventRecord
  frameName?: string
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null
    const fetchPreview = analysisId && frameName
      ? fetchExtractedFrameBlobUrl(analysisId, frameName)
      : sessionId
        ? fetchLiveEventSnapshotBlobUrl(sessionId, event.id)
        : Promise.resolve(null)
    void fetchPreview.then((url) => {
      if (!active) {
        if (url) URL.revokeObjectURL(url)
        return
      }
      objectUrl = url
      setImageUrl(url)
    }).catch(() => {
      if (active) setImageUrl(null)
    })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [analysisId, sessionId, event.id, frameName])

  return imageUrl ? (
    <img src={imageUrl} alt={`Evidence for ${event.event_type}`} className="h-16 w-24 rounded-lg border border-slate-200 object-cover" />
  ) : (
    <div className="flex h-16 w-24 items-center justify-center rounded-lg border border-slate-200 bg-white text-[#64748B]">
      <CircleHelp className="h-4 w-4" />
    </div>
  )
}

export function SmartZoneManagementPage() {
  const [searchParams] = useSearchParams()
  const [sourceKind, setSourceKind] = useState<SourceKind>(
    searchParams.get('liveSessionId') ? 'live' : 'video',
  )
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [liveSessions, setLiveSessions] = useState<LiveSessionStatusResponse[]>([])
  const [analysisId, setAnalysisId] = useState(searchParams.get('analysisId') ?? '')
  const [liveSessionId, setLiveSessionId] = useState(searchParams.get('liveSessionId') ?? '')
  const [analysisResults, setAnalysisResults] = useState<AnalysisResultsResponse | null>(null)
  const [frameIndex, setFrameIndex] = useState(0)
  const [zones, setZones] = useState<ZoneRecord[]>([])
  const [zoneEvents, setZoneEvents] = useState<ZoneEventRecord[]>([])
  const [activity, setActivity] = useState<ZoneActivitySummary | null>(null)
  const [frameImageUrl, setFrameImageUrl] = useState<string | null>(null)
  const [frameError, setFrameError] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [loadingSource, setLoadingSource] = useState(false)
  const [saving, setSaving] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [editingZoneId, setEditingZoneId] = useState<string | null>(null)
  const [drawing, setDrawing] = useState(false)
  const [polygonDraft, setPolygonDraft] = useState<Point[]>([])
  const [zoneDraft, setZoneDraft] = useState<ZoneDraft>({
    name: '',
    zone_type: 'monitoring',
    color: '#2563EB',
    polygon: [],
    settings: { ...DEFAULT_ZONE_SETTINGS },
  })
  const editorRef = useRef<SVGSVGElement | null>(null)
  const dragRef = useRef<{ index: number | null; x: number; y: number; polygon: Point[] } | null>(null)

  const selectedAnalysis = useMemo(
    () => analyses.find((item) => item.analysis_id === analysisId) ?? null,
    [analyses, analysisId],
  )
  const selectedLiveSession = useMemo(
    () => liveSessions.find((item) => item.session_id === liveSessionId) ?? null,
    [liveSessions, liveSessionId],
  )
  const selectedFrame = analysisResults?.frames[frameIndex] ?? null
  const polygonForDisplay = drawing ? polygonDraft : zoneDraft.polygon
  const selectedSourceId = sourceKind === 'video' ? selectedAnalysis?.video_id : liveSessionId

  const loadSourceData = useCallback(async () => {
    if (!selectedSourceId) return null
    const [nextZones, nextEvents, nextActivity] = await Promise.all([
      listZones(
        sourceKind === 'video'
          ? { videoId: selectedSourceId }
          : { liveSessionId: selectedSourceId },
      ),
      sourceKind === 'video'
        ? getAnalysisZoneEvents(analysisId)
        : getLiveZoneEvents(liveSessionId),
      sourceKind === 'video'
        ? getAnalysisZoneActivity(analysisId)
        : getLiveZoneActivity(liveSessionId),
    ])
    return { nextZones, nextEvents, nextActivity }
  }, [analysisId, liveSessionId, selectedSourceId, sourceKind])

  const refreshSourceData = useCallback(async () => {
    try {
      const data = await loadSourceData()
      if (!data) return
      setZones(data.nextZones)
      setZoneEvents(data.nextEvents)
      setActivity(data.nextActivity)
    } catch (error) {
      setPageError(getAuthErrorMessage(error, 'Could not load zone configuration and activity.'))
    }
  }, [loadSourceData])

  useEffect(() => {
    let active = true
    Promise.all([listUserAnalyses(), listLiveMonitoringSessions()])
      .then(([analysisRows, sessionRows]) => {
        if (!active) return
        setAnalyses(analysisRows)
        setLiveSessions(sessionRows)
        if (!analysisId) {
          const firstCompleted = analysisRows.find((row) => row.status === 'completed')?.analysis_id ?? ''
          if (firstCompleted) setLoadingSource(true)
          setAnalysisId(firstCompleted)
        }
        if (!liveSessionId) {
          setLiveSessionId(sessionRows[0]?.session_id ?? '')
        }
      })
      .catch((error) => {
        if (active) setPageError(getAuthErrorMessage(error, 'Could not load available video and live sessions.'))
      })
    return () => {
      active = false
    }
  }, [analysisId, liveSessionId])

  useEffect(() => {
    let active = true
    let livePreviewUrl: string | null = null
    if (sourceKind === 'video' && analysisId) {
      getAnalysisResults(analysisId)
        .then((response) => {
          if (active) setAnalysisResults(response)
        })
        .catch((error) => {
          if (active) setPageError(getAuthErrorMessage(error, 'Could not load the selected analysis frames.'))
        })
        .finally(() => {
          if (active) setLoadingSource(false)
        })
    } else if (sourceKind === 'live' && liveSessionId) {
      fetchLiveLatestFrameBlobUrl(liveSessionId)
        .then((url) => {
          if (active) {
            livePreviewUrl = url
            setFrameImageUrl(url)
          }
          else URL.revokeObjectURL(url)
        })
        .catch((error) => {
          if (active) {
            setFrameImageUrl(null)
            setFrameError(getAuthErrorMessage(error, 'Start live monitoring to capture an editable reference frame.'))
          }
        })
        .finally(() => {
          if (active) setLoadingSource(false)
        })
    }
    return () => {
      active = false
      if (livePreviewUrl) URL.revokeObjectURL(livePreviewUrl)
    }
  }, [analysisId, liveSessionId, sourceKind])

  useEffect(() => {
    let active = true
    let createdUrl: string | null = null
    if (sourceKind === 'video' && selectedFrame && analysisId) {
      fetchExtractedFrameBlobUrl(analysisId, selectedFrame.filename)
        .then((url) => {
          if (active) {
            createdUrl = url
            setFrameImageUrl(url)
          } else URL.revokeObjectURL(url)
        })
        .catch((error) => {
          if (active) setFrameError(getAuthErrorMessage(error, 'Could not load the selected frame.'))
        })
    }
    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [analysisId, selectedFrame, sourceKind])

  useEffect(() => {
    let active = true
    loadSourceData()
      .then((data) => {
        if (!active || !data) return
        setZones(data.nextZones)
        setZoneEvents(data.nextEvents)
        setActivity(data.nextActivity)
      })
      .catch((error) => {
        if (active) setPageError(getAuthErrorMessage(error, 'Could not load zone configuration and activity.'))
      })
    return () => {
      active = false
    }
  }, [loadSourceData])

  const readEditorPoint = (clientX: number, clientY: number): Point => {
    const rect = editorRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0 || rect.height === 0) return [0, 0]
    return [
      Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)),
      Math.min(1, Math.max(0, (clientY - rect.top) / rect.height)),
    ]
  }

  const resetSourceView = () => {
    setPageError(null)
    setFrameError(null)
    setFrameImageUrl(null)
    setAnalysisResults(null)
    setFrameIndex(0)
    setZones([])
    setZoneEvents([])
    setActivity(null)
    setEditingZoneId(null)
    setDrawing(false)
    setPolygonDraft([])
    setZoneDraft((current) => ({ ...current, polygon: [] }))
  }

  const startNewZone = () => {
    setEditingZoneId(null)
    setZoneDraft({
      name: '',
      zone_type: 'monitoring',
      color: '#2563EB',
      polygon: [],
      settings: { ...DEFAULT_ZONE_SETTINGS },
    })
    setPolygonDraft([])
    setDrawing(true)
    setNotice('Click the frame to place polygon points, then save at least three points.')
  }

  const editZone = (zone: ZoneRecord) => {
    setEditingZoneId(zone.id)
    setZoneDraft({
      name: zone.name,
      zone_type: zone.zone_type,
      color: zone.color,
      polygon: zone.polygon.map(([x, y]) => [x, y]),
      settings: { ...DEFAULT_ZONE_SETTINGS, ...zone.settings },
    })
    setPolygonDraft([])
    setDrawing(false)
    setNotice(`Editing ${zone.name}. Drag a vertex to reshape or drag the polygon to move it.`)
  }

  const handleEditorPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    if (!drawing) return
    const [x, y] = readEditorPoint(event.clientX, event.clientY)
    setPolygonDraft((points) => [...points, [x, y]])
  }

  const handleEditorPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    if (!drag || event.buttons !== 1) return
    const [x, y] = readEditorPoint(event.clientX, event.clientY)
    if (drag.index !== null) {
      setZoneDraft((current) => ({
        ...current,
        polygon: current.polygon.map((point, index) =>
          index === drag.index ? [x, y] : point,
        ),
      }))
    } else {
      const dx = x - drag.x
      const dy = y - drag.y
      setZoneDraft((current) => ({
        ...current,
        polygon: drag.polygon.map(([px, py]) => [
          Math.min(1, Math.max(0, px + dx)),
          Math.min(1, Math.max(0, py + dy)),
        ]),
      }))
      dragRef.current = { ...drag, x, y }
    }
  }

  const startVertexDrag = (event: PointerEvent<SVGCircleElement>, index: number) => {
    event.stopPropagation()
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      index,
      x: 0,
      y: 0,
      polygon: zoneDraft.polygon.map(([x, y]) => [x, y]),
    }
  }

  const startPolygonDrag = (event: PointerEvent<SVGPolygonElement>) => {
    if (drawing || !editingZoneId) return
    event.stopPropagation()
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    const [x, y] = readEditorPoint(event.clientX, event.clientY)
    dragRef.current = {
      index: null,
      x,
      y,
      polygon: zoneDraft.polygon.map(([px, py]) => [px, py]),
    }
  }

  const handleSaveZone = async () => {
    if (!selectedSourceId) {
      setPageError('Select a video analysis or live session before saving zones.')
      return
    }
    const polygon = drawing ? polygonDraft : zoneDraft.polygon
    if (polygon.length < 3) {
      setPageError('A zone needs at least three polygon points.')
      return
    }
    if (!zoneDraft.name.trim()) {
      setPageError('Enter a name for this zone.')
      return
    }
    setSaving(true)
    setPageError(null)
    try {
      const payload = {
        ...zoneDraft,
        polygon,
        name: zoneDraft.name.trim(),
        ...(sourceKind === 'video' ? { video_id: selectedSourceId } : { live_session_id: selectedSourceId }),
      }
      const saved = editingZoneId
        ? await updateZone(editingZoneId, {
            name: payload.name,
            zone_type: payload.zone_type,
            color: payload.color,
            polygon: payload.polygon,
            settings: payload.settings,
          })
        : await createZone(payload)
      setEditingZoneId(saved.id)
      setZoneDraft({
        name: saved.name,
        zone_type: saved.zone_type,
        color: saved.color,
        polygon: saved.polygon.map(([x, y]) => [x, y]),
        settings: saved.settings,
      })
      setDrawing(false)
      setPolygonDraft([])
      setNotice(`Saved ${saved.name}.`)
      await refreshSourceData()
    } catch (error) {
      setPageError(getAuthErrorMessage(error, 'Could not save this zone.'))
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteZone = async (zone: ZoneRecord) => {
    if (!window.confirm(`Delete the zone "${zone.name}"?`)) return
    try {
      await deleteZone(zone.id)
      if (editingZoneId === zone.id) {
        setEditingZoneId(null)
        setZoneDraft((current) => ({ ...current, polygon: [] }))
      }
      setNotice(`Deleted ${zone.name}.`)
      await refreshSourceData()
    } catch (error) {
      setPageError(getAuthErrorMessage(error, 'Could not delete this zone.'))
    }
  }

  const analyzeZones = async () => {
    if (!analysisId) return
    setAnalyzing(true)
    setPageError(null)
    try {
      await discoverAnalysisEvents(analysisId)
      await refreshSourceData()
      setNotice('Zone events refreshed from saved tracked detections.')
    } catch (error) {
      setPageError(getAuthErrorMessage(error, 'Could not analyze saved zone activity.'))
    } finally {
      setAnalyzing(false)
    }
  }

  const updateSetting = <K extends keyof ZoneSettings>(key: K, value: ZoneSettings[K]) => {
    setZoneDraft((current) => ({
      ...current,
      settings: { ...current.settings, [key]: value },
    }))
  }

  const eventFrameName = (event: ZoneEventRecord) =>
    analysisResults?.frames.find((frame) => frame.frame_index === event.evidence_frame_ids[0])?.filename

  const typeInfo = ZONE_TYPES.find((item) => item.value === zoneDraft.zone_type)

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-[#2563EB]">
              <MapPinned className="h-3.5 w-3.5" /> Spatial rule editor
            </span>
            <h1 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827]">
              Smart Zone Intelligence
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-[#64748B]">
              Define normalized polygon areas and analyze confirmed tracked entry, exit, transitions, group presence, and time inside. Zone events describe observed movement, not intent.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/analysis/new" className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-semibold text-[#111827] hover:bg-slate-100">
              <Video className="h-4 w-4" /> New video analysis
            </Link>
            <Link to="/dashboard/live" className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-semibold text-[#111827] hover:bg-slate-100">
              <Radio className="h-4 w-4" /> Live monitoring
            </Link>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-[180px_1fr]">
          <div>
            <label htmlFor="zone-source-kind" className="text-xs font-semibold text-[#111827]">Source</label>
            <select id="zone-source-kind" value={sourceKind} onChange={(event) => {
              const nextKind = event.target.value as SourceKind
              resetSourceView()
              setLoadingSource(nextKind === 'video' ? Boolean(analysisId) : Boolean(liveSessionId))
              setSourceKind(nextKind)
            }} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm text-[#111827]">
              <option value="video">Recorded video</option>
              <option value="live">Live session</option>
            </select>
          </div>
          {sourceKind === 'video' ? (
            <div>
              <label htmlFor="zone-analysis" className="text-xs font-semibold text-[#111827]">Completed video analysis</label>
              <select id="zone-analysis" value={analysisId} onChange={(event) => {
                resetSourceView()
                setLoadingSource(Boolean(event.target.value))
                setAnalysisId(event.target.value)
              }} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm text-[#111827]">
                <option value="">Select a completed analysis</option>
                {analyses.filter((item) => item.status === 'completed').map((item) => (
                  <option key={item.analysis_id} value={item.analysis_id}>{item.video_filename} · {item.analysis_id.slice(0, 8)}</option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label htmlFor="zone-live-session" className="text-xs font-semibold text-[#111827]">Live monitoring session</label>
              <select id="zone-live-session" value={liveSessionId} onChange={(event) => {
                resetSourceView()
                setLoadingSource(Boolean(event.target.value))
                setLiveSessionId(event.target.value)
              }} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm text-[#111827]">
                <option value="">Select a live session</option>
                {liveSessions.map((item) => (
                  <option key={item.session_id} value={item.session_id}>{item.status.toUpperCase()} · {item.session_id.slice(0, 8)}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </motion.section>

      {pageError && <div role="alert" className="flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{pageError}<button type="button" className="ml-auto" onClick={() => setPageError(null)} aria-label="Dismiss error"><X className="h-4 w-4" /></button></div>}
      {notice && <div role="status" className="flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800"><Check className="h-4 w-4" />{notice}<button type="button" className="ml-auto" onClick={() => setNotice(null)} aria-label="Dismiss notice"><X className="h-4 w-4" /></button></div>}

      <div className="grid gap-6 xl:grid-cols-12">
        <section className="space-y-4 rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs xl:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 pb-3">
            <div>
              <h2 className="font-display text-base font-bold text-[#111827]">Frame &amp; polygon editor</h2>
              <p className="mt-0.5 text-[11px] text-[#64748B]">Coordinates are normalized (0–1) for any image resolution.</p>
            </div>
            <div className="flex items-center gap-2">
              {sourceKind === 'video' && analysisResults && (
                <label className="flex items-center gap-2 text-xs text-[#64748B]">
                  Frame
                  <select value={frameIndex} onChange={(event) => setFrameIndex(Number(event.target.value))} className="rounded-lg border border-slate-200 bg-[#F5F8FC] px-2 py-1.5 font-mono text-xs text-[#111827]">
                    {analysisResults.frames.map((frame, index) => <option key={frame.frame_index} value={index}>#{frame.frame_index + 1} · {frameTime(frame.timestamp_seconds)}</option>)}
                  </select>
                </label>
              )}
              {sourceKind === 'video' && analysisId && (
                <button type="button" onClick={() => void analyzeZones()} disabled={analyzing} className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-[#2563EB] disabled:opacity-50">
                  {analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Clock3 className="h-3.5 w-3.5" />}
                  Analyze zones
                </button>
              )}
            </div>
          </div>

          <div className="relative min-h-56 overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
            {frameImageUrl ? (
              <img src={frameImageUrl} alt={sourceKind === 'video' ? 'Selected analysis frame' : 'Latest live monitoring frame'} className="block h-auto max-h-[65vh] w-full object-contain" />
            ) : (
              <div className="flex aspect-video items-center justify-center bg-[#F5F8FC] px-6 text-center">
                {loadingSource ? <Loader2 className="h-6 w-6 animate-spin text-[#2563EB]" /> : <p className="max-w-sm text-xs text-[#64748B]">{frameError || 'Choose a completed analysis or an active session with at least one processed frame.'}</p>}
              </div>
            )}
            {frameImageUrl && (
              <svg
                ref={editorRef}
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
                className={`absolute inset-0 h-full w-full ${drawing ? 'cursor-crosshair' : 'cursor-default'}`}
                onPointerDown={handleEditorPointerDown}
                onPointerMove={handleEditorPointerMove}
                onPointerUp={() => { dragRef.current = null }}
                aria-label="Normalized polygon zone drawing canvas"
              >
                {zones.map((zone) => {
                  const points = zone.polygon.map(([x, y]) => `${x},${y}`).join(' ')
                  const isSelected = zone.id === editingZoneId
                  return (
                    <g key={zone.id}>
                      <polygon points={points} fill={zone.color} fillOpacity={isSelected ? 0.22 : 0.12} stroke={zone.color} strokeWidth="0.004" vectorEffect="non-scaling-stroke" onPointerDown={isSelected ? startPolygonDrag : undefined} />
                      <text x={zone.polygon[0]?.[0] ?? 0} y={zone.polygon[0]?.[1] ?? 0} fill={zone.color} fontSize="0.025" fontWeight="bold" stroke="white" strokeWidth="0.004" paintOrder="stroke">{zone.name}</text>
                    </g>
                  )
                })}
                {polygonForDisplay.length >= 2 && (
                  <g>
                    <polygon
                      points={polygonForDisplay.map(([x, y]) => `${x},${y}`).join(' ')}
                      fill={zoneDraft.color}
                      fillOpacity={polygonForDisplay.length >= 3 ? 0.2 : 0.05}
                      stroke={zoneDraft.color}
                      strokeWidth="0.005"
                      vectorEffect="non-scaling-stroke"
                      onPointerDown={startPolygonDrag}
                    />
                    {polygonForDisplay.map(([x, y], index) => (
                      <circle
                        key={`${index}-${x}-${y}`}
                        cx={x}
                        cy={y}
                        r="0.012"
                        fill="white"
                        stroke={zoneDraft.color}
                        strokeWidth="0.004"
                        vectorEffect="non-scaling-stroke"
                        onPointerDown={(event) => !drawing && startVertexDrag(event, index)}
                      />
                    ))}
                  </g>
                )}
              </svg>
            )}
            {frameImageUrl && sourceKind === 'video' && selectedFrame && <span className="absolute left-3 top-3 rounded-lg bg-white/90 px-2 py-1 font-mono text-[10px] font-bold text-[#111827]">VIDEO · {frameTime(selectedFrame.timestamp_seconds)}</span>}
            {frameImageUrl && sourceKind === 'live' && <span className="absolute left-3 top-3 rounded-lg bg-white/90 px-2 py-1 font-mono text-[10px] font-bold text-[#111827]">LIVE · {selectedLiveSession?.status}</span>}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={startNewZone} disabled={!selectedSourceId || !frameImageUrl} className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-4 py-2.5 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"><Plus className="h-4 w-4" />Draw new zone</button>
            {drawing && <><span className="text-xs text-[#64748B]">{polygonDraft.length} points · click to add</span><button type="button" onClick={() => { setZoneDraft((current) => ({ ...current, polygon: polygonDraft })); setDrawing(false) }} disabled={polygonDraft.length < 3} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-[#111827] disabled:opacity-50">Finish polygon</button><button type="button" onClick={() => setPolygonDraft((points) => points.slice(0, -1))} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-[#64748B]">Undo point</button></>}
          </div>
          {!frameImageUrl && frameError && <p className="text-xs text-amber-700">{frameError}</p>}
        </section>

        <section className="space-y-4 rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs xl:col-span-5">
          <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
            <div><h2 className="font-display text-base font-bold text-[#111827]">Zone configuration</h2><p className="mt-0.5 text-[11px] text-[#64748B]">{editingZoneId ? 'Edit, move, or reshape the selected area.' : 'Create multiple independent zones for this source.'}</p></div>
            {editingZoneId && <button type="button" onClick={startNewZone} className="rounded-lg p-2 text-[#64748B] hover:bg-[#F5F8FC]" title="Create another zone"><Plus className="h-4 w-4" /></button>}
          </div>

          {editingZoneId || drawing ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <label className="text-xs font-semibold text-[#111827]">Zone name<input value={zoneDraft.name} onChange={(event) => setZoneDraft((current) => ({ ...current, name: event.target.value }))} maxLength={100} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm font-normal" placeholder="e.g. North entrance" /></label>
                <label className="text-xs font-semibold text-[#111827]">Color<input type="color" value={zoneDraft.color} onChange={(event) => setZoneDraft((current) => ({ ...current, color: event.target.value.toUpperCase() }))} className="mt-1.5 h-10 w-16 cursor-pointer rounded-lg border border-slate-200 bg-white p-1" /></label>
              </div>
              <label className="block text-xs font-semibold text-[#111827]">Zone type
                <select value={zoneDraft.zone_type} onChange={(event) => {
                  const zone_type = event.target.value as ZoneType
                  setZoneDraft((current) => ({ ...current, zone_type, color: ZONE_TYPES.find((item) => item.value === zone_type)?.tone ?? current.color }))
                }} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm font-normal">
                  {ZONE_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-[#111827]">Confirm frames<input type="number" min={1} max={30} value={zoneDraft.settings.confirmation_frames} onChange={(event) => updateSetting('confirmation_frames', Number(event.target.value))} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm font-normal" /></label>
                <label className="text-xs font-semibold text-[#111827]">Event cooldown (s)<input type="number" min={0} max={3600} value={zoneDraft.settings.cooldown_seconds} onChange={(event) => updateSetting('cooldown_seconds', Number(event.target.value))} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm font-normal" /></label>
                <label className="text-xs font-semibold text-[#111827]">Loiter threshold (s)<input type="number" min={0.1} max={86400} step={0.5} value={zoneDraft.settings.loiter_seconds} onChange={(event) => updateSetting('loiter_seconds', Number(event.target.value))} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm font-normal" /></label>
                <label className="text-xs font-semibold text-[#111827]">Restricted group size<input type="number" min={2} max={50} value={zoneDraft.settings.restricted_group_threshold} onChange={(event) => updateSetting('restricted_group_threshold', Number(event.target.value))} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2.5 text-sm font-normal" /></label>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-xl border border-slate-200 bg-[#F5F8FC] p-3">
                <label className="flex items-center gap-2 text-xs text-[#111827]"><input type="checkbox" checked={zoneDraft.settings.alerts_enabled} onChange={(event) => updateSetting('alerts_enabled', event.target.checked)} />Show zone alerts</label>
                <label className="flex items-center gap-2 text-xs text-[#111827]"><input type="checkbox" checked={zoneDraft.settings.voice_alerts_enabled} onChange={(event) => updateSetting('voice_alerts_enabled', event.target.checked)} />Allow voice alerts</label>
              </div>
              <p className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-[11px] leading-relaxed text-blue-800">
                {typeInfo?.label} rules use {zoneDraft.settings.confirmation_frames} consecutive tracked observations. Loitering is only a duration threshold; it does not imply intent.
              </p>
              <div className="flex gap-2">
                <button type="button" onClick={() => void handleSaveZone()} disabled={saving || polygonForDisplay.length < 3} className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#2563EB] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{editingZoneId ? 'Save changes' : 'Save zone'}</button>
                <button type="button" onClick={() => { setEditingZoneId(null); setDrawing(false); setPolygonDraft([]); setZoneDraft((current) => ({ ...current, polygon: [] })) }} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-[#64748B]">Cancel</button>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-[#F5F8FC] px-4 py-6 text-center">
              <MapPinned className="mx-auto h-6 w-6 text-[#2563EB]" />
              <p className="mt-2 text-sm font-semibold text-[#111827]">Select a zone to edit</p>
              <p className="mt-1 text-xs text-[#64748B]">Or draw a new polygon on the selected frame.</p>
            </div>
          )}

          <div className="space-y-2 border-t border-slate-200/80 pt-4">
            <div className="flex items-center justify-between"><h3 className="text-xs font-bold text-[#111827]">Configured zones ({zones.length})</h3><ChevronDown className="h-4 w-4 text-[#64748B]" /></div>
            {zones.length === 0 ? <p className="rounded-xl bg-[#F5F8FC] p-3 text-xs text-[#64748B]">No zones saved for this source yet.</p> : zones.map((zone) => (
              <div key={zone.id} className={`flex items-center gap-2 rounded-xl border p-3 ${editingZoneId === zone.id ? 'border-blue-300 bg-blue-50/60' : 'border-slate-200 bg-[#F5F8FC]'}`}>
                <span className="h-3 w-3 shrink-0 rounded-sm" style={{ backgroundColor: zone.color }} />
                <button type="button" onClick={() => editZone(zone)} className="min-w-0 flex-1 text-left"><span className="block truncate text-xs font-bold text-[#111827]">{zone.name}</span><span className="text-[10px] uppercase tracking-wide text-[#64748B]">{zone.zone_type} · {zone.polygon.length} vertices</span></button>
                <button type="button" onClick={() => editZone(zone)} className="rounded-lg p-1.5 text-[#2563EB] hover:bg-white" aria-label={`Edit ${zone.name}`}><Pencil className="h-3.5 w-3.5" /></button>
                <button type="button" onClick={() => void handleDeleteZone(zone)} className="rounded-lg p-1.5 text-rose-600 hover:bg-white" aria-label={`Delete ${zone.name}`}><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        <section className="space-y-3 rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs lg:col-span-4">
          <div className="flex items-center gap-2 border-b border-slate-200/80 pb-3"><Shield className="h-4 w-4 text-[#7C3AED]" /><h2 className="font-display text-sm font-bold text-[#111827]">Zone activity summary</h2></div>
          <p className="font-mono text-2xl font-extrabold text-[#2563EB]">{activity?.total_events ?? 0}<span className="ml-2 text-xs font-semibold text-[#64748B]">confirmed events</span></p>
          {!activity || activity.zones.length === 0 ? <p className="text-xs text-[#64748B]">No saved zone activity for this source.</p> : activity.zones.map((item) => (
            <div key={item.zone_id} className="flex items-center justify-between rounded-xl bg-[#F5F8FC] px-3 py-2.5 text-xs"><span className="font-semibold text-[#111827]">{item.zone_name}</span><span className="font-mono text-[#64748B]">{item.event_count} events · {item.people_tracks.length} tracks</span></div>
          ))}
          {sourceKind === 'video' && analysisId && <p className="text-[11px] leading-relaxed text-[#64748B]">Run <strong>Analyze zones</strong> after saving changes to rebuild events from the video’s actual tracked detections.</p>}
          {sourceKind === 'live' && liveSessionId && <p className="text-[11px] leading-relaxed text-[#64748B]">Live zones are evaluated as new tracked frames arrive. Use the same session in Live Monitoring to see polygons over the camera preview.</p>}
        </section>

        <section className="space-y-3 rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs lg:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 pb-3"><div className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-[#2563EB]" /><h2 className="font-display text-sm font-bold text-[#111827]">Zone activity timeline</h2></div><span className="font-mono text-[10px] text-[#64748B]">{zoneEvents.length} event(s)</span></div>
          {zoneEvents.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-[#F5F8FC] px-5 py-8 text-center text-xs text-[#64748B]">Confirmed entry, exit, group, and loitering events will appear here.</div> : (
            <div className="max-h-[34rem] space-y-2 overflow-auto pr-1">
              {zoneEvents.map((event) => (
                <article key={event.id} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-[#F5F8FC] p-3 sm:flex-row sm:items-center">
                  <EventEvidencePreview analysisId={sourceKind === 'video' ? analysisId : undefined} sessionId={sourceKind === 'live' ? liveSessionId : undefined} event={event} frameName={eventFrameName(event)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase ${event.severity === 'high' ? 'border-rose-200 bg-rose-50 text-rose-700' : event.severity === 'medium' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-blue-100 bg-blue-50 text-blue-700'}`}>{event.severity}</span><span className="font-mono text-[10px] font-semibold text-[#2563EB]">{frameTime(event.start_timestamp)}{event.duration_seconds > 0 ? ` · ${event.duration_seconds.toFixed(1)}s` : ''}</span><span className="text-[10px] text-[#64748B]">{event.zone_name}</span></div>
                    <h3 className="mt-1 text-xs font-bold text-[#111827]">{event.event_type.replaceAll('_', ' ')}</h3>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-[#64748B]">{event.description}</p>
                    <p className="mt-1 font-mono text-[10px] text-[#64748B]">Track(s): {event.involved_track_ids.map((id) => `T${String(id).padStart(3, '0')}`).join(', ') || 'none'} · {Math.round(event.confidence * 100)}% confidence</p>
                  </div>
                  {event.evidence_reference && <span className="shrink-0 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-[#64748B]">Evidence #{event.evidence_frame_ids[0] ?? '—'}</span>}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
