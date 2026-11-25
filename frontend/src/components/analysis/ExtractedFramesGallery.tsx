import { Clock, Film, ImageOff, Layers } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useState } from 'react'
import {
  fetchExtractedFrameBlobUrl,
  type AnalysisResultsResponse,
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
}: {
  analysisId: string
  filename: string
  alt: string
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

  return (
    <img
      src={blobUrl}
      alt={alt}
      loading="lazy"
      className="aspect-video w-full bg-slate-100 object-cover"
    />
  )
}

interface ExtractedFramesGalleryProps {
  results: AnalysisResultsResponse
}

export function ExtractedFramesGallery({ results }: ExtractedFramesGalleryProps) {
  const dims = results.summary.original_dimensions
  const duration = results.summary.duration_seconds

  return (
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
              Extracted Frame Gallery
            </h3>
            <p className="text-xs text-[#64748B]">
              {results.frames.length} frames extracted · Sampling interval: every{' '}
              {results.sampling_interval} frame(s)
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

      {results.frames.length === 0 ? (
        <p className="py-10 text-center text-sm text-[#64748B]">
          No frames were extracted for this video.
        </p>
      ) : (
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {results.frames.map((frame) => (
            <article
              key={frame.filename}
              className="overflow-hidden rounded-2xl border border-slate-200/90 bg-[#F5F8FC] transition-shadow hover:shadow-md hover:shadow-slate-200/70"
            >
              <AuthenticatedFrameThumbnail
                analysisId={results.analysis_id}
                filename={frame.filename}
                alt={`Frame ${frame.frame_index + 1} at ${formatTimestamp(frame.timestamp_seconds)}`}
              />

              <div className="flex items-center justify-between gap-2 bg-white px-3 py-2">
                <span className="font-mono text-[11px] font-semibold text-[#111827]">
                  Frame #{frame.frame_index + 1}
                </span>
                <span className="rounded bg-[#EFF6FF] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#2563EB]">
                  {formatTimestamp(frame.timestamp_seconds)}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </motion.section>
  )
}
