import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Clock,
  Eye,
  ImageOff,
  Info,
  Loader2,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  discoverAnalysisEvents,
  fetchExtractedFrameBlobUrl,
  getAnalysisEvents,
  type EventCategory,
  type EventDiscoveryResponse,
  type EventRecordInfo,
  type EventSeverity,
} from '../../services/analysisService'
import { getAuthErrorMessage } from '../../services/authService'
import { PdfDownloadButton } from './PdfDownloadButton'

type FilterValue = 'all' | EventCategory

const CATEGORY_FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all', label: 'All events' },
  { value: 'people_movement', label: 'People movement' },
  { value: 'object_interactions', label: 'Object interactions' },
  { value: 'possible_unattended_objects', label: 'Possible unattended objects' },
  { value: 'other_activities', label: 'Other detected activities' },
]

const CATEGORY_LABELS: Record<EventCategory, string> = {
  people_movement: 'People movement',
  object_interactions: 'Object interactions',
  possible_unattended_objects: 'Possible unattended objects',
  other_activities: 'Other detected activities',
}

const SEVERITY_BADGE: Record<EventSeverity, string> = {
  high: 'border-rose-200 bg-rose-50 text-rose-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  low: 'border-[#2563EB]/20 bg-[#EFF6FF] text-[#2563EB]',
}

function formatHms(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatTrackCode(trackId: number): string {
  return `T${String(trackId).padStart(3, '0')}`
}

function EvidenceThumbnail({
  analysisId,
  filename,
  timestampSeconds,
}: {
  analysisId: string
  filename: string
  timestampSeconds: number
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let active = true
    let createdUrl: string | null = null

    fetchExtractedFrameBlobUrl(analysisId, filename)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setBlobUrl(url)
      })
      .catch(() => {
        if (active) setFailed(true)
      })

    return () => {
      active = false
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl)
      }
    }
  }, [analysisId, filename])

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-[#F5F8FC]">
      {failed ? (
        <div className="flex aspect-video w-28 items-center justify-center text-[#64748B]">
          <ImageOff className="h-4 w-4" />
        </div>
      ) : !blobUrl ? (
        <div className="aspect-video w-28 animate-pulse bg-slate-100" />
      ) : (
        <img
          src={blobUrl}
          alt={`Evidence frame at ${formatHms(timestampSeconds)}`}
          className="aspect-video w-28 object-cover"
        />
      )}
      <div className="bg-white px-2 py-1 text-center font-mono text-[10px] font-semibold text-[#2563EB]">
        {formatHms(timestampSeconds)}
      </div>
    </div>
  )
}

