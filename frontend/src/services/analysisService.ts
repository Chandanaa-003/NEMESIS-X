import { apiClient } from './api.ts'

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
  extracted_frames: number
  sampling_interval: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface AnalysisListItem {
  analysis_id: string
  video_id: string
  video_filename: string
  status: AnalysisStatus
  progress: number
  extracted_frames: number
  total_frames: number
  created_at: string
  completed_at: string | null
}

export interface BoundingBoxInfo {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface DetectedObjectInfo {
  track_id?: number | null
  track_code?: string | null
  identity_id?: string | null
  identity_code?: string | null
  identity_status?: 'confirmed' | 'probable' | 'unknown' | null
  identity_confidence?: number | null
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

export interface TrackPositionSnapshot {
  frame_index: number
  timestamp_seconds: number
  center_x: number
  center_y: number
  norm_x?: number | null
  norm_y?: number | null
  bbox: BoundingBoxInfo
}

export interface TrackSummaryInfo {
  track_id: number
  track_code?: string | null
  identity_id?: string | null
  identity_code?: string | null
  identity_status?: 'confirmed' | 'probable' | 'unknown' | null
  identity_confidence?: number | null
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
  last_known_position?: TrackPositionSnapshot | null
  timeline_points: TrackTimelinePointInfo[]
}

export interface TrackMovementStep {
  from_frame_index: number
  to_frame_index: number
  from_timestamp: number
  to_timestamp: number
  from_center_x: number
  from_center_y: number
  to_center_x: number
  to_center_y: number
  delta_x: number
  delta_y: number
  displacement_px: number
  displacement_norm?: number | null
  direction: string
}

export interface TrackMovementHistory {
  total_path_distance_px: number
  net_displacement_px: number
  net_displacement_norm?: number | null
  dominant_direction: string
  steps: TrackMovementStep[]
}

export interface TrackRelatedEventInfo {
  id: string
  event_type: string
  category: string
  title: string
  description: string
  start_timestamp: number
  end_timestamp: number
  severity: string
  confidence: number
  involved_track_ids: number[]
}

export interface TrackObservationFrameInfo {
  frame_index: number
  source_frame_index: number
  timestamp_seconds: number
  filename: string
  frame_url: string
  frame_available: boolean
  frame_width?: number | null
  frame_height?: number | null
  selected_detection: DetectedObjectInfo
  center_x: number
  center_y: number
  position_delta_x: number
  position_delta_y: number
  other_detections: DetectedObjectInfo[]
}

export interface TrackDetailResponse {
  analysis_id: string
  video_id: string
  track_code: string
  temporary_id_notice: string
  frame_width?: number | null
  frame_height?: number | null
  track: TrackSummaryInfo
  last_known_position?: TrackPositionSnapshot | null
  movement_history: TrackMovementHistory
  related_events: TrackRelatedEventInfo[]
  frames: TrackObservationFrameInfo[]
}

export interface TrackFramesResponse {
  analysis_id: string
  video_id: string
  track_id: number
  track_code: string
  class_name: string
  total_observations: number
  frames: TrackObservationFrameInfo[]
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

export type EventSeverity = 'low' | 'medium' | 'high'
export type EventCategory =
  | 'people_movement'
  | 'object_interactions'
  | 'possible_unattended_objects'
  | 'other_activities'

export interface EventEvidenceFrame {
  frame_index: number
  timestamp_seconds: number
  filename: string
  url: string
}

export interface EventExplanation {
  observed_sequence: string[]
  why_flagged: string
  evidence_timestamps: number[]
  confidence_note: string
  requires_human_review: boolean
  person_track_id?: number | null
  object_track_id?: number | null
  association_uncertainty?: string | null
  zone_id?: string | null
  zone_name?: string | null
  zone_type?: string | null
  duration_seconds?: number | null
  alerts_enabled?: boolean
  voice_alerts_enabled?: boolean
  anomaly_score?: {
    duration_score?: number
    movement_change_score?: number
    interaction_sequence_score?: number
    track_association_confidence?: number
    repeated_behavior_score?: number
    zone_rule_score?: number
    total_score?: number
    explanation?: string
  } | null
}

export interface EventRecordInfo {
  id: string
  analysis_id: string
  event_type: string
  category: EventCategory
  title: string
  description: string
  start_timestamp: number
  end_timestamp: number
  involved_track_ids: number[]
  confidence: number
  severity: EventSeverity
  evidence_frame_ids: number[]
  evidence_frames: EventEvidenceFrame[]
  explanation: EventExplanation
  created_at: string
}

export interface ImportantTimestampInfo {
  timestamp_seconds: number
  event_title: string
  severity: EventSeverity
}

export interface EventSummaryInfo {
  total_detected_objects: number
  total_unique_tracks: number
  total_discovered_events: number
  most_common_categories: Record<string, number>
  important_timestamps: ImportantTimestampInfo[]
  events_requiring_review: number
  summary_message: string
}

export interface EventDiscoveryResponse {
  analysis_id: string
  video_id: string
  summary: EventSummaryInfo
  events: EventRecordInfo[]
}

export type EvidenceType = 'original_frame' | 'annotated_detection' | 'annotated_tracking'

export interface EvidenceItemInfo {
  id: string
  event_id: string
  analysis_id: string
  frame_number: number
  timestamp_seconds: number
  evidence_type: EvidenceType
  image_url: string
  description: string
  event_title: string
  event_category: string
  event_severity: string
  event_confidence: number
  why_flagged: string
  involved_track_ids: number[]
  detection_count: number
  detection_summary: string[]
  created_at: string
}

export interface AnalysisEvidenceListResponse {
  analysis_id: string
  total_evidence: number
  evidence: EvidenceItemInfo[]
}

export async function listUserAnalyses(): Promise<AnalysisListItem[]> {
  const response = await apiClient.get<AnalysisListItem[]>('/analysis')
  return response.data
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

export async function getAnalysisTrackDetail(
  analysisId: string,
  trackId: number,
): Promise<TrackDetailResponse> {
  const response = await apiClient.get<TrackDetailResponse>(
    `/analysis/${analysisId}/tracks/${trackId}`,
  )
  return response.data
}

export async function getAnalysisTrackFrames(
  analysisId: string,
  trackId: number,
): Promise<TrackFramesResponse> {
  const response = await apiClient.get<TrackFramesResponse>(
    `/analysis/${analysisId}/tracks/${trackId}/frames`,
  )
  return response.data
}

export async function discoverAnalysisEvents(
  analysisId: string,
): Promise<EventDiscoveryResponse> {
  const response = await apiClient.post<EventDiscoveryResponse>(
    `/analysis/${analysisId}/discover-events`,
  )
  return response.data
}

export async function getAnalysisEvents(analysisId: string): Promise<EventDiscoveryResponse> {
  const response = await apiClient.get<EventDiscoveryResponse>(`/analysis/${analysisId}/events`)
  return response.data
}

export async function getAnalysisEventDetail(
  analysisId: string,
  eventId: string,
): Promise<EventRecordInfo> {
  const response = await apiClient.get<EventRecordInfo>(
    `/analysis/${analysisId}/events/${eventId}`,
  )
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

export async function getAnalysisEvidence(
  analysisId: string,
): Promise<AnalysisEvidenceListResponse> {
  const response = await apiClient.get<AnalysisEvidenceListResponse>(
    `/analysis/${analysisId}/evidence`,
  )
  return response.data
}

export async function getEventEvidence(eventId: string): Promise<AnalysisEvidenceListResponse> {
  const response = await apiClient.get<AnalysisEvidenceListResponse>(
    `/events/${eventId}/evidence`,
  )
  return response.data
}

export async function fetchEvidenceImageBlobUrl(evidenceId: string): Promise<string> {
  const response = await apiClient.get<Blob>(`/evidence/${evidenceId}/image`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(response.data)
}

export async function downloadAnalysisPdfReport(analysisId: string): Promise<void> {
  const response = await apiClient.get<Blob>(`/reports/${analysisId}/pdf`, {
    responseType: 'blob',
  })
  const blobUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = `nemesis-x-report-${analysisId.slice(0, 8)}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}
