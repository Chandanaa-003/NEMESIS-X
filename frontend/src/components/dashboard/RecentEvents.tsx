import { AlertCircle, Clock, ShieldAlert } from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'
import type { DemoEventItem } from '../../data/dashboardDemoData'

interface RecentEventsProps {
  items: DemoEventItem[]
}

const SEVERITY_STYLES: Record<DemoEventItem['severity'], string> = {
  High: 'border-rose-500/20 bg-rose-50 text-rose-700',
  Medium: 'border-amber-500/20 bg-amber-50 text-amber-700',
  Low: 'border-[#2563EB]/20 bg-[#EFF6FF] text-[#2563EB]',
}

export function RecentEvents({ items }: RecentEventsProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.18, ease: 'easeOut' }}
      className="flex flex-col rounded-2xl border border-slate-200/90 bg-white shadow-xs"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/80 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#7C3AED]/10 text-[#7C3AED]">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-display text-base font-bold text-[#111827]">Recent Events</h2>
            <p className="text-xs text-[#64748B]">Sample event log preview</p>
          </div>
        </div>

        <Link
          to="/dashboard/timeline"
          className="text-xs font-semibold text-[#2563EB] transition-colors hover:text-[#1D4ED8]"
        >
          Open Timeline
        </Link>
      </div>

      {/* Explicit sample data notice */}
      <div className="mx-5 mt-4 flex items-start gap-2 rounded-xl border border-[#7C3AED]/20 bg-[#F5F8FC] px-3 py-2.5 text-[11px] leading-relaxed text-[#64748B]">
        <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#7C3AED]" />
        <span>
          <strong className="font-semibold text-[#111827]">Sample Data Only:</strong> Illustrative
          events shown until the real AI analysis engine is connected.
        </span>
      </div>

      {items.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-[#64748B]">
          No sample events match your current filter.
        </div>
      ) : (
        <div className="flex-1 space-y-3 p-5">
          {items.map((evt) => (
            <div
              key={evt.id}
              className="rounded-xl border border-slate-200/80 bg-[#F5F8FC]/60 p-3.5 transition-colors hover:border-slate-300 hover:bg-[#F5F8FC]"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-[#2563EB]">
                  <Clock className="h-3 w-3" />
                  {evt.timestamp}
                </span>

                <div className="flex items-center gap-1.5">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${SEVERITY_STYLES[evt.severity]}`}
                  >
                    {evt.severity}
                  </span>
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 font-mono text-[10px] font-semibold text-[#111827]">
                    {evt.confidence}
                  </span>
                </div>
              </div>

              <h3 className="mt-2 text-sm font-semibold text-[#111827]">{evt.title}</h3>

              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-[#64748B]">
                <span>{evt.category}</span>
                <span className="font-mono text-[11px]">{evt.sourceVideo}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.section>
  )
}
