import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-center">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/10 text-amber-400">
        <AlertTriangle className="h-5 w-5" />
      </div>
      <h1 className="mt-3 text-2xl font-bold text-white">404 — Page Not Found</h1>
      <p className="mt-2 text-sm text-slate-400">The requested route does not exist.</p>
      <Link
        to="/"
        className="mt-4 inline-block rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-400"
      >
        Back to Home
      </Link>
    </section>
  )
}
