import { LogIn } from 'lucide-react'
import { Link } from 'react-router-dom'

export function LoginPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
      <section className="rounded-2xl border border-slate-200 bg-[#F5F8FC] p-8 shadow-xs">
        <div className="flex items-center gap-2 text-[#2563EB]">
          <LogIn className="h-5 w-5" />
          <span className="font-mono text-xs font-semibold tracking-wider uppercase">
            Route: /login
          </span>
        </div>
        <h1 className="mt-3 font-display text-2xl font-bold text-[#111827]">Login</h1>
        <p className="mt-2 text-sm text-[#64748B]">
          Authentication view placeholder. Account login will be connected in a later chunk.
        </p>
        <div className="mt-5 flex gap-3">
          <Link
            to="/"
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-[#111827] hover:bg-slate-50"
          >
            Back to Home
          </Link>
        </div>
      </section>
    </div>
  )
}
