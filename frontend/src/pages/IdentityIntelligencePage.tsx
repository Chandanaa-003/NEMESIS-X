import { AlertCircle, Check, ImageOff, Loader2, Search, ShieldCheck, UsersRound } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { getAuthErrorMessage } from '../services/authService'
import { listUserAnalyses, type AnalysisListItem } from '../services/analysisService'
import {
  correctEntityIdentity,
  fetchIdentityEvidenceBlobUrl,
  getEntityIdentity,
  searchEntityIdentities,
  type EntityIdentity,
  type IdentityEntityType,
  type IdentitySourceType,
} from '../services/identityService'
import { listLiveMonitoringSessions, type LiveSessionStatusResponse } from '../services/liveService'

interface SourceOption {
  key: string
  type: IdentitySourceType
  id: string
  label: string
}

function formatTime(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(value / 3600)
  const minutes = Math.floor((value % 3600) / 60)
  const remaining = value % 60
  return hours > 0
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
}

function IdentityEvidence({ url, label }: { url: string | null; label: string }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!url) return
    let active = true
    let createdUrl: string | null = null
    fetchIdentityEvidenceBlobUrl(url)
      .then((blobUrl) => {
        if (!active) {
          URL.revokeObjectURL(blobUrl)
          return
        }
        createdUrl = blobUrl
        setImageUrl(blobUrl)
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
      if (createdUrl) URL.revokeObjectURL(createdUrl)
    }
  }, [url])

  if (!url || failed) {
    return <div className="flex h-24 w-32 items-center justify-center rounded-lg bg-slate-100 text-slate-400"><ImageOff className="h-5 w-5" /></div>
  }
  if (!imageUrl) return <div className="h-24 w-32 animate-pulse rounded-lg bg-slate-100" />
  return <img src={imageUrl} alt={label} className="h-24 w-32 rounded-lg border border-slate-200 bg-slate-950 object-contain" />
}

