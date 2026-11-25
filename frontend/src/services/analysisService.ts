import { apiClient } from './api'

export type AnalysisStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface AnalysisStartResponse {
  analysis_id: string
  video_id: string
  status: AnalysisStatus
}

export interface AnalysisStatusResponse {
  analysis_id: string
  video_id: string
  status: AnalysisStatus
  progress: number
  total_frames: number
  processed_frames: number
  sampling_interval: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface BoundingBoxInfo {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface DetectedObjectInfo {
  track_id?: number | null
  class_id: number
  class_name: string
  confidence: number
  bbox: BoundingBoxInfo
}

export interface ExtractedFrameInfo {
  frame_index: number
  source_frame_index: number
  timestamp_seconds: number
  filename: string
  url: string
  frame_width?: number | null
  frame_height?: number | null
  detections: DetectedObjectInfo[]
}

export interface TrackTimelinePointInfo {
  frame_index: number
  timestamp_seconds: number
  center_x: number
  center_y: number
  confidence: number
  bbox: BoundingBoxInfo
}

export interface TrackSummaryInfo {
  track_id: number
  class_id: number
  class_name: string
  first_seen_frame: number
  last_seen_frame: number
  first_seen_timestamp: number
  last_seen_timestamp: number
  duration_seconds: number
  frame_count: number
  avg_confidence: number
  max_confidence: number
  timeline_points: TrackTimelinePointInfo[]
}

export interface AnalysisSummary {
  duration_seconds?: number | null
  original_dimensions?: { width: number; height: number } | null
  fps?: number
  total_frames?: number
  sampling_interval?: number
  max_width_applied?: number
  extracted_count?: number
}

export interface DetectionsSummary {
  model_name?: string | null
  tracker_name?: string | null
  device?: string
  image_size?: number
  confidence_threshold?: number
  total_detections?: number
  frames_with_detections?: number
  class_counts?: Record<string, number>
}

export interface TracksSummary {
  model_name?: string | null
  tracker_name?: string
  total_tracks?: number
  tracks_by_class?: Record<string, number>
}

export interface AnalysisResultsResponse {
  analysis_id: string
  video_id: string
  status: AnalysisStatus
  progress: number
  sampling_interval: number
  error_message: string | null
  summary: AnalysisSummary
  detections_summary: DetectionsSummary
  tracks_summary: TracksSummary
  tracks: TrackSummaryInfo[]
  frames: ExtractedFrameInfo[]
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface AnalysisTracksResponse {
  analysis_id: string
  video_id: string
  status: AnalysisStatus
  summary: TracksSummary
  tracks: TrackSummaryInfo[]
}

export async function startVideoAnalysis(
  videoId: string,
  targetFps = 1.0,
  confidenceThreshold = 0.4,
): Promise<AnalysisStartResponse> {
  const response = await apiClient.post<AnalysisStartResponse>(`/analysis/${videoId}/start`, {
    target_fps: targetFps,
    confidence_threshold: confidenceThreshold,
  })
  return response.data
}

export async function getAnalysisStatus(analysisId: string): Promise<AnalysisStatusResponse> {
  const response = await apiClient.get<AnalysisStatusResponse>(`/analysis/${analysisId}/status`)
  return response.data
}

export async function getAnalysisResults(analysisId: string): Promise<AnalysisResultsResponse> {
  const response = await apiClient.get<AnalysisResultsResponse>(`/analysis/${analysisId}/results`)
  return response.data
}

export async function getAnalysisTracks(analysisId: string): Promise<AnalysisTracksResponse> {
  const response = await apiClient.get<AnalysisTracksResponse>(`/analysis/${analysisId}/tracks`)
  return response.data
}

export async function fetchExtractedFrameBlobUrl(
  analysisId: string,
  filename: string,
): Promise<string> {
  const response = await apiClient.get<Blob>(`/analysis/${analysisId}/frames/${filename}`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(response.data)
}
