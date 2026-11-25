import { Activity, Clock, Eye, Film, MapPin, ShieldAlert } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { useState } from 'react'

interface SampleEvent {
  id: string
  timestamp: string
  progressPercent: number
  title: string
  category: string
  trackingLabel: string
  description: string
  severity: 'info' | 'attention' | 'anomaly'
  personBox: { top: string; left: string; width: string; height: string }
  objectBox: { top: string; left: string; width: string; height: string }
  objectLabel: string
}

const SAMPLE_EVENTS: SampleEvent[] = [
  {
    id: 'evt-1',
    timestamp: '00:01:12',
    progressPercent: 18,
    title: 'Authorized Entry Logged',
    category: 'Routine Flow',
    trackingLabel: 'TRK-104 · Person',
    description: 'Operator enters North Bay corridor carrying equipment crate.',
    severity: 'info',
    personBox: { top: '34%', left: '16%', width: '17%', height: '38%' },
    objectBox: { top: '48%', left: '36%', width: '16%', height: '24%' },
    objectLabel: 'TRK-201 · Crate (97%)',
  },
  {
    id: 'evt-2',
    timestamp: '00:02:45',
    progressPercent: 48,
    title: 'Zone B Loitering Threshold',
    category: 'Temporal Cue',
    trackingLabel: 'TRK-104 · Person',
    description: 'Subject remains stationary near restricted loading gate for 38s.',
    severity: 'attention',
    personBox: { top: '30%', left: '43%', width: '18%', height: '40%' },
    objectBox: { top: '50%', left: '63%', width: '18%', height: '26%' },
    objectLabel: 'TRK-208 · Cart (95%)',
  },
  {
    id: 'evt-3',
    timestamp: '00:04:18',
    progressPercent: 76,
    title: 'Unattended Package Flagged',
    category: 'Contextual Anomaly',
    trackingLabel: 'TRK-312 · Package',
    description: 'Object separated from TRK-104 trajectory inside egress lane.',
    severity: 'anomaly',
    personBox: { top: '28%', left: '68%', width: '16%', height: '36%' },
    objectBox: { top: '56%', left: '34%', width: '18%', height: '22%' },
    objectLabel: 'TRK-312 · Unattended (98%)',
  },
  {
    id: 'evt-4',
    timestamp: '00:05:30',
    progressPercent: 92,
    title: 'Evidence Clip Archived',
    category: 'Report Ready',
    trackingLabel: 'TRK-104 + TRK-312',
    description: 'Keyframes and bounding overlays indexed for rapid investigation.',
    severity: 'info',
    personBox: { top: '32%', left: '54%', width: '17%', height: '38%' },
    objectBox: { top: '54%', left: '28%', width: '19%', height: '23%' },
    objectLabel: 'TRK-312 · Indexed (99%)',
  },
]

const severityStyles: Record<SampleEvent['severity'], { badge: string; dot: string }> = {
  info: {
    badge: 'border-[#2563EB]/20 bg-[#2563EB]/8 text-[#2563EB]',
    dot: 'bg-[#2563EB]',
  },
  attention: {
    badge: 'border-amber-500/25 bg-amber-50 text-amber-700',
    dot: 'bg-amber-500',
  },
  anomaly: {
    badge: 'border-[#7C3AED]/25 bg-[#7C3AED]/10 text-[#7C3AED]',
    dot: 'bg-[#7C3AED]',
  },
}

