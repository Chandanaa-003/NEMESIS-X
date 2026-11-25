import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Clock,
  Eye,
  HelpCircle,
  Layers,
  Package,
  ShieldAlert,
  Sparkles,
  Target,
  User,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  fetchExtractedFrameBlobUrl,
  type EventRecordInfo,
  type TrackSummaryInfo,
} from '../../services/analysisService.ts'

interface InteractionIntelligenceSectionProps {
  analysisId: string
  tracks: TrackSummaryInfo[]
  events: EventRecordInfo[]
}

function formatHms(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatPersonCode(id: number): string {
  return `P${String(id).padStart(3, '0')}`
}

function formatObjectCode(id: number): string {
  return `O${String(id).padStart(3, '0')}`
}

const UNCERTAINTY_BADGE: Record<string, string> = {
  low: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  high: 'border-rose-200 bg-rose-50 text-rose-700',
}

export function InteractionIntelligenceSection({
  analysisId,
  tracks,
  events,
}: InteractionIntelligenceSectionProps) {
  const [activeCategory, setActiveCategory] = useState<
    'all' | 'pickups' | 'placements' | 'unattended' | 'anomalies' | 'multi_person'
  >('all')
  const [inspectedEvent, setInspectedEvent] = useState<EventRecordInfo | null>(null)
  const [evidenceUrls, setEvidenceUrls] = useState<Record<string, string>>({})

  const personTracks = useMemo(
    () => tracks.filter((t) => t.class_name.toLowerCase() === 'person'),
    [tracks],
  )
  const objectTracks = useMemo(
    () => tracks.filter((t) => t.class_name.toLowerCase() !== 'person'),
    [tracks],
  )

  const pickups = useMemo(
    () => events.filter((e) => e.event_type === 'possible_object_pickup'),
    [events],
  )
  const placements = useMemo(
    () => events.filter((e) => e.event_type === 'possible_object_placement'),
    [events],
  )
  const unattended = useMemo(
    () => events.filter((e) => e.event_type === 'possible_unattended_object'),
    [events],
  )
  const anomalies = useMemo(
    () =>
      events.filter((e) =>
        [
          'movement_anomaly',
          'prolonged_stationary_person',
          'restricted_zone_entry',
          'object_movement_without_person',
          'after_hours_activity',
        ].includes(e.event_type),
      ),
    [events],
  )
  const multiPerson = useMemo(
    () =>
      events.filter((e) =>
        ['multi_person_object_interaction', 'multiple_people_interacting'].includes(e.event_type),
      ),
    [events],
  )

  const filteredEvents = useMemo(() => {
    switch (activeCategory) {
      case 'pickups':
        return pickups
      case 'placements':
        return placements
      case 'unattended':
        return unattended
      case 'anomalies':
        return anomalies
      case 'multi_person':
        return multiPerson
      default:
        return events.filter(
          (e) =>
            e.category === 'object_interactions' ||
            e.category === 'possible_unattended_objects' ||
            anomalies.some((a) => a.id === e.id),
        )
    }
  }, [activeCategory, events, pickups, placements, unattended, anomalies, multiPerson])

  const openEventInspector = (evt: EventRecordInfo) => {
    setInspectedEvent(evt)
    for (const frame of evt.evidence_frames) {
      if (!evidenceUrls[frame.filename]) {
        fetchExtractedFrameBlobUrl(analysisId, frame.filename)
          .then((url) => {
            setEvidenceUrls((prev) => ({ ...prev, [frame.filename]: url }))
          })
          .catch(() => {})
      }
    }
  }

  return (
    <section className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#7C3AED]">
            <Sparkles className="h-3.5 w-3.5 text-[#7C3AED]" />
            <span>Interaction & Anomaly Intelligence</span>
          </span>
          <h3 className="mt-2 font-display text-xl font-extrabold text-[#111827] sm:text-2xl">
            Person–Object Relationships & Behavioral Rules
          </h3>
          <p className="mt-1 text-xs text-[#64748B]">
            Temporal association of persistent person tracks, object displacements, pickups, placements, and explainable anomaly scores.
          </p>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
            <User className="h-3.5 w-3.5 text-[#2563EB]" />
            <span>Person Tracks</span>
          </div>
          <p className="mt-1 font-display text-2xl font-extrabold text-[#111827]">
            {personTracks.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
            <Package className="h-3.5 w-3.5 text-[#7C3AED]" />
            <span>Object Tracks</span>
          </div>
          <p className="mt-1 font-display text-2xl font-extrabold text-[#111827]">
            {objectTracks.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
            <Target className="h-3.5 w-3.5 text-rose-600" />
            <span>Possible Pickups</span>
          </div>
          <p className="mt-1 font-display text-2xl font-extrabold text-rose-700">
            {pickups.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
            <Layers className="h-3.5 w-3.5 text-amber-600" />
            <span>Possible Placements</span>
          </div>
          <p className="mt-1 font-display text-2xl font-extrabold text-amber-700">
            {placements.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
            <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
            <span>Unattended Objects</span>
          </div>
          <p className="mt-1 font-display text-2xl font-extrabold text-rose-700">
            {unattended.length}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-3.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#64748B]">
            <ShieldAlert className="h-3.5 w-3.5 text-[#7C3AED]" />
            <span>Anomaly Alerts</span>
          </div>
          <p className="mt-1 font-display text-2xl font-extrabold text-[#7C3AED]">
            {anomalies.length}
          </p>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {[
          { id: 'all', label: 'All Interactions & Anomalies' },
          { id: 'pickups', label: `Possible Pickups (${pickups.length})` },
          { id: 'placements', label: `Placements (${placements.length})` },
          { id: 'unattended', label: `Unattended (${unattended.length})` },
          { id: 'multi_person', label: `Multi-Person (${multiPerson.length})` },
          { id: 'anomalies', label: `Anomaly Alerts (${anomalies.length})` },
        ].map((tab) => {
          const active = activeCategory === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveCategory(tab.id as typeof activeCategory)}
              className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all ${
                active
                  ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                  : 'border-slate-200 bg-white text-[#64748B] hover:border-slate-300 hover:bg-[#F5F8FC]'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Interaction & Anomaly Cards */}
      {filteredEvents.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-[#F5F8FC] p-10 text-center">
          <Activity className="mx-auto h-7 w-7 text-slate-400" />
          <p className="mt-2 text-sm font-semibold text-slate-700">
            No matching interaction or anomaly patterns
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Normal movement without suspicious interactions or rule violations does not trigger anomaly alerts.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredEvents.map((evt) => {
            const pId = evt.explanation.person_track_id
            const oId = evt.explanation.object_track_id
            const uncertainty = evt.explanation.association_uncertainty
            const scoreObj = evt.explanation.anomaly_score

            return (
              <div
                key={evt.id}
                onClick={() => openEventInspector(evt)}
                className="cursor-pointer rounded-2xl border border-slate-200/90 bg-white p-4 shadow-2xs hover:border-blue-300 hover:shadow-md transition-all"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${
                          evt.severity === 'high'
                            ? 'border-rose-200 bg-rose-50 text-rose-700'
                            : evt.severity === 'medium'
                              ? 'border-amber-200 bg-amber-50 text-amber-700'
                              : 'border-blue-200 bg-blue-50 text-blue-700'
                        }`}
                      >
                        {evt.severity}
                      </span>

                      {pId !== undefined && pId !== null && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 font-mono text-[11px] font-bold text-[#2563EB]">
                          <User className="h-3 w-3" />
                          {formatPersonCode(pId)}
                        </span>
                      )}

                      {oId !== undefined && oId !== null && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-violet-50 px-2 py-0.5 font-mono text-[11px] font-bold text-[#7C3AED]">
                          <Package className="h-3 w-3" />
                          {formatObjectCode(oId)}
                        </span>
                      )}

                      {uncertainty && (
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                            UNCERTAINTY_BADGE[uncertainty] || UNCERTAINTY_BADGE.medium
                          }`}
                        >
                          <HelpCircle className="h-3 w-3" />
                          Uncertainty: {uncertainty}
                        </span>
                      )}

                      {scoreObj && typeof scoreObj.total_score === 'number' && (
                        <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-700">
                          Rule Score: {Math.round(scoreObj.total_score * 100)}/100
                        </span>
                      )}
                    </div>

                    <h4 className="font-display text-sm font-bold text-[#111827]">{evt.title}</h4>
                    <p className="text-xs text-[#64748B]">{evt.description}</p>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 text-[#111827] font-semibold">
                      <Clock className="h-3.5 w-3.5 text-[#2563EB]" />
                      {formatHms(evt.start_timestamp)} → {formatHms(evt.end_timestamp)}
                    </span>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 rounded-lg bg-[#EFF6FF] px-2.5 py-1 text-xs font-semibold text-[#2563EB]"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span>Timeline</span>
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Event Timeline & Evidence Inspector Modal */}
      {inspectedEvent && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
        >
          <div className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
              <div>
                <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-[#2563EB]">
                  {inspectedEvent.event_type.replaceAll('_', ' ')}
                </span>
                <h4 className="mt-1 font-display text-lg font-extrabold text-[#111827]">
                  {inspectedEvent.title}
                </h4>
                <p className="mt-1 text-xs text-slate-500">
                  Window: {formatHms(inspectedEvent.start_timestamp)} →{' '}
                  {formatHms(inspectedEvent.end_timestamp)} · Confidence:{' '}
                  {Math.round(inspectedEvent.confidence * 100)}%
                </p>
              </div>
              <button
                type="button"
                onClick={() => setInspectedEvent(null)}
                className="cursor-pointer rounded-xl border border-slate-200 p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Observed Actions vs Inference */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-[#F5F8FC] p-4 space-y-2">
                <p className="text-xs font-bold text-[#111827]">Observed Tracking Timeline</p>
                <ul className="space-y-1.5 text-xs text-slate-600">
                  {inspectedEvent.explanation.observed_sequence.map((line, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#2563EB]" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-[#F5F8FC] p-4 space-y-2">
                <p className="text-xs font-bold text-[#111827]">Rule Inference & Uncertainty</p>
                <p className="text-xs text-slate-600">{inspectedEvent.explanation.why_flagged}</p>
                {inspectedEvent.explanation.association_uncertainty && (
                  <p className="text-xs font-semibold text-slate-700">
                    Association Uncertainty:{' '}
                    <span className="uppercase">{inspectedEvent.explanation.association_uncertainty}</span>
                  </p>
                )}
              </div>
            </div>

            {/* Explainable Anomaly Score Breakdown */}
            {inspectedEvent.explanation.anomaly_score && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-[#111827]">
                    Explainable Rule-Based Anomaly Score Breakdown
                  </p>
                  <span className="rounded-lg bg-blue-50 px-2.5 py-1 font-mono text-xs font-bold text-[#2563EB]">
                    Total: {Math.round((inspectedEvent.explanation.anomaly_score.total_score || 0) * 100)} / 100
                  </span>
                </div>
                <div className="grid gap-2 sm:grid-cols-3 text-[11px]">
                  {[
                    ['Duration', inspectedEvent.explanation.anomaly_score.duration_score],
                    ['Movement Change', inspectedEvent.explanation.anomaly_score.movement_change_score],
                    ['Interaction Sequence', inspectedEvent.explanation.anomaly_score.interaction_sequence_score],
                    ['Track Confidence', inspectedEvent.explanation.anomaly_score.track_association_confidence],
                    ['Repeated Behavior', inspectedEvent.explanation.anomaly_score.repeated_behavior_score],
                    ['Zone Rules', inspectedEvent.explanation.anomaly_score.zone_rule_score],
                  ].map(([label, val]) => (
                    <div key={String(label)} className="flex justify-between rounded-lg bg-slate-50 px-2.5 py-1.5">
                      <span className="text-slate-500">{label}</span>
                      <span className="font-mono font-bold text-slate-800">
                        {Math.round(Number(val || 0) * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Supporting Evidence Frames */}
            {inspectedEvent.evidence_frames.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-bold text-[#111827]">Supporting Evidence Frames</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  {inspectedEvent.evidence_frames.map((frame) => (
                    <div
                      key={frame.frame_index}
                      className="overflow-hidden rounded-xl border border-slate-200 bg-slate-100"
                    >
                      {evidenceUrls[frame.filename] ? (
                        <img
                          src={evidenceUrls[frame.filename]}
                          alt={`Frame ${frame.frame_index}`}
                          className="aspect-video w-full object-cover"
                        />
                      ) : (
                        <div className="flex aspect-video items-center justify-center text-xs text-slate-400">
                          Loading frame...
                        </div>
                      )}
                      <div className="bg-white px-2.5 py-1.5 font-mono text-[10px] text-slate-600">
                        {formatHms(frame.timestamp_seconds)} · Frame {frame.frame_index}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
