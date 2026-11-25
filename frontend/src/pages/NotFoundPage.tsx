import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
      <section className="rounded-2xl border border-slate-200 bg-[#F5F8FC] p-10 text-center shadow-xs">
        <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-amber-100 text-amber-600">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <h1 className="mt-4 font-display text-2xl font-bold text-[#111827]">
          404 — Page Not Found
        </h1>
        <p className="mt-2 text-sm text-[#64748B]">The requested route does not exist.</p>
        <Link
          to="/"
          className="mt-5 inline-block rounded-lg bg-[#2563EB] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1D4ED8]"
        >
          Back to Home
        </Link>
      </section>
    </div>
  )
}
