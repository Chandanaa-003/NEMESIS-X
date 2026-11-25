import { AlertCircle, Clock3, Film, ImageOff, Loader2, Search, Video } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import {
  fetchSearchEvidenceBlobUrl,
  searchVideoIntelligence,
  type IntelligenceSearchFilters,
  type IntelligenceSearchResponse,
  type IntelligenceSearchResult,
} from '../services/intelligenceSearchService'
import { getAuthErrorMessage } from '../services/authService'
import { fetchVideoBlobUrl } from '../services/videoService'

const QUERY_EXAMPLES = [
  'Find when a person approached a backpack',
  'Show possible pickup events',
  'Find objects left stationary',
  'When did P001 enter the restricted zone?',
  'Show all interactions involving O001',
  'Find unusual movement sequences',
  'Show events between 00:01:00 and 00:02:00',
  'Find all available evidence for P001',
]

function formatTime(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const remaining = safe % 60
  return hours > 0
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
}

function SearchEvidenceThumbnail({
  result,
  onOpen,
}: {
  result: IntelligenceSearchResult
  onOpen: (url: string, title: string) => void
}) {
  const evidence = result.evidence[0]
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!evidence) return
    let active = true
    let createdUrl: string | null = null
    fetchSearchEvidenceBlobUrl(evidence.image_url)
      .then((url) => {
        if (!active) {
          URL.revokeObjectURL(url)
          return
        }
        createdUrl = url
        setImageUrl(url)
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [evidence])

  if (!evidence || failed) {
    return (
      <div className="flex h-24 w-36 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-[#F5F8FC] text-[#64748B]">
        <ImageOff className="h-5 w-5" />
      </div>
    )
  }
  if (!imageUrl) return <div className="h-24 w-36 shrink-0 animate-pulse rounded-xl bg-slate-100" />
  return (
    <button
      type="button"
      onClick={() => onOpen(imageUrl, `${result.title} evidence at ${formatTime(evidence.timestamp_seconds)}`)}
      className="shrink-0 rounded-xl focus-visible:outline-2 focus-visible:outline-[#2563EB]"
      aria-label={`Open evidence for ${result.title}`}
    >
      <img src={imageUrl} alt={`Evidence for ${result.title}`} className="h-24 w-36 rounded-xl border border-slate-200 object-cover" />
    </button>
  )
}

