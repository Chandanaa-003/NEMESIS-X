import {
  ArrowUpRight,
  Clock,
  Radio,
  ShieldCheck,
  UploadCloud,
  type LucideIcon,
} from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { Link } from 'react-router-dom'
import type { DemoQuickActionItem } from '../../data/dashboardDemoData'

const ICON_MAP: Record<DemoQuickActionItem['iconKey'], LucideIcon> = {
  upload: UploadCloud,
  live: Radio,
  evidence: ShieldCheck,
  timeline: Clock,
}

interface QuickActionsProps {
  actions: DemoQuickActionItem[]
}

export function QuickActions({ actions }: QuickActionsProps) {
  const prefersReducedMotion = useReducedMotion()

  return (
    <section aria-labelledby="quick-actions-heading">
      <div className="mb-4 flex items-center justify-between">
        <h2 id="quick-actions-heading" className="font-display text-base font-bold text-[#111827]">
          Quick Actions
        </h2>
        <span className="text-xs text-[#64748B]">Jump directly to a workspace module</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map((action, index) => {
          const Icon = ICON_MAP[action.iconKey]
          const isBlue = action.accent === 'blue'

          return (
            <motion.div
              key={action.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.2 + index * 0.05, ease: 'easeOut' }}
              whileHover={prefersReducedMotion ? undefined : { y: -3 }}
            >
              <Link
                to={action.to}
                className="group flex h-full flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs transition-all hover:border-[#2563EB]/35 hover:shadow-md hover:shadow-slate-200/70"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
                        isBlue
                          ? 'bg-[#2563EB]/10 text-[#2563EB] group-hover:bg-[#2563EB] group-hover:text-white'
                          : 'bg-[#7C3AED]/10 text-[#7C3AED] group-hover:bg-[#7C3AED] group-hover:text-white'
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <ArrowUpRight className="h-4 w-4 text-[#64748B] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-[#2563EB]" />
                  </div>

                  <h3 className="mt-4 font-display text-sm font-bold text-[#111827]">
                    {action.title}
                  </h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-[#64748B]">
                    {action.description}
                  </p>
                </div>
              </Link>
            </motion.div>
          )
        })}
      </div>
    </section>
  )
}
