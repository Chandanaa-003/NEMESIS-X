import { Calendar, Clock, ExternalLink, Film, Play } from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'
import type { DemoAnalysisItem } from '../../data/dashboardDemoData'

interface RecentAnalysesProps {
  items: DemoAnalysisItem[]
}

const STATUS_STYLES: Record<DemoAnalysisItem['status'], string> = {
  Completed: 'border-emerald-500/20 bg-emerald-50 text-emerald-700',
  'Needs Review': 'border-[#7C3AED]/20 bg-[#7C3AED]/10 text-[#7C3AED]',
  'Sample Queued': 'border-slate-200 bg-slate-100 text-[#64748B]',
}

const THUMB_GRADIENTS: Record<DemoAnalysisItem['thumbnailTheme'], string> = {
  blue: 'from-[#EFF6FF] to-[#DBEAFE] border-[#2563EB]/20 text-[#2563EB]',
  violet: 'from-[#F5F3FF] to-[#EDE9FE] border-[#7C3AED]/20 text-[#7C3AED]',
  indigo: 'from-[#EEF2FF] to-[#E0E7FF] border-indigo-200 text-indigo-600',
  slate: 'from-[#F8FAFC] to-[#E2E8F0] border-slate-200 text-slate-500',
}

function VideoThumbnail({
  theme,
  duration,
}: {
  theme: DemoAnalysisItem['thumbnailTheme']
  duration: string
}) {
  return (
    <div
      className={`bg-cv-grid relative flex h-12 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border bg-gradient-to-br ${THUMB_GRADIENTS[theme]}`}
    >
      <Play className="h-4 w-4 fill-current opacity-80" />
      <span className="absolute right-1 bottom-1 rounded bg-white/90 px-1 font-mono text-[9px] font-semibold text-[#111827] shadow-2xs">
        {duration}
      </span>
    </div>
  )
}

export function RecentAnalyses({ items }: RecentAnalysesProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.12, ease: 'easeOut' }}
      className="rounded-2xl border border-slate-200/90 bg-white shadow-xs"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2563EB]/10 text-[#2563EB]">
            <Film className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-display text-base font-bold text-[#111827]">Recent Analyses</h2>
            <p className="text-xs text-[#64748B]">Illustrative video queue and status summary</p>
          </div>
        </div>

        <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#64748B]">
          DEMO DATA
        </span>
      </div>

      {items.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-[#64748B]">
          No sample analyses match your current filter.
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-[#F5F8FC]/70 text-[11px] font-semibold tracking-wider text-[#64748B] uppercase">
                  <th className="px-5 py-3">Video</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {items.map((item) => (
                  <tr key={item.id} className="transition-colors hover:bg-[#F5F8FC]/60">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <VideoThumbnail theme={item.thumbnailTheme} duration={item.duration} />
                        <div className="min-w-0">
                          <p className="truncate font-mono text-xs font-semibold text-[#111827]">
                            {item.videoName}
                          </p>
                          <p className="mt-0.5 text-xs text-[#64748B]">{item.cameraLabel}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[item.status]}`}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-xs text-[#64748B]">
                      {item.duration}
                    </td>
                    <td className="px-4 py-3.5 text-xs text-[#64748B]">{item.date}</td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        to="/dashboard/history"
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] transition-colors hover:border-[#2563EB]/40 hover:bg-[#F5F8FC] hover:text-[#2563EB]"
                      >
                        <span>View</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile card list */}
          <div className="divide-y divide-slate-100 md:hidden">
            {items.map((item) => (
              <div key={item.id} className="space-y-3 p-4">
                <div className="flex items-start gap-3">
                  <VideoThumbnail theme={item.thumbnailTheme} duration={item.duration} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-xs font-semibold text-[#111827]">
                      {item.videoName}
                    </p>
                    <p className="mt-0.5 text-xs text-[#64748B]">{item.cameraLabel}</p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[#64748B]">
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${STATUS_STYLES[item.status]}`}
                    >
                      {item.status}
                    </span>
                    <span className="inline-flex items-center gap-1 font-mono text-[11px]">
                      <Clock className="h-3 w-3" />
                      {item.duration}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px]">
                      <Calendar className="h-3 w-3" />
                      {item.date}
                    </span>
                  </div>

                  <Link
                    to="/dashboard/history"
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#2563EB]"
                  >
                    <span>View</span>
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </motion.section>
  )
}
