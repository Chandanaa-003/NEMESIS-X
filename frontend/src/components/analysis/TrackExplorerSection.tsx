import {
  Activity,
  AlertCircle,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Clock,
  Compass,
  Crosshair,
  Film,
  GitBranch,
  ImageOff,
  Loader2,
  MapPin,
  Play,
  ShieldAlert,
  X,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ObjectDetectionOverlay,
} from './ObjectDetectionOverlay'
import {
  DEFAULT_DETECTION_OVERLAY_SETTINGS,
  type DetectionOverlaySettings,
} from './detectionOverlaySettings'
import {
  fetchExtractedFrameBlobUrl,
  getAnalysisTrackDetail,
  getAnalysisTrackFrames,
  getAnalysisTracks,
  type TrackDetailResponse,
  type TrackObservationFrameInfo,
  type TrackSummaryInfo,
} from '../../services/analysisService'
import { getAuthErrorMessage } from '../../services/authService'
import { fetchVideoBlobUrl } from '../../services/videoService'

function formatHms(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatTrackCode(track: Pick<TrackSummaryInfo, 'track_id' | 'track_code'>): string {
  return track.track_code || `T${String(track.track_id).padStart(3, '0')}`
}

function formatClassLabel(name: string): string {
  if (!name) return 'Object'
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function TrackAnnotatedFrameCard({
  analysisId,
  trackCode,
  observation,
  isActive,
  overlaySettings,
  onSelectObservation,
}: {
  analysisId: string
  trackCode: string
  observation: TrackObservationFrameInfo
  isActive: boolean
  overlaySettings: DetectionOverlaySettings
  onSelectObservation: (obs: TrackObservationFrameInfo) => void
}) {
  const [blobState, setBlobState] = useState<{ key: string; url: string | null; failed: boolean }>({
    key: '',
    url: null,
    failed: false,
  })
  const requestKey = `${analysisId}:${observation.filename}:${observation.frame_available}`
  const blobUrl = blobState.key === requestKey ? blobState.url : null
  const loadFailed = !observation.frame_available || (blobState.key === requestKey && blobState.failed)

  useEffect(() => {
    if (!observation.frame_available) {
      return
    }

    let active = true
    let createdUrl: string | null = null

    fetchExtractedFrameBlobUrl(analysisId, observation.filename)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setBlobState({ key: requestKey, url, failed: false })
      })
      .catch(() => {
        if (active) setBlobState({ key: requestKey, url: null, failed: true })
      })

    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [analysisId, observation.filename, observation.frame_available, requestKey])

  const fw = observation.frame_width
  const fh = observation.frame_height
  const canDrawBox = typeof fw === 'number' && fw > 0 && typeof fh === 'number' && fh > 0
  const sel = observation.selected_detection
  return (
    <article
      className={`overflow-hidden rounded-2xl border transition-all ${
        isActive
          ? 'border-[#2563EB] bg-[#EFF6FF]/60 ring-2 ring-[#2563EB]/25 shadow-sm'
          : 'border-slate-200/90 bg-[#F5F8FC] hover:border-[#2563EB]/40 hover:shadow-sm'
      }`}
    >
      <button
        type="button"
        onClick={() => onSelectObservation(observation)}
        className="relative block aspect-video w-full cursor-pointer overflow-hidden bg-slate-900/5 text-left"
        title={`Seek video to ${observation.timestamp_seconds.toFixed(2)}s`}
      >
        {!observation.frame_available || loadFailed ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1 bg-slate-100 px-3 text-center text-[#64748B]">
            <ImageOff className="h-5 w-5" />
            <span className="text-[11px] font-medium">Annotated frame missing on disk</span>
          </div>
        ) : !blobUrl ? (
          <div className="h-full w-full animate-pulse bg-slate-200/70" />
        ) : (
          <>
            <img
              src={blobUrl}
              alt={`${trackCode} frame #${observation.frame_index + 1} at ${formatHms(observation.timestamp_seconds)}`}
              loading="lazy"
              className="h-full w-full object-contain bg-slate-950/90"
            />
            {canDrawBox && (
              <ObjectDetectionOverlay
                detections={[sel, ...observation.other_detections]}
                width={fw ?? 0}
                height={fh ?? 0}
                settings={overlaySettings}
              />
            )}
          </>
        )}

      </button>

      <div className="space-y-1.5 bg-white px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] font-semibold text-[#111827]">
            Frame #{observation.frame_index + 1}
          </span>
          <button
            type="button"
            onClick={() => onSelectObservation(observation)}
            className="inline-flex cursor-pointer items-center gap-1 rounded-md bg-[#EFF6FF] px-2 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB] transition-colors hover:bg-[#2563EB] hover:text-white"
            title="Jump video to this timestamp"
          >
            <Play className="h-2.5 w-2.5" />
            <span>
              {formatHms(observation.timestamp_seconds)} ({observation.timestamp_seconds.toFixed(2)}s)
            </span>
          </button>
        </div>

        <div className="flex items-center justify-between gap-2 font-mono text-[10px] text-[#64748B]">
          <span>
            Center: ({Math.round(observation.center_x)}, {Math.round(observation.center_y)})
          </span>
          <span>
            Δ({observation.position_delta_x >= 0 ? '+' : ''}
            {Math.round(observation.position_delta_x)},{' '}
            {observation.position_delta_y >= 0 ? '+' : ''}
            {Math.round(observation.position_delta_y)})
          </span>
        </div>
      </div>
    </article>
  )
}

export interface TrackExplorerSectionProps {
  analysisId: string
  videoId?: string
  overlaySettings?: DetectionOverlaySettings
}

export function TrackExplorerSection({
  analysisId,
  videoId: initialVideoId,
  overlaySettings = DEFAULT_DETECTION_OVERLAY_SETTINGS,
}: TrackExplorerSectionProps) {
  const [tracks, setTracks] = useState<TrackSummaryInfo[]>([])
  const [fetchedVideoId, setFetchedVideoId] = useState<string>('')
  const [loadedTracksForId, setLoadedTracksForId] = useState<string | null>(null)
  const [tracksError, setTracksError] = useState<string | null>(null)
  const [classFilter, setClassFilter] = useState<string>('all')

  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null)
  const [trackDetail, setTrackDetail] = useState<TrackDetailResponse | null>(null)
  const [observationFrames, setObservationFrames] = useState<TrackObservationFrameInfo[]>([])
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const [activeObsIndex, setActiveObsIndex] = useState<number>(0)
  const [videoTime, setVideoTime] = useState<number>(0)
  const [streamedVideoState, setStreamedVideoState] = useState<{
    videoId: string
    url: string | null
    error: string | null
  }>({ videoId: '', url: null, error: null })
  const [videoPlaybackFailure, setVideoPlaybackFailure] = useState<{
    videoId: string
    message: string | null
  }>({ videoId: '', message: null })
  const [videoPreparation, setVideoPreparation] = useState<{
    videoId: string
    message: string
    progress: number
  }>({ videoId: '', message: '', progress: 0 })

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const pendingSeekRef = useRef<number | null>(null)
  const detailPanelRef = useRef<HTMLDivElement | null>(null)

  const resolvedVideoId = initialVideoId || fetchedVideoId
  const isLoadingTracks = Boolean(analysisId) && loadedTracksForId !== analysisId
  const videoPlaybackError =
    videoPlaybackFailure.videoId === resolvedVideoId ? videoPlaybackFailure.message : null
  const currentVideoPreparation =
    videoPreparation.videoId === resolvedVideoId ? videoPreparation : null

  // Load saved tracks list for this analysis
  useEffect(() => {
    if (!analysisId) return

    let cancelled = false

    getAnalysisTracks(analysisId)
      .then((res) => {
        if (cancelled) return
        setTracks(res.tracks ?? [])
        setTracksError(null)
        setLoadedTracksForId(analysisId)
        if (res.video_id) {
          setFetchedVideoId(res.video_id)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setTracksError(getAuthErrorMessage(error, 'Failed to load tracking records.'))
          setLoadedTracksForId(analysisId)
        }
      })

    return () => {
      cancelled = true
    }
  }, [analysisId])

  // Use the backend's inspected or converted playback source for saved analyses.
  useEffect(() => {
    if (!resolvedVideoId) {
      return
    }

    let active = true
    let createdUrl: string | null = null

    fetchVideoBlobUrl(resolvedVideoId, (progress, message) => {
      if (active) {
        setVideoPreparation({ videoId: resolvedVideoId, progress, message })
      }
    })
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setStreamedVideoState({ videoId: resolvedVideoId, url, error: null })
      })
      .catch((error) => {
        if (active) {
          setStreamedVideoState({
            videoId: resolvedVideoId,
            url: null,
            error:
              error instanceof Error
                ? error.message
                : getAuthErrorMessage(error, 'Unable to prepare source video playback.'),
          })
          setVideoPlaybackFailure({
            videoId: resolvedVideoId,
            message:
              error instanceof Error
                ? error.message
                : getAuthErrorMessage(error, 'Unable to prepare source video playback.'),
          })
        }
      })

    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [resolvedVideoId])

  const videoBlobUrl =
    streamedVideoState.videoId === resolvedVideoId ? streamedVideoState.url : null
  const videoLoadError =
    streamedVideoState.videoId === resolvedVideoId ? streamedVideoState.error : null
  const isLoadingVideo =
    Boolean(resolvedVideoId) && streamedVideoState.videoId !== resolvedVideoId

  const seekVideoTo = useCallback(
    (timestampSeconds: number) => {
      const safeTs = Math.max(0, timestampSeconds)
      const videoEl = videoRef.current
      setVideoTime(safeTs)

      if (observationFrames.length > 0) {
        let nearestIdx = 0
        let minDiff = Math.abs(observationFrames[0].timestamp_seconds - safeTs)
        for (let i = 1; i < observationFrames.length; i += 1) {
          const diff = Math.abs(observationFrames[i].timestamp_seconds - safeTs)
          if (diff < minDiff) {
            minDiff = diff
            nearestIdx = i
          }
        }
        if (minDiff <= 0.75) {
          setActiveObsIndex(nearestIdx)
        }
      }

      if (!videoEl) {
        pendingSeekRef.current = safeTs
        return
      }
      if (videoEl.readyState >= 1) {
        videoEl.currentTime = safeTs
        pendingSeekRef.current = null
      } else {
        pendingSeekRef.current = safeTs
      }
    },
    [observationFrames],
  )

  const handleSelectTrack = useCallback(
    async (trackId: number) => {
      if (!analysisId) return
      setSelectedTrackId(trackId)
      setIsLoadingDetail(true)
      setDetailError(null)
      setActiveObsIndex(0)

      try {
        const [detailRes, framesRes] = await Promise.all([
          getAnalysisTrackDetail(analysisId, trackId),
          getAnalysisTrackFrames(analysisId, trackId),
        ])
        setTrackDetail(detailRes)
        const framesList = framesRes.frames.length > 0 ? framesRes.frames : detailRes.frames
        setObservationFrames(framesList)
        if (detailRes.video_id) {
          setFetchedVideoId(detailRes.video_id)
        }
        if (framesList.length > 0) {
          seekVideoTo(framesList[0].timestamp_seconds)
        }
      } catch (error) {
        setDetailError(getAuthErrorMessage(error, 'Failed to load track detail information.'))
      } finally {
        setIsLoadingDetail(false)
      }
    },
    [analysisId, seekVideoTo],
  )

  const handleSelectObservationIndex = useCallback(
    (index: number) => {
      if (index < 0 || index >= observationFrames.length) return
      setActiveObsIndex(index)
      seekVideoTo(observationFrames[index].timestamp_seconds)
    },
    [observationFrames, seekVideoTo],
  )

  const handleSelectObservationFrame = useCallback(
    (obs: TrackObservationFrameInfo) => {
      const idx = observationFrames.findIndex((f) => f.frame_index === obs.frame_index)
      if (idx >= 0) {
        setActiveObsIndex(idx)
      }
      seekVideoTo(obs.timestamp_seconds)
    },
    [observationFrames, seekVideoTo],
  )

  const handleVideoLoadedMetadata = () => {
    const videoEl = videoRef.current
    if (!videoEl) return
    if (pendingSeekRef.current !== null) {
      videoEl.currentTime = pendingSeekRef.current
      pendingSeekRef.current = null
    }
  }

  const handleVideoTimeUpdate = () => {
    const videoEl = videoRef.current
    if (!videoEl || observationFrames.length === 0) return
    const now = videoEl.currentTime
    setVideoTime(now)

    let nearestIdx = 0
    let minDiff = Math.abs(observationFrames[0].timestamp_seconds - now)
    for (let i = 1; i < observationFrames.length; i += 1) {
      const diff = Math.abs(observationFrames[i].timestamp_seconds - now)
      if (diff < minDiff) {
        minDiff = diff
        nearestIdx = i
      }
    }
    if (minDiff <= 0.75) {
      setActiveObsIndex(nearestIdx)
    }
  }

  const classCounts = useMemo(() => {
    const map = new Map<string, number>()
    for (const trk of tracks) {
      map.set(trk.class_name, (map.get(trk.class_name) ?? 0) + 1)
    }
    return Array.from(map.entries())
  }, [tracks])

  const filteredTracks = useMemo(() => {
    if (classFilter === 'all') return tracks
    return tracks.filter((t) => t.class_name === classFilter)
  }, [tracks, classFilter])

  const activeObservation = observationFrames[activeObsIndex] ?? null
  const isVideoNearActiveObservation =
    activeObservation !== null && Math.abs(videoTime - activeObservation.timestamp_seconds) <= 0.85

  const overlayFrameW = activeObservation?.frame_width ?? trackDetail?.frame_width ?? null
  const overlayFrameH = activeObservation?.frame_height ?? trackDetail?.frame_height ?? null
  const canRenderVideoOverlay =
    isVideoNearActiveObservation &&
    activeObservation !== null &&
    typeof overlayFrameW === 'number' &&
    overlayFrameW > 0 &&
    typeof overlayFrameH === 'number' &&
    overlayFrameH > 0

  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="space-y-6 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs"
      aria-labelledby="track-explorer-heading"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#2563EB]/12 to-[#7C3AED]/12 text-[#2563EB]">
            <Crosshair className="h-5 w-5" />
          </div>
          <div>
            <h3
              id="track-explorer-heading"
              className="font-display text-lg font-bold text-[#111827]"
            >
              Track Explorer
            </h3>
            <p className="text-xs text-[#64748B]">
              Click any tracking ID to visually inspect its bounding box, movement history, and
              synced video observations.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#2563EB]/20 bg-[#EFF6FF] px-3 py-1 font-mono text-[11px] font-semibold text-[#2563EB]">
            {tracks.length} {tracks.length === 1 ? 'Track' : 'Tracks'} Saved
          </span>
          <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-[11px] font-medium text-[#64748B]">
            Temporary session IDs · Not real identities
          </span>
        </div>
      </div>

      {tracksError && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{tracksError}</span>
        </div>
      )}

      {isLoadingTracks ? (
        <div className="flex items-center gap-2.5 py-8 text-xs font-medium text-[#64748B]">
          <Loader2 className="h-4 w-4 animate-spin text-[#2563EB]" />
          <span>Loading persistent object tracks...</span>
        </div>
      ) : tracks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-[#F5F8FC] px-6 py-10 text-center">
          <GitBranch className="mx-auto h-7 w-7 text-[#64748B]" />
          <p className="mt-2.5 text-sm font-semibold text-[#111827]">
            No tracking records found for this analysis
          </p>
          <p className="mx-auto mt-1 max-w-md text-xs text-[#64748B]">
            ByteTrack only creates tracking IDs when objects are detected consistently across
            sampled frames. Try re-running analysis with higher sensitivity if expected objects were
            missed.
          </p>
        </div>
      ) : (
        <>
          {/* Class Filter Bar */}
          {classCounts.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setClassFilter('all')}
                className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  classFilter === 'all'
                    ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                    : 'border-slate-200 bg-white text-[#64748B] hover:border-slate-300 hover:bg-[#F5F8FC] hover:text-[#111827]'
                }`}
              >
                All tracks ({tracks.length})
              </button>
              {classCounts.map(([cls, count]) => (
                <button
                  key={cls}
                  type="button"
                  onClick={() => setClassFilter(cls)}
                  className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-xs font-semibold capitalize transition-all ${
                    classFilter === cls
                      ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                      : 'border-slate-200 bg-white text-[#64748B] hover:border-slate-300 hover:bg-[#F5F8FC] hover:text-[#111827]'
                  }`}
                >
                  {formatClassLabel(cls)} ({count})
                </button>
              ))}
            </div>
          )}

          {/* Track Cards Grid */}
          <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
            {filteredTracks.map((track) => {
              const code = formatTrackCode(track)
              const isSelected = selectedTrackId === track.track_id
              const lastPos = track.last_known_position

              return (
                <button
                  key={track.track_id}
                  type="button"
                  onClick={() => void handleSelectTrack(track.track_id)}
                  className={`cursor-pointer rounded-2xl border p-4 text-left transition-all ${
                    isSelected
                      ? 'border-[#2563EB] bg-[#EFF6FF]/75 ring-2 ring-[#2563EB]/20 shadow-sm'
                      : 'border-slate-200/90 bg-[#F5F8FC] hover:border-[#2563EB]/45 hover:bg-white hover:shadow-xs'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-lg px-2 py-0.5 font-mono text-xs font-bold ${
                          isSelected
                            ? 'bg-[#2563EB] text-white'
                            : 'bg-[#2563EB]/12 text-[#2563EB]'
                        }`}
                      >
                        {code}
                      </span>
                      <span className="font-display text-sm font-bold text-[#111827]">
                        {formatClassLabel(track.class_name)}
                      </span>
                    </div>

                    <span className="font-mono text-[11px] font-semibold text-[#7C3AED]">
                      {Math.round(track.avg_confidence * 100)}% avg
                    </span>
                  </div>

                  <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
                    <div>
                      <dt className="text-[#64748B]">First seen</dt>
                      <dd className="font-mono font-semibold text-[#111827]">
                        {formatHms(track.first_seen_timestamp)} ({track.first_seen_timestamp.toFixed(1)}s)
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#64748B]">Last seen</dt>
                      <dd className="font-mono font-semibold text-[#111827]">
                        {formatHms(track.last_seen_timestamp)} ({track.last_seen_timestamp.toFixed(1)}s)
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#64748B]">Observations</dt>
                      <dd className="font-mono font-semibold text-[#111827]">
                        {track.frame_count} frame{track.frame_count === 1 ? '' : 's'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#64748B]">Visible duration</dt>
                      <dd className="font-mono font-semibold text-[#111827]">
                        {track.duration_seconds.toFixed(1)}s
                      </dd>
                    </div>
                  </dl>

                  <div className="mt-3 flex items-center justify-between gap-2 border-t border-slate-200/80 pt-2.5 text-[11px]">
                    <span className="inline-flex items-center gap-1 truncate font-mono text-[#64748B]">
                      <MapPin className="h-3 w-3 shrink-0 text-[#2563EB]" />
                      {lastPos
                        ? `Last: (${Math.round(lastPos.center_x)}, ${Math.round(lastPos.center_y)}) px`
                        : 'Last position unavailable'}
                    </span>
                    <span className="inline-flex shrink-0 items-center gap-1 font-semibold text-[#2563EB]">
                      <span>Inspect</span>
                      <ArrowRight className="h-3 w-3" />
                    </span>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Track Detail Panel */}
          {selectedTrackId !== null && (
            <div
              ref={detailPanelRef}
              className="space-y-6 rounded-3xl border border-[#2563EB]/30 bg-[#F5F8FC]/70 p-5 sm:p-6"
            >
              {isLoadingDetail ? (
                <div className="flex items-center gap-2.5 py-10 text-xs font-medium text-[#64748B]">
                  <Loader2 className="h-4 w-4 animate-spin text-[#2563EB]" />
                  <span>Loading track detail, annotated frames, and movement history...</span>
                </div>
              ) : detailError ? (
                <div
                  role="alert"
                  className="flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
                >
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{detailError}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedTrackId(null)}
                    className="cursor-pointer rounded p-0.5 text-rose-700 hover:bg-rose-100"
                    aria-label="Close track detail"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                trackDetail && (
                  <>
                    {/* Detail Header */}
                    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-lg bg-[#2563EB] px-2.5 py-1 font-mono text-xs font-bold text-white">
                            {trackDetail.track_code}
                          </span>
                          <h4 className="font-display text-base font-bold text-[#111827]">
                            {formatClassLabel(trackDetail.track.class_name)} Trajectory Inspector
                          </h4>
                          <span className="rounded-full border border-[#7C3AED]/25 bg-white px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#7C3AED]">
                            {Math.round(trackDetail.track.avg_confidence * 100)}% avg ·{' '}
                            {Math.round(trackDetail.track.max_confidence * 100)}% peak
                          </span>
                        </div>
                        <p className="mt-1.5 text-xs text-[#64748B]">
                          {trackDetail.temporary_id_notice}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => setSelectedTrackId(null)}
                        className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] hover:border-slate-300 hover:bg-slate-50"
                      >
                        <X className="h-3.5 w-3.5" />
                        <span>Close Detail</span>
                      </button>
                    </div>

                    {/* Video Integration + Movement Summary */}
                    <div className="grid gap-5 lg:grid-cols-12">
                      {/* Uploaded Video Sync Player */}
                      <div className="space-y-3 rounded-2xl border border-slate-200/90 bg-white p-4 lg:col-span-7">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Film className="h-4 w-4 text-[#2563EB]" />
                            <h5 className="font-display text-sm font-bold text-[#111827]">
                              Synced Video Playback
                            </h5>
                          </div>

                          <div className="flex flex-wrap items-center gap-1.5">
                            <button
                              type="button"
                              disabled={observationFrames.length === 0 || activeObsIndex <= 0}
                              onClick={() => handleSelectObservationIndex(activeObsIndex - 1)}
                              className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 text-[11px] font-semibold text-[#111827] hover:border-[#2563EB]/40 hover:text-[#2563EB] disabled:cursor-not-allowed disabled:opacity-45"
                            >
                              <ChevronLeft className="h-3.5 w-3.5" />
                              <span>Prev Obs</span>
                            </button>
                            <span className="px-1.5 font-mono text-[11px] font-semibold text-[#64748B]">
                              {observationFrames.length > 0
                                ? `${activeObsIndex + 1} / ${observationFrames.length}`
                                : '0 / 0'}
                            </span>
                            <button
                              type="button"
                              disabled={
                                observationFrames.length === 0 ||
                                activeObsIndex >= observationFrames.length - 1
                              }
                              onClick={() => handleSelectObservationIndex(activeObsIndex + 1)}
                              className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 text-[11px] font-semibold text-[#111827] hover:border-[#2563EB]/40 hover:text-[#2563EB] disabled:cursor-not-allowed disabled:opacity-45"
                            >
                              <span>Next Obs</span>
                              <ChevronRight className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>

                        {isLoadingVideo ? (
                          <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-[#F5F8FC] px-6 text-xs font-medium text-[#64748B]">
                            <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin text-[#2563EB]" />{currentVideoPreparation?.message || 'Preparing video playback...'}</span>
                            <progress value={currentVideoPreparation?.progress ?? 0} max={100} className="h-1.5 w-full max-w-sm accent-blue-600" />
                            {currentVideoPreparation?.message.toLowerCase().includes('convert') && <span>{currentVideoPreparation.progress}%</span>}
                          </div>
                        ) : videoLoadError || videoPlaybackError || !videoBlobUrl ? (
                          <div className="flex aspect-video w-full flex-col items-center justify-center rounded-xl border border-slate-200 bg-[#F5F8FC] px-4 text-center">
                            <Film className="h-7 w-7 text-[#2563EB]" />
                            <p className="mt-2 text-xs font-semibold text-[#111827]">
                              {videoLoadError || videoPlaybackError || 'Video playback could not be prepared.'}
                            </p>
                            <p className="mt-1 text-[11px] text-[#64748B]">
                              You can still inspect every annotated frame and coordinate delta below.
                            </p>
                          </div>
                        ) : (
                          <div
                            className="relative mx-auto w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-950"
                            style={
                              overlayFrameW && overlayFrameH
                                ? { aspectRatio: `${overlayFrameW} / ${overlayFrameH}` }
                                : undefined
                            }
                          >
                            <video
                              ref={videoRef}
                              src={videoBlobUrl}
                              controls
                              playsInline
                              onLoadedMetadata={handleVideoLoadedMetadata}
                              onLoadedData={() => setVideoPlaybackFailure({ videoId: resolvedVideoId, message: null })}
                              onTimeUpdate={handleVideoTimeUpdate}
                              onSeeked={handleVideoTimeUpdate}
                              onError={(event) => {
                                const code = event.currentTarget.error?.code
                                setVideoPlaybackFailure({
                                  videoId: resolvedVideoId,
                                  message: code === 4
                                    ? 'The browser does not support this prepared video source.'
                                    : `Video playback failed${code ? ` (media error ${code})` : ''}.`,
                                })
                              }}
                              className="h-full w-full object-contain"
                            />

                            {canRenderVideoOverlay && activeObservation && overlayFrameW && overlayFrameH && (
                              <ObjectDetectionOverlay
                                detections={[
                                  activeObservation.selected_detection,
                                  ...activeObservation.other_detections,
                                ]}
                                width={overlayFrameW}
                                height={overlayFrameH}
                                settings={overlaySettings}
                              />
                            )}
                          </div>
                        )}

                        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                          <span className="font-mono text-[#64748B]">
                            {activeObservation ? (
                              isVideoNearActiveObservation ? (
                                <span className="font-semibold text-[#2563EB]">
                                  Overlay synced · {trackDetail.track_code} at{' '}
                                  {activeObservation.timestamp_seconds.toFixed(2)}s
                                </span>
                              ) : (
                                <span>
                                  Playhead at {videoTime.toFixed(2)}s · Click an observation below
                                  to sync overlay
                                </span>
                              )
                            ) : (
                              <span>No frame observations available</span>
                            )}
                          </span>

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleSelectObservationIndex(0)}
                              disabled={observationFrames.length === 0}
                              className="cursor-pointer font-mono font-semibold text-[#2563EB] hover:underline disabled:opacity-40"
                            >
                              First ({trackDetail.track.first_seen_timestamp.toFixed(2)}s)
                            </button>
                            <span className="text-slate-300">|</span>
                            <button
                              type="button"
                              onClick={() =>
                                handleSelectObservationIndex(observationFrames.length - 1)
                              }
                              disabled={observationFrames.length === 0}
                              className="cursor-pointer font-mono font-semibold text-[#7C3AED] hover:underline disabled:opacity-40"
                            >
                              Last ({trackDetail.track.last_seen_timestamp.toFixed(2)}s)
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Movement History & Position Changes */}
                      <div className="space-y-4 rounded-2xl border border-slate-200/90 bg-white p-4 lg:col-span-5">
                        <div className="flex items-center gap-2">
                          <Compass className="h-4 w-4 text-[#7C3AED]" />
                          <h5 className="font-display text-sm font-bold text-[#111827]">
                            Movement History &amp; Position Changes
                          </h5>
                        </div>

                        <div className="grid grid-cols-2 gap-2.5 text-xs">
                          <div className="rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3">
                            <p className="text-[11px] text-[#64748B]">Dominant Direction</p>
                            <p className="mt-0.5 font-semibold capitalize text-[#111827]">
                              {trackDetail.movement_history.dominant_direction}
                            </p>
                          </div>
                          <div className="rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3">
                            <p className="text-[11px] text-[#64748B]">Net Displacement</p>
                            <p className="mt-0.5 font-mono font-semibold text-[#111827]">
                              {trackDetail.movement_history.net_displacement_px.toFixed(1)} px
                              {trackDetail.movement_history.net_displacement_norm != null
                                ? ` (${Math.round(trackDetail.movement_history.net_displacement_norm * 100)}%)`
                                : ''}
                            </p>
                          </div>
                          <div className="rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3">
                            <p className="text-[11px] text-[#64748B]">Total Path Distance</p>
                            <p className="mt-0.5 font-mono font-semibold text-[#111827]">
                              {trackDetail.movement_history.total_path_distance_px.toFixed(1)} px
                            </p>
                          </div>
                          <div className="rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3">
                            <p className="text-[11px] text-[#64748B]">Last Known Position</p>
                            <p className="mt-0.5 font-mono font-semibold text-[#111827]">
                              {trackDetail.last_known_position
                                ? `(${Math.round(trackDetail.last_known_position.center_x)}, ${Math.round(trackDetail.last_known_position.center_y)})`
                                : 'Unavailable'}
                            </p>
                          </div>
                        </div>

                        {trackDetail.movement_history.steps.length === 0 ? (
                          <p className="rounded-xl border border-dashed border-slate-200 bg-[#F5F8FC] px-3 py-4 text-center text-xs text-[#64748B]">
                            Single observation recorded — at least two observations are needed to
                            compute step-by-step displacement.
                          </p>
                        ) : (
                          <div className="max-h-60 space-y-2 overflow-y-auto pr-1">
                            {trackDetail.movement_history.steps.map((step, idx) => (
                              <div
                                key={`${step.from_frame_index}-${step.to_frame_index}-${idx}`}
                                className="rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3 text-xs"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <span className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-[#111827]">
                                    <Activity className="h-3 w-3 text-[#2563EB]" />
                                    Frame #{step.from_frame_index + 1} → #{step.to_frame_index + 1}
                                  </span>
                                  <span className="rounded-md bg-white px-2 py-0.5 font-mono text-[10px] font-semibold text-[#7C3AED]">
                                    {step.direction} ({step.displacement_px.toFixed(1)} px)
                                  </span>
                                </div>

                                <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-[#64748B]">
                                  <span>
                                    ({Math.round(step.from_center_x)}, {Math.round(step.from_center_y)}
                                    ) → ({Math.round(step.to_center_x)},{' '}
                                    {Math.round(step.to_center_y)}) · Δ(
                                    {step.delta_x >= 0 ? '+' : ''}
                                    {Math.round(step.delta_x)},{' '}
                                    {step.delta_y >= 0 ? '+' : ''}
                                    {Math.round(step.delta_y)})
                                  </span>

                                  <button
                                    type="button"
                                    onClick={() => seekVideoTo(step.to_timestamp)}
                                    className="cursor-pointer font-semibold text-[#2563EB] hover:underline"
                                  >
                                    @ {formatHms(step.to_timestamp)} ({step.to_timestamp.toFixed(2)}s)
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Related Discovered Events */}
                    <div className="rounded-2xl border border-slate-200/90 bg-white p-4">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <ShieldAlert className="h-4 w-4 text-[#2563EB]" />
                          <h5 className="font-display text-sm font-bold text-[#111827]">
                            Related Discovered Events ({trackDetail.related_events.length})
                          </h5>
                        </div>
                      </div>

                      {trackDetail.related_events.length === 0 ? (
                        <p className="mt-2.5 text-xs text-[#64748B]">
                          No discovered events currently reference {trackDetail.track_code}. Run
                          Event Discovery above if you have not executed it yet for this analysis.
                        </p>
                      ) : (
                        <div className="mt-3 grid gap-2.5 md:grid-cols-2">
                          {trackDetail.related_events.map((evt) => (
                            <div
                              key={evt.id}
                              className="rounded-xl border border-slate-200/80 bg-[#F5F8FC] p-3.5"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-display text-xs font-bold text-[#111827]">
                                  {evt.title}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => seekVideoTo(evt.start_timestamp)}
                                  className="inline-flex cursor-pointer items-center gap-1 rounded-md bg-white px-2 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB] border border-slate-200 hover:border-[#2563EB]"
                                >
                                  <Clock className="h-3 w-3" />
                                  <span>
                                    {formatHms(evt.start_timestamp)} → {formatHms(evt.end_timestamp)}
                                  </span>
                                </button>
                              </div>
                              <p className="mt-1.5 text-xs leading-relaxed text-[#64748B]">
                                {evt.description}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Annotated Frames for Selected Track */}
                    <div className="space-y-3 rounded-2xl border border-slate-200/90 bg-white p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <h5 className="font-display text-sm font-bold text-[#111827]">
                            Annotated Frames Containing {trackDetail.track_code} (
                            {observationFrames.length})
                          </h5>
                          <p className="text-xs text-[#64748B]">
                            Selected track bounding box is highlighted in blue; click any frame or
                            timestamp to seek the video player.
                          </p>
                        </div>
                      </div>

                      {observationFrames.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-slate-200 bg-[#F5F8FC] px-4 py-8 text-center text-xs text-[#64748B]">
                          No observation frames were found for {trackDetail.track_code}.
                        </p>
                      ) : (
                        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
                          {observationFrames.map((obs, idx) => (
                            <TrackAnnotatedFrameCard
                              key={`${obs.frame_index}-${obs.filename}`}
                              analysisId={analysisId}
                              trackCode={trackDetail.track_code}
                              observation={obs}
                              isActive={idx === activeObsIndex}
                              overlaySettings={overlaySettings}
                              onSelectObservation={handleSelectObservationFrame}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )
              )}
            </div>
          )}
        </>
      )}
    </motion.section>
  )
}
