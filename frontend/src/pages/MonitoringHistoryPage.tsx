import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  Filter,
  History,
  Loader2,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  TrendingUp,
  Video,
  X,
} from 'lucide-react'
import { motion } from 'motion/react'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { IntelligenceAnalyticsDashboard } from '../components/monitoring/IntelligenceAnalyticsDashboard.tsx'
import { SessionDetailsModal } from '../components/monitoring/SessionDetailsModal.tsx'
import {
  fetchMonitoringHistory,
  type MonitoringHistoryResponse,
} from '../services/monitoringService.ts'

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hrs = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`
  if (mins > 0) return `${mins}m ${secs}s`
  return `${secs}s`
}

function formatDateTime(dtStr: string | null | undefined): string {
  if (!dtStr) return '—'
  const d = new Date(dtStr)
  if (isNaN(d.getTime())) return dtStr
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const STATUS_BADGES: Record<string, string> = {
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  active: 'border-blue-200 bg-blue-50 text-blue-700 animate-pulse',
  stopped: 'border-slate-200 bg-slate-100 text-slate-700',
  processing: 'border-amber-200 bg-amber-50 text-amber-700',
  queued: 'border-slate-200 bg-slate-50 text-slate-600',
  failed: 'border-rose-200 bg-rose-50 text-rose-700',
}

export function MonitoringHistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Tabs: 'history' or 'analytics'
  const currentTab = (searchParams.get('tab') as 'history' | 'analytics') || 'history'

  // Filter States
  const [sessionType, setSessionType] = useState<string>(searchParams.get('type') || 'all')
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get('status') || 'all')
  const [priorityFilter, setPriorityFilter] = useState<string>(searchParams.get('priority') || 'all')
  const [searchQuery, setSearchQuery] = useState<string>(searchParams.get('q') || '')
  const [dateFrom, setDateFrom] = useState<string>(searchParams.get('from') || '')
  const [dateTo, setDateTo] = useState<string>(searchParams.get('to') || '')
  const [currentPage, setCurrentPage] = useState<number>(Number(searchParams.get('page')) || 1)
  const [pageSize, setPageSize] = useState<number>(10)

  // Data States
  const [historyData, setHistoryData] = useState<MonitoringHistoryResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Selected session for details modal
  const [selectedSession, setSelectedSession] = useState<{
    id: string
    type?: 'recorded' | 'live'
  } | null>(null)

  // Load history data
  const loadHistory = useCallback(() => {
    setIsLoading(true)
    setErrorMsg(null)

    let isoFrom: string | undefined = undefined
    let isoTo: string | undefined = undefined
    if (dateFrom) isoFrom = new Date(dateFrom).toISOString()
    if (dateTo) {
      const d = new Date(dateTo)
      d.setHours(23, 59, 59, 999)
      isoTo = d.toISOString()
    }

    fetchMonitoringHistory({
      session_type: sessionType,
      status: statusFilter,
      priority: priorityFilter,
      search: searchQuery,
      date_from: isoFrom,
      date_to: isoTo,
      page: currentPage,
      page_size: pageSize,
    })
      .then((data) => {
        setHistoryData(data)
      })
      .catch((err) => {
        setErrorMsg(err.response?.data?.detail || 'Failed to load monitoring history.')
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [sessionType, statusFilter, priorityFilter, searchQuery, dateFrom, dateTo, currentPage, pageSize])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setCurrentPage(1)
    loadHistory()
  }

  const handleResetFilters = () => {
    setSessionType('all')
    setStatusFilter('all')
    setPriorityFilter('all')
    setSearchQuery('')
    setDateFrom('')
    setDateTo('')
    setCurrentPage(1)
  }

  const handleTabChange = (tab: 'history' | 'analytics') => {
    setSearchParams({ tab })
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#2563EB]">
              <History className="h-3.5 w-3.5 text-[#2563EB]" />
              <span>Unified Intelligence Archive</span>
            </span>
            <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827] sm:text-3xl">
              Monitoring History & Intelligence Analytics
            </h2>
            <p className="mt-1 text-sm text-[#64748B]">
              Comprehensive audit trail of recorded video analyses and live webcam monitoring runs.
            </p>
          </div>

          {/* Navigation Pill Tabs */}
          <div className="flex rounded-2xl border border-slate-200 bg-[#F5F8FC] p-1.5 shadow-2xs">
            <button
              type="button"
              onClick={() => handleTabChange('history')}
              className={`cursor-pointer inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                currentTab === 'history'
                  ? 'bg-white text-[#2563EB] shadow-xs'
                  : 'text-[#64748B] hover:text-[#111827]'
              }`}
            >
              <History className="h-4 w-4" />
              <span>Monitoring History</span>
            </button>
            <button
              type="button"
              onClick={() => handleTabChange('analytics')}
              className={`cursor-pointer inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                currentTab === 'analytics'
                  ? 'bg-white text-[#2563EB] shadow-xs'
                  : 'text-[#64748B] hover:text-[#111827]'
              }`}
            >
              <TrendingUp className="h-4 w-4" />
              <span>Intelligence Analytics</span>
            </button>
          </div>
        </div>
      </motion.section>

      {/* TAB 1: HISTORY TABLE & FILTERS */}
      {currentTab === 'history' && (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-bold text-[#111827]">
                <Filter className="h-4 w-4 text-[#2563EB]" />
                <span>Session Filters</span>
              </div>

              {(sessionType !== 'all' ||
                statusFilter !== 'all' ||
                priorityFilter !== 'all' ||
                searchQuery ||
                dateFrom ||
                dateTo) && (
                <button
                  type="button"
                  onClick={handleResetFilters}
                  className="cursor-pointer text-xs font-semibold text-[#2563EB] hover:underline"
                >
                  Reset all filters
                </button>
              )}
            </div>

            <form onSubmit={handleSearchSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {/* 1. Search Query */}
              <div className="relative lg:col-span-2">
                <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by session name or ID..."
                  className="w-full rounded-xl border border-slate-200 bg-[#F5F8FC] py-2 pr-9 pl-9 text-xs text-[#111827] placeholder:text-slate-400 focus:border-[#2563EB] focus:bg-white focus:ring-2 focus:ring-[#2563EB]/20 focus:outline-none"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchQuery('')
                      setCurrentPage(1)
                    }}
                    className="absolute top-1/2 right-2.5 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              {/* 2. Session Type Filter */}
              <div>
                <select
                  value={sessionType}
                  onChange={(e) => {
                    setSessionType(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-medium text-[#111827] focus:border-[#2563EB] focus:bg-white focus:outline-none"
                >
                  <option value="all">All Monitoring Types</option>
                  <option value="recorded">Recorded Video Analysis</option>
                  <option value="live">Live Webcam Monitoring</option>
                </select>
              </div>

              {/* 3. Processing Status Filter */}
              <div>
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-medium text-[#111827] focus:border-[#2563EB] focus:bg-white focus:outline-none"
                >
                  <option value="all">All Statuses</option>
                  <option value="completed">Completed</option>
                  <option value="active">Active (Live)</option>
                  <option value="stopped">Stopped (Live)</option>
                  <option value="processing">Processing</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              {/* 4. Event Priority Filter */}
              <div>
                <select
                  value={priorityFilter}
                  onChange={(e) => {
                    setPriorityFilter(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="w-full rounded-xl border border-slate-200 bg-[#F5F8FC] px-3 py-2 text-xs font-medium text-[#111827] focus:border-[#2563EB] focus:bg-white focus:outline-none"
                >
                  <option value="all">All Priorities</option>
                  <option value="high">High Priority Incidents</option>
                  <option value="medium">Medium Priority</option>
                  <option value="low">Low Priority</option>
                </select>
              </div>
            </form>

            {/* Date Range inputs */}
            <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-slate-100 text-xs">
              <span className="font-semibold text-slate-500">Date Range:</span>
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => {
                    setDateFrom(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 text-xs text-slate-700 focus:bg-white focus:outline-none"
                />
                <span className="text-slate-400">to</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => {
                    setDateTo(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 text-xs text-slate-700 focus:bg-white focus:outline-none"
                />
              </div>

              <button
                type="button"
                onClick={loadHistory}
                className="cursor-pointer ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1 font-semibold text-[#111827] hover:bg-slate-50 transition-colors"
              >
                <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin text-[#2563EB]' : ''}`} />
                <span>Apply & Refresh</span>
              </button>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-xs">
            {isLoading ? (
              <div className="flex h-64 flex-col items-center justify-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-[#2563EB]" />
                <p className="text-xs font-semibold text-slate-500">Loading monitoring records...</p>
              </div>
            ) : errorMsg ? (
              <div className="p-8 text-center text-rose-700">
                <AlertCircle className="mx-auto h-8 w-8 text-rose-500" />
                <p className="mt-2 text-sm font-bold">Failed to load history</p>
                <p className="text-xs mt-1 text-rose-600">{errorMsg}</p>
              </div>
            ) : historyData && historyData.items.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <History className="mx-auto h-9 w-9 text-slate-300" />
                <p className="mt-2 text-sm font-bold text-slate-700">No monitoring sessions found</p>
                <p className="mt-1 text-xs text-slate-400 max-w-sm mx-auto">
                  Try adjusting your search criteria, clearing filters, or start a new video analysis or live webcam stream.
                </p>
              </div>
            ) : historyData ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                      <th className="py-3.5 pl-6 pr-3">Session & Type</th>
                      <th className="px-3 py-3.5">Timeline</th>
                      <th className="px-3 py-3.5">Duration</th>
                      <th className="px-3 py-3.5">Status</th>
                      <th className="px-3 py-3.5 text-center">Detections</th>
                      <th className="px-3 py-3.5 text-center">Tracks</th>
                      <th className="px-3 py-3.5 text-center">Events</th>
                      <th className="px-3 py-3.5 text-center">Threats</th>
                      <th className="py-3.5 pr-6 pl-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {historyData.items.map((item) => (
                      <tr
                        key={item.session_id}
                        onClick={() =>
                          setSelectedSession({ id: item.session_id, type: item.session_type })
                        }
                        className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                      >
                        {/* Session & Type */}
                        <td className="py-3.5 pl-6 pr-3">
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                                item.session_type === 'live'
                                  ? 'bg-rose-50 text-rose-600'
                                  : 'bg-blue-50 text-[#2563EB]'
                              }`}
                            >
                              {item.session_type === 'live' ? (
                                <Radio className="h-4 w-4" />
                              ) : (
                                <Video className="h-4 w-4" />
                              )}
                            </div>
                            <div className="min-w-0 max-w-xs sm:max-w-sm">
                              <p className="font-semibold text-slate-900 truncate">{item.name}</p>
                              <div className="flex items-center gap-1.5 mt-0.5">
                                <span className="font-mono text-[10px] text-slate-400">
                                  {item.session_id.slice(0, 8)}
                                </span>
                                <span className="text-slate-300">•</span>
                                <span className="font-medium text-[10px] text-slate-500 capitalize">
                                  {item.session_type === 'live' ? 'Live Stream' : 'Recorded'}
                                </span>
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Timeline */}
                        <td className="px-3 py-3.5 text-slate-600 whitespace-nowrap">
                          <p className="font-medium text-slate-800">{formatDateTime(item.start_time)}</p>
                          <p className="text-[10px] text-slate-400">{formatDateTime(item.end_time)}</p>
                        </td>

                        {/* Duration */}
                        <td className="px-3 py-3.5 whitespace-nowrap">
                          <span className="font-mono text-slate-700 font-medium">
                            {formatDuration(item.duration_seconds)}
                          </span>
                        </td>

                        {/* Processing Status */}
                        <td className="px-3 py-3.5 whitespace-nowrap">
                          <span
                            className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase ${
                              STATUS_BADGES[item.status.toLowerCase()] ||
                              'border-slate-200 bg-slate-100 text-slate-700'
                            }`}
                          >
                            {item.status}
                          </span>
                        </td>

                        {/* Detections */}
                        <td className="px-3 py-3.5 text-center font-mono text-slate-700">
                          {item.total_detected_objects}
                        </td>

                        {/* Tracks */}
                        <td className="px-3 py-3.5 text-center font-mono text-slate-700">
                          {item.unique_tracked_objects}
                        </td>

                        {/* Events */}
                        <td className="px-3 py-3.5 text-center font-mono font-semibold text-slate-800">
                          {item.events_discovered}
                        </td>

                        {/* High Priority Threats */}
                        <td className="px-3 py-3.5 text-center">
                          {item.high_priority_events > 0 ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 font-mono text-[10px] font-bold text-rose-700">
                              <ShieldAlert className="h-3 w-3" />
                              {item.high_priority_events}
                            </span>
                          ) : (
                            <span className="font-mono text-[11px] text-slate-400">—</span>
                          )}
                        </td>

                        {/* Action */}
                        <td className="py-3.5 pr-6 pl-3 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setSelectedSession({
                                id: item.session_id,
                                type: item.session_type,
                              })
                            }}
                            className="cursor-pointer inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-[#2563EB] shadow-2xs hover:bg-[#EFF6FF] transition-colors"
                          >
                            <span>Inspect</span>
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {/* Pagination Controls */}
            {historyData && historyData.total > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 px-6 py-4 bg-slate-50/50">
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <div>
                    Showing <span className="font-bold text-slate-800">{(historyData.page - 1) * historyData.page_size + 1}</span> to{' '}
                    <span className="font-bold text-slate-800">
                      {Math.min(historyData.page * historyData.page_size, historyData.total)}
                    </span>{' '}
                    of <span className="font-bold text-slate-800">{historyData.total}</span> sessions
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Rows:</span>
                    <select
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value))
                        setCurrentPage(1)
                      }}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 focus:outline-none"
                    >
                      <option value="10">10</option>
                      <option value="25">25</option>
                      <option value="50">50</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage <= 1 || isLoading}
                    className="cursor-pointer inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition-colors shadow-2xs"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    <span>Previous</span>
                  </button>

                  <span className="px-2 font-mono text-xs text-slate-600">
                    Page {historyData.page} of {historyData.total_pages}
                  </span>

                  <button
                    type="button"
                    onClick={() => setCurrentPage((p) => Math.min(historyData.total_pages, p + 1))}
                    disabled={currentPage >= historyData.total_pages || isLoading}
                    className="cursor-pointer inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition-colors shadow-2xs"
                  >
                    <span>Next</span>
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: INTELLIGENCE ANALYTICS */}
      {currentTab === 'analytics' && <IntelligenceAnalyticsDashboard />}

      {/* Drill-down Session Details Modal */}
      {selectedSession && (
        <SessionDetailsModal
          sessionId={selectedSession.id}
          sessionType={selectedSession.type}
          onClose={() => setSelectedSession(null)}
        />
      )}
    </div>
  )
}