function EventCard({ event }: { event: EventRecordInfo }) {
  return (
    <article className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs transition-shadow hover:shadow-md hover:shadow-slate-200/60">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase ${SEVERITY_BADGE[event.severity]}`}
            >
              {event.severity} severity
            </span>
            <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-2.5 py-0.5 text-[11px] font-semibold text-[#64748B]">
              {CATEGORY_LABELS[event.category]}
            </span>
            {event.explanation.requires_human_review && (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                <AlertTriangle className="h-3 w-3" />
                Human Review Recommended
              </span>
            )}
          </div>

          <h4 className="mt-2.5 font-display text-base font-bold text-[#111827]">
            {event.title}
          </h4>
        </div>

        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 font-semibold text-[#111827]">
            <Clock className="h-3.5 w-3.5 text-[#2563EB]" />
            {formatHms(event.start_timestamp)} → {formatHms(event.end_timestamp)}
          </span>
          <span className="rounded-lg border border-[#7C3AED]/20 bg-[#F5F3FF] px-2.5 py-1 font-semibold text-[#7C3AED]">
            {Math.round(event.confidence * 100)}% Rule + Model
          </span>
        </div>
      </div>

      <p className="mt-2.5 text-sm leading-relaxed text-[#64748B]">{event.description}</p>

      {/* Involved Tracking IDs */}
      {event.involved_track_ids.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-semibold text-[#111827]">Involved Tracks:</span>
          {event.involved_track_ids.map((tid) => (
            <span
              key={tid}
              className="rounded-md bg-[#2563EB]/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-[#2563EB]"
            >
              {formatTrackCode(tid)}
            </span>
          ))}
        </div>
      )}

      {/* Observed Sequence & Explanation */}
      <div className="mt-4 grid gap-3 rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4 md:grid-cols-2">
        <div>
          <p className="text-xs font-bold text-[#111827]">Observed Sequence</p>
          <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-[#64748B]">
            {event.explanation.observed_sequence.map((step, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#2563EB]" />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-2">
          <div>
            <p className="text-xs font-bold text-[#111827]">Why Flagged</p>
            <p className="mt-1 text-xs leading-relaxed text-[#64748B]">
              {event.explanation.why_flagged}
            </p>
          </div>
          <p className="text-[11px] leading-relaxed text-[#64748B]">
            <strong className="text-[#111827]">Confidence Basis:</strong>{' '}
            {event.explanation.confidence_note}
          </p>
        </div>
      </div>

      {/* Evidence Thumbnails */}
      {event.evidence_frames.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-semibold text-[#111827]">Visual Evidence Frames</p>
          <div className="flex flex-wrap gap-2.5">
            {event.evidence_frames.map((frame) => (
              <EvidenceThumbnail
                key={`${event.id}-${frame.frame_index}`}
                analysisId={event.analysis_id}
                filename={frame.filename}
                timestampSeconds={frame.timestamp_seconds}
              />
            ))}
          </div>
        </div>
      )}
    </article>
  )
}

interface EventDiscoverySectionProps {
  analysisId: string
  showTimelineLink?: boolean
  autoLoadExisting?: boolean
}

export function EventDiscoverySection({
  analysisId,
  showTimelineLink = false,
  autoLoadExisting = true,
}: EventDiscoverySectionProps) {
  const [discoveryData, setDiscoveryData] = useState<EventDiscoveryResponse | null>(null)
  const [activeFilter, setActiveFilter] = useState<FilterValue>('all')
  const [isDiscovering, setIsDiscovering] = useState(false)
  const [loadedForId, setLoadedForId] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const isLoadingSaved = autoLoadExisting && Boolean(analysisId) && loadedForId !== analysisId

  useEffect(() => {
    if (!analysisId || !autoLoadExisting) return

    let cancelled = false

    getAnalysisEvents(analysisId)
      .then((data) => {
        if (!cancelled) {
          setDiscoveryData(data)
          setErrorMsg(null)
          setLoadedForId(analysisId)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMsg(getAuthErrorMessage(error, 'Failed to load existing discovered events.'))
          setLoadedForId(analysisId)
        }
      })

    return () => {
      cancelled = true
    }
  }, [analysisId, autoLoadExisting])

  const handleDiscoverEvents = async () => {
    if (!analysisId || isDiscovering) return
    setIsDiscovering(true)
    setErrorMsg(null)

    try {
      const data = await discoverAnalysisEvents(analysisId)
      setDiscoveryData(data)
      setLoadedForId(analysisId)
    } catch (error) {
      setErrorMsg(getAuthErrorMessage(error, 'Failed to run event discovery.'))
    } finally {
      setIsDiscovering(false)
    }
  }

  const filteredEvents = useMemo(() => {
    const list = discoveryData?.events ?? []
    if (activeFilter === 'all') return list
    return list.filter((evt) => evt.category === activeFilter)
  }, [discoveryData, activeFilter])

  const summary = discoveryData?.summary

  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className="space-y-6 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs"
    >
      {/* Header & Discover Events Action */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#2563EB]/12 to-[#7C3AED]/12 text-[#2563EB]">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-display text-lg font-bold text-[#111827]">
              Event Discovery &amp; Contextual Reasoning
            </h3>
            <p className="text-xs text-[#64748B]">
              Rule-based spatial-temporal analysis over detected objects and persistent tracks.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-start gap-2.5">
          <PdfDownloadButton analysisId={analysisId} />

          {showTimelineLink && (
            <Link
              to={`/dashboard/timeline?analysisId=${analysisId}`}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-[#111827] transition-colors hover:border-[#2563EB]/40 hover:bg-[#F5F8FC] hover:text-[#2563EB]"
            >
              <span>Open Event Timeline</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          )}

          <Link
            to={`/dashboard/evidence?analysisId=${analysisId}`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-[#111827] transition-colors hover:border-[#7C3AED]/40 hover:bg-[#F5F8FC] hover:text-[#7C3AED]"
          >
            <span>Evidence Center</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>

          <button
            type="button"
            onClick={handleDiscoverEvents}
            disabled={isDiscovering}
            className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-[#2563EB]/20 transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-65"
          >
            {isDiscovering ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Discovering Events...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                <span>Discover Events</span>
              </>
            )}
          </button>
        </div>
      </div>

      {errorMsg && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {isLoadingSaved && !discoveryData && (
        <div className="flex items-center gap-2.5 py-6 text-xs font-medium text-[#64748B]">
          <Loader2 className="h-4 w-4 animate-spin text-[#2563EB]" />
          <span>Checking saved event records...</span>
        </div>
      )}

      {/* Event Summary Grid */}
      {summary && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
              <p className="text-[11px] font-semibold text-[#64748B]">Total Detected Objects</p>
              <p className="mt-1 font-display text-2xl font-extrabold text-[#111827]">
                {summary.total_detected_objects}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
              <p className="text-[11px] font-semibold text-[#64748B]">Total Unique Tracks</p>
              <p className="mt-1 font-display text-2xl font-extrabold text-[#111827]">
                {summary.total_unique_tracks}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
              <p className="text-[11px] font-semibold text-[#64748B]">Total Discovered Events</p>
              <p className="mt-1 font-display text-2xl font-extrabold text-[#2563EB]">
                {summary.total_discovered_events}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200/80 bg-[#F5F8FC] p-4">
              <p className="text-[11px] font-semibold text-[#64748B]">Events Requiring Review</p>
              <p className="mt-1 font-display text-2xl font-extrabold text-[#7C3AED]">
                {summary.events_requiring_review}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2.5 rounded-xl border border-slate-200/90 bg-[#F5F8FC] px-4 py-3 text-xs leading-relaxed text-[#111827]">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#2563EB]" />
            <div className="space-y-1">
              <p className="font-medium">{summary.summary_message}</p>
              {summary.important_timestamps.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="font-semibold text-[#64748B]">Important Timestamps:</span>
                  {summary.important_timestamps.map((item, idx) => (
                    <span
                      key={idx}
                      className="rounded-md border border-slate-200 bg-white px-2 py-0.5 font-mono text-[10px] font-semibold text-[#111827]"
                    >
                      {formatHms(item.timestamp_seconds)} · {item.event_title}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Category Filter Pills */}
      {discoveryData && (
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORY_FILTERS.map((filter) => {
            const active = activeFilter === filter.value
            const count =
              filter.value === 'all'
                ? discoveryData.events.length
                : discoveryData.events.filter((e) => e.category === filter.value).length

            return (
              <button
                key={filter.value}
                type="button"
                onClick={() => setActiveFilter(filter.value)}
                className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  active
                    ? 'border-[#2563EB] bg-[#EFF6FF] text-[#2563EB]'
                    : 'border-slate-200 bg-white text-[#64748B] hover:border-slate-300 hover:bg-[#F5F8FC] hover:text-[#111827]'
                }`}
              >
                {filter.label} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Discovered Event Cards or Honest Empty State */}
      {discoveryData && filteredEvents.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-[#F5F8FC] px-6 py-10 text-center">
          <Eye className="mx-auto h-7 w-7 text-[#64748B]" />
          <p className="mt-2.5 text-sm font-semibold text-[#111827]">
            {discoveryData.events.length === 0
              ? 'No supported event patterns identified'
              : 'No events match this category filter'}
          </p>
          <p className="mx-auto mt-1 max-w-md text-xs text-[#64748B]">
            {discoveryData.events.length === 0
              ? 'Click "Discover Events" above to evaluate tracking trajectories, or adjust detection sensitivity if objects were missed.'
              : 'Select another filter category or switch to "All events".'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredEvents.map((evt) => (
            <EventCard key={evt.id} event={evt} />
          ))}
        </div>
      )}
    </motion.section>
  )
}
