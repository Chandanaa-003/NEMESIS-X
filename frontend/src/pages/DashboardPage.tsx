import { LayoutDashboard } from 'lucide-react'
import { apiClient } from '../services/api'

export function DashboardPage() {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-6">
      <div className="flex items-center gap-2 text-cyan-400">
        <LayoutDashboard className="h-5 w-5" />
        <span className="text-xs font-medium tracking-wider uppercase">Route: /dashboard</span>
      </div>
      <h1 className="mt-2 text-2xl font-bold text-white">Dashboard</h1>
      <p className="mt-2 text-sm text-slate-400">
        Dashboard placeholder. API base URL configured: <code>{apiClient.defaults.baseURL}</code>
      </p>
    </section>
  )
}
