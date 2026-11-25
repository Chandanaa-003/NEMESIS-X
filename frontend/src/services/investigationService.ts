import { API_BASE_URL, apiClient } from './api.ts'

export type InvestigationStatus = 'open' | 'reviewing' | 'closed'
export type InvestigationSourceType = 'analysis' | 'live_session'

export interface InvestigationSummary {
  id: string
  title: string
  description: string
  status: InvestigationStatus
  created_at: string
  updated_at: string
  source_count: number
  event_count: number
  track_count: number
  note_count: number
}

export interface InvestigationSource {
  id: string
  source_type: InvestigationSourceType
  source_id: string
  source_label: string
  analysis_id: string | null
  video_id: string | null
  live_session_id: string | null
  status: string
  created_at: string
  data_availability: string
  track_count: number
  event_count: number
}

export interface InvestigationEventLink {
  id: string
  source_id: string
  event_id: string | null
  live_event_id: string | null
  event_type: string
  event_category: string
  title: string
  timestamp_seconds: number
  track_ids: number[]
  track_labels: string[]
  confidence: number
  severity: string
  created_at: string
}

export interface InvestigationTrack {
  id: string
  source_id: string
  track_id: number
  track_label: string
  entity_label: string
  class_name: string
  first_seen_timestamp: number
  last_seen_timestamp: number
  detection_count: number
  linked: boolean
}

export interface InvestigationNote {
  id: string
  investigation_id: string
  source_id: string | null
  investigation_event_id: string | null
  timestamp_seconds: number | null
  content: string
  author_user_id: number
  source: 'user'
  created_at: string
  updated_at: string
}

export interface InvestigationDetail extends InvestigationSummary {
  sources: InvestigationSource[]
  linked_events: InvestigationEventLink[]
  linked_tracks: InvestigationTrack[]
  notes: InvestigationNote[]
}

export interface InvestigationTimelineItem {
  id: string
  record_type: 'event' | 'detection' | 'track_observation' | 'behavior_sequence' | 'anomaly'
  source_id: string
  source_type: InvestigationSourceType
  source_label: string
  event_id: string | null
  event_type: string
  event_category: string
  title: string
  explanation: string
  timestamp_seconds: number
  created_at: string | null
  track_ids: number[]
  track_labels: string[]
  confidence: number | null
  severity: string | null
  evidence: Array<{
    id: string
    timestamp_seconds: number
    evidence_type: string
    image_url: string
  }>
  linked: boolean
}

