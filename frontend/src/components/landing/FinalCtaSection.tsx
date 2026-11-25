import { ArrowRight } from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'

export function FinalCtaSection() {
  return (
    <section className="border-t border-slate-200/80 bg-[#F5F8FC] py-20 sm:py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.25 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="relative overflow-hidden rounded-3xl border border-slate-200 bg-white px-6 py-14 text-center shadow-xl shadow-slate-200/60 sm:px-12 sm:py-16"
        >
          {/* Subtle ambient blue/violet corner accents */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-24 -left-24 h-64 w-64 rounded-full bg-[#2563EB]/10 blur-3xl"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-24 -bottom-24 h-64 w-64 rounded-full bg-[#7C3AED]/10 blur-3xl"
          />

          <div className="relative mx-auto max-w-2xl">
            <p className="text-xs font-semibold tracking-widest text-[#2563EB] uppercase">
              NEMESIS-X Video Intelligence
            </p>
            <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight text-[#111827] sm:text-4xl">
              Stop Watching Hours. Start Understanding Moments.
            </h2>
            <p className="mt-4 text-base text-[#64748B]">
              Turn lengthy recordings into searchable events, persistent tracks, and timestamped
              visual evidence.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <Link
                to="/register"
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-7 py-3.5 text-sm font-semibold text-white shadow-md shadow-[#2563EB]/20 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-[#7C3AED]/25"
              >
                <span>Get Started</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/dashboard"
                className="rounded-xl border border-slate-200 bg-white px-6 py-3.5 text-sm font-semibold text-[#111827] transition-colors hover:bg-[#F5F8FC]"
              >
                Open Workspace
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
