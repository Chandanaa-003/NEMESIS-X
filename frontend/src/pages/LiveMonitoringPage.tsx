import axios from 'axios'
import {
  Activity,
  AlertCircle,
  Camera,
  CameraOff,
  Clock,
  Crosshair,
  GitBranch,
  ImageOff,
  Loader2,
  Play,
  Radio,
  ScanSearch,
  ShieldAlert,
  Sliders,
  Square,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { VoiceAlertCenter } from '../components/analysis/VoiceAlertCenter'
import {
  ObjectDetectionOverlay,
  ObjectOverlayControls,
} from '../components/analysis/ObjectDetectionOverlay'
import { useDetectionOverlaySettings } from '../components/analysis/detectionOverlaySettings'
import type { TrackSummaryInfo } from '../services/analysisService'
import { getAuthErrorMessage } from '../services/authService'
import {
  announceLiveMonitoringEvent,
  classifyEventPriority,
  setActiveVoiceSettings,
} from '../services/eventAnnouncementService'
import {
  fetchLiveEventSnapshotBlobUrl,
  sendLiveFrame,
  startLiveMonitoringSession,
  stopLiveMonitoringSession,
  type LiveDetectionInfo,
  type LiveEventInfo,
} from '../services/liveService'
import { listZones, type ZoneRecord } from '../services/zoneService'
import { fetchUserVoiceSettings } from '../services/settingsService'

type CameraPermissionState =
  | 'idle'
  | 'requesting'
  | 'granted'
  | 'denied'
  | 'unavailable'
  | 'error'

type MonitoringRunState = 'idle' | 'starting' | 'active' | 'stopped' | 'error'

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hrs > 0) {
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatTrackCode(track: Pick<TrackSummaryInfo, 'track_id' | 'track_code'>): string {
  return track.track_code || `T${String(track.track_id).padStart(3, '0')}`
}

function summarizeTrackMovement(track: TrackSummaryInfo): string {
  const pts = track.timeline_points
  if (!pts || pts.length === 0) return 'Position pending'
  const last = pts[pts.length - 1]
  if (pts.length === 1) {
    return `Pos (${Math.round(last.center_x)}, ${Math.round(last.center_y)}) px · 1st obs`
  }
  const first = pts[0]
  const dx = last.center_x - first.center_x
  const dy = last.center_y - first.center_y
  const dist = Math.hypot(dx, dy)
  const dir =
    dist <= 10
      ? 'stationary'
      : Math.abs(dx) >= Math.abs(dy)
        ? dx > 0
          ? 'moving right'
          : 'moving left'
        : dy > 0
          ? 'moving down'
          : 'moving up'
  return `${dir} (${dist.toFixed(0)} px) · (${Math.round(last.center_x)}, ${Math.round(last.center_y)})`
}

const SEVERITY_BADGE: Record<string, string> = {
  high: 'border-rose-200 bg-rose-50 text-rose-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  low: 'border-[#2563EB]/20 bg-[#EFF6FF] text-[#2563EB]',
}

function LiveSnapshotThumbnail({ sessionId, eventId, title }: { sessionId: string; eventId: string; title: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    let createdUrl: string | null = null

    fetchLiveEventSnapshotBlobUrl(sessionId, eventId)
      .then((blobUrl) => {
        if (!active) {
          URL.revokeObjectURL(blobUrl)
          return
        }
        createdUrl = blobUrl
        setUrl(blobUrl)
      })
      .catch(() => {
        if (active) setFailed(true)
      })

    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [sessionId, eventId])

  if (failed) {
    return (
      <div className="flex h-16 w-24 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-[#F5F8FC] text-[#64748B]">
        <ImageOff className="h-4 w-4" />
      </div>
    )
  }
  if (!url) {
    return <div className="h-16 w-24 shrink-0 animate-pulse rounded-xl bg-slate-100" />
  }
  return (
    <img
      src={url}
      alt={`Snapshot for ${title}`}
      className="h-16 w-24 shrink-0 rounded-xl border border-slate-200 object-cover"
    />
  )
}

export function LiveMonitoringPage() {
  const { settings: overlaySettings, updateSettings: updateOverlaySettings } =
    useDetectionOverlaySettings()
  // Configurable capture & inference parameters (CPU + bandwidth friendly)
  const [captureMaxWidth, setCaptureMaxWidth] = useState<number>(640)
  const [jpegQuality, setJpegQuality] = useState<number>(0.75)
  const [captureIntervalMs, setCaptureIntervalMs] = useState<number>(1000)
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.4)

  const [cameraPermission, setCameraPermission] = useState<CameraPermissionState>('idle')
  const [monitoringState, setMonitoringState] = useState<MonitoringRunState>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [errorBanner, setErrorBanner] = useState<string | null>(null)
  const [frameStatusText, setFrameStatusText] = useState<string>('Waiting to start monitoring')

  // Live telemetry
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0)
  const [framesProcessed, setFramesProcessed] = useState<number>(0)
  const [totalDetections, setTotalDetections] = useState<number>(0)
  const [uniqueTracksCount, setUniqueTracksCount] = useState<number>(0)
  const [eventsDiscoveredCount, setEventsDiscoveredCount] = useState<number>(0)

  const [currentFrameTimestamp, setCurrentFrameTimestamp] = useState<number | null>(null)
  const [latestFrameIndex, setLatestFrameIndex] = useState<number>(-1)
  const [overlaySize, setOverlaySize] = useState<{ width: number; height: number } | null>(null)
  const [currentDetections, setCurrentDetections] = useState<LiveDetectionInfo[]>([])
  const [processedFrameUrl, setProcessedFrameUrl] = useState<string | null>(null)
  const [activeTracks, setActiveTracks] = useState<TrackSummaryInfo[]>([])
  const [liveEvents, setLiveEvents] = useState<LiveEventInfo[]>([])
  const [liveZones, setLiveZones] = useState<ZoneRecord[]>([])

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const captureTimerRef = useRef<number | null>(null)
  const durationTimerRef = useRef<number | null>(null)
  const startedAtMsRef = useRef<number>(0)
  const sessionIdRef = useRef<string | null>(null)
  const isMonitoringRef = useRef<boolean>(false)
  const isSendingFrameRef = useRef<boolean>(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const processedFrameUrlRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      if (processedFrameUrlRef.current) URL.revokeObjectURL(processedFrameUrlRef.current)
    }
  }, [])

  // Sync user's saved Kannada/English voice preferences for live alerts
  useEffect(() => {
    let cancelled = false
    fetchUserVoiceSettings()
      .then((saved) => {
        if (!cancelled) {
          setActiveVoiceSettings(saved)
        }
      })
      .catch(() => {
        // Default settings remain active if backend fetch is unavailable
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!sessionId) return
    let active = true
    const refreshZones = async () => {
      try {
        const nextZones = await listZones({ liveSessionId: sessionId })
        if (active) setLiveZones(nextZones)
      } catch (error) {
        if (active) {
          setErrorBanner(getAuthErrorMessage(error, 'Could not refresh live zone configuration.'))
        }
      }
    }
    void refreshZones()
    const timerId = window.setInterval(() => void refreshZones(), 3000)
    return () => {
      active = false
      window.clearInterval(timerId)
    }
  }, [sessionId])

  const releaseLocalCamera = useCallback(() => {
    if (captureTimerRef.current !== null) {
      window.clearInterval(captureTimerRef.current)
      captureTimerRef.current = null
    }
    if (durationTimerRef.current !== null) {
      window.clearInterval(durationTimerRef.current)
      durationTimerRef.current = null
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        track.stop()
      }
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    isMonitoringRef.current = false
    isSendingFrameRef.current = false
  }, [])

  // Ensure hardware webcam & backend session stop cleanly if user navigates away
  useEffect(() => {
    return () => {
      const activeId = sessionIdRef.current
      releaseLocalCamera()
      if (activeId) {
        sessionIdRef.current = null
        void stopLiveMonitoringSession(activeId).catch(() => {})
      }
    }
  }, [releaseLocalCamera])

  const captureAndSendOneFrame = useCallback(async () => {
    if (!isMonitoringRef.current || isSendingFrameRef.current) return
    const activeSessionId = sessionIdRef.current
    const videoEl = videoRef.current
    const canvasEl = canvasRef.current
    if (!activeSessionId || !videoEl || !canvasEl) return
    if (videoEl.readyState < 2 || videoEl.videoWidth === 0 || videoEl.videoHeight === 0) return

    const srcW = videoEl.videoWidth
    const srcH = videoEl.videoHeight
    const targetW = Math.min(captureMaxWidth, srcW)
    const targetH = Math.max(1, Math.round(srcH * (targetW / srcW)))

    canvasEl.width = targetW
    canvasEl.height = targetH
    const ctx = canvasEl.getContext('2d')
    if (!ctx) return

    ctx.drawImage(videoEl, 0, 0, targetW, targetH)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvasEl.toBlob((result) => resolve(result), 'image/jpeg', jpegQuality)
    })
    if (!blob || !isMonitoringRef.current) return

    isSendingFrameRef.current = true
    setFrameStatusText('Analyzing live frame (YOLO + ByteTrack)...')
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      const elapsedSec = Math.max(0, (Date.now() - startedAtMsRef.current) / 1000)
      const res = await sendLiveFrame({
        sessionId: activeSessionId,
        frameBlob: blob,
        timestampSeconds: Number(elapsedSec.toFixed(2)),
        signal: controller.signal,
        timeoutMs: 8000,
      })
      if (!isMonitoringRef.current) return

      setFramesProcessed(res.frames_processed)
      setTotalDetections(res.total_detections)
      setUniqueTracksCount(res.unique_tracks_count)
      setEventsDiscoveredCount(res.events_discovered_count)
      setCurrentFrameTimestamp(res.timestamp_seconds)
      setLatestFrameIndex(res.frame_index)
      setOverlaySize({ width: res.frame_width, height: res.frame_height })
      const nextFrameUrl = URL.createObjectURL(blob)
      if (processedFrameUrlRef.current) URL.revokeObjectURL(processedFrameUrlRef.current)
      processedFrameUrlRef.current = nextFrameUrl
      setProcessedFrameUrl(nextFrameUrl)
      setCurrentDetections(res.detections)
      setActiveTracks(res.active_tracks)
      setFrameStatusText(`Frame #${res.frame_index + 1} processed in ${res.processing_ms} ms`)
      setErrorBanner(null)

      if (res.new_events.length > 0) {
        setLiveEvents((prev) => [...res.new_events, ...prev].slice(0, 40))
        for (const evt of res.new_events) {
          void announceLiveMonitoringEvent({
            id: evt.id,
            streamId: res.session_id,
            eventType: evt.event_type,
            category: evt.category,
            title: evt.title,
            timestampSeconds: evt.timestamp_seconds,
            severity: (evt.severity as 'low' | 'medium' | 'high') || 'low',
            requiresHumanReview: evt.requires_human_review,
            zoneName: evt.zone_name ?? undefined,
            alertsEnabled: evt.alerts_enabled,
            voiceAlertsEnabled: evt.voice_alerts_enabled,
          })
        }
      }
    } catch (error) {
      if (axios.isCancel(error)) {
        return
      }
      if (isMonitoringRef.current) {
        setFrameStatusText('Frame processing delayed or failed')
        setErrorBanner(
          getAuthErrorMessage(error, 'Error processing live webcam frame. Retrying next interval.'),
        )
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null
      }
      isSendingFrameRef.current = false
    }
  }, [captureMaxWidth, jpegQuality])

  const handleStartMonitoring = async () => {
    if (monitoringState === 'starting' || monitoringState === 'active') return

    setErrorBanner(null)
    setMonitoringState('starting')
    setFrameStatusText('Requesting webcam access...')

    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== 'function'
    ) {
      setCameraPermission('unavailable')
      setMonitoringState('error')
      setFrameStatusText('Browser camera API unavailable')
      setErrorBanner(
        'Webcam access (navigator.mediaDevices.getUserMedia) is unavailable in this browser or context (requires localhost or HTTPS).',
      )
      return
    }

    setCameraPermission('requesting')
    let mediaStream: MediaStream
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: captureMaxWidth },
          height: { ideal: Math.round((captureMaxWidth * 9) / 16) },
        },
        audio: false,
      })
    } catch (err) {
      const errName = err instanceof DOMException ? err.name : ''
      if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
        setCameraPermission('denied')
        setErrorBanner(
          'Camera permission was denied. Allow webcam access in browser site settings and click Start Monitoring again.',
        )
      } else if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError') {
        setCameraPermission('unavailable')
        setErrorBanner('No camera device was detected on this machine.')
      } else {
        setCameraPermission('error')
        setErrorBanner(
          'Unable to open webcam stream. Close any other application using the camera and try again.',
        )
      }
      setMonitoringState('error')
      setFrameStatusText('Camera access failed')
      return
    }

    streamRef.current = mediaStream
    setCameraPermission('granted')
    if (videoRef.current) {
      videoRef.current.srcObject = mediaStream
      try {
        await videoElPlaySafe(videoRef.current)
      } catch {
        // AutoPlay muted handles playback cleanly; ignore transient play promise cancellation
      }
    }

    setFrameStatusText('Starting backend live monitoring session...')
    try {
      const started = await startLiveMonitoringSession({
        confidence_threshold: confidenceThreshold,
        image_size: 416,
      })

      sessionIdRef.current = started.session_id
      setLiveZones([])
      setSessionId(started.session_id)
      startedAtMsRef.current = Date.now()

      setElapsedSeconds(0)
      setFramesProcessed(0)
      setTotalDetections(0)
      setUniqueTracksCount(0)
      setEventsDiscoveredCount(0)
      setCurrentDetections([])
      if (processedFrameUrlRef.current) URL.revokeObjectURL(processedFrameUrlRef.current)
      processedFrameUrlRef.current = null
      setProcessedFrameUrl(null)
      setActiveTracks([])
      setLiveEvents([])
      setCurrentFrameTimestamp(0)
      setLatestFrameIndex(-1)

      isMonitoringRef.current = true
      setMonitoringState('active')
      setFrameStatusText('Live monitoring active')

      durationTimerRef.current = window.setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startedAtMsRef.current) / 1000))
      }, 1000)

      // Kick off first frame once video settles, then capture at configured interval
      window.setTimeout(() => {
        void captureAndSendOneFrame()
      }, 350)

      captureTimerRef.current = window.setInterval(() => {
        void captureAndSendOneFrame()
      }, captureIntervalMs)
    } catch (error) {
      releaseLocalCamera()
      setMonitoringState('error')
      setFrameStatusText('Failed to start live session')
      setErrorBanner(
        getAuthErrorMessage(error, 'Failed to initialize live monitoring session on backend.'),
      )
    }
  }

  const handleStopMonitoring = async () => {
    const activeId = sessionIdRef.current
    releaseLocalCamera()
    sessionIdRef.current = null
    setMonitoringState('stopped')
    setFrameStatusText('Monitoring stopped')

    if (activeId) {
      try {
        const finalStatus = await stopLiveMonitoringSession(activeId)
        setFramesProcessed(finalStatus.frames_processed)
        setTotalDetections(finalStatus.total_detections)
        setUniqueTracksCount(finalStatus.unique_tracks_count)
        setEventsDiscoveredCount(finalStatus.events_discovered_count)
      } catch {
        // Local hardware and loop are already cleanly torn down
      }
    }
  }

  const isMonitoringActive = monitoringState === 'active'
  const isStarting = monitoringState === 'starting'

  return (
    <div className="space-y-6">
      {/* Header & Primary Start/Stop Controls */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#7C3AED]">
                <Radio className="h-3.5 w-3.5" />
                <span>Live Webcam Intelligence</span>
              </span>

              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] font-bold uppercase ${
                  isMonitoringActive
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : monitoringState === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-700'
                      : 'border-slate-200 bg-[#F5F8FC] text-[#64748B]'
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    isMonitoringActive
                      ? 'animate-pulse bg-emerald-500'
                      : monitoringState === 'error'
                        ? 'bg-rose-500'
                        : 'bg-slate-400'
                  }`}
                />
                {monitoringState === 'active'
                  ? 'Monitoring Active'
                  : monitoringState === 'starting'
                    ? 'Starting...'
                    : monitoringState === 'stopped'
                      ? 'Stopped'
                      : monitoringState === 'error'
                        ? 'Error'
                        : 'Idle'}
              </span>

              <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 font-mono text-[11px] font-semibold text-[#111827]">
                Camera: {cameraPermission}
              </span>
            </div>

            <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827]">
              Live Webcam Monitoring
            </h2>
            <p className="mt-1 text-sm text-[#64748B]">
              Stream webcam snapshots once per second through NEMESIS-X CPU YOLO detection, isolated
              ByteTrack tracking, event discovery, and English/Kannada voice alerts.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => void handleStartMonitoring()}
              disabled={isMonitoringActive || isStarting}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-xs font-semibold text-white shadow-sm shadow-[#2563EB]/20 transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-55"
            >
              {isStarting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Starting...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  <span>Start Monitoring</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => void handleStopMonitoring()}
              disabled={!isMonitoringActive && !isStarting}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Square className="h-4 w-4" />
              <span>Stop Monitoring</span>
            </button>
          </div>
        </div>

        {/* Live Telemetry Cards */}
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
              <Clock className="h-3.5 w-3.5 text-[#2563EB]" />
              <span>Duration</span>
            </p>
            <p className="mt-1 font-mono text-xl font-extrabold text-[#111827]">
              {formatDuration(elapsedSeconds)}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
              <Activity className="h-3.5 w-3.5 text-[#7C3AED]" />
              <span>Frames Processed</span>
            </p>
            <p className="mt-1 font-mono text-xl font-extrabold text-[#111827]">
              {framesProcessed}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
              <ScanSearch className="h-3.5 w-3.5 text-[#2563EB]" />
              <span>Objects Detected</span>
            </p>
            <p className="mt-1 font-mono text-xl font-extrabold text-[#111827]">
              {currentDetections.length}{' '}
              <span className="text-xs font-semibold text-[#64748B]">({totalDetections} total)</span>
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
              <GitBranch className="h-3.5 w-3.5 text-[#7C3AED]" />
              <span>Unique Tracks</span>
            </p>
            <p className="mt-1 font-mono text-xl font-extrabold text-[#111827]">
              {uniqueTracksCount}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
              <ShieldAlert className="h-3.5 w-3.5 text-[#2563EB]" />
              <span>Events Discovered</span>
            </p>
            <p className="mt-1 font-mono text-xl font-extrabold text-[#2563EB]">
              {eventsDiscoveredCount}
            </p>
          </div>
        </div>
      </motion.section>

      {errorBanner && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorBanner}</span>
        </div>
      )}

      {/* Main Split: Live Webcam + Overlay (Left) & Config + Live Tracks (Right) */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Webcam Preview with Detection & Tracking Overlay */}
        <section className="space-y-4 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs lg:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 pb-3.5">
            <div className="flex items-center gap-2">
              <Camera className="h-4 w-4 text-[#2563EB]" />
              <h3 className="font-display text-base font-bold text-[#111827]">
                Live Camera Preview &amp; Track Overlay
              </h3>
            </div>
            <span className="rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 font-mono text-[11px] font-semibold text-[#64748B]">
              {frameStatusText}
            </span>
          </div>

          <ObjectOverlayControls
            settings={overlaySettings}
            onChange={updateOverlaySettings}
            compact
          />

          <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-950">
            {isMonitoringActive && processedFrameUrl && (
              <img
                src={processedFrameUrl}
                alt={`Analyzed live frame at ${currentFrameTimestamp?.toFixed(1) ?? 'unknown'} seconds`}
                className="absolute inset-0 h-full w-full object-contain"
              />
            )}
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className={`h-full w-full object-contain ${isMonitoringActive && !processedFrameUrl ? 'block' : 'hidden'}`}
            />

            {!isMonitoringActive && (
              <div className="flex h-full w-full flex-col items-center justify-center bg-[#F5F8FC] px-6 text-center">
                {cameraPermission === 'denied' || cameraPermission === 'unavailable' ? (
                  <CameraOff className="h-9 w-9 text-rose-500" />
                ) : (
                  <Camera className="h-9 w-9 text-[#2563EB]" />
                )}
                <p className="mt-3 text-sm font-bold text-[#111827]">
                  {cameraPermission === 'denied'
                    ? 'Webcam Permission Denied'
                    : cameraPermission === 'unavailable'
                      ? 'No Webcam Detected'
                      : 'Webcam Preview Standby'}
                </p>
                <p className="mt-1 max-w-md text-xs text-[#64748B]">
                  Click <strong>Start Monitoring</strong> to request webcam access and begin
                  live CPU detection and ByteTrack tracking.
                </p>
              </div>
            )}

            {isMonitoringActive && processedFrameUrl && overlaySize && overlaySize.width > 0 && overlaySize.height > 0 && (
              <ObjectDetectionOverlay
                detections={currentDetections}
                width={overlaySize.width}
                height={overlaySize.height}
                settings={overlaySettings}
              />
            )}

            {/* Session zone outlines are independent of detection label visibility. */}
            {isMonitoringActive && processedFrameUrl && overlaySize && overlaySize.width > 0 && overlaySize.height > 0 && (
              <svg
                viewBox={`0 0 ${overlaySize.width} ${overlaySize.height}`}
                preserveAspectRatio="xMidYMid meet"
                className="pointer-events-none absolute inset-0 h-full w-full"
                aria-hidden="true"
              >
                  {liveZones.map((zone) => (
                    <g key={`live-zone-${zone.id}`}>
                      <polygon
                        points={zone.polygon
                          .map(([x, y]) => `${x * overlaySize.width},${y * overlaySize.height}`)
                          .join(' ')}
                        fill={zone.color}
                        fillOpacity={0.14}
                        stroke={zone.color}
                        strokeWidth={Math.max(2, overlaySize.width * 0.003)}
                      />
                      <text
                        x={zone.polygon[0][0] * overlaySize.width}
                        y={zone.polygon[0][1] * overlaySize.height}
                        fill={zone.color}
                        fontSize={Math.max(12, overlaySize.width * 0.02)}
                        fontWeight="bold"
                        stroke="white"
                        strokeWidth={Math.max(2, overlaySize.width * 0.004)}
                        paintOrder="stroke"
                      >
                        {zone.name}
                      </text>
                    </g>
                  ))}
              </svg>
            )}

            {isMonitoringActive && currentFrameTimestamp !== null && (
              <div className="absolute top-3 left-3 rounded-lg bg-white/92 px-2.5 py-1 font-mono text-[11px] font-bold text-[#111827] shadow-xs">
                LIVE · t = {currentFrameTimestamp.toFixed(1)}s
              </div>
            )}
          </div>
          {sessionId && (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2">
              <p className="text-[11px] text-blue-800">
                {liveZones.length} live zone(s) configured for this session.
              </p>
              <Link
                to={`/dashboard/zones?liveSessionId=${sessionId}`}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-[11px] font-semibold text-[#2563EB] hover:underline"
              >
                Manage zones in new tab
              </Link>
            </div>
          )}

          <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

          {/* Current Frame Detections Strip */}
          <div className="space-y-2 rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
            <p className="text-xs font-bold text-[#111827]">
              Current Frame Detections ({currentDetections.length})
              {currentFrameTimestamp !== null ? ` @ ${currentFrameTimestamp.toFixed(2)}s` : ''}
            </p>
            {currentDetections.length === 0 ? (
              <p className="text-xs text-[#64748B]">
                No objects detected in the most recent analyzed frame.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {currentDetections.map((det, idx) => (
                  <span
                    key={`det-pill-${idx}`}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-mono text-[11px] font-semibold text-[#111827]"
                  >
                    {det.track_code && (
                      <span className="rounded bg-[#2563EB] px-1.5 py-0.5 text-[10px] text-white">
                        {det.track_code}
                      </span>
                    )}
                    <span className="capitalize">{det.class_name}</span>
                    <span className="text-[#7C3AED]">{Math.round(det.confidence * 100)}%</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Right: Capture Settings + Active ByteTrack Trajectories */}
        <div className="space-y-6 lg:col-span-5">
          {/* Configurable Frame Capture Parameters */}
          <section className="space-y-4 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs">
            <div className="flex items-center gap-2 border-b border-slate-200/80 pb-3">
              <Sliders className="h-4 w-4 text-[#7C3AED]" />
              <h3 className="font-display text-base font-bold text-[#111827]">
                Capture &amp; CPU Efficiency Settings
              </h3>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="live-resolution-select"
                  className="block text-xs font-semibold text-[#111827]"
                >
                  Frame Width
                </label>
                <select
                  id="live-resolution-select"
                  disabled={isMonitoringActive || isStarting}
                  value={captureMaxWidth}
                  onChange={(e) => setCaptureMaxWidth(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-semibold text-[#111827] disabled:opacity-60"
                >
                  <option value={480}>480 px (Lowest CPU)</option>
                  <option value={640}>640 px (Balanced)</option>
                  <option value={720}>720 px (High Detail)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="live-quality-select"
                  className="block text-xs font-semibold text-[#111827]"
                >
                  JPEG Quality
                </label>
                <select
                  id="live-quality-select"
                  disabled={isMonitoringActive || isStarting}
                  value={jpegQuality}
                  onChange={(e) => setJpegQuality(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-semibold text-[#111827] disabled:opacity-60"
                >
                  <option value={0.6}>60% (Smallest)</option>
                  <option value={0.75}>75% (Balanced)</option>
                  <option value={0.85}>85% (Crisp)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="live-interval-select"
                  className="block text-xs font-semibold text-[#111827]"
                >
                  Capture Interval
                </label>
                <select
                  id="live-interval-select"
                  disabled={isMonitoringActive || isStarting}
                  value={captureIntervalMs}
                  onChange={(e) => setCaptureIntervalMs(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-semibold text-[#111827] disabled:opacity-60"
                >
                  <option value={1000}>Every 1.0s (~1 FPS)</option>
                  <option value={1500}>Every 1.5s</option>
                  <option value={2000}>Every 2.0s</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="live-conf-select"
                  className="block text-xs font-semibold text-[#111827]"
                >
                  Detection Confidence
                </label>
                <select
                  id="live-conf-select"
                  disabled={isMonitoringActive || isStarting}
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                  className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-semibold text-[#111827] disabled:opacity-60"
                >
                  <option value={0.25}>High Sensitivity (0.25)</option>
                  <option value={0.4}>Balanced (0.40)</option>
                  <option value={0.55}>Low False Positives (0.55)</option>
                </select>
              </div>
            </div>
          </section>

          {/* Active ByteTrack Trajectories */}
          <section className="space-y-3 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs">
            <div className="flex items-center justify-between gap-2 border-b border-slate-200/80 pb-3">
              <div className="flex items-center gap-2">
                <Crosshair className="h-4 w-4 text-[#2563EB]" />
                <h3 className="font-display text-base font-bold text-[#111827]">
                  Session Tracks ({activeTracks.length})
                </h3>
              </div>
              <span className="font-mono text-[10px] font-semibold text-[#64748B]">
                ISOLATED BYTETRACK
              </span>
            </div>

            {activeTracks.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-slate-200 bg-[#F5F8FC] px-4 py-6 text-center text-xs text-[#64748B]">
                No persistent tracks recorded yet in this live session.
              </p>
            ) : (
              <div className="max-h-64 space-y-2.5 overflow-y-auto pr-1">
                {activeTracks.map((trk) => {
                  const isCurrentlyTracked =
                    isMonitoringActive && trk.last_seen_frame === latestFrameIndex

                  return (
                    <div
                      key={trk.track_id}
                      className="space-y-1.5 rounded-xl border border-slate-200/90 bg-[#F5F8FC] p-3 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="inline-flex items-center gap-2 font-bold text-[#111827]">
                          <span className="rounded bg-[#2563EB] px-1.5 py-0.5 font-mono text-[10px] text-white">
                            {formatTrackCode(trk)}
                          </span>
                          <span className="capitalize">{trk.class_name}</span>
                          <span
                            className={`rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase ${
                              isCurrentlyTracked
                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                : 'border-slate-200 bg-white text-[#64748B]'
                            }`}
                          >
                            {isCurrentlyTracked ? 'Active' : 'Last Seen'}
                          </span>
                        </span>
                        <span className="font-mono text-[11px] font-semibold text-[#7C3AED]">
                          {Math.round(trk.avg_confidence * 100)}% avg
                        </span>
                      </div>
                      <div className="flex items-center justify-between font-mono text-[11px] text-[#64748B]">
                        <span>
                          Last seen: {trk.last_seen_timestamp.toFixed(1)}s (Frame #
                          {trk.last_seen_frame + 1})
                        </span>
                        <span>
                          {trk.frame_count} obs · {trk.duration_seconds.toFixed(1)}s
                        </span>
                      </div>
                      <p className="font-mono text-[10px] text-[#111827]">
                        Movement: {summarizeTrackMovement(trk)}
                      </p>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Live Event Feed + Voice Alert Center */}
      <div className="grid gap-6 lg:grid-cols-12">
        <section className="space-y-4 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs lg:col-span-7">
          <div className="flex items-center justify-between gap-2 border-b border-slate-200/80 pb-3.5">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-[#2563EB]" />
              <h3 className="font-display text-base font-bold text-[#111827]">
                Live Event Feed ({liveEvents.length})
              </h3>
            </div>
            <span className="font-mono text-[11px] text-[#64748B]">
              Real discovered events only
            </span>
          </div>

          {liveEvents.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-[#F5F8FC] px-6 py-10 text-center">
              <ShieldAlert className="mx-auto h-7 w-7 text-[#64748B]" />
              <p className="mt-2.5 text-sm font-semibold text-[#111827]">
                No live events discovered yet
              </p>
              <p className="mx-auto mt-1 max-w-md text-xs text-[#64748B]">
                Events appear here in real time only when ByteTrack trajectories satisfy factual
                event discovery rules.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {liveEvents.map((evt) => {
                const priority = classifyEventPriority({
                  category: evt.category,
                  severity: evt.severity,
                  requiresHumanReview: evt.requires_human_review,
                })

                return (
                  <article
                    key={evt.id}
                    className="flex flex-col gap-3 rounded-2xl border border-slate-200/90 bg-[#F5F8FC] p-4 sm:flex-row sm:items-start sm:justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                            SEVERITY_BADGE[priority] ?? SEVERITY_BADGE.low
                          }`}
                        >
                          {priority} priority
                        </span>
                        <span className="font-mono text-[11px] font-semibold text-[#2563EB]">
                          t = {evt.timestamp_seconds.toFixed(1)}s
                        </span>
                        <span className="font-mono text-[11px] text-[#7C3AED]">
                          {Math.round(evt.confidence * 100)}% confidence
                        </span>
                      </div>

                      <h4 className="font-display text-sm font-bold text-[#111827]">{evt.title}</h4>
                      <p className="text-xs leading-relaxed text-[#64748B]">{evt.description}</p>

                      {evt.involved_track_ids.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] font-semibold text-[#111827]">
                            Related Tracks:
                          </span>
                          {evt.involved_track_ids.map((tid) => (
                            <span
                              key={tid}
                              className="rounded bg-[#2563EB]/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB]"
                            >
                              T{String(tid).padStart(3, '0')}
                            </span>
                          ))}
                        </div>
                      )}

                      {evt.why_flagged && (
                        <p className="rounded-xl border border-slate-200/80 bg-white px-3 py-2 text-[11px] leading-relaxed text-[#64748B]">
                          <strong className="text-[#111827]">Explanation:</strong> {evt.why_flagged}
                        </p>
                      )}

                      {evt.snapshot_url && (
                        <div>
                          <Link
                            to={`/dashboard/evidence?liveSessionId=${evt.session_id}`}
                            className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold text-[#2563EB] hover:underline"
                          >
                            <span>Evidence Ref: {evt.id.slice(0, 8)} · Open in Evidence Center</span>
                          </Link>
                        </div>
                      )}
                    </div>

                    {evt.snapshot_url && (
                      <LiveSnapshotThumbnail
                        sessionId={evt.session_id}
                        eventId={evt.id}
                        title={evt.title}
                      />
                    )}
                  </article>
                )
              })}
            </div>
          )}
        </section>

        <div className="lg:col-span-5">
          <VoiceAlertCenter currentAnalysisId={sessionId ?? undefined} />
        </div>
      </div>
    </div>
  )
}

async function videoElPlaySafe(videoEl: HTMLVideoElement): Promise<void> {
  if (typeof videoEl.play === 'function') {
    await videoEl.play()
  }
}
