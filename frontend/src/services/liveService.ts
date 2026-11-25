import type {
  AnalysisEvidenceListResponse,
  BoundingBoxInfo,
  TrackSummaryInfo,
} from './analysisService.ts'
import { apiClient } from './api.ts'

export type LiveSessionStatus = 'active' | 'stopped' | 'error'

export interface LiveSessionStartPayload {
  confidence_threshold: number
  image_size: number
}

export interface LiveSessionStartResponse {
  session_id: string
  status: LiveSessionStatus
  confidence_threshold: number
  image_size: number
  started_at: string
}

export interface LiveDetectionInfo {
  track_id?: number | null
  track_code?: string | null
  identity_code?: string | null
  class_id: number
  class_name: string
  confidence: number
  bbox: BoundingBoxInfo
}

export interface LiveEventInfo {
  id: string
  session_id: string
  event_type: string
  category: string
  title: string
  description: string
  timestamp_seconds: number
  start_timestamp: number
  end_timestamp: number
  involved_track_ids: number[]
  confidence: number
  severity: string
  frame_index: number
  requires_human_review: boolean
  alerts_enabled: boolean
  voice_alerts_enabled: boolean
  zone_id?: string | null
  zone_name?: string | null
  why_flagged: string
  observed_sequence: string[]
  snapshot_url: string | null
  created_at: string
}

export interface LiveFrameProcessResponse {
  session_id: string
  status: LiveSessionStatus
  frame_index: number
  timestamp_seconds: number
  frame_width: number
  frame_height: number
  frames_processed: number
  total_detections: number
  unique_tracks_count: number
  events_discovered_count: number
  processing_ms: number
  detections: LiveDetectionInfo[]
  active_tracks: TrackSummaryInfo[]
  new_events: LiveEventInfo[]
}

export interface LiveSessionStatusResponse {
  session_id: string
  status: LiveSessionStatus
  confidence_threshold: number
  image_size: number
  frames_processed: number
  total_detections: number
  unique_tracks_count: number
  events_discovered_count: number
  duration_seconds: number
  frame_width?: number | null
  frame_height?: number | null
  started_at: string
  last_frame_at?: string | null
  stopped_at?: string | null
  active_tracks: TrackSummaryInfo[]
  events: LiveEventInfo[]
}

export async function startLiveMonitoringSession(
  payload: LiveSessionStartPayload,
): Promise<LiveSessionStartResponse> {
  const response = await apiClient.post<LiveSessionStartResponse>('/live/start', payload)
  return response.data
}

export async function sendLiveFrame(params: {
  sessionId: string
  frameBlob: Blob
  timestampSeconds: number
  signal?: AbortSignal
  timeoutMs?: number
}): Promise<LiveFrameProcessResponse> {
  const formData = new FormData()
  formData.append('file', params.frameBlob, 'live_frame.jpg')
  formData.append('timestamp_seconds', String(params.timestampSeconds))

  const response = await apiClient.post<LiveFrameProcessResponse>(
    `/live/${params.sessionId}/frame`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: params.timeoutMs ?? 8000,
      signal: params.signal,
    },
  )
  return response.data
}

export async function stopLiveMonitoringSession(
  sessionId: string,
): Promise<LiveSessionStatusResponse> {
  const response = await apiClient.post<LiveSessionStatusResponse>(`/live/${sessionId}/stop`)
  return response.data
}

export async function getLiveMonitoringStatus(
  sessionId: string,
): Promise<LiveSessionStatusResponse> {
  const response = await apiClient.get<LiveSessionStatusResponse>(`/live/${sessionId}/status`)
  return response.data
}

export async function listLiveMonitoringSessions(): Promise<LiveSessionStatusResponse[]> {
  const response = await apiClient.get<LiveSessionStatusResponse[]>('/live/sessions')
  return response.data
}

export async function getLiveSessionEvidence(
  sessionId: string,
): Promise<AnalysisEvidenceListResponse> {
  const response = await apiClient.get<AnalysisEvidenceListResponse>(`/live/${sessionId}/evidence`)
  return response.data
}

export async function downloadLiveSessionPdfReport(sessionId: string): Promise<void> {
  const response = await apiClient.get<Blob>(`/reports/live/${sessionId}/pdf`, {
    responseType: 'blob',
    timeout: 30000,
  })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `nemesis-x-live-report-${sessionId.slice(0, 8)}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export async function fetchLiveEventSnapshotBlobUrl(
  sessionId: string,
  eventId: string,
): Promise<string> {
  const response = await apiClient.get<Blob>(
    `/live/${sessionId}/events/${eventId}/snapshot`,
    {
      responseType: 'blob',
    },
  )
  return URL.createObjectURL(response.data)
}
