import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Clock3,
  GitBranch,
  RefreshCw,
  Save,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { listUserAnalyses, type AnalysisListItem } from '../services/analysisService.ts'
import {
  getAnalysisBehavior,
  getLiveBehavior,
  setAnalysisBehaviorBaseline,
  setLiveBehaviorBaseline,
  type BehaviorBaselineConfig,
  type BehaviorReport,
} from '../services/behaviorService.ts'
import {
  listLiveMonitoringSessions,
  type LiveSessionStatusResponse,
} from '../services/liveService.ts'

type SourceKind = 'analysis' | 'live'

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainder = total % 60
  return [hours, minutes, remainder].map((part) => String(part).padStart(2, '0')).join(':')
}

function trackLabel(trackId: number, report: BehaviorReport): string {
  const track = report.movement_summaries.find((item) => item.track_id === trackId)
  return track?.track_code ?? `T${String(trackId).padStart(3, '0')}`
}

export function BehaviourIntelligencePage() {
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([])
  const [liveSessions, setLiveSessions] = useState<LiveSessionStatusResponse[]>([])
  const [sourceKind, setSourceKind] = useState<SourceKind>('analysis')
  const [sourceId, setSourceId] = useState('')
  const [report, setReport] = useState<BehaviorReport | null>(null)
  const [baseline, setBaseline] = useState<BehaviorBaselineConfig | null>(null)
  const [trackFilter, setTrackFilter] = useState('')
  const [eventFilter, setEventFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([listUserAnalyses(), listLiveMonitoringSessions()])
      .then(([analysisRows, sessionRows]) => {
        if (!active) return
        const completed = analysisRows.filter((item) => item.status === 'completed')
        setAnalyses(completed)
        setLiveSessions(sessionRows)
        const firstId = completed[0]?.analysis_id ?? sessionRows[0]?.session_id ?? ''
        if (firstId) {
          setSourceKind(completed.length > 0 ? 'analysis' : 'live')
          setSourceId(firstId)
        }
      })
      .catch(() => {
        if (active) setError('Could not load your analysis and live-session list.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!sourceId) {
      return
    }
    let active = true
    const request =
      sourceKind === 'analysis' ? getAnalysisBehavior(sourceId) : getLiveBehavior(sourceId)
    request
      .then((data) => {
        if (!active) return
        setError('')
        setReport(data)
        setBaseline(data.baseline.config)
      })
      .catch(() => {
        if (active) setError('Could not load behavior intelligence for this session.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [sourceId, sourceKind])

  const visibleSequences = useMemo(() => {
    if (!report) return []
    return report.sequences.filter((sequence) => {
      if (trackFilter && !sequence.track_ids.includes(Number(trackFilter))) return false
      if (eventFilter && sequence.event_type !== eventFilter) return false
      if (severityFilter && sequence.severity !== severityFilter) return false
      const eventDate = sequence.created_at?.slice(0, 10)
      if (fromDate && (!eventDate || eventDate < fromDate)) return false
      if (toDate && (!eventDate || eventDate > toDate)) return false
      return true
    })
  }, [eventFilter, fromDate, report, severityFilter, toDate, trackFilter])

  const saveBaseline = async () => {
    if (!baseline || !sourceId) return
    setSaving(true)
    setNotice('')
    setError('')
    try {
      if (sourceKind === 'analysis') {
        await setAnalysisBehaviorBaseline(sourceId, baseline)
      } else {
        await setLiveBehaviorBaseline(sourceId, baseline)
      }
      const refreshed =
        sourceKind === 'analysis' ? await getAnalysisBehavior(sourceId) : await getLiveBehavior(sourceId)
      setReport(refreshed)
      setBaseline(refreshed.baseline.config)
      setNotice('Session baseline rules saved.')
    } catch {
      setError('Could not save baseline rules. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const sourceOptions =
    sourceKind === 'analysis'
      ? analyses.map((item) => ({ id: item.analysis_id, label: item.video_filename }))
      : liveSessions.map((item) => ({
          id: item.session_id,
          label: `${new Date(item.started_at).toLocaleString()} · ${item.status}`,
        }))

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            <Activity className="h-3.5 w-3.5" />
            Temporal behavior analysis
          </div>
          <h1 className="mt-3 font-display text-2xl font-extrabold text-slate-950 sm:text-3xl">
            Behaviour Intelligence
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Review movement histories, repeated interactions, explainable anomalies, and related
            observations across one recorded or live monitoring session.
          </p>
        </div>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </header>

      <section className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs sm:grid-cols-[200px_1fr]">
        <label className="text-xs font-semibold text-slate-600">
          Source
          <select
            value={sourceKind}
            onChange={(event) => {
              const nextKind = event.target.value as SourceKind
              setSourceKind(nextKind)
              setLoading(true)
              setError('')
              setSourceId(
                nextKind === 'analysis'
                  ? (analyses[0]?.analysis_id ?? '')
                  : (liveSessions[0]?.session_id ?? ''),
              )
            }}
            className="mt-1.5 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
          >
            <option value="analysis">Recorded analysis</option>
            <option value="live">Live monitoring session</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-600">
          Session
          <select
            value={sourceId}
            onChange={(event) => {
              setError('')
              setSourceId(event.target.value)
            }}
            className="mt-1.5 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
          >
            {sourceOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error && (
        <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          {notice}
        </p>
      )}

      {loading || (Boolean(sourceId) && report?.session_id !== sourceId && !error) ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          Loading behavior report…
        </div>
      ) : !sourceId ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-600">
          No {sourceKind === 'analysis' ? 'completed video analyses' : 'live sessions'} are available.
        </div>
      ) : report ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {([
              { label: 'Tracked entities', count: report.summary.track_count, icon: Users },
              { label: 'Behavior sequences', count: report.summary.sequence_count, icon: GitBranch },
              { label: 'Scored anomalies', count: report.summary.anomaly_count, icon: AlertTriangle },
              { label: 'Correlated events', count: report.summary.correlation_count, icon: Clock3 },
            ] satisfies Array<{
              label: string
              count: number
              icon: LucideIcon
            }>).map(({ label, count, icon: Icon }) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                  {label}
                  <Icon className="h-4 w-4 text-blue-600" />
                </div>
                <p className="mt-2 font-display text-2xl font-extrabold text-slate-950">{count}</p>
              </div>
            ))}
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-lg font-bold text-slate-950">Session baseline</h2>
                  <p className="mt-1 text-xs text-slate-500">{report.baseline.note}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">
                  {report.baseline.status.replaceAll('_', ' ')}
                </span>
              </div>
              <p className="mt-3 text-xs text-slate-600">
                Descriptive, session-specific rules only. No trained statistical model and no
                inference about a person’s intent.
              </p>
              {report.baseline.measurements && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {Object.entries(report.baseline.measurements).map(([key, value]) => (
                    <span key={key} className="rounded-lg bg-slate-50 px-2.5 py-1.5 text-slate-700">
                      {key.replaceAll('_', ' ')}: <strong>{String(value)}</strong>
                    </span>
                  ))}
                </div>
              )}
              {baseline && (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {(
                    [
                      ['minimum_tracks', 'Minimum track count', 1],
                      ['minimum_history_seconds', 'Minimum history (seconds)', 0.1],
                      ['stationary_displacement_threshold', 'Stationary displacement threshold', 0],
                      ['low_movement_speed_threshold', 'Low movement image-units/sec', 0],
                      ['running_like_speed_threshold', 'Running-like image-units/sec', 0],
                      ['prolonged_stationary_seconds', 'Prolonged stationary duration (seconds)', 0],
                    ] as const
                    ).map(([key, label, min]) => (
                      <label key={key} className="text-[11px] font-semibold text-slate-600">
                        {label}
                        <input
                          type="number"
                          min={min}
                          step="0.01"
                          value={baseline[key]}
                          onChange={(event) =>
                            setBaseline((current) =>
                              current
                                ? { ...current, [key]: Number(event.target.value) }
                                : current,
                            )
                          }
                          className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-800"
                        />
                      </label>
                    ))}
                  </div>
                  <div className="mt-4">
                    <p className="text-[11px] font-semibold text-slate-600">Anomaly score weights (must sum to 1)</p>
                    <div className="mt-2 grid gap-3 sm:grid-cols-2">
                      {(Object.keys(baseline.anomaly_weights) as Array<keyof BehaviorBaselineConfig['anomaly_weights']>).map((key) => (
                        <label key={key} className="text-[11px] font-semibold capitalize text-slate-600">
                          {key.replaceAll('_', ' ')}
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.01"
                            value={baseline.anomaly_weights[key]}
                            onChange={(event) =>
                              setBaseline((current) =>
                                current
                                  ? {
                                      ...current,
                                      anomaly_weights: {
                                        ...current.anomaly_weights,
                                        [key]: Number(event.target.value),
                                      },
                                    }
                                  : current,
                              )
                            }
                            className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-800"
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}
              <button
                type="button"
                onClick={saveBaseline}
                disabled={!baseline || saving}
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-bold text-white disabled:opacity-50"
              >
                <Save className="h-3.5 w-3.5" />
                {saving ? 'Saving…' : 'Save baseline rules'}
              </button>
              <p className="mt-3 text-[11px] text-slate-500">{report.scoring_logic.description}</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <h2 className="font-display text-lg font-bold text-slate-950">Movement timeline</h2>
              <p className="mt-1 text-xs text-slate-500">
                Relative image-plane movement only; values are not physical speed.
              </p>
              <div className="mt-4 space-y-3">
                {report.movement_summaries.map((track) => (
                  <article key={track.track_id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-blue-700">{track.track_code}</span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold capitalize text-slate-600">
                        {track.movement_type}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-600">
                      <span>{formatTime(track.start_timestamp)} – {formatTime(track.end_timestamp)}</span>
                      <span className="capitalize">{track.direction}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-slate-500">
                      <span>{track.direction_changes} direction changes</span>
                      <span>
                        Peak image-plane acceleration{' '}
                        {track.maximum_normalized_image_acceleration_per_second_squared.toFixed(3)} normalized units/s²
                      </span>
                      <span>{track.repeated_area_observations} repeated area observations</span>
                      {track.back_and_forth && <span className="font-semibold text-amber-700">Back-and-forth pattern</span>}
                      {track.prolonged_stationary && <span className="font-semibold text-slate-700">Prolonged stationary observation</span>}
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">{track.baseline_comparison.note}</p>
                    {track.related_tracks.length > 0 && (
                      <p className="mt-1 text-[10px] text-slate-600">
                        Related tracks:{' '}
                        {track.related_tracks.map((related) => (
                          `${trackLabel(related.other_track_id, report)} (${related.approach_observed ? 'approach' : ''}${related.approach_observed && related.moving_away_observed ? ', ' : ''}${related.moving_away_observed ? 'moved away' : ''}${related.proximity_visits > 1 ? ` · ${related.proximity_visits} visits` : ''})`
                        )).join('; ')}
                      </p>
                    )}
                  </article>
                ))}
                {report.movement_summaries.length === 0 && (
                  <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">No tracked movement history is available.</p>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-display text-lg font-bold text-slate-950">Behavior sequences</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Observed facts and rule inferences are shown separately.
                </p>
              </div>
              <span className="text-xs text-slate-500">{visibleSequences.length} shown</span>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
              <input
                value={trackFilter}
                onChange={(event) => setTrackFilter(event.target.value)}
                placeholder="Track ID"
                aria-label="Filter by track ID"
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
              />
              <input
                value={eventFilter}
                onChange={(event) => setEventFilter(event.target.value)}
                placeholder="Event type"
                aria-label="Filter by event type"
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
              />
              <select
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value)}
                aria-label="Filter by severity"
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
              >
                <option value="">All severities</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              <input
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
                aria-label="Filter from date"
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
              />
              <input
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
                aria-label="Filter to date"
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs"
              />
            </div>
            <div className="mt-4 space-y-3">
              {visibleSequences.map((sequence) => (
                <article key={sequence.sequence_id} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-700">
                        {sequence.track_ids.map((id) => trackLabel(id, report)).join(' · ')}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                        {sequence.event_type.replaceAll('_', ' ')}
                      </span>
                      <span className="text-[10px] text-slate-500">{sequence.severity} · {Math.round(sequence.confidence * 100)}% confidence</span>
                    </div>
                    <span className="font-mono text-[11px] text-slate-600">
                      {formatTime(sequence.start_timestamp)} – {formatTime(sequence.end_timestamp)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-800">{sequence.observed_facts}</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg bg-blue-50/70 p-3">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-blue-700">Actions observed</p>
                      <ul className="mt-1 list-inside list-disc space-y-1 text-xs text-slate-700">
                        {sequence.actions_observed.map((action, index) => <li key={index}>{action}</li>)}
                      </ul>
                    </div>
                    <div className="rounded-lg bg-amber-50/70 p-3">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-amber-800">Inference / uncertainty</p>
                      <p className="mt-1 text-xs text-slate-700">{sequence.inferred_conclusion || 'No additional inference was recorded.'}</p>
                    </div>
                  </div>
                  {sequence.supporting_evidence.length > 0 && (
                    <p className="mt-2 text-[11px] text-slate-500">
                      Evidence at {sequence.supporting_evidence.map((item) => formatTime(item.timestamp_seconds)).join(', ')}
                    </p>
                  )}
                </article>
              ))}
              {visibleSequences.length === 0 && (
                <p className="rounded-xl bg-slate-50 p-5 text-center text-sm text-slate-500">
                  No behavior sequences match the selected filters.
                </p>
              )}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <h2 className="flex items-center gap-2 font-display text-lg font-bold text-slate-950">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Explainable anomaly feed
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Existing weighted rule scores only; events without a stored score are not assigned one.
              </p>
              <div className="mt-4 space-y-3">
                {report.anomalies.map((anomaly) => (
                  <article key={anomaly.anomaly_id} className="rounded-xl border border-amber-100 bg-amber-50/40 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-slate-800">
                        {anomaly.track_ids.map((id) => trackLabel(id, report)).join(' · ')}
                      </span>
                      <span className="rounded-lg bg-white px-2 py-1 font-mono text-xs font-bold text-amber-800">
                        {Math.round(anomaly.score * 100)}/100 · {anomaly.severity}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-700">{anomaly.reason}</p>
                    <p className="mt-1 text-[11px] text-slate-500">Uncertainty: {anomaly.uncertainty}</p>
                  </article>
                ))}
                {report.anomalies.length === 0 && (
                  <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">No scored anomalies are available for this session.</p>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <h2 className="font-display text-lg font-bold text-slate-950">Contextual event correlations</h2>
              <div className="mt-4 space-y-3">
                {report.event_correlations.map((correlation) => (
                  <article key={correlation.correlation_id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                      <ArrowDownRight className="h-3.5 w-3.5 text-blue-600" />
                      {correlation.track_ids.map((id) => trackLabel(id, report)).join(' · ')}
                      <ArrowUpRight className="h-3.5 w-3.5 text-blue-600" />
                    </div>
                    <p className="mt-2 text-xs text-slate-600">{correlation.explanation}</p>
                    <ul className="mt-2 space-y-1 text-[11px] text-slate-500">
                      {correlation.observed_facts.map((fact, index) => <li key={index}>Observed: {fact}</li>)}
                    </ul>
                  </article>
                ))}
                {report.event_correlations.length === 0 && (
                  <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">
                    No adjacent events with shared tracks were found within the correlation window.
                  </p>
                )}
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}
