import { CheckCircle2, Clock, ShieldCheck, Sparkles } from 'lucide-react'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BrandLogo } from '../BrandLogo'

interface AuthLayoutProps {
  heading: string
  subheading: string
  children: ReactNode
}

const HIGHLIGHTS = [
  {
    icon: ShieldCheck,
    title: 'Multi-Object Tracking',
    detail: 'Persistent cross-frame identity continuity across dynamic scenes.',
  },
  {
    icon: Sparkles,
    title: 'Contextual Event Discovery',
    detail: 'Surfaces meaningful behavioral anomalies instead of raw noise.',
  },
  {
    icon: Clock,
    title: 'Timestamped Visual Evidence',
    detail: 'Jump directly to annotated keyframes and incident summaries.',
  },
]

export function AuthLayout({ heading, subheading, children }: AuthLayoutProps) {
  return (
    <div className="relative min-h-[calc(100vh-4.5rem)] overflow-hidden bg-[#F5F8FC] px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
      {/* Subtle light-theme ambient blue & violet gradients */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-28 -left-24 h-80 w-80 rounded-full bg-[#2563EB]/10 blur-3xl" />
        <div className="absolute -right-24 -bottom-24 h-80 w-80 rounded-full bg-[#7C3AED]/10 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-5xl overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-xl shadow-slate-200/60 lg:grid-cols-12">
        {/* Left column: Form panel */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="p-6 sm:p-10 lg:col-span-7"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link to="/" aria-label="NEMESIS-X Home">
              <BrandLogo />
            </Link>
            <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-[11px] font-semibold text-[#2563EB]">
              Beyond Detection. Into Understanding.
            </span>
          </div>

          <div className="mt-8">
            <h1 className="font-display text-2xl font-extrabold tracking-tight text-[#111827] sm:text-3xl">
              {heading}
            </h1>
            <p className="mt-2 text-sm text-[#64748B]">{subheading}</p>
          </div>

          <div className="mt-7">{children}</div>
        </motion.div>

        {/* Right column: SaaS intelligence preview panel */}
        <motion.aside
          initial={{ opacity: 0, x: 14 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: 'easeOut' }}
          className="bg-cv-grid hidden flex-col justify-between border-l border-slate-200/90 bg-gradient-to-br from-[#F5F8FC] via-white to-[#EEF2FF] p-8 lg:col-span-5 lg:flex"
        >
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#7C3AED]/20 bg-white px-3 py-1 font-mono text-[11px] font-semibold text-[#7C3AED] shadow-xs">
              NEMESIS-X WORKSPACE
            </span>

            <h2 className="mt-5 font-display text-xl font-bold tracking-tight text-[#111827]">
              AI Video Intelligence Built for Speed & Clarity
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-[#64748B]">
              Analyze hours of footage in minutes with contextual reasoning and audit-ready
              evidence.
            </p>

            <ul className="mt-7 space-y-4">
              {HIGHLIGHTS.map((item) => {
                const Icon = item.icon
                return (
                  <li
                    key={item.title}
                    className="flex items-start gap-3 rounded-2xl border border-slate-200/80 bg-white/90 p-3.5 shadow-xs"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#2563EB]/10 text-[#2563EB]">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[#111827]">{item.title}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-[#64748B]">
                        {item.detail}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>

          {/* Mini illustrative status card */}
          <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-semibold text-[#64748B]">
                SAMPLE TELEMETRY
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Ready
              </span>
            </div>
            <div className="mt-2.5 flex items-center justify-between font-mono text-xs text-[#111827]">
              <span>TRK-104 · Person</span>
              <span className="text-[#2563EB]">00:04:18.42</span>
            </div>
          </div>
        </motion.aside>
      </div>
    </div>
  )
}
