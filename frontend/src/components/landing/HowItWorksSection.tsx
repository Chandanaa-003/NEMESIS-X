import { ArrowRight, Cpu, FileSearch, Sparkles, UploadCloud, type LucideIcon } from 'lucide-react'
import { motion } from 'motion/react'

interface WorkflowStep {
  step: string
  title: string
  description: string
  icon: LucideIcon
}

const STEPS: WorkflowStep[] = [
  {
    step: '01',
    title: 'Upload',
    description: 'Ingest recorded MP4, surveillance, or operational video clips into your workspace.',
    icon: UploadCloud,
  },
  {
    step: '02',
    title: 'Analyze',
    description: 'Run object detection and cross-frame tracking across sampled temporal windows.',
    icon: Cpu,
  },
  {
    step: '03',
    title: 'Discover',
    description: 'Surface unusual events and contextual shifts instead of scrubbing hours of footage.',
    icon: Sparkles,
  },
  {
    step: '04',
    title: 'Investigate',
    description: 'Review timestamped visual evidence, tracking IDs, and structured incident reports.',
    icon: FileSearch,
  },
]

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="border-t border-slate-200/80 bg-white py-20 sm:py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mx-auto max-w-2xl text-center"
        >
          <span className="inline-block rounded-full border border-slate-200 bg-[#F5F8FC] px-3.5 py-1 text-xs font-semibold text-[#7C3AED]">
            Workflow
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-[#111827] sm:text-4xl">
            From Raw Footage to Clarity in Four Steps
          </h2>
          <p className="mt-3 text-base text-[#64748B]">
            A streamlined pipeline built to take teams from raw video files to actionable answers.
          </p>
        </motion.div>

        <div className="relative mt-14 grid gap-6 md:grid-cols-4">
          {/* Desktop connecting line */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute top-11 right-16 left-16 hidden h-px bg-gradient-to-r from-[#2563EB]/30 via-[#7C3AED]/40 to-[#2563EB]/30 md:block"
          />

          {STEPS.map((item, index) => {
            const Icon = item.icon

            return (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.45, delay: index * 0.1, ease: 'easeOut' }}
                className="relative flex flex-col rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="relative z-10 flex h-12 w-12 items-center justify-center rounded-xl border border-[#2563EB]/20 bg-[#F5F8FC] text-[#2563EB]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="font-mono text-xs font-bold text-[#7C3AED]">STEP {item.step}</span>
                </div>

                <div className="mt-5 flex items-center gap-2">
                  <h3 className="font-display text-lg font-bold text-[#111827]">{item.title}</h3>
                  {index < STEPS.length - 1 && (
                    <ArrowRight className="h-4 w-4 text-slate-300 md:hidden" />
                  )}
                </div>

                <p className="mt-2 text-sm leading-relaxed text-[#64748B]">{item.description}</p>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
