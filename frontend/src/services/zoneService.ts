import { apiClient } from './api'

export type ZoneType = 'restricted' | 'safe' | 'monitoring' | 'entry' | 'exit'

export interface ZoneSettings {
  confirmation_frames: number
  cooldown_seconds: number
  loiter_seconds: number
  restricted_group_threshold: number
  alerts_enabled: boolean
  voice_alerts_enabled: boolean
}

export interface ZoneRecord {
  id: string
  user_id: number
  video_id: string | null
  live_session_id: string | null
  name: string
  zone_type: ZoneType
  color: string
  polygon: number[][]
  settings: ZoneSettings
  created_at: string
  updated_at: string
}

export interface ZonePayload {
  video_id?: string
  live_session_id?: string
  name: string
  zone_type: ZoneType
  color: string
  polygon: number[][]
  settings: ZoneSettings
}

export interface ZoneEventRecord {
  id: string
  source_id: string
  event_type: string
  zone_id: string
  zone_name: string
  zone_type: ZoneType
  start_timestamp: number
  end_timestamp: number
  duration_seconds: number
  involved_track_ids: number[]
  confidence: number
  severity: string
  description: string
  evidence_frame_ids: number[]
  evidence_reference: string | null
  voice_alerts_enabled: boolean
  created_at: string
}

export interface ZoneActivitySummary {
  source_id: string
  total_events: number
  events_by_type: Record<string, number>
  zones: Array<{
    zone_id: string
    zone_name: string
    event_count: number
    people_tracks: number[]
    last_event_timestamp: number
  }>
}

export const DEFAULT_ZONE_SETTINGS: ZoneSettings = {
  confirmation_frames: 2,
  cooldown_seconds: 10,
  loiter_seconds: 30,
  restricted_group_threshold: 2,
  alerts_enabled: true,
  voice_alerts_enabled: true,
}

export async function listZones(scope: {
  videoId?: string
  liveSessionId?: string
}): Promise<ZoneRecord[]> {
  const response = await apiClient.get<ZoneRecord[]>('/zones', {
    params: {
      ...(scope.videoId ? { video_id: scope.videoId } : {}),
      ...(scope.liveSessionId ? { live_session_id: scope.liveSessionId } : {}),
    },
  })
  return response.data
}

export async function createZone(payload: ZonePayload): Promise<ZoneRecord> {
  const response = await apiClient.post<ZoneRecord>('/zones', payload)
  return response.data
}

export async function updateZone(
  zoneId: string,
  payload: Partial<ZonePayload>,
): Promise<ZoneRecord> {
  const response = await apiClient.patch<ZoneRecord>(`/zones/${zoneId}`, payload)
  return response.data
}

export async function deleteZone(zoneId: string): Promise<void> {
  await apiClient.delete(`/zones/${zoneId}`)
}

export async function getAnalysisZoneEvents(analysisId: string): Promise<ZoneEventRecord[]> {
  const response = await apiClient.get<ZoneEventRecord[]>(
    `/zones/analysis/${analysisId}/events`,
  )
  return response.data
}

export async function getLiveZoneEvents(sessionId: string): Promise<ZoneEventRecord[]> {
  const response = await apiClient.get<ZoneEventRecord[]>(`/zones/live/${sessionId}/events`)
  return response.data
}

export async function getAnalysisZoneActivity(
  analysisId: string,
): Promise<ZoneActivitySummary> {
  const response = await apiClient.get<ZoneActivitySummary>(
    `/zones/analysis/${analysisId}/activity`,
  )
  return response.data
}

export async function getLiveZoneActivity(sessionId: string): Promise<ZoneActivitySummary> {
  const response = await apiClient.get<ZoneActivitySummary>(
    `/zones/live/${sessionId}/activity`,
  )
  return response.data
}

export async function fetchLiveLatestFrameBlobUrl(sessionId: string): Promise<string> {
  const response = await apiClient.get<Blob>(`/live/${sessionId}/latest-frame`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(response.data)
}
