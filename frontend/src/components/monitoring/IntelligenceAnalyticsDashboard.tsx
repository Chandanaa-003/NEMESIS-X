import {
  Activity,
  BarChart3,
  Clock,
  Layers,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Target,
  TrendingUp,
  Video,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchIntelligenceAnalytics,
  type IntelligenceAnalyticsResponse,
} from '../../services/monitoringService.ts'

function formatHoursMinutes(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  const hrs = Math.floor(s / 3600)
  const mins = Math.floor((s % 3600) / 60)
  const secs = s % 60
  if (hrs > 0) return `${hrs}h ${mins}m`
  if (mins > 0) return `${mins}m ${secs}s`
  return `${secs}s`
}

const CATEGORY_NAMES: Record<string, string> = {
  people_movement: 'People Movement',
  object_interactions: 'Object Interactions',
  possible_unattended_objects: 'Unattended Objects',
  other_activities: 'Other Activities',
}

export function IntelligenceAnalyticsDashboard() {
  const [data, setData] = useState<IntelligenceAnalyticsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Filters
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const loadData = useCallback(() => {
    setIsLoading(true)
    setErrorMsg(null)

    let dateFrom: string | undefined = undefined
    let dateTo: string | undefined = undefined

    const now = new Date()
    if (timeRange === '7d') {
      const d = new Date()
      d.setDate(now.getDate() - 7)
      dateFrom = d.toISOString()
    } else if (timeRange === '30d') {
      const d = new Date()
      d.setDate(now.getDate() - 30)
      dateFrom = d.toISOString()
    } else if (timeRange === '90d') {
      const d = new Date()
      d.setDate(now.getDate() - 90)
      dateFrom = d.toISOString()
    } else if (customFrom || customTo) {
      if (customFrom) dateFrom = new Date(customFrom).toISOString()
      if (customTo) {
        const toD = new Date(customTo)
        toD.setHours(23, 59, 59, 999)
        dateTo = toD.toISOString()
      }
    }

    fetchIntelligenceAnalytics(dateFrom, dateTo)
      .then((res) => {
        setData(res)
      })
      .catch((err) => {
        const status = err.response?.status
        const detail = err.response?.data?.detail
        if (status === 404) {
          setErrorMsg(
            'The analytics API endpoint (/api/v1/monitoring/analytics) returned HTTP 404. Ensure the backend server has been restarted with the latest routes.',
          )
        } else if (status === 401) {
          setErrorMsg('Your session has expired. Please sign in again to view analytics.')
        } else if (!err.response) {
          setErrorMsg('Unable to reach the NEMESIS-X backend API server. Check that the backend is running.')
        } else {
          setErrorMsg(detail || 'Failed to compute analytics metrics from the database.')
        }
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [timeRange, customFrom, customTo])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Calculate max values for SVG chart scaling
  const maxTrendEvents = useMemo(() => {
    if (!data?.timeline_trends || data.timeline_trends.length === 0) return 10
    const m = Math.max(...data.timeline_trends.map((t) => Math.max(t.events_count, t.sessions_count)))
    return Math.max(m, 5)
  }, [data])

  return (
    <div className="space-y-6">
      {/* Analytics Filter Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#2563EB]">
            <TrendingUp className="h-3.5 w-3.5 text-[#2563EB]" />
            <span>Database Intelligence Analytics</span>
          </span>
          <h3 className="mt-2 font-display text-xl font-extrabold text-[#111827]">
            Operational Intelligence Metrics
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Real spatial-temporal telemetry aggregated across recorded analyses and live monitoring streams.
          </p>
        </div>

        {/* Date presets & reload */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl border border-slate-200 bg-slate-50 p-1">
            {(
              [
                { id: '7d', label: 'Last 7 Days' },
                { id: '30d', label: 'Last 30 Days' },
                { id: '90d', label: 'Last 90 Days' },
                { id: 'all', label: 'All Time' },
              ] as const
            ).map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => {
                  setCustomFrom('')
                  setCustomTo('')
                  setTimeRange(preset.id)
                }}
                className={`cursor-pointer rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  timeRange === preset.id && !customFrom && !customTo
                    ? 'bg-white text-[#2563EB] shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={loadData}
            disabled={isLoading}
            className="cursor-pointer inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50 hover:text-[#2563EB] disabled:opacity-50 transition-colors shadow-2xs"
            title="Refresh analytics data"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin text-[#2563EB]' : ''}`} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[#2563EB]" />
          <p className="text-xs font-semibold text-slate-500">Computing intelligence statistics from database records...</p>
        </div>
      ) : errorMsg ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-rose-700 space-y-3">
          <p className="font-bold text-sm">Failed to load analytics</p>
          <p className="text-xs max-w-lg mx-auto">{errorMsg}</p>
          <button
            type="button"
            onClick={loadData}
            className="cursor-pointer inline-flex items-center gap-1.5 rounded-xl border border-rose-300 bg-white px-4 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry</span>
          </button>
        </div>
      ) : data && data.total_sessions === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <BarChart3 className="mx-auto h-9 w-9 text-slate-300" />
          <p className="mt-3 text-sm font-bold text-slate-800">No Monitoring History Yet</p>
          <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
            No recorded video analyses or live webcam sessions were found for this date range. Run an
            analysis or start live monitoring to populate real intelligence metrics.
          </p>
        </div>
      ) : data ? (
        <div className="space-y-6">
          {/* KPI Summary Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Total Monitored Sessions</span>
                <span className="rounded-lg bg-blue-50 p-2 text-[#2563EB]">
                  <Video className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-2 font-display text-3xl font-extrabold text-[#111827]">
                {data.total_sessions}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                <span className="font-medium text-blue-700">{data.recorded_sessions_count} Recorded</span>
                <span>•</span>
                <span className="font-medium text-rose-600">{data.live_sessions_count} Live</span>
                <span>•</span>
                <span className="font-medium text-emerald-700">{data.completed_analyses_count} Done</span>
                {data.failed_analyses_count > 0 && (
                  <>
                    <span>•</span>
                    <span className="font-medium text-rose-700">{data.failed_analyses_count} Failed</span>
                  </>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Operational Duration</span>
                <span className="rounded-lg bg-violet-50 p-2 text-[#7C3AED]">
                  <Clock className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-2 font-display text-3xl font-extrabold text-[#111827]">
                {formatHoursMinutes(data.total_duration_seconds)}
              </p>
              <p className="mt-2 text-[11px] text-slate-500 font-mono">
                Avg {formatHoursMinutes(data.avg_processing_duration_seconds)} · {data.total_frames_processed.toLocaleString()} frames
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Discovered Events</span>
                <span className="rounded-lg bg-amber-50 p-2 text-amber-600">
                  <Activity className="h-4 w-4" />
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <p className="font-display text-3xl font-extrabold text-[#111827]">
                  {data.total_events}
                </p>
                {data.anomaly_events > 0 && (
                  <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-bold text-rose-700">
                    {data.anomaly_events} Anomalies
                  </span>
                )}
              </div>
              <p className="mt-2 text-[11px] text-slate-500">
                {data.high_priority_events} High · {data.medium_priority_events} Med · {data.low_priority_events} Low
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500">Tracked Trajectories</span>
                <span className="rounded-lg bg-emerald-50 p-2 text-emerald-600">
                  <Target className="h-4 w-4" />
                </span>
              </div>
              <p className="mt-2 font-display text-3xl font-extrabold text-[#111827]">
                {data.total_unique_tracks}
              </p>
              <p className="mt-2 text-[11px] text-slate-500">
                {data.total_detections.toLocaleString()} raw bounding box detections
              </p>
            </div>
          </div>

          {/* Timeline Activity Trend Chart */}
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h4 className="font-display text-base font-bold text-[#111827]">Activity & Incident Timeline</h4>
                <p className="text-xs text-slate-500">Daily frequency of analyzed sessions and discovered events.</p>
              </div>

              <div className="flex items-center gap-4 text-xs font-medium">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-[#2563EB]" />
                  <span className="text-slate-600">Events Discovered</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-rose-500" />
                  <span className="text-slate-600">High Priority</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-slate-300" />
                  <span className="text-slate-600">Sessions</span>
                </div>
              </div>
            </div>

            {data.timeline_trends.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 p-12 text-center text-slate-400">
                <BarChart3 className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-2 text-xs font-semibold text-slate-600">No trend points in selected date range</p>
              </div>
            ) : (
              <div className="h-48 w-full flex items-end gap-2 pt-6 pb-2 px-2 overflow-x-auto">
                {data.timeline_trends.map((pt) => {
                  const eventHeight = Math.max(4, Math.round((pt.events_count / maxTrendEvents) * 140))
                  const sessionHeight = Math.max(4, Math.round((pt.sessions_count / maxTrendEvents) * 140))

                  return (
                    <div
                      key={pt.date}
                      className="group relative flex-1 min-w-[28px] max-w-[48px] flex flex-col items-center justify-end h-full gap-1"
                    >
                      {/* Tooltip */}
                      <div className="pointer-events-none absolute -top-12 z-20 hidden -translate-y-2 group-hover:flex flex-col items-center rounded-lg bg-slate-900 px-2 py-1 text-[10px] text-white shadow-lg whitespace-nowrap">
                        <span className="font-bold">{pt.date}</span>
                        <span>{pt.events_count} events · {pt.high_priority_count} high · {pt.sessions_count} sessions</span>
                      </div>

                      {/* Bar columns */}
                      <div className="w-full flex items-end justify-center gap-1 h-36">
                        {/* Session bar */}
                        <div
                          className="w-1.5 rounded-t bg-slate-300 hover:bg-slate-400 transition-all"
                          style={{ height: `${sessionHeight}px` }}
                        />
                        {/* Event bar */}
                        <div
                          className={`w-2.5 rounded-t transition-all ${
                            pt.high_priority_count > 0 ? 'bg-rose-500' : 'bg-[#2563EB]'
                          }`}
                          style={{ height: `${eventHeight}px` }}
                        />
                      </div>

                      <span className="text-[10px] text-slate-400 font-mono rotate-45 sm:rotate-0 mt-1 truncate">
                        {pt.date.slice(5)}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Secondary Details Grid */}
          <div className="grid gap-6 md:grid-cols-3">
            {/* 1. Threat Severity Breakdown */}
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
              <h4 className="font-display text-sm font-bold text-[#111827] flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-rose-600" />
                <span>Threat Severity Distribution</span>
              </h4>

              <div className="space-y-3">
                {[
                  {
                    label: 'High Priority Threats',
                    count: data.high_priority_events,
                    bg: 'bg-rose-500',
                    badge: 'border-rose-200 bg-rose-50 text-rose-700',
                  },
                  {
                    label: 'Medium Severity Events',
                    count: data.medium_priority_events,
                    bg: 'bg-amber-500',
                    badge: 'border-amber-200 bg-amber-50 text-amber-700',
                  },
                  {
                    label: 'Low Severity Activities',
                    count: data.low_priority_events,
                    bg: 'bg-blue-500',
                    badge: 'border-blue-200 bg-blue-50 text-blue-700',
                  },
                ].map((item) => {
                  const pct = data.total_events > 0 ? Math.round((item.count / data.total_events) * 100) : 0
                  return (
                    <div key={item.label} className="space-y-1 text-xs">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-slate-700">{item.label}</span>
                        <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold ${item.badge}`}>
                          {item.count} ({pct}%)
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div className={`h-full ${item.bg} rounded-full`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* 2. Discovered Event Categories */}
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
              <h4 className="font-display text-sm font-bold text-[#111827] flex items-center gap-2">
                <Layers className="h-4 w-4 text-[#7C3AED]" />
                <span>Event Categories</span>
              </h4>

              {Object.keys(data.events_by_category).length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No categorized events recorded.</p>
              ) : (
                <div className="space-y-2.5">
                  {Object.entries(data.events_by_category).map(([catKey, cnt]) => {
                    const label = CATEGORY_NAMES[catKey] || catKey.replace('_', ' ')
                    const pct = data.total_events > 0 ? Math.round((cnt / data.total_events) * 100) : 0
                    return (
                      <div key={catKey} className="text-xs space-y-1">
                        <div className="flex justify-between">
                          <span className="font-medium text-slate-700 capitalize">{label}</span>
                          <span className="font-mono text-slate-500 font-semibold">{cnt}</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                          <div className="h-full bg-[#7C3AED] rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* 3. Top Detected Classes */}
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
              <h4 className="font-display text-sm font-bold text-[#111827] flex items-center gap-2">
                <Target className="h-4 w-4 text-[#2563EB]" />
                <span>Top Detected Classes</span>
              </h4>

              {data.top_object_classes.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No detected objects recorded yet.</p>
              ) : (
                <div className="space-y-2.5">
                  {data.top_object_classes.slice(0, 5).map((cls) => {
                    const maxCount = data.top_object_classes[0]?.count || 1
                    const pct = Math.round((cls.count / maxCount) * 100)
                    return (
                      <div key={cls.class_name} className="text-xs space-y-1">
                        <div className="flex justify-between">
                          <span className="font-medium text-slate-700 capitalize">{cls.class_name}</span>
                          <span className="font-mono text-slate-500 font-semibold">{cls.count}</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                          <div className="h-full bg-[#2563EB] rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
