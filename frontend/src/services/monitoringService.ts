import { apiClient } from './api.ts'

export type MonitoringSessionType = 'recorded' | 'live'

export interface MonitoringHistoryItem {
  session_id: string
  session_type: MonitoringSessionType
  name: string
  video_id: string | null
  start_time: string | null
  end_time: string | null
  duration_seconds: number
  status: string
  total_detected_objects: number
  unique_tracked_objects: number
  events_discovered: number
  high_priority_events: number
  created_at: string
}

export interface MonitoringHistoryResponse {
  items: MonitoringHistoryItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface MonitoringHistoryFilterParams {
  session_type?: string
  status?: string
  priority?: string
  search?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface ObjectClassCount {
  class_name: string
  count: number
}

export interface TimelineTrendPoint {
  date: string
  sessions_count: number
  events_count: number
  high_priority_count: number
}

export interface IntelligenceAnalyticsResponse {
  total_sessions: number
  recorded_sessions_count: number
  live_sessions_count: number
  total_duration_seconds: number
  total_frames_processed: number
  total_detections: number
  total_unique_tracks: number
  total_events: number
  high_priority_events: number
  medium_priority_events: number
  low_priority_events: number
  events_by_category: Record<string, number>
  events_by_severity: Record<string, number>
  top_object_classes: ObjectClassCount[]
  timeline_trends: TimelineTrendPoint[]
  session_status_breakdown: Record<string, number>
}

export interface SessionEventDetail {
  id: string
  event_type: string
  category: string
  title: string
  description: string
  start_timestamp: number
  end_timestamp: number
  involved_track_ids: number[]
  confidence: number
  severity: string
  why_flagged: string
  observed_sequence: string[]
  requires_human_review: boolean
  evidence_image_urls: string[]
  created_at: string
}

export interface SessionEvidenceDetail {
  id: string
  event_id: string | null
  frame_number: number
  timestamp_seconds: number
  evidence_type: string
  image_url: string
  description: string
  why_flagged: string
  involved_track_ids: number[]
  created_at: string
}

export interface UnifiedSessionDetailResponse {
  session_id: string
  session_type: MonitoringSessionType
  name: string
  video_id: string | null
  status: string
  started_at: string | null
  end_time: string | null
  duration_seconds: number
  frames_processed: number
  total_frames: number
  frame_width: number | null
  frame_height: number | null
  confidence_threshold: number
  detection_stats: {
    total_detections?: number
    class_counts?: Record<string, number>
    [key: string]: unknown
  }
  track_stats: {
    total_tracks?: number
    classes?: Record<string, number>
    tracks?: Array<{
      track_id: number
      class_name: string
      duration_seconds: number
      frame_count: number
      avg_confidence: number
      first_seen_timestamp: number
      last_seen_timestamp: number
    }>
    [key: string]: unknown
  }
  events: SessionEventDetail[]
  evidence_count: number
  evidence_items: SessionEvidenceDetail[]
  pdf_report_url: string
  ai_explanation_summary: {
    total_events?: number
    review_recommended_count?: number
    high_priority_count?: number
    most_common_category?: string
    model_architecture?: string
    [key: string]: unknown
  }
}

export async function fetchMonitoringHistory(
  params: MonitoringHistoryFilterParams = {},
): Promise<MonitoringHistoryResponse> {
  const query = new URLSearchParams()
  if (params.session_type && params.session_type !== 'all') {
    query.set('session_type', params.session_type)
  }
  if (params.status && params.status !== 'all') {
    query.set('status', params.status)
  }
  if (params.priority && params.priority !== 'all') {
    query.set('priority', params.priority)
  }
  if (params.search && params.search.trim()) {
    query.set('search', params.search.trim())
  }
  if (params.date_from) {
    query.set('date_from', params.date_from)
  }
  if (params.date_to) {
    query.set('date_to', params.date_to)
  }
  if (params.page && params.page > 0) {
    query.set('page', String(params.page))
  }
  if (params.page_size && params.page_size > 0) {
    query.set('page_size', String(params.page_size))
  }

  const queryString = query.toString()
  const endpoint = queryString ? `/monitoring/history?${queryString}` : '/monitoring/history'
  const response = await apiClient.get<MonitoringHistoryResponse>(endpoint)
  return response.data
}

export async function fetchIntelligenceAnalytics(
  dateFrom?: string,
  dateTo?: string,
): Promise<IntelligenceAnalyticsResponse> {
  const query = new URLSearchParams()
  if (dateFrom) query.set('date_from', dateFrom)
  if (dateTo) query.set('date_to', dateTo)

  const queryString = query.toString()
  const endpoint = queryString ? `/monitoring/analytics?${queryString}` : '/monitoring/analytics'
  const response = await apiClient.get<IntelligenceAnalyticsResponse>(endpoint)
  return response.data
}

export async function fetchUnifiedSessionDetails(
  sessionId: string,
  sessionType?: string,
): Promise<UnifiedSessionDetailResponse> {
  const url = sessionType
    ? `/monitoring/sessions/${sessionId}?session_type=${sessionType}`
    : `/monitoring/sessions/${sessionId}`
  const response = await apiClient.get<UnifiedSessionDetailResponse>(url)
  return response.data
}

export async function downloadSessionPdfReport(pdfUrl: string, fileName?: string): Promise<void> {
  // Normalize the URL if it already starts with api_prefix or relative path
  const normalizedUrl = pdfUrl.startsWith('http')
    ? pdfUrl
    : pdfUrl.replace(/^\/api\/v1/, '')

  const response = await apiClient.get<Blob>(normalizedUrl, {
    responseType: 'blob',
    timeout: 30000,
  })

  const blobUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = fileName || 'nemesis-x-session-report.pdf'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}