export function IdentityIntelligencePage() {
  const [sources, setSources] = useState<SourceOption[]>([])
  const [selectedSource, setSelectedSource] = useState('')
  const [entityType, setEntityType] = useState<'all' | IdentityEntityType>('all')
  const [identityCode, setIdentityCode] = useState('')
  const [minAppearances, setMinAppearances] = useState('1')
  const [firstSeenAfter, setFirstSeenAfter] = useState('')
  const [lastSeenBefore, setLastSeenBefore] = useState('')
  const [identities, setIdentities] = useState<EntityIdentity[]>([])
  const [selectedIdentity, setSelectedIdentity] = useState<EntityIdentity | null>(null)
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null)
  const [targetIdentityId, setTargetIdentityId] = useState('')
  const [isLoadingSources, setIsLoadingSources] = useState(true)
  const [isSearching, setIsSearching] = useState(false)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [isCorrecting, setIsCorrecting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [counts, setCounts] = useState({ people: 0, objects: 0 })

  useEffect(() => {
    let active = true
    Promise.all([listUserAnalyses(), listLiveMonitoringSessions()])
      .then(([analyses, sessions]) => {
        if (!active) return
        const analysisSources: SourceOption[] = analyses
          .filter((analysis) => analysis.status === 'completed')
          .map((analysis: AnalysisListItem) => ({
            key: `analysis:${analysis.analysis_id}`,
            type: 'analysis',
            id: analysis.analysis_id,
            label: `${analysis.video_filename} · recorded ${new Date(analysis.created_at).toLocaleString()}`,
          }))
        const liveSources: SourceOption[] = sessions
          .filter((session: LiveSessionStatusResponse) => session.status !== 'error')
          .map((session) => ({
            key: `live_session:${session.session_id}`,
            type: 'live_session',
            id: session.session_id,
            label: `Live ${session.status} · ${new Date(session.started_at).toLocaleString()} · ${session.session_id.slice(0, 8)}`,
          }))
        const options = [...analysisSources, ...liveSources]
        setSources(options)
        if (options.length > 0) setSelectedSource(options[0].key)
      })
      .catch((reason) => {
        if (active) setError(getAuthErrorMessage(reason, 'Could not load identity sources.'))
      })
      .finally(() => {
        if (active) setIsLoadingSources(false)
      })
    return () => {
      active = false
    }
  }, [])

  const source = useMemo(
    () => sources.find((item) => item.key === selectedSource) ?? null,
    [selectedSource, sources],
  )
  const correctionTargets = useMemo(
    () => identities.filter((identity) => identity.entity_type === selectedIdentity?.entity_type),
    [identities, selectedIdentity],
  )

  const runSearch = async () => {
    if (!source) return
    const minCount = Number(minAppearances)
    const first = firstSeenAfter ? Number(firstSeenAfter) : undefined
    const last = lastSeenBefore ? Number(lastSeenBefore) : undefined
    if (!Number.isInteger(minCount) || minCount < 0) {
      setError('Minimum appearances must be a non-negative whole number.')
      return
    }
    if ((first !== undefined && (!Number.isFinite(first) || first < 0)) ||
      (last !== undefined && (!Number.isFinite(last) || last < 0)) ||
      (first !== undefined && last !== undefined && first > last)) {
      setError('Enter valid non-negative timestamp filters; first seen must not exceed last seen.')
      return
    }

    setIsSearching(true)
    setError('')
    setNotice('')
    setSelectedIdentity(null)
    try {
      const result = await searchEntityIdentities({
        source_type: source.type,
        source_id: source.id,
        entity_type: entityType === 'all' ? undefined : entityType,
        identity_code: identityCode.trim() || undefined,
        min_appearances: minCount,
        first_seen_after: first,
        last_seen_before: last,
        limit: 500,
        offset: 0,
      })
      setIdentities(result.items)
      setCounts({ people: result.total_unique_people, objects: result.total_unique_objects })
      if (result.items.length === 0) setNotice('No identities match these filters. New results appear after a completed analysis or live frames are processed.')
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Identity search failed.'))
    } finally {
      setIsSearching(false)
    }
  }

  const openIdentity = async (identityId: string) => {
    setIsLoadingDetail(true)
    setError('')
    try {
      const detail = await getEntityIdentity(identityId)
      setSelectedIdentity(detail)
      setSelectedTrackId(detail.observations[0]?.track_id ?? null)
      setTargetIdentityId(detail.id)
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not load this identity.'))
    } finally {
      setIsLoadingDetail(false)
    }
  }

  const correctAssignment = async () => {
    if (!selectedIdentity || selectedTrackId === null || !targetIdentityId) return
    setIsCorrecting(true)
    setError('')
    setNotice('')
    try {
      const result = await correctEntityIdentity({
        identityId: selectedIdentity.id,
        trackId: selectedTrackId,
        targetIdentityId: targetIdentityId === 'new' ? undefined : targetIdentityId,
        createNewIdentity: targetIdentityId === 'new',
      })
      await runSearch()
      setSelectedIdentity(result.identity)
      setTargetIdentityId(result.identity.id)
      setNotice(result.correction)
    } catch (reason) {
      setError(getAuthErrorMessage(reason, 'Could not correct this identity assignment.'))
    } finally {
      setIsCorrecting(false)
    }
  }

  return (
    <div className="space-y-6">
      <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-indigo-700"><UsersRound className="h-3.5 w-3.5" /> Persistent identity review</div>
            <h1 className="mt-3 font-display text-2xl font-bold text-slate-900">Unique Entities</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">Search anonymous, source-local person and object labels, review their track fragments, and correct uncertain matches.</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-900">Appearance similarity is not proof of identity. No facial recognition, names, or cross-video matching are used.</div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <label className="space-y-1.5 text-xs font-medium text-slate-600 xl:col-span-2">Recording or live session
            <select value={selectedSource} onChange={(event) => { setSelectedSource(event.target.value); setIdentities([]); setSelectedIdentity(null) }} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900">
              <option value="">Select a source</option>{sources.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-600">Entity type
            <select value={entityType} onChange={(event) => setEntityType(event.target.value as 'all' | IdentityEntityType)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900">
              <option value="all">People and objects</option><option value="person">People</option><option value="object">Objects</option>
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-600">Identity ID
            <input value={identityCode} onChange={(event) => setIdentityCode(event.target.value.toUpperCase())} placeholder="P001 or O001" className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-600">Minimum appearances
            <input type="number" min="0" step="1" value={minAppearances} onChange={(event) => setMinAppearances(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" />
          </label>
          <button type="button" onClick={() => void runSearch()} disabled={!source || isSearching} className="mt-auto inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
            {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Search
          </button>
          <label className="space-y-1.5 text-xs font-medium text-slate-600">First seen after (sec)
            <input type="number" min="0" step="0.1" value={firstSeenAfter} onChange={(event) => setFirstSeenAfter(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-600">Last seen before (sec)
            <input type="number" min="0" step="0.1" value={lastSeenBefore} onChange={(event) => setLastSeenBefore(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" />
          </label>
        </div>
        {error && <div role="alert" className="mt-4 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
        {notice && <div role="status" className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"><Check className="h-4 w-4 shrink-0" />{notice}</div>}
      </motion.section>

      <div className="grid gap-5 xl:grid-cols-[minmax(300px,0.8fr)_minmax(0,1.4fr)]">
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-3"><div><h2 className="font-display text-lg font-bold text-slate-900">Source identities</h2><p className="text-xs text-slate-500">IDs are unique only within the selected source.</p></div>{identities.length > 0 && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{identities.length} results</span>}</div>
          {(isLoadingSources || isSearching) ? <div className="flex items-center justify-center py-14 text-sm text-slate-500"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading identities…</div> :
            identities.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center"><UsersRound className="mx-auto h-8 w-8 text-slate-400" /><p className="mt-3 text-sm font-semibold text-slate-700">{sources.length === 0 ? 'No completed analyses or live sessions' : 'Search this source to view identities'}</p><p className="mt-1 text-xs text-slate-500">{notice || 'Identity matching uses existing detections and tracks; it does not create sample records.'}</p></div> :
              <div className="space-y-2">
                <div className="mb-3 grid grid-cols-2 gap-2 text-xs"><div className="rounded-lg bg-blue-50 p-2 text-blue-800"><b>{counts.people}</b> unique people</div><div className="rounded-lg bg-violet-50 p-2 text-violet-800"><b>{counts.objects}</b> unique objects</div></div>
                {identities.map((identity) => <button key={identity.id} type="button" onClick={() => void openIdentity(identity.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedIdentity?.id === identity.id ? 'border-blue-300 bg-blue-50/70' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'}`}>
                  <div className="flex items-center justify-between gap-2"><span className="font-mono text-sm font-bold text-slate-900">{identity.identity_code}</span><span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${identity.status === 'confirmed' ? 'bg-emerald-100 text-emerald-800' : identity.status === 'probable' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>{identity.status}</span></div>
                  <p className="mt-1 text-xs text-slate-600">{identity.class_name} · {identity.appearance_count} track appearance(s)</p>
                  <p className="mt-1 font-mono text-[10px] text-slate-500">{formatTime(identity.first_seen_timestamp)} – {formatTime(identity.last_seen_timestamp)} · {identity.associated_track_ids.map((id) => `T${String(id).padStart(3, '0')}`).join(', ') || 'no tracks'}</p>
                </button>)}
              </div>}
        </section>

        <section className="min-h-[320px] rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          {isLoadingDetail ? <div className="flex h-full items-center justify-center text-sm text-slate-500"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading appearances…</div> : !selectedIdentity ? <div className="flex h-full min-h-[280px] flex-col items-center justify-center text-center"><Search className="h-8 w-8 text-slate-300" /><h2 className="mt-3 font-semibold text-slate-700">Select an identity</h2><p className="mt-1 max-w-sm text-xs text-slate-500">Review its associated ByteTrack fragments, evidence crops, and stored events.</p></div> :
            <div>
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4"><div><div className="flex items-center gap-2"><h2 className="font-mono text-xl font-bold text-slate-900">{selectedIdentity.identity_code}</h2><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase text-slate-700">{selectedIdentity.status}</span></div><p className="mt-1 text-sm text-slate-600">{selectedIdentity.entity_type === 'person' ? 'Anonymous person appearance' : `Object · ${selectedIdentity.class_name}`}</p></div><div className="text-right text-xs text-slate-500"><p>{selectedIdentity.appearance_count} appearance(s)</p><p>Similarity · {Math.round(selectedIdentity.matching_confidence * 100)}%</p></div></div>
              <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">{selectedIdentity.matching_explanation}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-600"><span className="rounded-md bg-blue-50 px-2 py-1">First {formatTime(selectedIdentity.first_seen_timestamp)}</span><span className="rounded-md bg-blue-50 px-2 py-1">Last {formatTime(selectedIdentity.last_seen_timestamp)}</span><span className="rounded-md bg-slate-100 px-2 py-1">Tracks {selectedIdentity.associated_track_ids.map((id) => `T${String(id).padStart(3, '0')}`).join(', ') || 'none'}</span></div>

              <h3 className="mt-5 text-sm font-semibold text-slate-800">Appearance history</h3>
              {selectedIdentity.observations.length === 0 ? <p className="mt-2 text-xs text-slate-500">No track observations are available.</p> : <div className="mt-2 space-y-3">
                {selectedIdentity.observations.map((observation) => <article key={`${selectedIdentity.id}-${observation.track_id}`} className="flex flex-wrap gap-3 rounded-xl border border-slate-200 p-3">
                  <IdentityEvidence url={observation.evidence_url} label={`${selectedIdentity.identity_code} appearance on ${observation.track_code}`} />
                  <div className="min-w-[180px] flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-mono text-xs font-bold text-slate-800">{observation.track_code}</p><p className="font-mono text-[10px] text-slate-500">{formatTime(observation.first_seen_timestamp)} – {formatTime(observation.last_seen_timestamp)}</p></div><p className="mt-1 text-[11px] text-slate-600">{observation.detection_count} detections · match {Math.round(observation.match_confidence * 100)}% · crop quality {Math.round(observation.feature_quality * 100)}%</p><p className="mt-1 text-[11px] leading-relaxed text-slate-500">{observation.matching_explanation}</p></div>
                </article>)}
              </div>}

              <div className="mt-5 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-indigo-950"><ShieldCheck className="h-4 w-4" />Manual identity review</div>
                <p className="mt-1 text-[11px] leading-relaxed text-indigo-800">Reassign a track fragment within this source, confirm its current label, or split it into a separate identity. Original track IDs are retained.</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1.2fr_auto]">
                  <select value={selectedTrackId ?? ''} onChange={(event) => setSelectedTrackId(event.target.value ? Number(event.target.value) : null)} className="rounded-lg border border-indigo-200 bg-white px-2.5 py-2 text-xs"><option value="">Track fragment</option>{selectedIdentity.observations.map((item) => <option key={item.track_id} value={item.track_id}>{item.track_code}</option>)}</select>
                  <select value={targetIdentityId} onChange={(event) => setTargetIdentityId(event.target.value)} className="rounded-lg border border-indigo-200 bg-white px-2.5 py-2 text-xs"><option value="">Target identity</option>{correctionTargets.map((item) => <option key={item.id} value={item.id}>{item.identity_code} · {item.class_name}</option>)}<option value="new">Create separate identity</option></select>
                  <button type="button" onClick={() => void correctAssignment()} disabled={isCorrecting || selectedTrackId === null || !targetIdentityId} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-indigo-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{isCorrecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}Apply</button>
                </div>
              </div>

              <h3 className="mt-5 text-sm font-semibold text-slate-800">Related stored events</h3>
              {selectedIdentity.related_events.length === 0 ? <p className="mt-2 text-xs text-slate-500">No stored events reference these tracking IDs.</p> : <div className="mt-2 space-y-2">{selectedIdentity.related_events.map((event) => <div key={event.event_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2"><div><p className="text-xs font-semibold text-slate-800">{event.title}</p><p className="text-[10px] text-slate-500">{event.event_type} · {event.involved_track_ids.map((id) => `T${String(id).padStart(3, '0')}`).join(', ')}</p></div><span className="font-mono text-[10px] text-slate-600">{formatTime(event.timestamp_seconds)}</span></div>)}</div>}
            </div>}
        </section>
      </div>
      <p className="text-center text-[11px] text-slate-500">Appearance matching uses low-dimensional color and shape descriptors only. Labels are anonymous, source-scoped, and require human review for uncertain matches.</p>
    </div>
  )
}
