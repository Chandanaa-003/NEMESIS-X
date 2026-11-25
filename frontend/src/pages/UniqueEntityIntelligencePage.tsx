import {
  AlertCircle,
  ArrowUpRight,
  Clock3,
  Fingerprint,
  ImageOff,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { listUserAnalyses, type AnalysisListItem } from '../services/analysisService.ts'
import {
  correctIdentityTrack,
  getIdentity,
  getIdentityCounts,
  getIdentityEvidence,
  searchIdentities,
  type EntityIdentity,
  type IdentityCounts,
  type IdentityEntityType,
  type IdentitySourceType,
} from '../services/identityService.ts'
import { listLiveMonitoringSessions, type LiveSessionStatusResponse } from '../services/liveService.ts'

interface IdentitySourceOption {
  type: IdentitySourceType
  id: string
  label: string
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainder = total % 60
  return [hours, minutes, remainder].map((part) => String(part).padStart(2, '0')).join(':')
}

function confidenceLabel(value: number | null): string {
  return value === null ? 'Not available' : `${Math.round(value * 100)}% appearance similarity`
}

function sourceOptions(
  analyses: AnalysisListItem[],
  sessions: LiveSessionStatusResponse[],
): IdentitySourceOption[] {
  return [
    ...analyses
      .filter((item) => item.status === 'completed')
      .map((item) => ({
        type: 'analysis' as const,
        id: item.analysis_id,
        label: `Video · ${item.video_filename}`,
      })),
    ...sessions.map((item) => ({
      type: 'live_session' as const,
      id: item.session_id,
      label: `Live session · ${new Date(item.started_at).toLocaleString()} · ${item.status}`,
    })),
  ]
}

export function UniqueEntityIntelligencePage() {
  const [sources, setSources] = useState<IdentitySourceOption[]>([])
  const [sourceKey, setSourceKey] = useState('')
  const [loadedSourceKey, setLoadedSourceKey] = useState('')
  const [identities, setIdentities] = useState<EntityIdentity[]>([])
  const [targetIdentities, setTargetIdentities] = useState<EntityIdentity[]>([])
  const [counts, setCounts] = useState<IdentityCounts | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<EntityIdentity | null>(null)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<IdentityEntityType | ''>('')
  const [minAppearances, setMinAppearances] = useState('1')
  const [firstSeenFrom, setFirstSeenFrom] = useState('')
  const [lastSeenTo, setLastSeenTo] = useState('')
  const [eventType, setEventType] = useState('')
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null)
  const [targetIdentityId, setTargetIdentityId] = useState('')
  const [correctionNote, setCorrectionNote] = useState('')
  const [evidence, setEvidence] = useState<{ key: string; url: string } | null>(null)
  const [loadingSources, setLoadingSources] = useState(true)
  const [savingCorrection, setSavingCorrection] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([listUserAnalyses(), listLiveMonitoringSessions()])
      .then(([analysisRows, sessionRows]) => {
        if (!active) return
        const options = sourceOptions(analysisRows, sessionRows)
        setSources(options)
        setSourceKey(options[0] ? `${options[0].type}:${options[0].id}` : '')
      })
      .catch(() => {
        if (active) setError('Could not load your recorded analyses and live sessions.')
      })
      .finally(() => {
        if (active) setLoadingSources(false)
      })
    return () => {
      active = false
    }
  }, [])

  const selectedSource = useMemo(
    () => sources.find((option) => `${option.type}:${option.id}` === sourceKey),
    [sourceKey, sources],
  )

  useEffect(() => {
    if (!selectedSource) {
      return
    }
    let active = true
    Promise.all([
      searchIdentities({
        sourceType: selectedSource.type,
        sourceId: selectedSource.id,
        limit: 200,
      }),
      getIdentityCounts(selectedSource.type, selectedSource.id),
    ])
      .then(([result, summary]) => {
        if (!active) return
        setSelectedId('')
        setIdentities(result.items)
        setTargetIdentities(result.items)
        setCounts(summary)
        setLoadedSourceKey(`${selectedSource.type}:${selectedSource.id}`)
        setError('')
      })
      .catch(() => {
        if (active) setError('Could not load identities for this source.')
      })
    return () => {
      active = false
    }
  }, [selectedSource])

  const sourceLoaded = sourceKey !== '' && loadedSourceKey === sourceKey
  const sourceTargetIdentities = sourceLoaded ? targetIdentities : []

  useEffect(() => {
    if (!selectedSource || !sourceLoaded) return
    let active = true
    const timer = window.setTimeout(() => {
      searchIdentities({
        sourceType: selectedSource.type,
        sourceId: selectedSource.id,
        entityType: typeFilter,
        query: search,
        minAppearances: Number(minAppearances) || 1,
        firstSeenFrom: firstSeenFrom === '' ? undefined : Number(firstSeenFrom),
        lastSeenTo: lastSeenTo === '' ? undefined : Number(lastSeenTo),
        eventType,
        limit: 200,
      })
        .then((result) => {
          if (active) setIdentities(result.items)
        })
        .catch(() => {
          if (active) setError('Could not apply identity search filters.')
        })
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [
    eventType,
    firstSeenFrom,
    lastSeenTo,
    minAppearances,
    search,
    selectedSource,
    sourceLoaded,
    typeFilter,
  ])

  const visibleIdentities = useMemo(() => {
    if (!sourceLoaded) return []
    const term = search.trim().toLowerCase()
    const minimum = Number(minAppearances) || 1
    return identities.filter((identity) => {
      if (typeFilter && identity.entity_type !== typeFilter) return false
      if (identity.appearance_count < minimum) return false
      if (!term) return true
      return [
        identity.identity_code,
        identity.category,
        ...identity.associated_track_codes,
      ].some((value) => value.toLowerCase().includes(term))
    })
  }, [identities, minAppearances, search, sourceLoaded, typeFilter])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    getIdentity(selectedId)
      .then((result) => {
        if (!active) return
        setDetail(result)
        setSelectedTrackId(result.track_appearances?.[0]?.track_id ?? null)
        setTargetIdentityId('')
        setCorrectionNote('')
      })
      .catch(() => {
        if (active) setError('Could not load the selected identity details.')
      })
    return () => {
      active = false
    }
  }, [selectedId])

  const visibleDetail = detail?.id === selectedId && sourceLoaded ? detail : null
  const selectedTrack = visibleDetail?.track_appearances?.find(
    (track) => track.track_id === selectedTrackId,
  )
  const selectedDetailId = visibleDetail?.id ?? ''
  const evidenceTrackId = selectedTrack?.evidence_url ? selectedTrack.track_id : null
  const currentEvidenceKey =
    selectedDetailId && evidenceTrackId !== null
      ? `${selectedDetailId}:${evidenceTrackId}`
      : ''
  const evidenceUrl = evidence?.key === currentEvidenceKey ? evidence.url : ''

  useEffect(() => {
    if (!selectedDetailId || evidenceTrackId === null) return
    let active = true
    let objectUrl = ''
    getIdentityEvidence(selectedDetailId, evidenceTrackId)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setEvidence({ key: `${selectedDetailId}:${evidenceTrackId}`, url: objectUrl })
      })
      .catch(() => undefined)
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [evidenceTrackId, selectedDetailId])

  const refreshSource = async (selectIdentityId?: string) => {
    if (!selectedSource) return
    setError('')
    const [result, summary] = await Promise.all([
      searchIdentities({
        sourceType: selectedSource.type,
        sourceId: selectedSource.id,
        limit: 200,
      }),
      getIdentityCounts(selectedSource.type, selectedSource.id),
    ])
    setIdentities(result.items)
    setTargetIdentities(result.items)
    setCounts(summary)
    if (selectIdentityId) setSelectedId(selectIdentityId)
  }

  const submitCorrection = async (createNewIdentity: boolean) => {
    if (!detail || selectedTrackId === null) return
    if (!createNewIdentity && !targetIdentityId) {
      setError('Choose an existing identity or create a separate identity.')
      return
    }
    setSavingCorrection(true)
    setError('')
    setNotice('')
    try {
      const corrected = await correctIdentityTrack({
        identityId: detail.id,
        trackId: selectedTrackId,
        targetIdentityId: createNewIdentity ? undefined : targetIdentityId,
        createNewIdentity,
        correctionNote,
      })
      await refreshSource(corrected.id)
      setDetail(corrected)
      setNotice(`Track ${selectedTrack?.track_code ?? `T${selectedTrackId}`} correction saved.`)
    } catch {
      setError('Could not save this identity correction. Refresh and try again.')
    } finally {
      setSavingCorrection(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-violet-100 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
            <Fingerprint className="h-3.5 w-3.5" />
            Anonymous, source-scoped visual matching
          </div>
          <h1 className="mt-3 font-display text-2xl font-extrabold text-slate-950 sm:text-3xl">
            Unique Entity Intelligence
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Review probable appearances, original tracker fragments, events, and stored evidence.
            Labels are anonymous and never connect people across videos or sessions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refreshSource(selectedId)}
          disabled={!selectedSource || !sourceLoaded}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </header>

      {(error || notice) && (
        <div
          role={error ? 'alert' : 'status'}
          className={`flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${
            error
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
          }`}
        >
          {error ? <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> : <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />}
          <span>{error || notice}</span>
        </div>
      )}

      <section className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs md:grid-cols-[minmax(240px,1fr)_repeat(4,minmax(100px,0.5fr))]">
        <label className="text-xs font-semibold text-slate-600">
          Recording or session
          <select
            value={sourceKey}
            onChange={(event) => setSourceKey(event.target.value)}
            disabled={loadingSources || sources.length === 0}
            className="mt-1.5 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800"
          >
            {sources.length === 0 && <option value="">No sources available</option>}
            {sources.map((source) => (
              <option key={`${source.type}:${source.id}`} value={`${source.type}:${source.id}`}>
                {source.label}
              </option>
            ))}
          </select>
        </label>
        {[
            { label: 'Unique people', value: sourceLoaded ? counts?.unique_people ?? '—' : '—', icon: Users },
            { label: 'Unique objects', value: sourceLoaded ? counts?.unique_objects ?? '—' : '—', icon: Fingerprint },
            { label: 'Probable', value: sourceLoaded ? counts?.probable ?? '—' : '—', icon: ShieldCheck },
            { label: 'Unresolved', value: sourceLoaded ? counts?.unknown ?? '—' : '—', icon: AlertCircle },
        ].map((item) => {
          const Icon = item.icon
          return (
            <div key={item.label} className="rounded-xl bg-slate-50 px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500">
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </div>
              <p className="mt-1 text-xl font-bold text-slate-900">{item.value}</p>
            </div>
          )
        })}
      </section>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.5fr)]">
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
          <div className="border-b border-slate-100 p-4">
            <h2 className="font-display text-base font-bold text-slate-900">Identity registry</h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_auto]">
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="P001, T008, backpack…"
                  className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400"
                />
              </label>
              <select
                value={typeFilter}
                onChange={(event) => {
                  const value = event.target.value
                  if (value === '' || value === 'person' || value === 'object') {
                    setTypeFilter(value)
                  }
                }}
                aria-label="Filter by entity type"
                className="rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              >
                <option value="">All types</option>
                <option value="person">People</option>
                <option value="object">Objects</option>
              </select>
              <select
                value={minAppearances}
                onChange={(event) => setMinAppearances(event.target.value)}
                aria-label="Minimum appearances"
                className="rounded-lg border border-slate-200 px-2.5 py-2 text-sm"
              >
                <option value="1">1+ appearances</option>
                <option value="2">2+ appearances</option>
                <option value="3">3+ appearances</option>
              </select>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <label className="text-[11px] font-medium text-slate-500">
                First seen from (seconds)
                <input
                  type="number"
                  min="0"
                  value={firstSeenFrom}
                  onChange={(event) => setFirstSeenFrom(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-800"
                />
              </label>
              <label className="text-[11px] font-medium text-slate-500">
                Last seen through (seconds)
                <input
                  type="number"
                  min="0"
                  value={lastSeenTo}
                  onChange={(event) => setLastSeenTo(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-800"
                />
              </label>
              <label className="text-[11px] font-medium text-slate-500">
                Related event type
                <input
                  value={eventType}
                  onChange={(event) => setEventType(event.target.value)}
                  placeholder="interaction, zone_entry…"
                  className="mt-1 w-full rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-800"
                />
              </label>
            </div>
          </div>
          <div className="max-h-[650px] divide-y divide-slate-100 overflow-y-auto">
            {!sourceLoaded && selectedSource ? (
              <div className="flex items-center justify-center gap-2 px-4 py-12 text-sm text-slate-500">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Loading source identities…
              </div>
            ) : visibleIdentities.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <Fingerprint className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-semibold text-slate-700">
                  {identities.length ? 'No identities match these filters' : 'No identity records yet'}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {identities.length
                    ? 'Try another ID, track, category, or appearance count.'
                    : 'A registry is available after analysis stores tracked appearance data.'}
                </p>
              </div>
            ) : (
              visibleIdentities.map((identity) => (
                <button
                  key={identity.id}
                  type="button"
                  onClick={() => setSelectedId(identity.id)}
                  className={`w-full px-4 py-3 text-left transition hover:bg-slate-50 ${
                    selectedId === identity.id ? 'bg-blue-50/70' : 'bg-white'
                  }`}
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className={`rounded-lg p-2 ${identity.entity_type === 'person' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>
                        {identity.entity_type === 'person' ? <Users className="h-4 w-4" /> : <Fingerprint className="h-4 w-4" />}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-bold text-slate-900">
                          {identity.identity_code} · {identity.category}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-slate-500">
                          {identity.associated_track_codes.join(', ') || 'No track IDs'}
                        </span>
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className={`block text-[10px] font-semibold uppercase ${
                        identity.status === 'confirmed' ? 'text-emerald-700' : identity.status === 'probable' ? 'text-blue-700' : 'text-amber-700'
                      }`}>{identity.status}</span>
                      <span className="mt-1 block text-[11px] text-slate-500">{identity.appearance_count} appearances</span>
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="min-w-0 space-y-4">
          {!visibleDetail ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-16 text-center">
              <Fingerprint className="mx-auto h-9 w-9 text-slate-300" />
              <p className="mt-3 text-sm font-semibold text-slate-700">Select an identity to investigate</p>
              <p className="mt-1 text-xs text-slate-500">Track IDs remain available alongside every anonymous identity.</p>
            </div>
          ) : (
            <>
              <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`rounded-xl p-2.5 ${visibleDetail.entity_type === 'person' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>
                        {visibleDetail.entity_type === 'person' ? <Users className="h-5 w-5" /> : <Fingerprint className="h-5 w-5" />}
                      </span>
                      <div>
                        <h2 className="font-display text-xl font-extrabold text-slate-950">
                          {visibleDetail.identity_code} · {visibleDetail.category}
                        </h2>
                        <p className="text-xs text-slate-500">{visibleDetail.source_type === 'analysis' ? 'This video analysis only' : 'This live session only'}</p>
                      </div>
                    </div>
                  </div>
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">
                    {visibleDetail.status}
                  </span>
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl bg-slate-50 p-3">
                    <p className="text-[11px] text-slate-500">First / last seen</p>
                    <p className="mt-1 text-sm font-semibold text-slate-800">{formatTime(visibleDetail.first_seen_timestamp)} – {formatTime(visibleDetail.last_seen_timestamp)}</p>
                  </div>
                  <div className="rounded-xl bg-slate-50 p-3">
                    <p className="text-[11px] text-slate-500">Appearance records</p>
                    <p className="mt-1 text-sm font-semibold text-slate-800">{visibleDetail.appearance_count} · {visibleDetail.associated_track_codes.length} tracker fragments</p>
                  </div>
                  <div className="rounded-xl bg-slate-50 p-3">
                    <p className="text-[11px] text-slate-500">Related stored events</p>
                    <p className="mt-1 text-sm font-semibold text-slate-800">{visibleDetail.related_event_count}</p>
                  </div>
                </div>
                <p className="mt-4 rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-xs leading-relaxed text-blue-900">
                  {visibleDetail.matching_explanation}
                  {visibleDetail.matching_confidence !== null && (
                    <span className="mt-1 block font-semibold">{confidenceLabel(visibleDetail.matching_confidence)}; not a calibrated probability or proof of identity.</span>
                  )}
                </p>
              </article>

              <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="font-display text-base font-bold text-slate-900">Appearance and evidence</h3>
                    <p className="mt-0.5 text-xs text-slate-500">Original T track identifiers are retained for auditability.</p>
                  </div>
                  {visibleDetail.track_appearances?.length ? (
                    <select
                      value={selectedTrackId ?? ''}
                      onChange={(event) => setSelectedTrackId(Number(event.target.value))}
                      aria-label="Select tracker fragment"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                    >
                      {visibleDetail.track_appearances.map((track) => (
                        <option key={track.track_id} value={track.track_id}>{track.track_code} · {track.category}</option>
                      ))}
                    </select>
                  ) : null}
                </div>
                {selectedTrack ? (
                  <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(180px,0.7fr)]">
                    <div className="space-y-2 text-sm">
                      <p><span className="text-slate-500">Track:</span> <strong className="text-slate-900">{selectedTrack.track_code}</strong></p>
                      <p><span className="text-slate-500">Observed:</span> <strong className="text-slate-900">{formatTime(selectedTrack.first_seen_timestamp)} – {formatTime(selectedTrack.last_seen_timestamp)}</strong></p>
                      <p><span className="text-slate-500">Detections:</span> <strong className="text-slate-900">{selectedTrack.detection_count}</strong></p>
                      <p><span className="text-slate-500">Association:</span> <strong className="capitalize text-slate-900">{selectedTrack.match_status}</strong></p>
                      <p className="text-xs leading-relaxed text-slate-600">{selectedTrack.matching_explanation}</p>
                      {selectedTrack.manually_corrected && (
                        <p className="rounded-lg bg-emerald-50 p-2 text-xs text-emerald-800">
                          Manually corrected{selectedTrack.correction_note ? `: ${selectedTrack.correction_note}` : ''}
                        </p>
                      )}
                    </div>
                    <div className="flex min-h-40 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                      {evidenceUrl ? (
                        <img src={evidenceUrl} alt={`${selectedTrack.track_code} stored appearance evidence`} className="max-h-64 w-full object-contain" />
                      ) : (
                        <div className="px-4 text-center text-xs text-slate-500">
                          <ImageOff className="mx-auto mb-2 h-5 w-5 text-slate-400" />
                          Evidence image is not available for this appearance.
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-slate-500">No tracker fragments are stored for this record.</p>
                )}
              </article>

              <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                <h3 className="font-display text-base font-bold text-slate-900">Correct an association</h3>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">
                  Manual changes are source-local and retain the original T ID. Visual similarity alone does not establish a real-world identity.
                </p>
                {visibleDetail.track_appearances?.length ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <label className="text-xs font-semibold text-slate-600">
                      Move selected track to
                      <select
                        value={targetIdentityId}
                        onChange={(event) => setTargetIdentityId(event.target.value)}
                        className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-800"
                      >
                        <option value="">Choose an identity…</option>
                        {sourceTargetIdentities.filter((item) => item.id !== visibleDetail.id && item.entity_type === visibleDetail.entity_type).map((item) => (
                          <option key={item.id} value={item.id}>{item.identity_code} · {item.category}</option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-semibold text-slate-600">
                      Review note
                      <input
                        value={correctionNote}
                        onChange={(event) => setCorrectionNote(event.target.value)}
                        maxLength={500}
                        placeholder="Optional reason for this correction"
                        className="mt-1 block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                      />
                    </label>
                    <div className="flex flex-wrap gap-2 sm:col-span-2">
                      <button
                        type="button"
                        onClick={() => void submitCorrection(false)}
                        disabled={!targetIdentityId || savingCorrection || selectedTrackId === null}
                        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {savingCorrection ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ArrowUpRight className="h-4 w-4" />}
                        Reassign track
                      </button>
                      <button
                        type="button"
                        onClick={() => void submitCorrection(true)}
                        disabled={savingCorrection || selectedTrackId === null}
                        className="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        Create separate identity
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">There are no stored track associations to correct.</p>
                )}
              </article>

              <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-slate-500" />
                  <h3 className="font-display text-base font-bold text-slate-900">Related stored events</h3>
                </div>
                {visibleDetail.related_events?.length ? (
                  <div className="mt-3 space-y-2">
                    {visibleDetail.related_events.map((event) => (
                      <div key={event.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-100 p-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-800">{event.title}</p>
                          <p className="mt-0.5 text-xs text-slate-500">{event.event_type} · {event.track_codes.join(', ')}</p>
                        </div>
                        <span className="rounded-lg bg-slate-50 px-2.5 py-1.5 font-mono text-xs font-semibold text-slate-700">
                          {formatTime(event.timestamp_seconds)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">No stored events reference these track fragments.</p>
                )}
              </article>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
