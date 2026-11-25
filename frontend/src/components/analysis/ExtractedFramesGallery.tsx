import { Clock, Film, GitBranch, ImageOff, Layers, ScanSearch } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import {
  fetchExtractedFrameBlobUrl,
  type AnalysisResultsResponse,
  type DetectedObjectInfo,
} from '../../services/analysisService'

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${String(mins).padStart(2, '0')}:${secs.toFixed(1).padStart(4, '0')}`
}

function AuthenticatedFrameThumbnail({
  analysisId,
  filename,
  alt,
  frameWidth,
  frameHeight,
  detections,
}: {
  analysisId: string
  filename: string
  alt: string
  frameWidth?: number | null
  frameHeight?: number | null
  detections: DetectedObjectInfo[]
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

  if (failed) {
    return (
      <div className="flex aspect-video w-full items-center justify-center bg-[#F5F8FC] text-[#64748B]">
        <ImageOff className="h-5 w-5" />
      </div>
    )
  }

  if (!blobUrl) {
    return <div className="aspect-video w-full animate-pulse bg-slate-100" />
  }

  const canOverlayBoxes =
    detections.length > 0 &&
    typeof frameWidth === 'number' &&
    frameWidth > 0 &&
    typeof frameHeight === 'number' &&
    frameHeight > 0

  return (
    <div className="relative aspect-video w-full overflow-hidden bg-slate-100">
      <img src={blobUrl} alt={alt} loading="lazy" className="h-full w-full object-contain" />
      {canOverlayBoxes && (
        <svg
          viewBox={`0 0 ${frameWidth} ${frameHeight}`}
          preserveAspectRatio="xMidYMid meet"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          {detections.map((det, idx) => {
            const width = Math.max(1, det.bbox.x2 - det.bbox.x1)
            const height = Math.max(1, det.bbox.y2 - det.bbox.y1)
            const strokeColor = det.class_name === 'person' ? '#2563EB' : '#7C3AED'
            return (
              <g key={`${det.class_name}-${det.track_id ?? 'na'}-${idx}`}>
                <rect
                  x={det.bbox.x1}
                  y={det.bbox.y1}
                  width={width}
                  height={height}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={Math.max(2, frameWidth * 0.005)}
                />
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}

interface ExtractedFramesGalleryProps {
  results: AnalysisResultsResponse
}

export function ExtractedFramesGallery({ results }: ExtractedFramesGalleryProps) {
  const dims = results.summary.original_dimensions
  const duration = results.summary.duration_seconds
  const detSummary = results.detections_summary
  const tracksSummary = results.tracks_summary
  const tracks = results.tracks ?? []
  const classCounts = Object.entries(detSummary.class_counts ?? {})

  return (
    <div className="space-y-6">
      {/* Persistent Object Tracks / Temporal Memory Summary */}
      {tracks.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
          className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#7C3AED]/10 text-[#7C3AED]">
                <GitBranch className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-display text-base font-bold text-[#111827]">
                  Temporal Memory &amp; Persistent Tracks
                </h3>
                <p className="text-xs text-[#64748B]">
                  {tracksSummary.total_tracks ?? tracks.length} unique object track(s) associated
                  via ByteTrack
                </p>
              </div>
            </div>

            <span className="rounded-full border border-[#7C3AED]/20 bg-[#F5F3FF] px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#7C3AED]">
              BYTETRACK · CPU
            </span>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tracks.map((track) => (
              <div
                key={track.track_id}
                className="rounded-2xl border border-slate-200/90 bg-[#F5F8FC] p-3.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 font-mono text-xs font-bold text-[#111827]">
                    <span className="rounded bg-[#2563EB] px-1.5 py-0.5 text-[10px] text-white">
                      ID #{track.track_id}
                    </span>
                    <span className="capitalize">{track.class_name}</span>
                  </span>
                  <span className="font-mono text-[11px] font-semibold text-[#7C3AED]">
                    {Math.round(track.avg_confidence * 100)}% avg
                  </span>
                </div>

                <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-[#64748B]">
                  <span>
                    {formatTimestamp(track.first_seen_timestamp)} →{' '}
                    {formatTimestamp(track.last_seen_timestamp)}
                  </span>
                  <span>
                    {track.duration_seconds.toFixed(1)}s · {track.frame_count} frame(s)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </motion.section>
      )}

      {/* Frame Gallery with Detections & Track IDs */}
      <motion.section
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#2563EB]/10 text-[#2563EB]">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-display text-base font-bold text-[#111827]">
                Extracted Frames &amp; Tracked Detections
              </h3>
              <p className="text-xs text-[#64748B]">
                {results.frames.length} frames · {detSummary.total_detections ?? 0} detections
                {detSummary.model_name ? ` (${detSummary.model_name} · CPU)` : ''}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 font-mono text-[11px] text-[#64748B]">
            {typeof duration === 'number' && (
              <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1">
                <Clock className="h-3 w-3 text-[#2563EB]" />
                {duration.toFixed(1)}s
              </span>
            )}
            {dims && (
              <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-[#F5F8FC] px-2.5 py-1">
                <Film className="h-3 w-3 text-[#7C3AED]" />
                {dims.width}×{dims.height}
              </span>
            )}
          </div>
        </div>

        {classCounts.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#111827]">
              <ScanSearch className="h-3.5 w-3.5 text-[#2563EB]" />
              Detected Categories:
            </span>
            {classCounts.map(([className, count]) => (
              <span
                key={className}
                className="rounded-full border border-[#2563EB]/20 bg-[#EFF6FF] px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#2563EB]"
              >
                {className}: {count}
              </span>
            ))}
          </div>
        )}

        {results.frames.length === 0 ? (
          <p className="py-10 text-center text-sm text-[#64748B]">
            No frames were extracted for this video.
          </p>
        ) : (
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {results.frames.map((frame) => {
              const topDetections = frame.detections.slice(0, 3)

              return (
                <article
                  key={frame.filename}
                  className="overflow-hidden rounded-2xl border border-slate-200/90 bg-[#F5F8FC] transition-shadow hover:shadow-md hover:shadow-slate-200/70"
                >
                  <AuthenticatedFrameThumbnail
                    analysisId={results.analysis_id}
                    filename={frame.filename}
                    frameWidth={frame.frame_width}
                    frameHeight={frame.frame_height}
                    detections={frame.detections}
                    alt={`Frame ${frame.frame_index + 1} at ${formatTimestamp(frame.timestamp_seconds)}`}
                  />

                  <div className="space-y-2 bg-white px-3 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] font-semibold text-[#111827]">
                        Frame #{frame.frame_index + 1}
                      </span>
                      <span className="rounded bg-[#EFF6FF] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB]">
                        {formatTimestamp(frame.timestamp_seconds)}
                      </span>
                    </div>

                    {topDetections.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {topDetections.map((det, idx) => (
                          <span
                            key={`${frame.filename}-${det.class_name}-${det.track_id ?? idx}-${idx}`}
                            className="rounded-md border border-slate-200 bg-[#F5F8FC] px-1.5 py-0.5 font-mono text-[10px] font-medium text-[#111827]"
                          >
                            {det.track_id != null ? `#${det.track_id} ` : ''}
                            {det.class_name} {Math.round(det.confidence * 100)}%
                          </span>
                        ))}
                        {frame.detections.length > 3 && (
                          <span className="font-mono text-[10px] text-[#64748B]">
                            +{frame.detections.length - 3} more
                          </span>
                        )}
                      </div>
                    ) : (
                      <p className="font-mono text-[10px] text-[#64748B]">No objects detected</p>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </motion.section>
    </div>
  )
}
