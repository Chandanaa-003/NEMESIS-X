import { apiClient } from './api.ts'

export type IdentitySourceType = 'analysis' | 'live_session'
export type IdentityEntityType = 'person' | 'object'
export type IdentityMatchStatus = 'confirmed' | 'probable' | 'unknown'

export interface IdentityTrackAppearance {
  track_id: number
  track_code: string
  category: string
  first_seen_timestamp: number
  last_seen_timestamp: number
  detection_count: number
  match_confidence: number | null
  match_status: IdentityMatchStatus
  matching_explanation: string
  unresolved_candidate_code: string | null
  evidence_url: string | null
  manually_corrected: boolean
  correction_note: string | null
}

export interface IdentityRelatedEvent {
  id: string
  event_type: string
  category: string
  title: string
  timestamp_seconds: number
  confidence: number
  severity: string
  track_codes: string[]
}

export interface EntityIdentity {
  id: string
  identity_code: string
  source_type: IdentitySourceType
  source_id: string
  entity_type: IdentityEntityType
  category: string
  first_seen_timestamp: number
  last_seen_timestamp: number
  appearance_count: number
  matching_confidence: number | null
  status: IdentityMatchStatus
  matching_explanation: string
  associated_track_ids: number[]
  associated_track_codes: string[]
  evidence_urls: string[]
  related_event_count: number
  merged_into_code: string | null
  track_appearances?: IdentityTrackAppearance[]
  related_events?: IdentityRelatedEvent[]
}

export interface IdentitySearchResponse {
  items: EntityIdentity[]
  total: number
  limit: number
  offset: number
}

export interface IdentityCounts {
  unique_people: number
  unique_objects: number
  confirmed: number
  probable: number
  unknown: number
}

export async function searchIdentities(params: {
  sourceType: IdentitySourceType
  sourceId: string
  entityType?: IdentityEntityType | ''
  query?: string
  minAppearances?: number
  firstSeenFrom?: number
  lastSeenTo?: number
  eventType?: string
  limit?: number
}): Promise<IdentitySearchResponse> {
  const response = await apiClient.get<IdentitySearchResponse>('/identities', {
    params: {
      source_type: params.sourceType,
      source_id: params.sourceId,
      entity_type: params.entityType || undefined,
      query: params.query?.trim() || undefined,
      min_appearances: params.minAppearances ?? 1,
      first_seen_from: params.firstSeenFrom,
      last_seen_to: params.lastSeenTo,
      event_type: params.eventType?.trim() || undefined,
      limit: params.limit ?? 200,
    },
  })
  return response.data
}

export async function getIdentityCounts(
  sourceType: IdentitySourceType,
  sourceId: string,
): Promise<IdentityCounts> {
  const response = await apiClient.get<IdentityCounts>('/identities/counts', {
    params: { source_type: sourceType, source_id: sourceId },
  })
  return response.data
}

export async function getIdentity(identityId: string): Promise<EntityIdentity> {
  const response = await apiClient.get<EntityIdentity>(`/identities/${identityId}`)
  return response.data
}

export async function getIdentityEvidence(
  identityId: string,
  trackId: number,
): Promise<Blob> {
  const response = await apiClient.get<Blob>(
    `/identities/${identityId}/tracks/${trackId}/evidence`,
    { responseType: 'blob' },
  )
  return response.data
}

export async function correctIdentityTrack(params: {
  identityId: string
  trackId: number
  targetIdentityId?: string
  createNewIdentity?: boolean
  correctionNote: string
}): Promise<EntityIdentity> {
  const response = await apiClient.patch<EntityIdentity>(
    `/identities/${params.identityId}/tracks/${params.trackId}`,
    {
      target_identity_id: params.targetIdentityId,
      create_new_identity: params.createNewIdentity ?? false,
      correction_note: params.correctionNote || undefined,
    },
  )
  return response.data
}
