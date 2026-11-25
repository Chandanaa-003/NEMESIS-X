import { Film, Radio, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import type { DemoStatItem } from '../../data/dashboardDemoData'

const ICON_MAP: Record<DemoStatItem['iconKey'], LucideIcon> = {
  videos: Film,
  events: Sparkles,
  evidence: ShieldCheck,
  sessions: Radio,
}

const ACCENT_MAP: Record<DemoStatItem['accent'], { iconBg: string; badge: string }> = {
  blue: {
    iconBg: 'bg-[#2563EB]/10 text-[#2563EB]',
    badge: 'border-[#2563EB]/20 bg-[#2563EB]/8 text-[#2563EB]',
  },
  violet: {
    iconBg: 'bg-[#7C3AED]/10 text-[#7C3AED]',
    badge: 'border-[#7C3AED]/20 bg-[#7C3AED]/8 text-[#7C3AED]',
  },
  emerald: {
    iconBg: 'bg-emerald-500/10 text-emerald-600',
    badge: 'border-emerald-500/20 bg-emerald-50 text-emerald-700',
  },
  amber: {
    iconBg: 'bg-amber-500/10 text-amber-600',
    badge: 'border-amber-500/20 bg-amber-50 text-amber-700',
  },
}

interface StatCardProps {
  stat: DemoStatItem
  index?: number
}

export function StatCard({ stat, index = 0 }: StatCardProps) {
  const prefersReducedMotion = useReducedMotion()
  const Icon = ICON_MAP[stat.iconKey]
  const accent = ACCENT_MAP[stat.accent]

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: 'easeOut' }}
      whileHover={prefersReducedMotion ? undefined : { y: -3 }}
      className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs transition-shadow hover:border-slate-300 hover:shadow-md hover:shadow-slate-200/60"
    >
      <div className="flex items-center justify-between gap-2">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${accent.iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>
        <span
          className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold ${accent.badge}`}
        >
          {stat.badge}
        </span>
      </div>

      <p className="mt-4 font-display text-3xl font-extrabold tracking-tight text-[#111827]">
        {stat.value}
      </p>
      <h2 className="mt-1 text-sm font-semibold text-[#111827]">{stat.label}</h2>
      <p className="mt-1 text-xs text-[#64748B]">{stat.helper}</p>
    </motion.article>
  )
}