export function IntelligencePreviewSection() {
  const prefersReducedMotion = useReducedMotion()
  const [activeId, setActiveId] = useState<string>(SAMPLE_EVENTS[2].id)

  const activeEvent = SAMPLE_EVENTS.find((item) => item.id === activeId) ?? SAMPLE_EVENTS[0]

  return (
    <section id="intelligence-preview" className="border-t border-slate-200/80 bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mx-auto max-w-2xl text-center"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3.5 py-1 text-xs font-semibold text-[#7C3AED]">
            <Eye className="h-3.5 w-3.5" />
            <span>Sample Preview · Illustrative Demo Data</span>
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-[#111827] sm:text-4xl">
            Video Intelligence at a Glance
          </h2>
          <p className="mt-3 text-base text-[#64748B]">
            Inspect how NEMESIS-X pairs frame-level detection with temporal tracking and timeline
            event discovery. Click any marker or event below to preview sample states.
          </p>
        </motion.div>

        {/* Workstation UI Frame */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.15 }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
          className="mt-12 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60"
        >
          {/* Workstation header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-[#F5F8FC] px-5 py-3.5">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2563EB]/10 text-[#2563EB]">
                <Film className="h-4 w-4" />
              </div>
              <div>
                <p className="font-mono text-xs font-semibold text-[#111827]">
                  sample_north_bay_cam02.mp4
                </p>
                <p className="text-[11px] text-[#64748B]">
                  Sample Preview Only · 1920×1080 · 30 FPS
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1 font-mono text-xs font-medium text-[#111827]">
                <Clock className="h-3.5 w-3.5 text-[#2563EB]" />
                {activeEvent.timestamp} / 00:06:00
              </span>
              <span className="hidden rounded-lg border border-[#7C3AED]/20 bg-[#7C3AED]/8 px-2.5 py-1 text-xs font-semibold text-[#7C3AED] sm:inline-flex">
                Sample Output
              </span>
            </div>
          </div>

          {/* Main grid: Video stage + Event Discovery panel */}
          <div className="grid lg:grid-cols-12">
            {/* Left: Video preview + timeline */}
            <div className="border-b border-slate-200 p-5 lg:col-span-8 lg:border-r lg:border-b-0">
              {/* Video canvas */}
              <div className="bg-cv-grid relative aspect-[16/9] w-full overflow-hidden rounded-xl border border-slate-200 bg-[#F5F8FC]">
                {/* Architectural scene backdrop */}
                <svg
                  viewBox="0 0 800 450"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-full w-full"
                  aria-hidden="true"
                >
                  <path d="M70 410L240 220H560L730 410" stroke="#CBD5E1" strokeWidth="1.5" />
                  <path d="M240 220V70H560V220" stroke="#CBD5E1" strokeWidth="1.5" />
                  <rect
                    x="275"
                    y="255"
                    width="250"
                    height="90"
                    rx="8"
                    fill="#7C3AED"
                    fillOpacity="0.05"
                    stroke="#7C3AED"
                    strokeOpacity="0.3"
                    strokeDasharray="6 6"
                  />
                  <text
                    x="328"
                    y="305"
                    fill="#64748B"
                    fontSize="12"
                    fontFamily="JetBrains Mono, monospace"
                    fontWeight="600"
                  >
                    EGRESS & LOADING ZONE B
                  </text>
                </svg>

                {/* Top timestamp & active detection counter */}
                <div className="pointer-events-none absolute inset-x-3 top-3 flex items-center justify-between gap-2">
                  <span className="rounded-md border border-slate-200 bg-white/95 px-2.5 py-1 font-mono text-[11px] font-semibold text-[#111827] shadow-xs">
                    REC · {activeEvent.timestamp}.42
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white/95 px-2.5 py-1 font-mono text-[11px] font-medium text-[#64748B] shadow-xs">
                    <Activity className="h-3 w-3 text-[#2563EB]" />2 Active Tracks
                  </span>
                </div>

                {/* Animated Person Tracking Box */}
                <motion.div
                  animate={{
                    top: activeEvent.personBox.top,
                    left: activeEvent.personBox.left,
                    width: activeEvent.personBox.width,
                    height: activeEvent.personBox.height,
                  }}
                  transition={{
                    type: prefersReducedMotion ? 'tween' : 'spring',
                    stiffness: 180,
                    damping: 24,
                    duration: prefersReducedMotion ? 0 : undefined,
                  }}
                  className="pointer-events-none absolute rounded-lg border-2 border-[#2563EB] bg-[#2563EB]/8"
                >
                  <span className="absolute -top-6 left-0 inline-flex items-center gap-1 rounded bg-[#2563EB] px-2 py-0.5 font-mono text-[10px] font-semibold whitespace-nowrap text-white shadow-xs">
                    TRK-104 · Person (98%)
                  </span>
                </motion.div>

                {/* Animated Object Tracking Box */}
                <motion.div
                  animate={{
                    top: activeEvent.objectBox.top,
                    left: activeEvent.objectBox.left,
                    width: activeEvent.objectBox.width,
                    height: activeEvent.objectBox.height,
                  }}
                  transition={{
                    type: prefersReducedMotion ? 'tween' : 'spring',
                    stiffness: 180,
                    damping: 24,
                    duration: prefersReducedMotion ? 0 : undefined,
                  }}
                  className="pointer-events-none absolute rounded-lg border-2 border-[#7C3AED] bg-[#7C3AED]/8"
                >
                  <span className="absolute -top-6 left-0 inline-flex items-center gap-1 rounded bg-[#7C3AED] px-2 py-0.5 font-mono text-[10px] font-semibold whitespace-nowrap text-white shadow-xs">
                    {activeEvent.objectLabel}
                  </span>
                </motion.div>

                {/* Bottom scene status overlay */}
                <div className="pointer-events-none absolute right-3 bottom-3 left-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200/90 bg-white/95 px-3 py-2 shadow-xs backdrop-blur-sm">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-[#7C3AED]" />
                    <span className="text-xs font-semibold text-[#111827]">{activeEvent.title}</span>
                  </div>
                  <span className="font-mono text-[11px] text-[#64748B]">
                    {activeEvent.trackingLabel}
                  </span>
                </div>
              </div>

              {/* Timeline Scrubber with Event Markers */}
              <div className="mt-5 rounded-xl border border-slate-200 bg-[#F5F8FC] p-4">
                <div className="mb-2.5 flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#111827]">Timeline Markers</span>
                  <span className="font-mono text-[#64748B]">
                    Selected: {activeEvent.timestamp}
                  </span>
                </div>

                <div className="relative h-8 pt-3">
                  {/* Track rail */}
                  <div className="h-2 w-full rounded-full bg-slate-200">
                    <motion.div
                      animate={{ width: `${activeEvent.progressPercent}%` }}
                      transition={{ duration: prefersReducedMotion ? 0 : 0.35, ease: 'easeOut' }}
                      className="h-full rounded-full bg-gradient-to-r from-[#2563EB] to-[#7C3AED]"
                    />
                  </div>

                  {/* Clickable timeline markers */}
                  {SAMPLE_EVENTS.map((evt) => {
                    const isSelected = evt.id === activeEvent.id
                    return (
                      <button
                        key={evt.id}
                        type="button"
                        onClick={() => setActiveId(evt.id)}
                        style={{ left: `${evt.progressPercent}%` }}
                        aria-label={`Jump to sample event at ${evt.timestamp}: ${evt.title}`}
                        className={`absolute top-1.5 -translate-x-1/2 rounded-full border-2 border-white transition-transform focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB] ${
                          isSelected ? 'h-5 w-5 scale-110 shadow-md' : 'h-4 w-4 hover:scale-110'
                        } ${severityStyles[evt.severity].dot}`}
                      />
                    )
                  })}
                </div>

                <div className="mt-1 flex justify-between font-mono text-[11px] text-[#64748B]">
                  <span>00:00:00</span>
                  <span>00:02:00</span>
                  <span>00:04:00</span>
                  <span>00:06:00</span>
                </div>
              </div>
            </div>

            {/* Right: Event Discovery Panel */}
            <div className="flex flex-col bg-white p-5 lg:col-span-4">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-sm font-bold tracking-tight text-[#111827]">
                  Event Discovery Panel
                </h3>
                <span className="rounded-md bg-[#F5F8FC] px-2 py-0.5 font-mono text-[11px] font-medium text-[#64748B]">
                  4 Sample Events
                </span>
              </div>

              <div className="mt-4 flex-1 space-y-2.5">
                {SAMPLE_EVENTS.map((evt) => {
                  const isSelected = evt.id === activeEvent.id
                  const badgeStyle = severityStyles[evt.severity].badge

                  return (
                    <button
                      key={evt.id}
                      type="button"
                      onClick={() => setActiveId(evt.id)}
                      className={`w-full rounded-xl border p-3.5 text-left transition-all ${
                        isSelected
                          ? 'border-[#2563EB]/40 bg-[#F5F8FC] shadow-xs'
                          : 'border-slate-200/90 bg-white hover:border-slate-300 hover:bg-[#F5F8FC]/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs font-semibold text-[#2563EB]">
                          {evt.timestamp}
                        </span>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${badgeStyle}`}
                        >
                          {evt.category}
                        </span>
                      </div>

                      <p className="mt-1.5 text-sm font-semibold text-[#111827]">{evt.title}</p>
                      <p className="mt-1 text-xs leading-relaxed text-[#64748B]">
                        {evt.description}
                      </p>

                      <div className="mt-2 inline-flex items-center gap-1 font-mono text-[11px] text-[#64748B]">
                        <MapPin className="h-3 w-3 text-[#7C3AED]" />
                        <span>{evt.trackingLabel}</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
