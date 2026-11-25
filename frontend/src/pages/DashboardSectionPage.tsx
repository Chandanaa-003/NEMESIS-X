import {
  ArrowLeft,
  Clock,
  History,
  Radio,
  Settings,
  ShieldCheck,
  UploadCloud,
  type LucideIcon,
} from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'

type SectionIconKey = 'upload' | 'live' | 'timeline' | 'evidence' | 'history' | 'settings'

const ICON_MAP: Record<SectionIconKey, LucideIcon> = {
  upload: UploadCloud,
  live: Radio,
  timeline: Clock,
  evidence: ShieldCheck,
  history: History,
  settings: Settings,
}

interface DashboardSectionPageProps {
  title: string
  routePath: string
  description: string
  iconKey: SectionIconKey
  badgeText?: string
}

export function DashboardSectionPage({
  title,
  routePath,
  description,
  iconKey,
  badgeText = 'MODULE PLACEHOLDER',
}: DashboardSectionPageProps) {
  const Icon = ICON_MAP[iconKey]

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="rounded-3xl border border-slate-200/90 bg-white p-8 shadow-xs"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#2563EB]/10 text-[#2563EB]">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <span className="font-mono text-[11px] font-semibold text-[#7C3AED] uppercase">
              Route: {routePath}
            </span>
            <h2 className="font-display text-xl font-bold text-[#111827]">{title}</h2>
          </div>
        </div>

        <span className="rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 font-mono text-[11px] font-semibold text-[#64748B]">
          {badgeText}
        </span>
      </div>

      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#64748B]">{description}</p>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 rounded-xl bg-[#2563EB] px-4 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-[#1D4ED8]"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    </motion.section>
  )
}