export interface InvestigationTimeline {
  items: InvestigationTimelineItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface InvestigationGraphNode {
  id: string
  node_type: 'person' | 'object' | 'unknown_track' | 'event'
  label: string
  source_id: string
  source_label: string
  timestamp_seconds: number | null
  details: Record<string, unknown>
}

export interface InvestigationGraphEdge {
  id: string
  source: string
  target: string
  label: string
  timestamp_seconds: number
  confidence: number | null
  uncertainty: string | null
  event_id: string
}

export interface InvestigationGraph {
  nodes: InvestigationGraphNode[]
  edges: InvestigationGraphEdge[]
}

export interface InvestigationEvidenceItem {
  id: string
  source_id: string
  event_id: string
  event_title: string
  timestamp_seconds: number
  frame_number: number
  evidence_type: string
  image_url: string | null
  original_image_url: string | null
  annotated_image_url: string | null
  explanation: string
  confidence: number | null
  track_ids: number[]
  track_labels: string[]
}

export interface InvestigationTrackDetail {
  source_id: string
  source_label: string
  track_id?: number
  track_label?: string
  entity_label?: string
  class_name?: string
  first_seen_timestamp?: number
  last_seen_timestamp?: number
  detection_count?: number
  history_availability?: string
  temporary_id_notice?: string
  track?: {
    class_name: string
    first_seen_timestamp: number
    last_seen_timestamp: number
    frame_count: number
    timeline_points: Array<{
      frame_index: number
      timestamp_seconds: number
      center_x: number
      center_y: number
      confidence: number
    }>
  }
  frames?: Array<{
    frame_index: number
    timestamp_seconds: number
    filename: string
    frame_url: string
    frame_available: boolean
    selected_detection: { confidence: number }
  }>
  detection_history?: Array<{
    frame_index: number
    timestamp_seconds: number
    center_x: number
    center_y: number
    confidence: number
  }>
  movement_history?: unknown
  related_events?: Array<{
    id: string
    event_type: string
    title?: string
    description?: string
    start_timestamp?: number
    timestamp_seconds?: number
    confidence: number
    severity: string
    snapshot_url?: string | null
  }>
}

export interface InvestigationFilters {
  event_category?: string
  source_id?: string
  track_id?: number
  severity?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export async function listInvestigations(): Promise<InvestigationSummary[]> {
  const response = await apiClient.get<InvestigationSummary[]>('/investigations')
  return response.data
}

export async function createInvestigation(payload: {
  title: string
  description: string
}): Promise<InvestigationDetail> {
  const response = await apiClient.post<InvestigationDetail>('/investigations', payload)
  return response.data
}

export async function getInvestigation(id: string): Promise<InvestigationDetail> {
  const response = await apiClient.get<InvestigationDetail>(`/investigations/${id}`)
  return response.data
}

export async function updateInvestigation(
  id: string,
  payload: Partial<Pick<InvestigationSummary, 'title' | 'description' | 'status'>>,
): Promise<InvestigationDetail> {
  const response = await apiClient.patch<InvestigationDetail>(`/investigations/${id}`, payload)
  return response.data
}

export async function deleteInvestigation(id: string): Promise<void> {
  await apiClient.delete(`/investigations/${id}`)
}

export async function addInvestigationSource(
  investigationId: string,
  payload: { analysis_id: string } | { live_session_id: string },
): Promise<InvestigationSource> {
  const response = await apiClient.post<InvestigationSource>(
    `/investigations/${investigationId}/sources`,
    payload,
  )
  return response.data
}

export async function removeInvestigationSource(
  investigationId: string,
  sourceId: string,
): Promise<void> {
  await apiClient.delete(`/investigations/${investigationId}/sources/${sourceId}`)
}

export async function searchInvestigationTracks(
  investigationId: string,
  params: { q?: string; entity?: 'person' | 'object'; source_id?: string; limit?: number } = {},
): Promise<InvestigationTrack[]> {
  const response = await apiClient.get<InvestigationTrack[]>(
    `/investigations/${investigationId}/tracks`,
    { params },
  )
  return response.data
}

export async function linkInvestigationTrack(
  investigationId: string,
  payload: { source_id: string; track_id: number },
): Promise<InvestigationTrack> {
  const response = await apiClient.post<InvestigationTrack>(
    `/investigations/${investigationId}/tracks`,
    payload,
  )
  return response.data
}

export async function unlinkInvestigationTrack(
  investigationId: string,
  linkId: string,
): Promise<void> {
  await apiClient.delete(`/investigations/${investigationId}/tracks/${linkId}`)
}

export async function getInvestigationTrackDetail(
  investigationId: string,
  sourceId: string,
  trackId: number,
): Promise<InvestigationTrackDetail> {
  const response = await apiClient.get<InvestigationTrackDetail>(
    `/investigations/${investigationId}/tracks/${sourceId}/${trackId}`,
  )
  return response.data
}

export async function linkInvestigationEvent(
  investigationId: string,
  payload: { source_id: string; event_id: string } | { source_id: string; live_event_id: string },
): Promise<InvestigationEventLink> {
  const response = await apiClient.post<InvestigationEventLink>(
    `/investigations/${investigationId}/events`,
    payload,
  )
  return response.data
}

export async function unlinkInvestigationEvent(
  investigationId: string,
  linkId: string,
): Promise<void> {
  await apiClient.delete(`/investigations/${investigationId}/events/${linkId}`)
}

export async function getInvestigationTimeline(
  investigationId: string,
  filters: InvestigationFilters = {},
): Promise<InvestigationTimeline> {
  const response = await apiClient.get<InvestigationTimeline>(
    `/investigations/${investigationId}/timeline`,
    { params: filters },
  )
  return response.data
}

export async function getInvestigationGraph(id: string): Promise<InvestigationGraph> {
  const response = await apiClient.get<InvestigationGraph>(`/investigations/${id}/graph`)
  return response.data
}

export async function getInvestigationEvidence(
  investigationId: string,
  params: { source_id?: string; event_link_id?: string; event_id?: string } = {},
): Promise<InvestigationEvidenceItem[]> {
  const response = await apiClient.get<InvestigationEvidenceItem[]>(
    `/investigations/${investigationId}/evidence`,
    { params },
  )
  return response.data
}

export async function addInvestigationNote(
  investigationId: string,
  payload: {
    content: string
    source_id?: string | null
    investigation_event_id?: string | null
    timestamp_seconds?: number | null
  },
): Promise<InvestigationNote> {
  const response = await apiClient.post<InvestigationNote>(
    `/investigations/${investigationId}/notes`,
    payload,
  )
  return response.data
}

export async function updateInvestigationNote(
  investigationId: string,
  noteId: string,
  payload: {
    content: string
    source_id?: string | null
    investigation_event_id?: string | null
    timestamp_seconds?: number | null
  },
): Promise<InvestigationNote> {
  const response = await apiClient.patch<InvestigationNote>(
    `/investigations/${investigationId}/notes/${noteId}`,
    payload,
  )
  return response.data
}

export async function deleteInvestigationNote(
  investigationId: string,
  noteId: string,
): Promise<void> {
  await apiClient.delete(`/investigations/${investigationId}/notes/${noteId}`)
}

export async function fetchInvestigationImageBlobUrl(imagePath: string): Promise<string> {
  const base = new URL(API_BASE_URL, window.location.origin)
  const image = new URL(imagePath, base.origin)
  if (image.origin !== base.origin) {
    throw new Error('Evidence image must be served by the NEMESIS-X API.')
  }
  const basePath = base.pathname.replace(/\/$/, '')
  const path = image.pathname.startsWith(`${basePath}/`)
    ? image.pathname.slice(basePath.length)
    : image.pathname
  const response = await apiClient.get<Blob>(path, { responseType: 'blob' })
  return URL.createObjectURL(response.data)
}
