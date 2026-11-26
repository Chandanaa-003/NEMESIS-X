import { apiClient } from './api'

export type IdentitySourceType = 'analysis' | 'live_session'
export type IdentityEntityType = 'person' | 'object'
export type IdentityStatus = 'confirmed' | 'probable' | 'unknown'

export interface IdentityObservation {
  track_id: number
  track_code: string
  first_seen_timestamp: number
  last_seen_timestamp: number
  detection_count: number
  match_confidence: number
  feature_quality: number
  matching_explanation: string
  bbox: { x1: number; y1: number; x2: number; y2: number } | null
  evidence_url: string | null
}

export interface IdentityRelatedEvent {
  event_id: string
  event_type: string
  title: string
  timestamp_seconds: number
  involved_track_ids: number[]
}

export interface EntityIdentity {
  id: string
  source_type: IdentitySourceType
  source_id: string
  identity_code: string
  entity_type: IdentityEntityType
  class_name: string
  status: IdentityStatus
  first_seen_timestamp: number
  last_seen_timestamp: number
  appearance_count: number
  associated_track_ids: number[]
  matching_confidence: number
  matching_explanation: string
  feature_reference: string
  evidence_refs: string[]
  observations: IdentityObservation[]
  related_events: IdentityRelatedEvent[]
}

export interface IdentitySearchResponse {
  source_type: IdentitySourceType
  source_id: string
  total_unique_people: number
  total_unique_objects: number
  total: number
  items: EntityIdentity[]
}

export async function searchEntityIdentities(params: {
  source_type: IdentitySourceType
  source_id: string
  entity_type?: IdentityEntityType
  identity_code?: string
  min_appearances?: number
  first_seen_after?: number
  last_seen_before?: number
  limit?: number
  offset?: number
}): Promise<IdentitySearchResponse> {
  const response = await apiClient.get<IdentitySearchResponse>('/identities', { params })
  return response.data
}

export async function getEntityIdentity(identityId: string): Promise<EntityIdentity> {
  const response = await apiClient.get<EntityIdentity>(`/identities/${identityId}`)
  return response.data
}

export async function correctEntityIdentity(params: {
  identityId: string
  trackId: number
  targetIdentityId?: string
  createNewIdentity?: boolean
  correctionNote?: string
}): Promise<{ identity: EntityIdentity; correction: string }> {
  if (params.createNewIdentity) {
    const response = await apiClient.patch<{ identity: EntityIdentity; correction: string }>(
      `/identities/${params.identityId}/tracks/${params.trackId}`,
      {
        create_new_identity: true,
        correction_note: params.correctionNote,
      },
    )
    return response.data
  }
  if (!params.targetIdentityId) {
    throw new Error('Choose an existing identity or create a separate identity.')
  }
  const response = await apiClient.patch<{ identity: EntityIdentity; correction: string }>(
    `/identities/${params.identityId}/observations/${params.trackId}`,
    { target_identity_id: params.targetIdentityId },
  )
  return response.data
}

export async function fetchIdentityEvidenceBlobUrl(imageUrl: string): Promise<string> {
  const route = imageUrl.replace(/^\/api\/v1\/?/, '')
  const response = await apiClient.get<Blob>(route, { responseType: 'blob' })
  return URL.createObjectURL(response.data)
}