export function IntelligentVideoSearchPage() {
  const [query, setQuery] = useState('')
  const [sourceType, setSourceType] = useState<'all' | 'analysis' | 'live_session'>('all')
  const [className, setClassName] = useState('')
  const [eventType, setEventType] = useState('')
  const [trackCode, setTrackCode] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [severity, setSeverity] = useState('all')
  const [response, setResponse] = useState<IntelligenceSearchResponse | null>(null)
  const [activeFilters, setActiveFilters] = useState<IntelligenceSearchFilters | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewerError, setViewerError] = useState<string | null>(null)
  const [activeViewer, setActiveViewer] = useState<{ type: 'video' | 'image'; url: string; result: IntelligenceSearchResult; title: string } | null>(null)
  const [isOpeningVideo, setIsOpeningVideo] = useState(false)

  useEffect(() => {
    return () => {
      if (activeViewer?.type === 'video') URL.revokeObjectURL(activeViewer.url)
    }
  }, [activeViewer])

  const buildFilters = (searchQuery: string): IntelligenceSearchFilters => {
    const enteredTrack = trackCode.trim()
    const parsedTrack = enteredTrack.match(/^([POT])?\s*0*(\d+)$/i)
    const queryWithRole = parsedTrack?.[1] && /^[PO]$/i.test(parsedTrack[1])
      ? `${searchQuery} ${enteredTrack}`.trim()
      : searchQuery
    return {
      q: queryWithRole,
      source_type: sourceType,
      class_name: className.trim() || undefined,
      event_type: eventType.trim() || undefined,
      track_id: parsedTrack ? Number(parsedTrack[2]) : undefined,
      start_seconds: startTime.trim() ? Number(startTime) : undefined,
      end_seconds: endTime.trim() ? Number(endTime) : undefined,
      limit: 50,
      offset: 0,
    }
  }

  const runSearch = async (searchQuery = query) => {
    setIsLoading(true)
    setError(null)
    setResponse(null)
    try {
      if (trackCode.trim() && !/^[POT]?\s*0*\d+$/i.test(trackCode.trim())) {
        throw new Error('Enter a valid source-local track ID such as T001, P001, or O001.')
      }
      const filters = buildFilters(searchQuery)
      if (filters.track_id !== undefined && !Number.isSafeInteger(filters.track_id)) {
        throw new Error('Enter a valid source-local track ID such as T001 or P001.')
      }
      if (
        (filters.start_seconds !== undefined && (!Number.isFinite(filters.start_seconds) || filters.start_seconds < 0)) ||
        (filters.end_seconds !== undefined && (!Number.isFinite(filters.end_seconds) || filters.end_seconds < 0))
      ) {
        throw new Error('Time filters must be non-negative seconds.')
      }
      if (filters.start_seconds !== undefined && filters.end_seconds !== undefined && filters.start_seconds > filters.end_seconds) {
        throw new Error('Start time must not exceed end time.')
      }
      const result = await searchVideoIntelligence(filters)
      setActiveFilters(filters)
      setResponse(result)
    } catch (requestError) {
      setError(
        requestError instanceof Error &&
            (requestError.message.startsWith('Enter a valid') ||
              requestError.message.toLowerCase().includes('time'))
            ? requestError.message
            : getAuthErrorMessage(requestError, 'Intelligent video search failed.'),
      )
    } finally {
      setIsLoading(false)
    }
  }

  const loadMore = async () => {
    if (!activeFilters || !response?.has_more || isLoadingMore) return
    setIsLoadingMore(true)
    setError(null)
    try {
      const next = await searchVideoIntelligence({
        ...activeFilters,
        offset: response.offset + response.results.length,
      })
      setResponse((current) =>
        current
          ? {
              ...next,
              results: [...current.results, ...next.results],
            }
          : next,
      )
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, 'Could not load more search results.'))
    } finally {
      setIsLoadingMore(false)
    }
  }

  const openEvidence = (url: string, title: string, result: IntelligenceSearchResult) => {
    setViewerError(null)
    setActiveViewer({ type: 'image', url, title, result })
  }

  const openVideo = async (result: IntelligenceSearchResult) => {
    setViewerError(null)
    if (!result.video_id) {
      setViewerError('Continuous live video is not archived for this session. Stored event evidence may still be available above.')
      return
    }
    setIsOpeningVideo(true)
    try {
      const url = await fetchVideoBlobUrl(result.video_id)
      setActiveViewer({ type: 'video', url, result, title: result.source_label })
    } catch (openError) {
      setViewerError(getAuthErrorMessage(openError, 'Could not open this recorded video.'))
    } finally {
      setIsOpeningVideo(false)
    }
  }

  const visibleResults = (response?.results ?? []).filter(
    (result) => severity === 'all' || result.severity?.toLowerCase() === severity,
  )

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-5 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              <Search className="h-3.5 w-3.5" /> Local Intelligence Search
            </span>
            <h1 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827]">
              Intelligent Video Search
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-[#64748B]">
              Search stored detections, tracks, events, and evidence. Queries are parsed deterministically and never send video to external services. Track IDs are source-local; matching codes across videos are not shared identities.
            </p>
          </div>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            void runSearch()
          }}
          className="space-y-4"
        >
          <label htmlFor="intelligence-query" className="sr-only">Search analyzed video intelligence</label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="intelligence-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ask about an event, object, track ID, or timestamp..."
              maxLength={500}
              className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-[#F8FAFC] px-4 py-3 text-sm text-[#111827] outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-blue-100"
            />
            <button type="submit" disabled={isLoading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#2563EB] px-5 py-3 text-sm font-bold text-white disabled:opacity-60">
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Search
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <label className="text-xs font-semibold text-slate-700">
              Data source
              <select value={sourceType} onChange={(event) => setSourceType(event.target.value as typeof sourceType)} className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2">
                <option value="all">All stored sources</option><option value="analysis">Recorded analysis</option><option value="live_session">Live sessions</option>
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Object class
              <input value={className} onChange={(event) => setClassName(event.target.value)} placeholder="e.g. backpack" className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2" />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Event type
              <input value={eventType} onChange={(event) => setEventType(event.target.value)} placeholder="e.g. zone_entry" className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2" />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Track ID
              <input value={trackCode} onChange={(event) => setTrackCode(event.target.value)} placeholder="T001 / P001" className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2" />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              From (seconds)
              <input type="number" min="0" step="0.1" value={startTime} onChange={(event) => setStartTime(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2" />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              To (seconds)
              <input type="number" min="0" step="0.1" value={endTime} onChange={(event) => setEndTime(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-200 px-2.5 py-2" />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-semibold text-slate-700">
              Severity
              <select value={severity} onChange={(event) => setSeverity(event.target.value)} className="ml-2 rounded-lg border border-slate-200 bg-white px-2.5 py-2">
                <option value="all">All</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
              </select>
            </label>
          </div>
        </form>

        <div className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Suggested searches</p>
          <div className="flex flex-wrap gap-2">
            {QUERY_EXAMPLES.map((example) => (
              <button key={example} type="button" onClick={() => { setQuery(example); void runSearch(example) }} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-left text-xs text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700">
                {example}
              </button>
            ))}
          </div>
        </div>
      </motion.section>

      {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      {viewerError && <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{viewerError}</div>}
      {isLoading && <div className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white py-12 text-sm text-slate-500"><Loader2 className="h-5 w-5 animate-spin" />Searching your stored intelligence…</div>}

      {response && !isLoading && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold text-[#111827]">Search results</h2>
              <p className="text-xs text-[#64748B]">{response.message} {visibleResults.length !== response.results.length ? `Showing ${visibleResults.length} after severity filter.` : ''}</p>
            </div>
            <span className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-800">{response.total} result{response.total === 1 ? '' : 's'}</span>
          </div>
          {!response.supported_query && <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{response.message}</p>}
          {response.supported_query && visibleResults.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
              <Search className="mx-auto h-7 w-7 text-slate-400" />
              <p className="mt-3 text-sm font-semibold text-slate-700">No matching stored records</p>
              <p className="mt-1 text-xs text-slate-500">Try another class, event term, track ID, or time range.</p>
            </div>
          )}
          <div className="space-y-3">
            {visibleResults.map((result) => (
              <article key={result.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs sm:p-5">
                <div className="flex flex-col gap-4 sm:flex-row">
                  {result.evidence.length > 0 && (
                    <SearchEvidenceThumbnail
                      result={result}
                      onOpen={(url, title) => openEvidence(url, title, result)}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-blue-700">{result.result_type}</span>
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">{result.event_category}</span>
                      {result.severity && <span className="rounded-md bg-amber-50 px-2 py-1 text-[10px] font-semibold capitalize text-amber-800">{result.severity}</span>}
                    </div>
                    <h3 className="mt-2 text-sm font-bold text-slate-900">{result.title}</h3>
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">{result.explanation}</p>
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                      <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{formatTime(result.timestamp_seconds)}</span>
                      <span className="inline-flex items-center gap-1"><Film className="h-3 w-3" />{result.source_label}</span>
                      {result.track_labels.map((label) => <span key={label} className="font-mono font-semibold text-blue-700">{label}</span>)}
                      {result.confidence !== null && <span>{Math.round(result.confidence * 100)}% confidence</span>}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {result.video_id && (
                        <button type="button" disabled={isOpeningVideo} onClick={() => void openVideo(result)} className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60">
                          {isOpeningVideo ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}Open recorded video at {formatTime(result.timestamp_seconds)}
                        </button>
                      )}
                      {result.evidence.length > 0 && <span className="self-center text-[10px] text-slate-500">{result.evidence.length} evidence reference(s)</span>}
                      {!result.video_id && <span className="self-center text-[10px] text-slate-500">Live video is not archived.</span>}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
          {response.has_more && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => void loadMore()}
                disabled={isLoadingMore}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                {isLoadingMore && <Loader2 className="h-4 w-4 animate-spin" />}
                Load more results
              </button>
            </div>
          )}
        </section>
      )}

      {activeViewer && (
        <div role="dialog" aria-modal="true" aria-label="Search evidence viewer" className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4" onClick={() => setActiveViewer(null)}>
          <div className="max-h-[92vh] w-full max-w-5xl overflow-auto rounded-2xl bg-white p-4 shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div><h2 className="text-sm font-bold text-slate-900">{activeViewer.title}</h2><p className="text-xs text-slate-500">{activeViewer.result.source_label} · {formatTime(activeViewer.result.timestamp_seconds)}</p></div>
              <button type="button" onClick={() => setActiveViewer(null)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700">Close</button>
            </div>
            {activeViewer.type === 'image' ? (
              <img src={activeViewer.url} alt={activeViewer.title} className="mx-auto max-h-[78vh] max-w-full object-contain" />
            ) : (
              <video
                src={activeViewer.url}
                controls
                autoPlay
                onLoadedMetadata={(event) => { event.currentTarget.currentTime = activeViewer.result.timestamp_seconds }}
                className="max-h-[78vh] w-full rounded-xl bg-black"
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
