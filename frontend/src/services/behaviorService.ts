import { apiClient } from './api.ts'

export interface BehaviorBaselineConfig {
  minimum_tracks: number
  minimum_history_seconds: number
  stationary_displacement_threshold: number
  low_movement_speed_threshold: number
  running_like_speed_threshold: number
  prolonged_stationary_seconds: number
  anomaly_weights: {
    duration: number
    movement_change: number
    interaction_sequence: number
    repeated_behavior: number
    zone_rule: number
  }
}

export interface BehaviorTrackSummary {
  track_id: number
  track_code: string
  class_name: string
  start_timestamp: number
  end_timestamp: number
  duration_seconds: number
  movement_type: string
  direction: string
  maximum_normalized_image_speed_per_second: number
  maximum_normalized_image_acceleration_per_second_squared: number
  speed_is_calibrated: boolean
  direction_changes: number
  back_and_forth: boolean
  stationary: boolean
  prolonged_stationary: boolean
  repeated_area_observations: number
  confidence: number
  uncertainty: string
  baseline_comparison: {
    status: string
    stationary_duration_deviation_seconds?: number
    direction_is_most_common?: boolean
    note: string
  }
  related_tracks: Array<{
    other_track_id: number
    other_class_name: string
    approach_observed: boolean
    moving_away_observed: boolean
    proximity_visits: number
    minimum_normalized_distance: number
  }>
}

export interface BehaviorSequence {
  sequence_id: string
  track_ids: number[]
  start_timestamp: number
  end_timestamp: number
  actions_observed: string[]
  event_type: string
  confidence: number
  severity: string
  created_at: string | null
  supporting_evidence: Array<{
    frame_index?: number
    timestamp_seconds: number
    url: string
  }>
  observed_facts: string
  inferred_conclusion: string
}

export interface BehaviorAnomaly {
  anomaly_id: string
  track_ids: number[]
  event_category: string
  severity: string
  confidence: number
  score: number
  reason: string
  supporting_timestamps: number[]
  uncertainty: string
}

export interface BehaviorReport {
  session_id: string
  generated_at: string
  summary: {
    track_count: number
    sequence_count: number
    anomaly_count: number
    correlation_count: number
    history_seconds: number
    baseline_status: string
  }
  baseline: {
    status: string
    model_trained: boolean
    note: string
    measurements: Record<string, unknown> | null
    config: BehaviorBaselineConfig
  }
  movement_summaries: BehaviorTrackSummary[]
  sequences: BehaviorSequence[]
  anomalies: BehaviorAnomaly[]
  event_correlations: Array<{
    correlation_id: string
    event_ids: string[]
    track_ids: number[]
    start_timestamp: number
    end_timestamp: number
    observed_facts: string[]
    explanation: string
  }>
  scoring_logic: {
    description: string
    weights: Record<string, number>
  }
}

export interface BehaviorFilters {
  track_id?: number
  event_type?: string
  severity?: string
  start_date?: string
  end_date?: string
}

export async function getAnalysisBehavior(analysisId: string): Promise<BehaviorReport> {
  const response = await apiClient.get<BehaviorReport>(`/behavior/analysis/${analysisId}`)
  return response.data
}

export async function getLiveBehavior(sessionId: string): Promise<BehaviorReport> {
  const response = await apiClient.get<BehaviorReport>(`/behavior/live/${sessionId}`)
  return response.data
}

export async function getAnalysisBehaviorSequences(
  analysisId: string,
  filters: BehaviorFilters = {},
): Promise<BehaviorSequence[]> {
  const response = await apiClient.get<BehaviorSequence[]>(
    `/behavior/analysis/${analysisId}/sequences`,
    { params: filters },
  )
  return response.data
}

export async function getLiveBehaviorSequences(
  sessionId: string,
  filters: BehaviorFilters = {},
): Promise<BehaviorSequence[]> {
  const response = await apiClient.get<BehaviorSequence[]>(
    `/behavior/live/${sessionId}/sequences`,
    { params: filters },
  )
  return response.data
}

export async function setAnalysisBehaviorBaseline(
  analysisId: string,
  baseline: BehaviorBaselineConfig,
): Promise<void> {
  await apiClient.put(`/behavior/analysis/${analysisId}/baseline`, baseline)
}

export async function setLiveBehaviorBaseline(
  sessionId: string,
  baseline: BehaviorBaselineConfig,
): Promise<void> {
  await apiClient.put(`/behavior/live/${sessionId}/baseline`, baseline)
}
