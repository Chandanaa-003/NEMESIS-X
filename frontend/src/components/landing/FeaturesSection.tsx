import { BrainCircuit, Camera, History, ScanSearch, type LucideIcon } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'

interface FeatureItem {
  title: string
  description: string
  tag: string
  icon: LucideIcon
  accent: 'blue' | 'violet'
}

const FEATURES: FeatureItem[] = [
  {
    title: 'Intelligent Object Detection',
    description:
      'High-precision detection across people, vehicles, and operational assets even in crowded or fast-moving video streams.',
    tag: 'Vision Layer',
    icon: ScanSearch,
    accent: 'blue',
  },
  {
    title: 'Temporal Memory & Tracking',
    description:
      'Maintains persistent identities across frames so trajectories, dwell times, and interactions remain connected over time.',
    tag: 'Identity Continuity',
    icon: History,
    accent: 'violet',
  },
  {
    title: 'Contextual Event Discovery',
    description:
      'Goes beyond isolated frame labels by reasoning across sequences to surface genuine anomalies and cut false alarms.',
    tag: 'Scene Reasoning',
    icon: BrainCircuit,
    accent: 'blue',
  },
  {
    title: 'Timestamped Visual Evidence',
    description:
      'Automatically captures annotated keyframes and incident clips with exact timecodes for fast, auditable review.',
    tag: 'Audit Trail',
    icon: Camera,
    accent: 'violet',
  },
]

export function FeaturesSection() {
  const prefersReducedMotion = useReducedMotion()

  return (
    <section id="features" className="border-t border-slate-200/80 bg-[#F5F8FC] py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mx-auto max-w-2xl text-center"
        >
          <span className="inline-block rounded-full border border-slate-200 bg-white px-3.5 py-1 text-xs font-semibold text-[#2563EB]">
            Core Capabilities
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-[#111827] sm:text-4xl">
            Engineered for Video Understanding
          </h2>
          <p className="mt-3 text-base text-[#64748B]">
            Every stage of the pipeline works together to convert long recordings into clear,
            verifiable insight.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature, index) => {
            const Icon = feature.icon
            const isBlue = feature.accent === 'blue'

            return (
              <motion.article
                key={feature.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.45, delay: index * 0.08, ease: 'easeOut' }}
                whileHover={prefersReducedMotion ? undefined : { y: -4 }}
                className="group flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs transition-shadow hover:border-slate-300 hover:shadow-lg hover:shadow-slate-200/70"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div
                      className={`flex h-11 w-11 items-center justify-center rounded-xl transition-colors ${
                        isBlue
                          ? 'bg-[#2563EB]/10 text-[#2563EB] group-hover:bg-[#2563EB] group-hover:text-white'
                          : 'bg-[#7C3AED]/10 text-[#7C3AED] group-hover:bg-[#7C3AED] group-hover:text-white'
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="font-mono text-[11px] font-medium text-[#64748B]">
                      {feature.tag}
                    </span>
                  </div>

                  <h3 className="mt-5 font-display text-lg font-bold text-[#111827]">
                    {feature.title}
                  </h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-[#64748B]">
                    {feature.description}
                  </p>
                </div>

                <div className="mt-6 h-1 w-10 rounded-full bg-gradient-to-r from-[#2563EB] to-[#7C3AED] opacity-60 transition-all duration-300 group-hover:w-16 group-hover:opacity-100" />
              </motion.article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
