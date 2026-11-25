import { apiClient } from './api'

export type SearchSourceType = 'analysis' | 'live_session'
export type SearchResultType = 'event' | 'detection' | 'track'

export interface SearchEvidenceReference {
  id: string
  evidence_type: string
  timestamp_seconds: number
  image_url: string
}

export interface SearchDetectionInfo {
  track_id: number | null
  track_code: string | null
  class_name: string
  confidence: number
  bbox: { x1: number; y1: number; x2: number; y2: number }
}

export interface IntelligenceSearchResult {
  id: string
  result_type: SearchResultType
  source_type: SearchSourceType
  source_id: string
  source_label: string
  analysis_id: string | null
  video_id: string | null
  live_session_id: string | null
  event_id: string | null
  event_type: string
  event_category: string
  title: string
  explanation: string
  timestamp_seconds: number
  end_timestamp_seconds: number | null
  overlay_timestamp_seconds: number | null
  track_ids: number[]
  track_labels: string[]
  class_name: string | null
  detection_count: number | null
  confidence: number | null
  severity: string | null
  frame_width: number | null
  frame_height: number | null
  detections: SearchDetectionInfo[]
  evidence: SearchEvidenceReference[]
}

export interface IntelligenceSearchResponse {
  query: string
  supported_query: boolean
  message: string
  total: number
  limit: number
  offset: number
  has_more: boolean
  truncated: boolean
  results: IntelligenceSearchResult[]
}

export interface IntelligenceSearchFilters {
  q: string
  source_type: 'all' | SearchSourceType
  class_name?: string
  event_type?: string
  event_category?: string
  track_id?: number
  start_seconds?: number
  end_seconds?: number
  limit: number
  offset: number
}

export async function searchVideoIntelligence(
  filters: IntelligenceSearchFilters,
): Promise<IntelligenceSearchResponse> {
  const response = await apiClient.get<IntelligenceSearchResponse>('/search/intelligence', {
    params: filters,
  })
  return response.data
}

export async function fetchSearchEvidenceBlobUrl(imageUrl: string): Promise<string> {
  const response = await apiClient.get<Blob>(imageUrl.replace(/^\/+/, ''), {
    responseType: 'blob',
  })
  return URL.createObjectURL(response.data)
}
