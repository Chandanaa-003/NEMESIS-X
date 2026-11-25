import { Radio, Search, Sparkles, UploadCloud, X } from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'react-router-dom'
import { QuickActions } from '../components/dashboard/QuickActions'
import { RecentAnalyses } from '../components/dashboard/RecentAnalyses'
import { RecentEvents } from '../components/dashboard/RecentEvents'
import { StatCard } from '../components/dashboard/StatCard'
import { useDashboardContext } from '../components/dashboard/dashboardContext'
import {
  DEMO_DASHBOARD_STATS,
  DEMO_QUICK_ACTIONS,
  DEMO_RECENT_ANALYSES,
  DEMO_RECENT_EVENTS,
} from '../data/dashboardDemoData'

export function DashboardPage() {
  const { searchQuery, setSearchQuery } = useDashboardContext()
  const normalizedQuery = searchQuery.trim().toLowerCase()

  const filteredAnalyses = normalizedQuery
    ? DEMO_RECENT_ANALYSES.filter(
        (item) =>
          item.videoName.toLowerCase().includes(normalizedQuery) ||
          item.cameraLabel.toLowerCase().includes(normalizedQuery) ||
          item.status.toLowerCase().includes(normalizedQuery),
      )
    : DEMO_RECENT_ANALYSES

  const filteredEvents = normalizedQuery
    ? DEMO_RECENT_EVENTS.filter(
        (evt) =>
          evt.title.toLowerCase().includes(normalizedQuery) ||
          evt.category.toLowerCase().includes(normalizedQuery) ||
          evt.severity.toLowerCase().includes(normalizedQuery) ||
          evt.sourceVideo.toLowerCase().includes(normalizedQuery),
      )
    : DEMO_RECENT_EVENTS

  return (
    <div className="space-y-6">
      {/* Mobile search input (Header search shows on md+) */}
      <div className="relative md:hidden">
        <Search
          className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-[#64748B]"
          aria-hidden="true"
        />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter sample videos or events..."
          aria-label="Filter sample videos or events"
          className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pr-9 pl-10 text-xs text-[#111827] placeholder:text-slate-400 focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 focus:outline-none"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            aria-label="Clear mobile search"
            className="absolute top-1/2 right-2.5 -translate-y-1/2 rounded p-1 text-[#64748B]"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* 3. Dashboard Welcome Section */}
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="relative overflow-hidden rounded-3xl border border-slate-200/90 bg-white p-6 shadow-xs sm:p-8"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-20 -right-16 h-60 w-60 rounded-full bg-[#2563EB]/10 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 left-1/3 h-56 w-56 rounded-full bg-[#7C3AED]/10 blur-3xl"
        />

        <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-3 py-1 text-xs font-semibold text-[#2563EB]">
              <Sparkles className="h-3.5 w-3.5 text-[#7C3AED]" />
              <span>Workspace Preview · Illustrative Demo Data</span>
            </span>

            <h2 className="mt-3 font-display text-2xl font-extrabold tracking-tight text-[#111827] sm:text-3xl">
              Welcome to NEMESIS-X
            </h2>
            <p className="mt-1.5 text-sm text-[#64748B] sm:text-base">
              Your video intelligence workspace. Discover what matters.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/dashboard/new-analysis"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-sm font-semibold text-white shadow-md shadow-[#2563EB]/20 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-[#2563EB]/25"
            >
              <UploadCloud className="h-4 w-4" />
              <span>Upload Video</span>
            </Link>

            <Link
              to="/dashboard/live"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-[#111827] shadow-2xs transition-all hover:border-[#2563EB]/30 hover:bg-[#F5F8FC] hover:text-[#2563EB]"
            >
              <Radio className="h-4 w-4 text-[#7C3AED]" />
              <span>Start Live Monitoring</span>
            </Link>
          </div>
        </div>
      </motion.section>

      {/* 4. Analytics Cards */}
      <section aria-labelledby="analytics-heading">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="analytics-heading" className="font-display text-base font-bold text-[#111827]">
            Overview Metrics
          </h2>
          <span className="font-mono text-[11px] text-[#64748B]">
            Illustrative sample counts (not live AI results)
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {DEMO_DASHBOARD_STATS.map((stat, index) => (
            <StatCard key={stat.id} stat={stat} index={index} />
          ))}
        </div>
      </section>

      {/* 5. Recent Analyses & 6. Recent Events */}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <RecentAnalyses items={filteredAnalyses} />
        </div>
        <div className="lg:col-span-5">
          <RecentEvents items={filteredEvents} />
        </div>
      </div>

      {/* 7. Quick Actions */}
      <QuickActions actions={DEMO_QUICK_ACTIONS} />
    </div>
  )
}
